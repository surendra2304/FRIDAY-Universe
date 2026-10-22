# FORGE — Phase 5 Handoff Report

**Date:** 2026-10-05
**Branch:** `arena/01a10cc0-forge`
**Scope:** Phases 0–5 complete. 29 prioritized defects triaged; 25 fixed with regression coverage; 4 consciously left open with reasons.
**Verification standard applied:** every "works" claim below is backed by a command that was actually executed in this workspace, with its output quoted. Anything that could not be executed here is labelled `CONFIGURED-BUT-UNVERIFIED` with the reason.

---

## 1. What was verified, and how

### 1.1 Automated suites

| Check | Command | Result |
|---|---|---|
| Full non-golden suite | `python -m pytest tests --ignore=tests/golden -q` | `SUITE_EXIT=0`, 440 dots, zero failures (~45 s) |
| Golden benchmarks | `python -m pytest tests/golden -q` | `GOLDEN_EXIT=0`, 6 passed (~13 s) |
| Lint | `python -m ruff check .` | `All checks passed!` |
| Package install | `pip install -e ".[dev]"` | exit 0 |

Evidence files: `/tmp/fs18.txt`, `/tmp/g19.txt`, `/tmp/ruff_final.txt`.

### 1.2 Live-server adversarial gauntlet — 23/23 passed

Booted a real `uvicorn` worker (not `TestClient`) and attacked it. `/tmp/pressure/gauntlet.py`, output `/tmp/pressure/gauntlet4.txt`, `GAUNTLET_EXIT=0`.

