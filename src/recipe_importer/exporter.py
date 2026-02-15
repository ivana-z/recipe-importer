"""Export formatted recipes to .paprikarecipe files (gzipped JSON)."""

import gzip
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path.home() / "paprika_recipes"


def export_recipe(
    recipe: dict,
    source_url: str | None = None,
    source_name: str | None = None,
    photo_data: str | None = None,
    image_url: str | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Export a recipe dict to a .paprikarecipe file.

    Returns the path to the created file.
    """
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    paprika_data = _build_paprika_json(recipe, source_url, source_name, photo_data, image_url)
    filename = _unique_filename(output_dir, recipe["name"])
    output_path = output_dir / filename

    json_bytes = json.dumps(paprika_data, ensure_ascii=False).encode("utf-8")
    with gzip.open(output_path, "wb") as f:
        f.write(json_bytes)

    return output_path


def _build_paprika_json(
    recipe: dict,
    source_url: str | None,
    source_name: str | None,
    photo_data: str | None,
    image_url: str | None,
) -> dict:
    """Build the full Paprika JSON schema."""
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    source = source_name or ""

    data = {
        "uid": uid,
        "name": recipe["name"],
        "ingredients": recipe["ingredients"],
        "directions": recipe["directions"],
        "description": "",
        "notes": recipe.get("notes", ""),
        "nutritional_info": "",
        "prep_time": recipe.get("prep_time", ""),
        "cook_time": recipe.get("cook_time", ""),
        "total_time": "",
        "servings": recipe.get("servings", ""),
        "difficulty": "",
        "source": source,
        "source_url": source_url or "",
        "image_url": image_url or "",
        "photo": "",
        "photo_hash": "",
        "photo_large": None,
        "photo_url": "",
        "photo_data": photo_data or "",
        "scale": "",
        "categories": [],
        "rating": 0,
        "in_trash": False,
        "is_pinned": False,
        "on_favorites": False,
        "on_grocery_list": False,
        "created": now,
    }

    # Hash is SHA-256 of the JSON content (without the hash field)
    content_json = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["hash"] = hashlib.sha256(content_json.encode("utf-8")).hexdigest().upper()

    return data


def _slugify(name: str) -> str:
    """Convert a recipe name to a filename-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "recipe"


def _unique_filename(output_dir: Path, recipe_name: str) -> str:
    """Generate a unique filename, adding numeric suffix if needed."""
    base = _slugify(recipe_name)
    filename = f"{base}.paprikarecipe"

    if not (output_dir / filename).exists():
        return filename

    counter = 2
    while True:
        filename = f"{base}-{counter}.paprikarecipe"
        if not (output_dir / filename).exists():
            return filename
        counter += 1
