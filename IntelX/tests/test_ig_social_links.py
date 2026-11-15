"""Tests for TASK-IG-INT-02 — social-link reader (Agent Reach pattern).

Hermetic: all fetching is injected; no network is touched. The fixtures are
shaped like the real public responses (YouTube oEmbed JSON, Reddit .json,
Instagram OpenGraph HTML) as observed 2026-11-15.
"""

from __future__ import annotations

import json

import pytest

from intelx.connectors.social_links import (
    SocialLinkReader,
    SocialLinkUnavailable,
    canonicalise,
    classify_social_url,
    youtube_video_id,
)

YOUTUBE_OEMBED = json.dumps(
    {
        "title": "Building a Jarvis in a weekend",
        "author_name": "Maker Channel",
        "author_url": "https://www.youtube.com/@maker",
        "type": "video",
    }
).encode()

YOUTUBE_WATCH = (
    b'<html><head><meta property="og:description" content="Short desc"></head>'
    b'<body><script>var x = {"shortDescription":"Full verbatim description line one.\\nLine two with \\"quotes\\"."};</script></body></html>'
)

REDDIT_JSON = json.dumps(
    [
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Show HN: my OSINT toolkit",
                            "selftext": "I built a read-only research toolkit. Details inside.",
                            "author": "researcher42",
                            "subreddit": "OSINT",
                        }
                    }
                ]
            }
        }
    ]
).encode()

INSTAGRAM_HTML = (
    b'<html><head>'
    b'<meta property="og:title" content="maker.lab on Instagram: reel">'
    b'<meta property="og:description" content="1,234 likes, 56 comments - maker.lab: '
    b'&quot;We gave our agent eyes on the machine. Full build log in the caption.&quot;">'
    b"</head><body></body></html>"
)

INSTAGRAM_LOGIN_WALL = (
    b"<html><head><title>Login \xe2\x80\xa2 Instagram</title></head>"
    b"<body><form>Log in</form></body></html>"
)

GENERIC_HTML = (
    b"<html><head><title>Deep Dive \xe2\x80\x94 Example Blog</title>"
    b'<meta property="og:description" content="A short summary."></head><body>'
    b"<p>This is the first real paragraph of the article, long enough to count as content.</p>"
    b"<p>Second paragraph with the actual findings and a verbatim sentence to cite.</p>"
    b"</body></html>"
)


