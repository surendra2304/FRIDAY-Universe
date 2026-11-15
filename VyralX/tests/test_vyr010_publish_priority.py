"""TASK-VYR-010 — publish-priority model tests.

The model ranks VyralX's ready pool for the day publishing becomes
possible again. These tests pin the properties that keep it honest:

* it is a metadata heuristic — with no metrics anywhere (the real
  pool's state: VIDEO_METRICS is empty), the engagement component
  never fires and every row is flagged METRICS_NO_DATA;
* the legacy pool's two known defects ride as flags, not silence —
  the blanket licence string is HOLD_PROVENANCE and every unmeasured
  render is SYNC_UNVERIFIED;
* scoring is deterministic, missing inputs renormalise instead of
  zeroing or being invented, and the duration/title curves reward
  the packaging the research supports over the autopsy era's formula.
"""
from __future__ import annotations

from app.services.publish_priority import (
    BLANKET_LICENCE,
    duration_fit,
    format_fit,
    pool_data_profile,
    rank_videos,
    score_video,
    source_signal,
    title_strength,
)


def _row(**kw):
    base = {
        "job_id": 1,
        "youtube_video_id": "abc123XYZ",
        "upload_title": "Only 7 Cheese Balls Left 🧀😳 #Shorts",
        "source_title": "Only 7 Cheese Balls Left🧀😳",
        "duration_seconds": 32.0,
        "width": 1080,
        "height": 1920,
        "created_epoch": 1000.0,
        "job_status": "uploaded",
        "license_name": "CC BY",
        "sync_measured": True,
        "trend_score": 0.0,
        "metrics": None,
    }
    base.update(kw)
    return base


# -- duration curve ---------------------------------------------------------

def test_duration_band_peaks_in_researched_range():
    assert duration_fit(35) > duration_fit(20) > duration_fit(14)
    assert duration_fit(45) >= duration_fit(35)
    assert duration_fit(75) < duration_fit(45)


def test_duration_missing_is_none_not_zero():
    assert duration_fit(None) is None
    assert duration_fit(0) is None


# -- title strength -----------------------------------------------------------

def test_word_salad_title_scores_below_punchy_title():
    salad, _ = title_strength(
        "White Shirt Pavement Pose Meets Cozy Couch Yawn and Car Kiss "
        "😱✨ #Shorts")
    punchy, _ = title_strength("Only 7 Cheese Balls Left 🧀😳 #Shorts")
    assert punchy > salad


def test_title_flags_emoji_spam_and_missing_anchor():
    _, notes = title_strength("Things Happen 😱🔥🤯💥🚀 #Shorts")
    assert any("emoji" in n for n in notes)


def test_title_missing_is_none():
    score, notes = title_strength(None)
    assert score is None and notes


# -- source signal / format ---------------------------------------------------

def test_source_signal_none_without_source():
    assert source_signal(None) is None
    assert source_signal("  ") is None


def test_format_fit_standard_and_outlier():
    assert format_fit(1080, 1920) == 1.0
    assert format_fit(480, 600) < 1.0
    assert format_fit(1920, 1080) < format_fit(480, 600)
    assert format_fit(None, None) is None


# -- scoring behaviour ----------------------------------------------------------

def test_no_metrics_means_engagement_never_fires():
    s = score_video(_row())
    assert "engagement" not in s["components"]
    assert "METRICS_NO_DATA" in s["flags"]
    assert any("engagement" in m for m in s["missing"])


def test_blanket_licence_is_a_hold_flag():
    s = score_video(_row(license_name=BLANKET_LICENCE))
    assert "HOLD_PROVENANCE" in s["flags"]


def test_unmeasured_sync_is_flagged():
    s = score_video(_row(sync_measured=False))
    assert "SYNC_UNVERIFIED" in s["flags"]
    s2 = score_video(_row(sync_measured=True))
    assert "SYNC_UNVERIFIED" not in s2["flags"]


def test_failed_upload_is_flagged_not_hidden():
    s = score_video(_row(job_status="failed", youtube_video_id=None))
    assert "NOT_UPLOADED" in s["flags"]


def test_missing_duration_renormalises_not_zeroes():
    full = score_video(_row())
    partial = score_video(_row(duration_seconds=None))
    assert partial["components"]["duration_fit"] is None
    assert partial["score"] > 0


def test_metrics_when_present_activate_engagement():
    s = score_video(_row(metrics={
        "views": 1000, "likes": 60,
        "_pool_max_views": 1000, "_pool_max_likes": 60,
    }))
    assert s["components"].get("engagement") is not None
    assert "METRICS_NO_DATA" not in s["flags"]


# -- ranking --------------------------------------------------------------------

def test_ranking_is_deterministic_and_ordered():
    rows = [
        _row(job_id=3, duration_seconds=16.0,
             upload_title="Things Happen 😱 #Shorts",
             created_epoch=900.0),
        _row(job_id=1, created_epoch=1000.0),
        _row(job_id=2, duration_seconds=41.0, created_epoch=1100.0),
    ]
    ranked = rank_videos(rows)
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    again = rank_videos(rows)
    assert [r["job_id"] for r in again] == [r["job_id"] for r in ranked]


def test_pool_profile_states_no_data_plainly():
    profile = pool_data_profile([_row(), _row(job_id=2)])
    assert profile["metrics_coverage"] == "0/2"
    assert profile["engagement_component_active"] is False
    assert "NO outcome data" in profile["verdict"]
