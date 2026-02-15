"""System prompt and message builders for Claude recipe formatting."""

import json

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
- Non-liquid ingredients: keep quantity in cups if originally in cups
- Convert all other imperial units to metric:
  - Under 1 L / 1 kg: convert to millilitres (ml) and grams (g), round UP to the \
nearest 5
  - Over 1 L / 1 kg: convert to litres (L) and kilograms (kg), round UP to the \
nearest 0.05
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


def build_url_message(recipe_data: dict) -> list:
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


def build_image_message(images: list[dict]) -> list:
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


def build_raw_html_message(html: str, url: str) -> list:
    """Build Claude user message for fallback raw/extracted HTML content."""
    return [{
        "type": "text",
        "text": (
            f"I extracted the following content from {url}. "
            f"Please find and reformat the recipe:\n\n{html}"
        ),
    }]
