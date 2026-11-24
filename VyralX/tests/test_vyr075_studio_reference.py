"""TASK-VYR-075 — Open Generative AI (reference-only): honest studio.

The pre-VYR-075 MultiModelStudio.generate() fabricated a result:
an output_path for a file never written, an elapsed time computed
from an estimate, a quality score derived from the fabrication —
and the /studio/generate route returned it as success. This file
proves the fix: generate() refuses honestly (available=False,
empty output_path, nothing counted), the route answers 503, the
multi-studio layout survives as data-only reference, and no paid
MuAPI endpoint exists anywhere in VyralX.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import real_media_routes
from app.services.real_open_higgsfield import (
    STUDIO_UNAVAILABLE_REASON,
    GenerationRequest,
    MultiModelStudio,
    studio_layout_reference,
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


def test_generate_refuses_honestly_and_counts_nothing():
    studio = MultiModelStudio()
    result = studio.generate(
        GenerationRequest(request_id="g1", model="Flux.1-dev",
                          prompt="test"))
    assert result.available is False
    assert result.output_path == ""
    assert result.elapsed == 0.0
    assert result.quality_score == 0.0
    assert "MuAPI" in result.reason
    assert "GPU" in result.reason
    assert studio.total_generations == 0
    assert studio.results == []
    batch = studio.generate_batch([
        GenerationRequest(request_id="g2", model="Kling-2.5",
                          prompt="test video")])
    assert len(batch) == 1 and batch[0].available is False
    assert studio.total_generations == 0


def test_generate_reason_is_stated_once():
    assert "FREE-only" in STUDIO_UNAVAILABLE_REASON
    assert "reference catalog" in STUDIO_UNAVAILABLE_REASON


def test_generate_route_answers_503(tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/v1/vyralx/engines/studio/generate",
        json={"prompt": "Cinematic visual render",
              "model": "Flux.1-dev", "width": 1024, "height": 1024,
              "num_steps": 20})
    assert resp.status_code == 503, resp.text
    detail = resp.json()["detail"]
    assert detail["available"] is False
    assert "MuAPI" in detail["reason"]
    assert "output_path" not in detail


def test_layout_reference_is_data_only():
    layout = studio_layout_reference()
    assert layout["fit"] == "reference-only"
    assert layout["studios_claimed_upstream"] == 14
    assert layout["studios_verified_count"] == 5
    names = [s["name"] for s in layout["studios"]]
    for expected in ("Image Studio", "Video Studio", "Lip Sync Studio",
                     "Cinema Studio", "Workflows Studio"):
        assert expected in names
    assert layout["studios_unverified"] == 9
    assert "NOT listed here rather than guessed" in (
        layout["unverified_note"])
    for studio in layout["studios"]:
        assert studio["purpose"] and studio["vyralx_note"]


def test_layout_reference_route(tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/v1/vyralx/engines/studio/layout-reference")
    assert resp.status_code == 200, resp.text
    layout = resp.json()["layout"]
    assert layout["fit"] == "reference-only"
    assert len(layout["studios"]) == 5


def test_no_muapi_endpoint_anywhere_in_vyralx():
    """Guardrail: no paid MuAPI endpoint/key/client in VyralX's code.

    Naming MuAPI in an honest refusal is required (the reason must
    say WHY generation is unavailable); what must never exist is
    a call to it. The same refusal pattern already exists in
    shorts_generator.py (paid api mode rejected).
    """
    import re

    app_root = Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in sorted(app_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"muapi\.ai|api\.muapi|MUAPI_API_KEY|muapi_key",
                     text, re.IGNORECASE):
            offenders.append(str(path.relative_to(app_root)))
        if re.search(r"httpx\.(get|post)\([^)]*muapi|requests\.(get|post)"
                     r"\([^)]*muapi", text, re.IGNORECASE):
            offenders.append(str(path.relative_to(app_root))
                             + " (http call)")
    assert offenders == [], f"MuAPI endpoint usage in VyralX/app: {offenders}"
