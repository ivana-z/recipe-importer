"""Gemini API call for recipe formatting with retry logic."""

import base64
import json
import logging
import os
import time

from google import genai
from google.genai import types

from .prompts import (
    SYSTEM_PROMPT,
    build_image_message,
    build_raw_html_message,
    build_text_message,
    build_url_message,
)
from .source_errors import SourceError

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3
BASE_DELAY = 2  # seconds
MAX_SOURCE_TEXT_CHARS = 100_000
MAX_RECIPES_PER_SOURCE = 10


def format_recipe(
    recipe_data: dict | None = None,
    images: list[dict] | None = None,
    text: str | None = None,
    text_label: str = "Pasted text",
    source_url: str | None = None,
) -> dict:
    """Format one source into a validated recipe batch using Gemini.

    Accepts structured recipe data, image parts, pasted or extracted text, or raw
    HTML fallback data. Returns ``{"recipes": [...]}``.
    """
    if text is not None:
        if not text.strip():
            raise ValueError("Must provide non-empty text")
        _ensure_source_size(text)
        contents = build_text_message(text, source_label=text_label)
    elif images:
        contents = _image_msg_to_parts(build_image_message(images))
    elif recipe_data and "raw_html" in recipe_data:
        raw_html = recipe_data["raw_html"]
        if not isinstance(raw_html, str):
            raise ValueError("Raw HTML source must be text")
        _ensure_source_size(raw_html)
        contents = build_raw_html_message(
            raw_html, recipe_data.get("url", source_url or "unknown")
        )
    elif recipe_data:
        _ensure_source_size(json.dumps(recipe_data, ensure_ascii=False, default=str))
        contents = build_url_message(recipe_data)
    else:
        raise ValueError("Must provide either recipe_data, images, or text")

    client = _get_client()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Gemini API call attempt %d/%d", attempt, MAX_RETRIES)
            response = client.models.generate_content(
                model=MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
                contents=contents,
            )
            text_response = response.text
            logger.debug("Gemini response: %s", text_response)
            return _parse_response(text_response)
        except SourceError:
            raise
        except Exception as e:
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))
                logger.debug("API error: %s. Retrying in %ds...", e, delay)
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"Gemini API call failed after {MAX_RETRIES} attempts: {e}"
                ) from e


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Set it in .env or as an environment variable."
        )
    return genai.Client(api_key=api_key)


def _image_msg_to_parts(msg: list) -> list:
    """Convert neutral image message format to Gemini Parts."""
    parts = []
    for item in msg:
        if item["type"] == "image":
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(item["data"]),
                    mime_type=item["media_type"],
                )
            )
        elif item["type"] == "text":
            parts.append(types.Part.from_text(text=item["text"]))
    return parts


def _parse_response(text: str) -> dict:
    """Parse and validate Gemini's bounded recipe batch."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Failed to parse Gemini response as JSON") from error

    if not isinstance(data, dict):
        raise RuntimeError("Gemini response must be a JSON object")
    if set(data) != {"recipes", "has_more"}:
        raise RuntimeError("Gemini response must contain only recipes and has_more")

    recipes = data.get("recipes")
    has_more = data.get("has_more")
    if not isinstance(recipes, list) or not isinstance(has_more, bool):
        raise RuntimeError("Gemini response must contain recipes and has_more")

    if has_more or len(recipes) > MAX_RECIPES_PER_SOURCE:
        raise SourceError(
            "too_many_recipes",
            f"This source contains more than {MAX_RECIPES_PER_SOURCE} recipes. Use a smaller source.",
            422,
        )
    if not recipes:
        raise SourceError(
            "no_recipe_found",
            "No complete recipe was found in this source.",
            422,
        )

    normalized_recipes: list[dict[str, str]] = []
    required_fields = ("name", "ingredients", "directions")
    optional_fields = ("prep_time", "cook_time", "servings", "notes")

    for index, recipe in enumerate(recipes):
        if not isinstance(recipe, dict):
            raise RuntimeError(f"Gemini recipe {index + 1} must be an object")

        for field in required_fields:
            value = recipe.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(
                    f"Gemini recipe {index + 1} has an invalid {field}"
                )

        normalized = {field: recipe[field] for field in required_fields}
        for field in optional_fields:
            value = recipe.get(field, "")
            if not isinstance(value, str):
                raise RuntimeError(
                    f"Gemini recipe {index + 1} has an invalid {field}"
                )
            normalized[field] = value
        normalized_recipes.append(normalized)

    return {"recipes": normalized_recipes}


def apply_source_metadata(batch: dict, *, source_url: str, source: str) -> dict:
    """Apply source metadata to every recipe in a validated batch."""
    return {
        "recipes": [
            {**recipe, "source_url": source_url, "source": source}
            for recipe in batch["recipes"]
        ]
    }


def _ensure_source_size(text: str) -> None:
    if len(text) > MAX_SOURCE_TEXT_CHARS:
        raise SourceError(
            "source_too_large",
            f"Recipe text is limited to {MAX_SOURCE_TEXT_CHARS} characters.",
            413,
        )
