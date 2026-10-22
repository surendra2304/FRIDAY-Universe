"""
Unit tests for SecurityChecker (Secret Scanner, SAST, Dependency Auditing) and SecurityReviewerRole.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.roles import SecurityReviewerRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.providers.direct import DirectProvider
from app.verification.checkers import SecurityChecker


@pytest.mark.asyncio
async def test_security_checker_secret_scanning_detection(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    checker = SecurityChecker()

    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # 1. Code with hardcoded OpenAI key and password
    insecure_code = """
import os
OPENAI_KEY = "sk-abcdef12345678901234567890"
DB_PASS = "password = 'SuperSecretProdPassword99!'"

def get_client():
    return OPENAI_KEY
"""
    wm.write_project_file(task_id, "src/config.py", insecure_code)

    evidence = await checker.run_check(task_id=task_id, engine=engine)
    assert evidence.passed is False
    assert evidence.exit_code == 1
    assert len(evidence.issues) >= 1
    assert any(i["type"] == "hardcoded_secret" for i in evidence.issues)


@pytest.mark.asyncio
async def test_security_checker_passes_on_secure_code(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    checker = SecurityChecker()

    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # Clean code using environment variables
    clean_code = """
import os

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_client():
    return OPENAI_KEY
"""
    wm.write_project_file(task_id, "src/config.py", clean_code)

    evidence = await checker.run_check(task_id=task_id, engine=engine)
    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert len(evidence.issues) == 0


@pytest.mark.asyncio
async def test_security_reviewer_role_auto_remediation(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # Seed vulnerable file
    insecure_code = 'API_TOKEN = "sk-ant-api03-abcdef12345678901234567890"\n'
    wm.write_project_file(task_id, "auth.py", insecure_code)

    # Mock remediated output from LLM
    mock_remediated_code = """
### File: auth.py
```python
import os

API_TOKEN = os.getenv("ANTHROPIC_API_KEY", "")
```
"""
    provider = DirectProvider(mock_response=mock_remediated_code)
    reviewer = SecurityReviewerRole(provider=provider)

    res = await reviewer.execute_step(
        task_id=task_id,
        node_title="Security Audit & Remediation",
        context={"goal": "Audit authentication security"},
        engine=engine,
    )

    assert res["status"] == "success"
    assert res["security_passed"] is True
    assert "auth.py" in res["files_remediated"]

    # Verify content in workspace is remediated
    remediated_content = engine.fs.read_file(task_id, "auth.py")
    assert "os.getenv" in remediated_content
    assert "sk-ant-" not in remediated_content
