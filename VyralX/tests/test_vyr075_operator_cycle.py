"""TASK-VYR-075 — Uplika adapt: approval-gated operator cycle, live.

The channel_operator module (TASK-IG-VYR-01) implemented the Uplika
pattern natively but was only reachable from its unit tests. This
file proves it through the LIVE route surface: a full operator
cycle over a channel snapshot, plus the honest failure cases
(no-metrics snapshot names no winner; unknown lane / empty topic /
naive start are 422s). The plan publishes nothing, ever.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import real_media_routes


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        media_dir=tmp_path / "media",
        render_dir=tmp_path / "renders",
    )
    for d in (settings.data_dir, settings.media_dir, settings.render_dir):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(real_media_routes, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(real_media_routes.router, prefix="/api/v1/vyralx")
    return TestClient(app)


_START = "2026-11-24T18:00:00+05:30"


def test_operator_cycle_end_to_end(tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/vyralx/engines/operator/cycle",
        json={
            "videos": [
                {"title": "Black holes, explained", "lane": "space_science",
                 "format_name": "explainer",
                 "metrics": {"views": 12000, "likes": 900,
                             "comments": 120}},
                {"title": "The Moon landing tapes", "lane": "space_science",
                 "format_name": "explainer",
                 "metrics": {"views": 8000, "likes": 500,
                             "comments": 60}},
                {"title": "Unmeasured draft", "lane": "history",
                 "format_name": "did-you-know"},
            ],
            "topics": [{"topic": "Black holes", "lane": "space_science"}],
            "comments": [{"comment_id": "c1", "author": "viewer1",
                          "text": "How does time dilation work?"}],
            "start": _START,
        })
    assert resp.status_code == 200, resp.text
    plan = resp.json()["plan"]
    # Winners come from measured views only.
    assert plan["analysis"]["metrics_available"] is True
    assert plan["analysis"]["winning_formats"] == ["explainer"]
    assert plan["analysis"]["measured_videos"] == 2
    # Everything is a proposal: nothing publishes.
    assert plan["publishes_anything"] is False
    assert plan["status"] == "pending_review"
    assert all(p["publish"] is False for p in plan["proposals"])
    assert all(s["publish"] is False and s["privacy"] == "unlisted"
               for s in plan["schedule"])
    assert all(d["posted"] is False for d in plan["comment_drafts"])
    # The question comment got a drafted reply, not a posted one.
    assert plan["comment_drafts"][0]["action"] == "reply"
    assert plan["comment_drafts"][0]["status"] == "draft_pending_approval"


def test_operator_cycle_no_metrics_names_no_winner(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/vyralx/engines/operator/cycle",
        json={
            "videos": [{"title": "Draft one", "lane": "history",
                        "format_name": "did-you-know"}],
            "topics": [{"topic": "Roman concrete", "lane": "history"}],
            "comments": [],
            "start": _START,
        })
    assert resp.status_code == 200, resp.text
    analysis = resp.json()["plan"]["analysis"]
    assert analysis["metrics_available"] is False
    assert analysis["winning_formats"] == []
    assert analysis["measured_videos"] == 0


def test_operator_cycle_failures_are_422(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    base = {"videos": [], "topics": [{"topic": "X", "lane": "history"}],
            "comments": [], "start": _START}
    # Unknown lane.
    bad_lane = dict(base, topics=[{"topic": "X", "lane": "nope"}])
    assert client.post("/api/v1/vyralx/engines/operator/cycle",
                       json=bad_lane).status_code == 422
    # Empty topic.
    bad_topic = dict(base, topics=[{"topic": "", "lane": "history"}])
    assert client.post("/api/v1/vyralx/engines/operator/cycle",
                       json=bad_topic).status_code == 422
    # Naive start (no timezone) — the cycle requires tz-aware input.
    bad_start = dict(base, start="2026-11-24T18:00:00")
    assert client.post("/api/v1/vyralx/engines/operator/cycle",
                       json=bad_start).status_code == 422
