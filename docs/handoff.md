# FRIDAY Universe — Handoff

Shared coordination and continuity document for Claude and ChatGPT.
Older handoff: docs/FRIDAY_Universe_Engineering_Handoff.md (superseded by this file; kept for history).

## A. Active task registry
| TASK-ID | Task | Owner | Branch | Files claimed | Status |
|---|---|---|---|---|---|
| TASK-DOC-001 | Create the three central documents | Claude | claude/TASK-DOC-001 | docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md | IN_REVIEW |
| TASK-OPS-002 | Verify OCI sniper authenticates (run 42497059156) | Claude | main (workflow dispatch) | .github/workflows/oracle-capacity-sniper.yml | IN_PROGRESS |
| TASK-CI-002 | Get main fully green | ChatGPT (claimed by activity; confirm) | main | CI workflows, tests | IN_PROGRESS |

## B. Completed tasks
(none verified yet under the DONE definition)

Recent work on main (not yet claimed under a TASK-ID, recorded for history):
- 28bd5e6 docs: master plan v2 — Claude. Verified infrastructure, routing, safety. Coverage stated.
- dd1ff29 ci: move Oracle sniper workflows to repo root — Claude. Needed because GitHub runs only root workflows.
- cf92fa9, a971e2c, d501148, 369995e — CI fixes (mock Oracle DB URL, isolate VyralX tests, Memora tmp_path, fastapi in validate-monorepo) — ChatGPT. Merge c097312 completes PR #19. Tests executed: not recorded here; ChatGPT to record.

## C. Current work
- Claude: TASK-DOC-001 (this document set). TASK-OPS-002: sniper run 42497059156 dispatched on main at c097312 at 15:53 UTC; in progress; its API step is running, log not yet readable. Owner can watch it at https://github.com/surendra2304/FRIDAY-Universe/actions/runs/42497059156
- ChatGPT: CI fixes on main (see B).

## D. Blocked tasks
| Blocker | Cause | Required action | Responsible |
|---|---|---|---|
| Sniper secrets might be wrong | OCI_KEY_CONTENT PEM is not in CREDENTIALS.md (only user OCID, tenancy OCID and fingerprint are) | Confirm the PEM was pasted into OCI_KEY_CONTENT, and that OCI_KEY_CONTENT_2 has the second key's PEM | Owner |
| History rewrite | Destructive; invalidates open branch bases | Coordinate timing with ChatGPT; run after open PRs merge | Claude (owner approved) |
| FRIDAY-Voice no memory limit | Not yet changed | Set MemoryMax | Claude (TASK-INF-002) |

## E. Next tasks (in roadmap order)
1. TASK-OPS-002 — confirm the sniper authenticates. Claude to read the run log when complete, or owner checks the live page.
2. TASK-INF-001 — infrastructure audit (Claude).
3. TASK-INF-002 — FRIDAY-Voice memory limit (Claude).
4. TASK-CI-002 — main green (ChatGPT confirms ownership).
5. TASK-CORE-001 — per-agent audit, starting with FRIDAY (Claude), in parallel with ChatGPT on a different agent.

## F. Shared decisions
- 2026-11-08: Both AIs work top to bottom through MASTER_PLAN.md. No bottom-up ownership split. (Owner decision.)
- 2026-11-08: Sniper workflows live at repo root only. Subfolder copies are not run by GitHub.
- 2026-11-08: Stratex trades on Binance testnet only. Owner confirmed. Code defaults to testnet (BINANCE_TESTNET default "true"); the effective value on the running units is UNVERIFIED.
- 2026-11-08: The UniverseOrchestrator live path returns a fixed success message without calling peers. Treated as a defect (TASK-CORE-002).
- 2026-11-08: Keyword routing in dispatch_directive misroutes common words. Treated as a defect (TASK-ORCH-001).
- 2026-11-08: Stratex and other agents stay on their current servers. Owner decision.
- 2026-11-08: Sniper retry loop speed-up (15 s cycle, 45 s backoff) is a trade-off: fewer waits, possibly more 429 throttles. Review after several hours of logs.

## G. Latest handoff checkpoint
- Last completed TASK-ID: none verified under DONE.
- Current IN_PROGRESS TASK-IDs: TASK-OPS-002 (Claude), TASK-CI-002 (ChatGPT, to confirm).
- Last modified files (this branch): docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md.
- Latest branch and PR: claude/TASK-DOC-001 (PR to be opened).
- Tests and results: no new tests this session. Last CI run on the earlier PR head failed; main head c097312 result UNVERIFIED.
- Outstanding issues: sniper authentication unconfirmed; FRIDAY-Voice memory limit; bridge has no auth (owner accepted); history rewrite pending.
- Exact next action: open the PR for claude/TASK-DOC-001; then read the sniper run log when it completes.
