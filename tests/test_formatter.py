"""Observable batch-contract coverage for Gemini formatting."""

import json
from types import SimpleNamespace

import pytest

from backend import formatter
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


def _format_response(monkeypatch: pytest.MonkeyPatch, payload: object) -> dict:
    class Models:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(text=json.dumps(payload))

    monkeypatch.setattr(
        formatter,
        "_get_client",
        lambda: SimpleNamespace(models=Models()),
    )
    monkeypatch.setattr(formatter.time, "sleep", lambda _delay: None)
    return formatter.format_recipe(text="Recipe source")


@pytest.mark.parametrize("count", [1, 3, formatter.MAX_RECIPES_PER_SOURCE])
def test_formatter_accepts_complete_bounded_batches(
    monkeypatch: pytest.MonkeyPatch,
    count: int,
):
    recipes = [_recipe(f"Recipe {index}") for index in range(count)]

    result = _format_response(
        monkeypatch,
        {"recipes": recipes, "has_more": False},
    )

    assert [recipe["name"] for recipe in result["recipes"]] == [
        recipe["name"] for recipe in recipes
    ]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"recipes": [], "has_more": False}, "no_recipe_found"),
        ({"recipes": [_recipe("Recipe")], "has_more": True}, "too_many_recipes"),
        (
            {
                "recipes": [
                    _recipe(f"Recipe {index}")
                    for index in range(formatter.MAX_RECIPES_PER_SOURCE + 1)
                ],
                "has_more": False,
            },
            "too_many_recipes",
        ),
    ],
)
def test_formatter_rejects_empty_or_over_limit_batches(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
    code: str,
):
    with pytest.raises(SourceError) as raised:
        _format_response(monkeypatch, payload)

    assert raised.value.code == code
    assert raised.value.status_code == 422


def test_formatter_rejects_entire_batch_when_one_recipe_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
):
    malformed = _recipe("Broken")
    malformed["ingredients"] = ""

    with pytest.raises(RuntimeError):
        _format_response(
            monkeypatch,
            {"recipes": [_recipe("Valid"), malformed], "has_more": False},
        )


def test_formatter_rejects_extra_batch_envelope_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    with pytest.raises(RuntimeError):
        _format_response(
            monkeypatch,
            {
                "recipes": [_recipe("Recipe")],
                "has_more": False,
                "summary": "unexpected",
            },
        )


def test_formatter_rejects_extracted_text_over_limit_before_client_creation(
    monkeypatch: pytest.MonkeyPatch,
):
    client_created = False

    def create_client():
        nonlocal client_created
        client_created = True

    monkeypatch.setattr(formatter, "_get_client", create_client)

    with pytest.raises(SourceError) as raised:
        formatter.format_recipe(
            recipe_data={
                "raw_html": "x" * (formatter.MAX_SOURCE_TEXT_CHARS + 1),
                "url": "https://recipes.example.test/large",
            }
        )

    assert raised.value.code == "source_too_large"
    assert client_created is False
