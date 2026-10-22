"""
Verify the deterministic synthesis engine: every generated project must compile
AND its own test suite must pass. Run in isolated temp dirs, no mocks.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/home/user/Forge")
from app.agents.synthesis import parse_goal, synthesize_project

GOALS = [
    "Create a Python CLI note-taking app with add, list and delete commands storing notes in a local JSON file",
    "Build a command-line todo manager in Python with add, complete, list and clear commands",
    "Create a Python CLI calculator supporting add, subtract, multiply and divide",
    "Create a FastAPI REST API for a todo list with create, read, update and delete endpoints",
    "Build a REST API for a bookstore inventory with CRUD operations using FastAPI",
    "Create a Python script that renames all files in a directory to lowercase",
    "Create a Python script that converts a JSON file to CSV",
    "Create a Python string utility library with reverse, palindrome and word count functions",
    "Build a Python statistics library with mean, median and mode functions",
    "Create a Python CLI password generator with length and complexity options",
    "Create a Python CLI pomodoro timer with start, pause and reset commands",
    "Build a REST API for notes with tagging and search using FastAPI",
    "Create a Python contact manager CLI with add, list, search and delete commands",
    "Create a Python expense tracker CLI with add, list and summary commands",
    "Build a Python habit tracker CLI with add, list and complete commands",
    "Create a Python recipe manager CLI with add, list and search commands",
    "Create a FastAPI REST API for user registration and login",
    "Build a Python event scheduler CLI with add, list and delete commands",
]

results = []
tmp = Path(tempfile.mkdtemp(prefix="synth_"))
for i, goal in enumerate(GOALS):
    d = tmp / f"p{i}"
    d.mkdir()
    spec = parse_goal(goal)
    files = synthesize_project(goal)
    if not files:
        results.append((goal[:45], spec.kind.value, "NO FILES", 0, 0, ""))
        continue
    for name, content in files.items():
        (d / name).write_text(content)
    tests = sorted(d.glob("test_*.py"))
    if not tests:
        results.append((goal[:45], spec.kind.value, "NO TESTS", len(files), 0, ""))
        continue
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
         *[t.name for t in tests]],
        cwd=str(d), capture_output=True, text=True, timeout=300,
    )
    import re
    p = re.search(r"(\d+) passed", r.stdout)
    f = re.search(r"(\d+) failed", r.stdout)
    e = re.search(r"(\d+) error", r.stdout)
    np_, nf, ne = (int(x.group(1)) if x else 0 for x in (p, f, e))
    results.append((goal[:45], spec.kind.value, "OK" if r.returncode == 0 else "FAIL",
                    len(files), np_, f"{nf} failed {ne} err" if (nf or ne) else ""))

print(f"{'goal':47} {'kind':9} {'res':6} {'files':>5} {'pass':>5}  detail")
print("-" * 95)
for goal, kind, res, nf_, np_, detail in results:
    print(f"{goal:47} {kind:9} {res:6} {nf_:5} {np_:5}  {detail}")

ok = sum(1 for r in results if r[2] == "OK")
tot = sum(r[4] for r in results)
print("-" * 95)
print(f"projects OK: {ok}/{len(results)}   tests passed: {tot}")
sys.exit(0 if ok == len(results) else 1)
