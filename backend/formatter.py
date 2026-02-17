"""Claude API call for recipe formatting with retry logic.

Includes system prompt and message builders (merged from prompts.py).
"""

import json
import logging
import os
import time

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250929"
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

- Preserve the original recipe's intent and proportions
- If information is missing (prep_time, cook_time, servings), use an empty string
- Do not invent or add ingredients/steps that are not in the original
- Return ONLY the JSON object, no markdown fencing or extra text
"""


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
        user_content = _build_image_message(images)
    elif recipe_data and "raw_html" in recipe_data:
        user_content = _build_raw_html_message(
            recipe_data["raw_html"], recipe_data.get("url", source_url or "unknown")
        )
    elif recipe_data:
        user_content = _build_url_message(recipe_data)
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
            raise RuntimeError(
                "ANTHROPIC_API_KEY is invalid. Check your API key at "
                "https://console.anthropic.com/"
            )
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
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found. Set it in .env or as an environment variable."
        )
    return anthropic.Anthropic()


def _fix_json_newlines(text: str) -> str:
    """Escape literal newlines that appear inside JSON string values."""
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch == "\n":
            result.append("\\n")
            continue
        result.append(ch)
    return "".join(result)


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
    except json.JSONDecodeError:
        # Claude sometimes outputs literal newlines inside JSON string values.
        # Fix by escaping newlines that appear inside quoted strings.
        fixed = _fix_json_newlines(cleaned)
        try:
            data = json.loads(fixed)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse Claude response as JSON: {e}\n{text}"
            )

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


def _build_url_message(recipe_data: dict) -> list:
    """Build Claude user message for a URL-scraped structured recipe."""
    parts = [f"Recipe: {recipe_data.get('title', 'Unknown')}"]

    if recipe_data.get("ingredients"):
        parts.append("\nIngredients:\n" + "\n".join(recipe_data["ingredients"]))

    if recipe_data.get("directions"):
        parts.append("\nDirections:\n" + "\n".join(recipe_data["directions"]))

    for field in ("prep_time", "cook_time", "total_time", "servings"):
        if recipe_data.get(field):
            parts.append(f"\n{field.replace('_', ' ').title()}: {recipe_data[field]}")

    text = "\n".join(parts)
    return [{"type": "text", "text": f"Please reformat this recipe:\n\n{text}"}]


def _build_image_message(images: list[dict]) -> list:
    """Build Claude user message for image-based recipe(s)."""
    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["media_type"],
                "data": img["data"],
            },
        })
    content.append({
        "type": "text",
        "text": "Please extract and reformat the recipe from the image(s) above.",
    })
    return content


def _build_raw_html_message(html: str, url: str) -> list:
    """Build Claude user message for fallback raw/extracted HTML content."""
    return [{
        "type": "text",
        "text": (
            f"I extracted the following content from {url}. "
            f"Please find and reformat the recipe:\n\n{html}"
        ),
    }]
