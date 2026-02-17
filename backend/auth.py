"""Bearer token authentication for the web API."""

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_security = HTTPBearer()


def get_app_secret() -> str:
    secret = os.environ.get("APP_SECRET", "")
    if not secret:
        raise RuntimeError("APP_SECRET not set in environment")
    return secret


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """Dependency that validates the Bearer token against APP_SECRET."""
    if credentials.credentials != get_app_secret():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return credentials.credentials
