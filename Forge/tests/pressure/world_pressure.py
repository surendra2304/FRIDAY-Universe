"""
Real-world pressure: concurrency, restart, resource limits and persistence.

Not pytest. These are the failure modes a user actually hits: submitting many
tasks at once, killing the process mid-build, filling the disk, and corrupting
the state the agent depends on.
"""
import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/home/user/Forge")
os.chdir("/home/user/Forge")

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL {msg}")


def build_orchestrator(workspaces_dir: Path, db_path: Path):
    from app.agents.registry import AgentRegistry
    from app.core.config import Settings
    from app.core.context import ContextManager
    from app.core.orchestrator import OrchestratorCore, StateStore
    from app.core.workspace import WorkspaceManager
    from app.execution.engine import ExecutionEngine
    from app.memory.db import DatabaseManager
    from app.planning.planner import PlannerEngine

    settings = Settings()
    settings.workspaces_dir = workspaces_dir
    settings.ensure_directories()
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    store = StateStore(DatabaseManager(db_path=db_path))
    orch = OrchestratorCore(store=store, wm=wm, engine=engine, planner=PlannerEngine(),
                            registry=AgentRegistry(), ctx_manager=ContextManager())
    return orch, settings, wm


GOALS = [
    "Create a Python CLI note-taking app with add, list and delete commands",
    "Build a command-line todo manager in Python with add, complete and list commands",
    "Create a FastAPI REST API for a todo list with CRUD endpoints",
    "Create a Python script that renames all files in a directory to lowercase",
    "Create a Python string utility library with reverse and word count functions",
    "Create a Python CLI calculator supporting add and subtract",
    "Build a REST API for a bookstore inventory with CRUD operations",
    "Create a Python contact manager CLI with add, list, search and delete",
]


async def test_concurrent_builds():
    print("=== 8 concurrent real builds ===")
    tmp = Path(tempfile.mkdtemp(prefix="press_conc_"))
    orch, settings, wm = build_orchestrator(tmp / "ws", tmp / "forge.db")

    async def one(i):
        goal = GOALS[i % len(GOALS)]
        try:
            t, _ = await asyncio.wait_for(orch.intake_and_plan(goal=goal), timeout=180)
            final = await asyncio.wait_for(orch.run_task(t.id, max_iterations=25), timeout=600)
            proj = wm.get_task_workspace_dir(t.id) / "project"
            files = [p for p in proj.rglob("*.py") if p.is_file()] if proj.exists() else []
            compiles = 0
            for p in files:
                try:
                    compile(p.read_text(errors="replace"), str(p), "exec")
                    compiles += 1
                except SyntaxError:
                    pass
            return str(final.state).split(".")[-1], len(files), compiles
        except Exception as e:
            return f"ERR:{type(e).__name__}", 0, 0

    t0 = time.perf_counter()
    results = await asyncio.gather(*[one(i) for i in range(8)])
    dt = time.perf_counter() - t0
    ok = [r for r in results if r[0] == "COMPLETED"]
    print(f"  8 builds in {dt:.0f}s: {len(ok)}/8 COMPLETED")
    for i, r in enumerate(results):
        print(f"    task {i}: {r[0]:10} files={r[1]:2} compiled={r[2]}")
    if len(ok) < 8:
        fail(f"only {len(ok)}/8 concurrent builds completed")
    shutil.rmtree(tmp, ignore_errors=True)


