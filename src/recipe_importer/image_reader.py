"""Image loading and base64 encoding for Claude vision API."""

import base64
import mimetypes
from pathlib import Path

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def read_images(paths: list[str]) -> list[dict]:
    """Read multiple image files and return Claude vision API-ready dicts.

    Each dict has: {"type": "image", "media_type": ..., "data": <base64>}

    Raises:
        FileNotFoundError: If a file does not exist.
        ValueError: If a file has an unsupported format.
    """
    results = []
    for path_str in paths:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported image format '{suffix}' for {path.name}. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        media_type = MIME_TYPES[suffix]
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        results.append({
            "type": "image",
            "media_type": media_type,
            "data": data,
        })
    return results
