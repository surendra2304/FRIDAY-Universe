# TASK-FRG-028 — Forge repos wave 3: Karpathy Skill / Graphify / Open Code Review / ECC

- **Task:** TASK-FRG-028 (P2) — REPO-IMPLEMENT Forge repos wave 3, target Forge.
- **Claim:** hub #1483 comment 7163453612 (2026-11-25 ~18:42 IST).
- **Branch:** `muse2/task-frg-028-forge-repos-wave3` (from current main; see §7).
- **Work PR:** (number added by the board-flip commit — see §7).
- **Five states:** implemented YES / tested YES (repo CI) / merged NO /
  deployed NO / production-verified NO.

## 1. Verdicts

| Repo | Verdict | What it means here |
|---|---|---|
| Karpathy Skill | **ADOPT** | Four principles (`Forge/forge_upgrade/coding_principles.py`, TASK-IG2-FRG-01, distilled from multica-ai/andrej-karpathy-skills, MIT declared in its README/manifests) now gate a real build run: `preflight` refuses a task with no assumptions/criteria, `guidance_block` renders into the run context, `scope_check` fail-closes the review. |
| Graphify | **ADOPT** | Graphify-Labs/graphify, Apache-2.0, CLI 0.9.119 (`Forge/forge_upgrade/code_graph.py`, TASK-IG2-FRG-02) now runs inside a build run's understand stage, with the `links` loader fix (§3). |
| Open Code Review | **ADOPT** | alibaba/open-code-review, Apache-2.0, CLI v1.14.3 (`Forge/forge_upgrade/ocr_review.py`, TASK-IG2-FRG-03) now runs inside a build run's review stage, with the real CLI shape (§3). |
| ECC — Everything Claude Code | **ADAPT** | affaan-m/ECC, MIT, OSS core only; pattern adoption, not a port (`Forge/app/harness/ecc_patterns.py`, TASK-IG2-FRG-05). The fixed pipeline, verification hooks, AgentShield-style config scan and Instincts now drive a build run. ECC Pro (paid hosted app) is out of scope under the FREE-only rule. |

## 2. What was built

`Forge/forge_upgrade/build_run.py` (new, +424) — `ForgeBuildRun`: one
end-to-end build run through `ForgeController`'s DAG, wiring all four
adopted components into their stage:

- **plan** — Karpathy `preflight` (refuses a task with no assumptions or no
  verifiable success criteria) + `guidance_block` into the run context;
  ECC `scan_agent_config` over the build config — a critical/high shield
  finding blocks the run before any code.
- **understand** — Graphify `build_graph` over the target subfolder and
  `CodeGraph` query/path over the produced graph (advisory: an unavailable
  CLI is recorded honestly, never faked).
- **implement** — the caller-supplied build steps, tracked file by file.
- **review** — Karpathy `scope_check` against the declared scope
  (fail-closed) + OCR delegate pass over the changed files; the OCR result
  is attached with `supplement_review` and can never change the gate verdict.
- **test / verify** — the declared test command runs for real; its result is
  recorded as ECC test evidence and the ECC `stage_gate` refuses to leave
  `verify` without passing evidence.
- **remember / deliver** — the outcome is observed into an ECC
  `InstinctStore` and the run summary is delivered.

Bar (FRG-10 supervisor bar): a module counts as wired only when a production
caller imports and calls it, with a test that exercises it THROUGH that
caller. The production caller here is `ForgeBuildRun` driving
`ForgeController`'s DAG — the 15 tests in `test_frg028_build_run.py` run a
real build task (write a module + its test, run pytest for real, review the
diff) through the run and read the evidence out of the report.

## 3. The two wiring-bug fixes (verified live, prior session)

- **Graphify emits edges under `links`, not `edges`.** A 31-file live run
  (graphify 0.9.119, 2026-11-25) wrote 395 nodes and 695 links, zero
  `edges`; the old loader silently read 0 edges, so `path` and `explain`
  always returned nothing on a real current graph. Fix
  (`code_graph.py`): `CodeGraph.load` accepts both keys, preferring
  `edges` when present so an explicit edge list is never shadowed.
- **OCR delegation is a subcommand, not a flag.** Verified live against ocr
  v1.14.3 (2026-11-25): `ocr delegate preview` lists reviewable files and
  `ocr delegate rule <files>` prints the resolved ruleset, both with no LLM
  and no provider configured. `ocr review` takes `--from` (not `--base`),
  takes no `--file` and no `--delegate` flag, and needs a configured LLM
  provider — so it is opt-in only (`provider_review=True`) and never runs
  by default. The wave-2 command builder
  (`ocr review --base main --format json --delegate --file ...`) matched
  no shipped CLI flag and would have failed on every invocation; it is
  replaced here (`ocr_review.py`, `build_ocr_command` removed — it had no
  other caller in the repo).

