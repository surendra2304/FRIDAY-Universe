"""TASK-VYR-039 regression: the remix path never supplied the mandatory BGM bed.

PR #1186 (TASK-VYR-032) made the bed mandatory in render_scene_timed
(_require_music_bed fails closed on music_bed_path=None) but never
updated produce_remix_short, which calls render_scene_timed without a
bed — so every remix produce died at render with ValueError. Proven
live 2026-11-22 on U2: VYR-037 pool candidate 1 (NASA "Gradient Sun",
record 1e06e9e0b37a) TTS'd its narration and built its caption cues,
then raised "BGM bed is mandatory: music_bed_path must be a real audio
file, not None" before any encode work started.

These tests pin the fix (same preparation as produce_viral_short): a
real bed from the BGM policy reaches the renderer, its source is
recorded on the result, and a disabled bed still fails closed instead
of shipping silent. Offline: ffmpeg builds the bed tone; network,
Whisper, TTS and the compliance gate are stubbed. Every test fails on
pristine base code (the renderer receives music_bed_path=None).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import compliance_gate
from app.services import remix_flow as rf
from app.services import source_analysis
from app.services import viral_bgm
from app.services import viral_remix as vr


def _record(**overrides):
    base = dict(
        platform="nasa",
        title="Gradient Sun",
        author="NASA",
        source_page_url="https://images.nasa.gov/details/GSFC_20121018_Gradient_m11112_Sun.en",
        media_url="http://images-assets.nasa.gov/video/GSFC_20121018_Gradient_m11112_Sun.en/GSFC_20121018_Gradient_m11112_Sun.en~small.mp4",
        license_name="Public Domain — NASA (U.S. Government work)",
        license_url="https://www.nasa.gov/nasa-brand-center/images-and-media/",
        retrieved_at="2026-11-15T07:31:55+00:00",
        duration_seconds=None,
        license_class="public_domain",
        allowed=True,
        decision_reason="public domain / CC0 — no rights reserved",
    )
    base.update(overrides)
    return rf.ProvenanceRecord(**base)


def _make_bed(tmp_path, name="bed.wav", seconds=47.18):
    """A real tone bed: _require_music_bed probes the file with ffprobe."""
    bed = tmp_path / name
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-c:a", "pcm_s16le", str(bed)],
        capture_output=True, check=True,
    )
    return bed


def _fake_settings(tmp_path, *, bed_enabled=True):
    render_dir = tmp_path / "renders"
    media_dir = tmp_path / "media"
    settings = SimpleNamespace(
        render_dir=render_dir,
        media_dir=media_dir,
        viral_music_bed_enabled=bed_enabled,
    )
    settings.prepare_directories = lambda: (render_dir.mkdir(parents=True, exist_ok=True),
                                            media_dir.mkdir(parents=True, exist_ok=True))
    return settings


def _probe(path):
    """Live U2 values for the Gradient Sun source; render probes 47.18s."""
    name = str(path)
    if "bed" in name:
        return SimpleNamespace(duration=47.18, has_audio=True, width=None, height=None)
    if "render" in name or name.endswith(".mp4"):
        return SimpleNamespace(duration=47.18, has_audio=True, width=1080, height=1920)
    return SimpleNamespace(duration=153.0, has_audio=True, width=640, height=360)


def _tracks(tmp_path):
    return {
        "total_seconds": 47.18,
        "narration_path": tmp_path / "narration.wav",
        "beats": [
            {"index": 0, "segment_seconds": 47.18, "audio_seconds": 47.18,
             "timing": {"factor": 1.0, "pad_seconds": 0.0,
                        "trim_head_seconds": 0.0, "trim_tail_seconds": 0.0}},
        ],
    }


def _wire(monkeypatch, tmp_path, bed, *, bed_enabled=True):
    """Stub everything produce_remix_short touches except the bed gate."""
    settings = _fake_settings(tmp_path, bed_enabled=bed_enabled)
    monkeypatch.setattr(rf, "get_settings", lambda: settings)
    monkeypatch.setattr(rf, "download_media",
                        lambda record, dest: tmp_path / "source.mp4")
    monkeypatch.setattr(source_analysis, "probe_media", _probe)
    monkeypatch.setattr(source_analysis, "detect_speech",
                        lambda path: SimpleNamespace(has_speech=False,
                                                    speech_seconds=0.0, cues=[]))
    monkeypatch.setattr(vr, "_decode_to_wav",
                        lambda src, dst: tmp_path / "probe.wav")
    monkeypatch.setattr(vr, "build_scene_tracks",
                        lambda *a, **k: _tracks(tmp_path))
    monkeypatch.setattr(vr, "build_commentary_cues",
                        lambda tracks, script: [
                            {"start": 0.0, "end": 1.0, "text": "HELLO WORLD",
                             "words": ["HELLO", "WORLD"]}])
    monkeypatch.setattr(vr, "_whisper_words", lambda path: [])
    prepared = {}

    def fake_prepare(destination, seconds, category):
        prepared["destination"] = Path(destination)
        prepared["seconds"] = seconds
        prepared["category"] = category
        return bed, "growth:test-bed"

    monkeypatch.setattr(viral_bgm, "prepare_music_bed", fake_prepare)
    monkeypatch.setattr(
        compliance_gate, "evaluate_compliance_gate",
        lambda gate_input: SimpleNamespace(
            passed=True, blocking_failures=[],
            to_dict=lambda: {"passed": True, "checks": [],
                             "blocking_failures": [], "evaluated_at": ""}))
    return settings, prepared


def _capture_render(monkeypatch):
    """Stub render_scene_timed that still enforces the real bed gate."""
    calls = []

    def fake_render(source_path, output_path, tracks, cues, category,
                    source_has_audio, music_bed_path=None):
        calls.append({"music_bed_path": music_bed_path})
        vr._require_music_bed(music_bed_path)  # real fail-closed gate
        return output_path

    monkeypatch.setattr(vr, "render_scene_timed", fake_render)
    return calls


def test_produce_remix_supplies_real_bed(monkeypatch, tmp_path):
    bed = _make_bed(tmp_path)
    settings, prepared = _wire(monkeypatch, tmp_path, bed)
    calls = _capture_render(monkeypatch)
    queue = tmp_path / "queue.jsonl"
    result = rf.produce_remix_short(
        _record(), "The Sun is losing four million tonnes every single second.",
        title="The Sun Loses 4 Million Tonnes Every Second",
        lane="space_science", queue_path=queue)
    assert result["status"] == "PENDING_REVIEW"
    assert len(calls) == 1
    assert calls[0]["music_bed_path"] == bed  # the prepared bed, not None
    assert result["bgm_source"] == "growth:test-bed"
    # Same convention as produce_viral_short: <project_key>-bed.wav
    # under the voiceovers dir, cut to the narration length.
    assert prepared["destination"].name.endswith("-bed.wav")
    assert prepared["destination"].parent == settings.media_dir / "voiceovers"
    assert prepared["seconds"] == 47.18
    assert prepared["category"] == "VIRAL"
    assert rf.list_review_queue(queue)[0]["status"] == "pending_review"


def test_produce_remix_fails_closed_without_bed(monkeypatch, tmp_path):
    bed = _make_bed(tmp_path)
    _wire(monkeypatch, tmp_path, bed, bed_enabled=False)
    calls = _capture_render(monkeypatch)
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        rf.produce_remix_short(
            _record(), "The Sun is losing four million tonnes every single second.",
            title="The Sun Loses 4 Million Tonnes Every Second",
            lane="space_science", queue_path=tmp_path / "queue.jsonl")
    assert calls[0]["music_bed_path"] is None
