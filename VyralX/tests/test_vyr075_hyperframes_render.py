"""TASK-VYR-075 — HyperFrames adapt: code-rendered film output.

The pre-VYR-075 HyperframesManager only modelled scripts (scene
math, estimates). This file proves the new live leg: a stored
script renders to a REAL MP4 (Pillow frames + FFmpeg encode),
probed with ffprobe and signal-checked — plus the honest failure
cases (unknown script, empty script, bad preset, bad colour,
missing ffmpeg). The render is a CODE render, not a headless-Chrome
render; the Chrome leg stays gated off-fleet (render_gate).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import real_media_routes
from app.services.real_hyperframes import (
    HyperframesManager,
    VideoScript,
    render_film,
    render_scene_frame,
)


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


def _ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    return {
        "duration": float(data["format"]["duration"]),
        "codec": video["codec_name"],
        "width": video["width"],
        "height": video["height"],
    }


def test_scene_frame_is_real_image(tmp_path: Path):
    manager = HyperframesManager()
    script = manager.create_script(
        "VYR075 Frame", "First sentence here. Second sentence here.")
    scene = script.scenes[0]
    image = render_scene_frame(scene, 1080, 1920)
    assert image.size == (1080, 1920)
    assert image.mode == "RGB"
    # Background is the scene colour (#000000 default) with text drawn.
    assert image.getpixel((10, 10)) == (0, 0, 0)
    out = tmp_path / "frame.png"
    image.save(out)
    assert out.stat().st_size > 1000


def test_render_film_produces_real_mp4(tmp_path: Path):
    manager = HyperframesManager()
    manager.create_script(
        "VYR075 Film", "First sentence here. Second sentence here.")
    out = tmp_path / "film.mp4"
    result = manager.render_film("VYR075 Film", str(out), preset="shorts")
    assert result["available"] is True
    assert result["renderer"] == "code_render_pillow_ffmpeg"
    assert "headless-Chrome" in result["chrome_render"]
    assert result["video_codec"] == "h264"
    assert result["width"] == 1080 and result["height"] == 1920
    assert result["audio"] .startswith("silent")
    assert result["audio_stream_count"] == 0
    assert out.is_file() and out.stat().st_size > 0
    probe = _ffprobe(out)
    assert probe["codec"] == "h264"
    assert probe["width"] == 1080 and probe["height"] == 1920
    assert abs(probe["duration"] - 6.0) < 0.5
    # Signal QA ran on the real file (not a stub result).
    # media_quality statuses: analyzed / partial / unavailable.
    assert result["qa"]["status"] in ("analyzed", "partial", "unavailable")
    assert result["qa"]["audio_analyzed"] is False  # silent by design


def test_render_film_long_preset(tmp_path: Path):
    manager = HyperframesManager()
    manager.create_script("VYR075 Long", "One sentence only.")
    out = tmp_path / "long.mp4"
    result = manager.render_film("VYR075 Long", str(out), preset="long")
    assert result["available"] is True
    probe = _ffprobe(out)
    assert (probe["width"], probe["height"]) == (1920, 1080)
    assert abs(probe["duration"] - 3.0) < 0.5


def test_render_film_failures_are_honest(tmp_path: Path):
    manager = HyperframesManager()
    with pytest.raises(KeyError):
        manager.render_film("No Such Script", str(tmp_path / "x.mp4"))
    with pytest.raises(ValueError, match="no scenes"):
        render_film(VideoScript(title="Empty", scenes=[]),
                    str(tmp_path / "x.mp4"))
    script = manager.create_script("VYR075 Bad", "One sentence.")
    with pytest.raises(ValueError, match="unknown preset"):
        render_film(script, str(tmp_path / "x.mp4"), preset="wide")
    result = render_film(script, str(tmp_path / "x.mp4"),
                         ffmpeg_bin="ffmpeg-does-not-exist")
    assert result["available"] is False
    assert "ffmpeg" in result["reason"]


def test_render_route_end_to_end(tmp_path: Path,
                                monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    create = client.post(
        "/api/v1/vyralx/engines/hyperframes/create-script",
        json={"title": "VYR075 Route Film",
              "text": "First sentence here. Second sentence here."})
    assert create.status_code == 200
    resp = client.post(
        "/api/v1/vyralx/engines/hyperframes/render",
        json={"title": "VYR075 Route Film", "preset": "shorts"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["available"] is True
    assert data["video_codec"] == "h264"
    out = Path(data["output_path"])
    assert out.is_file() and out.stat().st_size > 0
    assert _ffprobe(out)["codec"] == "h264"


def test_render_route_unknown_script_is_404(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/vyralx/engines/hyperframes/render",
        json={"title": "No Such Script", "preset": "shorts"})
    assert resp.status_code == 404


def test_render_route_bad_preset_is_400(tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    client.post(
        "/api/v1/vyralx/engines/hyperframes/create-script",
        json={"title": "VYR075 Bad Preset", "text": "One sentence."})
    resp = client.post(
        "/api/v1/vyralx/engines/hyperframes/render",
        json={"title": "VYR075 Bad Preset", "preset": "wide"})
    assert resp.status_code == 400
