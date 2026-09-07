"""Google OAuth2 callback routes."""

import logging
import os
import secrets
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .oauth import (
    create_jwt,
    create_oauth_state_cookie,
    decode_oauth_state_cookie,
    exchange_code_for_userinfo,
    get_google_auth_url,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/api/auth")
_OAUTH_STATE_COOKIE = "oauth_state"
_OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60
_OAUTH_STATE_COOKIE_PATH = "/api/auth/callback"


def _secure_cookies() -> bool:
    return not bool(os.environ.get("DEV_MODE"))




def _allowed_emails() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:5173")


@auth_router.get("/login")
def login():
    """Return Google OAuth2 consent URL and bind its state to the browser."""
    auth_url, state = get_google_auth_url()
    response = JSONResponse({"auth_url": auth_url, "state": state})
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=create_oauth_state_cookie(state),
        max_age=_OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=_secure_cookies(),
        samesite="lax",
        path=_OAUTH_STATE_COOKIE_PATH,
    )
    return response


@auth_router.get("/callback")
def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Exchange OAuth code for user info, upsert user, redirect with JWT."""
    state_cookie = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not state_cookie:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    try:
        expected_state = decode_oauth_state_cookie(state_cookie)
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    if not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    try:
        userinfo = exchange_code_for_userinfo(code)
    except Exception:
        logger.exception("OAuth code exchange failed")
        raise HTTPException(status_code=400, detail="OAuth exchange failed")

    email: str = userinfo.get("email", "").lower()
    google_sub: str = userinfo.get("sub", "")

    if not email or not google_sub:
        raise HTTPException(status_code=400, detail="Missing user info from Google")

    allowed = _allowed_emails()
    if allowed and email not in allowed:
        raise HTTPException(status_code=403, detail="Email not authorized")

    # Upsert user
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None:
        user = User(email=email, google_sub=google_sub)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.email != email:
        user.email = email
        db.commit()

    token = create_jwt(user.id, user.email)
    frontend_url = _frontend_url().rstrip("/")
    response = RedirectResponse(
        url=f"{frontend_url}/#{urlencode({'token': token})}",
        status_code=302,
    )
    response.delete_cookie(
        key=_OAUTH_STATE_COOKIE,
        httponly=True,
        secure=_secure_cookies(),
        samesite="lax",
        path=_OAUTH_STATE_COOKIE_PATH,
    )
    return response
