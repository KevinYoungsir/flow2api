"""Verify the deployed UI/API without printing or saving Railway variable values.

Default checks are read-only. --prepare-restart temporarily changes the error ban
threshold and saves only the original/expected integers; --verify-restart checks
that persisted value and restores the original setting.

Credentials are the Railway bootstrap variables. If credentials were rotated in
the admin UI after initialization, these variables may no longer match the DB.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

import httpx


def load_credentials(args):
    executable = shutil.which("railway")
    if not executable:
        raise RuntimeError("Railway CLI unavailable")
    result = subprocess.run(
        [executable, "variable", "list", "--project", args.project,
         "--environment", args.environment, "--service", args.service, "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if result.returncode:
        raise RuntimeError("Railway variable lookup failed (details suppressed)")
    values = json.loads(result.stdout)
    credentials = {name: values.get(name, "") for name in (
        "FLOW2API_ADMIN_USERNAME", "FLOW2API_ADMIN_PASSWORD", "FLOW2API_API_KEY"
    )}
    if not all(credentials.values()):
        raise RuntimeError("Required bootstrap variables absent; values suppressed")
    return credentials


def runtime_start(args):
    """Read Linux PID 1 start time; a marker cannot pass without an actual restart."""
    executable = shutil.which("railway")
    result = subprocess.run(
        [executable, "ssh", "--project", args.project, "--environment", args.environment,
         "--service", args.service, "--", "cat", "/proc/1/stat"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if result.returncode:
        raise RuntimeError("Unable to read runtime start marker")
    for line in result.stdout.splitlines():
        if line.startswith("1 ("):
            # stat field 22; fields after the command's closing ')' start at 3.
            return line.rsplit(") ", 1)[1].split()[19]
    raise RuntimeError("Runtime start marker missing")


def require(condition, name):
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    if not condition:
        raise RuntimeError("Acceptance check failed: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--project", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--service", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-restart", action="store_true")
    mode.add_argument("--verify-restart", action="store_true")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--wait-seconds", type=int, default=0, help="Wait for readiness during a rollout (0..300)")
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 300:
        parser.error("--wait-seconds must be 0..300")
    if (args.prepare_restart or args.verify_restart) and not args.state:
        parser.error("Restart checks require --state (non-secret JSON file)")
    values = load_credentials(args)
    require(len(values["FLOW2API_API_KEY"].strip()) >= 32, "configured API key meets length requirement")
    with httpx.Client(base_url=args.base_url.rstrip("/"), trust_env=False,
                      timeout=30, follow_redirects=False) as client:
        deadline = time.monotonic() + args.wait_seconds
        while True:
            try:
                health = client.get("/health", timeout=5)
                ready = health.status_code == 200 and health.json() == {"status": "ok"}
            except (httpx.TransportError, ValueError):
                ready = False
            if ready or time.monotonic() >= deadline:
                break
            time.sleep(2)
        require(ready, "public readiness")
        require(client.get("/manage").status_code == 302, "management page requires session")
        invalid = client.post("/api/admin/login", json={"username": values["FLOW2API_ADMIN_USERNAME"], "password": "incorrect-deployment-check"})
        require(invalid.status_code == 401, "incorrect admin password rejected")
        response = client.post("/api/admin/login", json={"username": values["FLOW2API_ADMIN_USERNAME"], "password": values["FLOW2API_ADMIN_PASSWORD"]})
        require(response.status_code == 200, "administrator login")
        cookie = response.headers.get("set-cookie", "").lower()
        require(all(flag in cookie for flag in ("secure", "httponly", "samesite=lax")), "secure admin cookie")
        session = response.json()["token"]
        for endpoint in ("/manage", "/test", "/api/tokens", "/api/logs", "/api/stats"):
            require(client.get(endpoint).status_code == 200, "authenticated " + endpoint)
        models = client.get("/v1/models", headers={"Authorization": "Bearer " + values["FLOW2API_API_KEY"]})
        require(models.status_code == 200 and bool(models.json().get("data")), "API key and nonempty model catalog")
        require(client.get("/v1/models", headers={"Authorization": "Bearer incorrect-deployment-check"}).status_code == 401, "incorrect API key rejected")
        settings = client.get("/api/admin/config").json()
        if args.prepare_restart:
            original = int(settings["error_ban_threshold"])
            expected = original + 1 if original < 9 else 3
            # Refuse to overwrite an unfinished earlier rehearsal.
            args.state.parent.mkdir(parents=True, exist_ok=True)
            with args.state.open("x", encoding="utf-8") as output:
                json.dump({"original": original, "expected": expected, "runtime_start": runtime_start(args), "project": args.project,
                           "environment": args.environment, "service": args.service}, output)
            saved = client.post("/api/admin/config", json={"error_ban_threshold": expected})
            require(saved.status_code == 200, "temporary persistence marker written")
            require(client.get("/api/admin/config").json()["error_ban_threshold"] == expected, "configuration read after write")
        if args.verify_restart:
            marker = json.loads(args.state.read_text(encoding="utf-8"))
            require(all(marker[key] == getattr(args, key) for key in ("project", "environment", "service")), "persistence marker matches target")
            require(runtime_start(args) != marker["runtime_start"], "process restart independently verified")
            require(settings["error_ban_threshold"] == marker["expected"], "configuration survived cloud restart")
            restored = client.post("/api/admin/config", json={"error_ban_threshold": marker["original"]})
            require(restored.status_code == 200, "original configuration restored")
            require(client.get("/api/admin/config").json()["error_ban_threshold"] == marker["original"], "restored configuration reread")
            marker["verified"] = True
            args.state.write_text(json.dumps(marker), encoding="utf-8")
        require(client.post("/api/admin/logout").status_code == 200, "administrator logout")
        client.cookies.clear()
        require(client.get("/api/stats", headers={"Authorization": "Bearer " + session}).status_code == 401, "logged-out session revoked")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
        # Never print exceptions whose request/response may contain secrets.
        print("FAIL: cloud acceptance stopped (" + type(exc).__name__ + "); variable values suppressed")
        raise SystemExit(1)
