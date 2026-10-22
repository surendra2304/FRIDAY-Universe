# Raw Findings Log (working notes, feeds REPO_ANALYSIS.md)

## Orientation
- Repo: surendra2304/Forge, Python-only, 289 tracked files, 251 .py files, 47,568 lines of Python (wc -l sum). app/=~30k LOC, tests/=11,865 LOC, forge_upgrade/=1,839 LOC.
- Git: 112 commits on main (after unshallow fetch), authors "Surendra" (104) and "surendra2304" (8) -- same person, two git identities. First commit 2026-08-25 (8feaf96), latest 2026-10-07 (ab049ac merge). ~6 weeks of history, very high commit frequency (112 commits/6 weeks).
- No LICENSE file at repo root despite pyproject.toml declaring `license = {text = "MIT"}`.
- No lockfile (no requirements.lock/poetry.lock/pip-compile output); all deps pinned with floating `>=` minimums only in pyproject.toml.
- docs/, diary/, multiple audit/handoff markdown files at root (AUDIT_REPORT.md, AUDIT_2026-10-05_PHASE0-2.md, FORGE_UPGRADE_AUDIT.md, HANDOFF_2026-10-05_PHASE5.md, HANDOFF_2026-10-06_PHASE6.md, FORGE_DIARY.md, SYSTEM_MANIFEST.md) -- self-authored engineering diary/audit culture.

