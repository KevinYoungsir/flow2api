"""Real Uvicorn process tests, with isolated data and no upstream generation calls."""

import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing

import httpx


ROOT = Path(__file__).resolve().parents[1]


class DeploymentProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.password = secrets.token_urlsafe(24)
        self.api_key = secrets.token_urlsafe(32)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("FLOW2API_", "RAILWAY_"))}
        self.env.update({
            "PYTHONIOENCODING": "utf-8", "FLOW2API_ENV": "production",
            "FLOW2API_ADMIN_USERNAME": "deployment-test-admin",
            "FLOW2API_ADMIN_PASSWORD": self.password, "FLOW2API_API_KEY": self.api_key,
            "FLOW2API_PUBLIC_BASE_URL": "https://socool.xin",
            "FLOW2API_CORS_ORIGINS": "https://socool.xin",
            "FLOW2API_DATA_DIR": str(self.work / "data"),
            "FLOW2API_TMP_DIR": str(self.work / "cache"), "PORT": str(self.port),
        })
        self.process = None
        self.log = (self.work / "runtime.log").open("wb")
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", trust_env=False, timeout=10, follow_redirects=False)

    def tearDown(self):
        self.stop()
        self.client.close()
        self.log.close()
        self.temp.cleanup()

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
            self.process = None

    def start(self):
        # Launch from a different cwd: DB, cache and static paths must still align.
        self.process = subprocess.Popen([sys.executable, str(ROOT / "main.py")], cwd=self.work, env=self.env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail("Application exited before readiness (see isolated runtime log)")
            try:
                if self.client.get("/health").status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        self.fail("Application did not become ready")

    def login(self, password=None):
        return self.client.post("/api/login", json={"username": "deployment-test-admin", "password": password or self.password})

    def test_production_http_auth_configuration_cache_and_restart(self):
        self.start()
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        for page in ("/", "/login"):
            self.assertEqual(self.client.get(page).status_code, 200)
        for page in ("/manage", "/test"):
            self.assertEqual(self.client.get(page).status_code, 302)
        self.assertEqual(self.client.get("/static/manage.html").status_code, 404)
        self.assertEqual(self.client.get("/static/sponsors/fastaitoken-logo.png").status_code, 200)
        self.assertEqual(self.client.get("/metrics").status_code, 401)
        self.assertEqual(self.client.get("/docs").status_code, 404)
        for headers in ({}, {"Authorization": "Bearer incorrect"}):
            self.assertEqual(self.client.get("/v1/models", headers=headers).status_code, 401)
        result = self.client.get("/v1/models", headers={"Authorization": f"Bearer {self.api_key}"})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["data"])
        check_env = self.env.copy()
        check_env["FLOW2API_CHECK_API_KEY"] = self.api_key
        probe = subprocess.run([sys.executable, str(ROOT / "scripts/check_deployment.py"), str(self.client.base_url)], env=check_env, capture_output=True, text=True, timeout=25)
        self.assertEqual(probe.returncode, 0, probe.stdout)
        self.assertEqual(self.login("wrong-password").status_code, 401)
        cross_site = self.client.post("/api/login", json={"username": "x", "password": "x"}, headers={"Origin": "https://untrusted.example"})
        self.assertEqual(cross_site.status_code, 403)
        for origin, allowed in (("https://socool.xin", True), ("https://untrusted.example", False)):
            preflight = self.client.options("/api/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
            self.assertEqual(preflight.status_code, 200 if allowed else 400)
            self.assertEqual(preflight.headers.get("access-control-allow-origin"), origin if allowed else None)
        logged_in = self.login()
        self.assertEqual(logged_in.status_code, 200)
        cookie = logged_in.headers["set-cookie"].lower()
        for flag in ("httponly", "secure", "samesite=lax", "max-age=43200"):
            self.assertIn(flag, cookie)
        session = logged_in.json()["token"]
        admin_headers = {"Authorization": f"Bearer {session}"}
        page_headers = {"Cookie": f"admin_session={session}"}
        for page in ("/manage", "/test"):
            self.assertEqual(self.client.get(page, headers=page_headers).status_code, 200)
        for endpoint in ("/api/tokens", "/api/logs", "/api/stats"):
            self.assertEqual(self.client.get(endpoint, headers=admin_headers).status_code, 200)
        # A legacy DB address must not be displayed as effective when production
        # supplies the public origin used by generated result URLs.
        legacy_base = "http://127.0.0.1:8000"
        self.assertEqual(self.client.post("/api/cache/config", headers=admin_headers,
                                         json={"base_url": legacy_base}).status_code, 200)
        cache_settings = self.client.get("/api/cache/config", headers=admin_headers)
        self.assertEqual(cache_settings.status_code, 200)
        self.assertEqual(cache_settings.json()["config"]["base_url"], legacy_base)
        self.assertEqual(cache_settings.json()["config"]["effective_base_url"], "https://socool.xin")
        saved = self.client.post("/api/admin/config", headers=admin_headers, json={"error_ban_threshold": 7})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.get("/api/admin/config", headers=admin_headers).json()["error_ban_threshold"], 7)
        # A local fixture verifies file routing only; this is not generated media.
        cache = self.work / "cache" / "deployment-probe.txt"
        cache.write_text("routing-fixture", encoding="utf-8")
        self.assertEqual(self.client.get("/tmp/deployment-probe.txt").text, "routing-fixture")
        # Database lock must make health fail without leaking exception/account details.
        db_path = self.work / "data" / "flow.db"
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            health = self.client.get("/health")
            self.assertEqual(health.status_code, 503)
            self.assertEqual(health.json(), {"status": "unavailable"})
            connection.rollback()
        self.assertEqual(self.client.get("/health").status_code, 200)
        new_password = secrets.token_urlsafe(24)
        changed = self.client.post("/api/admin/password", headers=admin_headers, json={"old_password": self.password, "new_password": new_password})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get("/api/stats", headers=admin_headers).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        new_session = self.login(new_password).json()["token"]
        next_headers = {"Authorization": f"Bearer {new_session}"}
        self.assertEqual(self.client.post("/api/admin/apikey", headers=next_headers, json={"new_api_key": "han1234"}).status_code, 400)
        new_key = secrets.token_urlsafe(32)
        self.assertEqual(self.client.post("/api/admin/apikey", headers=next_headers, json={"new_api_key": new_key}).status_code, 200)
        self.stop()
        # Conflicting bootstrap values must not reset the persisted credentials.
        self.env.update(FLOW2API_ADMIN_PASSWORD="admin", FLOW2API_API_KEY="han1234")
        self.start()
        self.assertEqual(self.client.get("/api/stats", headers=next_headers).status_code, 401)
        session_after = self.login(new_password).json()["token"]
        after_headers = {"Authorization": f"Bearer {session_after}"}
        settings = self.client.get("/api/admin/config", headers=after_headers).json()
        self.assertEqual(settings["error_ban_threshold"], 7)
        self.assertEqual(settings["api_key"], new_key)
        self.assertEqual(self.client.get("/v1/models", headers={"Authorization": f"Bearer {self.api_key}"}).status_code, 401)
        self.assertEqual(self.client.get("/v1/models", headers={"Authorization": f"Bearer {new_key}"}).status_code, 200)
        self.assertEqual(self.client.post("/api/admin/logout", headers=after_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/stats", headers=after_headers).status_code, 401)
        self.stop()
        # Existing database must also boot with no bootstrap credentials at all.
        self.env.pop("FLOW2API_ADMIN_PASSWORD")
        self.env.pop("FLOW2API_API_KEY")
        self.start()
        self.assertEqual(self.login(new_password).status_code, 200)
        with closing(sqlite3.connect(db_path)) as connection:
            stored_password = connection.execute("SELECT password FROM admin_config WHERE id=1").fetchone()[0]
            self.assertTrue(stored_password.startswith("$2b$"))
        self.stop()
        runtime_log = (self.work / "runtime.log").read_text(encoding="utf-8")
        for secret in (self.password, self.api_key, new_password, new_key, session, new_session, session_after):
            self.assertNotIn(secret, runtime_log)

    def test_missing_credentials_fails_without_initializing_database(self):
        self.env.pop("FLOW2API_ADMIN_PASSWORD")
        self.env.pop("FLOW2API_API_KEY")
        self.process = subprocess.Popen([sys.executable, str(ROOT / "main.py")], cwd=self.work, env=self.env, stdout=self.log, stderr=subprocess.STDOUT)
        self.assertNotEqual(self.process.wait(timeout=20), 0)
        self.assertFalse((self.work / "data" / "flow.db").exists())
        self.assertIn("Production requires", (self.work / "runtime.log").read_text(encoding="utf-8"))
