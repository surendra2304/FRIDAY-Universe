"""TASK-VYR-044: machine-QA gates over the held-render pool.

Behaviour pinned here:

* ASS parsing: timestamps parse to seconds; malformed Dialogue
  lines are skipped and counted, never invented; the track count
  is the max distinct (style, text) tracks active at once, so the
  doubled-caption class (two tracks ~1s out of sync) counts 2;
* voiced/voiceless split: dialogue intervals union into voiced
  stretches; gaps >= 1.0 s (head, between, tail) are voiceless;
* loudness: pass iff integrated LUFS in [-24, -10] and true peak
  <= -1.0 dBFS; an unmeasured scan reports loudness_unmeasured;
  clipped_samples rides along as context only (None on the
  deployed scanner, never a pass/fail input);
* BGM: pass iff every voiceless gap measures above the -45 dBFS
  floor and no silence interval from the loudness scan falls in a
  voiceless stretch; a silent gap is a bed dropout. When the speech
  union tiles the whole render, a silence interval is itself the
  absence evidence, and with neither a gap nor a silence interval
  the gate is unmeasured;
* watermark: pass iff the ffprobe comment marker
  ``vyralx-provenance:`` is present; the LSB payload is reported,
  never required; a failed probe fails watermark_unmeasured;
* caption: the VYR-045 gate over the sampler; a sampler returning
  None reports caption_gate_unmeasured — fail-closed, never a pass;
  a single track passes, two tracks fail multiple_caption_tracks:2;
* run_held_render_qa wires all four gates and fails overall when
  any gate fails; the ASS corroboration (track count, event count)
  is reported alongside the vision verdict.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import held_render_qa as hrq


_ASS_SINGLE = """[Script Info]
Title: single
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Anton,,0,0,0,,Hello world
Dialogue: 0,0:00:04.00,0:00:06.00,Anton,,0,0,0,,Second line
"""

_ASS_DOUBLED = """[Script Info]
Title: doubled
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Anton,,0,0,0,,Same words here
Dialogue: 0,0:00:02.00,0:00:05.00,Anton2,,0,0,0,,Same words here
Dialogue: 0,0:00:06.00,0:00:08.00,Anton,,0,0,0,,Later clean line
"""

_ASS_MALFORMED = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.00,Anton,,0,0,0,,Good line
Dialogue: 0,not-a-time,0:00:03.00,Anton,,0,0,0,,Bad start
Dialogue: 0,0:00:03.00,0:00:02.00,Anton,,0,0,0,,End before start
Dialogue: 0,0:00:04.00
"""


