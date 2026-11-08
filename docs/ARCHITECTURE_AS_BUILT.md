# FRIDAY Universe — Architecture As Built

Describes what is implemented and running, not what is intended.
Labels: VERIFIED (independently checked), PARTIALLY VERIFIED, UNVERIFIED, GAP (missing or wrong), CONFLICT (sources disagree).
Evidence cited by file path or command. Secrets are named, never printed.

## 1. Repository structure (VERIFIED)
- 5,288 tracked files; about 1.1 million lines of Python.
- Agent folders: FRIDAY (1,122 files, about 202k lines), Stratex (840 files, about 155k), Sentinel, Cortex, Inference, Forge, IntelX, Futuris, VyralX, Memora.
- Shared: tests/ (89 files), scripts/ (30), mesh/ (21 files, the health checker), docs/, deploy/, docker/, tools/.
- Only root-level .github/workflows/ runs on GitHub. Agent-level .github folders are inert (VERIFIED: sniper workflows were inert under FRIDAY/.github until moved).

## 2. Ten-agent implementation (VERIFIED in AGENTS.yaml; PARTIALLY VERIFIED in code)
| Agent | Entry point (observed) | Server | Port | Status |
|---|---|---|---|---|
| FRIDAY | src/friday/api/server.py (3,089 lines) | 1 | 10000 | Running (systemd FRIDAY.service) |
| Inference | Inference/app/main.py (per deploy guide) | 1 | 8001 | Running |
| Memora | Memora/apps/api | 1 | 8002 | Running |
| Stratex | Stratex/dashboard.py and autonomy/run_daemon.py | 1 | 8003 | Running (+ Stratex-Daemon) |
| Futuris | Futuris app | 1 | 8004 | Running |
| IntelX | IntelX/intelx/app/main.py | 1 | 8005 | Running |
| Forge | Forge app | 1 | 8006 | Running |
| Cortex | Cortex/apps/api (cortex_api.main:app) | 2 | 8009 | Running |
| Sentinel | Sentinel app | 2 | 8008 | Running |
| VyralX | VyralX/app/main.py | 2 | 8010 | Running (+ daemon, autopilot) |
- VERIFIED: services are active on both servers (systemctl list-units, Server 1 and 2).
- CONFLICT: docs/DEPLOYMENT_GUIDE.md described the port map as 8000–8010 container ports before PR #20; that PR changed it to production host ports. Confirm the current file.
- VERIFIED: `friday-oci-a1-allocator.service` is referenced in docs but not registered on Server 1 (not-found).

## 3. Internal APIs and communication (VERIFIED in fleet_client.py)
- FRIDAY's fleet client (src/friday/ecosystem/fleet_client.py) calls each peer over HTTP: probe_* for health, ask_* for queries, dispatch_task for typed envelopes.
- Typed dispatch posts to /v1/task/execute. VERIFIED present in: Inference, Memora, Stratex (1 definition each), Futuris (4), VyralX (5), IntelX (1), Cortex (1). VERIFIED absent in: Forge, Sentinel.
- CONFLICT: dispatch_task sends typed tasks to Forge and Sentinel, which do not implement that endpoint.
- The Caddy public routes (VERIFIED, /etc/caddy/Caddyfile on Server 1): /friday, /inference, /memora, /stratex, /futuris, /intelx, /forge, /bridge, /mcp, /messages, /vyralx, /sentinel, /cortex.

## 4. FRIDAY orchestration and task dispatch (VERIFIED by reading; behaviour PARTIALLY VERIFIED)
- Command router: _dispatch_command in src/friday/api/server.py. Checks prompt injection, refuses destructive intents, then routes to ask_* calls. Routing table is substring matching.
- Directive router: fleet_client.dispatch_directive, substring keyword matching. Misroutes observed by test: "decode this base64"→Forge, "I want to trader-proof my plan"→Stratex, "cashback offers"→Stratex, "the weather in the webpage"→Cortex.
- FIXED ON BRANCH, NOT DEPLOYED: integrations/universe_orchestrator.py execute_universe_goal, with no simulation API set, used to return status "dispatched", real_agents 8, and a fixed synthesis without calling any peer. grok/TASK-CORE-002 calls FleetClient.get_fleet_summary and returns status not_executed with the probed online/total counts, or the probe error. It does not execute the goal. Verified by FRIDAY/tests/test_universe_orchestrator_no_fake_dispatch.py (2 passed) plus the existing mock-API test file (3 passed) on Server 2, 2026-11-08.
- Task records: none found. No table or store tracks assignment, status or result across agents. (PARTIALLY VERIFIED: searched for dispatch/task store; not exhaustive.)
- Autonomy: src/friday/autonomous/ exists (controller.py, daemon.py, enhanced_controller.py). UNVERIFIED: whether it can assign work to agents.
- Dispatch bus: FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py exists and is mounted at /api/v1 (VERIFIED by grep). UNVERIFIED: its behaviour.

