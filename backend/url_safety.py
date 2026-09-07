"""Validation helpers for safe server-side URL imports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urlsplit

from .source_errors import SourceError

_ALLOWED_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class ValidatedSourceUrl:
    """A structurally valid source URL and its optional approved host match."""

    url: str
    hostname: str
    port: int | None
    approved_host: str | None


def validate_source_url(
    url: str, *, approved_hosts: Iterable[str] = ()
) -> ValidatedSourceUrl:
    """Validate URL structure without making a network request.

    ``approved_hosts`` only classifies a structurally valid host for later source
    dispatch; every caller must still validate its resolved destination.
    """
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        raise _invalid_source_url()

    if (
        not url
        or url != url.strip()
        or any(character.isspace() for character in url)
        or parsed.scheme.lower() not in _ALLOWED_SCHEMES
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise _invalid_source_url()

    hostname = hostname.rstrip(".").lower()
    if not hostname:
        raise _invalid_source_url()

    return ValidatedSourceUrl(
        url=url,
        hostname=hostname,
        port=port,
        approved_host=_matching_approved_host(hostname, approved_hosts),
    )


def ensure_public_destination(source_url: ValidatedSourceUrl) -> None:
    """Resolve a host and reject every non-global address before connecting."""
    try:
        results = socket.getaddrinfo(
            source_url.hostname,
            source_url.port or _default_port(source_url.url),
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        raise SourceError(
            "source_fetch_failed",
            "The recipe page could not be fetched.",
            502,
        ) from error

    addresses = {result[4][0] for result in results}
    if not addresses:
        raise SourceError(
            "source_fetch_failed",
            "The recipe page could not be fetched.",
            502,
        )

    for address in addresses:
        try:
            is_global = ipaddress.ip_address(address).is_global
        except ValueError as error:
            raise SourceError(
                "source_fetch_failed",
                "The recipe page could not be fetched.",
                502,
            ) from error
        if not is_global:
            raise SourceError(
                "unsafe_source_url",
                "This URL points to an unsafe network destination.",
                400,
            )


def _matching_approved_host(hostname: str, approved_hosts: Iterable[str]) -> str | None:
    for approved_host in approved_hosts:
        normalized = approved_host.rstrip(".").lower()
        if hostname == normalized or hostname.endswith(f".{normalized}"):
            return normalized
    return None


def _default_port(url: str) -> int:
    return 443 if urlsplit(url).scheme.lower() == "https" else 80


def _invalid_source_url() -> SourceError:
    return SourceError(
        "invalid_source_url",
        "Enter a valid HTTP or HTTPS URL.",
        400,
    )
