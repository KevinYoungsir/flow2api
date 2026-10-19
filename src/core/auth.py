"""Authentication module"""

import bcrypt
import secrets
import re
from typing import Optional
from fastapi import Header, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import config

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


class AuthManager:
    """Authentication manager"""

    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """Verify API key"""
        return bool(api_key) and secrets.compare_digest(api_key.encode(), config.api_key.encode())

    @staticmethod
    def verify_admin(username: str, password: str) -> bool:
        """Verify admin credentials"""
        # Compare with current config (which may be from database or config file)
        stored = config.admin_password
        password_ok = (AuthManager.verify_password(password, stored) if AuthManager.is_password_hash(stored)
                       else secrets.compare_digest(password.encode(), stored.encode()))
        return secrets.compare_digest(username.encode(), config.admin_username.encode()) and password_ok

    @staticmethod
    def is_password_hash(value: str) -> bool:
        return bool(re.fullmatch(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", value or ""))

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password"""
        if len(password.encode()) > 72:
            return False
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except (ValueError, TypeError):
            return False


async def verify_api_key_header(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Verify API key from Authorization header"""
    api_key = credentials.credentials
    if not AuthManager.verify_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


async def verify_api_key_flexible(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
    x_goog_api_key: Optional[str] = Header(None, alias="x-goog-api-key"),
    key: Optional[str] = Query(None),
) -> str:
    """Verify API key from Authorization header, x-goog-api-key header, or key query param."""
    api_key = None

    if credentials is not None:
        api_key = credentials.credentials
    elif x_goog_api_key:
        api_key = x_goog_api_key
    elif key:
        api_key = key

    if not api_key or not AuthManager.verify_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key
