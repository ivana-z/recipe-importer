"""URL fetching and recipe scraping with recipe-scrapers + trafilatura fallback."""

import logging
from urllib.parse import urljoin

import httpx
from recipe_scrapers import scrape_html

import trafilatura

from .source_errors import SourceError
from .url_safety import ensure_public_destination, validate_source_url

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

MAX_REDIRECTS = 5


def scrape_url(url: str) -> dict:
    """Scrape a recipe from a URL.

    Tries recipe-scrapers first for structured data.
    Falls back to trafilatura for raw content extraction.

    Returns a dict with either structured recipe fields or {"raw_html": ...}.
    """
    with httpx.Client(
        timeout=_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        html = _fetch_html(client, url)

        # Try structured extraction first
        try:
            recipe_data = _extract_structured(html, url)
            logger.debug("Structured extraction succeeded for %s", url)
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
    """Fetch HTML after validating each resolved destination and redirect."""
    current_url = validate_source_url(url)
    visited_urls = {current_url.url}
    redirects = 0

    while True:
        ensure_public_destination(current_url)
        try:
            response = client.get(current_url.url)
        except httpx.HTTPError as error:
            logger.warning("Recipe page fetch failed for %s", current_url.url, exc_info=True)
            raise SourceError(
                "source_fetch_failed",
                "The recipe page could not be fetched.",
                502,
            ) from error

        if not response.is_redirect:
            try:
                response.raise_for_status()
            except httpx.HTTPError as error:
                logger.warning("Recipe page fetch failed for %s", current_url.url, exc_info=True)
                raise SourceError(
                    "source_fetch_failed",
                    "The recipe page could not be fetched.",
                    502,
                ) from error
            return response.text

        location = response.headers.get("location")
        if not location:
            raise SourceError(
                "source_fetch_failed",
                "The recipe page could not be fetched.",
                502,
            )

        next_url = validate_source_url(urljoin(current_url.url, location))
        redirects += 1
        if redirects > MAX_REDIRECTS or next_url.url in visited_urls:
            raise SourceError(
                "source_fetch_failed",
                "The recipe page could not be fetched.",
                502,
            )

        visited_urls.add(next_url.url)
        current_url = next_url


def _extract_structured(html: str, url: str) -> dict:
    """Extract structured recipe data using recipe-scrapers."""
    scraper = scrape_html(html=html, org_url=url, wild_mode=True)
    data = {
        "title": scraper.title(),
        "ingredients": scraper.ingredients(),
        "directions": scraper.instructions_list(),
        "prep_time": _safe_call(scraper.prep_time),
        "cook_time": _safe_call(scraper.cook_time),
        "total_time": _safe_call(scraper.total_time),
        "servings": _safe_call(scraper.yields),
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
