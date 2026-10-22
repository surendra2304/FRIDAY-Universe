"""
Prompt 4 Acceptance Test Battery for Forge (surendra2304/Forge).
Verifies:
1. FRIDAY Task Envelope delegation & async job polling (/tasks/{id}/status)
2. Task Sandboxing & Path Traversal Confinement (rejects ../../)
3. Command Policy & Shell Injection Rejection (blocks format, shutdown, sudo, pipe-to-shell)
4. Git Push Gated Authorization (rejects unauthorized git push with UnauthorizedGitPushError)
5. Git Commit Authorization Gating
6. Subprocess Timeout & Process-Tree Termination
7. Anti-Loop Deduplication & RepairLoopDetectedError
8. Workspace Snapshot & Rollback
9. Objective Verification Manifest Structure
10. Partial Failure Reporting (never reports success when verification fails)
11. Sentinel Pre-Delivery Security Review Gate
12. Memora Post-Verification Writeback Gating
13. Repository Allowlist Validation
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.delivery import DeliveryPackager, SecurityGateFailure
from app.execution.filesystem import FilesystemTool
from app.execution.git_tool import GitTool
from app.execution.permissions import (
    PermissionManager,
    SandboxViolationError,
    ToolPermission,
    UnauthorizedGitOperationError,
    UnauthorizedGitPushError,
)
from app.execution.terminal import TerminalTool
from app.main import app
from app.memory.db import DatabaseManager
from app.memory.models import TaskEntity, TaskState
from app.recovery.classifier import FailureClass
from app.recovery.loop_guard import AntiLoopController, RepairLoopDetectedError
from app.verification.engine import VerificationEngine, verification_engine
from app.verification.evidence import (
    CheckCategory,
    VerificationEvidence,
    VerificationReport,
)


@pytest.fixture(autouse=True)
async def setup_db(isolated_db_manager: DatabaseManager):
    # Every test in this file used to call the real global
    # app.memory.db.db_manager directly (data/forge.db on disk).
    # isolated_db_manager (tests/conftest.py) redirects every module-level
    # db_manager binding plus the shared Settings singleton's base_dir into
    # an isolated temp directory for the duration of each test.
    await isolated_db_manager.init_db()
    yield


@pytest.fixture
def temp_workspace_context(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    pm = PermissionManager()
    fs = FilesystemTool(wm=wm, pm=pm)
    terminal = TerminalTool(wm=wm, pm=pm)
    git = GitTool(wm=wm, pm=pm)
    return {
        "settings": settings,
        "wm": wm,
        "pm": pm,
        "fs": fs,
        "terminal": terminal,
        "git": git,
        "tmp_path": tmp_path,
    }


@pytest.mark.asyncio
async def test_friday_task_envelope_and_status_polling():
    """1. FRIDAY delegates task via envelope, then polls status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        envelope = {
            "task_id": f"task_{uuid4().hex[:8]}",
            "source_agent": "friday",
            "target_agent": "forge",
            "action": "build",
            "payload": {
                "goal": "Build a telemetry calculation module",
                "requirements": ["Calculate latency percentiles"],
                "mode": "standard",
            },
            "priority": "high",
        }
        resp = await client.post("/api/v1/forge/delegate", json=envelope)
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_agent"] == "forge"
        assert data["status"] == "SUCCESS"
        forge_task_id = data["result"]["forge_task_id"]

        # Poll status
        status_resp = await client.get(f"/api/v1/forge/tasks/{forge_task_id}/status")
        assert status_resp.status_code == 200
        st_data = status_resp.json()
        assert st_data["task_id"] == forge_task_id
        assert "READY" in st_data["result"]["state"] or "PENDING" in st_data["result"]["state"]


@pytest.mark.asyncio
async def test_sandbox_path_traversal_blocked(temp_workspace_context):
    """2. Path traversal attempts escaping workspace project directory are blocked."""
    fs: FilesystemTool = temp_workspace_context["fs"]
    task_id = f"sec_task_{uuid4().hex[:6]}"

    # Traversal via relative ../
    with pytest.raises(SandboxViolationError):
        fs.create_file(task_id, "../../escaped_secret.txt", "leaked", role="developer")

    # Traversal via absolute path outside sandbox
    with pytest.raises(SandboxViolationError):
        fs.read_file(task_id, "C:/Windows/System32/drivers/etc/hosts" if os.name == "nt" else "/etc/passwd", role="developer")