## Architecture
- Single FastAPI app (app/main.py) + Rich CLI (app/cli.py, entry point `forge` script) + a second, largely-dormant "forge_upgrade" package (overlay added in one big commit 6dbe522).
- forge_upgrade usage check (grep): only `forge_upgrade.command_policy`, `forge_upgrade.secret_redaction`, `forge_upgrade.memora_client` are imported from app/*. Everything else in forge_upgrade (orchestrator.py, dag.py, budget.py, plan_guard.py, patching.py, path_guard.py, repo_intelligence.py, verification.py, checkpoint.py, artifacts.py, audit.py, exec_runner.py, git_safety.py, provider.py, persistence/, providers/, recovery/, tools/) is exercised ONLY by its own dedicated unit tests (tests/test_*.py at repo root), never imported by the production app or forge_upgrade/orchestrator.py's consumers. forge_upgrade/orchestrator.py docstring literally says "Safety-first orchestration reference path for integration into FORGE" -- i.e. reference/staging code, not wired in.
- FORGE_UPGRADE_AUDIT.md (self-authored) claims "All architectural components ... integrated directly into active execution paths" and cites paths like `forge_upgrade/tools/command_policy.py`, `forge_upgrade/planning/dag.py`, `forge_upgrade/repo/repo_intelligence.py` -- these subdirectories (tools/planning/repo) do NOT match the actual flat layout of forge_upgrade/*.py. Documentation-vs-code mismatch, confirmed by `find`/`ls`.

## Orchestration core (app/core/orchestrator.py)
- `OrchestratorCore.intake_and_plan` -> workspace creation -> goal sanitization (strips control chars, documented live bug: NUL byte crashed release_engineer node) -> TaskEntity persisted PENDING -> TaskAnalyzer.analyze -> PlannerEngine.plan (8-stage tree) -> ExecutableTaskDAG.from_tree + validate (cycle check) -> task -> READY.
- `step_task` executes one parallel wave of ready DAG nodes via `asyncio.gather`; on completion of all nodes checks for FALLBACK_STUB marker (means synthesis fell back to template/stub) and fails the task rather than reporting false success.
- `run_task` loops `step_task` up to max_iterations=20, then ALWAYS calls `_verify_and_repair` regardless of per-node results.
- `_verify_and_repair` is the ONLY place VerificationEngine.verify_task() runs the full 10-check battery and writes `verification_report.json`. It runs strictly AFTER the DAG (including the Release stage) has already completed.

## CONFIRMED LIVE BUG: completion_report.json ships stale/fabricated verification status
- Pipeline order (from app/planning/planner.py): Project -> Requirements -> Architecture -> Implementation -> Integration -> Verification(gate, role=tester) -> Security(gate, role=security_reviewer) -> Release(milestone, role=release_engineer).
- TesterRole.execute_step (app/agents/roles.py ~1117) writes/augments test files; it does NOT invoke VerificationEngine's 10-check battery.
- ReleaseEngineerRole.execute_step (app/agents/roles.py ~1437) calls `DeliveryPackager.package_delivery()` (app/execution/delivery.py) which reads `artifacts/verification_report.json` IF IT EXISTS, else defaults to `{"all_passed": True, "total_checks": 0, ...}` (app/execution/delivery.py lines ~100-114).
- Because VerificationEngine only runs in `_verify_and_repair()` AFTER `run_task`'s DAG loop (i.e., after Release already ran), on first pass `verification_report.json` does not exist yet when DeliveryPackager runs.
- LIVE REPRODUCTION: POST /api/tasks goal="Build a CLI todo app" -> task completed in ~33s.
  - workspaces/<id>/artifacts/completion_report.json: `"test_build_status": {"all_passed": true, "total_checks": 0, "passed_checks": 0, "failed_checks": 0}` timestamp 09:15:05.578
  - workspaces/<id>/artifacts/verification_report.json (written later): `"all_passed": false, "total_checks": 10, "passed_checks": 8, "failed_checks": 2` with timestamps starting 09:15:05.862 (AFTER completion report).
  - Real failures in that run: "Ruff / Static Code Linter" exit 127 (ruff not found on PATH of the server process) and "Code Quality & Complexity Verification" exit 1.
- Net effect: the artifact a consumer is told to trust (`completion_report.json`, the thing docs/README calls "evidence over model confidence") can and did assert full success while the real verification battery had 2/10 failing checks. This directly contradicts README.md's "Core Verification & Isolation Principles" claim.

## CONFIRMED finding: `ruff` invoked as bare shell command, PATH-dependent
- app/verification/checkers.py:311-315: `"ruff check . --no-cache --select=E,F --ignore=E501,F841"` run via subprocess/shell. If the process's PATH doesn't resolve `ruff` (e.g., uvicorn launched without venv activation, or `.venv/bin` not on PATH), the lint check always exit=127 and fails silently into the evidence list (not a crash, just a failed check) -- discovered live.
- When the *pytest* suite is run via `source .venv/bin/activate && pytest`, ruff is found and tests pass (416 collected, 1 skipped, rest passed, confirmed exit 0, ~72s). When run via `.venv/bin/python -m pytest` without sourcing activate (PATH not updated), 7 tests fail for the same "ruff: not found" reason. This is a reproducible fresh-machine/CI gotcha.

## CONFIRMED finding: test isolation gap pollutes the real dev database
- tests/conftest.py provides `test_db_manager`/`async_client` fixtures that correctly isolate to temp dirs.
- BUT tests/unit/test_cli.py, test_tasks_enhanced_api.py, test_webhooks.py, tests/test_prompt4_forge.py import the *global* `app.memory.db.db_manager` singleton directly and call `db_manager.init_db()` / construct `StateStore(db_manager)` without overriding `database_path`. Default settings path is `data/forge.db` relative to CWD (app/core/config.py Settings.database_path default `Path("data/forge.db")`).
- tests/golden/*.py and tests/pressure/*.py instantiate a bare `Settings()` (app/core/config.Settings) without overriding `database_path` (only `workspaces_dir` is overridden in most), though they do construct their own `DatabaseManager(db_path=temp_dir/...)` for the orchestrator's `store` -- so the worst offenders are the four files above that touch the literal global singleton.
- LIVE VERIFICATION: after running the full pytest suite once from repo root, then starting the API fresh and submitting the FIRST EVER task via curl, `GET /health/detailed` reported `"total_tasks_recorded": 50` -- i.e., 49 rows already existed in `data/forge.db` purely from the test run, despite `data/` being .gitignored and not present at checkout. Confirms tests write into the same file a developer's real dev server reads.

## CONFIRMED finding: orphaned auth/rate-limit subsystem (app/security/api_keys.py)
- `APIKeyManager`, `RateLimiter`, `verify_api_key` (FastAPI dependency) are fully implemented (sliding window, 100 req/hr, 10 req/min burst, failed-auth lockout) but `verify_api_key` is never attached as a `Depends()` to any route; `rate_limiter` is never referenced outside app/security/api_keys.py and app/security/__init__.py's re-export.
- The ACTUAL enforced auth mechanism is the ad hoc middleware `require_production_api_key` in app/main.py (added as a hardening patch, commit c5e2e9f/4faf060), which does a straightforward `hmac.compare_digest` check against `FORGE_API_KEY`/`FRIDAY_API_KEY` and has NO rate limiting at all.
- docs/PRODUCTION_DEPLOYMENT.md section 3 documents "Rate Limiting: Enforces a sliding-window limit (default 100 requests/hour per client)" -- this is only true of the orphaned, unwired code path; in the live app no endpoint is rate-limited.

## CONFIRMED finding: docker-compose.yml ships a self-locking config
- docker-compose.yml sets `FORGE_ENV=production`, `API_KEY_REQUIRED=false`, and does NOT set `FORGE_API_KEY`.
- `require_production_api_key` middleware (app/main.py) ignores `api_key_required`/`API_KEY_REQUIRED` entirely -- it only checks `production_settings.env != PRODUCTION` to skip, then unconditionally demands a configured `forge_api_key` of length >= 32 that isn't a known placeholder.
- LIVE REPRODUCTION: `FORGE_ENV=production API_KEY_REQUIRED=false uvicorn app.main:app` (no FORGE_API_KEY) -> `GET /health` = 200, `GET /api/tasks` = 503 `{"error":"service_auth_unconfigured","detail":"A unique FORGE_API_KEY is required."}`.
- Net effect: `docker compose up -d --build` (the exact command docs/PRODUCTION_DEPLOYMENT.md tells operators to run) boots a container whose entire data API is permanently 503 until an operator independently discovers they must also inject a 32+ char FORGE_API_KEY -- `API_KEY_REQUIRED=false` in the shipped compose file is misleading dead configuration.

## Documentation-vs-reality: "standalone" claim
- README.md: "FORGE operates as a 100% independent, standalone tool ... requiring no external ecosystem dependencies." docs/ARCHITECTURE.md: "External platform integrations (FRIDAY/Jarvis...) are explicitly deferred until FORGE achieves mature standalone product readiness."
- SYSTEM_MANIFEST.md (committed in repo root) describes Forge as one of 9 named agents in "FRIDAY Universe" with a live delegation contract, lists sibling service URLs (Inference, Memora, Stratex, IntelX, Futuris, Cortex, Sentinel, FRIDAY), and says "Communicates directly with peer agents via authenticated REST and WebSocket protocols."
- Code backs the ecosystem version: app/api/delegate.py ("FRIDAY Universe Forge Delegation" router, mounted in app/main.py), app/config/production.py's `friday_api_key`, app/core/config.py's ai_universe_url/intelx_url/futuris_url/cortex_url/memora_url settings (all default to live friday_mesh URLs), provisioning FRIDAY_URL/STRATEX_URL/SENTINEL_URL secrets.
- Verdict: both documents are accurate about different things -- FORGE *can* run standalone (DirectProvider, template fallback, local SQLite) but ships pre-wired, by default, with a whole constellation of external services it will try to reach (and gracefully fall back from) unless explicitly air-gapped.

## Live run: autonomous build actually works end to end
- POST /api/tasks {"goal": "Build a CLI todo app"} -> task READY -> orchestrator auto-progresses (some mechanism runs run_task in background; task reached COMPLETED with workspace files) in ~33 seconds wall clock, fully offline-degraded (AI Universe/Memora calls failed with SSL errors against the sandboxed network -- confirmed in logs -- and the system fell back to DirectProvider/local reasoning without crashing).
- Produced workspace: project/main.py, test_main.py, README.md, requirements.txt, docs/ARCHITECTURE_SPEC.md, docs/FILE_MANIFEST.json, a local git repo with a `v1.0-forge-delivery` tag, and `artifacts/{completion_report.json, COMPLETION_REPORT.md, verification_report.json, verification_manifest.json}`.
- Confirms: DAG planning, parallel wave execution, template/direct-provider fallback, delivery packaging, and local git tagging are all real and functional, not vaporware -- a materially positive finding alongside the verification-ordering bug above.

## CI
- .github/workflows/ci.yml: matrix [ubuntu-latest, windows-latest]. Linux leg ONLY lints (`ruff check .`) and does an import smoke test (`python -c "import app.main, ..."`) -- explicitly because "The 7 GB ubuntu runner OOM-killed pytest even serially". The FULL test suite (including golden benchmarks) only runs on the Windows runner. This means Linux deployments/contributions are not covered by the real test gate in CI, only by a human running pytest locally.
- ruff clean (0 errors) verified locally: `ruff check app forge_upgrade tests` -> "All checks passed!" (matches FORGE_UPGRADE_AUDIT.md claim).
- Full pytest run (venv activated, ruff on PATH): 416 collected tests, 1 skipped (`test_deterministic_synthesis.py:125`, "website project has no test suite" -- a conditional skip, not a failure), remainder passed, exit code 0, wall time ~72s.
- pip-audit: only `setuptools==66.1.1` (bundled via pip's build isolation, not a direct project dependency) flagged with 3 known CVEs recommending >=70-83. No vulnerabilities reported against the project's actual direct dependencies (fastapi, pydantic, httpx, etc. at their locally-resolved versions).
- No committed secrets found via pattern grep (AKIA/sk-/BEGIN PRIVATE KEY/ghp_) across git-tracked files.

## Data layer
- Single SQLite DB (aiosqlite) at data/forge.db, WAL mode, tables: projects, tasks, audit_events, artifacts, task_graphs, checkpoints (app/memory/db.py SCHEMA_SQL). No foreign-key-enforced user table -- no multi-tenant concept; the whole DB is one operator's task history.
- `ALTER TABLE tasks ADD COLUMN metadata ...` executed unconditionally at every init_db() call and the "duplicate column" exception swallowed -- ad hoc, code-level, run-every-boot migration strategy; no formal migration tool (no Alembic).
- Second SQLite DB `data/memora.db` for the Memora long-term-memory subsystem (agents/namespaces/memory_records schema, shared between app/integrations/memora_client.py (cloud-first) and forge_upgrade/memora_client.py (local fallback), per forge_upgrade/memora_client.py's own docstring).

## Security posture (app's own code, not the code it generates)
- Global production auth middleware: constant-time comparison (hmac.compare_digest), minimum 32-char key, rejects common placeholder keys ("changeme" etc.) -- reasonably careful.
- CORS is wide open always: `allow_origins=["*"], allow_credentials=True` (app/main.py) regardless of environment -- combining wildcard origin with allow_credentials=True is a recognized bad practice (browsers largely block the combination, but the declared policy itself is a smell / confusing).
- Rate limiting code exists but is dead (see above) -- no real throttle on a production deployment beyond what any reverse proxy in front of it provides.
- MAX_REQUEST_BODY_BYTES = 8MB enforced via Content-Length pre-check middleware (does not protect against chunked transfer without Content-Length, only declared-length bodies).
- Secrets: `.env.example` ships all keys blank (good -- commit message e08... explicitly calls out removing previous placeholder secrets that "trained operators to ship real secrets in plaintext"). git-grep found no committed secrets.
- Self-repair/terminal execution: app/execution/terminal.py uses forge_upgrade.command_policy.CommandPolicy + secret_redaction.redact -- destructive-command blocklist and secret-masking are real and wired in (confirmed via grep + forge_upgrade.command_policy consumption).

## Testing quality spot-check (5 read in full)
1. tests/test_path_guard.py -- small, real assertion (SandboxViolation raised on `..` escape). Minimal but meaningful.
2. tests/test_idempotency.py -- trivial happy-path only (`seen`/`remember`), no edge cases (concurrent keys, TTL). Shallow but tests the forge_upgrade module that app code never imports anyway (dead-code test).
3. tests/test_production_api_auth.py -- strong: 3 tests enforce fail-closed behavior, document a historical CI bug ("no such table: tasks") inline, assert the API key never leaks into dashboard HTML.
4. tests/unit/test_selfrepair_proposer.py -- explicit test philosophy comment: "most of these tests are about what it *refuses* to do" (restraint-testing of an autonomous-patch proposer) -- mature design intent.
5. tests/golden/test_golden_cli_tool.py -- true end-to-end integration test: builds a real project via the real orchestrator/engine/verifier stack in a temp workspace, asserts on DAG node counts and on-disk files. Good signal-to-noise; exercises the real pipeline, not mocks.
Overall: tests at the "forge_upgrade root-level test_*.py" tier are shallow unit tests of isolated, largely-unused safety primitives; tests under tests/unit and tests/golden are substantially meatier and assert real behavior, including deliberately re-creating past production bugs as regression tests (common convention across the suite: comments explaining the historical bug a test guards against).

## Churn / history
- Top churned files: FORGE_DIARY.md (29 commits, docs), app/agents/roles.py (27), app/core/config.py (18), app/cli.py (17), app/api/routes.py (15), app/main.py (12), app/verification/checkers.py (11), app/integrations/ai_universe_client.py (11).
- Biggest single commits: 6dbe522 "feat(upgrade): complete FORGE deep upgrade overlay integration" (160 files, +5265/-1312) and fd5bd49 diary system rewrite (58 files, +5713/-752).
- Commit cadence by month: 2026-08: 45, 2026-09: 52, 2026-10: 15 (so far) -- sustained, almost daily, single-author development over ~6 weeks.
- No TODO/FIXME/HACK/XXX markers anywhere in app/ or forge_upgrade/ (grep returned zero). Project convention instead: long inline comments narrating a specific historical bug, its live-reproduction evidence, and the fix (dozens of examples across orchestrator.py, main.py, memora_client.py, api_keys.py, etc.) -- unusually candid and traceable commit/comment culture, functions as an informal in-code changelog.

## Misc
- `app.cli:main` console-script entry point (`forge` command) registered via pyproject.toml `[project.scripts]`.
- `ask_inference_from_forge.py` and `peer_mesh_forge_results.json` at repo root look like ad hoc experiment/debug scripts, not part of the package (not under app/ or tests/, not imported anywhere) -- candidate dead/scratch files.
