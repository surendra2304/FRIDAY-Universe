"""TASK-IG3-VYR-03: Reddit story sourcing (cluster B113).

Behaviour pinned here:

* a Reddit listing payload parses into normalised post records,
  and an unrecognised payload is refused, never guessed at;
* fetching goes through an injectable fetcher (the URL is the
  public JSON endpoint; a bad subreddit or listing is refused
  before any fetch happens);
* story selection is deterministic and honest: self-posts with
  real body text only, stickied never, NSFW excluded by default,
  ranked by score then comments;
* every brief carries its provenance and is rewrite-required —
  the source text is excerpted for identification, never handed
  over as a script;
* briefs enqueue onto the VYR-004 review queue, and the module's
  router answers through the app pattern with app.main mounting
  it (AUDIT-2 production-caller standard).

On clean main every test fails: the module does not exist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import reddit_trends as rt

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")

_LONG = ("It began on the night the lighthouse went dark. " * 12).strip()


def _post(pid, **kw):
    base = {
        "id": pid, "subreddit": "nosleep", "author": "someone",
        "title": f"Story {pid}", "selftext": _LONG, "score": 100,
        "num_comments": 10, "permalink": f"/r/nosleep/comments/{pid}/x/",
        "created_utc": 1700000000.0, "stickied": False,
        "over_18": False, "is_self": True,
    }
    base.update(kw)
    return base


def _listing(*posts):
    return {"data": {"children": [{"data": p} for p in posts]}}


def test_parse_listing_normalises_posts():
    posts = rt.parse_listing(_listing(_post("a1", score=42)))
    assert len(posts) == 1
    post = posts[0]
    assert post["post_id"] == "a1"
    assert post["score"] == 42
    assert post["url"] == "https://www.reddit.com/r/nosleep/comments/a1/x/"
    assert post["is_self"] is True


def test_parse_listing_accepts_bare_list_and_refuses_garbage():
    assert len(rt.parse_listing([_post("b2")])) == 1
    with pytest.raises(ValueError):
        rt.parse_listing({"unexpected": True})
    with pytest.raises(ValueError):
        rt.parse_listing("not a listing")


def test_listing_url_and_fetch_with_injected_fetcher():
    seen = {}

    def fake_fetcher(url):
        seen["url"] = url
        return _listing(_post("c3"))

    posts = rt.fetch_listing("nosleep", fetcher=fake_fetcher, limit=5)
    assert seen["url"] == ("https://www.reddit.com/r/nosleep/top.json"
                           "?t=week&limit=5&raw_json=1")
    assert [p["post_id"] for p in posts] == ["c3"]
    with pytest.raises(ValueError):
        rt.fetch_listing("bad name!", fetcher=fake_fetcher)
    with pytest.raises(ValueError):
        rt.fetch_listing("nosleep", fetcher=fake_fetcher, listing="bogus")


def test_select_stories_filters_and_ranks_deterministically():
    posts = rt.parse_listing(_listing(
        _post("low", score=5, num_comments=1),
        _post("sticky", score=9999, stickied=True),
        _post("link", score=9999, is_self=False),
        _post("short", score=9999, selftext="too short"),
        _post("nsfw", score=9999, over_18=True),
        _post("high", score=500, num_comments=3),
        _post("mid", score=500, num_comments=40),
    ))
    selected = rt.select_stories(posts)
    assert [p["post_id"] for p in selected] == ["mid", "high", "low"]
    # The same input selects identically on a second pass.
    assert [p["post_id"] for p in rt.select_stories(posts)] == \
        ["mid", "high", "low"]
    # NSFW joins only when explicitly allowed.
    assert rt.select_stories(posts, include_nsfw=True)[0]["post_id"] == "nsfw"
    # A score floor is honoured.
    assert [p["post_id"] for p in rt.select_stories(posts, min_score=100)] \
        == ["mid", "high"]


def test_story_brief_carries_provenance_and_requires_rewrite():
    brief = rt.story_brief(rt.parse_listing(_listing(_post("d4")))[0])
    assert brief["kind"] == "reddit_story_brief"
    assert brief["ig_source"] == "Dd4D7qrgb9V"
    assert brief["rewrite_required"] is True
    assert brief["status"] == "pending_review"
    assert brief["publish"] is False
    src = brief["source"]
    assert src["platform"] == "reddit"
    assert src["subreddit"] == "nosleep"
    assert src["post_id"] == "d4"
    assert src["url"].endswith("/r/nosleep/comments/d4/x/")
    # Excerpt is identification-sized, not the story.
    assert brief["excerpt_truncated"] is True
    assert len(brief["excerpt"]) <= 300
    assert brief["word_count"] > len(brief["excerpt"].split())


def test_build_briefs_counts_received_vs_eligible():
    result = rt.build_briefs(_listing(
        _post("e5"), _post("e6", is_self=False)))
    assert result["received"] == 2
    assert result["eligible"] == 1
    assert [b["source"]["post_id"] for b in result["briefs"]] == ["e5"]


def test_enqueue_briefs_writes_review_queue_records(tmp_path):
    result = rt.build_briefs(_listing(_post("f7"), _post("f8")))
    queue = tmp_path / "queue.jsonl"
    assert rt.enqueue_briefs(result["briefs"], queue) == 2
    lines = queue.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert {r["kind"] for r in records} == {"reddit_story_brief"}
    assert all(r["rewrite_required"] for r in records)


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(rt.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/reddit-trends/policy")
    assert res.status_code == 200
    assert res.json()["rewrite_required"] is True

    res = client.post("/api/v1/reddit-trends/briefs",
                      json={"listing": _listing(_post("g9"))})
    assert res.status_code == 200
    body = res.json()
    assert body["eligible"] == 1
    assert body["briefs"][0]["source"]["post_id"] == "g9"

    res = client.post("/api/v1/reddit-trends/briefs",
                      json={"listing": {"bogus": 1}})
    assert res.status_code == 422

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.reddit_trends import router as " \
        "reddit_trends_router" in main_src
    assert "app.include_router(reddit_trends_router" in main_src
