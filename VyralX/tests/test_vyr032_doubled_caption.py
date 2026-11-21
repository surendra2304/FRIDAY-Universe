"""TASK-VYR-032 regression: doubled captions + missing BGM.

Renders 823, 841 and 861 all failed the coordinator's end-to-end watch
with two speech-caption tracks burned in ~1s out of sync (plus a top
hook layer); 861 also had no audible BGM though BGM is mandatory.

Diagnosis (from the code, before the fix):
* Each renderer burns exactly one caption track — one ASS file, one
  ``subtitles`` filter. The second track is the SOURCE footage's own
  burned-in captions. The only guard was the TASK-VYR-025 vision gate:
  ``analyze_scene`` samples one frame per beat and the source counted
  as captioned only when a strict majority of beats flagged captions.
  Render 861 shipped doubled after that gate because its caption track
  was not visible in two of the three sampled stills — word-by-word
  captions flash per word. The gate is now any-beat.
* BGM was documented mandatory but the renderers accepted
  ``music_bed_path=None`` and rendered fine with no bed. The bed is
  now required at the renderer: missing, empty or undecodable raises
  instead of shipping silent.

Every test that pins the new behaviour fails on pristine base code;
the lock tests pin the single-track / bed-in-mix command shape so the
fix cannot silently regress.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import scene_analysis
from app.services import viral_framing
from app.services import viral_quality as vq
from app.services import viral_remix as vr


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_bed(tmp_path, name="bed.wav", frequency=440, seconds=1.0):
    """A real tone bed: _require_music_bed probes the file with ffprobe."""
    bed = tmp_path / name
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y",
         "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={seconds}",
         "-c:a", "pcm_s16le", str(bed)],
        capture_output=True, check=True,
    )
    return bed


def _make_source(tmp_path, name="source.mp4", seconds=2.0):
    source = tmp_path / name
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y",
         "-f", "lavfi", "-i", f"color=c=blue:s=320x480:d={seconds}:r=30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        capture_output=True, check=True,
    )
    return source


def _beat(index, start, end, audio, factor=1.0):
    return {
        "index": index,
        "start": start,
        "end": end,
        "segment_seconds": round(end - start, 3),
        "audio_seconds": audio,
        "target_seconds": audio,
        "timing": {
            "factor": factor,
            "trim_head_seconds": 0.0,
            "trim_tail_seconds": 0.0,
            "pad_seconds": 0.0,
        },
    }


def _captioned_payload(flags):
    return {
        "beats": [{
            "setting": "running track", "time_of_day": "day",
            "subjects": [], "objects": ["mascot costume"],
            "summary": "A mascot races a runner down the track.",
            "captions_present": flag,
        } for flag in flags],
        "event_arc": "the race is run",
        "static": False,
    }


class _FakeSession:
    def __init__(self):
        self.added: list = []
        self._next_id = 1

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    def commit(self):
        pass


def _candidate():
    return SimpleNamespace(
        video_id="Pfxp6mysc90",
        title="Can You Beat The Fastest Mascot?",
        channel="BoltMotivation",
        duration=21.0,
        category="SPORTS",
        hook="WAIT FOR IT",
    )


def _wire_common(monkeypatch, tmp_path):
    monkeypatch.setattr(vr, "download_audio_only",
                        lambda video_id, dest: tmp_path / "probe.webm")
    monkeypatch.setattr(vr, "detect_speech",
                        lambda path: SimpleNamespace(
                            has_speech=False, text="", speech_seconds=0.0))
    monkeypatch.setattr(vr, "download_source_video",
                        lambda video_id, dest: tmp_path / "source.mp4")
    monkeypatch.setattr(vr, "probe_media", lambda path: SimpleNamespace(
        duration=21.0, width=1080, height=1920, has_audio=True))
    monkeypatch.setattr(vr, "existing_upload_titles", lambda db: set())


def _capture_scene_timed(monkeypatch, tmp_path, *, source_has_audio=True,
                         bed="real"):
    captured = {}

    def fake_run(cmd, timeout=None):
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr(vr, "_run", fake_run)
    if bed == "real":
        bed_path = _make_bed(tmp_path)
    elif bed == "empty":
        bed_path = tmp_path / "bed.wav"
        bed_path.write_bytes(b"")
    elif bed == "garbage":
        bed_path = tmp_path / "bed.wav"
        bed_path.write_bytes(b"this is not audio at all" * 10)
    else:
        bed_path = None
    tracks = {
        "beats": [_beat(0, 0.0, 2.0, 2.0)],
        "narration_path": tmp_path / "narration.wav",
        "total_seconds": 2.0,
    }
    cues = [{"start": 0.0, "end": 2.0, "text": "HELLO WORLD"}]
    vr.render_scene_timed(
        tmp_path / "source.mp4", tmp_path / "out.mp4", tracks, cues, "VIRAL",
        source_has_audio=source_has_audio,
        music_bed_path=bed_path,
    )
    return captured


def _capture_framed(monkeypatch, tmp_path, *, bed="real"):
    captured = {}

    def fake_run(cmd, *, timeout=600):
        captured["cmd"] = [str(part) for part in cmd]
        captured["timeout"] = timeout

    monkeypatch.setattr(vr, "_run", fake_run)
    if bed == "real":
        bed_path = _make_bed(tmp_path)
    elif bed == "empty":
        bed_path = tmp_path / "bed.wav"
        bed_path.write_bytes(b"")
    else:
        bed_path = None
    cues = [
        {"start": 1.0, "end": 2.5, "text": "the moment lands", "speech": True},
        {"start": 0.0, "end": 4.0, "text": "watch what he does next"},
    ]
    viral_framing.render_framed(
        tmp_path / "source.mp4",
        tmp_path / "out.mp4",
        excerpt_start=9.0,
        excerpt_seconds=40.0,
        hook_audio=tmp_path / "hook.mp3",
        hook_seconds=4.0,
        payoff_audio=tmp_path / "payoff.mp3",
        payoff_seconds=6.0,
        cues=cues,
        category="VIRAL",
        music_bed_path=bed_path,
    )
    return captured


def _filter_complex(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


# --------------------------------------------------------------------------- #
# caption gate: one flagged beat is a track (render 861)
# --------------------------------------------------------------------------- #
def test_single_flagged_beat_is_a_caption_track():
    assert scene_analysis.source_caption_track(1, 3) is True
    assert scene_analysis.source_caption_track(1, 2) is True
    assert scene_analysis.source_caption_track(0, 3) is False
    assert scene_analysis.source_caption_track(0, 0) is False


def test_record_flags_a_single_captioned_beat():
    record = scene_analysis._coerce_record(_captioned_payload([True, False, False]))
    assert record is not None
    assert record["caption_beats"] == 1
    assert record["source_caption_track"] is True
    assert scene_analysis.record_visual_defects(record) == ["source_captioned"]


def test_produce_skips_single_beat_captioned_source(monkeypatch, tmp_path):
    # The commentary path's gate end to end: a source whose captions show
    # in only one sampled beat is skipped before any editorial work.
    _wire_common(monkeypatch, tmp_path)
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    record = scene_analysis._coerce_record(_captioned_payload([True, False, False]))
    monkeypatch.setattr(vr, "analyze_scene", lambda *a, **k: record)
    editorial_calls = []
    monkeypatch.setattr(vr, "generate_editorial",
                        lambda *a, **k: editorial_calls.append(1) or {
                            "commentary": "A chef flips pancakes in a busy "
                                          "kitchen while the crowd cheers.",
                            "title": "Pancake Flip Chaos",
                            "description": "Pancakes fly.",
                            "hashtags": "",
                        })
    result = vr.produce_viral_short(_candidate(), _FakeSession(), publish=False)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "source_captioned"
    assert result["visual_defects"] == ["source_captioned"]
    assert editorial_calls == []  # rejected before any editorial/render work


def test_framed_path_skips_single_beat_captioned_source(monkeypatch, tmp_path):
    # The framed path's gate end to end, same single-beat record.
    monkeypatch.setattr(viral_framing, "get_settings", lambda: SimpleNamespace(
        prepare_directories=lambda: None,
        render_dir=tmp_path / "renders",
        media_dir=tmp_path / "media",
        ffmpeg_bin="ffmpeg",
        viral_quality_gates_enabled=True,
        viral_max_source_seconds=58.0,
    ))
    monkeypatch.setattr(vr, "download_audio_only",
                        lambda video_id, dest: tmp_path / "probe.webm")
    monkeypatch.setattr(vr, "detect_speech", lambda path: SimpleNamespace(
        has_speech=True,
        cues=[{"start": 0.0, "end": 1.0, "text": "go"}],
        text="go go go",
    ))
    monkeypatch.setattr(vr, "download_source_video",
                        lambda video_id, dest: tmp_path / "source.mp4")
    monkeypatch.setattr(vr, "probe_media", lambda path: SimpleNamespace(
        duration=30.0, width=1080, height=1920, has_audio=True))
    monkeypatch.setattr(viral_framing, "_cut_excerpt",
                        lambda *a, **k: tmp_path / "excerpt.mp4")
    monkeypatch.setattr(viral_framing, "measure_tail_trim",
                        lambda *a, **k: (None, ""))
    monkeypatch.setattr(vq, "measure_event_arc", lambda *a, **k: None)
    record = scene_analysis._coerce_record(_captioned_payload([True, False, False]))
    monkeypatch.setattr(viral_framing, "analyze_scene", lambda *a, **k: record)
    editorial_calls = []
    monkeypatch.setattr(viral_framing, "generate_framing",
                        lambda *a, **k: editorial_calls.append(1) or {})

    candidate = SimpleNamespace(
        video_id="Pfxp6mysc90", title="Can You Beat The Fastest Mascot?",
        channel="BoltMotivation", duration=30.0, category="SPORTS",
    )
    result = viral_framing.produce_framed_short(candidate, None, publish=False)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "source_captioned"
    assert result["visual_defects"] == ["source_captioned"]
    assert editorial_calls == []


# --------------------------------------------------------------------------- #
# BGM bed: mandatory at the renderer (render 861)
# --------------------------------------------------------------------------- #
def test_render_scene_timed_without_bed_refuses(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        _capture_scene_timed(monkeypatch, tmp_path, bed=None)


def test_render_framed_without_bed_refuses(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        _capture_framed(monkeypatch, tmp_path, bed=None)


def test_render_scene_timed_with_empty_bed_refuses(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        _capture_scene_timed(monkeypatch, tmp_path, bed="empty")


def test_render_framed_with_empty_bed_refuses(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        _capture_framed(monkeypatch, tmp_path, bed="empty")


def test_render_scene_timed_with_undecodable_bed_refuses(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        _capture_scene_timed(monkeypatch, tmp_path, bed="garbage")


def test_require_music_bed_rejects_missing_and_silent_files(tmp_path):
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        vr._require_music_bed(None)
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        vr._require_music_bed(tmp_path / "no-such-bed.wav")
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="BGM bed is mandatory"):
        vr._require_music_bed(empty)
    assert vr._require_music_bed(_make_bed(tmp_path)).is_file()


# --------------------------------------------------------------------------- #
# lock tests: exactly one caption track, bed actually in the mix
# --------------------------------------------------------------------------- #
def test_render_scene_timed_burns_exactly_one_caption_track(monkeypatch, tmp_path):
    captured = _capture_scene_timed(monkeypatch, tmp_path)
    chain = _filter_complex(captured["cmd"])
    assert chain.count("subtitles=") == 1


def test_render_framed_burns_exactly_one_caption_track(monkeypatch, tmp_path):
    captured = _capture_framed(monkeypatch, tmp_path)
    chain = _filter_complex(captured["cmd"])
    assert chain.count("subtitles=") == 1


def test_render_scene_timed_mixes_bed_with_source_audio(monkeypatch, tmp_path):
    captured = _capture_scene_timed(monkeypatch, tmp_path, source_has_audio=True)
    chain = _filter_complex(captured["cmd"])
    assert "[2:a]volume=0.10[bed]" in chain
    assert "amix=inputs=3" in chain
    assert str(tmp_path / "bed.wav") in captured["cmd"]


def test_render_scene_timed_mixes_bed_without_source_audio(monkeypatch, tmp_path):
    captured = _capture_scene_timed(monkeypatch, tmp_path, source_has_audio=False)
    chain = _filter_complex(captured["cmd"])
    assert "[2:a]volume=0.10[bed]" in chain
    assert "amix=inputs=2" in chain
    assert str(tmp_path / "bed.wav") in captured["cmd"]


def test_render_framed_mixes_bed(monkeypatch, tmp_path):
    captured = _capture_framed(monkeypatch, tmp_path)
    chain = _filter_complex(captured["cmd"])
    assert "[3:a]volume=0.12" in chain
    assert "amix=inputs=3" in chain
    assert str(tmp_path / "bed.wav") in captured["cmd"]


def test_real_render_mixes_bed_and_burns_one_caption_track(tmp_path):
    # Real ffmpeg end to end: the mandatory-bed command the capture
    # tests pin must actually encode — a malformed filter graph would
    # only surface here.
    source = _make_source(tmp_path)
    narration = _make_bed(tmp_path, name="narration.wav", frequency=880, seconds=2.0)
    bed = _make_bed(tmp_path, name="bed.wav", frequency=440, seconds=2.0)
    tracks = {
        "beats": [_beat(0, 0.0, 2.0, 2.0)],
        "narration_path": narration,
        "total_seconds": 2.0,
    }
    cues = [{"start": 0.0, "end": 2.0, "text": "HELLO WORLD"}]
    out = vr.render_scene_timed(
        source, tmp_path / "out.mp4", tracks, cues, "VIRAL",
        source_has_audio=False,
        music_bed_path=bed,
    )
    assert Path(out).is_file() and Path(out).stat().st_size > 0
    probe = vr.probe_media(out)
    assert 1.5 <= float(probe.duration) <= 2.5
    assert probe.has_audio is True
    assert Path(str(out).replace(".mp4", ".ass")).is_file()
