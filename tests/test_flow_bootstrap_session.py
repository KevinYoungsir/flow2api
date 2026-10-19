"""Flow bootstrap/RPC session continuity, using synthetic cookies and no network."""

import json
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from curl_cffi import CurlInfo
from curl_cffi.requests.cookies import CurlMorsel

from src.services.flow_client import FlowClient
from src.services.protocol_login import _cookie_jar


class FlowBootstrapSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original = json.dumps([
            {"name": "OSID", "value": "synthetic-session-old", "domain": "flow.google.com",
             "hostOnly": True, "path": "/", "secure": True, "httpOnly": True},
            {"name": "SID", "value": "synthetic-account", "domain": ".google.com",
             "hostOnly": False, "path": "/", "secure": True},
            {"name": "removed", "value": "synthetic-deleted", "domain": "flow.google.com", "path": "/"},
            {"name": "project_only", "value": "synthetic-project", "domain": "flow.google.com", "path": "/projects"},
            {"name": "account_only", "value": "synthetic-private", "domain": "accounts.google.com", "path": "/"},
        ])
        updated = self.original.replace("synthetic-session-old", "synthetic-session-new")
        jar = _cookie_jar(updated)
        jar.clear("flow.google.com", "/", "removed")
        lines = [
            (("#HttpOnly_" if cookie.has_nonstandard_attr("HttpOnly") else "")
             + CurlMorsel.from_cookiejar_cookie(cookie).to_curl_format()).encode()
            for cookie in jar
        ]
        self.response = types.SimpleNamespace(
            text=('boq_labs-ai-sandbox-frontend_20261007.14_p0 '
                  '{"FdrFJe":"123","SNlM0e":"synthetic-xsrf","oPEP7c":"account@example.com"}'),
            url="https://flow.google.com/projects", status_code=200,
            infos={CurlInfo.COOKIELIST: lines},
        )
        self.session = MagicMock()
        self.session.__aenter__.return_value = self.session
        self.session.get = AsyncMock(return_value=self.response)
        factory = patch("src.services.flow_frontend.AsyncSession", return_value=self.session)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = FlowClient(None)
        self.client._make_text_request = AsyncMock(return_value=json.dumps(
            [["wrb.fr", "nzlxg", json.dumps([100])]]
        ))

    async def call_credits(self):
        return await self.client.get_credits(google_cookies=self.original)

    def assert_fresh_scoped_rpc_cookies(self):
        header = self.client._make_text_request.call_args.kwargs["headers"]["Cookie"]
        self.assertIn("OSID=synthetic-session-new", header)
        self.assertNotIn("synthetic-session-old", header)
        self.assertNotIn("synthetic-deleted", header)
        self.assertNotIn("synthetic-project", header)
        self.assertNotIn("synthetic-private", header)
        self.assertIn("SID=synthetic-account", header)

    async def test_rpc_retains_rotation_deletion_and_cookie_scope(self):
        self.assertEqual((await self.call_credits())["credits"], 100)
        self.assert_fresh_scoped_rpc_cookies()
        # A real cookie jar follows redirect/Set-Cookie rules without a stale
        # manually supplied Cookie header overriding the jar.
        self.assertNotIn("Cookie", self.session.get.call_args.kwargs["headers"])
        self.assertIn("cookies", self.factory.call_args.kwargs)

    async def test_stream_chat_retains_the_same_session_updates(self):
        self.client._make_text_request.return_value = "[]"
        self.client._extract_stream_chat_media_ids = Mock(return_value=[])
        await self.client._call_flow_stream_chat(
            project_id="fixture-project", prompt="synthetic fixture",
            recaptcha_token="synthetic-fixture", session_id="fixture-session",
            cookie_header="", cookie_storage=self.original, timeout=10,
        )
        self.assert_fresh_scoped_rpc_cookies()

    async def test_upstream_rejection_remains_an_error_with_safe_context(self):
        self.client._make_text_request.return_value = json.dumps([
            ["er", "nzlxg", None, None, None, 401]
        ])
        with self.assertRaisesRegex(RuntimeError, "code=401") as caught:
            await self.call_credits()
        message = str(caught.exception)
        self.assertIn("page_identity=present", message)
        self.assertIn("cookies_changed=yes", message)
        for private in ("synthetic-session", "synthetic-account", "account@example.com", "synthetic-xsrf"):
            self.assertNotIn(private, message)

    async def test_redirect_to_login_is_rejected_before_rpc(self):
        self.response.url = "https://accounts.google.com/signin"
        with self.assertRaisesRegex(RuntimeError, "Flow 登录认证失败"):
            await self.call_credits()
        self.client._make_text_request.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
