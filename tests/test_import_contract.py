"""Public import API and service contract coverage."""

import asyncio

import pytest

from backend import main, services
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


def test_openapi_exposes_plural_imports_and_singular_sync():
    schema = main.app.openapi()

    assert {
        "/api/import/url",
        "/api/import/images",
        "/api/import/text",
        "/api/sync",
    }.issubset(schema["paths"])

    import_result = schema["components"]["schemas"]["ImportResult"]
    assert set(import_result["properties"]) == {"recipes"}
    assert import_result["required"] == ["recipes"]

    url_request = schema["components"]["schemas"]["ImportUrlRequest"]
    assert set(url_request["properties"]) == {"url"}

    image_operation = schema["paths"]["/api/import/images"]["post"]
    image_body_ref = image_operation["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]["$ref"]
    image_body = schema["components"]["schemas"][image_body_ref.rsplit("/", 1)[-1]]
    assert set(image_body["properties"]) == {"images"}

    sync_request = schema["components"]["schemas"]["SyncRequest"]
    assert "recipes" not in sync_request["properties"]
    assert "name" in sync_request["properties"]


def test_conventional_url_applies_source_metadata_to_every_recipe(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(services, "classify_social_url", lambda _url: None)
    monkeypatch.setattr(
        services,
        "scrape_url",
        lambda _url: {
            "title": "Dinner",
            "ingredients": ["1 carrot"],
            "directions": ["Mix"],
            "site_name": "Example Kitchen",
        },
    )
    monkeypatch.setattr(
        services,
        "format_recipe",
        lambda **_kwargs: {
            "recipes": [_recipe("Soup"), _recipe("Bread")]
        },
    )

    result = asyncio.run(
        services.import_from_url("https://recipes.example.test/dinner")
    )

    assert [recipe["name"] for recipe in result["recipes"]] == ["Soup", "Bread"]
    assert all(recipe["source"] == "Example Kitchen" for recipe in result["recipes"])
    assert all(
        recipe["source_url"] == "https://recipes.example.test/dinner"
        for recipe in result["recipes"]
    )


def test_image_limits_accept_the_documented_boundaries(
    monkeypatch: pytest.MonkeyPatch,
):
    formatter_calls: list[dict] = []
    monkeypatch.setattr(
        services,
        "format_recipe",
        lambda **kwargs: formatter_calls.append(kwargs)
        or {"recipes": [_recipe("Photo recipe")]},
    )
    files = [("large.jpg", b"x" * services.MAX_IMAGE_BYTES)]
    files.extend(
        (f"page-{index}.jpg", b"x")
        for index in range(1, services.MAX_IMAGE_COUNT)
    )

    result = asyncio.run(services.import_from_images(files))

    assert [recipe["name"] for recipe in result["recipes"]] == ["Photo recipe"]
    assert len(formatter_calls) == 1


def test_image_count_limit_rejects_before_formatter(
    monkeypatch: pytest.MonkeyPatch,
):
    formatter_calls: list[dict] = []
    monkeypatch.setattr(
        services,
        "format_recipe",
        lambda **kwargs: formatter_calls.append(kwargs),
    )
    files = [
        (f"page-{index}.jpg", b"x")
        for index in range(services.MAX_IMAGE_COUNT + 1)
    ]

    with pytest.raises(SourceError) as raised:
        asyncio.run(services.import_from_images(files))

    assert raised.value.code == "too_many_images"
    assert raised.value.status_code == 413
    assert formatter_calls == []


def test_per_image_limit_rejects_before_formatter(
    monkeypatch: pytest.MonkeyPatch,
):
    formatter_calls: list[dict] = []
    monkeypatch.setattr(
        services,
        "format_recipe",
        lambda **kwargs: formatter_calls.append(kwargs),
    )

    with pytest.raises(SourceError) as raised:
        asyncio.run(
            services.import_from_images(
                [("too-large.jpg", b"x" * (services.MAX_IMAGE_BYTES + 1))]
            )
        )

    assert raised.value.code == "image_too_large"
    assert raised.value.status_code == 413
    assert formatter_calls == []