@pytest.mark.asyncio
async def test_command_injection_and_policy_denial(temp_workspace_context):
    """3. Terminal tool blocks dangerous commands and pipe injections."""
    terminal: TerminalTool = temp_workspace_context["terminal"]
    task_id = f"term_sec_{uuid4().hex[:6]}"

    # Block destructive commands
    res1 = await terminal.run_command(task_id, "format C: /fs:NTFS", role="developer")
    assert res1.exit_code != 0
    assert "denied" in res1.stderr.lower()

    res2 = await terminal.run_command(task_id, "shutdown /s /t 0", role="developer")
    assert res2.exit_code != 0
    assert "denied" in res2.stderr.lower()

    # Block pipe-to-shell injection
    res3 = await terminal.run_command(task_id, "echo bad | bash", role="developer")
    assert res3.exit_code != 0
    assert "denied" in res3.stderr.lower()


@pytest.mark.asyncio
async def test_git_push_requires_authorization(temp_workspace_context):
    """4. Git push without explicit authorization is rejected fail-closed."""
    git: GitTool = temp_workspace_context["git"]
    terminal: TerminalTool = temp_workspace_context["terminal"]
    task_id = f"git_push_{uuid4().hex[:6]}"

    # GitTool.push without authorization
    with pytest.raises(UnauthorizedGitPushError):
        await git.push(task_id, remote="origin", branch="main", role="developer", authorized=False)

    # terminal command 'git push' without allow_git_push
    res = await terminal.run_command(task_id, "git push origin main", role="developer", allow_git_push=False)
    assert res.exit_code != 0
    assert "separate authorization" in res.stderr.lower()


@pytest.mark.asyncio
async def test_git_push_succeeds_with_explicit_authorization(temp_workspace_context):
    """5. Git push proceeds when explicitly authorized."""
    git: GitTool = temp_workspace_context["git"]
    pm: PermissionManager = temp_workspace_context["pm"]
    task_id = f"git_push_auth_{uuid4().hex[:6]}"
    await git.init_repo(task_id)

    # Grant GIT_PUSH to release_engineer
    pm.grant_permission("release_engineer", ToolPermission.GIT_PUSH)

    # Authorized push with elevated token
    with patch.object(git, "_run_git", return_value=(0, "Everything up-to-date", "")):
        success = await git.push(
            task_id,
            remote="origin",
            branch="feature/verified-build",
            role="release_engineer",
            authorized=True,
            push_token="auth_token_forge_4982",
        )
        assert success is True


@pytest.mark.asyncio
async def test_git_commit_authorization_enforcement(temp_workspace_context):
    """6. Git commit fails if authorized=False."""
    git: GitTool = temp_workspace_context["git"]
    task_id = f"git_commit_{uuid4().hex[:6]}"

    with pytest.raises(UnauthorizedGitOperationError):
        await git.commit(task_id, "Unauthorized commit", role="developer", authorized=False)


@pytest.mark.asyncio
async def test_subprocess_timeout_and_process_cleanup(temp_workspace_context):
    """7. Long-running command times out and cleans up process tree."""
    terminal: TerminalTool = temp_workspace_context["terminal"]
    task_id = f"timeout_task_{uuid4().hex[:6]}"

    res = await terminal.run_command(
        task_id,
        'python -c "import time; time.sleep(10)"',
        timeout_seconds=1,
        role="developer",
    )
    assert res.timed_out is True
    assert res.exit_code != 0
    assert "timed out" in res.stderr.lower()


def test_anti_loop_duplicate_patch_detection():
    """8. AntiLoopController detects duplicate patches and raises violation."""
    controller = AntiLoopController(max_retries_per_class=2, max_total_retries=4)
    task_id = "loop_test_task"
    patch_code = "def solve(): return 42"

    # First attempt allowed
    allowed, _ = controller.can_attempt_repair(task_id, FailureClass.SYNTAX_ERROR, patch_code)
    assert allowed is True
    controller.record_repair_attempt(task_id, FailureClass.SYNTAX_ERROR, patch_code)

    # Identical patch attempt rejected
    allowed2, reason2 = controller.can_attempt_repair(task_id, FailureClass.SYNTAX_ERROR, patch_code)
    assert allowed2 is False
    assert "Duplicate patch detected" in reason2

    # assert_can_attempt_repair raises RepairLoopDetectedError
    with pytest.raises(RepairLoopDetectedError):
        controller.assert_can_attempt_repair(task_id, FailureClass.SYNTAX_ERROR, patch_code)