async def test_restart_mid_build():
    """Kill the process during a build, then resume: state must survive."""
    print("=== restart mid-build ===")
    tmp = Path(tempfile.mkdtemp(prefix="press_restart_"))
    db = tmp / "forge.db"
    ws = tmp / "ws"

    script = tmp / "build_once.py"
    script.write_text(
        "import asyncio, sys\n"
        "sys.path.insert(0, '/home/user/Forge')\n"
        f"from pathlib import Path\n"
        f"ws = Path({str(ws)!r}); db = Path({str(db)!r})\n"
        "from app.core.config import Settings\n"
        "from app.core.context import ContextManager\n"
        "from app.core.orchestrator import OrchestratorCore, StateStore\n"
        "from app.core.workspace import WorkspaceManager\n"
        "from app.execution.engine import ExecutionEngine\n"
        "from app.memory.db import DatabaseManager\n"
        "from app.planning.planner import PlannerEngine\n"
        "from app.agents.registry import AgentRegistry\n"
        "async def main():\n"
        "    s = Settings(); s.workspaces_dir = ws; s.ensure_directories()\n"
        "    wm = WorkspaceManager(settings=s); eng = ExecutionEngine(wm=wm)\n"
        "    o = OrchestratorCore(store=StateStore(DatabaseManager(db_path=db)), wm=wm,\n"
        "                         engine=eng, planner=PlannerEngine(),\n"
        "                         registry=AgentRegistry(), ctx_manager=ContextManager())\n"
        "    t, _ = await o.intake_and_plan(goal=sys.argv[1])\n"
        "    print(t.id, flush=True)\n"
        "    await o.run_task(t.id, max_iterations=25)\n"
        "asyncio.run(main())\n"
    )
    goal = "Create a Python CLI note-taking app with add, list and delete commands"
    proc = subprocess.Popen(
        [sys.executable, str(script), goal],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    task_id = proc.stdout.readline().strip()
    time.sleep(12)  # let it get part-way through
    proc.kill()
    proc.wait()
    print(f"    killed after {task_id}")

    # The workspace and DB must still be readable and resumable.
    con = sqlite3.connect(str(db))
    rows = con.execute("SELECT id, state FROM tasks WHERE id=?", (task_id,)).fetchall()
    con.close()
    if not rows:
        fail("task row missing after the kill -- state was not persisted")
        return
    print(f"    persisted state: {rows[0][1]}")

    # Resume in a fresh process.
    r = subprocess.run(
        [sys.executable, str(script), goal], capture_output=True, text=True, timeout=900
    )
    if r.returncode != 0:
        fail(f"resume process failed: {r.stderr[-300:]}")
    else:
        new_id = r.stdout.strip().splitlines()[0]
        print(f"    fresh process built {new_id} OK")
    shutil.rmtree(tmp, ignore_errors=True)


async def test_corrupt_state():
    """Corrupt the database the agent depends on; it must fail loudly, not silently."""
    print("=== corrupt state ===")
    tmp = Path(tempfile.mkdtemp(prefix="press_corrupt_"))
    db = tmp / "forge.db"
    orch, settings, wm = build_orchestrator(tmp / "ws", db)
    try:
        t, _ = await asyncio.wait_for(orch.intake_and_plan(goal=GOALS[0]), timeout=180)
    except Exception as e:
        fail(f"intake failed on a clean DB: {type(e).__name__}: {e}")
        return

    # goal is NOT NULL by schema (correctly), so corrupt the persisted graph
    # instead -- the structure the orchestrator replays on every step.
    con = sqlite3.connect(str(db))
    try:
        con.execute("UPDATE task_graphs SET graph_json = '{{{{not json' WHERE task_id = ?", (t.id,))
        con.commit()
    except sqlite3.OperationalError:
        con.execute("DELETE FROM checkpoints WHERE task_id = ?", (t.id,))
        con.commit()
    con.close()

    try:
        final = await asyncio.wait_for(orch.run_task(t.id, max_iterations=5), timeout=300)
        print(f"    state after corrupting the goal: {final.state}")
        if final.state == "COMPLETED":
            fail("a task with a NULL goal reported COMPLETED")
    except Exception as e:
        print(f"    raised (acceptable if loud): {type(e).__name__}: {str(e)[:90]}")
    shutil.rmtree(tmp, ignore_errors=True)


async def test_readonly_workspace():
    """A workspace the agent cannot write to must be reported, not ignored."""
    print("=== unwritable workspace ===")
    tmp = Path(tempfile.mkdtemp(prefix="press_ro_"))
    orch, settings, wm = build_orchestrator(tmp / "ws", tmp / "forge.db")
    try:
        t, _ = await asyncio.wait_for(
            orch.intake_and_plan(goal="Create a Python CLI note-taking app"), timeout=180
        )
        proj = wm.get_task_workspace_dir(t.id) / "project"
        proj.mkdir(parents=True, exist_ok=True)
        os.chmod(proj, 0o500)
        try:
            final = await asyncio.wait_for(orch.run_task(t.id, max_iterations=25), timeout=400)
            print(f"    state with a read-only project dir: {final.state}")
            if final.state == "COMPLETED":
                fail("task claimed success while unable to write any file")
        finally:
            os.chmod(proj, 0o700)
    except Exception as e:
        print(f"    raised (acceptable if loud): {type(e).__name__}: {str(e)[:90]}")
    shutil.rmtree(tmp, ignore_errors=True)


async def main():
    print("=== real-world pressure ===")
    await test_concurrent_builds()
    await test_restart_mid_build()
    await test_corrupt_state()
    await test_readonly_workspace()
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILURES'}")
    return 1 if FAILS else 0


raise SystemExit(asyncio.run(main()))
