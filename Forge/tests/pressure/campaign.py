"""
CAMPAIGN DRIVER -- drive FORGE like a real user and record what happens.

Submits real tasks through the real pipeline (intake -> plan -> execute ->
verify -> recover -> peer review) and reports, for every task:
  state, files produced, which files compile, verification score, duration,
  and whether the goal's stated requirements were honoured.

Nothing is mocked. The workspace is a fresh temp dir per task.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/home/user/Forge")
os.chdir("/home/user/Forge")

REAL_TASKS = [
    ("cli_notes", "Create a Python CLI note-taking app with add, list and delete commands storing notes in a local JSON file"),
    ("cli_todo", "Build a command-line todo manager in Python with add, complete, list and clear commands"),
    ("cli_calc", "Create a Python CLI calculator supporting add, subtract, multiply and divide"),
    ("cli_fetch", "Build a Python CLI tool that fetches a URL and prints the page title"),
    ("api_todo", "Create a FastAPI REST API for a todo list with create, read, update and delete endpoints"),
    ("api_books", "Build a REST API for a bookstore inventory with CRUD operations using FastAPI"),
    ("api_auth", "Create a FastAPI service with user registration and login endpoints"),
    ("script_rename", "Create a Python script that renames all files in a directory to lowercase"),
    ("script_backup", "Build a Python script that copies files modified today into a backup folder"),
    ("script_csv", "Create a Python script that reads a CSV and prints summary statistics"),
    ("web_landing", "Create a landing page website for a coffee shop with a menu section and contact form"),
    ("web_portfolio", "Build a personal portfolio website with an about section, projects grid and contact link"),
    ("lib_strutil", "Create a Python string utility library with reverse, palindrome and word count functions"),
    ("lib_stats", "Build a Python statistics library with mean, median and mode functions"),
    ("cli_timer", "Create a Python CLI pomodoro timer with start, pause and reset commands"),
    ("api_notes", "Build a REST API for notes with tagging and search using FastAPI"),
    ("cli_pwd", "Create a Python CLI password generator with length and complexity options"),
    ("script_json", "Create a Python script that converts a JSON file to CSV"),
]

HOSTILE_TASKS = [
    ("empty", ""),
    ("whitespace", "   \n\t  "),
    ("one_word", "app"),
    ("punct", "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"),
    ("unicode", "создать приложение для заметок с добавлением и удалением"),
    ("emoji", "Build an app 🚀 that does ✨ things 🎉 with 💥 features"),
    ("very_long", "Create an app " + ("that does everything " * 400)),
    ("injection", "Create an app'); DROP TABLE tasks;-- with features"),
    ("newlines", "Create\n\nan\n\napp\n\nwith\n\nfeatures"),
    ("null_ish", "Create an app with a\x00null byte"),
    ("html", "<script>alert(1)</script>Create an app"),
    ("sql", "SELECT * FROM users WHERE name='x'"),
    ("path_trav", "../../etc/passwd Create an app"),
    ("cmd_inj", "Create an app; rm -rf / with features"),
    ("only_numbers", "1234567890"),
    ("repeat", "app " * 2000),
]


def requirement_hints(goal: str) -> list[str]:
    """The features a user explicitly asked for, used to detect silent drops."""
    g = goal.lower()
    hints = []
    for kw in ["add", "list", "delete", "remove", "update", "edit", "create",
               "read", "search", "clear", "complete", "reset", "start", "pause",
               "register", "login", "tag", "fetch", "rename", "backup", "convert",
               "mean", "median", "mode", "reverse", "palindrome", "count"]:
        if re.search(rf"\b{kw}\b", g):
            hints.append(kw)
    return hints


async def drive_one(orchestrator, task_id_holder, label, goal, timeout=600):
    from app.core.orchestrator import OrchestratorCore  # noqa

    t0 = time.perf_counter()
    rec = {"label": label, "goal": goal[:80], "state": None, "files": 0, "py": 0,
           "compiled": 0, "tests_passed": 0, "tests_total": 0,
           "verify": None, "reqs": requirement_hints(goal), "reqs_hit": [],
           "duration_s": 0.0, "error": None}
    try:
        task, _ = await asyncio.wait_for(orchestrator.intake_and_plan(goal=goal), timeout=timeout)
        tid = task.id
        rec["task_id"] = tid
        final = await asyncio.wait_for(orchestrator.run_task(tid, max_iterations=25), timeout=timeout)
        rec["state"] = str(final.state).split(".")[-1]
        rec["progress"] = final.progress_percentage

        wsd = orchestrator.wm.get_task_workspace_dir(tid)
        proj = wsd / "project"
        files = sorted(p for p in proj.rglob("*") if p.is_file() and ".git" not in p.parts)
        rec["files"] = len(files)
        py = [p for p in files if p.suffix == ".py"]
        rec["py"] = len(py)
        for p in py:
            try:
                compile(p.read_text(errors="replace"), str(p), "exec")
                rec["compiled"] += 1
            except SyntaxError:
                pass
        # Did the goal's requested features actually appear?
        blob = " ".join(p.read_text(errors="replace").lower() for p in py)
        for kw in rec["reqs"]:
            if re.search(rf"\b{re.escape(kw)}\b", blob):
                rec["reqs_hit"].append(kw)
        # Verification report
        vf = wsd / "artifacts" / "verification_report.json"
        if vf.exists():
            d = json.loads(vf.read_text())
            rec["verify"] = f"{d.get('passed_checks')}/{d.get('total_checks')}"
        # Run the project's own tests if it has any
        tests = [p for p in py if p.name.startswith("test_") or p.name.endswith("_test.py")]
        if tests:
            import subprocess
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                 *[str(p) for p in tests]],
                cwd=str(proj), capture_output=True, text=True, timeout=180,
            )
            m = re.search(r"(\d+) passed", r.stdout)
            f = re.search(r"(\d+) failed", r.stdout)
            rec["tests_passed"] = int(m.group(1)) if m else 0
            rec["tests_total"] = rec["tests_passed"] + (int(f.group(1)) if f else 0)
    except asyncio.TimeoutError:
        rec["error"] = "TIMEOUT"
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    rec["duration_s"] = round(time.perf_counter() - t0, 1)
    return rec


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="real", choices=["real", "hostile", "both"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="/tmp/pressure/campaign")
    args = ap.parse_args()

    from app.agents.coordinator import AgentCoordinator  # noqa
    from app.core.config import Settings
    from app.core.context import ContextManager
    from app.core.orchestrator import OrchestratorCore, StateStore
    from app.core.workspace import WorkspaceManager
    from app.execution.engine import ExecutionEngine
    from app.planning.planner import PlannerEngine
    from app.agents.registry import AgentRegistry

    tmp = Path(tempfile.mkdtemp(prefix="forge_campaign_"))
    settings = Settings()
    settings.workspaces_dir = tmp / "workspaces"
    settings.ensure_directories()
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    orch = OrchestratorCore(store=StateStore(), wm=wm, engine=engine,
                            planner=PlannerEngine(), registry=AgentRegistry(),
                            ctx_manager=ContextManager())

    suites = {"real": REAL_TASKS, "hostile": HOSTILE_TASKS}
    todo = []
    for name in (["real", "hostile"] if args.suite == "both" else [args.suite]):
        todo += [(f"{name}_{slug}", g) for slug, g in suites[name]]
    if args.limit:
        todo = todo[: args.limit]

    print(f"driving {len(todo)} real tasks through the full pipeline...\n")
    results = []
    for i, (label, goal) in enumerate(todo, 1):
        rec = await drive_one(orch, None, label, goal)
        results.append(rec)
        req = f"{len(rec['reqs_hit'])}/{len(rec['reqs'])}" if rec["reqs"] else "-"
        print(f"[{i:2}/{len(todo)}] {label:22} {str(rec['state']):10} "
              f"files={rec['files']:3} py={rec['py']:2} comp={rec['compiled']:2} "
              f"tests={rec['tests_passed']}/{rec['tests_total']} "
              f"verify={rec['verify']} reqs={req} {rec['duration_s']:5.1f}s "
              f"{rec['error'] or ''}")

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"campaign_{args.suite}.json").write_text(json.dumps(results, indent=2))

    # Summary
    ok = [r for r in results if r["state"] == "COMPLETED"]
    print(f"\n{'='*70}\nSUMMARY ({args.suite})")
    print(f"  tasks            : {len(results)}")
    print(f"  reached COMPLETED: {len(ok)}")
    print(f"  produced 0 files : {sum(1 for r in results if r['files']==0)}")
    print(f"  produced py      : {sum(1 for r in results if r['py']>0)}")
    print(f"  all py compiled  : {sum(1 for r in results if r['py']>0 and r['compiled']==r['py'])}")
    print(f"  project tests    : {sum(r['tests_passed'] for r in results)} passed / {sum(r['tests_total'] for r in results)} total")
    print(f"  errors           : {sum(1 for r in results if r['error'])}")
    dropped = [r["label"] for r in results if r["reqs"] and len(r["reqs_hit"]) < len(r["reqs"])]
    print(f"  dropped features : {len(dropped)} tasks {dropped[:6]}")
    shutil.rmtree(tmp, ignore_errors=True)


raise SystemExit(asyncio.run(main()))
