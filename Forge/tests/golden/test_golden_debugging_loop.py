"""
Golden Benchmark 5: Automated Debugging & Self-Healing Loop.
Validates failure classification, LLM / heuristic patch synthesis, anti-loop constraints,
and re-verification gate recovery for broken initial requirements or syntax/logic bugs.
"""

import shutil
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.orchestrator import OrchestratorCore
from app.core.workspace import WorkspaceManager
from app.execution.delivery import DeliveryPackager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.models import TaskMode, TaskState
from app.memory.state_store import StateStore
from app.providers.direct import DirectProvider
from app.recovery.classifier import FailureClass, FailureClassifier
from app.recovery.engine import RecoveryEngine
from app.verification.engine import VerificationEngine


@pytest.mark.asyncio
async def test_golden_benchmark_automated_debugging_loop(temp_dir: Path):
    """
    Benchmark Scenario:
    1. Scaffold a project with an intentional syntax/logic flaw in a core calculation module.
    2. Run verification battery -> catch build/test failure.
    3. FailureClassifier isolates the failing file, line, and failure class.
    4. RecoveryEngine generates a clean patch (via LLM/debugger), checks loop guard, and applies fix.
    5. Re-verification succeeds with 100% assertions passing.
    6. DeliveryPackager seals the release artifact.
    """
    db_mgr = DatabaseManager(db_path=temp_dir / "golden_debug.db")
    await db_mgr.init_db()
    store = StateStore(db_mgr)

    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    verifier = VerificationEngine(engine=engine, wm=wm)
    orchestrator = OrchestratorCore(store=store, wm=wm, engine=engine)

    goal = (
        "Create a robust Metrics Aggregator with statistical calculation functions and unit tests"
    )
    requirements = [
        "Compute mean, median, standard deviation, and percentiles for series data",
        "Include unit tests asserting correct mathematical results",
        "Self-heal if initial code contains syntax or logic regressions",
    ]

    task_id = None
    try:
        # 1. Intake and DAG Planning
        task, _graph = await orchestrator.intake_and_plan(
            goal=goal,
            requirements=requirements,
            mode=TaskMode.AUTONOMOUS,
        )
        task_id = task.id
        assert task.state == TaskState.READY

        # 2. Scaffold Implementation with Intentional Syntax Defect on line 12
        broken_code = """\"\"\"Metrics Aggregator module with intentional syntax error.\"\"\"
from typing import List
import math
import sys

def compute_mean(data: List[float]) -> float:
    if not data:
        return 0.0
    return sum(data) / len(data)

# Intentional syntax flaw: missing colon in function definition
def compute_variance(data: List[float]) -> float
    if len(data) < 2:
        return 0.0
    m = compute_mean(data)
    return sum((x - m) ** 2 for x in data) / (len(data) - 1)

def compute_std(data: List[float]) -> float:
    return math.sqrt(compute_variance(data))

def main():
    print("Metrics Aggregator operational.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

        test_code = """\"\"\"Unit tests for Metrics Aggregator.\"\"\"
from main import compute_mean, compute_variance, compute_std

def test_compute_mean():
    assert compute_mean([10.0, 20.0, 30.0]) == 20.0
    assert compute_mean([]) == 0.0

def test_compute_variance_and_std():
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    var = compute_variance(data)
    assert round(var, 2) == 4.57
    std = compute_std(data)
    assert round(std, 2) == 2.14
"""

        wm.write_project_file(task_id, "main.py", broken_code)
        wm.write_project_file(task_id, "test_main.py", test_code)
        wm.write_project_file(
            task_id, "README.md", "# Metrics Aggregator\nStatistical calculation utility.\n"
        )

        # 3. Initial Verification: Must detect failure and produce failed evidence
        initial_report = await verifier.verify_task(task_id)
        assert initial_report.all_passed is False
        assert initial_report.failed_checks >= 1

        failed_ev = next(e for e in initial_report.evidence if not e.passed)
        assert failed_ev is not None

        # 4. Failure Classifier Isolation
        classifier = FailureClassifier()
        diagnosis = classifier.classify(failed_ev)
        assert diagnosis.failure_class == FailureClass.SYNTAX_ERROR
        assert diagnosis.failing_file in ["main.py", "project/main.py"]
        assert diagnosis.failing_line == 12

        # 5. Recovery Engine Self-Healing Loop with Debugger / LLM Provider
        mock_llm_fix = """
### File: main.py
```python
\"\"\"Metrics Aggregator module with fixed syntax.\"\"\"
from typing import List
import math
import sys

def compute_mean(data: List[float]) -> float:
    if not data:
        return 0.0
    return sum(data) / len(data)

def compute_variance(data: List[float]) -> float:
    if len(data) < 2:
        return 0.0
    m = compute_mean(data)
    return sum((x - m) ** 2 for x in data) / (len(data) - 1)

def compute_std(data: List[float]) -> float:
    return math.sqrt(compute_variance(data))

def main():
    print("Metrics Aggregator operational.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```
"""
        provider = DirectProvider(mock_response=mock_llm_fix)
        recovery = RecoveryEngine(
            classifier=classifier,
            verifier=verifier,
            store=store,
            exec_engine=engine,
        )
        recovery.set_provider(provider)

        recovered, msg, patch = await recovery.attempt_recovery(task_id, failed_ev)
        assert recovered is True
        assert "Recovery succeeded" in msg
        assert patch is not None
        assert patch.target_file == "main.py"

        # 6. Post-Recovery Verification Gate
        recheck_report = await verifier.verify_task(task_id)
        assert recheck_report.all_passed is True
        assert recheck_report.failed_checks == 0

        # 7. Package Delivery Report
        packager = DeliveryPackager(engine=engine, wm=wm)
        delivery = await packager.package_delivery(
            task_id=task_id,
            goal=goal,
            requirements=requirements,
            tag_name="v1.0-forge-delivery",
        )

        assert delivery.release_tag == "v1.0-forge-delivery"
        assert delivery.test_build_status["all_passed"] is True

        artifacts_dir = wm.get_task_workspace_dir(task_id) / "artifacts"
        assert (artifacts_dir / "completion_report.json").exists()
        assert (artifacts_dir / "COMPLETION_REPORT.md").exists()

    finally:
        # 8. Test Resilience: Workspace Cleanup
        if task_id:
            ws_dir = wm.get_task_workspace_dir(task_id)
            if ws_dir.exists():
                shutil.rmtree(ws_dir, ignore_errors=True)
