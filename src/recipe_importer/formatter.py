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
    build_url_message,
)

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3
BASE_DELAY = 2  # seconds


def format_recipe(
    recipe_data: dict | None = None,
    images: list[dict] | None = None,
    source_url: str | None = None,
) -> dict:
    """Format a recipe using Gemini.

    Accepts either structured recipe_data (from URL scraping),
    images (from photo input), or raw HTML fallback data.

    Returns a dict with: name, ingredients, directions, prep_time,
    cook_time, servings, notes.
    """
    client = _get_client()

    if images:
        contents = _image_msg_to_parts(build_image_message(images))
    elif recipe_data and "raw_html" in recipe_data:
        contents = build_raw_html_message(
            recipe_data["raw_html"], recipe_data.get("url", source_url or "unknown")
        )
    elif recipe_data:
        contents = build_url_message(recipe_data)
    else:
        raise ValueError("Must provide either recipe_data or images")

    last_error = None
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
            text = response.text
            logger.debug("Gemini response: %s", text)
            return _parse_response(text)
        except Exception as e:
            last_error = e
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
    """Parse Gemini's JSON response into a recipe dict."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to parse Gemini response as JSON: {e}\n{text}"
        )

    required_fields = ["name", "ingredients", "directions"]
    for field in required_fields:
        if field not in data:
            raise RuntimeError(f"Gemini response missing required field: {field}")

    return {
        "name": data["name"],
        "ingredients": data["ingredients"],
        "directions": data["directions"],
        "prep_time": data.get("prep_time", ""),
        "cook_time": data.get("cook_time", ""),
        "servings": data.get("servings", ""),
        "notes": data.get("notes", ""),
    }
