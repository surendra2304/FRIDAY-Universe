"""TASK-VYR-075 — LTX-2 (reject): live evidence of absence.

The registry verdict is reject on hardware alone (22B model,
~66 GiB weights, no GPU on the fleet). A paper judgement is NOT
a result, so this file proves the reject with live evidence:
(1) a fully-provenanced LTX-2.5 clip with a rights assertion is
still refused as a remix candidate by the VYR-004 gate;
(2) the reject verdict is recorded in docs/GENERATED_FOOTAGE.md;
(3) no LTX inference, weights path or download exists anywhere
in VyralX's production code.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.services import generated_footage


def _ltx_clip() -> dict:
    return {
        "generator": "Lightricks LTX-2.5",
        "model": "LTX-2.5",
        "prompt": "A lighthouse in a storm, cinematic",
        "generated_at": "2026-11-24T10:00:00Z",
        "media_url": "https://example.invalid/ltx-clip.mp4",
        "title": "LTX-2.5 test clip",
        "creator": "vyralx-test",
        "rights_assertion": "commercial_and_derivative",
        "terms_url": "https://example.invalid/ltx-terms",
    }


def test_ltx_clip_never_becomes_a_candidate(tmp_path: Path):
    """Even complete provenance + a rights assertion does not admit it."""
    verdict = generated_footage.intake_generated_clip(
        _ltx_clip(), registry_path=tmp_path / "registry.json")
    assert verdict["terms"]["terms_class"] == "ai_generated_terms"
    assert verdict["terms"]["terms_grant"] is True
    assert verdict["candidate"] is False
    assert "cc0/public_domain/cc_by/cc_by_sa/owner" in (
        verdict["candidate_reason"])
    assert verdict["status"] == "pending_review"


def test_ltx_reject_verdict_is_recorded():
    """The reject verdict lives in the generated-footage decision doc."""
    doc = (Path(__file__).resolve().parent.parent / "docs"
           / "GENERATED_FOOTAGE.md").read_text(encoding="utf-8")
    assert "LTX-2.5" in doc
    assert "REJECT" in doc
    assert "GPU" in doc


def test_no_ltx_in_production_path():
    """Guardrail: no LTX inference, weights or download in VyralX/app.

    The only allowed mentions are the model-catalog name and the
    router's video-model name lists in real_open_higgsfield.py —
    strings in a reference catalog, with no execution path behind
    them (generate() refuses all models; see the studio test).
    """
    app_root = Path(__file__).resolve().parent.parent / "app"
    # Allowlist: the reference catalog's model name (no execution
    # path behind it) and the intake module's docstring citing the
    # LTX-2.5 reject verdict. Anything else mentioning LTX is an
    # integration that must not exist.
    allowed = {"real_open_higgsfield.py", "generated_footage.py"}
    offenders: list[str] = []
    for path in sorted(app_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "ltx" not in text.lower():
            continue
        if path.name in allowed:
            continue
        offenders.append(str(path.relative_to(app_root)))
    assert offenders == [], f"LTX references outside allowlist: {offenders}"

    for name in allowed:
        text = (app_root / "services" / name).read_text(encoding="utf-8")
        assert not re.search(r"from\s+ltx|import\s+ltx", text, re.IGNORECASE)
        assert "huggingface" not in text.lower()
        assert "66 GiB" not in text and "66GiB" not in text
        assert not re.search(r"ltx.{0,40}weight|weight.{0,40}ltx",
                             text, re.IGNORECASE)
