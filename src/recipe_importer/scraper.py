"""URL fetching and recipe scraping with recipe-scrapers + trafilatura fallback."""

import base64
import logging

import httpx
from recipe_scrapers import scrape_html

import trafilatura

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def scrape_url(url: str) -> dict:
    """Scrape a recipe from a URL.

    Tries recipe-scrapers first for structured data.
    Falls back to trafilatura for raw content extraction.

    Uses a single HTTP client so the image download shares
    cookies/session from the initial page fetch.

    Returns a dict with either structured recipe fields or {"raw_html": ...}.
    May include "photo_data" (base64) if a photo was found.
    """
    with httpx.Client(
        timeout=_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        html = _fetch_html(client, url)

        # Try structured extraction first
        try:
            recipe_data = _extract_structured(html, url)
            logger.debug("Structured extraction succeeded for %s", url)
            photo_data = _download_photo(client, recipe_data.get("image"))
            if photo_data:
                recipe_data["photo_data"] = photo_data
            return recipe_data
        except Exception as e:
            logger.debug("Structured extraction failed: %s", e)

        # Fallback: extract main content with trafilatura
        main_content = trafilatura.extract(html, include_comments=False, include_tables=True)
        if main_content:
            logger.debug("Trafilatura extraction succeeded for %s", url)
            return {"raw_html": main_content, "url": url}

        # Last resort: send the raw HTML
        logger.debug("All extraction methods limited, sending raw HTML")
        return {"raw_html": html, "url": url}


def _fetch_html(client: httpx.Client, url: str) -> str:
    """Fetch HTML content from a URL."""
    response = client.get(url)
    response.raise_for_status()
    return response.text


def _extract_structured(html: str, url: str) -> dict:
    """Extract structured recipe data using recipe-scrapers."""
    scraper = scrape_html(html=html, org_url=url)
    data = {
        "title": scraper.title(),
        "ingredients": scraper.ingredients(),
        "directions": scraper.instructions_list(),
        "prep_time": _safe_call(scraper.prep_time),
        "cook_time": _safe_call(scraper.cook_time),
        "total_time": _safe_call(scraper.total_time),
        "servings": _safe_call(scraper.yields),
        "image": _safe_call(scraper.image),
        "site_name": _safe_call(scraper.site_name),
    }
    # Require at least a title and some content
    if not data["title"] or (not data["ingredients"] and not data["directions"]):
        raise ValueError("Insufficient structured data extracted")
    return data


def _safe_call(func):
    """Call a scraper method, returning None on any error."""
    try:
        result = func()
        return result if result else None
    except Exception:
        return None


def _download_photo(client: httpx.Client, image_url: str | None) -> str | None:
    """Download an image and return base64-encoded data."""
    if not image_url:
        return None
    try:
        response = client.get(image_url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii")
    except Exception as e:
        logger.debug("Failed to download photo from %s: %s", image_url, e)
        return None
