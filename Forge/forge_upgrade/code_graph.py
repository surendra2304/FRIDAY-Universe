"""Graphify code->knowledge-graph step for Forge (TASK-IG2-FRG-02).

Integrates Graphify (Graphify-Labs/graphify, Apache-2.0) into Forge's
repo-understanding workflow as an *on-demand* tool:

* no resident service, no idle RAM — a CLI run when a crew needs a
  caller/dependency map, then plain files on disk;
* runs are per-agent subfolder (the upstream skill warns past ~500
  files / 2M words and this repo is ~5,300 files), never one giant
  whole-repo graph;
* the deterministic AST pass only — the optional LLM semantic pass over
  docs/PDFs stays OFF by default (it spends model tokens);
* Graphify Cloud (paid) is never invoked.

The upstream PyPI package is ``graphifyy`` (double-y; other graphify*
packages are unaffiliated). If the CLI is not installed, every entry
point reports UNAVAILABLE honestly instead of fabricating a graph.

The query side (load/query/path/explain over ``graphify-out/graph.json``)
is implemented here in stdlib Python so a produced graph stays usable
without NetworkX or the CLI present.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

GRAPHIFY_PACKAGE = "graphifyy"  # PyPI name, double-y — see module docstring.
MAX_FILES_PER_RUN = 500  # upstream guidance: split beyond ~500 files.
IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
           "dist", "build", "graphify-out"}


@dataclass(slots=True)
class GraphifyStatus:
    available: bool
    executable: str | None
    detail: str


def graphify_status() -> GraphifyStatus:
    """Is the graphify CLI available on this machine?"""
    exe = shutil.which("graphify")
    if exe:
        return GraphifyStatus(True, exe, f"graphify CLI at {exe}")
    return GraphifyStatus(
        False,
        None,
        "graphify CLI not installed; install the upstream package with "
        f"`pip install {GRAPHIFY_PACKAGE}` (on-demand tool, not a service)",
    )


def plan_subfolder_runs(root: str | Path) -> list[Path]:
    """Split a repo into per-agent subfolder run targets.

    Top-level directories are the run units (one graph per agent).
    Files at the repo root are grouped under the root itself only when
    a top-level directory does not already cover the tree.
    """
    root = Path(root)
    runs = sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and child.name not in IGNORED
    )
    return runs


def count_source_files(target: str | Path) -> int:
    target = Path(target)
    return sum(
        1
        for p in target.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )


def build_command(target: str | Path, semantic: bool = False) -> list[str]:
    """Build the graphify invocation for one subfolder.

    ``semantic=False`` (default) keeps the run to the deterministic,
    no-LLM code pass. There is deliberately no cloud flag here.
    """
    cmd = ["graphify", str(target)]
    if not semantic:
        cmd.append("--code-only")
    return cmd


@dataclass(slots=True)
class GraphBuildResult:
    status: str  # "built" | "unavailable" | "refused" | "failed"
    target: str
    detail: str
    graph_json: str | None = None


def build_graph(
    target: str | Path,
    semantic: bool = False,
    max_files: int = MAX_FILES_PER_RUN,
    runner=subprocess.run,
) -> GraphBuildResult:
    """Run graphify over ONE subfolder, on demand.

    Refuses oversized targets (split per agent instead) and reports
    UNAVAILABLE when the CLI is missing — never invents a graph.
    """
    target = Path(target)
    if not target.is_dir():
        return GraphBuildResult("refused", str(target), "target is not a directory")
    files = count_source_files(target)
    if files > max_files:
        return GraphBuildResult(
            "refused",
            str(target),
            f"{files} files exceeds the {max_files}-file per-run limit; "
            "run per-agent subfolders (see plan_subfolder_runs)",
        )
    status = graphify_status()
    if not status.available:
        return GraphBuildResult("unavailable", str(target), status.detail)
    proc = runner(
        build_command(target, semantic=semantic),
        capture_output=True,
        text=True,
        timeout=900,
    )
    graph_json = target / "graphify-out" / "graph.json"
    if proc.returncode != 0:
        return GraphBuildResult(
            "failed", str(target), (proc.stderr or proc.stdout or "")[-500:]
        )
    if not graph_json.is_file():
        return GraphBuildResult(
            "failed", str(target), "graphify exited 0 but graphify-out/graph.json is missing"
        )
    return GraphBuildResult("built", str(target), f"graph for {files} files", str(graph_json))


# ---------------------------------------------------------------------------
# Query side: graphify-out/graph.json -> query / path / explain (stdlib only)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CodeGraph:
    """A loaded graphify graph: nodes with labels, edges with provenance."""

    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, graph_json: str | Path) -> "CodeGraph":
        data = json.loads(Path(graph_json).read_text(encoding="utf-8"))
        nodes = {}
        for node in data.get("nodes", []):
            node_id = str(node.get("id", ""))
            if node_id:
                nodes[node_id] = node
        return cls(nodes=nodes, edges=list(data.get("edges", [])))

    def _adjacency(self) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {node_id: set() for node_id in self.nodes}
        for edge in self.edges:
            src, dst = str(edge.get("source", "")), str(edge.get("target", ""))
            if src in adj and dst in adj:
                adj[src].add(dst)
                adj[dst].add(src)
        return adj

    def query(self, term: str, limit: int = 20) -> list[dict]:
        """Nodes whose id/label mentions ``term`` (case-insensitive)."""
        needle = term.casefold()
        hits = [
            node
            for node_id, node in self.nodes.items()
            if needle in node_id.casefold()
            or needle in str(node.get("label", "")).casefold()
        ]
        return hits[:limit]

    def path(self, start: str, goal: str) -> list[str] | None:
        """Shortest undirected path between two node ids, or None."""
        if start not in self.nodes or goal not in self.nodes:
            return None
        adj = self._adjacency()
        seen = {start}
        queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
        while queue:
            node, trail = queue.popleft()
            if node == goal:
                return trail
            for nxt in sorted(adj[node]):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, trail + [nxt]))
        return None

    def explain(self, node_id: str) -> dict | None:
        """A node plus its direct edges, each tagged EXTRACTED/INFERRED."""
        node = self.nodes.get(node_id)
        if node is None:
            return None
        related = [
            edge
            for edge in self.edges
            if node_id in (str(edge.get("source", "")), str(edge.get("target", "")))
        ]
        return {"node": node, "edges": related, "degree": len(related)}
