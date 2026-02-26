"""Paprika recipe builder and cloud sync client."""

import gzip
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.paprikaapp.com/api/v1"
_TIMEOUT = httpx.Timeout(30.0)


def build_paprika_json(
    recipe: dict,
    source_url: str | None = None,
    source_name: str | None = None,
    categories: list[str] | None = None,
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
        "image_url": "",
        "photo": "",
        "photo_hash": "",
        "photo_large": None,
        "photo_url": "",
        "photo_data": "",
        "scale": "",
        "categories": categories or [],
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


class PaprikaClient:
    """Client for the Paprika 3 cloud sync API (v1).

    Uses HTTP Basic Auth with Paprika account email/password.
    Accepts explicit credentials (from per-user DB record) or falls back to env vars.
    """

    def __init__(self, email: str | None = None, password_enc: str | None = None):
        if email and password_enc:
            from .oauth import decrypt_password
            self._auth = (email, decrypt_password(password_enc))
        else:
            env_email = os.environ.get("PAPRIKA_EMAIL")
            env_password = os.environ.get("PAPRIKA_PASSWORD")
            if not env_email or not env_password:
                raise RuntimeError(
                    "Paprika credentials not found. Set PAPRIKA_EMAIL and "
                    "PAPRIKA_PASSWORD in .env or as environment variables."
                )
            self._auth = (env_email, env_password)

    def upload_recipe(self, recipe_data: dict) -> None:
        """Upload a recipe to Paprika cloud.

        Args:
            recipe_data: Full Paprika JSON recipe dict (with uid, name, etc.)
        """
        uid = recipe_data["uid"]
        url = f"{BASE_URL}/sync/recipe/{uid}/"

        # Gzip-compress the JSON payload
        json_bytes = json.dumps(recipe_data, ensure_ascii=False).encode("utf-8")
        compressed = gzip.compress(json_bytes)

        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                url,
                auth=self._auth,
                files={"data": ("file", compressed)},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("result") is not True:
                raise RuntimeError(f"Upload failed: {result}")

        logger.debug("Uploaded recipe %s (%s) to Paprika cloud", uid, recipe_data.get("name"))
