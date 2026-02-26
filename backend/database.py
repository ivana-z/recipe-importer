"""SQLAlchemy database setup."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "")

engine = create_engine(DATABASE_URL) if DATABASE_URL else None  # type: ignore[arg-type]
SessionLocal: sessionmaker[Session] | None = (
    sessionmaker(bind=engine) if engine else None
)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a database session."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables (idempotent). Call on startup."""
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
