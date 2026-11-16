"""TASK-IG3-VYR-06: the WanGP local-generation evaluation (V-08).

This cluster's deliverable is an evaluation, not code — the
fleet cannot run the tool, and pretending otherwise would be
the failure. Behaviour pinned here:

* the evaluation document exists and records the verdict with
  its evidence: the licence position (NOASSERTION; models
  carry their own licences), the hardware floor (4GB VRAM,
  CUDA, Python 3.11) against the fleet's reality (no GPU,
  ~956MB RAM, Python 3.10) — NOT fleet-runnable;
* the owner-hardware path is named (generate locally, enter
  only through the generated_footage provenance intake);
* the document does NOT take the A3 decision: it records the
  admission as not yet taken and the gate as CLOSED;
* and the gate itself is still closed in code — the pin below
  reads generated_footage.py so this PR (or any later one)
  cannot quietly open it.

On clean main the document tests fail: the evaluation does
not exist.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DOC = _ROOT / "docs" / "LOCAL_GENERATION_EVALUATION.md"
_GATE = _ROOT / "app" / "services" / "generated_footage.py"


def _doc() -> str:
    return _DOC.read_text(encoding="utf-8")


def test_evaluation_records_the_verdict_and_its_evidence():
    doc = _doc()
    assert "TASK-IG3-VYR-06" in doc
    assert "NOT fleet-runnable" in doc
    # Licence evidence.
    assert "NOASSERTION" in doc
    assert "underlying models carry their own licences" in doc
    # Hardware evidence, both sides of the comparison.
    assert "4GB VRAM" in doc
    assert "956MB" in doc
    assert "No GPU at all" in doc
    # Sources the evaluation answers to.
    assert "Dd7M_sLjunh" in doc and "DeRrQa-E2AV" in doc
    assert "V-08" in doc


def test_evaluation_names_the_owner_hardware_path():
    doc = _doc()
    assert "provenance intake" in doc
    assert "generated_footage.intake_generated_clip" in doc
    assert "his own GPU hardware" in doc


def test_evaluation_does_not_take_the_a3_decision():
    doc = _doc()
    assert "ai_generated_terms" in doc
    assert "not yet taken" in doc
    assert "gate stays CLOSED" in doc


def test_the_gate_itself_is_still_closed_in_code():
    # HARD RULE pin: the generated-footage admission gate must
    # remain closed. If this test ever fails, a change has
    # touched the gate — that is the owner's A3 decision to
    # make, not an implementation detail.
    src = _GATE.read_text(encoding="utf-8")
    assert "always False" in src
