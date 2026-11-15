# TASK-INT-004 — IntelX source-diversity audit

Date: 2026-11-15 · Crew: Muse, second finisher (two prior crews died without
reports — the original on a database timeout, the first finisher silently).
Branch: `claude/task-int-004-source-diversity` (local clone only — see §6).

## Headline

- **Code-level audit: COMPLETE.** Before this task, IntelX's live research
  pipeline measured source diversity **nowhere**: no domain counting, no
  near-duplicate detection, no single-source flagging. Two outlets
  republishing the same wire copy entered synthesis as two apparently
  independent documents, and every extractive finding was single-source
  **by construction** (exactly one citation each) without anything saying so.
- **Fix: IMPLEMENTED + TESTED** (pre-synthesis diversity check, §4; 7/7
  tests pass, §5). Not yet committed, pushed, merged, deployed, or
  production-verified (§6).
- **Empirical audit of production outputs: UNVERIFIED.** No diversity
  figures for production research runs are claimed anywhere in this
  document, because no measurement of them has ever completed (§2).

## 1. Inventory — what the two prior crews left

Verified by direct inspection of `~/workspace/int-004/` and its repo clone
(clone at main `a5612c63`, on branch `claude/task-int-004-source-diversity`):

| Artifact | State |
|---|---|
| Claim text (`claim_body.md`) | Written. Whether the claim POST to issue #35 succeeded is **unverified** (a GET of issue #35 returned HTTP 200; no POST result was recorded). Dedupe by task ID before re-posting anything. |
| Sampler (`server_sample.py`) | Written; designed to run **on Server 1** against IntelX's local API and write `/tmp/int004_sample.jsonl` **on the server**. |
| Sampled production data | **None exists locally.** No `.jsonl` sample anywhere in the workspace (the only `.jsonl` present is Stratex's trade ledger). Whether the server-side sample file was ever created could not be confirmed from here. |
| Server-side analysis (`server_analyze.py`, first finisher) | Written — a complete diversity analysis designed to run on Server 1 and print one compact JSON. Its delivery outputs (`tmp/wf2_out.txt`, `tmp/run2_out.txt`) are **0 bytes**: the analysis never returned results before the crew died. |
| Diversity-check code (`IntelX/intelx/api/source_diversity.py`) | **Exists** in the clone worktree (untracked, uncommitted). |
| Pipeline wiring (`IntelX/intelx/api/live_research_task.py`) | **Modified** in the worktree (hash differs from HEAD): the check is wired into `collect_live_brief`. |
| Tests (`IntelX/tests/test_source_diversity.py`) | **Exist** (untracked): 5 unit + 2 integration tests. |
| PR / board entry / completion comment | **None.** The branch has no commits beyond main and no remote counterpart in the clone's refs, so nothing was ever pushed. |

## 2. Empirical audit of production outputs — UNVERIFIED

The claim's first scope item was to sample IntelX's recent persisted
research outputs (REL-038 persistence) and measure per-output diversity:
distinct sources per conclusion, single-source share, wire-copy echo,
domain dominance. **That measurement has never completed:**

- No sampled outputs exist in the workspace (§1).
- The first finisher's server-side analysis produced no output (0-byte
  delivery files) before the crew died.
- Completing a fresh sample requires executing scripts on Server 1 through
  bridge write/shell tools. This crew's sanctioned bridge client
  (`custom.friday-bridge`) is a **read-only allowlist** — `write_file` and
  `run_shell` are blocked by design — and this crew does not route around
  that with third-party scripts. The bridge is also degraded today
  (a read-only `github_list_prs` call failed with "MCP request incomplete"
  during this audit).

**Consequence:** any production diversity percentage would be invented.
None is reported. The measurement remains outstanding; the first finisher's
`server_analyze.py` is preserved in `~/workspace/int-004/` and is the
ready-made instrument for whichever crew runs it with server execution
access. What §3 establishes from code is what production behaviour
*necessarily* was, independent of the missing sample.

## 3. Code-level audit — how the pipeline counted sources before this task

Read from `IntelX/intelx/api/live_research_task.py` at HEAD (`a5612c63`),
function `collect_live_brief` — the live brief pipeline behind the
persisted research runs:

1. **Retrieval.** Search returns up to 15 candidates (or explicit URLs in
   the query are fetched directly); at most `max_sources=5` documents are
   kept. De-duplication is by **exact URL string only** (`seen` set) — the
   same article at two URLs, or the same wire copy at ten outlets, counts
   as ten distinct sources.
2. **Findings.** Each kept document yields up to 3 extractive findings,
   and each finding is built with **exactly one citation** — the document
   it was extracted from. Extractive findings are therefore single-source
   by construction, and nothing in the result said so.
3. **Synthesis.** When a synthesis callback is configured, it received
   **all** retrieved documents uncollapsed (`synthesize(query,
   source_documents)` in pre-fix shape). Syndicated copies of one wire
   story were indistinguishable from independent corroboration, and a
   synthesised finding citing two of them looked doubly supported.
