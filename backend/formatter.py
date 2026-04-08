"""Gemini API call for recipe formatting with retry logic.

Includes system prompt and message builders (merged from prompts.py).
"""

import base64
import json
import logging
import os
import time

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3
BASE_DELAY = 2  # seconds

SYSTEM_PROMPT = """\
You are a recipe editor. You receive recipe data (from a URL scrape or photos) and \
reformat it according to strict rules. Return ONLY valid JSON with these fields:
- "name": recipe title
- "ingredients": formatted ingredients text
- "directions": formatted directions text
- "prep_time": preparation time (e.g. "15 min") or ""
- "cook_time": cooking time (e.g. "30 min") or ""
- "servings": servings (e.g. "4 servings") or ""
- "notes": any additional notes or ""

## Ingredient Formatting Rules

- Each ingredient on its own line, no bullet points or numbering
- Format: quantity first, then ingredient name
- Never omit quantities — if the source provides a quantity for an ingredient, it must \
appear in the output; do not list ingredient names alone without their amount
- For multi-part recipes (marinade, sauce, dressing, etc.): list ingredients under \
each part title on its own line
- Abbreviations: use "tbsp" for tablespoons, "tsp" for teaspoons
- Show only ONE unit of measurement and quantity per ingredient
- Do NOT convert tbsp/tsp quantities to metric, EXCEPT for butter — always convert \
butter to grams
- Cups: keep cups as-is by default. ONLY convert cups to ml when the ingredient is \
a pourable liquid (water, milk, broth, stock, cream, juice, oil, wine, vinegar, \
soy sauce, etc.). Everything else stays in cups — this includes flour, sugar, herbs, \
leaves, oats, rice, nuts, cheese, breadcrumbs, chocolate chips, diced vegetables, \
and any other solid, dry, or non-pourable ingredient.
- Convert all other imperial units (oz, lb, fl oz, pints, quarts, gallons) to metric:
  - Under 1 L / 1 kg: convert to millilitres (ml) and grams (g), round UP to the \
nearest 5
  - Over 1 L / 1 kg: convert to litres (L) and kilograms (kg), round UP to the \
nearest 0.05
- Length: convert inches to metric. If the converted value is 20 mm or less, show \
in mm rounded UP to the nearest whole number. If over 20 mm, show in cm rounded UP \
to the nearest 0.5.
- Temperatures: Celsius only (°C). Delete any gas mark or Fahrenheit references. \
If only Fahrenheit is given, convert to Celsius.

## Direction Formatting Rules

- Structure into chapters with bold titles (e.g. **Soaking**, **Preparation**, \
**Cooking**)
- Convert any amounts/temperatures in directions using the same rules as ingredients
- Bold each ingredient name when it is first mentioned in a step, and include its \
quantity (e.g. "Add **200g flour** and mix")

## General

- Translate all content to English regardless of the source language
- Preserve the original recipe's intent and proportions
- If information is missing (prep_time, cook_time, servings), use an empty string
- Do not invent or add ingredients/steps that are not in the original
- Return ONLY the JSON object, no markdown fencing or extra text
"""

_RULES_REMINDER = (
    "Apply ALL formatting rules from your instructions without exception:\n"
    "- Translate all content to English\n"
    "- Ingredients: one per line, quantity first (never omit quantities), no bullets, "
    "correct abbreviations (tbsp/tsp), group multi-part recipes under section titles\n"
    "- Units: convert butter to grams; pourable liquids cups→ml; all other imperial "
    "(oz, lb, fl oz, pints, quarts, gallons) to metric (g/ml under 1kg/L, kg/L over); "
    "inches to mm/cm; Fahrenheit to Celsius only\n"
    "- Directions: use bold chapter titles (e.g. **Preparation**, **Cooking**); bold "
    "each ingredient name on first mention with its quantity\n"
    "- Return ONLY the JSON object, no markdown fencing or extra text"
)


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
        contents = _image_msg_to_parts(_build_image_message(images))
    elif recipe_data and "raw_html" in recipe_data:
        contents = _build_raw_html_message(
            recipe_data["raw_html"], recipe_data.get("url", source_url or "unknown")
        )
    elif recipe_data:
        contents = _build_url_message(recipe_data)
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


def _build_url_message(recipe_data: dict) -> str:
    parts = [f"Recipe: {recipe_data.get('title', 'Unknown')}"]

    if recipe_data.get("ingredients"):
        parts.append("\nIngredients:\n" + "\n".join(recipe_data["ingredients"]))

    if recipe_data.get("directions"):
        parts.append("\nDirections:\n" + "\n".join(recipe_data["directions"]))

    for field in ("prep_time", "cook_time", "total_time", "servings"):
        if recipe_data.get(field):
            parts.append(f"\n{field.replace('_', ' ').title()}: {recipe_data[field]}")

    text = "\n".join(parts)
    return f"Please reformat this recipe:\n\n{text}\n\n{_RULES_REMINDER}"


def _build_image_message(images: list[dict]) -> list:
    content = list(images)
    content.append({
        "type": "text",
        "text": f"Please extract and reformat the recipe from the image(s) above.\n\n{_RULES_REMINDER}",
    })
    return content


def _build_raw_html_message(html: str, url: str) -> str:
    return (
        f"I extracted the following content from {url}. "
        f"Please find and reformat the recipe:\n\n{html}\n\n{_RULES_REMINDER}"
    )
