# FRIDAY Universe — Handoff

Shared coordination and continuity document for the project owner and all human/AI collaborators (Claude, ChatGPT, Grok, ZAI, Vercel v0 and future contributors).
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
| TASK-INT-001 | IntelX evidence pipeline and Oracle persistence audit | ChatGPT | chatgpt/TASK-INT-001-intelx-json | IntelX/intelx/oracle_dialect_compat.py, IntelX/intelx/db/engine.py, tests/test_intelx_oracle_json_compat.py | IN_REVIEW (PR #32); FRIDAY CI passed, monorepo validation still fails on broader repository issues; no deployment |
| TASK-FUT-001 | Prevent fabricated Stratex positions/funding telemetry | ChatGPT | chatgpt/TASK-FUT-001-stratex-telemetry | Futuris connector, risk router and regression tests | IN_REVIEW (PR #33); FRIDAY CI passed, monorepo validation failed during collection because root validation lacks NumPy; no deployment |
| TASK-MEM-001 | Memora Oracle vector tenant and transaction integrity | ChatGPT | chatgpt/TASK-MEM-001-memora-oracle-vector-audit | Memora Oracle vector adapter, regression tests, root and nested CI workflows, package/config docs | IN_REVIEW (PR #37); focused vector suite 8 passed/1 warning (run 42596147391); full FRIDAY CI passed (run 42596147378); live Oracle/Qdrant unverified |
| TASK-CI-004 | Root-cause fixes for fleet CI failures | Claude | claude/TASK-CI-004 | validate-monorepo.yml, dispatch bus, Forge optimizers, tests/conftest.py, e2e tests | IN_REVIEW (PR #34); FRIDAY CI and image build passed; both monorepo validators failed |
| TASK-COLLAB-001 | Shared multi-AI collaboration centre | ChatGPT | chatgpt/TASK-DOC-SYNC-001 | docs/collaboration/* and three central documents | IN_REVIEW (PR #30); GitHub claim hub issue #35 created; records are a snapshot and require review/merge |

## B. Merged implementation work (not equivalent to production VERIFIED/DONE)
- TASK-DOC-001: PR #21 merged at 515858e.
- TASK-CORE-002: PR #25 merged at 79c1f75; stops the false `dispatched` claim and reports `not_executed` after a live fleet probe when no Universe API exists. The goal is still not executed on that path.
- CI baseline: PR #22 merged at 0a2eeb4; subsequent main commits f24ff91 and 680c04e add missing test dependencies and the `sys` import in mesh/memory_fabric.py. Full validation still not green.
- TASK-SEC-004: PR #31 adds `.github/workflows/secret-scan.yml`. Gitleaks action run 42525352655 failed because shallow checkout did not contain event base/head refs. The workflow was changed to `fetch-depth: 0` and scans the event change range only; run 42525462164 passed. This does not scan/clean historical commit 46034a4.

Recent work on main (not yet claimed under a TASK-ID, recorded for history):
- 28bd5e6 docs: master plan v2 — Claude. Verified infrastructure, routing, safety. Coverage stated.
- dd1ff29 ci: move Oracle sniper workflows to repo root — Claude. Needed because GitHub runs only root workflows.
- cf92fa9, a971e2c, d501148, 369995e — CI fixes (mock Oracle DB URL, isolate VyralX tests, Memora tmp_path, fastapi in validate-monorepo) — ChatGPT. Merge c097312 completes PR #19. Tests executed: not recorded here; ChatGPT to record.

## C. Current work (GitHub and read-only live VM state checked 2026-11-09)
- PHASE 0 STARTED (Claude, 2026-11-08 ~16:05 UTC), per owner instruction. Steps:
  1. OCI secrets present in repo (names verified via API). Values unverified.
  2. Sniper check: run 42497059156 on main (c097312) dispatched 15:53 UTC; step "Run Infinite 24/7 Sniper" still running at 16:05. No failure. Authentication not yet confirmed; logs not readable until the job ends. Live log: https://github.com/surendra2304/FRIDAY-Universe/actions/runs/42497059156
  3. History rewrite (leaked keys from commit 46034a4): DEFERRED until PRs #20 and #21 are resolved, because a rewrite changes every commit ID on main and would invalidate both PR bases. Owner approved the rewrite. Note: ChatGPT's own rules say "never force-push main"; the owner's explicit approval is the exception and is recorded here.
- CI on main is RED. Root cause for the docs PR check "Validate fleet layout and mirror safety": 37 failed, 43 errors in tests (missing sqlalchemy and pydantic_settings in the CI install step; NameError 'sys' in tests/test_real_deep_layer11.py). This is a pre-existing defect on main, not caused by PR #21.
- PR #20 merged via commit 94fed85 (2026-11-08). PR #21 merged via commit 515858e.
- Claude currently owns TASK-CI-002, TASK-API-001 (PR #29), TASK-DISPATCH-001 (PR #28), TASK-MIRROR-001 (PR #27), and TASK-OPS-002 per existing coordination notes.
- ChatGPT currently owns TASK-SEC-003 (PR #24), TASK-CTX-001 (PR #26), TASK-SEC-004 (PR #31), and the IntelX audit slice TASK-INT-001 (PR #32). PR #24/#26 still require review findings below to be resolved before merge.
- Grok's TASK-CORE-002 implementation was merged through PR #25.
- Current `main` HEAD observed via GitHub: `680c04ee383066874cad42a3295d18008eb6e1d2` (2026-11-08T19:34:57Z); active PR branches are ahead of main and remain unmerged.
- TASK-INF-002 verified read-only: FRIDAY-Voice.service active on Server 1; systemd drop-in `memory.conf` loaded, MemoryHigh=250M and MemoryMax=300M; service used 7.4M at check time. This corrects the stale architecture gap. No restart or configuration change was made.

## D. Blocked tasks
| Blocker | Cause | Required action | Responsible |
|---|---|---|---|
| TASK-CI-002 / required validation | Last documented full validation had 38 failed and 43 errors (run 42502800827); later fixes are on main but no fresh green full-suite evidence found in this review | Re-run current main validation; fix genuine integration/test failures without skips, xfails or weakened assertions | Claude |
| PR #28 dispatch review | Codex identified payload priority type mismatch, missing peer-specific auth headers, unsupported/missing endpoints for Forge/Futuris/Sentinel, inaccurate receipt handling of DEGRADED/ERROR and Stratex false-success on unsupported actions. ChatGPT posted detailed review comment 2026-11-09. | Resolve each contract finding with per-peer regression tests before merge | Claude (PR author) |
| Sniper secrets might be wrong | OCI_KEY_CONTENT PEM is not in CREDENTIALS.md (only user OCID, tenancy OCID and fingerprint are) | Confirm the PEM was pasted into OCI_KEY_CONTENT, and that OCI_KEY_CONTENT_2 has the second key's PEM | Owner |
| History rewrite | Destructive; invalidates open branch bases | Coordinate timing with ChatGPT; run after open PRs merge | Claude (owner approved) |
| PR #26 Cortex auth | Codex identified that method-only POST=>operator blocks viewer read-only forecast endpoint; ChatGPT posted a route-capability review comment 2026-11-09. | Separate read/analysis capability from state mutation and add viewer regression test | ChatGPT (PR author) |

## E. Next tasks (dependency- and ownership-aware)
1. TASK-CI-002 — Claude gets the full main validation green without weakening tests.
2. PR #28 / #29 — Claude resolves dispatch contract blockers and completes Forge/Sentinel task-route capability.
3. TASK-INT-001 / PR #32 — ChatGPT finishes IntelX Oracle JSON fix and root-suite regression after latest CI run; production behavior requires a later deployment and live DB verification.
4. PR #26 / #24 — ChatGPT resolves Cortex viewer read-only POST authorization and bridge auth compatibility/activation requirements.
5. TASK-OPS-002 — Claude confirms OCI sniper credentials authenticate from current run logs; still in progress.
6. Continue per-agent TASK-CORE-001 audit split (Claude FRIDAY, ChatGPT IntelX), then data foundation tasks.

## F. Shared decisions
- 2026-11-08: Both AIs work top to bottom through MASTER_PLAN.md. No bottom-up ownership split. (Owner decision.)
- 2026-11-08: Sniper workflows live at repo root only. Subfolder copies are not run by GitHub.
- 2026-11-08: Stratex trades on Binance testnet only. Owner confirmed. Code defaults to testnet (BINANCE_TESTNET default "true"); the effective value on the running units is UNVERIFIED.
- 2026-11-08: TASK-CORE-002: Grok's fix merged via PR #25 (commit 79c1f75). Tests reported 5 passed via venv pytest on Server 2. Deployment/runtime behavior not verified in this session.
- 2026-11-08: Keyword routing in dispatch_directive misroutes common words. Treated as a defect (TASK-ORCH-001).
- 2026-11-08: Stratex and other agents stay on their current servers. Owner decision.
- 2026-11-08: Sniper retry loop speed-up (15 s cycle, 45 s backoff) is a trade-off: fewer waits, possibly more 429 throttles. Review after several hours of logs.
- 2026-11-09: TASK-INF-002 systemd cap verified: FRIDAY-Voice.service has MemoryHigh=250M and MemoryMax=300M. The older architecture statement that it had no MemoryMax is stale.
- 2026-11-09: IntelX Oracle issue observed in live logs at 2026-11-08 20:22:08 UTC: SQLAlchemy `OracleDialectAsync_oracledb` missing `_json_deserializer` during result processing. Source uses generic SQLAlchemy JSON fields with an Oracle DDL compiler hook only. PR #32 adds base-dialect serializer/deserializer defaults through a standalone import module and a generic JSON processor regression. Full CI remains pending; no production restart.

## G. Latest handoff checkpoint (ChatGPT reconnect, 2026-11-09)
- Last implementation merged: TASK-CORE-002 (PR #25, 79c1f75). No production task is claimed DONE/VERIFIED based only on this connector inspection.
- Main HEAD: `680c04ee383066874cad42a3295d18008eb6e1d2`.
- Open PRs observed in the latest snapshot: #23 (CI environment), #24 (bridge auth), #26 (Cortex auth), #27 (manual/no-force mirror), #28 (dispatch bus), #29 (Sentinel task API), #30 (ChatGPT docs/collaboration centre), #31 (Gitleaks), #32 (IntelX Oracle JSON), #33 (Futuris/Stratex data integrity), #34 (Claude CI root-cause fixes), #36 (Vercel v0 collaboration-centre bootstrap).
- ChatGPT review comments posted 2026-11-09: #23 TASK-ID collision/full-suite concern; #26 read-only POST forecast viewer access; #28 peer contract/endpoint/receipt/fake-success blockers.
- CI evidence: run 42502800827 reported 3,286 passed, 74 skipped, 38 failed, 43 errors. This is historical evidence from PR #24's run, not a result for current HEAD. Current main's full validation remains UNVERIFIED in this session.
- ChatGPT docs/collaboration branch: `chatgpt/TASK-DOC-SYNC-001`; PR #30 updates the three central docs and adds the initial `docs/collaboration/` system. PR #30 remains open; nothing has been merged to main.
- Live system bridge checked 2026-11-09: workspace on Server 2 is branch `claude/TASK-DISPATCH-001`, commit `f09e29f`, with one untracked file `Forge/tests/unit/test_task_execute_contract.py`; this work was preserved and not edited. Both Oracle VMs were online. Server 1: 956 MB RAM, 464 MB used, 337 MB available, 97 GB disk 22%; Server 2: 956 MB RAM, 265 MB used, 538 MB available, 49 GB disk 36%. These are point-in-time read-only diagnostics. All ten canonical agent systemd services were active when checked; liveness is not proof of each API's end-to-end functionality.
- TASK-SEC-004 PR #31: Gitleaks run 42525462164 PASS after initial run 42525352655 failed due shallow-fetch range resolution. Current action scans PR/push change ranges only, not entire history. It must pass CI and merge before TASK-SEC-004 can be VERIFIED.
- Tests: Forge targeted workspace test command was attempted on Server 2 but stopped in `Forge/tests/conftest.py` because the venv lacks installed `anthropic` (`ModuleNotFoundError`); the new Forge contract test was not executed. The dependency is listed in `Forge/requirements.txt`. No test was skipped or weakened.
- IntelX PR #32 CI history: initial test collection failed because importing `intelx.db` eagerly imports `engine.py` and SQLAlchemy asyncio, which requires greenlet in the root validation environment. The compatibility module was moved to `IntelX/intelx/oracle_dialect_compat.py` outside the eager `intelx.db` package. Latest root CI run on commit `372d8252` is queued/in progress; prior run at `a5e33634` failed collection for the same greenlet dependency. A local SQLAlchemy 2.0.50 generic OracleDialect JSON bind/result round-trip passed after adding both None defaults; this is focused local processor evidence, not the GitHub root-suite result.
- Outstanding external actions: TASK-OPS-002 sniper OCI authentication needs current workflow log verification; owner-reported credential rotation and approved history rewrite still need safe timing after open PRs settle; infrastructure and FRIDAY-Voice resource limits require authorized host access.
- Exact next steps: (1) review PR #34's two failed monorepo validator jobs and reconcile its overlapping files with PR #23/#28; (2) finish and review the collaboration files in PR #30 and synchronize all three central docs; (3) Claude resolves PR #28 dispatch contracts and completes PR #29 Sentinel verification; (4) ChatGPT resolves PR #26/#24 findings and refreshes PR #31/#32/#33 checks; (5) Grok should independently review PR #28/#34 after rejoining; (6) onboard ZAI and Vercel v0 only after verifying actual repo/tool access; (7) continue owner actions and per-agent audits without unapproved production changes.


## H. Multi-AI collaboration snapshot (2026-11-09)

- Shared collaboration centre: `docs/collaboration/`; onboarding instructions are in `docs/collaboration/README.md`. Initial validator run 42564054378 failed because `project_owner_id` did not match the roster ID; fixed to `human_surendra`. Latest validator run 42566339658 passed on PR #30 head `4a00f428`.
- Shared claim/release/review thread: [GitHub issue #35](https://github.com/surendra2304/FRIDAY-Universe/issues/35). Contributors must post a claim before editing, then update the board and file-ownership registry.
- Current roster: Claude (active), ChatGPT (active), Grok (previous contributor; current availability unknown), Vercel v0 (active contributor with PR #36), ZAI (planned/not onboarded), Surendra (project owner). V0 reports local shell/Vercel Git sync; only branch/PR existence is independently verified in this snapshot.
- Current active PR ownership and changed-file lists are mirrored in `docs/collaboration/WORK_BOARD.yaml` and `FILE_OWNERSHIP.yaml`. PR #30 is the proposed integration branch; PR #36's separate changes must be compared and consolidated.
- Explicit overlap conflicts: PR #23/#34 both modify `.github/workflows/validate-monorepo.yml`; PR #28/#34 both modify `FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py`; PR #24/#26/#30 all modify the three central docs; PR #30/#36 both modify the seven core `docs/collaboration/` files. Coordinate and reconcile combined diffs before merge. PR #36 was opened on `v0/coordination-bootstrap`; a coordination comment was posted on PR #36 (#6732575647).
- Shared Server 2 workspace last observed on `claude/TASK-CI-004` with untracked `Forge/tests/unit/test_task_execute_contract.py`. This file remains protected and must not be deleted or overwritten without its owner confirming disposition.
- CI refresh: PR #30 FRIDAY CI run 42564999315 PASS; Collaboration Registry Validation 42564999184 PASS; Monorepo Structure and Safety CI runs 42564999230 and 42564999188 FAIL. Fleet validation run 42564999230: 37 failed, 3272 passed, 73 skipped, 40 errors. Failures include unresolved Docker service-name dispatch targets (`inference`), 28/100 concurrent dispatch receipts, circuit-breaker failures, unconfigured Oracle memory DB during Inference app tests, missing test dependencies and CPU-worker process startup. Monorepo policy run 42564999188 also failed on dependency/import/process-worker issues. PR #34 FRIDAY CI run 42560097648 PASS; Heavy-Task Runtime Image Build run 42560097625 PASS; its monorepo jobs 42560097582/580 FAIL. PR #33 FRIDAY CI run 42530391450 PASS; its monorepo validation run 42530741161 FAIL during collection due missing NumPy. Main full validation remains red.
- TASK-CI-ID reconciliation: PR #23 uses TASK-CI-003 for CI dependencies/test DB setup while Master Plan TASK-CI-003 describes run_workspace_test; PR #34 uses TASK-CI-004 for broad validation fixes while Master Plan TASK-CI-004 describes bridge/** .gitignore. Claude must reconcile these IDs with the project owner before acceptance criteria are changed.
- No merge, production deployment, service restart, secret provisioning or history rewrite was performed in this session. PR #30 remains open and mergeable; PR #36 also remains open. The latest registry validator and FRIDAY CI passed; both broader monorepo validation jobs failed.


## I. Collaboration registry validation added

- Added `scripts/validate_collaboration.py` and `.github/workflows/collaboration-registry.yml` to PR #30.
- The workflow installs PyYAML and checks the YAML records, unique collaborator/task/conflict IDs, valid statuses, registered task owners, conflict-path references, required handoff files, central documents and the canonical ten-agent list.
- Command: `python scripts/validate_collaboration.py`.
- Latest result: PASS, run 42566339658 on PR #30 head `4a00f428d85b74834eff5ff29b54e6a032f64e15`. This validates registry structure only; full monorepo CI remains failed.
- Claim: TASK-COLLAB-001 was posted to issue #35, comment [#6732479100](https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6732479100).


## J. Latest CI evidence and cross-AI actions — 2026-11-09

- Current PR #30 head: `4a00f428` (`4a00f428d85b74834eff5ff29b54e6a032f64e15`).
- Collaboration Registry Validation: run 42596903311 — PASS on PR #30 head `5920161f`.
- Broad monorepo Structure and Safety CI runs 42596903328 and 42596903017 were in progress at the latest check. These are not implied to have passed.
- Prior PR #30 head `7ec4cdda` results: run 42564999230 — FAIL (37 failed, 3272 passed, 73 skipped, 40 errors), and run 42564999188 — FAIL. Observed prior-head failure groups included Docker service hostname `inference` DNS failures, only 28/100 concurrent dispatch receipts, circuit breaker open, Inference test DB unconfigured, missing agent dependencies, namespace collisions and CPU-worker startup failures. These results must not be presented as the latest-head result.
- Vercel v0 PR #36 monorepo-policy check run 42564376993 — FAIL, with overlapping test/dependency/import issues. PR #36 remains open and overlaps seven files with PR #30; no handoff response observed.
- Claude PR #34 review posted at PR comment #6732764298. Findings: permissive stub fleet can return false success on arbitrary routes/actions; real-fleet override comment does not match implementation; dependency lists remain incomplete; PR #27 mirror-policy changes are not part of its base; stale path assertions and Memora import collision remain.
- Exact next actions: Claude addresses PR #34 review and reconciles overlaps with PR #23/#28; v0 and ChatGPT consolidate PR #30/#36 through issue #35; ChatGPT maintains the single operational registry. All PR branches remain preserved and unmerged.


## K. Memora Oracle vector audit — latest PR #37 evidence (2026-11-09)

- PR #37 branch: `chatgpt/TASK-MEM-001-memora-oracle-vector-audit`; latest head `730ee962bb36e72d9a40c29821d84c8624b4c85a`; PR open and mergeable.
- Focused Memora Vector Regression run 42596147391 — PASS (8 passed, 1 warning).
- Full FRIDAY Universe CI/CD run 42596147378 — PASS. The job completed basic, cross-agent, advanced, deep, orchestrator, realtime, dashboard, Memora vector regression and HTTP/API tests; artifact upload also passed. Docker build remains skipped on PR branches by workflow design.
- Monorepo-only policy validator run 42596147434 and fleet-layout validator run 42596147572 were still in progress at the latest status check. They are not included in the green FRIDAY CI result.
- Source fixes: Oracle MERGE matches vector ID and tenant; SQLite fallback refuses cross-tenant ID reassignments; caller-owned writes/deletes use savepoints without committing the memory pipeline's parent transaction; schema bootstrap uses a separately managed session; readiness reports not-initialized/unavailable truthfully; vector ID/dimension/finite-value/threshold/payload guards were added.
- Dependency: `greenlet>=3.0.0,<4.0.0` is now declared in both `Memora/requirements.txt` and `Memora/pyproject.toml` because SQLAlchemy asyncio is imported by the package test/runtime surface.
- Dimension contract: generator/Oracle table are fixed at 384. Removed the unused `VECTOR_DIMENSION=1536` setting and documented that Qdrant (if used) must be externally provisioned at 384; no live collection/Oracle schema was contacted.
- Exact next action: review PR #37, obtain Oracle-specific verification in a controlled non-production database when available, verify Qdrant collection shape/config if deployed, then request owner review before merge.


## L. Latest Memora and collaboration registry handoff — 2026-11-09

- PR #37 / TASK-MEM-001: focused Memora vector tests run 42596147391 PASS (8 passed, 1 warning); full FRIDAY CI run 42596147378 PASS, including the Memora step and HTTP/API tests.
- PR #37 latest head: `730ee962bb36e72d9a40c29821d84c8624b4c85a`; open/mergeable; no live Oracle or Qdrant integration performed.
- PR #30 latest head: `5920161f457e4216f13edd260862ef6476d2612c`; collaboration registry validation run 42596903311 PASS. The two broad monorepo validation jobs on that head were still in progress at the latest check.
- TASK-MEM-001 has been added to the work board, roster, file ownership, activity log, handoff, Master Plan and as-built architecture.