## 4. Guardrail proof of absence (GitHub code search, main, 2026-11-25)

Before this PR, none of the four components had a production caller:

- `coding_principles`: only `Forge/AGENT_GUIDELINES.md`, the INT-044
  tracker doc, and its own test — no production import.
- `CodeGraph`: only the module, `Forge/docs/CODE_GRAPH.md`, and its own test.
- `run_ocr_review`: only the module, `Forge/docs/OCR_REVIEW.md`, and its
  own test.
- `ecc_patterns`: only `Forge/app/harness/__init__.py` (re-export),
  `Forge/docs/IG2_EVALUATION_NOTES.md`, the INT-044 tracker, and its own test.
- `build_ocr_command`: only the module itself and its own test (both changed
  here) — the rename breaks nothing else.
- `test_plan_guard.py`'s `build_graph` is a local helper defined in that
  file, unrelated to Forge's `code_graph.build_graph`; the three
  `build_graph` hits in Inference/Memora are different functions in other
  agents.

## 5. Tests — 39 across 3 files, all registered in CI

| File | Tests | Change |
|---|---|---|
| `Forge/tests/test_frg028_build_run.py` (new) | 15 | Happy path through all four components; graphify/ocr unavailable recorded, not faked; failure cases: preflight refusal, shield block (pipe_to_shell + hardcoded secret), scope failure, failing tests, step exception, no steps, no test command; instinct recording; report shape. |
| `Forge/tests/test_ig2_frg02_code_graph.py` | 10 (8 + 2 new) | New: `links` graph loads with edges, `edges` preferred when both present. |
| `Forge/tests/test_ig2_frg03_ocr_review.py` | 14 (7 + 7 new) | New: delegate-rule/preview/review command shapes pinned to the real CLI; delegate pass as the default; delegate failure; provider path findings + unparseable output. |

All three files are registered in the Forge tier-1 step ("Generated-code
ingestion and saved verification status", `PYTHONPATH: Forge`) in
`.github/workflows/owner-workflows.yml`. This also fixes a REL-068 gap found
while preparing this PR: the two `test_ig2_*` files were collected by NO
PR-triggered workflow (all 27 workflow files scanned) — the contracts
guard (`scripts/ci_test_collection_audit.py`) would have failed this PR on
them unregistered.

## 6. Live-CLI proof (prior session — honesty bound)

`/tmp/frg028-proof-out.txt`, produced by the prior (timed-out) session
running the real CLIs locally on this VM:

- **Happy path:** build run `frg028-live-proof` completed (stage improve):
  graphify built a graph for 32 files; implement 1 step, 3 files changed;
  OCR delegate pass fetched rules for 3 files (1 rule group), no LLM
  judgement run, no findings; preflight OK; review verdict PASS (OCR
  changed gate: False); scope OK; shield scan clean; tests exit 0;
  verify gate passed.
- **Failure case 1 — no assumptions:** preflight refused, run blocked at
  plan, no code written.
- **Failure case 2 — failing tests:** test command exit 1
  (`greet('forge')` returned 42, not `'hello, forge'`); verify gate
  failed the run.
- **Failure case 3 — dangerous hook:** `curl … | sudo sh` in the build
  config's `hooks.pre` — shield scan blocked the run at plan
  (`pipe_to_shell`, critical).

Honesty bound: this proof is a LOCAL run by the prior session, not repo CI
and not the live fleet. Repo CI is the verification for this PR; live-fleet
execution is owed after Muse's clearance (§8).

## 7. Resume note

The 18:37 self-check implementation session hit the 3600s timeout with the
work stranded as 6 uncommitted files in the flagged local clone (no remote
branch, no work PR, no board edits). This session recovered the 6 files
read-only (identified by mtime window, each modified file diffed against
main via the API to confirm the exact change), rebuilt the PR API-only — no
local git operations on the flagged clone, no local pytest, no local
execution/import of fetched code — and re-verified every depended-on API by
reading main (ECC stage order, `ForgeController`/`DagScheduler`,
`PlanGuard`, `coding_principles`, `code_graph`, `ocr_review`,
`ecc_patterns`). The branch was created fresh from current main, so no
merge-in was needed (the stall notice's anticipated merge-in does not apply).
Board flip rides in this PR (rule 4): FRG-028 → IN_REVIEW. INF-039 was
already MERGED on main (verified first-hand) and is kept byte-identical.

## 8. Still owed

- Peer merge of this work PR (never merge own PR).
- Deploy + live proof after Muse's clearance: one real build task for
  another agent executed end-to-end through the deployed Forge, with its
  output actually used by that agent in production (board acceptance),
  plus a failure case. Fleet CD is broken (WATCH098: S1 dirty, S2 perms) —
  deploy also waits on the CD repair. The owner stop order on live dispatch
  runs is still in force; no deploy, restart, or live-fleet writes were done
  in this PR.
