"""TASK-FRG-027: Forge repos wave 3 through the production caller.

M3E Canvas (adopt) and JCode (adapt) are exercised THROUGH
``ForgeBuildRun`` — the same production caller FRG-028 wired —
never only as libraries. MausBot/OpenMausBot and Paperclip are
reference-only: the guardrail test proves their absence from
every Forge production path and dependency surface.

Live-fleet proof (a real build task for another agent through
the deployed Forge, output used in production) is owed after
coordinator clearance and is NOT claimed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from forge_upgrade.build_run import BuildRunSpec, ForgeBuildRun
from forge_upgrade.jcode_harness import LeanSessionLedger, compact_context

LINKS_GRAPH = {
    "directed": False,
    "nodes": [
        {"id": "demo_greeter", "label": "Greeter"},
        {"id": "demo_greeter_greet", "label": "greet"},
        {"id": "demo_test_greeter", "label": "test_greet"},
    ],
    "links": [
        {
            "source": "demo_greeter",
            "target": "demo_greeter_greet",
            "relation": "contains",
            "confidence": "EXTRACTED",
        },
        {
            "source": "demo_greeter_greet",
            "target": "demo_test_greeter",
            "relation": "calls",
            "confidence": "EXTRACTED",
        },
    ],
}

RULE_OUTPUT = (
    "### Rule Group 1: system / **/*.py\n\nApplies to:\n- demo/greeter.py\n\n"
    "### Rule Group 2: python / **/*.py\n\nApplies to:\n- demo/test_greeter.py\n"
)

SKETCH = {
    "app_name": "Kirana List",
    "screens": [
        {
            "id": "home",
            "name": "Home",
            "components": [
                {"type": "app_bar", "label": "Kirana List"},
                {"type": "list", "label": "Shopping items"},
                {"type": "fab", "label": "Add item"},
            ],
            "links": [{"to": "add", "trigger": "tap the Add item button"}],
        },
        {
            "id": "add",
            "name": "Add Item",
            "components": [
                {"type": "text_field", "label": "Item name"},
                {"type": "button", "label": "Save"},
            ],
            "links": [{"to": "home", "trigger": "tap Save"}],
        },
    ],
}


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _runner(proc):
    def run(cmd, **kwargs):
        return proc

    return run


def _write_sketch_app(workdir: Path) -> list[str]:
    demo = workdir / "demo"
    demo.mkdir(exist_ok=True)
    (demo / "__init__.py").write_text("", encoding="utf-8")
    (demo / "greeter.py").write_text(
        '"""Demo build output for the FRG-027 proof run."""\n\n\n'
        'def greet(name: str) -> str:\n'
        '    return f"hello, {name}"\n',
        encoding="utf-8",
    )
    (demo / "test_greeter.py").write_text(
        "from demo.greeter import greet\n\n\n"
        "def test_greet_names_the_person():\n"
        '    assert greet("forge") == "hello, forge"\n',
        encoding="utf-8",
    )
    (demo / "index.html").write_text(
        "<h1>Kirana List</h1><a href='add.html'>Add item</a>\n",
        encoding="utf-8",
    )
    (demo / "add.html").write_text(
        "<h1>Add Item</h1><a href='index.html'>Save</a>\n",
        encoding="utf-8",
    )
    return [
        "demo/__init__.py",
        "demo/greeter.py",
        "demo/test_greeter.py",
        "demo/index.html",
        "demo/add.html",
    ]


def _base_spec(**overrides) -> BuildRunSpec:
    spec = BuildRunSpec(
        task_id="frg027-demo",
        task="Build the sketched Kirana List app pages with a greeter test",
        assumptions=["the demo workspace is writable", "pytest is available"],
        success_criteria=["one page per sketched screen", "pytest passes"],
        target_agent="demo",
        target_dir=".",
        scope_prefixes=["demo"],
        build_config={"name": "frg027-demo", "tools": ["pytest"]},
        steps=[_write_sketch_app],
        test_command=[sys.executable, "-m", "pytest", "-q", "demo/test_greeter.py"],
        graph_terms=["greeter", "test_greeter"],
        graph_runner=_runner(_Proc(0, "")),
        ocr_runner=_runner(_Proc(0, RULE_OUTPUT)),
        sketch=SKETCH,
        session_id="frg027-session-a",
    )
    for key, value in overrides.items():
        setattr(spec, key, value)
    return spec


def _seed_links_graph(workdir: Path) -> None:
    out = workdir / "graphify-out"
    out.mkdir(exist_ok=True)
    (out / "graph.json").write_text(json.dumps(LINKS_GRAPH), encoding="utf-8")


def _fake_graphify_cli(monkeypatch) -> None:
    monkeypatch.setattr(
        "forge_upgrade.code_graph.shutil.which", lambda _: "/usr/bin/graphify"
    )


def test_sketch_and_lean_session_run_through_build_run(tmp_path, monkeypatch) -> None:
    _fake_graphify_cli(monkeypatch)
    _seed_links_graph(tmp_path)
    report = ForgeBuildRun(_base_spec()).run(tmp_path)
    assert report.status == "completed", report.summary()
    assert report.evidence["m3e_sketch"].startswith("adopted: Kirana List")
    assert "2 screens" in report.evidence["m3e_sketch"]
    assert "2 flows" in report.evidence["m3e_sketch"]
    assert "Kirana List" in report.evidence["m3e_prompt"]
    assert report.evidence["jcode_context"].startswith("lean context ")
    assert "reserved scope demo" in report.evidence["jcode_session"]
    assert report.evidence["jcode_files"] == "no cross-session file conflicts"
    assert "demo/index.html" in report.changed_files
    assert "demo/add.html" in report.changed_files


def test_broken_sketch_blocks_before_any_code(tmp_path) -> None:
    written: list[str] = []

    def spy_step(workdir: Path) -> list[str]:
        written.append("ran")
        return []

    broken = {
        "app_name": "Broken",
        "screens": [
            {
                "id": "home",
                "name": "Home",
                "components": [{"type": "button", "label": "Go"}],
                "links": [{"to": "missing", "trigger": "tap Go"}],
            }
        ],
    }
    report = ForgeBuildRun(_base_spec(sketch=broken, steps=[spy_step])).run(tmp_path)
    assert report.status == "blocked", report.summary()
    assert written == []
    assert "links to unknown screen id 'missing'" in report.blockers[0]
    assert report.evidence["m3e_sketch"].startswith("refused:")


def test_lean_context_over_budget_blocks_before_any_code(tmp_path) -> None:
    written: list[str] = []

    def spy_step(workdir: Path) -> list[str]:
        written.append("ran")
        return []

    report = ForgeBuildRun(
        _base_spec(context_budget_chars=10, steps=[spy_step])
    ).run(tmp_path)
    assert report.status == "blocked", report.summary()
    assert written == []
    assert "lean session context refused" in report.blockers[0]
    assert "exceeds lean budget 10" in report.evidence["jcode_context"]


def test_parallel_session_scope_conflict_blocks_before_any_code(tmp_path) -> None:
    ledger = LeanSessionLedger()
    assert ledger.reserve("other-session", ["demo"]) == []
    written: list[str] = []

    def spy_step(workdir: Path) -> list[str]:
        written.append("ran")
        return []

    report = ForgeBuildRun(
        _base_spec(session_ledger=ledger, steps=[spy_step])
    ).run(tmp_path)
    assert report.status == "blocked", report.summary()
    assert written == []
    assert "lean session scope conflict" in report.blockers[0]
    assert "other-session" in report.evidence["jcode_session"]


def test_compact_context_drops_optional_never_required() -> None:
    required = ["task text", "criteria"]
    optional = ["x" * 500, "y" * 500]
    result = compact_context(required, optional, budget_chars=600)
    assert result.ok
    assert result.dropped_optional == 1
    assert result.total_chars <= 600


def test_reference_only_repos_absent_from_production_paths() -> None:
    forge_root = Path(__file__).resolve().parents[1]
    forbidden = ("mausbot", "openmausbot", "paperclip")
    hits: list[str] = []
    for base in (forge_root / "app", forge_root / "forge_upgrade"):
        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for token in forbidden:
                if token in text:
                    hits.append(f"{path.relative_to(forge_root)}: {token}")
    for dep_file in ("requirements.txt", "pyproject.toml"):
        text = (forge_root / dep_file).read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        for token in forbidden:
            if token in text:
                hits.append(f"{dep_file}: {token}")
    assert hits == []
