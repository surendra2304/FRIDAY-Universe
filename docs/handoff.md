# FRIDAY Universe — Handoff

Shared coordination and continuity document for Claude, ChatGPT, and Grok.
Older handoff: docs/FRIDAY_Universe_Engineering_Handoff.md (superseded by this file; kept for history).

## A. Active task registry
| TASK-ID | Task | Owner | Branch | Files claimed | Status |
|---|---|---|---|---|---|
| TASK-DOC-001 | Create the three central documents | Claude | claude/TASK-DOC-001 | docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md | MERGED (PR #21, 2026-11-08; commit 515858e) |
| PHASE-0 | Phase 0 — owner actions executed by Claude (owner instructed: implement Phase 0 without asking ChatGPT) | Claude | main / claude/TASK-DOC-001 | docs/handoff.md, docs/MASTER_PLAN.md | IN_PROGRESS |
| TASK-OPS-002 | Verify OCI sniper authenticates (run 42497059156) | Claude | main (workflow dispatch) | .github/workflows/oracle-capacity-sniper.yml | IN_PROGRESS |
| TASK-CI-002 | Get main fully green | Claude | claude/TASK-CI-002 | CI workflows/tests | IN_PROGRESS; fixes landed on main through PR #22 and commits f24ff91/680c04e, but full suite/main validation remains unresolved |
| TASK-CORE-002 | Remove fabricated universe_orchestrator success | Grok | grok/TASK-CORE-002 | FRIDAY/src/friday/integrations/universe_orchestrator.py and regression tests | MERGED to main via PR #25 (commit 79c1f75); code test evidence 5 passed on Server 2; production verification outstanding |
| TASK-SEC-004 | Secret-management audit and CI leak prevention | ChatGPT | chatgpt/TASK-SEC-004 | .github/workflows/secret-scan.yml | IN_REVIEW (PR #31); change-range Gitleaks scan passed run 42525462164; not merged / not yet verified on main |

## B. Merged implementation work (not equivalent to production VERIFIED/DONE)
- TASK-DOC-001: PR #21 merged at 515858e.
- TASK-CORE-002: PR #25 merged at 79c1f75; stops the false `dispatched` claim and reports `not_executed` after a live fleet probe when no Universe API exists. The goal is still not executed on that path.
- CI baseline: PR #22 merged at 0a2eeb4; subsequent main commits f24ff91 and 680c04e add missing test dependencies and the `sys` import in mesh/memory_fabric.py. Full validation still not green.
- TASK-SEC-004: PR #31 adds `.github/workflows/secret-scan.yml`. Gitleaks action run 42525352655 failed because shallow checkout did not contain event base/head refs. The workflow was changed to `fetch-depth: 0` and scans the event change range only; run 42525462164 passed. This does not scan/clean historical commit 46034a4.

Recent work on main (not yet claimed under a TASK-ID, recorded for history):
- 28bd5e6 docs: master plan v2 — Claude. Verified infrastructure, routing, safety. Coverage stated.
- dd1ff29 ci: move Oracle sniper workflows to repo root — Claude. Needed because GitHub runs only root workflows.
- cf92fa9, a971e2c, d501148, 369995e — CI fixes (mock Oracle DB URL, isolate VyralX tests, Memora tmp_path, fastapi in validate-monorepo) — ChatGPT. Merge c097312 completes PR #19. Tests executed: not recorded here; ChatGPT to record.

## C. Current work (GitHub state checked 2026-11-09; no live VM/connector runtime inspected in this session)
- PHASE 0 STARTED (Claude, 2026-11-08 ~16:05 UTC), per owner instruction. Steps:
  1. OCI secrets present in repo (names verified via API). Values unverified.
  2. Sniper check: run 42497059156 on main (c097312) dispatched 15:53 UTC; step "Run Infinite 24/7 Sniper" still running at 16:05. No failure. Authentication not yet confirmed; logs not readable until the job ends. Live log: https://github.com/surendra2304/FRIDAY-Universe/actions/runs/42497059156
  3. History rewrite (leaked keys from commit 46034a4): DEFERRED until PRs #20 and #21 are resolved, because a rewrite changes every commit ID on main and would invalidate both PR bases. Owner approved the rewrite. Note: ChatGPT's own rules say "never force-push main"; the owner's explicit approval is the exception and is recorded here.
- CI on main is RED. Root cause for the docs PR check "Validate fleet layout and mirror safety": 37 failed, 43 errors in tests (missing sqlalchemy and pydantic_settings in the CI install step; NameError 'sys' in tests/test_real_deep_layer11.py). This is a pre-existing defect on main, not caused by PR #21.
- PR #20 merged via commit 94fed85 (2026-11-08). PR #21 merged via commit 515858e.
- Claude currently owns TASK-CI-002, TASK-API-001 (PR #29), TASK-DISPATCH-001 (PR #28), TASK-MIRROR-001 (PR #27), and TASK-OPS-002 per existing coordination notes.
- ChatGPT currently owns TASK-SEC-003 (PR #24), TASK-CTX-001 (PR #26), and TASK-SEC-004 (PR #31). PR #24/#26 require review findings below to be resolved before merge.
- Grok's TASK-CORE-002 implementation was merged through PR #25.
- Current `main` HEAD observed via GitHub: `680c04ee383066874cad42a3295d18008eb6e1d2` (2026-11-08T19:34:57Z).

## D. Blocked tasks
| Blocker | Cause | Required action | Responsible |
|---|---|---|---|
| TASK-CI-002 / required validation | Last documented full validation had 38 failed and 43 errors (run 42502800827); later fixes are on main but no fresh green full-suite evidence found in this review | Re-run current main validation; fix genuine integration/test failures without skips, xfails or weakened assertions | Claude |
| PR #28 dispatch review | Codex identified payload priority type mismatch, missing peer-specific auth headers, unsupported/missing endpoints for Forge/Futuris/Sentinel, inaccurate receipt handling of DEGRADED/ERROR and Stratex false-success on unsupported actions. ChatGPT posted detailed review comment 2026-11-09. | Resolve each contract finding with per-peer regression tests before merge | Claude (PR author) |
| Sniper secrets might be wrong | OCI_KEY_CONTENT PEM is not in CREDENTIALS.md (only user OCID, tenancy OCID and fingerprint are) | Confirm the PEM was pasted into OCI_KEY_CONTENT, and that OCI_KEY_CONTENT_2 has the second key's PEM | Owner |
| History rewrite | Destructive; invalidates open branch bases | Coordinate timing with ChatGPT; run after open PRs merge | Claude (owner approved) |
| PR #26 Cortex auth | Codex identified that method-only POST=>operator blocks viewer read-only forecast endpoint; ChatGPT posted a route-capability review comment 2026-11-09. | Separate read/analysis capability from state mutation and add viewer regression test | ChatGPT (PR author) |

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
- 2026-11-08: TASK-CORE-002: Grok's fix merged via PR #25 (commit 79c1f75). Tests reported 5 passed via venv pytest on Server 2. Deployment/runtime behavior not verified in this session.
- 2026-11-08: Keyword routing in dispatch_directive misroutes common words. Treated as a defect (TASK-ORCH-001).
- 2026-11-08: Stratex and other agents stay on their current servers. Owner decision.
- 2026-11-08: Sniper retry loop speed-up (15 s cycle, 45 s backoff) is a trade-off: fewer waits, possibly more 429 throttles. Review after several hours of logs.

## G. Latest handoff checkpoint (ChatGPT reconnect, 2026-11-09)
- Last implementation merged: TASK-CORE-002 (PR #25, 79c1f75). No production task is claimed DONE/VERIFIED based only on this connector inspection.
- Main HEAD: `680c04ee383066874cad42a3295d18008eb6e1d2`.
- Open PRs observed: #23 (CI), #24 (bridge auth), #26 (Cortex route auth), #27 (manual/no-force mirror), #28 (dispatch bus), #29 (Sentinel task endpoint), #30 (central docs sync), #31 (Gitleaks change-range scan).
- ChatGPT review comments posted 2026-11-09: #23 TASK-ID collision/full-suite concern; #26 read-only POST forecast viewer access; #28 peer contract/endpoint/receipt/fake-success blockers.
- CI evidence: run 42502800827 reported 3,286 passed, 74 skipped, 38 failed, 43 errors. This is historical evidence from PR #24's run, not a result for current HEAD. Current main's full validation remains UNVERIFIED in this session.
- ChatGPT docs synchronization branch: `chatgpt/TASK-DOC-SYNC-001`; PR #30 updates the three central docs. This update adds TASK-SEC-004 state; PR #30 remains open and docs-only.
- Live system bridge checked 2026-11-09: workspace on Server 2 is branch `claude/TASK-DISPATCH-001`, commit `f09e29f`, with one untracked file `Forge/tests/unit/test_task_execute_contract.py`; this work was preserved and not edited. Both Oracle VMs were online. Server 1: 956 MB RAM, 464 MB used, 337 MB available, 97 GB disk 22%; Server 2: 956 MB RAM, 265 MB used, 538 MB available, 49 GB disk 36%. These are point-in-time read-only diagnostics.
- TASK-SEC-004 PR #31: Gitleaks run 42525462164 PASS after initial run 42525352655 failed due shallow-fetch range resolution. Current action scans PR/push change ranges only, not entire history. It must pass CI and merge before TASK-SEC-004 can be VERIFIED.
- Tests: Forge targeted workspace test command was attempted on Server 2 but stopped in `Forge/tests/conftest.py` because the venv lacks installed `anthropic` (`ModuleNotFoundError`); the new Forge contract test was not executed. The dependency is listed in `Forge/requirements.txt`. No test was skipped or weakened.
- Outstanding external actions: TASK-OPS-002 sniper OCI authentication needs current workflow log verification; owner-reported credential rotation and approved history rewrite still need safe timing after open PRs settle; infrastructure and FRIDAY-Voice resource limits require authorized host access.
- Exact next steps: (1) confirm all PR #31 CI jobs finish and review scanner policy; (2) keep PR #30 central docs aligned with accepted/merged work; (3) Claude resolves PR #28 dispatch findings and continues CI/Forge/Sentinel API work; (4) ChatGPT resolves PR #26 and #24 review findings; (5) pursue remaining owner actions and continue TASK-CORE-001 / data foundation audits without changing live services.
