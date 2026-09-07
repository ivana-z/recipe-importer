"""Regression coverage for the Google OAuth callback boundary."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import auth_routes
from backend.database import Base, get_db

JWT_SECRET = "test-jwt-secret-with-at-least-32-bytes"


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://testserver/api/auth/callback")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("FRONTEND_URL", "http://frontend.test")
    monkeypatch.setenv("ALLOWED_EMAILS", "cook@example.com")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(auth_routes.auth_router)

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    exchange_calls: list[str] = []

    def exchange_code(code: str) -> dict[str, str]:
        exchange_calls.append(code)
        return {"email": "cook@example.com", "sub": "google-user-1"}

    monkeypatch.setattr(auth_routes, "exchange_code_for_userinfo", exchange_code)
    monkeypatch.setattr(auth_routes, "create_jwt", lambda _user_id, _email: "application-jwt")

    with TestClient(app) as client:
        yield client, exchange_calls

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_matching_state_redirects_with_fragment_and_clears_cookie(auth_client):
    client, exchange_calls = auth_client

    login_response = client.get("/api/auth/login")
    assert login_response.status_code == 200
    state = login_response.json()["state"]
    login_cookie = login_response.headers["set-cookie"].lower()
    assert "oauth_state=" in login_cookie
    assert "httponly" in login_cookie
    assert "samesite=lax" in login_cookie
    assert "max-age=600" in login_cookie
    assert "secure" not in login_cookie

    callback_response = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )

    assert callback_response.status_code == 302
    redirect = urlsplit(callback_response.headers["location"])
    assert redirect.query == ""
    assert parse_qs(redirect.fragment) == {"token": ["application-jwt"]}
    assert exchange_calls == ["google-code"]
    cleared_cookie = callback_response.headers["set-cookie"].lower()
    assert "oauth_state=" in cleared_cookie
    assert "max-age=0" in cleared_cookie


def test_state_cookie_is_secure_outside_dev_mode(
    auth_client, monkeypatch: pytest.MonkeyPatch
):
    client, _ = auth_client
    monkeypatch.delenv("DEV_MODE")

    response = client.get("/api/auth/login")

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("invalid_state", ["missing", "mismatched", "expired"])
def test_invalid_state_is_rejected_before_google_exchange(auth_client, invalid_state):
    client, exchange_calls = auth_client

    if invalid_state == "missing":
        callback_state = "unbound-state"
    else:
        login_response = client.get("/api/auth/login")
        callback_state = login_response.json()["state"]
        if invalid_state == "mismatched":
            callback_state = f"{callback_state}-wrong"
        else:
            expired_cookie = jwt.encode(
                {
                    "state": callback_state,
                    "purpose": "google_oauth_state",
                    "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
                },
                JWT_SECRET,
                algorithm="HS256",
            )
            client.cookies.set(
                "oauth_state",
                expired_cookie,
                path="/api/auth/callback",
            )

    response = client.get(
        "/api/auth/callback",
        params={"code": "must-not-be-exchanged", "state": callback_state},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired OAuth state"}
    assert exchange_calls == []
