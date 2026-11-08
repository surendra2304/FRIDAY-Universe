# FRIDAY Universe — Handoff

Shared coordination and continuity document for Claude, ChatGPT, and Grok.
Older handoff: docs/FRIDAY_Universe_Engineering_Handoff.md (superseded by this file; kept for history).

## A. Active task registry
| TASK-ID | Task | Owner | Branch | Files claimed | Status |
|---|---|---|---|---|---|
| TASK-DOC-001 | Create the three central documents | Claude | claude/TASK-DOC-001 | docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md | IN_REVIEW (PR #21, blocked by red CI on main) |
| PHASE-0 | Phase 0 — owner actions executed by Claude (owner instructed: implement Phase 0 without asking ChatGPT) | Claude | main / claude/TASK-DOC-001 | docs/handoff.md, docs/MASTER_PLAN.md | IN_PROGRESS |
| TASK-OPS-002 | Verify OCI sniper authenticates (run 42497059156) | Claude | main (workflow dispatch) | .github/workflows/oracle-capacity-sniper.yml | IN_PROGRESS |
| TASK-CI-002 | Get main fully green | ChatGPT (claimed by activity; confirm) | main | CI workflows, tests | IN_PROGRESS |
| TASK-CORE-002 | Remove fabricated universe_orchestrator success | Grok | grok/TASK-CORE-002 | FRIDAY/src/friday/integrations/universe_orchestrator.py, FRIDAY/tests/test_universe_orchestrator_no_fake_dispatch.py, docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md | IN_REVIEW |

## B. Completed tasks
(none verified yet under the DONE definition)

Recent work on main (not yet claimed under a TASK-ID, recorded for history):
- 28bd5e6 docs: master plan v2 — Claude. Verified infrastructure, routing, safety. Coverage stated.
- dd1ff29 ci: move Oracle sniper workflows to repo root — Claude. Needed because GitHub runs only root workflows.
- cf92fa9, a971e2c, d501148, 369995e — CI fixes (mock Oracle DB URL, isolate VyralX tests, Memora tmp_path, fastapi in validate-monorepo) — ChatGPT. Merge c097312 completes PR #19. Tests executed: not recorded here; ChatGPT to record.

## C. Current work
- PHASE 0 STARTED (Claude, 2026-11-08 ~16:05 UTC), per owner instruction. Steps:
  1. OCI secrets present in repo (names verified via API). Values unverified.
  2. Sniper check: run 42497059156 on main (c097312) dispatched 15:53 UTC; step "Run Infinite 24/7 Sniper" still running at 16:05. No failure. Authentication not yet confirmed; logs not readable until the job ends. Live log: https://github.com/surendra2304/FRIDAY-Universe/actions/runs/42497059156
  3. History rewrite (leaked keys from commit 46034a4): DEFERRED until PRs #20 and #21 are resolved, because a rewrite changes every commit ID on main and would invalidate both PR bases. Owner approved the rewrite. Note: ChatGPT's own rules say "never force-push main"; the owner's explicit approval is the exception and is recorded here.
- CI on main is RED. Root cause for the docs PR check "Validate fleet layout and mirror safety": 37 failed, 43 errors in tests (missing sqlalchemy and pydantic_settings in the CI install step; NameError 'sys' in tests/test_real_deep_layer11.py). This is a pre-existing defect on main, not caused by PR #21.
- PR #20 still open and red (see its comment); not merged.
- Claude: TASK-DOC-001 (this document set). TASK-OPS-002: sniper run 42497059156 dispatched on main at c097312 at 15:53 UTC; in progress; its API step is running, log not yet readable. Owner can watch it at https://github.com/surendra2304/FRIDAY-Universe/actions/runs/42497059156
- ChatGPT: CI fixes on main (see B).

## D. Blocked tasks
| Blocker | Cause | Required action | Responsible |
|---|---|---|---|
| Merging PR #20 and PR #21 | Required check "Validate fleet layout and mirror safety" fails on main too | Fix test dependencies in CI install step and missing sys import; re-run | Claude (Phase 0 scope: CI on main is on the critical path) — ChatGPT to tell Claude if it has already started this |
| Full main CI green | Same as above | Same | Same |
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
- 2026-11-08: The UniverseOrchestrator live path returned a fixed success message without calling peers. Treated as a defect (TASK-CORE-002). Grok, same day: branch grok/TASK-CORE-002 makes that path call get_fleet_summary and return status not_executed. Tests: 5 passed (2 new + 3 existing in test_universe_phase20_21.py) via venv pytest on Server 2. Not merged. Not deployed. Claude's uncommitted TASK-CI-002 edits were stashed as "WIP preserved from claude/TASK-CI-002 before grok/TASK-CORE-002 (do not drop)" and should be restored onto claude/TASK-CI-002.
- 2026-11-08: Keyword routing in dispatch_directive misroutes common words. Treated as a defect (TASK-ORCH-001).
- 2026-11-08: Stratex and other agents stay on their current servers. Owner decision.
- 2026-11-08: Sniper retry loop speed-up (15 s cycle, 45 s backoff) is a trade-off: fewer waits, possibly more 429 throttles. Review after several hours of logs.

## G. Latest handoff checkpoint
- Last completed TASK-ID: none verified under DONE.
- Current IN_PROGRESS / IN_REVIEW TASK-IDs: TASK-OPS-002 (Claude), TASK-CI-002 (ChatGPT, to confirm), TASK-CORE-002 (Grok, IN_REVIEW).
- Last modified files (this branch): docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md.
- Latest branch and PR: claude/TASK-DOC-001 (PR to be opened).
- Tests and results: no new tests this session. Last CI run on the earlier PR head failed; main head c097312 result UNVERIFIED.
- Outstanding issues: sniper authentication unconfirmed; FRIDAY-Voice memory limit; bridge has no auth (owner accepted); history rewrite pending.
- Exact next action: (1) read sniper run 42497059156 when it ends; (2) fix the CI install step and the sys import on a branch claude/TASK-CI-FIX-001 and open a PR; (3) after main is green, merge PRs #21 and #20 with the comment 'Merged by Claude after reviewing'; (4) run the history rewrite and record the commit IDs here.
