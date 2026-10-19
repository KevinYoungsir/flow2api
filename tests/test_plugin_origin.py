"""Production CSRF boundaries for the header-authenticated Chrome updater."""

import os
import secrets
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.api import admin


class PluginOriginTests(unittest.TestCase):
    def setUp(self):
        self.origin = "chrome-extension://" + "a" * 32
        self.connection_token = secrets.token_urlsafe(32)
        self.payload = {
            "google_cookies": "OSID=synthetic; SID=synthetic",
            "login_account": "account@example.com",
            "protocol_mode": "protocol",
        }
        self.environment = patch.dict(os.environ, {
            "FLOW2API_ENV": "production",
            "FLOW2API_PUBLIC_BASE_URL": "https://socool.xin",
            "FLOW2API_CORS_ORIGINS": "https://socool.xin",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        plugin_config = patch.object(admin.db, "get_plugin_config", AsyncMock(
            return_value=SimpleNamespace(connection_token=self.connection_token)
        ))
        plugin_config.start()
        self.addCleanup(plugin_config.stop)
        token_rows = patch.object(admin.db, "get_all_tokens_with_stats", AsyncMock(return_value=[]))
        token_rows.start()
        self.addCleanup(token_rows.stop)
        # No lifespan or real upstream calls; this suite tests the HTTP/auth boundary.
        self.client = TestClient(app, base_url="https://socool.xin")
        self.addCleanup(self.client.close)

    def test_missing_and_invalid_connection_tokens_are_rejected(self):
        for endpoint, payload in (("/api/plugin/check-tokens", {}),
                                  ("/api/plugin/update-token", self.payload)):
            for authorization in (None, "Bearer incorrect-plugin-token"):
                with self.subTest(endpoint=endpoint, authorization=bool(authorization)):
                    headers = {"Origin": self.origin, "Sec-Fetch-Site": "cross-site"}
                    if authorization:
                        headers["Authorization"] = authorization
                    response = self.client.post(endpoint, json=payload, headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json(), {"detail": "Invalid connection token"})

    def test_valid_connection_token_reaches_sync_validation(self):
        headers = {"Origin": self.origin, "Authorization": "Bearer " + self.connection_token,
                   "Sec-Fetch-Site": "cross-site"}
        response = self.client.post("/api/plugin/check-tokens", json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "tokens": []})
        with patch.object(admin.token_manager.flow_client, "st_to_at", AsyncMock(
            side_effect=ValueError("Invalid synthetic cookie fixture")
        )) as validate:
            response = self.client.post("/api/plugin/update-token", json=self.payload, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Google Cookie", response.json()["detail"])
        validate.assert_awaited_once_with("", google_cookies=self.payload["google_cookies"])

    def test_admin_session_cannot_replace_plugin_connection_token(self):
        session = secrets.token_urlsafe(32)
        with patch.dict(admin.active_admin_tokens, {session: time.time() + 600}):
            response = self.client.post("/api/plugin/check-tokens", json={}, headers={
                "Origin": self.origin, "Cookie": "admin_session=" + session,
            })
        self.assertEqual(response.status_code, 401)

    def test_other_admin_writes_still_reject_extension_origin(self):
        session = secrets.token_urlsafe(32)
        with patch.dict(admin.active_admin_tokens, {session: time.time() + 600}):
            for endpoint in ("/api/plugin/config", "/api/admin/config", "/api/login"):
                with self.subTest(endpoint=endpoint):
                    response = self.client.post(endpoint, json={}, headers={
                        "Origin": self.origin, "Cookie": "admin_session=" + session,
                        "Authorization": "Bearer " + self.connection_token,
                    })
                    self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.options("/api/plugin/update-token", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST",
        }).status_code, 400)


if __name__ == "__main__":
    unittest.main()
