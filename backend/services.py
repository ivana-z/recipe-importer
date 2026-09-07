"""Orchestration layer: wraps existing pipeline modules for async web use."""

from __future__ import annotations

import asyncio
import base64
import logging

from .formatter import MAX_SOURCE_TEXT_CHARS, apply_source_metadata, format_recipe
from .paprika import PaprikaClient, build_paprika_json
from .scraper import scrape_url
from .social_extractor import classify_social_url, import_social_url
from .source_errors import SourceError

logger = logging.getLogger(__name__)
MAX_IMAGE_COUNT = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def import_from_url(url: str) -> dict:
    """Scrape a URL and format the recipe via Gemini."""
    social_platform = classify_social_url(url)
    if social_platform is not None:
        return await asyncio.to_thread(import_social_url, url, social_platform)

    recipe_data = await asyncio.to_thread(scrape_url, url)

    source_name = recipe_data.pop("site_name", None) or ""

    formatted = await asyncio.to_thread(
        format_recipe, recipe_data=recipe_data, source_url=url
    )

    return apply_source_metadata(formatted, source_url=url, source=source_name)


async def import_from_images(image_files: list[tuple[str, bytes]]) -> dict:
    """Process uploaded images through Gemini for recipe extraction."""
    if len(image_files) > MAX_IMAGE_COUNT:
        raise SourceError(
            "too_many_images",
            f"Upload no more than {MAX_IMAGE_COUNT} images at a time.",
            413,
        )
    oversized = next(
        (filename for filename, data in image_files if len(data) > MAX_IMAGE_BYTES),
        None,
    )
    if oversized is not None:
        raise SourceError(
            "image_too_large",
            f"Each image must be {MAX_IMAGE_BYTES // (1024 * 1024)} MB or smaller.",
            413,
        )

    images = []
    for filename, data in image_files:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpeg"
        media_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "image/jpeg")

        images.append(
            {
                "type": "image",
                "media_type": media_type,
                "data": base64.b64encode(data).decode("ascii"),
            }
        )

    formatted = await asyncio.to_thread(format_recipe, images=images)

    return apply_source_metadata(formatted, source_url="", source="")


async def import_from_text(text: str) -> dict:
    """Process pasted recipe text through Gemini."""
    cleaned_text = text.strip()
    if not cleaned_text:
        raise SourceError(
            "invalid_source_text",
            "Paste the recipe text before importing it.",
            400,
        )
    if len(text) > MAX_SOURCE_TEXT_CHARS:
        raise SourceError(
            "source_too_large",
            f"Recipe text is limited to {MAX_SOURCE_TEXT_CHARS} characters.",
            413,
        )

    formatted = await asyncio.to_thread(
        format_recipe,
        text=cleaned_text,
        text_label="Pasted text",
    )

    return apply_source_metadata(formatted, source_url="", source="")


async def get_categories(
    paprika_email: str | None = None,
    paprika_password_enc: str | None = None,
) -> list[dict]:
    """Fetch categories from Paprika API.

    Returns a list of {name, uid, children} dicts representing the category hierarchy.
    """
    client = await asyncio.to_thread(PaprikaClient, paprika_email, paprika_password_enc)

    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), auth=client._auth) as http:
        response = await http.get(
            "https://www.paprikaapp.com/api/v1/sync/categories/"
        )
        response.raise_for_status()
        entries = response.json()["result"]

    # Each entry has uid, name, parent_uid, order_flag
    # Build hierarchy: group children under parents
    by_uid = {}
    for entry in entries:
        by_uid[entry["uid"]] = entry

    top_level = []
    children_map: dict[str, list[dict]] = {}

    for entry in entries:
        parent_uid = entry.get("parent_uid") or ""
        if parent_uid and parent_uid in by_uid:
            children_map.setdefault(parent_uid, []).append(
                {
                    "name": entry["name"],
                    "uid": entry["uid"],
                }
            )
        else:
            top_level.append(entry)

    result = []
    for entry in sorted(top_level, key=lambda e: e.get("order_flag", 0)):
        children = sorted(children_map.get(entry["uid"], []), key=lambda c: c["name"])
        result.append(
            {
                "name": entry["name"],
                "uid": entry["uid"],
                "children": children,
            }
        )

    return result


async def sync_recipe(
    name: str,
    source: str,
    source_url: str,
    categories: list[str],
    ingredients: str,
    directions: str,
    prep_time: str,
    cook_time: str,
    servings: str,
    notes: str,
    paprika_email: str | None = None,
    paprika_password_enc: str | None = None,
) -> str:
    """Build Paprika JSON and upload.

    Returns the recipe name.
    """
    recipe = {
        "name": name,
        "ingredients": ingredients,
        "directions": directions,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "servings": servings,
        "notes": notes,
    }

    paprika_data = build_paprika_json(
        recipe=recipe,
        source_url=source_url or None,
        source_name=source or None,
        categories=categories,
    )

    client = PaprikaClient(paprika_email, paprika_password_enc)
    await asyncio.to_thread(client.upload_recipe, paprika_data)

    return name
