"""TASK-VYR-019: the all-category trending sweep returns ordinary
Candidates filed under series labels, filtered by the loop's bounds,
and honestly empty under the reuse_licensed policy (the chart cannot
prove a licence for anyone)."""
from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services import viral_trending


def _item(video_id, *, views=1_000_000, duration="PT40S", published="2026-11-01T00:00:00Z"):
    return {
        "id": video_id,
        "snippet": {
            "title": f"Video {video_id}",
            "channelTitle": "Some Channel",
            "publishedAt": published,
            "categoryId": "17",
            "description": "desc",
            "tags": ["x"],
        },
        "contentDetails": {"duration": duration},
        "statistics": {"viewCount": str(views), "likeCount": "5000", "commentCount": "100"},
    }


class _Request:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _Videos:
    def __init__(self, by_category):
        self._by_category = by_category
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return _Request({"items": self._by_category.get(kwargs["videoCategoryId"], [])})


class _Service:
    def __init__(self, by_category):
        self._videos = _Videos(by_category)

    def videos(self):
        return self._videos


def test_sweep_labels_filters_and_dedupes():
    service = _Service({
        "17": [_item("sport1"), _item("lowviews", views=10)],
        "20": [_item("game1"), _item("toolong", duration="PT20M")],
        "23": [_item("sport1")],  # same video charting in two categories
    })
    found = viral_trending.trending_candidates(
        per_category=5, service=service, max_seconds=600.0,
    )
    by_id = {candidate.video_id: candidate for candidate in found}
    assert set(by_id) == {"sport1", "game1"}
    assert by_id["sport1"].category == "SPORTS"
    assert by_id["game1"].category == "GAMING"
    assert by_id["sport1"].license == "transformative_commentary"
    assert by_id["sport1"].duration == 40.0
    # One call per assignable category, chart pinned to mostPopular.
    assert all(call["chart"] == "mostPopular" for call in service.videos().calls)


def test_sweep_honours_exclusions():
    service = _Service({"17": [_item("sport1"), _item("sport2")]})
    found = viral_trending.trending_candidates(
        per_category=5, service=service, exclude_ids={"sport1"},
    )
    assert [candidate.video_id for candidate in found] == ["sport2"]


def test_reuse_licensed_policy_yields_nothing(tmp_path, monkeypatch):
    settings = Settings(
        data_dir=tmp_path / "data", media_dir=tmp_path / "media",
        render_dir=tmp_path / "renders", viral_source_policy="reuse_licensed",
    )
    monkeypatch.setattr(viral_trending, "get_settings", lambda: settings)
    service = _Service({"17": [_item("sport1")]})
    assert viral_trending.trending_candidates(service=service) == []
