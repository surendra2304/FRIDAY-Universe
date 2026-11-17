"""
Verification Engine for Project FORGE.
Orchestrates batteries of objective verification checks and compiles verifiable evidence reports.
"""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from mesh.heavy_task import HeavyTaskCoordinator, coordinator_from_environment

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.engine import ExecutionEngine, execution_engine
from app.monitoring.production_monitor import production_monitor
from app.verification.review_passes import ReviewStatus, run_review_passes
from app.verification.checkers import (
    BaseChecker,
    BuildChecker,
    FeaturePresenceChecker,
    LintChecker,
    RuntimeChecker,
    SecurityChecker,
    TestChecker,
)
from app.verification.evidence import (
    VerificationEvidence,
    VerificationManifest,
    VerificationReport,
    VerificationStageResult,
)
from app.verification.golden_values import GoldenValueChecker
from app.verification.security_gate import OutputSecurityGateChecker
from app.verification.source_integrity import project_snapshot
from app.verification.expanded_battery import (
    AccessibilityChecker,
    CodeQualityComplexityChecker,
    PerformanceSanityChecker,
    SecurityVulnerabilityChecker,
)

logger = get_logger("verification.engine")

# TASK-FRG-007: checkers that execute or import the generated project.
# Running the generated code can materialise files in the workspace (the
# TASK-REL-028 shape: a program writing its own module at import time), so
# these stay serialised -- in their original relative order -- while every
# read-only checker runs concurrently. See _run_checkers().
_EXECUTING_CHECKERS = frozenset(
    {"TestChecker", "RuntimeChecker", "BrowserChecker", "GoldenValueChecker"}
)


