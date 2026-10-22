"""
Verification Engine for Project FORGE.
Orchestrates batteries of objective verification checks and compiles verifiable evidence reports.
"""

import json
from typing import Any

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.engine import ExecutionEngine, execution_engine
from app.monitoring.production_monitor import production_monitor
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
from app.verification.expanded_battery import (
    AccessibilityChecker,
    CodeQualityComplexityChecker,
    PerformanceSanityChecker,
    SecurityVulnerabilityChecker,
)

logger = get_logger("verification.engine")


class VerificationEngine:
    """Coordinates objective verification batteries across task workspaces."""

    def __init__(
        self,
        engine: ExecutionEngine | None = None,
        wm: WorkspaceManager | None = None,
        custom_checkers: list[BaseChecker] | None = None,
    ):
        self.engine = engine or execution_engine
        self.wm = wm or workspace_manager
        self.checkers: list[Any] = custom_checkers or [
            BuildChecker(),
            LintChecker(),
            TestChecker(),
            RuntimeChecker(),
            SecurityChecker(),
            SecurityVulnerabilityChecker(),
            FeaturePresenceChecker(),
            PerformanceSanityChecker(),
            CodeQualityComplexityChecker(),
            AccessibilityChecker(),
        ]

    async def capture_baseline(self, task_id: str) -> VerificationReport:
        """
        Capture baseline test suite and build verification metrics before any modifications are made.
        Saves baseline_report.json to the task artifacts directory.
        """
        logger.info(f"Capturing baseline verification metrics for task '{task_id}'...")
        evidence_list: list[VerificationEvidence] = []

        for checker in self.checkers:
            try:
                ev = await checker.run_check(task_id=task_id, engine=self.engine)
                evidence_list.append(ev)
            except Exception as e:
                logger.error(f"Checker '{checker.name}' failed during baseline capture: {e}")
                evidence_list.append(
                    VerificationEvidence(
                        check_name=checker.name,
                        category=checker.category,
                        exit_code=1,
                        passed=False,
                        stderr=str(e),
                    )
                )

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
        """
        Run the complete battery of verification checks for a task workspace.
        Enforces regression awareness if a baseline report exists.
        """
        logger.info(
            f"Initiating verification battery for task '{task_id}' with {len(self.checkers)} checkers"
        )
        evidence_list: list[VerificationEvidence] = []

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

        for checker in self.checkers:
            try:
                ev = await checker.run_check(task_id=task_id, engine=self.engine)
                evidence_list.append(ev)
                status_str = "PASS" if ev.passed else f"FAIL (exit={ev.exit_code})"
                logger.info(f"Check [{checker.category.value}] '{checker.name}': {status_str}")
            except Exception as e:
                logger.error(f"Checker '{checker.name}' failed with unexpected exception: {e}")
                evidence_list.append(
                    VerificationEvidence(
                        check_name=checker.name,
                        category=checker.category,
                        exit_code=1,
                        passed=False,
                        stderr=str(e),
                    )
                )

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
