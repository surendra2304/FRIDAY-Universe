"""TASK-IG3-VYR-10: the scene-by-scene assembly evaluation
(cluster B120, IG source De1VfkaOM_2).

This cluster's deliverable is an evaluation, not code —
the composition layer already exists on main and the
generation step is off-fleet by design; pretending to
build it would be the failure. Behaviour pinned here:

* the evaluation document exists and records the split
  with its evidence: the composition layer that exists
  (named module by module), the generation step that
  stays off-fleet, and the two independent reasons
  (cluster 117's hosted-product SKIP; the fleet's
  hardware facts);
* the document does NOT take the A3 decision: it records
  the admission as not yet taken and the gate as CLOSED;
* the code pins below read the live modules so this PR
  (or any later one) cannot quietly change the facts the
  evaluation rests on: the generated-footage gate is
  still closed, the film render gate still refuses
  in-service rendering, and the composition functions
  the document names still exist.

On clean main the document tests fail: the evaluation
does not exist.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DOC = _ROOT / "docs" / "SCENE_ASSEMBLY_EVALUATION.md"
_GATE = _ROOT / "app" / "services" / "generated_footage.py"


def _doc() -> str:
    return _DOC.read_text(encoding="utf-8")


def test_evaluation_records_the_split_and_its_evidence():
    doc = _doc()
    assert "TASK-IG3-VYR-10" in doc
    assert "De1VfkaOM_2" in doc
    # The composition layer, named as it exists.
    for name in ("previs.build_storyboard",
                 "short_video_assembly.build_assembly_plan",
                 "film_pipeline.build_film",
                 "film_pipeline.apply_studio_edit",
                 "pipeline_orchestration.evaluate_quality_gate"):
        assert name in doc, name
    # The generation step and why it stays off-fleet.
    assert "OFF-FLEET by" in doc
    assert "Google Vids" in doc
    assert "117" in doc
    assert "956MB" in doc


def test_evaluation_names_the_owner_path():
    doc = _doc()
    assert "provenance intake" in doc
    assert "generated_footage.intake_generated_clip" in doc


def test_evaluation_does_not_take_the_a3_decision():
    doc = _doc()
    assert "ai_generated_terms" in doc
    assert "not yet taken" in doc
    assert "gate stays CLOSED" in doc


def test_the_facts_the_evaluation_rests_on_still_hold():
    # HARD RULE pin: the generated-footage admission gate
    # must remain closed — the owner's A3 decision, not an
    # implementation detail.
    gate_src = _GATE.read_text(encoding="utf-8")
    assert "always False" in gate_src

    # The render gate still refuses in-service rendering.
    from app.services import film_pipeline
    gate = film_pipeline.render_gate(host_role="fleet_service")
    assert gate["allowed"] is False
    assert gate["renders_in_service"] is False

    # The composition functions the document names exist.
    from app.services import (pipeline_orchestration, previs,
                              short_video_assembly)
    assert callable(film_pipeline.build_film)
    assert callable(film_pipeline.apply_studio_edit)
    assert callable(previs.build_storyboard)
    assert callable(short_video_assembly.build_assembly_plan)
    assert callable(pipeline_orchestration.evaluate_quality_gate)
