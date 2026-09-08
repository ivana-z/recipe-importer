"""Shared PWA prompt strings and message builders for Gemini formatting."""

SYSTEM_PROMPT = """\
You are a recipe editor. You receive recipe data from a URL, images, pasted text, \
or extracted social text and reformat every distinct complete recipe according to \
strict rules. Return ONLY valid JSON in this exact envelope:
{"recipes": [{"name": "...", "ingredients": "...", "directions": "...", \
"prep_time": "", "cook_time": "", "servings": "", "notes": ""}], "has_more": false}

Each recipe object has these fields:
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
- If an ingredient has no specific quantity (e.g. "q.b.", "quanto basta", "to taste", \
"as needed", "as desired"), list just the ingredient name with no quantity prefix
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
- Within each chapter, divide the directions into short, sequential, action-focused \
steps like a recipe card
- Write each step as its own paragraph, separated from the next step by a blank line. \
A step may contain multiple closely related sentences; never collapse all of a \
chapter's instructions into one paragraph
- Convert any amounts/temperatures in directions using the same rules as ingredients
- Bold each ingredient name when it is first mentioned in a step, and include its \
quantity (e.g. "Add **200g flour** and mix")

## General

- Translate all content to English regardless of the source language
- Preserve each original recipe's intent and proportions
- Return every distinct complete recipe found, up to 10 recipes
- Keep a component explicitly belonging to one recipe inside that recipe
- Do not merge distinct recipes, sauces, variants, or menu items
- Set "has_more" to true when the source appears to contain more than 10 recipes
- Never silently truncate recipes
- If information is missing (prep_time, cook_time, servings), use an empty string
- Do not invent or add ingredients/steps that are not in the original
- Return ONLY the JSON envelope, no markdown fencing or extra text
"""

_RULES_REMINDER = (
    "Apply ALL formatting rules from your instructions without exception:\n"
    "- Translate all content to English\n"
    "- Ingredients: one per line, quantity first, no bullets, correct abbreviations "
    "(tbsp/tsp), group multi-part recipes under section titles; omit quantity prefix "
    "when source says q.b./quanto basta/to taste/as needed\n"
    "- Units: convert butter to grams; pourable liquids cups→ml; all other imperial "
    "(oz, lb, fl oz, pints, quarts, gallons) to metric (g/ml under 1kg/L, kg/L over); "
    "inches to mm/cm; Fahrenheit to Celsius only\n"
    "- Directions: use bold chapter titles; divide each chapter into short, sequential, "
    "action-focused steps; put each step in its own paragraph separated by a blank line; "
    "never collapse a chapter into one paragraph; bold each ingredient name on first "
    "mention with its quantity\n"
    "- Return every distinct complete recipe in the required recipes/has_more JSON "
    "envelope; never merge or silently truncate recipes; no markdown fencing or extra text"
)


def build_url_message(recipe_data: dict) -> str:
    parts = [f"Recipe: {recipe_data.get('title', 'Unknown')}"]

    if recipe_data.get("ingredients"):
        parts.append("\nIngredients:\n" + "\n".join(recipe_data["ingredients"]))

    if recipe_data.get("directions"):
        parts.append("\nDirections:\n" + "\n".join(recipe_data["directions"]))

    for field in ("prep_time", "cook_time", "total_time", "servings"):
        if recipe_data.get(field):
            parts.append(f"\n{field.replace('_', ' ').title()}: {recipe_data[field]}")

    text = "\n".join(parts)
    return f"Please reformat every complete recipe in this source:\n\n{text}\n\n{_RULES_REMINDER}"



def build_image_message(images: list[dict]) -> list:
    content = list(images)
    content.append(
        {
            "type": "text",
            "text": f"Please extract and reformat every complete recipe from the image(s) above.\n\n{_RULES_REMINDER}",
        }
    )
    return content



def build_text_message(text: str, source_label: str = "Pasted text") -> str:
    label = source_label.strip().lower() or "text"
    return f"Please reformat every complete recipe from this {label}:\n\n{text}\n\n{_RULES_REMINDER}"



def build_raw_html_message(html: str, url: str) -> str:
    return (
        f"I extracted the following content from {url}. "
        f"Please find and reformat every complete recipe:\n\n{html}\n\n{_RULES_REMINDER}"
    )
