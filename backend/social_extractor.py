"""Social URL metadata extraction for public YouTube and Instagram sources."""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
import logging
import re
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
import yt_dlp

from .formatter import MAX_SOURCE_TEXT_CHARS, apply_source_metadata, format_recipe
from .source_errors import SourceError
from .url_safety import ensure_public_destination, validate_source_url

logger = logging.getLogger(__name__)

MAX_CAPTION_RESPONSE_BYTES = 2_000_000
MAX_CAPTION_REDIRECTS = 5
SOCIAL_EXTRACTION_TIMEOUT_SECONDS = 30.0
_SOCIAL_HOSTS = ("youtube.com", "youtube-nocookie.com", "youtu.be", "instagram.com")

_YOUTUBE_SUPPORTED_EXTS = {"json3", "vtt", "srv3", "srv2", "srv1", "ttml", "srt", "ass", "lrc", "txt"}
_YOUTUBE_FORMAT_RANK = {"json3": 0, "vtt": 1}


@dataclass(frozen=True)
class CaptionSelection:
    """One chosen caption track and one preferred representation."""

    language: str
    automatic: bool
    url: str
    ext: str


def classify_social_url(url: str) -> str | None:
    """Return the social platform for a supported public URL, or None for generic hosts."""
    validated = validate_source_url(url, approved_hosts=_SOCIAL_HOSTS)
    host = validated.approved_host
    if host is None:
        return None

    if host in {"youtube.com", "youtu.be", "youtube-nocookie.com"}:
        if _is_supported_youtube_url(validated.url):
            return "youtube"
        raise SourceError(
            "invalid_source_url",
            "Enter a supported individual YouTube video URL.",
            400,
        )

    if host == "instagram.com":
        if _is_supported_instagram_url(validated.url):
            return "instagram"
        raise SourceError(
            "invalid_source_url",
            "Enter a supported individual Instagram post, Reel, or TV URL.",
            400,
        )

    return None


def import_social_url(url: str, platform: str) -> dict:
    """Extract public social metadata and format it through the shared text path."""
    ensure_public_destination(
        validate_source_url(url, approved_hosts=_SOCIAL_HOSTS)
    )
    if platform == "youtube":
        return _import_youtube(url)
    if platform == "instagram":
        return _import_instagram(url)
    raise ValueError(f"Unsupported social platform: {platform}")


def _import_youtube(url: str) -> dict:
    try:
        info = _extract_youtube_info(url)
        title = _clean_text(info.get("title"))
        description = _clean_text(info.get("description"))
        caption_text = _select_and_fetch_caption_text(info)

        sections: list[str] = []
        if title:
            sections.append(f"Title:\n{title}")
        if description:
            sections.append(f"Description:\n{description}")
        if caption_text:
            sections.append(f"Captions:\n{caption_text}")

        if not description and not caption_text:
            raise SourceError(
                "source_unavailable",
                "No public YouTube description or captions were available. Extract the recipe separately and paste it into Text.",
                422,
            )

        text = "\n\n".join(sections)
        if len(text) > MAX_SOURCE_TEXT_CHARS:
            raise SourceError(
                "source_too_large",
                f"Recipe text is limited to {MAX_SOURCE_TEXT_CHARS} characters.",
                413,
            )

        formatted = format_recipe(text=text, text_label="YouTube description and captions")
        return apply_source_metadata(
            formatted,
            source_url=url,
            source=_infer_source_name(info, fallback="YouTube"),
        )
    except SourceError:
        raise
    except Exception as error:
        logger.exception("YouTube extraction failed for %s", url)
        if _is_known_social_unavailable_error(error):
            raise SourceError(
                "source_unavailable",
                "No public YouTube description or captions were available. Extract the recipe separately and paste it into Text.",
                422,
            ) from error
        raise SourceError(
            "source_fetch_failed",
            "The YouTube source could not be fetched.",
            502,
        ) from error


