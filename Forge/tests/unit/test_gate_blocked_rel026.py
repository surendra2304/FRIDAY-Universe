"""TASK-REL-026: a gate that could not run is not a failed build.

Production defect (TASK-REL-023 evidence, 2026-11-14): Inference's
generate-tests endpoint degraded under provider strain (gemini
TimeoutError) and returned no tests; TesterRole ran pytest over an empty
project and the verification gate FAILED a build whose code was complete
and correct. The invariant from TASK-REL-019 stands — no tests, no pass —
but "tests could not be generated" is now a distinct, retryable outcome:

- TesterRole reports status="blocked" with failure_kind
  "test_generation_unavailable" (retryable) when generation produced no
  runnable tests and nothing executed; "failed" is reserved for tests
  that actually ran and failed.
- The Inference client surfaces the endpoint's 503 body
  (generation_status / retryable / error) instead of flattening it.
- OrchestratorCore parks the task in BLOCKED (resumable) without marking
  the gate node completed or failed; a resume re-runs the gate and the
  build is then judged by real tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.agents.roles import TesterRole
from app.integrations import ai_universe_client
from app.integrations.ai_universe_client import AIUniverseClient
from app.providers.base import ProviderResponse

MAIN_CODE = "def is_palindrome(s):\n    return s == s[::-1]\n"
GENERATED_TESTS = "def test_palindrome():\n    assert is_palindrome('aba')\n"


def _engine(fs, terminal, tmp_path):
    return SimpleNamespace(
        fs=fs,
        wm=SimpleNamespace(
            get_workspace_paths=lambda task_id: SimpleNamespace(project=tmp_path)
        ),
        terminal=terminal,
    )


def _terminal(exit_code, stdout="", stderr=""):
    return SimpleNamespace(
        run_command=AsyncMock(
            return_value=SimpleNamespace(exit_code=exit_code, stdout=stdout, stderr=stderr)
        )
    )


def _role_with_fallback(content=""):
    role = TesterRole()
    role.prompt_model = AsyncMock(
        return_value=ProviderResponse(content=content, model="explicit-fixture")
    )
    return role


@pytest.mark.asyncio
async def test_generated_tests_that_pass_are_a_success(monkeypatch, tmp_path):
    client = SimpleNamespace(
        generate_tests=AsyncMock(return_value={"test_code": GENERATED_TESTS, "generation_status": "generated"})
    )
    monkeypatch.setattr(ai_universe_client, "get_ai_universe_client", lambda: client)
    fs = MagicMock()
    fs.search_files.side_effect = [[], ["test_main.py"]]
    fs.read_file.return_value = MAIN_CODE
    fs.create_file.side_effect = lambda **kw: kw["relative_path"]
    role = _role_with_fallback()
    result = await role.execute_step(
        "t1", "Automated Test Suite & Verification Gate",
        {"goal": "write a palindrome checker", "requirements": []},
        _engine(fs, _terminal(0, stdout="1 passed"), tmp_path),
    )
    assert result["status"] == "success"
    assert result["failure_kind"] is None
    assert result["retryable"] is False


@pytest.mark.asyncio
async def test_generated_tests_that_fail_are_a_failed_verdict(monkeypatch, tmp_path):
    client = SimpleNamespace(
        generate_tests=AsyncMock(return_value={"test_code": GENERATED_TESTS, "generation_status": "generated"})
    )
    monkeypatch.setattr(ai_universe_client, "get_ai_universe_client", lambda: client)
    fs = MagicMock()
    fs.search_files.side_effect = [[], ["test_main.py"]]
    fs.read_file.return_value = MAIN_CODE
    fs.create_file.side_effect = lambda **kw: kw["relative_path"]
    role = _role_with_fallback()
    result = await role.execute_step(
        "t2", "Automated Test Suite & Verification Gate",
        {"goal": "write a palindrome checker", "requirements": []},
        _engine(fs, _terminal(1, stdout="1 failed", stderr="assert False"), tmp_path),
    )
    # Tests RAN and failed: a real verdict on the code, unchanged.
    assert result["status"] == "failed"
    assert result["failure_kind"] is None
    assert result["retryable"] is False


@pytest.mark.asyncio
async def test_unavailable_generation_blocks_the_gate_retryably(monkeypatch, tmp_path):
    client = SimpleNamespace(
        generate_tests=AsyncMock(return_value={
            "test_code": "",
            "generation_status": "degraded",
            "error": "attempt 1 (gemini/gemini-flash-latest): gemini: TimeoutError",
            "retryable": True,
        })
    )
    monkeypatch.setattr(ai_universe_client, "get_ai_universe_client", lambda: client)
    fs = MagicMock()
    fs.search_files.return_value = []
    fs.read_file.return_value = MAIN_CODE
    role = _role_with_fallback(content="")
    result = await role.execute_step(
        "t3", "Automated Test Suite & Verification Gate",
        {"goal": "write a palindrome checker", "requirements": []},
        _engine(fs, _terminal(5, stderr="no tests ran"), tmp_path),
    )
    assert result["status"] == "blocked"
    assert result["failure_kind"] == "test_generation_unavailable"
    assert result["retryable"] is True
    assert "generation_status='degraded'" in result["stderr"]


@pytest.mark.asyncio
async def test_existing_suite_that_collects_nothing_stays_a_failed_verdict(tmp_path):
    """Boundary of the REL-026 deferral: the blocked outcome exists for
    the case where Forge had to GENERATE tests and could not. A
    pre-existing suite that collects nothing is the deliverable's own
    defect and keeps the historical failed verdict (same pin as
    test_zero_unittest_exit_zero_is_not_passing_evidence)."""
    fs = MagicMock()
    fs.search_files.return_value = ["test_helpers.py"]
    fs.read_file.return_value = (
        "# helpers only, no test functions\n"
        "def helper_one():\n    return 1\n\n"
        "def helper_two():\n    return 2\n"
    )
    role = _role_with_fallback()
    result = await role.execute_step(
        "t4", "Automated Test Suite & Verification Gate",
        {"goal": "write a palindrome checker", "requirements": []},
        _engine(fs, _terminal(5, stderr="no tests ran"), tmp_path),
    )
    assert result["status"] == "failed"
    assert result["failure_kind"] is None
    assert result["retryable"] is False


def _http_client(monkeypatch, post):
    class Client:
        async def __aenter__(self):
            return SimpleNamespace(post=post)

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr(
        "app.integrations.ai_universe_client.httpx.AsyncClient", lambda **_: Client()
    )
    return AIUniverseClient(base_url="https://explicit-fixture.invalid")


@pytest.mark.asyncio
async def test_client_surfaces_503_generation_body(monkeypatch):
    response = httpx.Response(
        503,
        json={
            "test_code": "",
            "generation_status": "degraded",
            "error": "attempt 1 (gemini/gemini-flash-latest): gemini: TimeoutError",
            "retryable": True,
            "attempts": 3,
        },
        request=httpx.Request("POST", "https://explicit-fixture.invalid/v1/forge/generate-tests"),
    )

    async def post(*a, **kw):
        raise httpx.HTTPStatusError("503", request=response.request, response=response)

    client = _http_client(monkeypatch, post)
    result = await client.generate_tests("def convert(): pass")
    assert result["test_code"] == ""
    assert result["generation_status"] == "degraded"
    assert result["retryable"] is True
    assert "TimeoutError" in result["error"]


@pytest.mark.asyncio
async def test_client_transport_error_is_degraded_and_retryable(monkeypatch):
    async def post(*a, **kw):
        raise httpx.ReadTimeout("explicit fixture")

    client = _http_client(monkeypatch, post)
    result = await client.generate_tests("def convert(): pass")
    assert result["test_code"] == ""
    assert result["generation_status"] == "degraded"
    assert result["retryable"] is True
    assert "no tests generated" in result["error"]


@pytest.mark.asyncio
async def test_client_returns_generated_body_unchanged(monkeypatch):
    body = {"test_code": GENERATED_TESTS, "generation_status": "generated", "attempts": 2}

    async def post(*a, **kw):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)

    client = _http_client(monkeypatch, post)
    result = await client.generate_tests("def convert(): pass")
    assert result == body


# --- Orchestrator: blocked gate parks the task; resume re-runs it. ---
# Import app.recovery.engine at collection time (see the note in
# test_task_forge_002_truthful_completion.py: the recovery module binds
# VerificationEngine at class-creation and breaks if a double is in place).
import app.recovery.engine  # noqa: E402,F401
from app.core.config import Settings  # noqa: E402
from app.core.orchestrator import OrchestratorCore  # noqa: E402
from app.core.workspace import WorkspaceManager  # noqa: E402
from app.execution.engine import ExecutionEngine  # noqa: E402
from app.memory.models import TaskState  # noqa: E402
from app.memory.sqlite_test_backend import SQLiteTestDatabase  # noqa: E402
from app.memory.state_store import StateStore  # noqa: E402


class _StubRegistry:
    def __init__(self, tester_result):
        self.tester_result = tester_result

    def create_agent(self, role_name):
        if role_name == "tester":
            return SimpleNamespace(
                execute_step=AsyncMock(return_value=dict(self.tester_result))
            )
        return SimpleNamespace(execute_step=AsyncMock(return_value={"status": "success"}))


async def _make_orchestrator(temp_dir):
    db = SQLiteTestDatabase(temp_dir / "rel026.db")
    await db.init_db()
    store = StateStore(db)
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return OrchestratorCore(store=store, wm=wm, engine=engine), store


BLOCKED_GATE_RESULT = {
    "status": "blocked",
    "exit_code": 5,
    "stdout": "",
    "stderr": "Inference test generation returned no tests (generation_status='degraded', error='gemini: TimeoutError').",
    "failure_kind": "test_generation_unavailable",
    "retryable": True,
}


@pytest.mark.asyncio
async def test_blocked_gate_parks_task_without_a_verdict(temp_dir, monkeypatch):
    orchestrator, store = await _make_orchestrator(temp_dir)
    task, _graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction"],
    )
    orchestrator.registry = _StubRegistry(BLOCKED_GATE_RESULT)
    monkeypatch.setattr(
        OrchestratorCore, "_verify_and_repair", AsyncMock(return_value=None)
    )

    final = await orchestrator.run_task(task.id, max_iterations=30)

    assert final.state == TaskState.BLOCKED, (
        "a gate that could not run must park the task, not fail or complete it"
    )
    assert "test_generation_unavailable" in (final.error_message or "")
    event_types = [e.event_type for e in await store.get_audit_trail(task.id)]
    assert "node.blocked" in event_types
    assert "task.blocked" in event_types
    assert "task.failed" not in event_types
    assert "task.completed" not in event_types


@pytest.mark.asyncio
async def test_resumed_task_is_judged_by_real_gate_outcome(temp_dir, monkeypatch):
    orchestrator, store = await _make_orchestrator(temp_dir)
    task, _graph = await orchestrator.intake_and_plan(
        goal="Build arithmetic calculator CLI",
        requirements=["Support addition and subtraction"],
    )
    orchestrator.registry = _StubRegistry(BLOCKED_GATE_RESULT)
    monkeypatch.setattr(
        OrchestratorCore, "_verify_and_repair", AsyncMock(return_value=None)
    )
    blocked = await orchestrator.run_task(task.id, max_iterations=30)
    assert blocked.state == TaskState.BLOCKED

    # Provider strain cleared: resume (BLOCKED -> RUNNING is a legal
    # lifecycle transition) and let the gate actually run this time.
    await orchestrator.lifecycle.transition(
        task.id, TaskState.RUNNING, reason="resume after test generation recovered"
    )
    orchestrator.registry = _StubRegistry(
        {"status": "success", "exit_code": 0, "stdout": "3 passed", "stderr": ""}
    )
    final = await orchestrator.run_task(task.id, max_iterations=30)
    assert final.state == TaskState.COMPLETED
