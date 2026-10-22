"""
Regression test for Finding 25: the generated CLI's JSON-backed store had no
locking around its load-modify-save cycle, and every writer used the exact
same literal `.tmp` filename.

Live reproduction (see notes/LIVE_USAGE_FINDINGS.md Finding 25 for the full
write-up): launching 20 concurrent `python main.py add ...` invocations
against a fresh store -- an entirely realistic way to use a local CLI tool
(two terminal tabs, a background job, a shell loop with `&`) -- crashed
several invocations with `FileNotFoundError: ... '<db>.tmp' -> '<db>'`
(all writers raced on the identical tmp filename) and silently lost others
to a lost-update race (two processes load the same list, each append their
own record, each save their own full copy, last writer wins). Only 12 of
the 20 records survived, with zero non-zero exit codes to signal anything
had gone wrong.

This test actually launches real concurrent subprocesses against a real
generated CLI script on a real temp directory -- no mocks -- and asserts
every single record survives with a unique id and no process crashes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.agents.synthesis import synthesize_project

GOAL = (
    "Create a Python CLI note-taking app with add, list, delete and update "
    "commands storing notes in a local JSON file"
)


def _write_generated_cli(tmp_path: Path) -> Path:
    files = synthesize_project(GOAL)
    main_path = tmp_path / "main.py"
    main_path.write_text(files["main.py"], encoding="utf-8")
    return main_path


def test_concurrent_add_invocations_never_lose_or_crash(tmp_path: Path):
    main_path = _write_generated_cli(tmp_path)
    db_path = tmp_path / "notes.json"
    n = 20

    procs = [
        subprocess.Popen(
            [sys.executable, str(main_path), "--db", str(db_path), "add", f"Note {i}"],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(n)
    ]
    outcomes = [(p, *p.communicate(timeout=30)) for p in procs]

    crashed = [
        (p.returncode, err) for p, _out, err in outcomes if p.returncode != 0 or "Traceback" in err
    ]
    assert not crashed, f"{len(crashed)}/{n} concurrent `add` invocations crashed: {crashed[:3]}"

    import json

    items = json.loads(db_path.read_text())
    assert len(items) == n, (
        f"expected all {n} concurrent adds to survive, found {len(items)} -- "
        f"lost-update race reintroduced"
    )
    ids = [item["id"] for item in items]
    assert len(set(ids)) == n, f"duplicate ids assigned under concurrency: {sorted(ids)}"


def test_concurrent_mixed_add_update_delete_do_not_crash(tmp_path: Path):
    main_path = _write_generated_cli(tmp_path)
    db_path = tmp_path / "notes.json"

    # Seed 20 records sequentially first.
    for i in range(20):
        subprocess.run(
            [sys.executable, str(main_path), "--db", str(db_path), "add", f"Seed {i}"],
            cwd=str(tmp_path), capture_output=True, text=True, timeout=30, check=True,
        )

    procs = []
    for i in range(1, 11):
        procs.append(subprocess.Popen(
            [sys.executable, str(main_path), "--db", str(db_path), "update", str(i),
             "--title", f"Updated {i}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ))
    for i in range(11, 21):
        procs.append(subprocess.Popen(
            [sys.executable, str(main_path), "--db", str(db_path), "delete", str(i)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ))
    outcomes = [(p, *p.communicate(timeout=30)) for p in procs]

    crashed = [
        (p.returncode, err) for p, _out, err in outcomes if p.returncode != 0 or "Traceback" in err
    ]
    assert not crashed, f"concurrent mixed update/delete crashed: {crashed[:3]}"

    import json

    items = json.loads(db_path.read_text())
    assert len(items) == 10, f"expected 10 records left after deleting 10 of 20, got {len(items)}"
    updated_titles = {item["id"]: item["title"] for item in items}
    for i in range(1, 11):
        assert updated_titles.get(i) == f"Updated {i}", (
            f"update for id {i} lost to a concurrent write race: {updated_titles.get(i)!r}"
        )
