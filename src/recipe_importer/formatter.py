"""Claude API call for recipe formatting with retry logic."""

import json
import logging
import sys
import time

import anthropic

from .prompts import (
    SYSTEM_PROMPT,
    build_image_message,
    build_raw_html_message,
    build_url_message,
)

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250929"
MAX_RETRIES = 3
BASE_DELAY = 2  # seconds


def format_recipe(
    recipe_data: dict | None = None,
    images: list[dict] | None = None,
    source_url: str | None = None,
) -> dict:
    """Format a recipe using Claude.

    Accepts either structured recipe_data (from URL scraping),
    images (from photo input), or raw HTML fallback data.

    Returns a dict with: name, ingredients, directions, prep_time,
    cook_time, servings, notes.
    """
    client = _get_client()

    # Build the appropriate user message
    if images:
        user_content = build_image_message(images)
    elif recipe_data and "raw_html" in recipe_data:
        user_content = build_raw_html_message(
            recipe_data["raw_html"], recipe_data.get("url", source_url or "unknown")
        )
    elif recipe_data:
        user_content = build_url_message(recipe_data)
    else:
        raise ValueError("Must provide either recipe_data or images")

    # Call Claude with retries
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Claude API call attempt %d/%d", attempt, MAX_RETRIES)
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            text = response.content[0].text
            logger.debug("Claude response: %s", text)
            return _parse_response(text)
        except anthropic.AuthenticationError:
            _print_api_key_error()
            sys.exit(1)
        except anthropic.APIError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))
                logger.debug("API error: %s. Retrying in %ds...", e, delay)
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"Claude API call failed after {MAX_RETRIES} attempts: {e}"
                ) from e


def _get_client() -> anthropic.Anthropic:
    """Create an Anthropic client, checking for API key."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        _print_api_key_error()
        sys.exit(1)
    return anthropic.Anthropic()


def _parse_response(text: str) -> dict:
    """Parse Claude's JSON response into a recipe dict."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Claude response as JSON: {e}\n{text}")

    required_fields = ["name", "ingredients", "directions"]
    for field in required_fields:
        if field not in data:
            raise RuntimeError(f"Claude response missing required field: {field}")

    return {
        "name": data["name"],
        "ingredients": data["ingredients"],
        "directions": data["directions"],
        "prep_time": data.get("prep_time", ""),
        "cook_time": data.get("cook_time", ""),
        "servings": data.get("servings", ""),
        "notes": data.get("notes", ""),
    }


def _print_api_key_error():
    """Print a helpful error message for missing API key."""
    print(
        "\nError: ANTHROPIC_API_KEY not found.\n"
        "\n"
        "To set up your API key:\n"
        "  1. Get your key from https://console.anthropic.com/\n"
        "  2. Create a .env file in the project root:\n"
        "     ANTHROPIC_API_KEY=sk-ant-...\n"
        "\n"
        "Or set the environment variable directly:\n"
        "  export ANTHROPIC_API_KEY=sk-ant-...\n",
        file=sys.stderr,
    )
