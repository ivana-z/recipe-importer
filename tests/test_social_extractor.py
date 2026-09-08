"""Regression coverage for YouTube and Instagram source extraction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend import services, social_extractor
from backend.source_errors import SourceError

YOUTUBE_URL = "https://www.youtube.com/watch?v=video123"
INSTAGRAM_URL = "https://www.instagram.com/p/post123/"


class _FakeResponse:
    def __init__(self, *, body: bytes, headers: dict[str, str] | None = None, status_code: int = 200):
        self._body = body
        self.headers = headers or {}
        self.status_code = status_code
        self.request = SimpleNamespace(url="https://caption.example.test/subs")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise social_extractor.httpx.HTTPStatusError(
                "boom",
                request=self.request,
                response=SimpleNamespace(status_code=self.status_code),
            )

    def iter_bytes(self):
        yield self._body


class _FakeStream:
    def __init__(self, response: _FakeResponse):
        self._response = response

    def __enter__(self):
        return self._response

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *args, response: _FakeResponse, **kwargs):
        self.response = response
        self.kwargs = kwargs
        self.requests: list[tuple[str, str]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str):
        self.requests.append((method, url))
        return _FakeStream(self.response)


@pytest.fixture
def recipe_result():
    return {
        "name": "Recipe",
        "ingredients": "1 carrot",
        "directions": "Mix.",
        "prep_time": "",
        "cook_time": "",
        "servings": "",
        "notes": "",
    }


@pytest.fixture(autouse=True)
def avoid_live_destination_resolution(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        social_extractor,
        "ensure_public_destination",
        lambda _source_url: None,
    )


@pytest.fixture
def capture_formatter(monkeypatch: pytest.MonkeyPatch, recipe_result):
    captured: dict[str, str] = {}

    def fake_format_recipe(*, text: str, text_label: str):
        captured["text"] = text
        captured["text_label"] = text_label
        return {"recipes": [dict(recipe_result)]}

    monkeypatch.setattr(social_extractor, "format_recipe", fake_format_recipe)
    return captured


@pytest.fixture
def youtube_info():
    return {
        "title": "Summer Soup",
        "description": "Recipe description",
        "uploader": "Chef Channel",
        "subtitles": {},
        "automatic_captions": {},
    }


@pytest.fixture
def instagram_info():
    return {
        "description": "",
        "uploader": "chef_account",
    }


@pytest.fixture
def fake_youtube_extractor(monkeypatch: pytest.MonkeyPatch, youtube_info):
    captured: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            captured["url"] = url
            captured["download"] = download
            return dict(youtube_info)

    monkeypatch.setattr(social_extractor.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    return captured


@pytest.fixture
def fake_instagram_extractor(monkeypatch: pytest.MonkeyPatch, instagram_info):
    captured: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            captured["url"] = url
            captured["download"] = download
            return dict(instagram_info)

    monkeypatch.setattr(social_extractor.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    return captured


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/watch?v=video123", "youtube"),
        ("https://youtu.be/video123", "youtube"),
        ("https://www.youtube-nocookie.com/embed/video123", "youtube"),
        ("https://www.instagram.com/p/post123/", "instagram"),
        ("https://www.instagram.com/reel/post123/", "instagram"),
        ("https://www.instagram.com/tv/post123/", "instagram"),
    ],
)
def test_social_url_classification_accepts_supported_individual_paths(url: str, expected: str):
    assert social_extractor.classify_social_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/feed/trending",
        "https://www.youtube.com/@chef/videos",
        "https://www.instagram.com/chef_account/",
        "https://www.instagram.com/explore/tags/soup/",
        "https://www.instagram.com/stories/chef_account/123/",
    ],
)
def test_social_url_rejections_are_structured_invalid_source_urls(url: str):
    with pytest.raises(SourceError) as raised:
        social_extractor.classify_social_url(url)

    assert raised.value.code == "invalid_source_url"
    assert raised.value.status_code == 400


def test_youtube_metadata_extraction_uses_only_metadata_and_no_media_download(
    fake_youtube_extractor, capture_formatter, recipe_result
):
    result = social_extractor.import_social_url(YOUTUBE_URL, "youtube")
    recipe = result["recipes"][0]

    assert fake_youtube_extractor["url"] == YOUTUBE_URL
    assert fake_youtube_extractor["download"] is False
    assert fake_youtube_extractor["options"]["skip_download"] is True
    assert fake_youtube_extractor["options"]["noplaylist"] is True
    assert fake_youtube_extractor["options"]["quiet"] is True
    assert fake_youtube_extractor["options"]["no_warnings"] is True
    assert fake_youtube_extractor["options"]["socket_timeout"] == social_extractor.SOCIAL_EXTRACTION_TIMEOUT_SECONDS
    assert "format" not in fake_youtube_extractor["options"]
    assert "outtmpl" not in fake_youtube_extractor["options"]
    assert "postprocessors" not in fake_youtube_extractor["options"]
    assert recipe["source_url"] == YOUTUBE_URL
    assert recipe["source"] == "Chef Channel"
    assert capture_formatter["text_label"] == "YouTube description and captions"
    assert capture_formatter["text"] == "Title:\nSummer Soup\n\nDescription:\nRecipe description"
    assert recipe["name"] == recipe_result["name"]


def test_youtube_page_fallback_recovers_description_when_extractor_omits_it(
    monkeypatch: pytest.MonkeyPatch,
    youtube_info,
    fake_youtube_extractor,
    capture_formatter,
):
    youtube_info["description"] = ""
    page = """
        <script>
        var ytInitialPlayerResponse = {
            "videoDetails": {
                "title": "Summer Soup",
                "shortDescription": "1 carrot\\nMix &amp; serve.",
                "author": "Fallback Chef"
            }
        };
        </script>
    """
    monkeypatch.setattr(social_extractor, "_fetch_youtube_page", lambda _url: page)

    result = social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert result["recipes"][0]["source"] == "Chef Channel"
    assert capture_formatter["text"] == (
        "Title:\nSummer Soup\n\nDescription:\n1 carrot\nMix & serve."
    )


def test_social_source_metadata_applies_to_every_formatted_recipe(
    monkeypatch: pytest.MonkeyPatch,
    youtube_info,
    recipe_result,
):
    monkeypatch.setattr(
        social_extractor,
        "_extract_youtube_info",
        lambda _url: dict(youtube_info),
    )
    second_recipe = dict(recipe_result, name="Second recipe")
    monkeypatch.setattr(
        social_extractor,
        "format_recipe",
        lambda **_kwargs: {"recipes": [dict(recipe_result), second_recipe]},
    )

    result = social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert [recipe["name"] for recipe in result["recipes"]] == [
        "Recipe",
        "Second recipe",
    ]
    assert all(recipe["source_url"] == YOUTUBE_URL for recipe in result["recipes"])
    assert all(recipe["source"] == "Chef Channel" for recipe in result["recipes"])


@pytest.mark.parametrize(
    "info, payload, expected_caption",
    [
        (
            {
                "title": "Soup",
                "description": "",
                "uploader": "Chef Channel",
                "subtitles": {
                    "en": [{"ext": "vtt", "url": "https://caption.example.test/human.vtt"}],
                },
                "automatic_captions": {
                    "en": [{"ext": "json3", "url": "https://caption.example.test/auto.json3"}],
                },
            },
            {
                "https://caption.example.test/human.vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHuman track\n",
                "https://caption.example.test/auto.json3": "{\"events\":[{\"segs\":[{\"utf8\":\"Automatic track\"}]}]}",
            },
            "Human track",
        ),
        (
            {
                "title": "Soup",
                "description": "",
                "uploader": "Chef Channel",
                "subtitles": {},
                "automatic_captions": {
                    "en": [{"ext": "vtt", "url": "https://caption.example.test/auto.vtt"}],
                },
            },
            {
                "https://caption.example.test/auto.vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nAutomatic fallback\n",
            },
            "Automatic fallback",
        ),
        (
            {
                "title": "Soup",
                "description": "",
                "uploader": "Chef Channel",
                "subtitles": {
                    "fr": [{"ext": "json3", "url": "https://caption.example.test/fr.json3"}],
                },
                "automatic_captions": {},
            },
            {
                "https://caption.example.test/fr.json3": "{\"events\":[{\"segs\":[{\"utf8\":\"Bonjour &amp; bonjour\"}]},{\"segs\":[{\"utf8\":\"Bonjour &amp; bonjour\"}]},{\"segs\":[{\"utf8\":\"Versez\"}]}]}",
            },
            "Bonjour & bonjour\nVersez",
        ),
        (
            {
                "title": "Soup",
                "description": "",
                "uploader": "Chef Channel",
                "subtitles": {
                    "fr": [{"ext": "vtt", "url": "https://caption.example.test/fr.vtt"}],
                },
                "automatic_captions": {},
            },
            {
                "https://caption.example.test/fr.vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nBonjour &amp; bonjour\n\n00:00:01.000 --> 00:00:02.000\nBonjour &amp; bonjour\n\n00:00:02.000 --> 00:00:03.000\nVersez\n",
            },
            "Bonjour & bonjour\nVersez",
        ),
    ],
)
def test_youtube_caption_selection_and_parsing(
    monkeypatch: pytest.MonkeyPatch,
    recipe_result,
    info,
    payload,
    expected_caption,
):
    monkeypatch.setattr(social_extractor, "_extract_youtube_info", lambda _url: dict(info))
    monkeypatch.setattr(social_extractor, "_fetch_caption_payload", lambda url: payload[url])
    captured: dict[str, str] = {}

    def fake_format_recipe(*, text: str, text_label: str):
        captured["text"] = text
        captured["text_label"] = text_label
        return {"recipes": [dict(recipe_result)]}

    monkeypatch.setattr(social_extractor, "format_recipe", fake_format_recipe)

    result = social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert result["recipes"][0]["source"] == "Chef Channel"
    assert capture_text_section(captured["text"], "Captions:") == expected_caption
    assert captured["text_label"] == "YouTube description and captions"


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Video unavailable"),
        RuntimeError("Login required"),
        RuntimeError("Private video"),
    ],
)
def test_youtube_known_unavailable_failures_become_source_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
):
    monkeypatch.setattr(social_extractor, "_extract_youtube_info", lambda _url: (_ for _ in ()).throw(error))

    with pytest.raises(SourceError) as raised:
        social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert raised.value.code == "source_unavailable"
    assert raised.value.status_code == 422
    assert raised.value.message == (
        "No public YouTube description or captions were available. Extract the recipe separately and paste it into Text."
    )


def test_youtube_title_only_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        social_extractor,
        "_extract_youtube_info",
        lambda _url: {
            "title": "Summer Soup",
            "description": "",
            "subtitles": {},
            "automatic_captions": {},
        },
    )

    with pytest.raises(SourceError) as raised:
        social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert raised.value.code == "source_unavailable"


def test_youtube_combined_text_limit_is_enforced_before_formatter(monkeypatch: pytest.MonkeyPatch):
    called = False

    def fake_format_recipe(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("formatter should not be called when source text is too large")

    monkeypatch.setattr(social_extractor, "format_recipe", fake_format_recipe)
    monkeypatch.setattr(
        social_extractor,
        "_extract_youtube_info",
        lambda _url: {
            "title": "x" * 10,
            "description": "x" * social_extractor.MAX_SOURCE_TEXT_CHARS,
            "subtitles": {},
            "automatic_captions": {},
        },
    )

    with pytest.raises(SourceError) as raised:
        social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert raised.value.code == "source_too_large"
    assert raised.value.status_code == 413
    assert called is False


def test_social_destination_is_rejected_before_metadata_extraction(
    monkeypatch: pytest.MonkeyPatch,
):
    extracted = False

    def reject_destination(_source_url):
        raise SourceError(
            "unsafe_source_url",
            "This URL points to an unsafe network destination.",
            400,
        )

    def extract_info(_url):
        nonlocal extracted
        extracted = True
        return {}

    monkeypatch.setattr(
        social_extractor,
        "ensure_public_destination",
        reject_destination,
    )
    monkeypatch.setattr(social_extractor, "_extract_youtube_info", extract_info)

    with pytest.raises(SourceError) as raised:
        social_extractor.import_social_url(YOUTUBE_URL, "youtube")

    assert raised.value.code == "unsafe_source_url"
    assert extracted is False


def test_caption_redirect_revalidates_destination(
    monkeypatch: pytest.MonkeyPatch,
):
    checked_hosts: list[str] = []
    redirect = _FakeResponse(
        body=b"",
        headers={"location": "http://127.0.0.1/private.vtt"},
        status_code=302,
    )

    class FakeClient(_FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, response=redirect, **kwargs)

    def reject_private(source_url):
        checked_hosts.append(source_url.hostname)
        if source_url.hostname == "127.0.0.1":
            raise SourceError(
                "unsafe_source_url",
                "This URL points to an unsafe network destination.",
                400,
            )

    monkeypatch.setattr(social_extractor.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        social_extractor,
        "ensure_public_destination",
        reject_private,
    )

    with pytest.raises(SourceError) as raised:
        social_extractor._fetch_caption_payload(
            "https://caption.example.test/subs.vtt"
        )

    assert raised.value.code == "unsafe_source_url"
    assert checked_hosts == ["caption.example.test", "127.0.0.1"]


def test_youtube_caption_response_limit_is_enforced(monkeypatch: pytest.MonkeyPatch):
    payload = b"x" * (social_extractor.MAX_CAPTION_RESPONSE_BYTES + 1)
    response = _FakeResponse(body=payload, headers={})

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            return _FakeStream(response)

    monkeypatch.setattr(social_extractor.httpx, "Client", FakeClient)

    with pytest.raises(SourceError) as raised:
        social_extractor._fetch_caption_payload("https://caption.example.test/huge.vtt")

    assert raised.value.code == "source_too_large"
    assert raised.value.status_code == 413


def test_youtube_caption_fetch_http_error_is_structured_as_fetch_failure(monkeypatch: pytest.MonkeyPatch):
    request = social_extractor.httpx.Request("GET", "https://caption.example.test/denied.vtt")
    response = social_extractor.httpx.Response(500, request=request)
    selection = social_extractor.CaptionSelection(
        language="en",
        automatic=False,
        url="https://caption.example.test/denied.vtt",
        ext="vtt",
    )

    monkeypatch.setattr(social_extractor, "_select_caption_track", lambda _info: selection)
    monkeypatch.setattr(
        social_extractor,
        "_fetch_caption_payload",
        lambda _url: (_ for _ in ()).throw(
            social_extractor.httpx.HTTPStatusError("boom", request=request, response=response)
        ),
    )

    with pytest.raises(SourceError) as raised:
        social_extractor._select_and_fetch_caption_text({})

    assert raised.value.code == "source_fetch_failed"


def test_instagram_public_caption_uses_caption_text_and_ignores_media_fields(
    monkeypatch: pytest.MonkeyPatch,
    recipe_result,
):
    class InstagramInfo(dict):
        def get(self, key, default=None):
            if key in {"formats", "thumbnails", "subtitles", "comments", "requested_formats", "uploader_id"}:
                raise AssertionError(f"media field should not be accessed: {key}")
            return super().get(key, default)

    monkeypatch.setattr(
        social_extractor,
        "_extract_instagram_info",
        lambda _url: InstagramInfo(
            description="Rustic soup",
            uploader="chef_account",
            title="Should be ignored",
            formats=[{"url": "https://media.example.test/video.mp4"}],
            thumbnails=[{"url": "https://media.example.test/thumb.jpg"}],
            subtitles={"en": [{"url": "https://media.example.test/subs.vtt"}]},
            comments=[{"text": "ignore"}],
        ),
    )
    captured: dict[str, str] = {}

    def fake_format_recipe(*, text: str, text_label: str):
        captured["text"] = text
        captured["text_label"] = text_label
        return {"recipes": [dict(recipe_result)]}

    monkeypatch.setattr(social_extractor, "format_recipe", fake_format_recipe)

    result = social_extractor.import_social_url(INSTAGRAM_URL, "instagram")

    assert result["recipes"][0]["source"] == "chef_account"
    assert result["recipes"][0]["source_url"] == INSTAGRAM_URL
    assert captured["text_label"] == "Instagram caption"
    assert captured["text"] == "Caption:\nRustic soup"


@pytest.mark.parametrize(
    "error",
    [RuntimeError("Login required"), RuntimeError("This post is private")],
)
def test_instagram_private_or_login_required_posts_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
):
    monkeypatch.setattr(social_extractor, "_extract_instagram_info", lambda _url: (_ for _ in ()).throw(error))

    with pytest.raises(SourceError) as raised:
        social_extractor.import_social_url(INSTAGRAM_URL, "instagram")

    assert raised.value.code == "source_unavailable"
    assert raised.value.status_code == 422
    assert raised.value.message == "No public Instagram caption was available. Extract the recipe separately and paste it into Text."


def test_instagram_missing_caption_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        social_extractor,
        "_extract_instagram_info",
        lambda _url: {
            "description": "   ",
            "uploader": "chef_account",
        },
    )

    with pytest.raises(SourceError) as raised:
        social_extractor.import_social_url(INSTAGRAM_URL, "instagram")

    assert raised.value.code == "source_unavailable"
    assert raised.value.status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/chef_account/",
        "https://www.instagram.com/explore/tags/soup/",
        "https://www.instagram.com/stories/chef_account/123/",
    ],
)
def test_instagram_unsupported_paths_are_invalid_source_urls(url: str):
    with pytest.raises(SourceError) as raised:
        social_extractor.classify_social_url(url)

    assert raised.value.code == "invalid_source_url"


def test_dispatch_keeps_generic_public_hosts_on_the_recipe_scraper(monkeypatch: pytest.MonkeyPatch):
    called = {"scraper": False, "social": False}

    def fake_scrape(url: str):
        called["scraper"] = True
        assert url == "https://recipes.example.test/dinner"
        return {
            "title": "Recipe page",
            "ingredients": ["1 carrot"],
            "directions": ["Mix"],
            "site_name": "Example",
        }

    def fake_format_recipe(*, recipe_data=None, source_url=None, images=None, text=None, text_label=None):
        assert recipe_data["title"] == "Recipe page"
        assert source_url == "https://recipes.example.test/dinner"
        return {
            "recipes": [
                {
                    "name": "Recipe page",
                    "ingredients": "1 carrot",
                    "directions": "Mix",
                    "prep_time": "",
                    "cook_time": "",
                    "servings": "",
                    "notes": "",
                }
            ]
        }

    monkeypatch.setattr(services, "scrape_url", fake_scrape)
    monkeypatch.setattr(services, "format_recipe", fake_format_recipe)
    monkeypatch.setattr(services, "import_social_url", lambda *_args, **_kwargs: called.__setitem__("social", True))

    result = asyncio_run(services.import_from_url("https://recipes.example.test/dinner"))

    assert called == {"scraper": True, "social": False}
    assert result["recipes"][0]["source"] == "Example"
    assert (
        result["recipes"][0]["source_url"]
        == "https://recipes.example.test/dinner"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.instagram.com/explore/tags/soup/",
    ],
)
def test_dispatch_rejects_unsupported_social_paths_before_scraping(monkeypatch: pytest.MonkeyPatch, url: str):
    monkeypatch.setattr(services, "scrape_url", lambda _url: (_ for _ in ()).throw(AssertionError("scraper should not be used")))
    monkeypatch.setattr(services, "import_social_url", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("social extractor should not be used")))

    with pytest.raises(SourceError) as raised:
        asyncio_run(services.import_from_url(url))

    assert raised.value.code == "invalid_source_url"


@pytest.mark.parametrize(
    "url, platform",
    [
        (YOUTUBE_URL, "youtube"),
        (INSTAGRAM_URL, "instagram"),
    ],
)
def test_dispatch_routes_supported_social_urls_to_the_social_extractor(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    platform: str,
):
    called = {"scraper": False, "social": False}

    def fake_social_import(seen_url: str, seen_platform: str):
        called["social"] = True
        assert seen_url == url
        assert seen_platform == platform
        return {
            "recipes": [
                {
                    "name": "Social recipe",
                    "ingredients": "1 carrot",
                    "directions": "Mix",
                    "prep_time": "",
                    "cook_time": "",
                    "servings": "",
                    "notes": "",
                    "source_url": url,
                    "source": platform,
                }
            ]
        }

    monkeypatch.setattr(services, "scrape_url", lambda _url: (_ for _ in ()).throw(AssertionError("scraper should not be used")))
    monkeypatch.setattr(services, "import_social_url", fake_social_import)

    result = asyncio_run(services.import_from_url(url))

    assert called == {"scraper": False, "social": True}
    assert result["recipes"][0]["source_url"] == url
    assert result["recipes"][0]["source"] == platform


# Small local helpers so the test file can stay synchronous.

def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def capture_text_section(text: str, heading: str) -> str:
    start = text.index(heading) + len(heading) + 1
    remainder = text[start:]
    next_heading = remainder.find("\n\n")
    if next_heading == -1:
        return remainder.strip()
    return remainder[:next_heading].strip()
