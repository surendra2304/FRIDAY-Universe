"""TASK-VYR-075 — Hypit adapt: format cloning through the live routes.

The format_clone module (TASK-IG-VYR-03) implemented the Hypit
pattern natively, but only score_hook was reachable from the live
path (via competitor_ads / idea_generator). This file proves the
clone leg itself live: template → clone plan → variants, plus
keyframe extraction from a REAL video, and the honest failure
cases (empty script, template without beats, missing video,
video outside media storage).
"""
from __future__ import annotations

import subprocess
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


def _timed_words(n: int = 24) -> list[dict]:
    words, t = [], 0.0
    for i in range(n):
        words.append({"word": f"w{i}", "start": round(t, 2),
                      "end": round(t + 0.3, 2)})
        t += 0.4 + (0.6 if i in (7, 15) else 0.0)  # pauses → beats
    return words


def test_format_clone_end_to_end(tmp_path: Path,
                                 monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    template_resp = client.post(
        "/api/v1/vyralx/engines/format-clone/template",
        json={"duration_seconds": 12.0, "timed_words": _timed_words()})
    assert template_resp.status_code == 200, template_resp.text
    template = template_resp.json()["template"]
    assert template["structure_only"] is True
    assert template["carries_reference_media"] is False
    assert template["carries_reference_words"] is False
    assert len(template["beats"]) >= 2
    assert template["beats"][0]["role"] == "hook"

    new_script = ("How do black holes actually work? Nobody tells you "
                  "the simple version. Watch what the footage shows.")
    clone_resp = client.post(
        "/api/v1/vyralx/engines/format-clone/clone",
        json={"template": template, "new_script": new_script,
              "topic": "Black holes"})
    assert clone_resp.status_code == 200, clone_resp.text
    plan = clone_resp.json()["plan"]
    assert plan["status"] == "pending_review"
    assert plan["requires_approval"] is True
    assert plan["publish"] is False
    assert plan["segments"][0]["role"] == "hook"
    assert "black holes" in " ".join(
        s["text"] for s in plan["segments"]).lower()
    assert plan["hook_score"]["score"] > 0

    variants_resp = client.post(
        "/api/v1/vyralx/engines/format-clone/variants",
        json={"template": template,
              "scripts": [new_script, "Why is the Moon drifting away?"]})
    assert variants_resp.status_code == 200
    assert len(variants_resp.json()["plans"]) == 2


def test_format_clone_failures_are_422(tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    # Template needs timed words.
    assert client.post(
        "/api/v1/vyralx/engines/format-clone/template",
        json={"duration_seconds": 10.0, "timed_words": []}).status_code == 422
    # Clone needs a non-empty script.
    template = client.post(
        "/api/v1/vyralx/engines/format-clone/template",
        json={"duration_seconds": 12.0,
              "timed_words": _timed_words()}).json()["template"]
    assert client.post(
        "/api/v1/vyralx/engines/format-clone/clone",
        json={"template": template, "new_script": "",
              "topic": "X"}).status_code == 422
    # Clone needs beats in the template.
    assert client.post(
        "/api/v1/vyralx/engines/format-clone/clone",
        json={"template": {"beats": []}, "new_script": "Some words here.",
              "topic": "X"}).status_code == 422


def _make_test_video(path: Path) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_keyframes_from_real_video(tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch):
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
    client = TestClient(app)

    video = settings.media_dir / "reference.mp4"
    _make_test_video(video)
    resp = client.post("/api/v1/vyralx/engines/format-clone/keyframes",
                       json={"video_path": str(video)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["available"] is True
    assert len(data["frames"]) >= 1
    assert Path(data["frames"][0]).is_file()

    # Missing file: honest unavailable, never invented frames.
    missing = client.post(
        "/api/v1/vyralx/engines/format-clone/keyframes",
        json={"video_path": str(settings.media_dir / "nope.mp4")})
    assert missing.status_code == 200
    assert missing.json()["available"] is False
    assert missing.json()["frames"] == []

    # Path outside media storage: refused (traversal defence).
    outside = client.post(
        "/api/v1/vyralx/engines/format-clone/keyframes",
        json={"video_path": str(tmp_path / "outside.mp4")})
    assert outside.status_code == 422
