"""Regression coverage for deployment version metadata."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import api


def test_version_endpoint_returns_railway_commit_subject_and_short_sha(monkeypatch):
    monkeypatch.setenv(
        "RAILWAY_GIT_COMMIT_MESSAGE",
        "Fix YouTube description extraction fallback\n\nAdditional context",
    )
    monkeypatch.setenv(
        "RAILWAY_GIT_COMMIT_SHA",
        "829dd4171f9c6d03249d3a843d5971c6c623be0e",
    )
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: SimpleNamespace()

    response = TestClient(app).get("/api/version")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Fix YouTube description extraction fallback",
        "commit_sha": "829dd41",
    }
