"""TASK-IG3-VYR-05: best-take selection + blank-frame verification
(clusters B119 + B121).

Behaviour pinned here:

* ffmpeg blackdetect output parses into exactly the segments
  the filter reported — nothing invented, nothing dropped;
* the blank gate fails a recording on a long single blank or
  an excessive blank share, and reports the measured numbers
  either way;
* take scoring reuses style_recipe.clean_transcript: kept words
  are the payload, retakes/false starts are penalised, pauses
  are evidence only;
* best-take selection is deterministic and ships the full
  evidence table, not just a winner;
* a recording with no kept words fails verification even when
  its blank gate passes;
* the router answers through the app pattern and app.main
  mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: the module does not exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import take_verification as tv

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")

_BLACKDETECT = (
    "[blackdetect @ 0x55a0] black_start:12.34 black_end:15.01 "
    "black_duration:2.67\n"
    "[blackdetect @ 0x55a0] black_start:40.0 black_end:40.4 "
    "black_duration:0.4\n"
)


def _words(text, *, step=0.3):
    return [{"word": w, "start": round(i * step, 2),
             "end": round(i * step + 0.25, 2)}
            for i, w in enumerate(text.split())]


_GOOD = {"take_id": "take-2",
         "timed_words": _words("the lighthouse keeper watched the sea")}
_MESSY = {"take_id": "take-1",
          "timed_words": _words("the the lighthouse um keeper "
                                "watched the sea")}


def test_parse_blackdetect_reads_exactly_what_the_filter_reported():
    segments = tv.parse_blackdetect(_BLACKDETECT)
    assert segments == [
        {"start": 12.34, "end": 15.01, "duration": 2.67},
        {"start": 40.0, "end": 40.4, "duration": 0.4},
    ]
    assert tv.parse_blackdetect("") == []
    assert tv.parse_blackdetect("no detections in this log") == []


def test_blank_gate_fails_long_blank_and_high_ratio_with_numbers():
    gate = tv.blank_gate(tv.parse_blackdetect(_BLACKDETECT),
                         duration_s=60.0)
    assert gate["passed"] is False
    assert gate["blank_seconds"] == 3.07
    assert gate["longest_blank_s"] == 2.67
    kinds = {f["kind"] for f in gate["failures"]}
    assert kinds == {"single_blank_too_long", "blank_ratio_too_high"}


def test_blank_gate_passes_a_clean_recording():
    gate = tv.blank_gate(
        [{"start": 5.0, "end": 5.4, "duration": 0.4}], duration_s=60.0)
    assert gate["passed"] is True
    assert gate["blank_ratio"] == round(0.4 / 60.0, 4)
    assert gate["failures"] == []
    empty = tv.blank_gate([], duration_s=60.0)
    assert empty["passed"] is True
    assert empty["blank_seconds"] == 0
    with pytest.raises(ValueError):
        tv.blank_gate([], duration_s=0)


def test_score_take_reuses_clean_transcript_evidence():
    good = tv.score_take(_GOOD)
    assert good["kept_words"] == 6
    assert good["cuts"] == {"retake": 0, "false_start": 0,
                            "pause": 0, "total": 0}
    assert good["score"] == 6
    messy = tv.score_take(_MESSY)
    assert messy["kept_words"] == 6
    assert messy["cuts"]["retake"] == 1
    assert messy["cuts"]["false_start"] == 1
    assert messy["score"] == 6 - 3 - 2
    # Pauses are evidence, not a penalty.
    paused = tv.score_take({"take_id": "take-3", "timed_words": [
        {"word": "hello", "start": 0.0, "end": 0.25},
        {"word": "world", "start": 2.0, "end": 2.25}]})
    assert paused["cuts"]["pause"] == 1
    assert paused["score"] == 2
    with pytest.raises(ValueError, match="timed_words"):
        tv.score_take({"take_id": "take-x"})


def test_select_best_take_is_deterministic_and_shows_the_table():
    result = tv.select_best_take([_MESSY, _GOOD])
    assert result["best_take_id"] == "take-2"
    assert [r["take_id"] for r in result["ranking"]] == \
        ["take-2", "take-1"]
    assert result["status"] == "pending_review"
    again = tv.select_best_take([_GOOD, _MESSY])
    assert again["best_take_id"] == "take-2"
    with pytest.raises(ValueError):
        tv.select_best_take([])


def test_verify_recording_combines_transcript_and_blank_gate():
    ok = tv.verify_recording(_GOOD, "", duration_s=30.0)
    assert ok["passed"] is True
    blanked = tv.verify_recording(_GOOD, _BLACKDETECT, duration_s=60.0)
    assert blanked["passed"] is False
    assert blanked["blank_gate"]["passed"] is False
    silent = tv.verify_recording(
        {"take_id": "take-0", "timed_words": []}, "", duration_s=30.0)
    assert silent["passed"] is False
    assert silent["transcript"]["kept_words"] == 0


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(tv.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/take-verification/policy")
    assert res.status_code == 200
    assert res.json()["publish"] is False

    res = client.post("/api/v1/take-verification/blank-gate", json={
        "blackdetect_output": _BLACKDETECT, "duration_s": 60.0})
    assert res.status_code == 200
    assert res.json()["passed"] is False

    res = client.post("/api/v1/take-verification/blank-gate", json={
        "blackdetect_output": "", "duration_s": 0})
    assert res.status_code == 422

    res = client.post("/api/v1/take-verification/best-take",
                      json={"takes": [_MESSY, _GOOD]})
    assert res.status_code == 200
    assert res.json()["best_take_id"] == "take-2"

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.take_verification import router as " \
        "take_verification_router" in main_src
    assert "app.include_router(take_verification_router" in main_src
