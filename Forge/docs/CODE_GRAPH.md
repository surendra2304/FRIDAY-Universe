# Code graphs for Forge — Graphify (TASK-IG2-FRG-02)

Forge's repo-understanding workflow gains an on-demand code →
knowledge-graph step, adopting [Graphify](https://github.com/Graphify-Labs/graphify)
(Apache-2.0; pre-relicense portions under MIT, see its LICENSE-MIT).

## Rules of use in FRIDAY Universe

- **On-demand only.** Graphify is a CLI run when a crew needs a
  caller/dependency map. It is never a resident service (fleet RAM is
  ~956 MB per server; idle cost must be zero).
- **Per-agent subfolders.** The upstream tool warns past ~500 files /
  2M words; this repo is ~5,300 files. Graph one agent at a time
  (`Forge/`, `Stratex/`, …), never the whole repo at once.
  `forge_upgrade.code_graph.plan_subfolder_runs()` lists the run units
  and `build_graph()` refuses targets over the per-run file limit.
- **Code pass only by default.** The deterministic tree-sitter AST pass
  is local and costs no LLM credits. The optional semantic pass over
  docs/PDFs spends model tokens and stays off unless a task explicitly
  asks for it.
- **No Graphify Cloud.** The paid always-on/cross-repo sibling is not
  used (free-only rule).

## Install (developer machine / CI, not the fleet servers)

```bash
pip install graphifyy   # double-y: other graphify* PyPI packages are unaffiliated
```

## Use

```python
from forge_upgrade.code_graph import build_graph, CodeGraph

result = build_graph("Forge")            # -> Forge/graphify-out/graph.json
graph = CodeGraph.load(result.graph_json)
graph.query("review")                    # nodes mentioning a term
graph.path("mod_a", "mod_b")             # shortest dependency path
graph.explain("mod_a")                   # node + edges (EXTRACTED/INFERRED)
```

If the CLI is not installed, `build_graph()` returns status
`unavailable` with the install hint — it never fabricates a graph.
Outputs land in `<agent>/graphify-out/` (`graph.json`, `GRAPH_REPORT.md`,
`graph.html`); treat them as regenerable artefacts, not source.

Source reel: https://www.instagram.com/reel/DdPncBxAQoz/