def test_workspace_snapshot_and_rollback(temp_workspace_context):
    """9. Workspace snapshot creates pristine copy and rollback restores it."""
    wm: WorkspaceManager = temp_workspace_context["wm"]
    fs: FilesystemTool = temp_workspace_context["fs"]
    task_id = f"snap_task_{uuid4().hex[:6]}"

    # Initial pristine state
    fs.create_file(task_id, "src/app.py", "# Pristine state v1.0", role="developer")
    assert "Pristine" in fs.read_file(task_id, "src/app.py", role="developer")

    # Take snapshot
    snap_path = wm.create_snapshot(task_id, "pristine_snapshot")
    assert snap_path.exists()
    assert "pristine_snapshot" in wm.list_snapshots(task_id)

    # Mutate / break the workspace
    fs.create_file(task_id, "src/app.py", "# Corrupted broken state v2.0", role="developer")
    fs.create_file(task_id, "src/trash.py", "# Unwanted garbage", role="developer")
    assert "Corrupted" in fs.read_file(task_id, "src/app.py", role="developer")

    # Rollback
    restored = wm.rollback_snapshot(task_id, "pristine_snapshot")
    assert restored is True

    # Verify original pristine contents restored
    restored_code = fs.read_file(task_id, "src/app.py", role="developer")
    assert "# Pristine state v1.0" in restored_code
    assert not (wm.get_workspace_paths(task_id).project / "src" / "trash.py").exists()


def test_objective_verification_manifest_generation(temp_workspace_context):
    """10. VerificationEngine compiles objective manifest with exact commands, exit codes, and timestamps."""
    wm: WorkspaceManager = temp_workspace_context["wm"]
    engine = VerificationEngine(wm=wm)
    task_id = f"manif_task_{uuid4().hex[:6]}"

    report = VerificationReport(
        task_id=task_id,
        all_passed=True,
        total_checks=2,
        passed_checks=2,
        failed_checks=0,
        evidence=[
            VerificationEvidence(
                check_name="Pytest Suite",
                category=CheckCategory.TEST,
                command="pytest tests/unit",
                exit_code=0,
                passed=True,
                duration_ms=210.5,
                stdout="2 passed in 0.21s",
                artifacts_inspected=["tests/test_mod.py"],
            ),
            VerificationEvidence(
                check_name="Ruff Linter",
                category=CheckCategory.LINT,
                command="ruff check .",
                exit_code=0,
                passed=True,
                duration_ms=45.0,
                stdout="All checks passed!",
            ),
        ],
    )

    manifest = engine.generate_manifest(task_id, report)
    assert manifest.overall_status == "PASSED"
    assert manifest.all_passed is True
    assert manifest.total_stages == 2
    assert "Pytest Suite" in manifest.stages
    stage_res = manifest.stages["Pytest Suite"]
    assert stage_res.exit_code == 0
    assert stage_res.command == "pytest tests/unit"
    assert stage_res.duration_ms == 210.5
    assert "tests/test_mod.py" in stage_res.artifacts