4. **Counting/flagging.** Nothing counted domains, nothing detected
   near-duplicates, nothing flagged single-source findings, and no
   diversity field existed on the result. The only source counts on the
   result were `len(sources)`-style totals.
5. **Dominance.** No per-domain cap existed: one domain could supply all
   5 documents in a run, and no record of the domain distribution was kept.

**Defect verdict: PROVEN at code level.** The pipeline could — and by
construction regularly would — present single-source, possibly
wire-echoed evidence with no diversity signal attached. A code fix was
warranted; it exists (§4).

## 4. The fix (implemented in the clone worktree, uncommitted)

New module `IntelX/intelx/api/source_diversity.py` (pure stdlib,
deterministic, no network), wired into `collect_live_brief` **before**
synthesis:

- **Near-duplicate clustering.** Retrieved documents are clustered by
  token-set Jaccard similarity of their full text; ≥ 0.80 = same
  underlying copy (wire syndication, mirrors, reprints). Each cluster
  collapses to **one** independent source (its first-retrieved member).
- **Synthesis input.** The synthesizer is handed only cluster
  representatives, so syndicated copies cannot masquerade as independent
  corroboration in the draft either.
- **Per-finding annotation.** Every final finding (extractive or
  synthesised) gains `independent_source_count` = the number of distinct
  clusters behind its citations, and `diversity_flag` =
  `single_source` when that count is < 2, else `multi_source`. Citations
  resolving to no retrieved document count as zero.
- **Run-level report.** The result gains a `source_diversity` object:
  `documents_retrieved`, `distinct_domains`, `independent_sources`,
  `collapsed_groups` (the wire-echo evidence, with member domains),
  `findings`, `single_source_findings`, `single_source_share`,
  `min_independent_sources_required` (= 2).

Honesty note: similarity is a lexical proxy for "same copy", not a
semantic judgement; the report records exactly which documents collapsed
together so the decision is auditable. (One wording correction by this
finisher: the module docstring originally credited an empirical audit of
persisted outputs that never completed; it now credits the code audit and
points here.)

## 5. Test evidence (this finisher's own run)

`IntelX/tests/test_source_diversity.py` — run 2026-11-15 by this crew with
its own minimal runner (package placeholders so the real modules load
without the web-app dependency chain; CI runs the same file against the
real package):

**7 passed in 0.31s** (pytest 9.2.0):

- `test_source_domain_strips_www_and_case`
- `test_text_similarity_identical_and_disjoint`
- `test_cluster_collapses_wire_copy_across_domains` — Reuters + Yahoo
  carrying the same wire text cluster together; a distinct article does not.
- `test_annotate_counts_clusters_not_citations` — two citations into one
  wire-copy cluster count as **1** independent source and flag
  `single_source`; citations across two clusters count as 2.
- `test_report_shape_and_share`
- `test_wire_copy_collapses_before_synthesis` (integration) — 3 retrieved
  documents on 3 domains reach the synthesizer as **2** documents;
  report: `independent_sources=2`, collapsed group domains
  {news.yahoo.com, reuters.com}; the synthesised finding is annotated
  `independent_source_count=1`, `diversity_flag=single_source`.
- `test_extractive_findings_are_flagged_too` (integration) — with no
  synthesis, `single_source_share == 1.0` and every extractive finding
  carries the flag: the §3 headline, surfaced on the result, not hidden.

## 6. Delivery state and what remains

Five states: **implemented YES** (worktree) · **tested YES** (§5) ·
**merged NO** · **deployed NO** · **production-verified NO**.

Blocking this crew from shipping it itself, stated plainly:

- The clone's git index is not writable from this sandbox
  (`index.lock` write error), so the worktree changes cannot be committed
  here; the branch was never pushed by the original crew either.
- This crew's bridge client is read-only: `github_create_pr`,
  `github_comment` (via `github_api`), and `github_write_file` are outside
  its allowlist, so it cannot open the PR, post the completion comment, or
  land the board entry.

Prepared for the coordinator / merge-runner in `~/workspace/int-004/`:
this audit (also copied to `IntelX/docs/SOURCE_DIVERSITY_AUDIT_INT004.md`
in the worktree), the data file (`diversity_audit_data.json`, also copied
to `IntelX/docs/source_diversity_audit_int004.json`), `pr_body.md`,
`board_entry.yaml`, and `completion_comment.md`. The PR should contain
exactly: `IntelX/intelx/api/source_diversity.py` (new),
`IntelX/intelx/api/live_research_task.py` (modified),
`IntelX/tests/test_source_diversity.py` (new), and the two docs files
above. Before posting the completion comment, dedupe the TASK-INT-004
claim on issue #35 (§1).

**Remaining work after merge:** (a) deploy + confirm a live brief result
carries `source_diversity` (production verification); (b) run the
preserved server-side analysis (`~/workspace/int-004/server_analyze.py`)
against persisted production runs to replace §2's UNVERIFIED with measured
figures; (c) consider a per-domain retrieval cap — the fix measures and
flags dominance but does not yet prevent one domain from supplying most
documents in a run.
