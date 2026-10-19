"""Build/run/recreate an isolated Docker test service; no production resources used."""

import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(["docker", *args], cwd=ROOT, check=True, **kwargs)


def main():
    if not shutil.which("docker"):
        print("BLOCKED: Docker CLI not found; install/start Docker Desktop with Linux containers")
        return 2
    run("info", stdout=subprocess.DEVNULL)
    run("compose", "-f", "docker-compose.local.yml", "config", "--quiet")
    run("build", "-t", "flow2api:railway-check", ".")
    suffix = uuid.uuid4().hex[:12]
    name = "flow2api-check-" + suffix
    volume = "flow2api-check-data-" + suffix
    env = os.environ.copy()
    # Fresh synthetic secrets exist only for the isolated test container.
    env.update(FLOW2API_ADMIN_PASSWORD=secrets.token_urlsafe(24), FLOW2API_API_KEY=secrets.token_urlsafe(32))
    created_volume = False
    created_container = False
    try:
        run("volume", "create", volume, stdout=subprocess.DEVNULL)
        created_volume = True

        def start():
            nonlocal created_container
            run("run", "-d", "--name", name, "-p", "127.0.0.1::8000", "--mount", f"type=volume,source={volume},target=/app/data",
                "-e", "PORT=8000", "-e", "FLOW2API_ENV=production", "-e", "FLOW2API_ADMIN_USERNAME=deployment-check",
                "-e", "FLOW2API_ADMIN_PASSWORD", "-e", "FLOW2API_API_KEY", "-e", "FLOW2API_PUBLIC_BASE_URL=https://socool.xin",
                "-e", "FLOW2API_CORS_ORIGINS=https://socool.xin", "flow2api:railway-check", env=env, stdout=subprocess.DEVNULL)
            created_container = True
            address = run("port", name, "8000/tcp", capture_output=True, text=True).stdout.strip().splitlines()[0]
            client = httpx.Client(base_url="http://" + address, trust_env=False, timeout=10)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    if client.get("/health").status_code == 200:
                        return client
                except httpx.TransportError:
                    pass
                time.sleep(0.5)
            client.close()
            raise RuntimeError("Container readiness timeout")

        def login(client):
            response = client.post("/api/admin/login", json={"username": "deployment-check", "password": env["FLOW2API_ADMIN_PASSWORD"]})
            response.raise_for_status()
            return {"Authorization": "Bearer " + response.json()["token"]}

        with start() as client:
            headers = login(client)
            response = client.post("/api/admin/config", headers=headers, json={"error_ban_threshold": 9})
            response.raise_for_status()
            assert client.get("/v1/models", headers={"Authorization": "Bearer " + env["FLOW2API_API_KEY"]}).status_code == 200
        run("rm", "-f", name, stdout=subprocess.DEVNULL)
        created_container = False
        with start() as client:
            headers = login(client)
            assert client.get("/api/admin/config", headers=headers).json()["error_ban_threshold"] == 9
        print("PASS: Docker build, Compose config, readiness, auth, container recreation and Volume persistence")
        return 0
    finally:
        # Names are unique and created here; never delete user databases/volumes.
        if created_container:
            subprocess.run(["docker", "rm", "-f", name], cwd=ROOT, stdout=subprocess.DEVNULL, check=False)
        if created_volume:
            subprocess.run(["docker", "volume", "rm", volume], cwd=ROOT, stdout=subprocess.DEVNULL, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
