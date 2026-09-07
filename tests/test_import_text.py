"""Behavioral coverage for pasted-text recipe imports."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import api, services
from backend.source_errors import SourceError


def _recipe(name: str) -> dict[str, str]:
    return {
        "name": name,
        "ingredients": "1 carrot",
        "directions": "Mix.",
        "prep_time": "",
        "cook_time": "",
        "servings": "",
        "notes": "",
    }


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


def test_blank_text_is_rejected_before_gemini(monkeypatch: pytest.MonkeyPatch):
    called = False

    def fail_if_called(**_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(services, "format_recipe", fail_if_called)

    with pytest.raises(SourceError) as raised:
        asyncio.run(services.import_from_text("   \n\t"))

    assert raised.value.code == "invalid_source_text"
    assert raised.value.status_code == 400
    assert called is False


def test_exact_text_limit_is_accepted_with_plural_result(
    monkeypatch: pytest.MonkeyPatch,
):
    source = "x" * services.MAX_SOURCE_TEXT_CHARS
    monkeypatch.setattr(
        services,
        "format_recipe",
        lambda **_kwargs: {"recipes": [_recipe("Pasta"), _recipe("Sauce")]},
    )

    result = asyncio.run(services.import_from_text(source))

    assert [recipe["name"] for recipe in result["recipes"]] == ["Pasta", "Sauce"]
    assert all(recipe["source"] == "" for recipe in result["recipes"])
    assert all(recipe["source_url"] == "" for recipe in result["recipes"])


def test_over_limit_text_is_rejected_before_gemini(monkeypatch: pytest.MonkeyPatch):
    called = False

    def fail_if_called(**_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(services, "format_recipe", fail_if_called)

    with pytest.raises(SourceError) as raised:
        asyncio.run(
            services.import_from_text("x" * (services.MAX_SOURCE_TEXT_CHARS + 1))
        )

    assert raised.value.code == "source_too_large"
    assert raised.value.status_code == 413
    assert called is False


def test_text_route_returns_only_plural_recipes(
    import_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def import_batch(_text: str):
        return {
            "recipes": [
                {**_recipe("Soup"), "source_url": "", "source": ""},
                {**_recipe("Bread"), "source_url": "", "source": ""},
            ]
        }

    monkeypatch.setattr(api, "import_from_text", import_batch)

    response = import_client.post("/api/import/text", json={"text": "Recipe text"})

    assert response.status_code == 200
    assert [recipe["name"] for recipe in response.json()["recipes"]] == [
        "Soup",
        "Bread",
    ]
    assert set(response.json()) == {"recipes"}


@pytest.mark.parametrize(
    "error",
    [
        SourceError(
            "invalid_source_text",
            "Paste the recipe text before importing it.",
            400,
        ),
        SourceError(
            "source_too_large",
            "Recipe text is limited to 100000 characters.",
            413,
        ),
    ],
)
def test_text_route_preserves_safe_source_errors(
    import_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error: SourceError,
):
    async def fail_import(_text: str):
        raise error

    monkeypatch.setattr(api, "import_from_text", fail_import)

    response = import_client.post("/api/import/text", json={"text": "Recipe text"})

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}