def _import_instagram(url: str) -> dict:
    try:
        info = _extract_instagram_info(url)
        caption = _clean_text(info.get("description"))
        if not caption:
            raise SourceError(
                "source_unavailable",
                "No public Instagram caption was available. Extract the recipe separately and paste it into Text.",
                422,
            )

        text = f"Caption:\n{caption}"
        if len(text) > MAX_SOURCE_TEXT_CHARS:
            raise SourceError(
                "source_too_large",
                f"Recipe text is limited to {MAX_SOURCE_TEXT_CHARS} characters.",
                413,
            )

        formatted = format_recipe(text=text, text_label="Instagram caption")
        return apply_source_metadata(
            formatted,
            source_url=url,
            source=_infer_source_name(info, fallback="Instagram"),
        )
    except SourceError:
        raise
    except Exception as error:
        logger.exception("Instagram extraction failed for %s", url)
        if _is_known_social_unavailable_error(error):
            raise SourceError(
                "source_unavailable",
                "No public Instagram caption was available. Extract the recipe separately and paste it into Text.",
                422,
            ) from error
        raise SourceError(
            "source_fetch_failed",
            "The Instagram source could not be fetched.",
            502,
        ) from error


def _extract_youtube_info(url: str) -> dict:
    options = {
        "skip_download": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": SOCIAL_EXTRACTION_TIMEOUT_SECONDS,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def _extract_instagram_info(url: str) -> dict:
    options = {
        "skip_download": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": SOCIAL_EXTRACTION_TIMEOUT_SECONDS,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def _select_and_fetch_caption_text(info: dict) -> str:
    selection = _select_caption_track(info)
    if selection is None:
        return ""

    try:
        payload = _fetch_caption_payload(selection.url)
    except httpx.HTTPStatusError as error:
        if error.response.status_code in {401, 403, 404, 410}:
            return ""
        raise SourceError(
            "source_fetch_failed",
            "The YouTube captions could not be fetched.",
            502,
        ) from error
    except httpx.HTTPError as error:
        raise SourceError(
            "source_fetch_failed",
            "The YouTube captions could not be fetched.",
            502,
        ) from error

    try:
        if selection.ext == "json3":
            return _parse_json3_captions(payload)
        if selection.ext == "vtt":
            return _parse_vtt_captions(payload)
        return _parse_generic_caption_text(payload)
    except SourceError:
        raise
    except Exception as error:
        logger.exception("Failed to parse YouTube captions from %s", selection.url)
        raise SourceError(
            "source_fetch_failed",
            "The YouTube captions could not be parsed.",
            502,
        ) from error


def _select_caption_track(info: dict) -> CaptionSelection | None:
    for automatic in (False, True):
        tracks = info.get("subtitles" if not automatic else "automatic_captions") or {}
        candidates: list[tuple[int, int, int, str, CaptionSelection]] = []
        for order, (language, formats) in enumerate(tracks.items()):
            if _is_live_chat_language(language):
                continue
            format_entry = _select_caption_format(formats or [])
            if format_entry is None:
                continue
            candidates.append(
                (
                    0 if _is_english_language(language) else 1,
                    _caption_format_rank(format_entry.get("ext")),
                    order,
                    language,
                    CaptionSelection(
                        language=language,
                        automatic=automatic,
                        url=str(format_entry["url"]),
                        ext=str(format_entry.get("ext") or ""),
                    ),
                )
            )

        if candidates:
            candidates.sort(key=lambda item: item[:3])
            return candidates[0][4]
    return None


def _select_caption_format(formats: list[dict]) -> dict | None:
    candidates: list[tuple[int, int, dict]] = []
    for order, format_entry in enumerate(formats):
        url = format_entry.get("url")
        ext = str(format_entry.get("ext") or "").lower()
        if not url or ext not in _YOUTUBE_SUPPORTED_EXTS:
            continue
        candidates.append((_caption_format_rank(ext), order, format_entry))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[:2])
    return candidates[0][2]


def _caption_format_rank(ext: str | None) -> int:
    if not ext:
        return 99
    return _YOUTUBE_FORMAT_RANK.get(ext.lower(), 2)


def _fetch_caption_payload(url: str) -> str:
    timeout = httpx.Timeout(SOCIAL_EXTRACTION_TIMEOUT_SECONDS)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }
    current_url = url
    with httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
    ) as client:
        for redirect_count in range(MAX_CAPTION_REDIRECTS + 1):
            validated = validate_source_url(current_url)
            ensure_public_destination(validated)
            with client.stream("GET", validated.url) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirect_count == MAX_CAPTION_REDIRECTS:
                        raise SourceError(
                            "source_fetch_failed",
                            "The YouTube captions redirected too many times.",
                            502,
                        )
                    current_url = urljoin(validated.url, location)
                    continue

                response.raise_for_status()
                if response.headers.get("content-length"):
                    try:
                        if int(response.headers["content-length"]) > MAX_CAPTION_RESPONSE_BYTES:
                            raise SourceError(
                                "source_too_large",
                                f"Caption response is limited to {MAX_CAPTION_RESPONSE_BYTES} bytes.",
                                413,
                            )
                    except ValueError:
                        pass

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_CAPTION_RESPONSE_BYTES:
                        raise SourceError(
                            "source_too_large",
                            f"Caption response is limited to {MAX_CAPTION_RESPONSE_BYTES} bytes.",
                            413,
                        )
                    chunks.append(chunk)

                return b"".join(chunks).decode("utf-8", errors="replace")

    raise RuntimeError("Caption redirect loop exited unexpectedly")


