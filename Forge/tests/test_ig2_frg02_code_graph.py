"""TASK-IG2-FRG-02: Graphify code-graph step for Forge.

Pins: per-agent subfolder planning, the per-run file limit refusal,
honest UNAVAILABLE when the CLI is absent, code-only command building
(no cloud, semantic pass off by default), and the stdlib query/path/
explain side over a graphify-style graph.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from forge_upgrade.code_graph import (
    MAX_FILES_PER_RUN,
    CodeGraph,
    build_command,
    build_graph,
    graphify_status,
    plan_subfolder_runs,
)

GRAPH = {
    "nodes": [
        {"id": "forge_main", "label": "Forge main"},
        {"id": "review_passes", "label": "Review passes"},
        {"id": "fleet_client", "label": "Fleet client"},
        {"id": "isolated", "label": "Isolated node"},
    ],
    "edges": [
        {"source": "forge_main", "target": "review_passes", "type": "EXTRACTED"},
        {"source": "review_passes", "target": "fleet_client", "type": "INFERRED"},
    ],
}


def _write_graph(tmp_path: Path) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(GRAPH), encoding="utf-8")
    return path


def test_query_matches_id_and_label(tmp_path) -> None:
    graph = CodeGraph.load(_write_graph(tmp_path))
    assert [n["id"] for n in graph.query("review")] == ["review_passes"]
    assert [n["id"] for n in graph.query("FLEET")] == ["fleet_client"]


def test_path_follows_edges_and_reports_none_when_disconnected(tmp_path) -> None:
    graph = CodeGraph.load(_write_graph(tmp_path))
    assert graph.path("forge_main", "fleet_client") == [
        "forge_main",
        "review_passes",
        "fleet_client",
    ]
    assert graph.path("forge_main", "isolated") is None
    assert graph.path("forge_main", "missing-node") is None


def test_explain_returns_node_edges_and_degree(tmp_path) -> None:
    graph = CodeGraph.load(_write_graph(tmp_path))
    info = graph.explain("review_passes")
    assert info is not None
    assert info["degree"] == 2
    assert {e["type"] for e in info["edges"]} == {"EXTRACTED", "INFERRED"}
    assert graph.explain("missing-node") is None


def test_plan_subfolder_runs_lists_agent_dirs(tmp_path) -> None:
    (tmp_path / "Forge").mkdir()
    (tmp_path / "Stratex").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    runs = plan_subfolder_runs(tmp_path)
    assert [p.name for p in runs] == ["Forge", "Stratex"]


def test_build_graph_refuses_oversized_target(tmp_path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x = 1\n", encoding="utf-8")
    result = build_graph(tmp_path, max_files=3)
    assert result.status == "refused"
    assert "per-agent" in result.detail


def test_build_graph_refuses_non_directory(tmp_path) -> None:
    result = build_graph(tmp_path / "nope")
    assert result.status == "refused"


def test_build_command_is_code_only_by_default() -> None:
    cmd = build_command(Path("Forge"))
    assert cmd[0] == "graphify"
    assert "--code-only" in cmd
    assert not any("cloud" in part.lower() for part in cmd)
    assert "--code-only" not in build_command(Path("Forge"), semantic=True)


def test_status_reports_unavailable_without_cli(monkeypatch) -> None:
    monkeypatch.setattr("forge_upgrade.code_graph.shutil.which", lambda _: None)
    status = graphify_status()
    assert not status.available
    assert "graphifyy" in status.detail
    assert MAX_FILES_PER_RUN == 500
