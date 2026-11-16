"""TASK-IG2-FRG-10: review passes wired into the verification battery.

Supervisor bar (round-2 audit C-2): a module counts as wired only
when a production route/service imports and calls it, with a test
that exercises it THROUGH that caller. The production caller here is
``VerificationEngine.verify_task`` — the method ``app/api/delegate.py``
invokes on the ``verification_engine`` singleton (delegate.py:316,
:424). These tests therefore never call ``run_review_passes``
directly: they build a real task workspace, run ``verify_task``, and
read the "Independent Review Passes" evidence out of the battery
report.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.verification.checkers import BaseChecker
from app.verification.engine import VerificationEngine
from app.verification.evidence import CheckCategory, VerificationEvidence

STAGE = "Independent Review Passes"


class _PassingChecker(BaseChecker):
    """A trivial always-pass checker: the battery under test is the
    review stage, not the default checker suite (an empty
    custom_checkers list would select the defaults — ``[] or defaults``
    in the engine constructor — so a stub stands in)."""

    def __init__(self):
        super().__init__(name="Stub Pass", category=CheckCategory.BUILD)

    async def run_check(self, task_id: str, engine) -> VerificationEvidence:
        return VerificationEvidence(
            check_name=self.name, category=self.category, exit_code=0, passed=True
        )


def _engine(tmp_path: Path, **review_kwargs) -> tuple[VerificationEngine, WorkspaceManager]:
    settings = Settings(base_dir=tmp_path)
    wm = WorkspaceManager(settings)
    engine = VerificationEngine(wm=wm, custom_checkers=[_PassingChecker()], **review_kwargs)
    return engine, wm


def _project(wm: WorkspaceManager, task_id: str, files: dict[str, str]) -> Path:
    paths = wm.create_workspace(task_id)
    for rel, content in files.items():
        dest = paths.project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return paths.project


def _stage_evidence(report) -> dict:
    matches = [e for e in report.evidence if e.check_name == STAGE]
    assert len(matches) == 1, [e.check_name for e in report.evidence]
    return matches[0]


async def _passing_review(prompt: str) -> str:
    return json.dumps({"verdict": "pass", "issues": []})


async def _exploding_review(prompt: str) -> str:
    raise RuntimeError("provider down")


@pytest.mark.asyncio
async def test_findings_in_the_project_fail_the_battery_through_verify_task(tmp_path):
    engine, wm = _engine(tmp_path)
    _project(
        wm,
        "task-xss",
        {"templates/page.html": "<div>{{ user_bio|safe }}</div>\n"},
    )
    report = await engine.verify_task("task-xss")
    stage = _stage_evidence(report)
    assert stage.passed is False
    assert stage.exit_code == 1
    assert any("safe" in (i.get("description") or "") for i in stage.issues)
    # A named hard failure: the battery as a whole cannot pass, and the
    # stage appears in the report's failure reasons by name.
    assert report.all_passed is False
    assert any(STAGE in reason for reason in report.failure_reasons)
    # The full review report is persisted as a task artifact.
    artifact = wm.get_workspace_paths("task-xss").artifacts / "review_passes_report.json"
    saved = json.loads(artifact.read_text(encoding="utf-8"))
    assert saved["overall_status"] == "FINDINGS"


@pytest.mark.asyncio
async def test_clean_project_with_configured_audit_passes_through_verify_task(tmp_path):
    engine, wm = _engine(
        tmp_path,
        review_author_model="model-alpha",
        review_reviewer_model="model-beta",
        review_fn=_passing_review,
    )
    _project(wm, "task-clean", {"main.py": "VALUE = 1\n"})
    report = await engine.verify_task("task-clean")
    stage = _stage_evidence(report)
    assert stage.passed is True
    assert "cross_model_audit=PASS" in stage.stdout
    assert report.all_passed is True


@pytest.mark.asyncio
async def test_unconfigured_audit_is_a_disclosed_gate_result_not_a_pass(tmp_path):
    engine, wm = _engine(tmp_path)  # no review models configured
    _project(wm, "task-plain", {"main.py": "VALUE = 1\n"})
    report = await engine.verify_task("task-plain")
    stage = _stage_evidence(report)
    # The deterministic security review ran and passed; the battery is
    # not failed for a review nobody configured — but the evidence
    # must SAY the audit did not run, not dress it up as a pass.
    assert stage.passed is True
    assert "UNAVAILABLE" in stage.stdout
    assert "NOT counted as an audit pass" in stage.stdout
    saved = json.loads(
        (wm.get_workspace_paths("task-plain").artifacts / "review_passes_report.json").read_text(encoding="utf-8")
    )
    assert saved["overall_status"] == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_configured_but_dead_provider_fails_closed(tmp_path):
    engine, wm = _engine(
        tmp_path,
        review_author_model="model-alpha",
        review_reviewer_model="model-beta",
        review_fn=_exploding_review,
    )
    _project(wm, "task-dead", {"main.py": "VALUE = 1\n"})
    report = await engine.verify_task("task-dead")
    stage = _stage_evidence(report)
    assert stage.passed is False
    assert "UNAVAILABLE" in stage.stderr
    assert report.all_passed is False


@pytest.mark.asyncio
async def test_same_model_configuration_cannot_self_grade_through_the_battery(tmp_path):
    engine, wm = _engine(
        tmp_path,
        review_author_model="model-alpha",
        review_reviewer_model="model-alpha",  # self-grading: refused by the audit
        review_fn=_passing_review,
    )
    _project(wm, "task-selfgrade", {"main.py": "VALUE = 1\n"})
    report = await engine.verify_task("task-selfgrade")
    stage = _stage_evidence(report)
    assert stage.passed is False
    assert "self-grading" in stage.stderr