class VerificationEngine:
    """Coordinates objective verification batteries across task workspaces."""

    def __init__(
        self,
        engine: ExecutionEngine | None = None,
        wm: WorkspaceManager | None = None,
        custom_checkers: list[BaseChecker] | None = None,
        heavy_task_coordinator: HeavyTaskCoordinator | None = None,
        review_author_model: str | None = None,
        review_reviewer_model: str | None = None,
        review_fn: Callable[[str], Awaitable[str]] | None = None,
    ):
        self.engine = engine or execution_engine
        self.wm = wm or workspace_manager
        # TASK-IG2-FRG-10: independent review passes (TASK-IG-FRG-01)
        # configuration. Models default from the service environment so
        # the production singleton below picks them up at startup; the
        # review_fn is injectable for tests/deployments, otherwise one
        # is built lazily from app.providers for the reviewer model.
        self.review_author_model = (
            review_author_model
            if review_author_model is not None
            else (os.environ.get("FORGE_REVIEW_AUTHOR_MODEL") or None)
        )
        self.review_reviewer_model = (
            review_reviewer_model
            if review_reviewer_model is not None
            else (os.environ.get("FORGE_REVIEW_REVIEWER_MODEL") or None)
        )
        self.review_fn = review_fn
        self.heavy_task_coordinator = (
            heavy_task_coordinator
            if heavy_task_coordinator is not None
            else coordinator_from_environment()
        )
        self.checkers: list[Any] = custom_checkers or [
            BuildChecker(),
            LintChecker(),
            TestChecker(),
            # TASK-FRG-013: execute the generated tests' golden values
            # against the implementation, so a fabricated constant is
            # named as a TEST defect instead of the pytest stage (and
            # the recovery classifier) blaming correct code. Runs in
            # the executing phase (it evaluates generated calls).
            GoldenValueChecker(),
            RuntimeChecker(),
            SecurityChecker(),
            SecurityVulnerabilityChecker(),
            OutputSecurityGateChecker(),
            FeaturePresenceChecker(),
            PerformanceSanityChecker(),
            CodeQualityComplexityChecker(),
            AccessibilityChecker(),
        ]

    async def _run_checkers(self, task_id: str) -> list[VerificationEvidence]:
        """Run every checker and return evidence in the original checker order.

        TASK-FRG-007 (build-time optimisation): the battery used to run its
        checkers strictly serially, so a battery cost the SUM of all checker
        durations and a build pays that sum once per verify_task() call
        (initial pass, post-repair re-verify, post-peer-review re-verify).

        The checkers split into two phases with identical verdicts:

        * Phase A -- read-only checkers (AST/build integrity, lint, static
          security scans, feature/quality/performance/a11y analysis) run
          CONCURRENTLY. None of them executes the project or writes to it,
          so none can observe another's side effects.
        * Phase B -- checkers that execute or import the generated code
          (TestChecker, RuntimeChecker; see _EXECUTING_CHECKERS) run
          SERIALLY, in their original relative order, after Phase A.
          Executing a generated program can materialise files in the
          workspace, and two executors racing the same import could
          interleave those writes; serialising them preserves the exact
          pre-change execution semantics for the only checkers whose
          behaviour can mutate the tree (the Project Source Integrity
          evidence appended by the caller still catches any mutation,
          exactly as it did when everything was serial).

        Per-checker exception isolation is unchanged: a checker that raises
        produces the same failed evidence it produced in the serial loop.
        """
        results: list[VerificationEvidence | None] = [None] * len(self.checkers)

        async def run_one(index: int, checker: Any) -> None:
            try:
                ev = await checker.run_check(task_id=task_id, engine=self.engine)
                results[index] = ev
                status_str = "PASS" if ev.passed else f"FAIL (exit={ev.exit_code})"
                logger.info(
                    f"Check [{checker.category.value}] '{checker.name}': {status_str}"
                )
            except Exception as e:
                logger.error(
                    f"Checker '{checker.name}' failed with unexpected exception: {e}"
                )
                results[index] = VerificationEvidence(
                    check_name=checker.name,
                    category=checker.category,
                    exit_code=1,
                    passed=False,
                    stderr=str(e),
                )

        static_idx = [
            i
            for i, c in enumerate(self.checkers)
            if type(c).__name__ not in _EXECUTING_CHECKERS
        ]
        exec_idx = [
            i
            for i, c in enumerate(self.checkers)
            if type(c).__name__ in _EXECUTING_CHECKERS
        ]
        await asyncio.gather(*(run_one(i, self.checkers[i]) for i in static_idx))
        for i in exec_idx:
            await run_one(i, self.checkers[i])
        return [r for r in results if r is not None]

    def _provider_review_fn(self) -> Callable[[str], Awaitable[str]]:
        """Build the review callable for the configured reviewer model
        from the provider factory. Constructed lazily so importing this
        module never touches provider configuration; any provider
        failure inside the callable surfaces as the audit's UNAVAILABLE,
        which the stage below treats fail-closed."""
        reviewer_model = self.review_reviewer_model

        async def review_fn(prompt: str) -> str:
            from app.providers.factory import get_provider

            provider = get_provider(model_name=reviewer_model)
            response = await provider.generate(prompt)
            return response.content

        return review_fn

    async def _run_review_stage(
        self, task_id: str, project_dir: Path | None
    ) -> VerificationEvidence | None:
        """TASK-IG2-FRG-10: run the independent review passes
        (TASK-IG-FRG-01's ``run_review_passes``) over the settled
        workspace as a battery stage — the wiring its module docstring
        named as the integration point, so the passes are reachable
        from the production path (app/api/delegate.py ->
        verification_engine.verify_task) instead of only from tests.

        Outcome mapping (agreement, not inflation):
        * FINDINGS -> failed evidence: a named hard failure in the
          report's failure_reasons, so the build cannot surface as
          SUCCESS anywhere (verdict rule 3).
        * PASS -> passed evidence.
        * UNAVAILABLE -> depends on configuration, honestly:
          - reviewer models CONFIGURED but the audit did not run
            (provider failure, same-model refusal, unparseable
            verdict): failed evidence — a configured gate that could
            not run fails closed, never silently green;
          - reviewer NOT configured: the deterministic security review
            still ran; if it passed, the stage records a passed
            evidence whose stdout DISCLOSES that the cross-model audit
            did not run (a named gate result, not an audit pass), and
            if the security review itself could not run, failed
            evidence — absence of evidence is not a pass.
        The full ReviewReport is persisted as the
        ``review_passes_report.json`` task artifact either way.
        """
        from app.verification.evidence import CheckCategory

        if project_dir is None or not Path(project_dir).is_dir():
            return None
        review_fn = self.review_fn
        if (
            review_fn is None
            and self.review_author_model
            and self.review_reviewer_model
        ):
            review_fn = self._provider_review_fn()
        report = await run_review_passes(
            Path(project_dir),
            author_model=self.review_author_model,
            reviewer_model=self.review_reviewer_model,
            review_fn=review_fn,
        )
        try:
            self.wm.save_artifact(
                task_id,
                "review_passes_report.json",
                json.dumps(report.to_dict(), indent=2),
            )
        except Exception as exc:  # artifact loss must not hide the outcome
            logger.warning(f"Could not save review passes report for {task_id}: {exc}")

        name = "Independent Review Passes"
        command = "run_review_passes(settled workspace)"
        issues = [i.to_dict() for i in report.all_issues]
        per_pass = "; ".join(
            f"{p.name}={p.status.value} ({p.detail})" for p in report.passes
        )
        overall = report.overall_status
        if overall is ReviewStatus.FINDINGS:
            return VerificationEvidence(
                check_name=name,
                category=CheckCategory.SECURITY,
                command=command,
                exit_code=1,
                passed=False,
                stderr=(
                    f"Independent review found {len(issues)} issue(s). {per_pass}"
                ),
                issues=issues,
                artifacts_inspected=sorted(
                    {i["file_path"] for i in issues if i.get("file_path")}
                ),
            )
        if overall is ReviewStatus.PASS:
            return VerificationEvidence(
                check_name=name,
                category=CheckCategory.SECURITY,
                command=command,
                exit_code=0,
                passed=True,
                stdout=f"Independent review PASS. {per_pass}",
                issues=[],
            )
        # UNAVAILABLE aggregate: at least one pass did not run.
        configured = bool(self.review_author_model and self.review_reviewer_model)
        security = next(
            (p for p in report.passes if p.name == "security_review"), None
        )
        if not configured and security is not None and security.status is ReviewStatus.PASS:
            return VerificationEvidence(
                check_name=name,
                category=CheckCategory.SECURITY,
                command=command,
                exit_code=0,
                passed=True,
                stdout=(
                    "Deterministic security review PASS. Cross-model audit "
                    "UNAVAILABLE: no reviewer configured (set "
                    "FORGE_REVIEW_AUTHOR_MODEL and FORGE_REVIEW_REVIEWER_MODEL "
                    "to enable it) — recorded as a gate result, NOT counted "
                    f"as an audit pass. {per_pass}"
                ),
                issues=[],
            )
        return VerificationEvidence(
            check_name=name,
            category=CheckCategory.SECURITY,
            command=command,
            exit_code=1,
            passed=False,
            stderr=(
                "Independent review UNAVAILABLE — a configured review pass "
                f"did not run; failing closed. {per_pass}"
            ),
            issues=issues,
        )

    async def _run_with_heavy_lease(
        self,
        task_id: str,
        operation: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Serialize build/test verification against other fleet-wide heavy work."""
        coordinator = self.heavy_task_coordinator
        if coordinator is None:
            # Local development is allowed only when shared coordination was not
            # explicitly required in service configuration.
            return await operation(None)

        async def guarded(lease: Any) -> Any:
            lease.ensure_valid()
            try:
                result = await operation(lease)
                lease.ensure_valid()
                return result
            except asyncio.CancelledError:
                # Lease loss must stop the actual shell/process workers, not
                # merely cancel the coroutine waiting for their output. The
                # terminal and process managers own those child processes.
                try:
                    await asyncio.shield(
                        self.engine.terminate_all_sandboxes(timeout=4.0)
                    )
                except Exception:
                    logger.exception(
                        "Failed to fully terminate Forge workers after lease loss",
                        extra={"task_id": task_id},
                    )
                raise

        return await coordinator.run(
            task_id=task_id,
            owner="forge",
            operation=guarded,
            wait_timeout=None,
        )

    async def capture_baseline(self, task_id: str) -> VerificationReport:
        """Capture a baseline while holding the global heavy-task lease."""
        async def execute(_lease: Any) -> VerificationReport:
            return await self._capture_baseline_uncoordinated(task_id)

        return await self._run_with_heavy_lease("forge:baseline-verification", execute)

    async def _capture_baseline_uncoordinated(self, task_id: str) -> VerificationReport:
        """
        Capture baseline test suite and build verification metrics before any modifications are made.
        Saves baseline_report.json to the task artifacts directory.
        """
        logger.info(f"Capturing baseline verification metrics for task '{task_id}'...")
        evidence_list: list[VerificationEvidence] = []

        evidence_list = await self._run_checkers(task_id)

        passed_count = sum(1 for e in evidence_list if e.passed)
        failed_count = len(evidence_list) - passed_count
        report = VerificationReport(
            task_id=task_id,
            all_passed=(failed_count == 0),
            total_checks=len(evidence_list),
            passed_checks=passed_count,
            failed_checks=failed_count,
            evidence=evidence_list,
        )

        production_monitor.record_verification(passed=report.all_passed)
        report_json = json.dumps(report.model_dump(mode="json"), indent=2)
        self.wm.save_artifact(task_id, "baseline_report.json", report_json)
        logger.info(
            f"Baseline captured for task '{task_id}': {passed_count}/{len(evidence_list)} checks passed"
        )
        return report

    async def verify_task(
        self,
        task_id: str,
        baseline_report: VerificationReport | None = None,
    ) -> VerificationReport:
        """Run build/test and quality gates while holding the shared fleet lease."""
        async def execute(_lease: Any) -> VerificationReport:
            return await self._verify_task_uncoordinated(task_id, baseline_report)

        return await self._run_with_heavy_lease("forge:verification-battery", execute)

    async def _verify_task_uncoordinated(
        self,
        task_id: str,
        baseline_report: VerificationReport | None = None,
    ) -> VerificationReport:
        """
        Run the complete battery of verification checks for a task workspace.
        Enforces regression awareness if a baseline report exists.
        """
        logger.info(
            f"Initiating verification battery for task '{task_id}' with {len(self.checkers)} checkers"
        )
        evidence_list: list[VerificationEvidence] = []

        paths = self.wm.get_workspace_paths(task_id)
        initial_snapshot = None
        try:
            initial_snapshot = project_snapshot(paths.project) if paths else None
        except (OSError, ValueError):
            pass  # The explicit integrity stage below prevents certification.

        # Load baseline report from artifacts if not explicitly passed
        if baseline_report is None:
            paths = self.wm.get_workspace_paths(task_id)
            if paths:
                baseline_file = paths.artifacts / "baseline_report.json"
                if baseline_file.exists():
                    try:
                        data = json.loads(baseline_file.read_text(encoding="utf-8"))
                        baseline_report = VerificationReport(**data)
                    except Exception as e:
                        logger.debug(f"Could not load baseline report: {e}")

        evidence_list = await self._run_checkers(task_id)

        # TASK-IG2-FRG-10: independent review passes over the settled
        # workspace (see _run_review_stage). Runs BEFORE the source
        # integrity stage: the integrity evidence is the battery's seal
        # and must stay the final stage evidence (a source change made
        # during ANY stage — review included — must not be stampable as
        # passing). The review stage only reads the project tree (its
        # report artifact lands outside it), so the before/after
        # snapshot comparison below now also covers the review stage.
        review_evidence = await self._run_review_stage(
            task_id, paths.project if paths else None
        )
        if review_evidence is not None:
            evidence_list.append(review_evidence)

        from app.verification.evidence import CheckCategory
        snapshot_stable = False
        try:
            snapshot_stable = bool(initial_snapshot) and initial_snapshot == project_snapshot(paths.project)
        except (OSError, ValueError, AttributeError):
            pass
        evidence_list.append(VerificationEvidence(
            check_name="Project Source Integrity", category=CheckCategory.SECURITY,
            command="compare bounded project SHA256 inventory before/after verification",
            exit_code=0 if snapshot_stable else 1, passed=snapshot_stable,
            stderr="" if snapshot_stable else "Project changed during verification or cannot be fingerprinted; re-run verification on stable regular files.",
        ))

        # Evaluate Regression Guard across all check categories against baseline
        baseline_comparison = None
        if baseline_report:
            from app.verification.evidence import CheckCategory

            regressions = []

            # Map baseline checks by check_name
            baseline_map = {e.check_name: e for e in baseline_report.evidence}
            for ev in evidence_list:
                base_ev = baseline_map.get(ev.check_name)
                if base_ev and base_ev.passed and not ev.passed:
                    regressions.append(
                        f"Check '{ev.check_name}' [{ev.category.value}] passed in baseline but failed post-modification (exit={ev.exit_code})."
                    )

            has_regression = len(regressions) > 0
            regression_reason = "; ".join(regressions) if has_regression else ""

            baseline_comparison = {
                "baseline_all_passed": baseline_report.all_passed,
                "baseline_passed_checks": baseline_report.passed_checks,
                "current_passed_checks": sum(1 for e in evidence_list if e.passed),
                "regression_detected": has_regression,
                "regression_reason": regression_reason if has_regression else None,
            }

            if has_regression:
                logger.warning(
                    f"[Task {task_id}] Regressions detected against baseline: {regression_reason}"
                )
                evidence_list.append(
                    VerificationEvidence(
                        check_name="Baseline Regression Guard",
                        category=CheckCategory.TEST,
                        exit_code=1,
                        passed=False,
                        stderr=regression_reason,
                    )
                )

        passed_count = sum(1 for e in evidence_list if e.passed)
        failed_count = len(evidence_list) - passed_count
        all_passed = failed_count == 0

        report = VerificationReport(
            task_id=task_id,
            source_snapshot=initial_snapshot if snapshot_stable else None,
            all_passed=all_passed,
            total_checks=len(evidence_list),
            passed_checks=passed_count,
            failed_checks=failed_count,
            evidence=evidence_list,
            baseline_comparison=baseline_comparison,
        )

        # Feed the production monitor: record_verification() had no callers, so
        # verification pass/fail ratios never reached /metrics.
        production_monitor.record_verification(passed=all_passed)

        # Persist verification report in task artifacts
        report_json = json.dumps(report.model_dump(mode="json"), indent=2)
        self.wm.save_artifact(task_id, "verification_report.json", report_json)

        # Generate canonical verification manifest with full objective metrics
        self.generate_manifest(task_id, report)

        return report

    def generate_manifest(self, task_id: str, report: VerificationReport) -> VerificationManifest:
        """
        Compile canonical VerificationManifest with exact commands, exit codes, logs, artifacts, and timestamps.
        Detects partial failures when some checks/stages passed and others failed.
        """
        stages_map: dict[str, VerificationStageResult] = {}
        for ev in report.evidence:
            stage_key = ev.category.value if hasattr(ev.category, "value") else str(ev.category)
            stdout_snip = ev.stdout[:500] if ev.stdout else ""
            stderr_snip = ev.stderr[:500] if ev.stderr else ""
            stages_map[ev.check_name] = VerificationStageResult(
                stage=stage_key,
                command=ev.command,
                exit_code=ev.exit_code,
                passed=ev.passed,
                duration_ms=ev.duration_ms,
                stdout_snippet=stdout_snip,
                stderr_snippet=stderr_snip,
                artifacts=ev.artifacts_inspected,
                timestamp=(
                    ev.timestamp.isoformat()
                    if hasattr(ev.timestamp, "isoformat")
                    else str(ev.timestamp)
                ),
            )

        passed_stages = sum(1 for s in stages_map.values() if s.passed)
        failed_stages = len(stages_map) - passed_stages

        # Check partial failure: if any failed, but at least one stage passed
        partial_failure = (failed_stages > 0 and passed_stages > 0)
        overall_status = (
            "PASSED"
            if failed_stages == 0
            else ("PARTIAL_FAILURE" if partial_failure else "FAILED")
        )

        manifest = VerificationManifest(
            task_id=task_id,
            source_snapshot=report.source_snapshot,
            overall_status=overall_status,
            all_passed=(failed_stages == 0),
            partial_failure=partial_failure,
            failure_summary="; ".join(report.failure_reasons) if report.failure_reasons else None,
            total_stages=len(stages_map),
            passed_stages=passed_stages,
            failed_stages=failed_stages,
            stages=stages_map,
            evidence=report.evidence,
        )

        manifest_json = json.dumps(manifest.model_dump(mode="json"), indent=2)
        self.wm.save_artifact(task_id, "verification_manifest.json", manifest_json)
        return manifest


verification_engine = VerificationEngine()
