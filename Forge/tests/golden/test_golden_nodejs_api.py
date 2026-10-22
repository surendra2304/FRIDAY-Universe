"""
Golden Benchmark: Node.js & TypeScript REST API Service.

Validates:
1. TaskAnalyzer stack detection recognizing Node.js, TypeScript, and Express.js.
2. PlannerEngine and dynamic specialist agent synthesis of TypeScript manifests, entrypoints, and routes.
3. VerificationEngine polyglot checkers executing Node/TypeScript build and test suites.
4. DeliveryPackager generating release artifacts and tags.
5. Resilient workspace sandboxing and cleanup.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.registry import agent_registry
from app.core.analyzer import TaskAnalyzer
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.delivery import DeliveryPackager
from app.execution.engine import ExecutionEngine
from app.memory.db import DatabaseManager
from app.memory.state_store import StateStore
from app.providers.direct import DirectProvider
from app.verification.engine import VerificationEngine


@pytest.mark.asyncio
async def test_golden_benchmark_nodejs_typescript_api(temp_dir: Path):
    """
    End-to-End Golden Benchmark:
    Synthesizes an Express.js & TypeScript REST API with package manifests,
    routing, JSON models, tests, verification battery, and release packaging.
    """
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    db_mgr = DatabaseManager(db_path=temp_dir / "test_nodejs_golden.db")
    await db_mgr.init_db()
    StateStore(db_mgr)
    analyzer = TaskAnalyzer()
    verifier = VerificationEngine(engine=engine, wm=wm)
    packager = DeliveryPackager(engine=engine, wm=wm)

    task_id = f"task_golden_nodejs_{uuid4().hex[:8]}"

    try:
        # 1. Goal Specification & Stack Analysis
        goal = "Build a high-performance Express.js REST API with TypeScript for Task & Note Management"
        requirements = [
            "Use TypeScript with tsconfig.json and package.json",
            "Implement REST endpoints: GET /health, GET /tasks, POST /tasks, DELETE /tasks/:id",
            "Include input validation and structured JSON error responses",
            "Write automated unit/integration tests with Node test runner or Jest",
            "Create production build artifacts in dist/",
        ]

        analysis = await analyzer.analyze(goal=goal, requirements=requirements)
        assert analysis.primary_language == "TypeScript"
        assert analysis.detected_runtime == "Node.js"
        assert "Express.js" in analysis.detected_frameworks

        # 2. Workspace Provisioning
        ws_paths = wm.create_workspace(task_id)
        assert ws_paths.project.exists()

        # 3. Dynamic Specialist Generation via Routed Model Provider
        mock_developer_code = """
### File: package.json
```json
{
  "name": "express-task-api",
  "version": "1.0.0",
  "description": "Express.js TypeScript Task API",
  "main": "dist/index.js",
  "scripts": {
    "build": "node -e 'console.log(\\\"Build success\\\")'",
    "start": "node dist/index.js",
    "test": "node --test tests/*.test.js"
  },
  "dependencies": {
    "express": "^4.19.2"
  },
  "devDependencies": {
    "typescript": "^5.4.0"
  }
}
```

### File: tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

### File: src/index.ts
```typescript
export interface TaskItem {
  id: string;
  title: string;
  completed: boolean;
}

export class TaskService {
  private tasks: Map<string, TaskItem> = new Map();

  getAll(): TaskItem[] {
    return Array.from(this.tasks.values());
  }

  create(title: string): TaskItem {
    const id = Date.now().toString();
    const task: TaskItem = { id, title, completed: false };
    this.tasks.set(id, task);
    return task;
  }

  delete(id: string): boolean {
    return this.tasks.delete(id);
  }
}
```

### File: dist/index.js
```javascript
// Compiled distribution bundle
class TaskService {
  constructor() {
    this.tasks = new Map();
  }
  getAll() {
    return Array.from(this.tasks.values());
  }
  create(title) {
    const id = Date.now().toString();
    const task = { id, title, completed: false };
    this.tasks.set(id, task);
    return task;
  }
  delete(id) {
    return this.tasks.delete(id);
  }
}

module.exports = { TaskService };
```

### File: tests/api.test.js
```javascript
const test = require('node:test');
const assert = require('node:assert');
const { TaskService } = require('../dist/index.js');

test('TaskService create and get tasks', (t) => {
  const service = new TaskService();
  const task = service.create('Write Golden Test');
  assert.strictEqual(task.title, 'Write Golden Test');
  assert.strictEqual(task.completed, false);

  const all = service.getAll();
  assert.strictEqual(all.length, 1);
  assert.strictEqual(all[0].id, task.id);
});

test('TaskService delete task', (t) => {
  const service = new TaskService();
  const task = service.create('Temporary Task');
  assert.strictEqual(service.delete(task.id), true);
  assert.strictEqual(service.getAll().length, 0);
});
```
"""

        from unittest.mock import AsyncMock, patch

        from app.integrations.ai_universe_client import AIUniverseResponse

        provider = DirectProvider(mock_response=mock_developer_code)
        dev_agent = agent_registry.create_agent("developer", provider=provider)

        with patch(
            "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
        ) as mock_ask:
            mock_ask.return_value = AIUniverseResponse(
                answer=mock_developer_code,
                confidence=0.95,
                run_id="run_golden_node_001",
            )
            exec_res = await dev_agent.execute_step(
                task_id=task_id,
                node_title="Implement Express & TypeScript Task API",
                context={"goal": goal, "requirements": requirements},
                engine=engine,
            )

        assert exec_res["status"] == "success"
        assert len(exec_res["files_written"]) >= 4
        assert "package.json" in exec_res["files_written"]
        assert "src/index.ts" in exec_res["files_written"]
        assert "dist/index.js" in exec_res["files_written"]
        assert "tests/api.test.js" in exec_res["files_written"]

        # 4. Objective Polyglot Verification Battery
        verification_report = await verifier.verify_task(task_id)

        # Check evidence items
        check_names = [ev.check_name for ev in verification_report.evidence]
        assert "Node.js / TypeScript Build Check" in check_names
        assert "Node.js Test Suite Runner" in check_names

        # Assert all Node checks passed
        for ev in verification_report.evidence:
            assert ev.passed is True, f"Check '{ev.check_name}' failed: {ev.stderr}"
        assert verification_report.all_passed is True

        # 5. Release Delivery Packaging
        delivery = await packager.package_delivery(
            task_id=task_id,
            goal=goal,
            requirements=requirements,
            tag_name="v1.0-nodejs-delivery",
        )

        assert delivery.release_tag == "v1.0-nodejs-delivery"
        assert delivery.test_build_status["all_passed"] is True
        assert (ws_paths.artifacts / "COMPLETION_REPORT.md").exists()
        assert (ws_paths.artifacts / "completion_report.json").exists()

    finally:
        wm.cleanup_workspace(task_id)
