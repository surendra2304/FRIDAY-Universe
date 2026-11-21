"""TASK-VYR-004 regression: render_scene_timed head-trim chains.

Found by the VYR-004 proof run (NASA 'Gradient Sun', 153.32s source,
47.18s narration): the last beat needed an 18.005s head trim, and the
post-retime timestamp trims silently misbehaved in ffmpeg — the video
chain ignored the trim and the audio chain produced an EMPTY segment,
so the render truncated at 40.37s while its captions ran to 46.2s.

The fix selects the tail of the SOURCE window before retiming
(``_head_trim_window_start``). These tests pin the constructed filter
graph so the pattern cannot regress.
"""
from pathlib import Path
import subprocess

import pytest

from app.services import viral_remix as vr


def _beat(index, start, end, audio, factor, trim_head=0.0, trim_tail=0.0, pad=0.0):
    return {
        "index": index,
        "start": start,
        "end": end,
        "segment_seconds": round(end - start, 3),
        "audio_seconds": audio,
        "target_seconds": audio,
        "timing": {
            "factor": factor,
            "trim_head_seconds": trim_head,
            "trim_tail_seconds": trim_tail,
            "pad_seconds": pad,
        },
    }


def _make_bed(tmp_path):
    # TASK-VYR-032: the BGM bed is mandatory — render_scene_timed probes
    # it with ffprobe before building the command, so the capture helper
    # needs a real bed file, not just a path.
    bed = tmp_path / "bed.wav"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:a", "pcm_s16le", str(bed)],
        capture_output=True, check=True,
    )
    return bed


def _capture_graph(monkeypatch, tmp_path, beats):
    captured = {}

    def fake_run(cmd, timeout=None):
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr(vr, "_run", fake_run)
    tracks = {
        "beats": beats,
        "narration_path": tmp_path / "narration.wav",
        "total_seconds": sum(b["audio_seconds"] for b in beats),
    }
    cues = [{"start": 0.0, "end": 1.0, "text": "HELLO", "words": []}]
    vr.render_scene_timed(
        Path("/src.mp4"), tmp_path / "out.mp4", tracks, cues, "VIRAL",
        source_has_audio=True,
        music_bed_path=_make_bed(tmp_path),
    )
    cmd = captured["cmd"]
    graph = cmd[cmd.index("-filter_complex") + 1]
    return graph


def test_head_trim_uses_source_window_tail(monkeypatch, tmp_path):
    # The exact Gradient Sun proof numbers: last beat window
    # [103.491, 153.320], 6.91s of audio at factor 0.5 -> the window
    # tail is the last 13.82 source-seconds: start 139.500.
    beats = [
        _beat(0, 0.0, 49.829, 20.88, 0.5, trim_tail=4.035),
        _beat(1, 49.829, 103.491, 19.39, 0.5, trim_tail=7.441),
        _beat(2, 103.491, 153.320, 6.91, 0.5, trim_head=18.005),
    ]
    graph = _capture_graph(monkeypatch, tmp_path, beats)
    assert "[0:v]trim=start=139.500:end=153.320" in graph
    assert "[0:a]atrim=start=139.500:end=153.320" in graph
    # The broken post-retime timestamp trims must never come back.
    assert "trim=start=18.005" not in graph
    assert "atrim=start=18.005" not in graph
    # Head-trimmed beat is still bounded to its target length.
    assert "trim=duration=6.910" in graph


def test_tail_trim_beats_keep_full_window(monkeypatch, tmp_path):
    beats = [
        _beat(0, 0.0, 49.829, 20.88, 0.5, trim_tail=4.035),
        _beat(1, 49.829, 103.491, 19.39, 0.5, trim_tail=7.441),
    ]
    graph = _capture_graph(monkeypatch, tmp_path, beats)
    assert "[0:v]trim=start=0.000:end=49.829" in graph
    assert "[0:v]trim=start=49.829:end=103.491" in graph
    assert "[0:a]atrim=start=0.000:end=49.829" in graph


def test_head_trim_window_start_math():
    beat = _beat(2, 103.491, 153.320, 6.91, 0.5, trim_head=18.005)
    assert vr._head_trim_window_start(beat) == pytest.approx(139.500, abs=0.01)
    # No head trim -> window unchanged.
    plain = _beat(0, 10.0, 60.0, 20.0, 0.5, trim_tail=5.0)
    assert vr._head_trim_window_start(plain) == 10.0
    # Speed-up factor (>1) still lands inside the window.
    fast = _beat(1, 0.0, 10.0, 16.0, 2.0, trim_head=4.0)
    assert vr._head_trim_window_start(fast) == pytest.approx(2.0, abs=1e-9)