- **Path traversal (36 probes):** `../`, `..%2f`, `%2e%2e%2f`, `....//`, `..\`, double-encoded, NUL-suffixed variants against `GET /api/tasks/{id}/artifacts/{path}` — every one refused, zero leaks.
- **Injection payloads (12):** SQL injection, `<script>`, JNDI/Log4Shell, SSTI `{{7*7}}`, NUL bytes, 100 KB string, 5 000 emoji, `$(id)`, backticks — 0 × 5xx.
- **Malformed bodies (11):** invalid JSON, `[]`, `null`, wrong types, negative and infinite budget — 0 × 5xx.
- **Odd routes/methods:** `TRACE`, `PATCH`, deep paths, 5 000-char ids, `/../etc/passwd` — 0 × 5xx.
- **Concurrency:** 50 and 200 parallel requests, 100 % success; 25 parallel task creations, 25/25 → 201; 10 concurrent websockets, 10/10 connected.
- **Secret-leak scan:** `openapi.json`, health, metrics, tasks, analytics, marketplace, dashboard, capabilities — no `sk-ant-`, `ghp_`, `AKIA`, PEM header, `xoxb-`, `AIza`, and no host env var names echoed.

### 1.3 Extreme-pressure gauntlet — 33/33 passed

`/tmp/pressure/extreme.py`, output `/tmp/pressure/extreme6.txt`, `EXTREME_EXIT=0`.

- **End-to-end autonomous build through the public API:** created a task, polled to a terminal state, then verified timeline / logs / artifacts / inspect all return 200, the workspace is populated, and `verification_report.json` exists with real check counts (`all_passed=False 9/10`).
- **Sustained mixed load (45 s, two phases):** reads-only `p50=193ms p99=349ms`; reads-while-pipelines-execute `p50=260ms p99=2913ms`; 662 ops, 0 errors.
- **Fault injection (10):** missing binary (`exit=127`), segfault (`exit=139`), binary garbage on stdout, deleted CWD, permission denied, syntax-error project, failing tests, empty workspace, 40-level-deep path, symlink escape — all handled without a crash, and the failing cases correctly reported as failures.
- **Resource exhaustion:** 10 MB body → clean `413`; deeply nested JSON → `422`; 10 000-element list → `422`; 60 large reads and 80 connection churns → all 200; server alive afterwards.
- **Restart resilience:** task persisted across a process restart and visible to a freshly constructed app instance, timeline included.

### 1.4 Real-world CLI build

`forge build "Create a Python CLI note-taking app with add, list and delete commands"` run from `/tmp/cli_final`:
full pipeline executed (intake → 8-stage DAG → execute → 10-check verification → self-repair → report), `Checks Passed 8/10`, and `CLI_EXIT=1`.

---

## 2. REAL vs CONFIGURED-BUT-UNVERIFIED

This table is deliberately blunt. "REAL" means I ran it and saw it. Anything else is listed with the specific reason it could not be executed here.

| Capability | Status | Evidence / reason |
|---|---|---|
| Path-traversal containment on artifact download | **REAL** | 36 live probes, all refused |
| Concurrent task creation (no duplicate-id 500s) | **REAL** | 25/25 → 201 on a live worker |
| Process-group timeout kill (CRITICAL-1) | **REAL** | Grandchild marker file absent after timeout; 12 concurrent timeouts all reaped; 0 zombies after 20 timeouts |
| `forge build` full pipeline + non-zero exit on failure | **REAL** | `CLI_EXIT=1`, 8/10 checks |
| API-driven autonomous execution + verification report | **REAL** | X2 suite, 9/10 checks, report on disk |
| OpenAPI operation-id uniqueness (91 ops) | **REAL** | `duplicates=[]` from a live `/openapi.json` |
| Request-body size limit (413) | **REAL** | 10 MB body → `413` |
| Secrets never committed | **REAL** | grep of credential patterns found only regexes/dummy fixtures; `.env.example` now blank |
| Webhook dispatch on `task_started` / `task_failed` | **REAL** | observed dispatched in a live probe |
| **`stage_completed` / `verification_result` / `task_completed` webhooks** | **CONFIGURED-BUT-UNVERIFIED** | A live probe showed only `task_started`/`task_failed` are ever emitted; the other three event names have no call site. The dispatcher works, but those events do not exist. |
| **Real AI code generation (AI Universe / OpenAI / Anthropic)** | **CONFIGURED-BUT-UNVERIFIED** | This sandbox cannot reach the providers: every call fails with `TLS/SSL connection has been closed (EOF)` or `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. Every build here takes the offline fallback-stub path. The provider code is wired and retries correctly, but no real generation was ever produced here. |
| **GitHub push / PR creation** | **CONFIGURED-BUT-UNVERIFIED** | `Failed to connect to GitHub API: CERTIFICATE_VERIFY_FAILED`. The branch→commit→push→PR flow is wired and unit-tested, but never completed against a real remote. No credentials are configured (correctly). |
| **Real browser verification (screenshots)** | **CONFIGURED-BUT-UNVERIFIED** | `playwright` is **not installed and not in `pyproject.toml`**. `BrowserChecker` always degrades to the HTTP fallback. It now honestly records `screenshot: false` and stores the fetched HTML instead of fabricating a PNG. |
| **Production mode auth (503 when `FORGE_API_KEY` unset)** | **CONFIGURED-BUT-UNVERIFIED** | `render.yaml` sets `FORGE_ENV=production` with `FORGE_API_KEY` as `sync: false`. I verified the fail-closed middleware logic and the `Settings.env`/`ProductionSettings.env` agreement, but did not deploy to Render. **If that key is unset in the real environment, every data endpoint returns 503.** This is the single highest-risk deployment item. |
| `forge serve` static file serving | **CONFIGURED-BUT-UNVERIFIED** | Fixed (binds loopback, restores CWD, opens browser only after the port accepts) and unit-verified, but I did not drive the browser UI end to end. |
| `TestChecker` shelling out to a working pytest | **REAL (as fixed)** | Now uses `sys.executable`; the verification battery ran real pytest inside a live build |
| Multi-project manager, `TaskAnalyzer.analyze`, `forge_upgrade/` (~90 %) | **CONFIGURED-BUT-UNVERIFIED / DEAD** | Not wired into any reachable path. See §4. |

---

## 3. Defects fixed in this phase (pressure-test discoveries)

These five were found **only** by exercising the live system; all were invisible to the 440-test suite.

| # | Defect | Root cause | Proof of fix |
|---|---|---|---|
| 1 | **Concurrent task creation 500'd** | Task id derived from `COUNT(*)` then "checked" with `get_task()` — a check-then-act race. Two concurrent submissions produced the same id and the second `INSERT` hit `sqlite3.IntegrityError: UNIQUE constraint failed: tasks.id`. 25 parallel `POST /api/tasks` → **23 × 500**. | 25/25 → 201; plus a last-resort retry with a collision-proof id |
| 2 | **API never executed tasks** | `POST /api/tasks` called `intake_and_plan()` and returned. Every task sat in READY forever — a write-only task board. | Live build reaches a terminal state, progress 100 %, report written |
| 3 | **Orchestrator never ran verification** | Only the CLI called `VerificationEngine`, so API-driven tasks finished unverified: no `verification_report.json`, no `record_verification()` telemetry, no recovery attempt. | `X2.verification_report_real :: all_passed=False 9/10` |
| 4 | **Unbounded concurrent pipelines** | Each submission spawned a full autonomous pipeline (subprocesses, LLM calls, git) on one worker. | Semaphore (`FORGE_MAX_CONCURRENT_TASKS=3`) + `GET /api/tasks/queue` returning `{"max_concurrent":3,"running":[...],"waiting":[...]}` |
| 5 | **Missing index on `tasks(created_at)`** | `EXPLAIN QUERY PLAN` → `SCAN tasks` + `USE TEMP B-TREE FOR ORDER BY`: a full scan and sort on the product's most common read. | Same query on the same 456-row DB: **54.50 ms → 0.42 ms** (130×). Read p99 under load 564 ms → 349 ms |

