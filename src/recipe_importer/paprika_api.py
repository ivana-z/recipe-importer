"""Paprika 3 cloud sync client using the v1 API."""

import asyncio
import gzip
import json
import logging
import os
import sys

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.paprikaapp.com/api/v1"
_TIMEOUT = httpx.Timeout(30.0)
_MAX_CONCURRENT = 20


class PaprikaClient:
    """Client for the Paprika 3 cloud sync API (v1).

    Uses HTTP Basic Auth with Paprika account email/password.
    """

    def __init__(self):
        email = os.environ.get("PAPRIKA_EMAIL")
        password = os.environ.get("PAPRIKA_PASSWORD")
        if not email or not password:
            _print_credentials_error()
            sys.exit(1)
        self._auth = (email, password)

    def get_existing_names(self) -> set[str]:
        """Fetch all recipe names from Paprika cloud.

        Returns a set of lowercase recipe names for duplicate checking.
        """
        # Get list of all recipe UIDs
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(
                f"{BASE_URL}/sync/recipes/",
                auth=self._auth,
            )
            response.raise_for_status()
            entries = response.json()["result"]

        if not entries:
            return set()

        # Fetch all recipe details concurrently
        uids = [e["uid"] for e in entries]
        names = asyncio.run(self._fetch_names(uids))
        return {n.lower() for n in names}

    async def _fetch_names(self, uids: list[str]) -> list[str]:
        """Fetch names of non-trashed recipes concurrently."""
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=self._auth) as client:
            tasks = [self._fetch_one_name(client, semaphore, uid) for uid in uids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        names = []
        for r in results:
            if isinstance(r, Exception):
                logger.debug("Failed to fetch recipe: %s", r)
            elif isinstance(r, str):
                names.append(r)
        return names

    async def _fetch_one_name(
        self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, uid: str
    ) -> str | None:
        async with semaphore:
            response = await client.get(f"{BASE_URL}/sync/recipe/{uid}/")
            response.raise_for_status()
            recipe = response.json()["result"]
            if recipe.get("in_trash"):
                return None
            return recipe["name"]

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


def _print_credentials_error():
    """Print a helpful error message for missing Paprika credentials."""
    print(
        "\nError: Paprika credentials not found.\n"
        "\n"
        "To sync recipes to Paprika cloud, add to your .env file:\n"
        "  PAPRIKA_EMAIL=your@email.com\n"
        "  PAPRIKA_PASSWORD=your_password\n",
        file=sys.stderr,
    )