def _write_ass(tmp_path, text, name="render.ass"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _signals(loudness=None, peak=None, clipped=None, status="analyzed"):
    return {
        "status": status,
        "error_type": None,
        "audio_metrics": {
            "integrated_loudness_lufs": loudness,
            "true_peak_dbfs": peak,
            "clipped_samples": clipped,
        },
    }


# --- ASS parsing ------------------------------------------------------


def test_parse_ass_timestamp_valid_and_invalid():
    assert hrq.parse_ass_timestamp("0:00:01.00") == 1.0
    assert hrq.parse_ass_timestamp("1:02:03.50") == 3723.5
    assert hrq.parse_ass_timestamp("not-a-time") is None
    assert hrq.parse_ass_timestamp("") is None


def test_parse_ass_dialogue_single_track(tmp_path):
    events, malformed = hrq.parse_ass_dialogue(
        _write_ass(tmp_path, _ASS_SINGLE))
    assert malformed == 0
    assert len(events) == 2
    assert events[0]["start"] == 1.0 and events[0]["end"] == 3.0
    assert hrq.ass_caption_track_count(events) == 1


def test_parse_ass_dialogue_doubled_track_counts_two(tmp_path):
    events, malformed = hrq.parse_ass_dialogue(
        _write_ass(tmp_path, _ASS_DOUBLED))
    assert malformed == 0
    assert len(events) == 3
    # Two tracks overlap 2.0–4.0 s (the 823/841/861 class).
    assert hrq.ass_caption_track_count(events) == 2


def test_parse_ass_dialogue_malformed_skipped_and_counted(tmp_path):
    events, malformed = hrq.parse_ass_dialogue(
        _write_ass(tmp_path, _ASS_MALFORMED))
    assert malformed == 3
    assert len(events) == 1
    assert hrq.ass_caption_track_count(events) == 1


def test_parse_ass_dialogue_missing_file():
    events, malformed = hrq.parse_ass_dialogue("/nonexistent/render.ass")
    assert events == [] and malformed == 0


def test_voiced_segments_union_and_gaps():
    events = [
        {"start": 1.0, "end": 3.0, "style": "A", "text": "x"},
        {"start": 2.5, "end": 4.0, "style": "A", "text": "y"},
        {"start": 6.0, "end": 7.0, "style": "A", "text": "z"},
    ]
    voiced, voiceless = hrq.voiced_segments(events, 10.0)
    assert voiced == [(1.0, 4.0), (6.0, 7.0)]
    assert voiceless == [(0.0, 1.0), (4.0, 6.0), (7.0, 10.0)]


def test_voiced_segments_short_gaps_not_voiceless():
    events = [{"start": 1.0, "end": 2.0, "style": "A", "text": "x"},
              {"start": 2.4, "end": 3.4, "style": "A", "text": "y"}]
    voiced, voiceless = hrq.voiced_segments(events, 4.0)
    assert voiced == [(1.0, 2.0), (2.4, 3.4)]
    # 0.4 s gap excluded; 1.0 s head and 0.6 s tail included.
    assert voiceless == [(0.0, 1.0), (3.4, 4.0)]


_ASS_HOOK_AND_TAGS = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.33,AntonFraming,,0,0,0,,{\\c&H00FFE5&} WATCH A CLASSIC {\\fscx115\\fscy115}1970{\\c&H00FFE5&} CHARGER
Dialogue: 0,0:00:01.00,0:00:03.00,AntonBold,,0,0,0,,{\\c&H00E5FF&} TODAY WE FIND OUT
Dialogue: 0,0:00:04.00,0:00:06.00,AntonBold,,0,0,0,,Second line here
"""


def test_parse_ass_dialogue_strips_override_tags_and_hook(tmp_path):
    events, malformed = hrq.parse_ass_dialogue(
        _write_ass(tmp_path, _ASS_HOOK_AND_TAGS))
    assert malformed == 0
    assert len(events) == 3
    assert events[0]["style"] == "AntonFraming"
    assert "{" not in events[0]["text"]
    assert events[0]["text"].startswith("WATCH A CLASSIC 1970")
    speech = hrq.speech_events(events)
    assert len(speech) == 2
    assert all(e["style"] != "AntonFraming" for e in speech)
    # Speech-only count: the two speech events do not overlap, and the
    # hook layer no longer inflates the count.
    assert hrq.ass_caption_track_count(speech) == 1
    assert hrq.ass_caption_track_count(events) == 2


# --- loudness ---------------------------------------------------------


def test_loudness_gate_pass_carries_clipped_none():
    ok, reason, detail = hrq.loudness_gate(_signals(-14.2, -1.2, None))
    assert (ok, reason) == (True, "loudness_ok")
    assert detail["clipped_samples"] is None


def test_loudness_gate_out_of_range_and_peak():
    ok, reason, _ = hrq.loudness_gate(_signals(-30.0, -1.2, None))
    assert (ok, reason) == (False, "loudness_out_of_range")
    ok, reason, _ = hrq.loudness_gate(_signals(-14.0, -0.2, None))
    assert (ok, reason) == (False, "true_peak_too_high")


def test_loudness_gate_unmeasured_never_passes():
    ok, reason, _ = hrq.loudness_gate(_signals(None, None, None))
    assert (ok, reason) == (False, "loudness_unmeasured")
    ok, reason, _ = hrq.loudness_gate(
        {"status": "unavailable", "error_type": "ffmpeg_exit"})
    assert (ok, reason) == (False, "loudness_unmeasured:ffmpeg_exit")


# --- BGM --------------------------------------------------------------


def _events():
    return [
        {"start": 2.0, "end": 5.0, "style": "A", "text": "voice"},
        {"start": 8.0, "end": 11.0, "style": "A", "text": "more voice"},
    ]


def _measure_factory(voiced_dbfs, voiceless_dbfs):
    def measure(render_path, start, end, *, ffmpeg_bin="ffmpeg"):
        # Voiced windows are 2–5 s and 8–11 s; the rest is voiceless.
        if start >= 2.0 and end <= 5.0 or start >= 8.0 and end <= 11.0:
            return voiced_dbfs
        return voiceless_dbfs
    return measure


def test_bgm_gate_present_in_both():
    ok, reason, detail = hrq.bgm_gate(
        "render.mp4", _events(), 12.0, audio_stream_count=1,
        measure=_measure_factory(-20.0, -30.0))
    assert (ok, reason) == (True, "bgm_present")
    assert detail["voiced_mean_dbfs"] == -20.0
    assert detail["voiceless_mean_dbfs"] == -30.0


def test_bgm_gate_absent_in_voiceless_gaps():
    ok, reason, detail = hrq.bgm_gate(
        "render.mp4", _events(), 12.0, audio_stream_count=1,
        measure=_measure_factory(-18.0, -60.0))
    assert (ok, reason) == (False, "bgm_absent_voiceless")
    assert detail["silent_voiceless_gaps"]


def test_bgm_gate_silence_interval_in_gap_is_absence():
    ok, reason, detail = hrq.bgm_gate(
        "render.mp4", _events(), 12.0, audio_stream_count=1,
        silence_intervals=[{"start_seconds": 5.5, "end_seconds": 7.0}],
        measure=_measure_factory(-18.0, -30.0))
    assert (ok, reason) == (False, "bgm_absent_voiceless")
    assert detail["silent_voiceless_gaps"][0]["start_seconds"] == 5.0


def test_bgm_gate_no_gap_silence_is_evidence_unmeasured_without():
    tiling = [{"start": 0.0, "end": 12.0, "style": "A", "text": "wall"}]
    ok, reason, _ = hrq.bgm_gate(
        "render.mp4", tiling, 12.0, audio_stream_count=1,
        silence_intervals=[{"start_seconds": 3.0, "end_seconds": 5.0}],
        measure=_measure_factory(-18.0, -30.0))
    assert (ok, reason) == (False, "bgm_absent_voiceless")
    ok, reason, _ = hrq.bgm_gate(
        "render.mp4", tiling, 12.0, audio_stream_count=1,
        silence_intervals=[],
        measure=_measure_factory(-18.0, -30.0))
    assert (ok, reason) == (False, "bgm_unmeasured")


def test_bgm_gate_no_audio_stream_and_unmeasured():
    ok, reason, _ = hrq.bgm_gate(
        "render.mp4", _events(), 12.0, audio_stream_count=0,
        measure=_measure_factory(-20.0, -30.0))
    assert (ok, reason) == (False, "no_audio_stream")
    ok, reason, _ = hrq.bgm_gate(
        "render.mp4", _events(), 12.0, audio_stream_count=1,
        measure=lambda *a, **k: None)
    assert (ok, reason) == (False, "bgm_unmeasured")


# --- watermark --------------------------------------------------------


def test_watermark_gate_marker_present_lsb_reported(tmp_path):
    from PIL import Image

    frame = tmp_path / "frame.png"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(frame)
    ok, reason, detail = hrq.watermark_gate(
        "render.mp4",
        ffprobe=lambda p: {"comment": "vyralx-provenance:rec-1"},
        extract_frame=lambda p, at: frame,
        extract_payload=lambda image: b"payload",
    )
    assert (ok, reason) == (True, "watermark_present")
    assert detail["marker_present"] is True
    assert detail["lsb_payload_present"] is True


def test_watermark_gate_absent_is_a_table_result_not_a_skip():
    ok, reason, detail = hrq.watermark_gate(
        "render.mp4",
        ffprobe=lambda p: {},
        extract_frame=lambda p, at: None,
        extract_payload=lambda image: None,
    )
    assert (ok, reason) == (False, "watermark_absent")
    assert detail["marker_present"] is False
    assert detail["lsb_payload_present"] is None


def test_watermark_gate_unmeasured_on_probe_failure():
    ok, reason, _ = hrq.watermark_gate(
        "render.mp4", ffprobe=lambda p: None)
    assert (ok, reason) == (False, "watermark_unmeasured")


# --- caption ----------------------------------------------------------


def _detections(n_tracks):
    if n_tracks == 1:
        return [{"y": 900, "start": 1.0, "end": 3.0, "text": "Hello"}]
    if n_tracks == 2:
        # The two tracks carry the same words ~1 s out of sync, so at
        # any instant the visible texts differ — that is what the
        # VYR-045 gate counts (distinct texts active at once).
        return [
            {"y": 900, "start": 1.0, "end": 4.0, "text": "Same words here now"},
            {"y": 860, "start": 2.0, "end": 5.0, "text": "Same words here"},
        ]
    return []


def test_caption_gate_single_track_passes():
    ok, reason, detail = hrq.caption_gate(
        "render.mp4", 10.0,
        sampler=lambda p, d: _detections(1))
    assert (ok, reason) == (True, "single_caption_track")
    assert detail["tracks"] == 1


def test_caption_gate_doubled_track_fails():
    ok, reason, detail = hrq.caption_gate(
        "render.mp4", 10.0,
        sampler=lambda p, d: _detections(2))
    assert (ok, reason) == (False, "multiple_caption_tracks:2")
    assert detail["tracks"] == 2


def test_caption_gate_unmeasured_never_passes():
    ok, reason, _ = hrq.caption_gate(
        "render.mp4", 10.0, sampler=lambda p, d: None)
    assert (ok, reason) == (False, "caption_gate_unmeasured")


# --- wiring -----------------------------------------------------------


def test_run_held_render_qa_wires_all_four_gates(tmp_path):
    ass = _write_ass(tmp_path, _ASS_SINGLE)
    result = hrq.run_held_render_qa(
        tmp_path / "missing-render.mp4",
        duration=10.0, audio_stream_count=1, ass_path=ass,
        caption_sampler=lambda p, d: _detections(1),
        measure=_measure_factory(-20.0, -30.0),
    )
    assert result["ass_events"] == 2
    assert result["ass_caption_tracks"] == 1
    assert result["gates"]["caption_track"]["passed"] is True
    assert result["gates"]["bgm"]["passed"] is True
    # Missing file: loudness + watermark are unmeasured, never passing.
    assert result["gates"]["loudness"]["reason"] == (
        "loudness_unmeasured:missing_output")
    assert result["gates"]["watermark"]["reason"] == "watermark_unmeasured"
    assert result["passed"] is False
    assert result["failed_gates"] == ["watermark", "loudness"]


def test_ass_path_for_render(tmp_path):
    render = tmp_path / "framed-abc-123.mp4"
    assert hrq.ass_path_for_render(render) is None
    ass = tmp_path / "framed-abc-123.ass"
    ass.write_text("[Events]\n", encoding="utf-8")
    assert hrq.ass_path_for_render(render) == ass


def test_measure_segment_rms_dbfs_missing_file_returns_none(tmp_path):
    assert hrq.measure_segment_rms_dbfs(
        tmp_path / "nope.mp4", 0.0, 2.0) is None
    assert hrq.measure_segment_rms_dbfs(
        tmp_path / "nope.mp4", 2.0, 2.0) is None
