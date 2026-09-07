"""Regression coverage for conventional recipe-page URL safety."""

import socket

import httpx
import pytest

from backend import scraper
from backend.source_errors import SourceError
from backend.url_safety import validate_source_url

PUBLIC_IPV4 = "93.184.216.34"


def _dns_result(address: str):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (address, 0))]


def _public_dns(*_args, **_kwargs):
    return _dns_result(PUBLIC_IPV4)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_safe_public_url_fetches_html(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.url_safety.socket.getaddrinfo", _public_dns)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, text="<html>recipe</html>", request=request)

    with _client(handler) as client:
        assert scraper._fetch_html(client, "https://recipes.example.test/dinner") == "<html>recipe</html>"

    assert requests == ["https://recipes.example.test/dinner"]


@pytest.mark.parametrize(
    ("url", "resolved_address"),
    [
        ("http://127.0.0.1/recipe", "127.0.0.1"),
        ("https://internal.example.test/recipe", "10.0.0.8"),
        ("https://[::1]/recipe", "::1"),
    ],
    ids=["raw-private-ip", "dns-private-ip", "ipv6-loopback"],
)
def test_non_global_destinations_are_blocked_before_http_request(
    monkeypatch: pytest.MonkeyPatch, url: str, resolved_address: str
):
    monkeypatch.setattr(
        "backend.url_safety.socket.getaddrinfo",
        lambda *_args, **_kwargs: _dns_result(resolved_address),
    )
    requested = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested
        requested = True
        return httpx.Response(200, request=request)

    with _client(handler) as client:
        with pytest.raises(SourceError) as raised:
            scraper._fetch_html(client, url)

    assert raised.value.code == "unsafe_source_url"
    assert raised.value.status_code == 400
    assert requested is False


def test_embedded_credentials_are_rejected():
    with pytest.raises(SourceError) as raised:
        validate_source_url("https://user:password@recipes.example.test/recipe")

    assert raised.value.detail == {
        "code": "invalid_source_url",
        "message": "Enter a valid HTTP or HTTPS URL.",
    }


def test_approved_host_classification_preserves_generic_url_validation():
    source_url = validate_source_url(
        "https://www.youtube.com/watch?v=example",
        approved_hosts=("youtube.com", "instagram.com"),
    )

    assert source_url.approved_host == "youtube.com"


def test_redirect_to_private_destination_is_blocked_before_following(
    monkeypatch: pytest.MonkeyPatch,
):
    def dns(hostname, *_args, **_kwargs):
        return _dns_result("10.0.0.9" if hostname == "private.example.test" else PUBLIC_IPV4)

    monkeypatch.setattr("backend.url_safety.socket.getaddrinfo", dns)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://private.example.test/recipe"},
            request=request,
        )

    with _client(handler) as client:
        with pytest.raises(SourceError) as raised:
            scraper._fetch_html(client, "https://recipes.example.test/recipe")

    assert raised.value.code == "unsafe_source_url"
    assert requests == ["https://recipes.example.test/recipe"]


def test_redirect_loop_is_rejected_without_repeating_a_request(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.url_safety.socket.getaddrinfo", _public_dns)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "/loop"}, request=request)

    with _client(handler) as client:
        with pytest.raises(SourceError) as raised:
            scraper._fetch_html(client, "https://recipes.example.test/loop")

    assert raised.value.code == "source_fetch_failed"
    assert requests == ["https://recipes.example.test/loop"]


def test_redirect_overflow_is_rejected_after_maximum_redirects(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.url_safety.socket.getaddrinfo", _public_dns)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        index = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(302, headers={"location": f"/{index + 1}"}, request=request)

    with _client(handler) as client:
        with pytest.raises(SourceError) as raised:
            scraper._fetch_html(client, "https://recipes.example.test/0")

    assert raised.value.code == "source_fetch_failed"
    assert requests == [f"https://recipes.example.test/{index}" for index in range(6)]


def test_upstream_fetch_failure_is_safe_and_structured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.url_safety.socket.getaddrinfo", _public_dns)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("resolver diagnostic must stay private", request=request)

    with _client(handler) as client:
        with pytest.raises(SourceError) as raised:
            scraper._fetch_html(client, "https://recipes.example.test/recipe")

    assert raised.value.detail == {
        "code": "source_fetch_failed",
        "message": "The recipe page could not be fetched.",
    }
    assert raised.value.status_code == 502


def test_scrape_url_preserves_structured_trafilatura_and_raw_html_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(scraper, "_fetch_html", lambda _client, _url: "<html>raw</html>")

    structured = {"title": "Soup", "ingredients": ["water"], "directions": ["boil"]}
    monkeypatch.setattr(scraper, "_extract_structured", lambda _html, _url: structured)
    assert scraper.scrape_url("https://recipes.example.test/soup") == structured

    def fail_structured(_html, _url):
        raise ValueError("not structured")

    monkeypatch.setattr(scraper, "_extract_structured", fail_structured)
    monkeypatch.setattr(scraper.trafilatura, "extract", lambda *_args, **_kwargs: "recipe text")
    assert scraper.scrape_url("https://recipes.example.test/soup") == {
        "raw_html": "recipe text",
        "url": "https://recipes.example.test/soup",
    }

    monkeypatch.setattr(scraper.trafilatura, "extract", lambda *_args, **_kwargs: None)
    assert scraper.scrape_url("https://recipes.example.test/soup") == {
        "raw_html": "<html>raw</html>",
        "url": "https://recipes.example.test/soup",
    }
