"""Route-level source-error contract coverage for URL imports."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import api
from backend.source_errors import SourceError


@pytest.fixture
def import_client():
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: SimpleNamespace(
        paprika_email=None,
        paprika_password_enc=None,
    )

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "url",
    [
        "ftp://recipes.example.test/recipe",
        "https://user:password@recipes.example.test/recipe",
        "https:///missing-host",
    ],
    ids=["unsupported-scheme", "embedded-credentials", "missing-host"],
)
def test_invalid_url_returns_the_source_error_contract(import_client, url: str):
    response = import_client.post("/api/import/url", json={"url": url})

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "invalid_source_url",
            "message": "Enter a valid HTTP or HTTPS URL.",
        }
    }


@pytest.mark.parametrize(
    "error",
    [
        SourceError(
            "unsafe_source_url",
            "This URL points to an unsafe network destination.",
            400,
        ),
        SourceError(
            "source_fetch_failed",
            "The recipe page could not be fetched.",
            502,
        ),
    ],
)
def test_expected_source_errors_use_structured_route_detail(
    import_client, monkeypatch: pytest.MonkeyPatch, error: SourceError
):
    async def raise_source_error(_url: str):
        raise error

    monkeypatch.setattr(api, "import_from_url", raise_source_error)

    response = import_client.post(
        "/api/import/url", json={"url": "https://recipes.example.test/recipe"}
    )

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}


def test_unexpected_url_import_errors_remain_generic_and_logged(
    import_client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    async def fail_import(_url: str):
        raise RuntimeError("private upstream diagnostic")

    monkeypatch.setattr(api, "import_from_url", fail_import)

    response = import_client.post(
        "/api/import/url", json={"url": "https://recipes.example.test/recipe"}
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Import failed"}
    assert "URL import failed" in caplog.text
    assert "private upstream diagnostic" not in response.text