def _parse_json3_captions(payload: str) -> str:
    data = json.loads(payload)
    chunks: list[str] = []
    for event in data.get("events") or []:
        segs = event.get("segs") or []
        text = "".join(str(seg.get("utf8", "")) for seg in segs)
        normalized = _normalize_caption_chunk(text)
        if normalized:
            _append_unique(chunks, normalized)
    return "\n".join(chunks)


def _parse_vtt_captions(payload: str) -> str:
    payload = payload.lstrip("\ufeff")
    chunks: list[str] = []
    current: list[str] = []
    collecting = False

    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            if collecting:
                _flush_caption_chunk(chunks, current)
                current = []
                collecting = False
            continue

        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue

        if "-->" in line:
            if collecting and current:
                _flush_caption_chunk(chunks, current)
                current = []
            collecting = True
            continue

        if not collecting:
            continue

        current.append(line)

    if collecting and current:
        _flush_caption_chunk(chunks, current)

    return "\n".join(chunks)


_TIME_LINE_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}(?:[\.,]\d{1,3})?\s+-->\s+\d{1,2}:\d{2}:\d{2}(?:[\.,]\d{1,3})?$")
_TAG_RE = re.compile(r"<[^>]+>")


def _parse_generic_caption_text(payload: str) -> str:
    chunks: list[str] = []
    current: list[str] = []

    for raw_line in payload.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _normalize_caption_chunk(raw_line)
        if not line:
            if current:
                _flush_caption_chunk(chunks, current)
                current = []
            continue
        if line == "WEBVTT" or line.isdigit() or _TIME_LINE_RE.match(line):
            continue
        current.append(line)

    if current:
        _flush_caption_chunk(chunks, current)

    return "\n".join(chunks)


def _flush_caption_chunk(chunks: list[str], current: list[str]) -> None:
    text = _normalize_caption_chunk(" ".join(current))
    if text:
        _append_unique(chunks, text)


def _append_unique(chunks: list[str], text: str) -> None:
    if not chunks or chunks[-1] != text:
        chunks.append(text)


def _normalize_caption_chunk(text: str) -> str:
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return html.unescape(value).strip()




def _infer_source_name(info: dict, *, fallback: str) -> str:
    for key in ("uploader", "channel", "creator", "account_name", "full_name", "display_name"):
        value = _clean_text(info.get(key))
        if value:
            return value
    return fallback


def _is_english_language(language: str) -> bool:
    normalized = language.lower().replace("_", "-")
    return normalized == "en" or normalized.startswith("en-")


def _is_live_chat_language(language: str) -> bool:
    return "live_chat" in language.lower()


def _is_supported_youtube_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")

    if host == "youtu.be":
        return bool(path and path.count("/") == 1 and path != "/")

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
        if path == "/watch":
            return bool(parse_qs(parsed.query).get("v", [""])[0])
        if path.startswith("/shorts/") or path.startswith("/embed/") or path.startswith("/live/"):
            parts = path.split("/")
            return len(parts) >= 3 and bool(parts[2])
        return False

    return False


def _is_supported_instagram_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host not in {"instagram.com", "www.instagram.com", "m.instagram.com"}:
        return False

    path = parsed.path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        return False
    return parts[0] in {"p", "reel", "tv"} and bool(parts[1])


def _is_known_social_unavailable_error(error: Exception) -> bool:
    message = f"{error.__class__.__name__} {error.__class__.__module__} {error}".lower()
    return any(
        token in message
        for token in (
            "private",
            "login required",
            "loginrequired",
            "sign in",
            "sign-in",
            "not available",
            "unavailable",
            "members only",
            "members-only",
            "geo restricted",
            "georestricted",
            "age restricted",
            "age-restricted",
        )
    )
