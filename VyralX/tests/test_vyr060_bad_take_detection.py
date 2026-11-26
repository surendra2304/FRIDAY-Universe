"""TASK-VYR-060: automatic bad-take detection per render segment
in the render QA chain.

Behaviour pinned here:

* each caption segment is judged on its own window: black and
  silence intervals are clipped to the segment, so a bad take
  in one segment cannot hide inside a whole-render pass and a
  clean segment is not blamed for another segment's glitch;
* a sustained black overlapping a segment (>= 0.5 s, the
  blackdetect minimum and the whole-render black bar) flags
  that segment; a small edge overlap below the bar does not;
* silence flags a segment when one silence runs longer than
  2.0 s (the whole-render silence floor) or silence covers
  more than half the segment; a short pause does not;
* timed words, when the caller carries them, are scored by
  score_take: a delivery with no kept words, or at least two
  retakes + false starts, is an awkward take; a clean delivery
  passes;
* an unavailable signal scan is reported unavailable, never
  as passing — a segment with no measured half reports
  passed None;
* malformed segments are skipped and counted, never invented;
  loudness and clipping ride along as whole-render context,
  never as per-segment judgements;
* project_pipeline records the verdict into the QA report of
  the held render (source-level wiring check).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import take_verification as tv


_PIPELINE = (Path(__file__).resolve().parent.parent / "app"
             / "services" / "project_pipeline.py")


def _words(text, *, start=0.0, step=0.3):
    return [{"word": w, "start": round(start + i * step, 2),
             "end": round(start + i * step + 0.25, 2)}
            for i, w in enumerate(text.split())]


def _cue(text, start, end, timed_words=None):
    cue = {"start_seconds": start, "end_seconds": end, "text": text}
    if timed_words is not None:
        cue["timed_words"] = timed_words
    return cue


def _signals(black=None, silence=None):
    return {
        "status": "analyzed",
        "error_type": None,
        "black_intervals": black or [],
        "silence_intervals": silence or [],
        "audio_analyzed": True,
        "audio_metrics": {
            "status": "analyzed",
            "integrated_loudness_lufs": -16.5,
            "true_peak_dbfs": -1.5,
            "clipped_samples": 0,
        },
        "thresholds": {
            "black_min_duration_seconds": 0.5,
            "silence_threshold_db": -45,
            "silence_min_duration_seconds": 1.0,
            "loudness_min_lufs": -24.0,
            "loudness_max_lufs": -10.0,
            "true_peak_max_dbfs": -1.0,
            "clipped_samples_max": 0,
        },
    }


_CLEAN_SEGMENTS = [
    _cue("the lighthouse keeper watched the sea", 0.0, 4.0),
    _cue("every single night he lit the lamp", 4.0, 8.0),
    _cue("and the ships found their way home", 8.0, 12.0),
]


def test_clean_render_all_segments_pass():
    result = tv.detect_bad_takes(_CLEAN_SEGMENTS, _signals())
    assert result["kind"] == "bad_take_detection"
    assert result["task"] == "TASK-VYR-060"
    assert result["status"] == "measured"
    assert result["passed"] is True
    assert result["segment_count"] == 3
    assert result["bad_segment_count"] == 0
    assert result["bad_segment_ids"] == []
    assert result["skipped_segments"] == []
    assert all(s["passed"] is True for s in result["segments"])
    assert all(s["signals_measured"] is True for s in result["segments"])
    assert result["audio_context"]["integrated_loudness_lufs"] == -16.5
    assert result["audio_context"]["clipped_samples"] == 0


def test_black_overlap_flags_each_segment_it_touches():
    black = [{"start_seconds": 5.0, "end_seconds": 9.0,
              "duration_seconds": 4.0}]
    result = tv.detect_bad_takes(_CLEAN_SEGMENTS, _signals(black=black))
    assert result["passed"] is False
    assert result["bad_segment_count"] == 2
    assert result["bad_segment_ids"] == ["segment-2", "segment-3"]
    flagged = {s["segment_id"]: s for s in result["segments"]}
    assert flagged["segment-1"]["passed"] is True
    seg2 = flagged["segment-2"]
    assert seg2["blank_seconds"] == 3.0
    assert seg2["longest_blank_s"] == 3.0
    assert seg2["blank_ratio"] == 0.75
    assert seg2["failures"][0]["kind"] == "blank_in_segment"
    assert flagged["segment-3"]["blank_seconds"] == 1.0


def test_small_edge_overlap_below_the_bar_is_not_a_bad_take():
    black = [{"start_seconds": 3.8, "end_seconds": 4.3,
              "duration_seconds": 0.5}]
    result = tv.detect_bad_takes(_CLEAN_SEGMENTS, _signals(black=black))
    assert result["passed"] is True
    assert result["segments"][0]["blank_seconds"] == 0.2
    assert result["segments"][0]["longest_blank_s"] == 0.2
    assert result["segments"][1]["blank_seconds"] == 0.3


def test_silence_dominating_a_segment_flags_it():
    silence = [{"start_seconds": 10.0, "end_seconds": 16.0,
                "duration_seconds": 6.0}]
    segments = [_cue("the lighthouse keeper watched the sea", 0.0, 4.0),
                _cue("every single night he lit the lamp", 10.0, 14.0)]
    result = tv.detect_bad_takes(segments, _signals(silence=silence))
    assert result["bad_segment_ids"] == ["segment-2"]
    seg = result["segments"][1]
    assert seg["silence_seconds"] == 4.0
    assert seg["silence_ratio"] == 1.0
    assert seg["longest_silence_s"] == 4.0
    kinds = {f["kind"] for f in seg["failures"]}
    assert kinds == {"long_silence_in_segment",
                     "silence_dominates_segment"}


def test_short_silence_is_not_a_bad_take():
    silence = [{"start_seconds": 1.0, "end_seconds": 2.2,
                "duration_seconds": 1.2}]
    segments = [_cue("the lighthouse keeper watched the sea", 0.0, 10.0)]
    result = tv.detect_bad_takes(segments, _signals(silence=silence))
    assert result["passed"] is True
    assert result["segments"][0]["silence_seconds"] == 1.2
    assert result["segments"][0]["silence_ratio"] == 0.12


def test_retake_heavy_delivery_is_an_awkward_take():
    awkward = _cue("the lighthouse keeper watched the sea", 0.0, 10.0,
                   timed_words=_words(
                       "the the lighthouse um keeper watched the sea"))
    clean = _cue("every single night he lit the lamp", 10.0, 20.0,
                 timed_words=_words(
                     "every single night he lit the lamp"))
    result = tv.detect_bad_takes([awkward, clean], _signals())
    assert result["bad_segment_ids"] == ["segment-1"]
    seg = result["segments"][0]
    assert seg["transcript_measured"] is True
    assert seg["transcript"]["cuts"]["retake"] == 1
    assert seg["transcript"]["cuts"]["false_start"] == 1
    assert seg["failures"][0]["kind"] == "awkward_delivery"
    assert result["segments"][1]["passed"] is True


def test_delivery_with_no_kept_words_is_an_awkward_take():
    silent = _cue("um uh", 0.0, 4.0,
                  timed_words=_words("um uh"))
    result = tv.detect_bad_takes([silent], _signals())
    assert result["bad_segment_ids"] == ["segment-1"]
    assert result["segments"][0]["transcript"]["kept_words"] == 0


def test_unmeasured_scan_is_never_a_pass():
    result = tv.detect_bad_takes(_CLEAN_SEGMENTS, None)
    assert result["status"] == "unavailable"
    assert result["passed"] is None
    assert all(s["passed"] is None for s in result["segments"])
    assert all(s["signals_measured"] is False
               for s in result["segments"])
    unavailable = {"status": "unavailable", "error_type": "ffmpeg_exit",
                   "black_intervals": [], "silence_intervals": [],
                   "audio_analyzed": True,
                   "audio_metrics": {"status": "unavailable",
                                     "integrated_loudness_lufs": None,
                                     "true_peak_dbfs": None,
                                     "clipped_samples": None}}
    result = tv.detect_bad_takes(_CLEAN_SEGMENTS, unavailable)
    assert result["status"] == "unavailable"
    assert result["passed"] is None


def test_malformed_segments_are_skipped_never_invented():
    segments = [
        "not a segment",
        {"start_seconds": 5.0, "end_seconds": 5.0, "text": "empty"},
        {"start_seconds": "x", "end_seconds": 9.0, "text": "bad"},
        _cue("the lighthouse keeper watched the sea", 0.0, 4.0),
    ]
    result = tv.detect_bad_takes(segments, _signals())
    assert result["segment_count"] == 1
    assert len(result["skipped_segments"]) == 3
    assert result["segments"][0]["segment_id"] == "segment-4"
    assert result["segments"][0]["passed"] is True


def test_empty_segments_are_vacuous_not_a_pass_claim():
    result = tv.detect_bad_takes([], _signals())
    assert result["status"] == "measured"
    assert result["passed"] is True
    assert result["segment_count"] == 0
    assert result["bad_segment_count"] == 0
    assert "nothing to judge" in result["basis"]


def test_audio_context_is_whole_render_only():
    result = tv.detect_bad_takes(_CLEAN_SEGMENTS, _signals())
    assert result["audio_context"]["true_peak_dbfs"] == -1.5
    assert "whole-render" in result["audio_context"]["scope"]


def test_project_pipeline_records_bad_take_detection():
    source = _PIPELINE.read_text(encoding="utf-8")
    assert "detect_bad_takes" in source
    assert 'qa_report["bad_take_detection"]' in source
