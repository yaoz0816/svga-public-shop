"""Public preview URL filtering without network access."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

from .schema import (
    DENIED_PATH_MARKERS,
    DENIED_QUERY_KEYS,
    IMAGE_FORMATS,
    UNSUPPORTED_FORMATS,
    VIDEO_FORMATS,
)


def classify_public_preview(value: object) -> tuple[str, str, str]:
    """Return approved URL, extension, and browser support state."""
    if not isinstance(value, str) or not value:
        return "", "", "unavailable"

    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return "", "", "unavailable"
    if any(marker in parsed.path.lower() for marker in DENIED_PATH_MARKERS):
        return "", "", "unavailable"
    if any(key.lower() in DENIED_QUERY_KEYS for key, _ in parse_qsl(parsed.query)):
        return "", "", "unavailable"

    extension = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""
    if extension in IMAGE_FORMATS:
        return value, extension, "image"
    if extension in VIDEO_FORMATS:
        return value, extension, "video"
    if extension in UNSUPPORTED_FORMATS:
        return value, extension, "unsupported"
    return "", "", "unavailable"