Also fixed in this phase: `/api/metrics` and `/api/health/*` 404'd under the `/api` prefix the docs use; `TerminalTool` truncated output *after* slicing so the 200 KB limit was never honoured (now exactly 200 000 chars); `forge build` exited 0 on failure; the cancelled subprocess transport leaked pipes.

### Investigated and rejected

A pooled-connection `DatabaseManager` was implemented, measured, and **reverted in full**. The measured saving was 0.98 ms per call (1.20 ms fresh + 2 PRAGMAs vs 0.22 ms reused) against a 54 ms query — it could not have been the bottleneck — and it made the process **hang at exit**, because aiosqlite's worker thread is non-daemon and an idle pooled connection keeps it alive forever. Verified: a script that leaves one connection open never terminates. `app/memory/db.py` is back to its original behaviour plus the new indexes.

---

## 4. Consciously left open

1. **`render.yaml` production auth** (§2) — highest deployment risk.
2. **Dead modules** (~12 in `app/`, ~90 % of `forge_upgrade/`) — imported only by their own tests. Deleting them is a large, separate change with real regression risk; it belongs in a dedicated cleanup phase, not a bug-fix pass.
3. **`docs/API_REFERENCE.md`** documents a `since` parameter and a `provenance_summary` field that do not exist in the code or response model.
4. **`TaskAnalyzer.analyze` / `multi_project_manager`** — keyword-only, never call their provider, unreachable from any command path.

---

## 5. Prioritized 5-item roadmap

**1. Make production auth deployable (blocks go-live).**
Set a real `FORGE_API_KEY` in Render (or change `render.yaml` to not set `FORGE_ENV=production`). Until one of those happens, every data endpoint returns `503`. *This is the difference between a working deployment and a broken one.*

**2. Prove the AI provider path against a real endpoint.**
Everything generated in this sandbox used the offline fallback stub. The retry/fallback logic is correct and observed, but no real model output was ever produced here. Run one build with valid credentials and record the real file count and check ratio.

**3. Delete or wire the dead code, in that order.**
`forge_upgrade/` is ~90 % orphaned and 12 `app/` modules are reachable only from their own tests. Either delete them (with a test-count audit) or wire them into a real command path. Right now they inflate the apparent surface area and will silently rot.

**4. Add `playwright` and make browser verification real.**
`BrowserChecker` now honestly reports `screenshot: false`. Adding the dependency turns web verification from "the page returned HTTP 200" into "the page renders and is accessible" — a materially stronger gate, and the honest-evidence plumbing is already in place.

**5. Emit the missing webhook events, or remove them from the contract.**
`stage_completed`, `verification_result` and `task_completed` have no call site. Either wire them into the orchestrator's stage/verification transitions or delete them from the documented event list — a documented event that never fires is worse than no documentation.

---

## 6. Commits on this branch

| Commit | Summary |
|---|---|
| `5b458b0` | CRITICAL-1: process-group timeout kill + 8 regression tests |
| `2ba347e` | CRITICAL-2 artifact traversal, router mounting, `list_tasks` filters, from-template containment |
| `10a3f06` | Fail-closed git-push auth, strict `validate_repository_url`, release-engineer permissions |
| `8791b60` | Telemetry wiring: middleware counters, progress tracker, verification/security metrics |
| `6282ec3` | Parser accumulation, web-studio requirements, context folding, PR delegation |
| `91b803f` | Fail-closed API-key/websocket auth, env allowlist, honest browser evidence, dependency scanner, delivery flags |
| `3d26a47` | Execute API tasks, latency regression, request-body cap |
| `b841ca5` | Orchestrator verification + recovery, bounded concurrency, queue endpoint, `created_at` index |
| `ae8a944` | `forge build` exits non-zero on failure |

**Uncommitted:** `AUDIT_2026-10-05_PHASE0-2.md` (the Phase 0–2 prioritized defect report, retained as the audit trail).

---

## 7. Bottom line

The engine is now safe under the conditions that previously broke it: it survives adversarial input, concurrent load, timeouts that outlive their commands, and process restart, and it tells the truth about what it did — including refusing to fabricate a screenshot it never took.

The one thing I could not verify here is the thing that matters most commercially: **whether it can write real software with a real AI provider behind it.** Every build in this sandbox took the fallback path. That is item 2 on the roadmap and it should be the first thing run with live credentials.