class FakeFetch:
    """Records every request; serves canned responses by URL substring."""

    def __init__(self, routes: dict[str, tuple[int, str, bytes]]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    async def __call__(self, url: str) -> tuple[int, str, bytes]:
        self.calls.append(url)
        for key, response in self.routes.items():
            if key in url:
                return response
        return (404, url, b"")


def test_classify_and_canonicalise() -> None:
    assert classify_social_url("https://youtu.be/abc123") == "youtube"
    assert classify_social_url("https://old.reddit.com/r/x/comments/1") == "reddit"
    assert classify_social_url("https://www.instagram.com/reel/XYZ/") == "instagram"
    assert classify_social_url("https://example.com/post") == "web"
    assert youtube_video_id("https://www.youtube.com/watch?v=abc123&t=9") == "abc123"
    assert youtube_video_id("https://www.youtube.com/shorts/xyz789") == "xyz789"
    assert canonicalise("https://youtu.be/abc123?t=3") == "https://www.youtube.com/watch?v=abc123"
    assert canonicalise("https://old.reddit.com/r/x/comments/1/") == "https://www.reddit.com/r/x/comments/1"


async def test_youtube_read_verbatim_description() -> None:
    fetch = FakeFetch(
        {
            "oembed": (200, "https://www.youtube.com/oembed", YOUTUBE_OEMBED),
            "watch?v=": (200, "https://www.youtube.com/watch?v=abc123", YOUTUBE_WATCH),
        }
    )
    doc = await SocialLinkReader(fetch=fetch).read("https://youtu.be/abc123")
    assert doc.platform == "youtube"
    assert doc.author == "Maker Channel"
    assert doc.title == "Building a Jarvis in a weekend"
    assert doc.text == 'Full verbatim description line one.\nLine two with "quotes".'
    assert doc.extraction_method == "youtube_oembed+watch_page"
    assert doc.media_kind == "video"


async def test_youtube_oembed_failure_is_honest() -> None:
    fetch = FakeFetch({"oembed": (404, "https://www.youtube.com/oembed", b"")})
    with pytest.raises(SocialLinkUnavailable) as exc:
        await SocialLinkReader(fetch=fetch).read("https://www.youtube.com/watch?v=nope")
    assert "404" in exc.value.reason


async def test_reddit_read() -> None:
    fetch = FakeFetch({".json": (200, "https://www.reddit.com/r/OSINT/comments/1/.json", REDDIT_JSON)})
    doc = await SocialLinkReader(fetch=fetch).read("https://www.reddit.com/r/OSINT/comments/1")
    assert doc.platform == "reddit"
    assert doc.author == "u/researcher42"
    assert doc.text.startswith("I built a read-only research toolkit.")
    assert doc.extraction_method == "reddit_json"


async def test_reddit_block_is_honest_not_fabricated() -> None:
    fetch = FakeFetch({".json": (403, "https://www.reddit.com/r/OSINT/comments/1/.json", b"blocked")})
    with pytest.raises(SocialLinkUnavailable) as exc:
        await SocialLinkReader(fetch=fetch).read("https://www.reddit.com/r/OSINT/comments/1")
    assert "403" in exc.value.reason


async def test_instagram_opengraph_read() -> None:
    fetch = FakeFetch({"instagram.com": (200, "https://www.instagram.com/reel/XYZ/", INSTAGRAM_HTML)})
    doc = await SocialLinkReader(fetch=fetch).read("https://www.instagram.com/reel/XYZ/")
    assert doc.platform == "instagram"
    assert doc.author == "@maker.lab"
    assert "We gave our agent eyes on the machine." in doc.text
    assert doc.extraction_method == "opengraph"


async def test_instagram_login_wall_is_honest() -> None:
    fetch = FakeFetch({"instagram.com": (200, "https://www.instagram.com/accounts/login/", INSTAGRAM_LOGIN_WALL)})
    with pytest.raises(SocialLinkUnavailable) as exc:
        await SocialLinkReader(fetch=fetch).read("https://www.instagram.com/reel/XYZ/")
    assert "login wall" in exc.value.reason


async def test_generic_web_read() -> None:
    fetch = FakeFetch({"example.com": (200, "https://example.com/post", GENERIC_HTML)})
    doc = await SocialLinkReader(fetch=fetch).read("https://example.com/post")
    assert doc.platform == "web"
    assert doc.title == "Deep Dive \u2014 Example Blog"
    assert "verbatim sentence to cite" in doc.text


async def test_reader_is_read_only_by_construction() -> None:
    """Every request the reader makes must be a plain page fetch of the link
    itself or a documented public metadata endpoint — no action endpoints."""
    fetch = FakeFetch(
        {
            "oembed": (200, "https://www.youtube.com/oembed", YOUTUBE_OEMBED),
            "watch?v=": (200, "https://www.youtube.com/watch?v=abc123", YOUTUBE_WATCH),
        }
    )
    await SocialLinkReader(fetch=fetch).read("https://www.youtube.com/watch?v=abc123")
    forbidden = ("like", "comment", "follow", "subscribe", "post?", "/api/")
    for called in fetch.calls:
        assert not any(word in called.lower() for word in forbidden), called


async def test_rejects_non_http_schemes() -> None:
    with pytest.raises(SocialLinkUnavailable):
        await SocialLinkReader(fetch=FakeFetch({})).read("file:///etc/passwd")
