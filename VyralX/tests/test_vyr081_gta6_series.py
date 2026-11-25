"""TASK-VYR-081: GTA 6 series — moment-finding, vertical cut, series gate.

Pins:
* the series record carries the model, footage rule and honest limits,
  loop OFF, uploader paused, unlisted, nothing publishes;
* only own capture / live EARN-024 footage is accepted;
* audio spikes and scene cuts are found on generated test footage
  (real ffmpeg where present), and a source with no moment signal
  yields an honest empty result;
* the series gate fails closed on every unmeasured standing gate,
  passes only when all four are measured clean, and treats the
  VYR-060 bad-take verdict as advisory until PR #1730 merges.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services import gta6_series as gs

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")

_SINGLE_CAPTION = [{"y": 0.85, "start": 0.0, "end": 10.0, "text": "hello world"}]
_CLEAN_SIGNAL = {
    "status": "analyzed",
    "black_intervals": [],
    "audio_metrics": {
        "status": "analyzed",
        "integrated_loudness_lufs": -14.0,
        "true_peak_dbfs": -3.0,
        "clipped_samples": 0,
    },
}


def _clean_gate(**overrides):
    kw = {
        "caption_detections": _SINGLE_CAPTION,
        "bgm_present": True,
        "watermark_verified": True,
        "signal_analysis": _CLEAN_SIGNAL,
        "duration_s": 20.0,
    }
    kw.update(overrides)
    return gs.gate_series_episode(**kw)


def _ffmpeg(*args):
    proc = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-500:]


def _burst_clip(tmp_path):
    out = tmp_path / "burst.mp4"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-f", "lavfi", "-i", "testsrc=duration=8:size=640x360:rate=25",
            "-filter_complex",
            "[0:a]volume=0.15[a0];[1:a]volume=0.9[a1];"
            "[a0][a1]concat=n=2:v=0:a=1[aout]",
            "-map", "[aout]", "-map", "2:v", "-t", "8",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(out))
    return out


def _cuts_clip(tmp_path):
    out = tmp_path / "cuts.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:d=2:size=640x360:rate=25",
            "-f", "lavfi", "-i", "color=c=blue:d=2:size=640x360:rate=25",
            "-f", "lavfi", "-i", "color=c=red:d=2:size=640x360:rate=25",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[vout]",
            "-map", "[vout]", "-t", "6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out))
    return out


def _quiet_clip(tmp_path):
    out = tmp_path / "quiet.mp4"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=25",
            "-filter_complex", "[0:a]volume=0.05[aout]",
            "-map", "[aout]", "-map", "1:v", "-t", "6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(out))
    return out


def _black_silent_clip(tmp_path):
    out = tmp_path / "black.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=black:d=6:size=640x360:rate=25",
            "-map", "0:v", "-t", "6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out))
    return out


# --- series record -------------------------------------------------------

def test_series_record_carries_model_limits_and_no_publish():
    record = gs.build_series_record()
    assert record["series_id"] == "gta6-clips"
    assert record["task"] == "TASK-VYR-081"
    assert "her English narration" in record["model"]
    assert "subtitles ALWAYS on" in record["model"]
    assert "BGM mandatory" in record["model"]
    assert "own gameplay capture" in record["footage_rule"]
    assert "TASK-EARN-024" in record["footage_rule"]
    assert "YouTube pays NOTHING" in record["honest_limits"]
    assert "takedown at will" in record["honest_limits"]
    assert record["loop"] == "OFF"
    assert record["uploader"] == "paused"
    assert record["privacy"] == "unlisted"
    assert record["review_first"] is True
    assert record["publishes_anything"] is False
    assert record["episodes"] == []


def test_series_seed_shape_matches_series_automation():
    seed = gs.series_seed()
    assert seed["series_id"] == "gta6-clips"
    assert seed["title"]
    assert len(seed["topics"]) >= 5
    assert all(isinstance(t, str) and t for t in seed["topics"])
    assert seed["cadence_days"] >= 1
    assert "no permitted footage on file" in seed["status"]


def test_validate_footage_source_accepts_permitted():
    assert gs.validate_footage_source("own_capture") == "own_capture"
    assert gs.validate_footage_source("earn024_campaign") == "earn024_campaign"


@pytest.mark.parametrize("source", ["youtube_download", "streamer_rip", "", "public_domain"])
def test_validate_footage_source_rejects_third_party(source):
    with pytest.raises(ValueError, match="not permitted"):
        gs.validate_footage_source(source)


# --- ffmpeg log parsers (unit, no binary) ---------------------------------

def _fake_run_factory(monkeypatch):
    def fake(cmd, *, timeout_seconds):
        joined = " ".join(str(c) for c in cmd)
        if "ffprobe" in joined and "format=duration" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="8.0\n", stderr="")
        if "ffprobe" in joined and "stream=codec_type" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout="video\naudio\n", stderr="")
        if "ebur128" in joined:
            lines = []
            for i in range(80):
                t = round(0.1 * (i + 1), 4)
                m = -22.3 if t >= 6.0 else -38.2
                lines.append(f"[Parsed_ebur128_0 @ 0x1] t: {t}  TARGET:-23 LUFS    M:{m} S:{m}     I: -70.0 LUFS")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="\n".join(lines))
        if "showinfo" in joined:
            lines = [
                "[Parsed_showinfo_1 @ 0x1] n:   0 pts:  25600 pts_time:2       duration:    512",
                "[Parsed_showinfo_1 @ 0x1] n:   1 pts:  51200 pts_time:4       duration:    512",
            ]
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="\n".join(lines))
        raise AssertionError(f"unexpected command: {joined}")
    monkeypatch.setattr(gs, "_run", fake)


def test_audio_spike_parser_finds_sustained_burst(tmp_path, monkeypatch):
    _fake_run_factory(monkeypatch)
    clip = tmp_path / "fake.mp4"
    clip.write_bytes(b"x" * 100)
    result = gs.detect_audio_spikes(clip)
    assert result["status"] == "analyzed"
    assert len(result["spikes"]) == 1
    spike = result["spikes"][0]
    assert spike["start_seconds"] >= 5.9
    assert spike["peak_lufs"] > -30.0
    assert spike["duration_seconds"] >= 0.5


def test_scene_cut_parser_reads_showinfo_times(tmp_path, monkeypatch):
    _fake_run_factory(monkeypatch)
    clip = tmp_path / "fake.mp4"
    clip.write_bytes(b"x" * 100)
    result = gs.detect_scene_cuts(clip)
    assert result["status"] == "analyzed"
    assert result["cuts"] == [2.0, 4.0]


def test_find_moments_unit_path_combines_spike_and_cut(tmp_path, monkeypatch):
    _fake_run_factory(monkeypatch)
    clip = tmp_path / "fake.mp4"
    clip.write_bytes(b"x" * 100)
    result = gs.find_moments(clip, footage_source="own_capture")
    assert result["status"] == "analyzed"
    assert result["source_duration_s"] == 8.0
    assert len(result["moments"]) >= 1
    moment = result["moments"][0]
    assert moment["start_seconds"] <= 6.0 <= moment["end_seconds"]
    assert 8.0 <= moment["duration_seconds"] <= 59.0
    assert moment["status"] == "pending_review"
    assert moment["privacy"] == "unlisted"
    assert moment["publish"] is False
    assert "audio_spike" in moment["basis"]


# --- real ffmpeg ----------------------------------------------------------

@needs_ffmpeg
def test_detect_audio_spikes_finds_burst_on_real_media(tmp_path):
    clip = _burst_clip(tmp_path)
    result = gs.detect_audio_spikes(clip)
    assert result["status"] == "analyzed"
    assert result["has_audio"] is True
    assert len(result["spikes"]) >= 1
    assert any(s["start_seconds"] >= 5.5 for s in result["spikes"])


@needs_ffmpeg
def test_detect_audio_spikes_quiet_clip_has_none(tmp_path):
    clip = _quiet_clip(tmp_path)
    result = gs.detect_audio_spikes(clip)
    assert result["status"] == "analyzed"
    assert result["spikes"] == []


@needs_ffmpeg
def test_detect_scene_cuts_finds_color_joins(tmp_path):
    clip = _cuts_clip(tmp_path)
    result = gs.detect_scene_cuts(clip)
    assert result["status"] == "analyzed"
    assert result["cuts"] == [2.0, 4.0]


@needs_ffmpeg
def test_find_moments_on_generated_footage(tmp_path):
    clip = _burst_clip(tmp_path)
    result = gs.find_moments(clip, footage_source="own_capture")
    assert result["status"] == "analyzed"
    assert result["source_duration_s"] == 8.0
    assert len(result["moments"]) >= 1
    for moment in result["moments"]:
        assert 0.0 <= moment["start_seconds"] < moment["end_seconds"] <= 8.0
        assert moment["duration_seconds"] <= 59.0
        assert 0.0 < moment["viral_score"] <= 1.0
        assert moment["status"] == "pending_review"
        assert moment["privacy"] == "unlisted"
    assert result["audio_spikes"]
    assert result["scene_cuts"] == [] or all(
        isinstance(c, float) for c in result["scene_cuts"])


@needs_ffmpeg
def test_find_moments_empty_signal_is_honest_empty(tmp_path):
    clip = _black_silent_clip(tmp_path)
    result = gs.find_moments(clip, footage_source="own_capture")
    assert result["status"] == "analyzed"
    assert result["moments"] == []
    assert "no moment signal found" in result["reason"]


def test_find_moments_missing_file_is_unavailable(tmp_path):
    result = gs.find_moments(tmp_path / "missing.mp4")
    assert result["status"] == "unavailable"
    assert result["moments"] == []


def test_find_moments_rejects_unpermitted_footage(tmp_path):
    with pytest.raises(ValueError, match="not permitted"):
        gs.find_moments(tmp_path / "any.mp4", footage_source="streamer_rip")


def test_detect_audio_spikes_missing_file_is_unavailable(tmp_path):
    result = gs.detect_audio_spikes(tmp_path / "missing.mp4")
    assert result["status"] == "unavailable"
    assert result["error_type"] == "missing_output"


def test_detect_scene_cuts_missing_file_is_unavailable(tmp_path):
    result = gs.detect_scene_cuts(tmp_path / "missing.mp4")
    assert result["status"] == "unavailable"


# --- vertical cut ----------------------------------------------------------

def test_plan_episode_cut_is_9x16_unlisted():
    moment = {"start_seconds": 5.0, "end_seconds": 35.0, "basis": "audio_spike"}
    plan = gs.plan_episode_cut(moment)
    assert plan["crop"]["width"] == 1080
    assert plan["crop"]["height"] == 1920
    assert plan["crop"]["aspect"] == "9:16"
    assert plan["crop"]["ffmpeg_args"]
    assert plan["status"] == "pending_review"
    assert plan["privacy"] == "unlisted"
    assert plan["publish"] is False


# --- series gate -----------------------------------------------------------

def test_gate_passes_when_all_measured_clean():
    gate = _clean_gate()
    assert gate["passed"] is True
    assert gate["reason"] == "series_gate_passed"
    assert gate["checks"]["captions"]["passed"] is True
    assert gate["checks"]["bgm"]["passed"] is True
    assert gate["checks"]["watermark"]["passed"] is True
    assert gate["checks"]["loudness"]["passed"] is True
    assert gate["checks"]["blank"]["passed"] is True
    assert gate["checks"]["bad_takes"]["passed"] is None
    assert gate["checks"]["bad_takes"]["advisory"] is True


@pytest.mark.parametrize("overrides,reason", [
    ({"caption_detections": []}, "no_caption_track_visible"),
    ({"caption_detections": [
        {"y": 0.85, "start": 0.0, "end": 10.0, "text": "line one"},
        {"y": 0.70, "start": 0.0, "end": 10.0, "text": "line two"}]},
     "multiple_caption_tracks:2"),
    ({"caption_detections": None}, "caption_gate_unmeasured"),
    ({"bgm_present": False}, "bgm_missing"),
    ({"bgm_present": None}, "bgm_unmeasured"),
    ({"watermark_verified": False}, "watermark_unverified"),
    ({"watermark_verified": None}, "watermark_unmeasured"),
    ({"signal_analysis": {**_CLEAN_SIGNAL, "audio_metrics": {
        "integrated_loudness_lufs": -30.0, "true_peak_dbfs": -3.0,
        "clipped_samples": 0}}}, "loudness_out_of_range"),
    ({"signal_analysis": None}, "loudness_unmeasured"),
    ({"duration_s": None}, "blank_unmeasured"),
])
def test_gate_fails_each_standing_gate(overrides, reason):
    gate = _clean_gate(**overrides)
    assert gate["passed"] is False
    assert gate["reason"] == reason


def test_gate_fails_when_bad_takes_present():
    gate = _clean_gate(bad_take_verdict={"bad_take_count": 2})
    assert gate["passed"] is False
    assert gate["reason"] == "bad_takes_detected:2"


def test_gate_passes_with_clean_bad_take_verdict():
    gate = _clean_gate(bad_take_verdict={"bad_take_count": 0})
    assert gate["passed"] is True


def test_gate_bad_take_verdict_unrecognized_is_advisory():
    gate = _clean_gate(bad_take_verdict={"something": "else"})
    assert gate["passed"] is True
    assert gate["checks"]["bad_takes"]["reason"] == "bad_take_verdict_unrecognized"


# --- episode record ---------------------------------------------------------

def test_build_series_episode_held_or_rejected():
    moment = {"start_seconds": 5.0, "end_seconds": 35.0, "basis": "audio_spike"}
    cut = gs.plan_episode_cut(moment)
    held = gs.build_series_episode(
        episode_no=1, moment=moment, cut_plan=cut, gate=_clean_gate(),
        footage_source="earn024_campaign")
    assert held["status"] == "held_for_review"
    assert held["privacy"] == "unlisted"
    assert held["publish"] is False
    assert held["footage_source"] == "earn024_campaign"
    rejected = gs.build_series_episode(
        episode_no=2, moment=moment, cut_plan=cut,
        gate=_clean_gate(bgm_present=False), footage_source="own_capture")
    assert rejected["status"] == "rejected"
    assert rejected["publish"] is False


def test_episode_qa_evidence_shape():
    moment = {"start_seconds": 5.0, "end_seconds": 35.0, "basis": "audio_spike"}
    episode = gs.build_series_episode(
        episode_no=1, moment=moment, cut_plan=gs.plan_episode_cut(moment),
        gate=_clean_gate(), footage_source="own_capture")
    evidence = gs.episode_qa_evidence(episode)
    assert evidence["series_id"] == "gta6-clips"
    assert evidence["episode_no"] == 1
    assert evidence["gate_passed"] is True
    assert evidence["publish"] is False
    assert set(evidence["checks"]) == {
        "captions", "bgm", "watermark", "loudness", "blank", "bad_takes"}


def test_module_source_names_the_task_and_the_footage_rule():
    source = (Path(__file__).resolve().parent.parent / "app" / "services"
              / "gta6_series.py").read_text(encoding="utf-8")
    assert "TASK-VYR-081" in source
    assert "TASK-EARN-024" in source
    assert "YouTube pays NOTHING" in source
    assert json.loads(json.dumps(gs.build_series_record()))
