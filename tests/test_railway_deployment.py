import asyncio
import os
import secrets
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock

from src.core.auth import AuthManager
from src.core.config import Config
from src.core.database import Database
from scripts.sqlite_backup import snapshot


def clean_environment():
    return {k: v for k, v in os.environ.items() if not k.startswith(("FLOW2API_", "RAILWAY_")) and k != "PORT"}


class RailwayConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, clean_environment(), clear=True)
        self.env.start()
        self.settings = Config()

    def tearDown(self):
        self.env.stop()

    def test_port_env_precedes_toml_and_forces_public_bind(self):
        self.settings._config["server"] = {"host": "127.0.0.1", "port": 8000}
        self.assertEqual(self.settings.server_host, "127.0.0.1")
        with patch.dict(os.environ, {"PORT": "9123"}):
            self.assertEqual(self.settings.server_port, 9123)
            self.assertEqual(self.settings.server_host, "0.0.0.0")
        for value in ("0", "-1", "65536", "abc", ""):
            with self.subTest(value=value), patch.dict(os.environ, {"PORT": value}):
                with self.assertRaises(ValueError):
                    self.settings.validate_runtime()

    def test_production_requires_explicit_https_origins(self):
        with patch.dict(os.environ, {"FLOW2API_ENV": "production"}):
            with self.assertRaises(ValueError):
                self.settings.validate_runtime()
            for origin in ("*", "http://example.com", "https://example.com/path", "https://user:secret@example.com", "https://example.com?key=secret"):
                with self.subTest(origin=origin), patch.dict(os.environ, {"FLOW2API_PUBLIC_BASE_URL": origin, "FLOW2API_CORS_ORIGINS": origin}):
                    with self.assertRaises(ValueError):
                        self.settings.validate_runtime()
            with patch.dict(os.environ, {"FLOW2API_PUBLIC_BASE_URL": "https://socool.xin", "FLOW2API_CORS_ORIGINS": "https://socool.xin"}):
                self.settings.validate_runtime()

    def test_production_rejects_sample_credentials(self):
        with patch.dict(os.environ, {"FLOW2API_ENV": "production"}):
            for password, key in (("admin", "han1234"), (secrets.token_urlsafe(24), "han1234"), ("admin", secrets.token_urlsafe(32))):
                with self.assertRaises(ValueError):
                    self.settings.validate_credentials("admin", password, key)
            with self.assertRaises(ValueError):
                self.settings.validate_credentials("admin", AuthManager.hash_password("admin"), secrets.token_urlsafe(32), stored=True)

    def test_railway_cannot_disable_production_or_omit_volume(self):
        with patch.dict(os.environ, {"RAILWAY_PROJECT_ID": "test-project", "FLOW2API_ENV": "development", "FLOW2API_PUBLIC_BASE_URL": "https://socool.xin", "FLOW2API_CORS_ORIGINS": "https://socool.xin"}):
            self.assertTrue(self.settings.production)
            with self.assertRaisesRegex(ValueError, "Volume"):
                self.settings.validate_runtime()
            with patch.dict(os.environ, {"RAILWAY_VOLUME_MOUNT_PATH": str(self.settings.data_dir)}):
                self.settings.validate_runtime()

    def test_bootstrap_env_and_invalid_numbers(self):
        key = secrets.token_urlsafe(32)
        with patch.dict(os.environ, {"FLOW2API_API_KEY": key, "FLOW2API_CACHE_ENABLED": "true", "FLOW2API_VIDEO_TIMEOUT": "600"}):
            settings = Config()
            self.assertEqual(settings.api_key, key)
            self.assertTrue(settings.cache_enabled)
            self.assertEqual(settings.video_timeout, 600)
        for name, value in (("FLOW2API_CACHE_ENABLED", "maybe"), ("FLOW2API_VIDEO_TIMEOUT", "-1")):
            with patch.dict(os.environ, {name: value}), self.assertRaises(ValueError):
                Config()

    def test_production_disables_debug_even_if_database_enabled_it(self):
        self.settings.set_debug_enabled(True)
        with patch.dict(os.environ, {"FLOW2API_ENV": "production"}):
            self.assertFalse(self.settings.debug_enabled)

    def test_public_result_url_ignores_forwarded_headers(self):
        from starlette.requests import Request
        from src.api.routes import _get_request_base_url
        from src.services.generation_handler import GenerationHandler
        request = Request({"type": "http", "scheme": "http", "path": "/", "headers": [(b"host", b"internal:8000"), (b"x-forwarded-host", b"spoofed.example"), (b"x-forwarded-proto", b"http")]})
        with patch.dict(os.environ, {"FLOW2API_PUBLIC_BASE_URL": "https://socool.xin"}):
            base = _get_request_base_url(request)
            self.assertEqual(base, "https://socool.xin")
            handler = object.__new__(GenerationHandler)
            self.assertEqual(handler._get_base_url({"base_url": "http://internal:8000"}), "https://socool.xin")

    def test_health_initialization_and_admin_session_expiry(self):
        from fastapi.testclient import TestClient
        from src.main import app, db
        from src.api import admin
        client = TestClient(app, base_url="https://socool.xin")
        was_ready = app.state.ready
        try:
            # Deliberately omit lifespan; no database initialization in this probe.
            app.state.ready = False
            self.assertEqual(client.get("/health").status_code, 503)
            app.state.ready = True
            with patch.object(db, "check_ready", AsyncMock(side_effect=OSError("private database details"))):
                response = client.get("/health")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"status": "unavailable"})
            admin.active_admin_tokens["expired-test-session"] = 0
            self.assertFalse(admin.is_admin_session_token_valid("expired-test-session"))
            self.assertNotIn("expired-test-session", admin.active_admin_tokens)
        finally:
            app.state.ready = was_ready
            client.close()


class RailwayDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp.name) / "flow.db"))
        self.env = patch.dict(os.environ, clean_environment(), clear=True)
        self.env.start()

    async def asyncTearDown(self):
        self.env.stop()
        self.temp.cleanup()

    async def test_bootstrap_migration_preserves_admin_and_data(self):
        settings = Config()
        settings._config["global"].update(admin_password=secrets.token_urlsafe(24), api_key=secrets.token_urlsafe(32))
        await self.db.init_db()
        await self.db.init_config_from_toml(settings.get_raw_config())
        await self.db.hash_legacy_admin_password()
        before = await self.db.get_admin_config()
        self.assertTrue(AuthManager.is_password_hash(before.password))
        await self.db.update_admin_config(error_ban_threshold=8)
        with patch.dict(os.environ, {"FLOW2API_ENV": "production", "FLOW2API_ADMIN_PASSWORD": "admin", "FLOW2API_API_KEY": "han1234"}):
            second = Config()
            await self.db.validate_startup_credentials(second)
            await self.db.check_and_migrate_db(second.get_raw_config())
        after = await self.db.get_admin_config()
        self.assertEqual(after.password, before.password)
        self.assertEqual(after.api_key, before.api_key)
        self.assertEqual(after.error_ban_threshold, 8)
        await self.db.check_ready()

    async def test_existing_insecure_database_fails_without_overwrite(self):
        await self.db.init_db()
        await self.db.init_config_from_toml(Config().get_raw_config())
        with patch.dict(os.environ, {"FLOW2API_ENV": "production", "FLOW2API_ADMIN_PASSWORD": secrets.token_urlsafe(24), "FLOW2API_API_KEY": secrets.token_urlsafe(32)}):
            with self.assertRaises(ValueError):
                await self.db.validate_startup_credentials(Config())
        self.assertEqual((await self.db.get_admin_config()).password, "admin")

    async def test_health_does_not_recreate_missing_database(self):
        with self.assertRaises(sqlite3.OperationalError):
            await self.db.check_ready()
        self.assertFalse(Path(self.db.db_path).exists())

    async def test_health_detects_locked_database(self):
        await self.db.init_db()
        await self.db.init_config_from_toml(Config().get_raw_config())
        with closing(sqlite3.connect(self.db.db_path)) as locked:
            locked.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError):
                await self.db.check_ready()
            locked.rollback()

    async def test_snapshot_includes_wal_and_restores_to_new_path(self):
        source = Path(self.db.db_path)
        backup = source.with_name("backup.db")
        restored = source.with_name("restored.db")
        with closing(sqlite3.connect(source)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE preserved (value TEXT)")
            conn.execute("INSERT INTO preserved VALUES ('retained')")
            conn.commit()
            snapshot(source, backup)
            with self.assertRaises(FileExistsError):
                snapshot(source, backup)
            snapshot(backup, restored)
        with closing(sqlite3.connect(restored)) as conn:
            self.assertEqual(conn.execute("SELECT value FROM preserved").fetchone(), ("retained",))
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone(), ("ok",))
