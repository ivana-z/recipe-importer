"""Google OAuth2 helpers, JWT signing, and Fernet encryption."""

import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from cryptography.fernet import Fernet

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_JWT_ALGORITHM = "HS256"
_TOKEN_LIFETIME_DAYS = 30


def _client_id() -> str:
    v = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_ID not set")
    return v


def _client_secret() -> str:
    v = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_SECRET not set")
    return v


def _redirect_uri() -> str:
    v = os.environ.get("GOOGLE_REDIRECT_URI", "")
    if not v:
        raise RuntimeError("GOOGLE_REDIRECT_URI not set")
    return v


def _jwt_secret() -> str:
    v = os.environ.get("JWT_SECRET", "")
    if not v:
        raise RuntimeError("JWT_SECRET not set")
    return v


def _fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return Fernet(key.encode())


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_google_auth_url() -> tuple[str, str]:
    """Return (auth_url, state) for the Google OAuth2 consent page."""
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{_GOOGLE_AUTH_URL}?{query}", state


def exchange_code_for_userinfo(code: str) -> dict:
    """Exchange an OAuth authorization code for Google userinfo."""
    with httpx.Client(timeout=15) as client:
        token_resp = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "redirect_uri": _redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_jwt(user_id: int, email: str) -> str:
    """Sign a 30-day JWT for the given user."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=_TOKEN_LIFETIME_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT, raising jwt.PyJWTError on failure."""
    return jwt.decode(token, _jwt_secret(), algorithms=[_JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# Fernet encryption helpers
# ---------------------------------------------------------------------------

def encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext password, returning a URL-safe string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted password."""
    return _fernet().decrypt(ciphertext.encode()).decode()