## 5. Inference routing and providers (PARTIALLY VERIFIED)
- Inference exposes health and a routing gateway; key pools exist for Gemini, Groq, OpenRouter and NVIDIA NIM in the (untracked) credentials file. Names and counts only are recorded here.
- Keys were committed in public history (commit 46034a4). Owner rotated them.
- UNVERIFIED: fallback order and failover behaviour.

## 6. Memora databases and memory sharing (PARTIALLY VERIFIED)
- Memora manifest: Oracle Autonomous Database, schema MEMORA, Oracle 23ai vector store. (Memora/SYSTEM_MANIFEST.md, changed in PR #20.)
- CONFLICT: an older manifest said SQLite WAL. Current code and manifest should be checked against each other (UNVERIFIED).
- Memory namespaces: memora://<agent>/private (documented). UNVERIFIED: enforcement.
- Stratex: Oracle schema STRATEX (manifest); code uses SQLite in places (e.g. sqlite+aiosqlite path in old manifest). CONFLICT, UNVERIFIED.

## 7. Oracle Cloud infrastructure and placement (VERIFIED)
- Server 1: 140.245.208.100 (private 10.0.0.121). 956 MB RAM. Disk 97 GB, 26% used.
- Server 2: 140.245.243.168 (private 10.0.0.120). 956 MB RAM. Disk 49 GB, 37% used.
- Memory use at time of check: Server 1 454 MB used, 346 MB available, 1.5 GB swap used. Server 2 466 MB used, 337 MB available.
- Region ap-hyderabad-1. Always Free A1 capacity: none available (sniper log, 287 attempts, "Capacity full").
- GAP: FRIDAY-Voice has no MemoryMax (systemd show, infinity). All other units have one.

## 8. Service ports, health and deployment configuration (VERIFIED)
- Health: each agent answers GET /health on its port (curl through Caddy returned 200 for FRIDAY).
- Restart policy: all units Restart=always (VERIFIED). A crash loop restarts silently; no alerting found.
- Deploy: deploy-monorepo.yml on push to main; SSH to each server; `git fetch origin main; git reset --hard origin/main`; restarts changed agents. VERIFIED by reading the workflow.
- Mirror: mirror-subrepos.yml force-pushes each agent folder to its standalone repo.

## 9. Authentication and authorization (PARTIALLY VERIFIED)
- Agents require bearer keys named in their manifests (MEMORA_API_KEY, STRATEX_API_KEY, FRIDAY_API_KEY and so on). Values are secrets; not recorded.
- Bridge (friday-bridge, :8011, exposed via Caddy /bridge, /mcp, /messages): run_shell, github_api, github_write_file, read_text, github_run_logs. No authentication found in bridge/server.py (PARTIALLY VERIFIED: a request to /bridge/mcp timed out instead of being rejected). Owner accepted the risk; recommendation stands.
- CI secrets: DATABASE_URL in CI is a test-only placeholder (VERIFIED in monorepo-validation.yml from PR #20).

## 10. Secret management (VERIFIED)
- GitHub Actions secrets in FRIDAY-Universe: GH_PAT_MIRROR, ORACLE_SSH_KEY, SERVER1_HOST, SERVER2_HOST, OCI_USER_OCID, OCI_KEY_CONTENT, OCI_FINGERPRINT, OCI_TENANCY_OCID, OCI_REGION, OCI_USER_OCID_2, OCI_KEY_CONTENT_2, OCI_FINGERPRINT_2 (names verified via API).
- CREDENTIALS.md on Server 2 (/opt/friday_universe/CREDENTIALS.md): untracked by git (VERIFIED, 0 history commits). Holds identifiers and provider keys in plaintext. Keep it out of git.
- Leaked keys in public history commit 46034a4: owner rotated. History not yet rewritten.
- Binance testnet keys are present in the credentials file; testnet only.

## 11. External integrations (PARTIALLY VERIFIED)
- Binance Futures testnet (Stratex). Code default BINANCE_TESTNET true; effective value UNVERIFIED (owner states testnet).
- Telegram (Stratex notifications). UNVERIFIED.
- LiveKit (FRIDAY-Voice). UNVERIFIED.
- Gemini, Groq, OpenRouter, NVIDIA NIM (Inference). UNVERIFIED.
- AWS Mumbai libSQL (Memora, IntelX per old credentials file). CONFLICT with Oracle manifest; UNVERIFIED.

## 12. Background workers and scheduled jobs (VERIFIED)
- Oracle sniper: hourly cron (workflows at repo root) plus 6-hour relay (workflow_dispatch). VERIFIED in workflow files.
- Stratex-Daemon and VyralX-Daemon / VyralX-Autopilot: long-running services. VERIFIED units exist.
- friday-oci-a1-allocator.service: referenced, not installed (VERIFIED).

## 13. Failure handling and recovery (PARTIALLY VERIFIED)
- Circuit breakers exist in fleet_client (get_circuit_breaker). UNVERIFIED thresholds.
- Restart=always on all services. No alerting found (GAP).
- Backups: UNVERIFIED. No backup job found in this review.
- Rollback: none documented (GAP).

## 14. CI/CD (VERIFIED)
- Workflows at root: deploy-monorepo, mirror-subrepos, monorepo-validation, validate-monorepo, friday-universe-ci, heavy-task-image-build, oracle-capacity-sniper, oracle-capacity-sniper-worker2.
- Failing before the CI fixes: VyralX/Futuris `app` collision (ModuleNotFoundError: app.services.autonomous_orchestrator). ChatGPT pushed fixes; current status of main c097312 UNVERIFIED.
- Workflows run on Node 20 with actions/checkout@v4 (deprecation warning in logs; not blocking).

## 15. Known gaps and inconsistencies (summary)
1. CONFLICT: Stratex database (Oracle manifest vs SQLite code).
2. CONFLICT: Memora database (Oracle manifest vs SQLite in older docs).
3. CONFLICT: Stratex venues (Binance Futures vs MT5 vs cTrader). Owner says Binance testnet.
4. IN_REVIEW: universe_orchestrator no longer fabricates a live dispatch (grok/TASK-CORE-002). The goal is still not executed when no Universe API is configured.
5. GAP: keyword routing misroutes.
6. GAP: Forge and Sentinel lack /v1/task/execute.
7. GAP: FRIDAY-Voice memory limit.
8. GAP: bridge authentication.
9. GAP: no task records for cross-agent assignment.
10. GAP: no alerting on crash loops; no documented rollback.
11. GAP: sniper secrets authentication unconfirmed (TASK-OPS-002).
12. UNVERIFIED: most per-agent internals (not yet read in full).


## 16. Cortex agent — source and runtime audit (PARTIALLY VERIFIED, 2026-11-08)
- Entry point: `Cortex/apps/api/src/cortex_api/main.py`; deployed service runs `uvicorn apps.api.src.cortex_api.main:app` on Server 2, port 8009. Service is active; observed 85.1 MB current memory with a 200 MB MemoryMax.
- Public health endpoint `/cortex/health` returned HTTP 200, version 2.1.0, evidence class `process_liveness` at 2026-11-08T17:56:22Z. This proves process liveness, not database or downstream readiness.
- FRIDAY task contract: `POST /v1/task/execute` is declared in `main.py` and depends on `verify_friday_token`; `friday_router.py` FRIDAY endpoints also use the FRIDAY service-key dependency. Key header: `X-Friday-Api-Key`.
- Human/operator auth: `auth.py` implements JWT validation and role hierarchy. Development bypass requires explicit `CORTEX_DEV_AUTH_BYPASS=true` and is disabled when `APP_ENV=production` or Render production is detected. `require_role` provides viewer/operator/admin tiers.
- Data/services: `config.py` configures an async SQLAlchemy engine/session and Redis pool. DSN selection can resolve Oracle, PostgreSQL, or SQLite based on runtime environment. The actual production DSN/backend and live Redis connectivity were not independently verified here. Schema bootstrap errors are logged but do not prevent app startup.
- Integrations declared: FRIDAY peer URL, Memora peer URL, SendGrid, Twilio, HubSpot, Stripe, and multiple marketing/analytics modules. Dependency declarations and code paths do not prove external credentials are provisioned or live provider calls succeed.
- Tests run on the connected workspace: `test_prompt9_cortex.py` 22 passed; `test_friday_integration.py` 27 passed; `test_peer_integration_contract.py` 9 passed, 2 skipped; `test_multi_tenant_security_isolation.py` 1 passed. `test_route_authorization.py` failed (1 failed, 1 passed) and enumerated more than 100 feature routes lacking recognized auth dependencies.
- GAP: marketing/content/decision/forecasting/risk/campaign/journey/segmentation/inbox feature routers had routes without route-level authentication dependencies in the audited source. This is a source-level access-control risk; live unauthenticated access was not tested. A method-aware RBAC remediation is proposed in PR #26; it is not deployed and requires passing CI plus review.
- GAP: several marketing/content modules still contain simulated campaign status/metrics rather than demonstrated external provider execution (for example, in-memory campaign state and comments indicating production API calls are future work). Do not represent these integrations as production-verified.
