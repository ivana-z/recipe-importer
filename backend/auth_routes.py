"""Google OAuth2 callback routes."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .oauth import create_jwt, exchange_code_for_userinfo, get_google_auth_url

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/api/auth")


def _allowed_emails() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:5173")


@auth_router.get("/login")
def login():
    """Return Google OAuth2 consent URL and state token."""
    auth_url, state = get_google_auth_url()
    return {"auth_url": auth_url, "state": state}


@auth_router.get("/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Exchange OAuth code for user info, upsert user, redirect with JWT."""
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
    return RedirectResponse(url=f"{frontend_url}/?token={token}", status_code=302)