@pytest.mark.asyncio
async def test_partial_failure_reporting():
    """11. When verification fails, Forge returns PARTIAL_FAILURE, never SUCCESS."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task_id = f"pf_task_{uuid4().hex[:8]}"
        fake_report = VerificationReport(
            task_id=task_id,
            all_passed=False,
            total_checks=2,
            passed_checks=1,
            failed_checks=1,
            evidence=[
                VerificationEvidence(
                    check_name="Build Checker",
                    category=CheckCategory.BUILD,
                    exit_code=0,
                    passed=True,
                ),
                VerificationEvidence(
                    check_name="Unit Tests",
                    category=CheckCategory.TEST,
                    exit_code=1,
                    passed=False,
                    stderr="AssertionError: expected 42 got 0",
                ),
            ],
        )
        verification_engine.generate_manifest(task_id, fake_report)

        with patch("app.api.delegate.verification_engine.verify_task", return_value=fake_report):
            envelope = {
                "task_id": task_id,
                "source_agent": "friday",
                "target_agent": "forge",
                "action": "test",
                "payload": {"task_id": task_id},
            }
            resp = await client.post("/api/v1/forge/delegate", json=envelope)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "PARTIAL_FAILURE"
            assert "AssertionError" in data["error"]
            assert data["verification_manifest"]["all_passed"] is False


@pytest.mark.asyncio
async def test_sentinel_pre_delivery_gate(temp_workspace_context):
    """12. Sentinel security gate detects critical vulnerabilities and halts delivery."""
    packager = DeliveryPackager(wm=temp_workspace_context["wm"])
    fs: FilesystemTool = temp_workspace_context["fs"]
    task_id = f"sec_gate_task_{uuid4().hex[:6]}"

    # Inject critical hardcoded AWS secret (AKIA + 16 chars = 20 chars total)
    fs.create_file(
        task_id,
        "src/config.py",
        "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n",
        role="developer",
    )

    with pytest.raises(SecurityGateFailure) as exc_info:
        await packager.package_delivery(
            task_id=task_id,
            goal="Deploy payment microservice",
            require_sentinel_gate=True,
        )
    assert "Sentinel security gate failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_memora_post_verification_writeback_gate():
    """13. Memora writeback only occurs when verification passes completely."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Mock memora client
        mock_memora = AsyncMock()
        mock_memora.a_record_interaction = AsyncMock(return_value="mem_event_123")

        with patch("app.api.delegate.get_memora_client", return_value=mock_memora):
            # 1. Successful verification -> writeback called
            envelope_success = {
                "task_id": f"mem_success_{uuid4().hex[:6]}",
                "source_agent": "friday",
                "target_agent": "forge",
                "action": "build",
                "payload": {
                    "goal": "Implement Fibonacci sequence generator",
                    "execute_now": True,
                },
            }
            pass_report = VerificationReport(
                task_id=envelope_success["task_id"],
                all_passed=True,
                total_checks=1,
                passed_checks=1,
                failed_checks=0,
                evidence=[VerificationEvidence(check_name="Math Check", category=CheckCategory.TEST, exit_code=0, passed=True)],
            )
            fake_task = TaskEntity(
                id=envelope_success["task_id"],
                goal=envelope_success["payload"]["goal"],
                workspace_path="/tmp/test",
                state=TaskState.COMPLETED,
            )
            with patch("app.core.orchestrator.OrchestratorCore.run_task", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = fake_task
                with patch("app.api.delegate.verification_engine.verify_task", return_value=pass_report):
                    resp = await client.post("/api/v1/forge/delegate", json=envelope_success)
                    assert resp.status_code == 200
                    assert resp.json()["status"] == "SUCCESS"
                    assert mock_memora.a_record_interaction.called

        # 2. Failed verification -> writeback NOT called
        mock_memora_fail = AsyncMock()
        with patch("app.api.delegate.get_memora_client", return_value=mock_memora_fail):
            envelope_fail = {
                "task_id": f"mem_fail_{uuid4().hex[:6]}",
                "source_agent": "friday",
                "target_agent": "forge",
                "action": "build",
                "payload": {
                    "goal": "Implement Broken Service",
                    "execute_now": True,
                },
            }
            fail_report = VerificationReport(
                task_id=envelope_fail["task_id"],
                all_passed=False,
                total_checks=1,
                passed_checks=0,
                failed_checks=1,
                evidence=[VerificationEvidence(check_name="Broken Check", category=CheckCategory.TEST, exit_code=1, passed=False)],
            )
            fake_fail_task = TaskEntity(
                id=envelope_fail["task_id"],
                goal=envelope_fail["payload"]["goal"],
                workspace_path="/tmp/test",
                state=TaskState.FAILED,
            )
            with patch("app.core.orchestrator.OrchestratorCore.run_task", new_callable=AsyncMock) as mock_run2:
                mock_run2.return_value = fake_fail_task
                with patch("app.api.delegate.verification_engine.verify_task", return_value=fail_report):
                    resp2 = await client.post("/api/v1/forge/delegate", json=envelope_fail)
                    assert resp2.status_code == 200
                    assert resp2.json()["status"] in ("FAILED", "PARTIAL_FAILURE")
                    assert not mock_memora_fail.a_record_interaction.called


def test_repository_allowlist_validation():
    """14. Repository allowlist rejects malicious or unauthorized URLs."""
    # Allowed
    WorkspaceManager.validate_repository_url("https://github.com/surendra2304/FRIDAY.git")
    WorkspaceManager.validate_repository_url("https://github.com/surendra2304/Forge")
    WorkspaceManager.validate_repository_url("git@github.com:surendra2304/Forge.git")

    # Disallowed
    with pytest.raises(ValueError):
        WorkspaceManager.validate_repository_url("javascript:alert(1)")

    with pytest.raises(ValueError):
        WorkspaceManager.validate_repository_url("http://insecure-untrusted-repo.org/malware.git")
