"""
Unit tests for Dynamic Agent execution and automatic code file application.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.roles import (
    ArchitectRole,
    BackendEngineerRole,
    DebuggerRole,
    DeveloperRole,
    FrontendEngineerRole,
)
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.providers.direct import DirectProvider


@pytest.mark.asyncio
async def test_architect_generates_spec_file(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    mock_llm_response = """
# System Architecture Plan

### File: docs/ARCHITECTURE_SPEC.md
```markdown
# Architecture Specification
## Modules
- auth
- api
```

### File: schemas/models.py
```python
class Item:
    id: int
```
"""
    provider = DirectProvider(mock_response=mock_llm_response)
    architect = ArchitectRole(provider=provider)

    task_id = str(uuid4())
    res = await architect.execute_step(
        task_id=task_id,
        node_title="System Architecture",
        context={"goal": "Build scalable catalog service"},
        engine=engine,
    )

    assert res["status"] == "success"
    assert "docs/ARCHITECTURE_SPEC.md" in res["files_written"]

    # Verify file was written to workspace
    spec_content = engine.fs.read_file(task_id, "docs/ARCHITECTURE_SPEC.md")
    assert "Architecture Specification" in spec_content

    models_content = engine.fs.read_file(task_id, "schemas/models.py")
    assert "class Item:" in models_content


@pytest.mark.asyncio
async def test_developer_extracts_and_creates_code_files(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    mock_code_output = """
Here is the core math module implementation:

### File: math_engine/calculator.py
```python
def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b
```
"""
    provider = DirectProvider(mock_response=mock_code_output)
    dev = DeveloperRole(provider=provider)

    task_id = str(uuid4())
    res = await dev.execute_step(
        task_id=task_id,
        node_title="Core Calculator Implementation",
        context={"goal": "Calculator utility"},
        engine=engine,
    )

    assert res["status"] == "success"
    assert "math_engine/calculator.py" in res["files_written"]

    calc_code = engine.fs.read_file(task_id, "math_engine/calculator.py")
    assert "def add(a: int, b: int) -> int:" in calc_code
    assert "def multiply(a: int, b: int) -> int:" in calc_code


@pytest.mark.asyncio
async def test_frontend_and_backend_roles(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    fe_mock = """
### File: static/app.js
```javascript
console.log("Frontend initialized");
```
"""
    be_mock = """
### File: api/routes.py
```python
from fastapi import APIRouter
router = APIRouter()
```
"""
    fe_agent = FrontendEngineerRole(provider=DirectProvider(mock_response=fe_mock))
    be_agent = BackendEngineerRole(provider=DirectProvider(mock_response=be_mock))

    task_id = str(uuid4())
    fe_res = await fe_agent.execute_step(task_id, "UI Component", {"goal": "Web App"}, engine)
    be_res = await be_agent.execute_step(task_id, "API Routes", {"goal": "Web App"}, engine)

    assert "static/app.js" in fe_res["files_written"]
    assert "api/routes.py" in be_res["files_written"]

    assert engine.fs.read_file(task_id, "static/app.js") == 'console.log("Frontend initialized");'
    assert "from fastapi import APIRouter" in engine.fs.read_file(task_id, "api/routes.py")


@pytest.mark.asyncio
async def test_debugger_applies_fix_files(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    fix_mock = """
Fixing bug in utils:

### File: utils/helpers.py
```python
def safe_divide(a, b):
    if b == 0:
        return 0
    return a / b
```
"""
    debugger = DebuggerRole(provider=DirectProvider(mock_response=fix_mock))
    task_id = str(uuid4())

    res = await debugger.execute_step(
        task_id=task_id,
        node_title="Fix ZeroDivisionError",
        context={"error": "ZeroDivisionError: division by zero"},
        engine=engine,
    )

    assert res["status"] == "success"
    assert "utils/helpers.py" in res["fixed_files"]
    assert "def safe_divide(a, b):" in engine.fs.read_file(task_id, "utils/helpers.py")
