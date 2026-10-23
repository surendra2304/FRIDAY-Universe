---
title: "FRIDAY UNIVERSE"
author: "Architecture and implementation continuation brief"
date: "18 October 2026"
lang: en-US
---

# 1. How the next chat must use this document

This is a continuation handoff, not a claim that FRIDAY Universe is already completely upgraded. For the current implementation, inspect GitHub repositories, default-branch SHAs, branches, pull requests and CI before changing code. The user's active scope is GitHub-only: do not access or edit the laptop, Oracle Cloud, or Dokploy. Revalidate every historical statement against current GitHub evidence.

## Non-negotiable instructions

**Current execution boundary:** this implementation is restricted to GitHub source, tests, workflows, branches and PRs. Do not access or edit local laptop files or Oracle Cloud/Dokploy infrastructure unless the user separately changes this scope.

1. Preserve the existing ten repositories and their Git histories. Do not recreate them, rewrite history or replace them with a monorepo.
2. Never run blanket `git reset --hard`, `git clean`, force-push, bulk checkout, or blind pull/merge commands. The local workspace has had substantial uncommitted work, deletions and untracked files.
3. Preserve and inspect the pre-reconciliation backup before changing local working trees.
4. Use feature branches and pull requests for substantive changes. Do not push directly to `main` merely because permission allows it.
5. Never claim completion without evidence from the exact commit: test output, CI state, container build, deployment health and/or demo integration results as applicable.
6. A green unit-test suite is not proof of a live service working. A merged PR is not proof of a production deployment. A healthy container is not proof that its database contains the correct data.
7. No live-money trading is authorized. Stratex must remain execution-disabled until the documented venue lifecycle and safety gates have been demonstrated in non-production testing.
8. Do not include secrets in prompts, PR bodies, logs, Markdown, PDFs, screenshots, Git history or tool output.
9. The main FRIDAY Universe chat coordinates all ten agents. Do not run parallel chats that edit the same repository or shared infrastructure at the same time.
10. Do not add unrelated products or agents. Work only on the ten repositories listed in this handoff.

## Evidence labels

Use these labels in every status report:

- **User-reported:** stated by the user or pasted from Antigravity, but not independently inspected.
- **Repository-verified:** supported by current code or configuration at a specified Git commit.
- **CI-verified:** workflow result observed for the exact commit SHA.
- **Runtime-verified:** inspected against the running service or host.
- **Demo-validated:** exercised against the real non-production broker/service lifecycle and reconciled with its authoritative state.
- **Unverified / blocked:** access or evidence is missing. State the blocker plainly.

# 2. Executive summary

FRIDAY Universe is a sovereign, self-hosted multi-agent system built from ten independent repositories. FRIDAY is the user-facing orchestrator, Inference is the canonical model/provider reasoning gateway, and Memora is the single long-term cross-agent memory authority. Eight other specialist capabilities (including Inference and Memora among the ten total systems) retain domain responsibilities, independent safety controls, service APIs and their own operational records.

The intended production deployment is on Oracle Cloud Infrastructure. The user's current reported production host is an AMD64 Always Free instance with approximately 1 GB RAM and 50 GB storage. The desired replacement is an ARM64 A1 Flex instance with 2 OCPUs and 12 GB RAM, provisioned through capacity retry/sniper scripts. Do not assume the ARM instance is already allocated: validate OCI state before migration. The user's longer-term plan is to delete the interim AMD host only after verified cutover and consolidate available block-volume capacity onto the ARM instance. The specification originally names a 150 GB target boot volume; the user's later plan refers to using up to 200 GB. The actual allowed boot-volume size and tenancy quota must be checked in OCI rather than assumed.

The user operates Dokploy for deployment and GitHub-to-server synchronization. All services should remain self-hosted on OCI; do not introduce Vercel, Render or Kubernetes as an unneeded layer. External AI APIs may still be used through Inference.

The major planned upgrade areas are:

- Move production persistence to PostgreSQL 18 after a safe compatibility and data migration plan.
- Give each agent a separate logical operational database and least-privilege PostgreSQL role.
- Keep Memora as the single place for durable cross-agent memories; do not copy every operational record into it.
- Standardize authenticated inter-agent contracts, deadlines, correlation IDs, errors, retries, idempotency and failure handling.
- Fix real security and reliability defects, including unsafe defaults, tenant isolation, TLS verification, secret exposure risks and fail-open verification.
- Make the ten services fit the 2-OCPU/12-GB server with resource budgets, bounded CPU-heavy work and sufficient OS headroom.
- Operate backups in private OCI Object Storage with encryption, retention, checksums and tested restoration.
- Work in a safe GitHub feature-branch/PR flow, then deploy the exact reviewed commit via Dokploy and verify the runtime independently.

The work done in the previous session is useful but incomplete. Some narrow PRs have been merged; Cortex remains blocked by failed CI; Futuris has an open PR with successful CI; Stratex has other open PRs. The current local MCP endpoint failed to connect during the preparation of this handoff, so its present availability must be checked before local edits or server actions.

# 3. Source of truth and known contradictions

## 3.1 Source documents

The attached `FRIDAY_UNIVERSE_MASTER_SPECIFICATION(2).md` is the primary architectural source. It defines the ten services, strict evidence and safety principles, the private `friday_mesh`, centralized Memora memory, one PostgreSQL cluster with ten logical databases, Redis/Qdrant components, Oracle deployment and encrypted backups.

The attached `Stratex_FRIDAY_Universe_Upgrade_Handoff_2026-10-18.pdf` is the specific continuation guide for Stratex. It is subordinate to the overall ecosystem specification and documents the order-management system (OMS), venue boundaries, risk gates, PR checkpoint, test matrix and next steps. Its PR status has to be refreshed because GitHub state changed after that PDF was produced.

The user's conversation instructions after the source specification are also authoritative, especially:

- The canonical name is **Inference**, not “AI Universe”.
- Memora is currently the single memory authority and is planned to use PostgreSQL for all agents' private, shared and universal memories.
- Each agent is intended to have a distinct operational database within a shared PostgreSQL server.
- The user wants implementation across all ten existing repos, not just a list of recommendations or a small number of unrelated patches.
- Work must be verified locally, in GitHub and on Oracle/Dokploy, with no unsupported claim of completion.
- The user explicitly rejected continuing Antigravity implementation in parallel while this direct ChatGPT workflow is coordinated. Antigravity may be used for setup/infrastructure support only when asked, but must not independently edit the same files concurrently.

## 3.2 PostgreSQL version conflict

The original specification mentions PostgreSQL 16. Later, the user decided to target PostgreSQL 18. Antigravity reported that `dokploy-postgres` was changed to `postgres:18-alpine` and that a backup of the previous volume was made, but the current bridge failure prevented independent live confirmation during this handoff.

Use PostgreSQL 18 as the intended target, but verify the running server, database list, extensions, application connections, volume mount and backup/restore path. A major image-tag change is not itself a database migration. If old major-version data exists, use a verified `pg_upgrade` or dump/restore process; do not assume PostgreSQL 16 data can safely be opened directly by PostgreSQL 18.

The PostgreSQL 18 Docker image changed its recommended data mount layout compared with older versions. Confirm the correct path and actual data directory for the exact image being used, and verify that the running container has not silently initialized an empty new cluster while leaving the old data volume behind.

## 3.3 Current vs. target is not the same

The source specification says Phase 0 was complete, with all repos lint-clean and tests passing. Later local audit results contradicted that statement: all ten repos had dirty working trees and several were behind GitHub `main`; PR checks also exposed failures. Treat “Phase 0 complete” as a claim from the source document, not as verified current state.

The repository descriptions, target port numbers and schema proposals in the specification are architectural targets; do not assume all existing code currently matches them.

# 4. The ten repositories and responsibilities

## 4.1 FRIDAY — main orchestrator and user-facing assistant

Repository: https://github.com/surendra2304/FRIDAY

FRIDAY owns user interaction, voice/multimodal flows, task decomposition and lifecycle, task dispatch, user-facing summaries, approval requests, tool-invocation audit and integration with the Windows desktop companion. The service entry point described in the specification is `friday.api.server:app` on internal port 10000.

It must orchestrate tasks but cannot bypass specialist safety gates. It must not become a second long-term memory store, or duplicate Inference's full provider-routing implementation. It may have local short-lived task state/checkpoints, but durable long-term memories flow through Memora.

Suggested operational records in `friday_db`: tasks, task steps, approval requests, tool invocations, correlation traces and audit log. Do not copy all of these into Memora; store selective durable lessons or context there where appropriate.

The Windows desktop companion is a separate runtime boundary: local microphone, screen capture, native Windows input and desktop automation stay on the user's Windows machine. The Oracle-hosted FRIDAY core should communicate with it using an authenticated outbound/private connection. Do not assume Windows-only dependencies work in Linux containers.

A dangerous legacy upgrade script was found and a PR was prepared to disable source rewriting, unpinned dependency upgrades, workflow overwrites and direct pushes to `main`. Verify the merged code and tests rather than reintroducing autonomous destructive updating.

## 4.2 Inference — canonical model/provider gateway

Repository: https://github.com/surendra2304/Inference

Inference is the sole authorized route to external LLM providers. It owns provider selection and fallback, API-key pools, quotas and token budgets, concurrency controls, circuit breakers, output validation, deliberation and evaluations. Specialist services should not scatter provider credentials throughout the ecosystem.

Use low-cost/simple routes for ordinary tasks and more expensive multi-model deliberation only when risk/complexity warrants it. Model agreement is never evidence by itself. Validate schemas and claims against sources where relevant.

Suggested `inference_db`: provider/model health, latency and cost statistics, routing events, quota/token budgets, evaluation outcomes and deliberation session metadata. Do not store provider secret keys in DB rows or logs.

A fix rejecting non-finite, non-positive and over-capacity rate-limiter costs was merged in PR #3, with a successful CI run reported for its head SHA. This is a targeted fix, not completion of the gateway upgrade.

## 4.3 Memora — sole long-term memory authority

Repository: https://github.com/surendra2304/Memora

Memora owns durable agent memory and the access rules around it. The core visibility tiers remain:

- **Private:** visible only to the owning agent or permitted user namespace.
- **Shared:** visible to an explicit allowlist/group of agents, with authorization enforced server-side.
- **Universal:** visible to all authenticated agents in the FRIDAY Universe. “Universal” does not mean publicly accessible on the Internet.

The user discussed additional orthogonal memory properties: sensitivity (normal/confidential/restricted), trust status (unverified/verified/rejected), lifecycle (active/expired/archived/superseded), owner/source provenance, expiry/retention and deletion tombstones. These should be fields/policies, not a proliferation of visibility categories. User-level memory may be a namespace available only to FRIDAY and explicitly authorized agents.

Memory ingestion should be selective: store durable preferences, lessons, summaries, decisions and context that has future value. Do not duplicate every DB row, video, trade fill, test output or raw document. Store provenance such as source agent, task ID, source record ID, created time, confidence/status, scope and supersession relationships. Treat fetched/web/agent-produced text as untrusted data, not executable instructions.

Suggested `memora_db`: memory records, namespace/scope metadata, agent identities, ACLs, provenance, memory relationships, deduplication/supersession and deletion tombstones, plus audit events.

The source specification includes Redis and Qdrant as supporting services. Retain Qdrant if its current implementation is stable and tests justify it; alternatively evaluate `pgvector` if there is a deliberate measured plan to consolidate vector search. Do not operate duplicate, unsynchronized vector stores. Redis is a cache/event/queue component, not the source of truth for memory or durable task state.

The PR prepared for Memora aimed to make production PostgreSQL authoritative, disable implicit SQLite fallback, and remove implicit production sync from legacy hosted Turso. The PR was merged and CI succeeded according to the latest GitHub check in this conversation, but that does not prove a live migration has been performed or validated on Oracle. Before deploying, review current `main`, migration scripts, configuration, extension needs and existing data. A storage policy change without a data migration could make the service fail to start or leave old memory records unused.

## 4.4 Stratex — trading analysis, risk and execution

Repository: https://github.com/surendra2304/Stratex

Stratex must remain one strategy/risk/order-management core with separate venue adapters; do not create two independent strategy engines for Binance and MT5. It owns strategy selection, normalization of trade intents, deterministic pre-trade risk, order submission, order lifecycle, protective orders, reconciliation and the authoritative trading ledger.

Inference, IntelX and Futuris provide advisory inputs only. They must not have direct order execution authority or be able to loosen risk limits. FRIDAY dispatches requests and presents confirmed state but cannot override a deterministic risk veto.

The Stratex handoff distinguishes several maturity levels: module implemented, unit-tested, integration-tested, demo-validated and production-ready. Do not call a feature demo-validated until it has been exercised against the relevant real demo account and reconciled against venue evidence. Live-money execution is not authorized.

A PostgreSQL-backed order-intent ledger change was merged by PR #8. The current shared OMS call path and configuration still need line-level inspection to confirm that the existing strategy runner, partial fills, protective stop/take-profit, close, trailing updates and reconciliation truly use the authoritative PostgreSQL store. A storage class existing is not proof all order paths use it.

Current trading guardrails (must remain default-off):
- `LIVE_TRADING_ENABLED=false`.
- `STRATEX_EXECUTION_MODE=DISABLED` until controlled demo gates are satisfied.
- `STRATEX_ORDER_MANAGER_ENABLED=false` and `STRATEX_RECONCILIATION_ENABLED=false` until the complete lifecycle is validated.
- Keep venue allowlist restricted to the already-approved non-production venue. Do not add MT5 until its full demo workflow is accepted.
- Binance Demo Trading credentials and endpoints must remain distinct from legacy Testnet credentials; never fall back to live endpoints/keys.
- MT5 requires an authenticated private bridge to an always-on Windows terminal, confirmed demo account status and broker-native symbol/contract/lot/margin calculations. The user's laptop cannot be required to stay on for production MT5 bridging.
- Persist intent before submit, use stable client order IDs, prevent duplicate submits, mark ambiguous results `UNKNOWN`, then resolve using venue evidence. Do not blindly retry a timeout or fail over a single order to another venue.
- Confirm protective exits are live before reporting a position as protected. Reconcile sibling SL/TP orders and venue state after an exit or restart.

The Stratex handoff reports PR #7 open for portfolio-wide risk gating and PR #9 open for a documentation handoff. At the latest query in this conversation, PR #7 had head SHA `2231f456792a9d3fd146d248d934fac7dc67be61`, but the GitHub connector returned no PR-triggered workflow run for that exact SHA. Do not assume green. PR #9 was open with CI success, but is a documentation handoff, not proof the trading engine is complete. Recheck both before touching Stratex because another ChatGPT session has also worked on it.

Suggested `stratex_db`: durable order intents and state transitions, orders, venue order IDs, fills, positions, append-only ledger entries, fees/funding/swap, portfolio/risk snapshots, reconciliation events and audit records. Treat the exchange/broker as the source of truth for actual order/position state, while PostgreSQL is the durable local record of intent and observations; reconcile the two after failures.

## 4.5 Forge — autonomous software engineering

Repository: https://github.com/surendra2304/Forge

Forge plans coding tasks, writes proposed changes, runs builds/tests and produces evidence-based verification. All code execution must occur in isolated workspaces/containers with path confinement, bounded CPU/memory/time, restricted filesystem mounts, restricted network access and no Docker socket exposure. The host must remain protected even if generated code is malicious.

A task must not be considered verified if the checker found no workspace paths or did not actually execute its checks. A fix for the no-workspace false-positive condition was merged in PR #3 with successful CI reported. That is a focused reliability fix, not a complete Forge upgrade.

Suggested `forge_db`: build jobs, DAG/task state, verification runs, artifact manifests, test outcomes, repair attempts and workspace metadata. Large build outputs remain as files/artifacts with integrity metadata, not giant DB blobs.

## 4.6 Cortex — governed web operations and multi-tenant business workflows

Repository: https://github.com/surendra2304/Cortex

Cortex serves the web/dashboard, tenant-scoped visitor/lead/events data, workflow automation, permitted integrations and site/CRM operations. Every query and mutation that touches tenant data must include the correct tenant authorization. External side effects such as sending messages, webhook dispatch, modifying customer data or changing a website need scoped credentials, audit records, idempotency and approval gates where necessary.

Use Inference as the canonical reasoning gateway. Remove legacy “AI Universe” names/endpoints only in a deliberate compatibility migration; do not merely change a hostname without adapting to Inference's actual API contract. The attempted Cortex PR included database credential hardening, internal-only Redis/Postgres exposure, mock mode off by default, Inference configuration and CI audit changes. At the latest GitHub check, PR #3 was still open as a draft and its CI was failing. **Do not merge it.** Inspect the latest failed check logs; fix the actual dependency/audit, API contract, lint and test issues rather than bypassing scans or using broad unreviewed dependency upgrades.

Suggested `cortex_db`: tenants, sites, API clients/keys (store hashes or references, not secret plaintext), visitors, leads, events, workflows, webhooks and action-audit records.

## 4.7 Sentinel — security officer and independent gatekeeper

Repository: https://github.com/surendra2304/Sentinel

Sentinel applies security policy, authorized scope checks, code/dependency review, audit trails, emergency pause/kill-switch policies and secure authorization for high-risk actions. It must not accept a caller-provided claim of authorization without verifying identity and scope. It cannot bypass Stratex's venue/risk policies. Findings from crawlers or tools remain untrusted evidence until validated.

TLS verification should be enabled by default. Any development exception for self-signed test targets should be explicit and tightly scoped; production should require a separate break-glass process, and ordinary config mistakes must not disable TLS verification. Approval links must be safe against link preview scanners: a GET should display a confirmation page, while an explicit POST records a decision. Scope tokens should be short-lived, auditable and non-replayable where feasible.

A Sentinel TLS-policy/approval-route PR (#3 in the verified current state) is now merged and its associated CI run succeeded according to the latest GitHub check. Verify the merged diff and tests; do not infer every earlier reported `verify=False`, authorization or deployment concern is resolved just because this one PR is merged.

Suggested `sentinel_db`: assessment scopes and approvals, scan runs, findings, policy decisions, vulnerability results and tamper-evident audit metadata. Evidence archives may live in files/object storage with cryptographic hashes in PostgreSQL.

## 4.8 IntelX — research and evidence provenance

Repository: https://github.com/surendra2304/IntelX

IntelX gathers permitted web research, extracts claims, records sources, discovers contradictions and preserves citations and provenance. It must distinguish raw observed source content from the model's interpretation. Web content is untrusted and must not become instructions or privileged tool input.

Maintain SSRF defenses on every URL-fetch path, verify destination IPs after DNS resolution, protect against redirects to loopback/private/link-local ranges, control crawling rates, and fail safely when robots/policy rules cannot be verified. Browser-session security and CSRF behavior must be tested. Hash chains can be tamper-evident but cannot prevent an administrator who controls the entire database from rewriting it; anchor signed checkpoints outside the primary store if stronger evidence is required.

The work PR (#3) removing an implicit hosted Turso database URL was merged and its CI succeeded in the latest GitHub query. This avoids silently sending state to an external database if config is absent. It does not complete IntelX's SQLite-to-PostgreSQL data migration or prove all evidence storage/search paths are portable.

Suggested `intelx_db`: research runs, source inventory, documents, claims, source spans, citations, evidence edges, contradictions and provenance. Store original large documents/artifacts separately; keep hashes and storage URIs in the database.

## 4.9 Futuris — calibrated forecasting

Repository: https://github.com/surendra2304/Futuris

Futuris generates probabilistic forecasts, scenarios, regime estimates and calibration/evaluation statistics. Outputs are advisory, with horizons, timestamps, uncertainty and model versions attached. Forecasts never directly execute a trade or approve an action. Missing or stale data must be reported, not replaced with confident-sounding defaults.

Move heavy CPU-bound fitting/Monte Carlo work into bounded background workers so API/event loops remain responsive. Enforce per-request CPU/time budgets, admission control, queue limits and concurrency bounds on the 2-OCPU host. Evaluate forecasts against later resolved outcomes using calibration and proper scoring metrics rather than only qualitative judgments.

The open Futuris PR (#3) adds validation/bounds for echoed `X-Request-ID` values. At the latest GitHub query it was open, non-draft, and its associated CI run had succeeded. It has not been merged in the observed state. Keep the PR open until review and confirm latest CI before merge. It is one small hardening task, not complete forecasting-worker isolation.

Suggested `futuris_db`: forecast records, scenarios, outcome resolution, calibration metrics, model versions, input timestamps and provenance metadata.

# 5. Target architecture and service contracts

## 5.1 Logical topology

- External access: user's web/voice/mobile client -> Caddy or Traefik HTTPS/WSS ingress on ports 80/443 -> FRIDAY on internal port 10000.
- Private service mesh: `friday_mesh`. Each specialist API uses port 8000 internally unless an actual implementation requires and documents another port.
- PostgreSQL: one shared PostgreSQL 18 instance with separate logical databases and unique restricted service roles.
- Redis: one shared instance where needed, with access control, bounded memory, and key/namespace discipline.
- Vector store: current Qdrant may remain for Memora if needed; evaluate `pgvector` only through measured tests.
- Deployment: Dokploy manages builds and service deploys from reviewed GitHub commits. Dokploy is not a substitute for CI, secrets governance or runtime checks.
- Backups: encrypted copies to a private OCI Object Storage bucket separate from VM boot/block volume use.

No database, Redis, Qdrant or specialist API ports should be published publicly. Only intended reverse-proxy ports should be externally reachable. Internal DNS, authentication, network membership and service identities must be verified from the actual production stack.

## 5.2 Standard task envelope

Define and test one common service envelope, adapted by each API rather than forcing every domain into one giant schema. It should include:

- `task_id` and idempotency key when the operation can be retried.
- `correlation_id` / trace ID propagated through all downstream calls.
- authenticated caller identity and intended audience/target service.
- schema/version and explicit operation name.
- deadline/timeout and bounded resource budget.
- untrusted-input labels/provenance where useful.
- request payload and typed domain constraints.

Use consistent response/error envelopes with machine-readable error code, retriable flag, safe message, correlation ID and optional validated result. Do not echo credentials, raw secret payloads or untrusted model-generated commands.

## 5.3 Reliability behavior

- Set connect/read/total timeouts for every HTTP/database/venue operation.
- Use bounded retries with jitter and respect idempotency. Never retry non-idempotent operations blindly.
- Use circuit breakers, queue depth limits and a global semaphore for expensive work.
- Implement cancellation and shutdown behavior so task state persists and jobs stop cleanly.
- If Memora is unavailable, do not falsely claim a memory write succeeded; queue a retry if designed, or report the limitation.
- If Inference is unavailable, allow a deterministic/basic fallback for suitable tasks only; do not endlessly retry or silently switch to an unconfigured external provider.
- If Sentinel can't verify a safety requirement, block delivery or sensitive execution.
- If IntelX cannot verify source policy/claim evidence, label uncertainty and do not treat the result as fact.
- If Futuris is unavailable or stale, Stratex must not treat missing analysis as permission to trade.
- If Stratex cannot reconcile an order, mark the order uncertain and prevent duplicates; do not report a success/failure unsupported by venue evidence.

# 6. Database architecture and migration requirements

## 6.1 One PostgreSQL instance, ten logical databases

Use a single PostgreSQL 18 server to conserve memory and operational overhead on the one VM, with these database/role pairs:

| Logical database | Role | Authoritative operational data |
|---|---|---|
| `friday_db` | `friday_user` | Tasks, step state, approvals, invocations, orchestration audit |
| `inference_db` | `inference_user` | Provider metrics, routing events, usage budgets, evaluation results |
| `memora_db` | `memora_user` | Scoped long-term memory, ACLs, provenance, lifecycle, deletion tombstones |
| `stratex_db` | `stratex_user` | OMS intents, order state, fills, positions, ledger, risk and reconciliation records |
| `forge_db` | `forge_user` | Build jobs, DAG/checkpoints, verification evidence and artifact metadata |
| `cortex_db` | `cortex_user` | Tenant records, sites, leads, events, workflows and action audits |
| `sentinel_db` | `sentinel_user` | Scopes, assessments, scans, findings, policy decisions and audit records |
| `intelx_db` | `intelx_user` | Research runs, sources, documents, claims, evidence relationships and citations |
| `futuris_db` | `futuris_user` | Forecasts, scenarios, outcome results, calibration and model versions |
| `vyralx_db` | `vyralx_user` | Video production tasks, projects, scenes, media assets, render jobs, publishing checkpoints and provenance metadata |

Each service gets only its database credentials. No agent role is a superuser. Do not grant cross-database write access as a shortcut. The only supported cross-agent memory flow is through Memora's authenticated API. Cross-agent operational tasks should use the service API, not direct SQL into another agent's database.

Use database migrations (prefer Alembic where supported), explicit connection pool limits, statement/connection timeouts, and separate test databases. A PostgreSQL connection URL alone does not mean the app actually uses PostgreSQL; inspect every startup path and query backend, including fallback logic and test configuration.

## 6.2 Safe migration plan per service

1. Inventory all SQLite files, schemas, tables, indices, triggers, WAL state, implicit types and hard-coded SQLite SQL/search functions.
2. Back up every database and verify that the backup can be opened/restored. Do not commit DB files or secrets.
3. Create each PostgreSQL database and least-privilege role; store connection URLs privately in Dokploy environment/secret configuration.
4. Build idempotent, versioned migrations. Translate SQLite-specific features (for example FTS5, `PRAGMA`, `BEGIN IMMEDIATE`, SQLite upsert idioms, date/JSON handling, `lastrowid`, boolean types) deliberately.
5. Test the migration against a copy of actual data, not only an empty DB. Record row counts, key invariants, foreign keys, uniqueness and representative queries.
6. Do a planned cutover: stop writes or use a well-defined migration window, export, import, validate, and switch the configured DSN. Do not allow uncontrolled dual-writes to SQLite and PostgreSQL.
7. Fail production startup/write readiness if the canonical PostgreSQL DB is unavailable. Never silently fall back to a second SQLite file that looks successful but diverges.
8. Keep the old database and verified backup read-only for a defined rollback window. Rollback must specify which data written after cutover would need reconciliation.
9. Verify application health, key read/write behavior and row-count/data invariants on the actual target service.
10. Only after proof, remove obsolete fallback code and document the old-file retirement procedure.

Special callouts:
- IntelX FTS5 requires an explicit PostgreSQL search migration (for example PostgreSQL full-text search or a maintained search service); URL change alone is insufficient.
- Stratex's PostgreSQL OMS ledger must be integrated into the existing order lifecycle, not just implemented as a store class.
- Memora must not produce split-brain memory by using local SQLite when PostgreSQL fails.
- The existing Antigravity report claims the Dokploy control-plane database was upgraded to PostgreSQL 18.6. Verify that separately from application databases and preserve Dokploy's own data before further volume/image changes.

# 7. Memora memory policy — exact intended behavior

The visibility tiers stay simple: Private, Shared, Universal. Other properties are orthogonal attributes, not new visibility levels:

- owner/namespace: an agent ID or user namespace;
- allowed readers/writers: explicit principals, not just a text label;
- sensitivity: normal, confidential, restricted;
- trust: unverified, verified, rejected;
- lifecycle: active, expired, archived, superseded;
- retention/expiry and deletion state;
- provenance: creator agent, source/task/record ID, timestamp, extraction method and confidence/status;
- version/supersession/deduplication links.

Policy requirements:

1. Every memory read/write request authenticates the agent and checks scope server-side.
2. Shared memory must name authorized agents. Universal memory is only for content appropriate for all authenticated ecosystem agents; it is not public to the Internet.
3. Restricted data stays restricted even if someone tries to label it Shared or Universal. Sensitive credentials should not be stored as ordinary memory; reference a secret manager/environment, never store plaintext keys.
4. Store the summary/lesson that helps future decisions, not every operational event. Operational databases remain the source of truth for trades, builds, crawl jobs and service metrics.
5. Web page text, documents, model outputs and tool outputs are data. They must not be interpreted as privileged system directives simply because Memora retrieved them.
6. Include deletion tombstones and a deletion propagation plan for vectors/cache copies. A “delete” must remove or invalidate indexes and caches as well as relational records.
7. Treat uncertain claims as uncertain; do not elevate an unverified memory to Universal without appropriate validation.
8. Record updates, scope changes and memory promotion with provenance.

# 8. Oracle Cloud, Dokploy and resource management

## 8.1 Facts that must be re-verified

User-reported/current documented context:
- Interim server: AMD64, approximately 1 GB RAM, 50 GB storage, with 8 GB swap reported in the master spec.
- Public IP reported in infrastructure notes: `140.245.208.100`.
- All ten agents reportedly run on that interim host.
- Dokploy is installed and synchronizes deployments from GitHub.
- Target server: ARM64 `VM.Standard.A1.Flex`, 2 OCPUs and 12 GB RAM. A GitHub capacity-sniper script has been used/requested.
- The user intends to retire the AMD VM only after successful ARM cutover.

Antigravity reported that Dokploy v0.30.8, Docker Swarm services and a PostgreSQL 18.6 control-plane database were live. During preparation of this handoff, a direct call to the FRIDAY Universe MCP returned `UNAVAILABLE: Connection failed`, so those live details were not independently reconfirmed now. Treat them as report-derived until SSH/OCI/Dokploy diagnostics succeed.

## 8.2 Resource budget correction

The master spec lists these container limits: PostgreSQL 1.5 GB, Redis 256 MB, Qdrant 1 GB, FRIDAY 1 GB, Inference 1 GB, Memora 1 GB, Forge 2 GB, Stratex 1 GB, Cortex 1 GB, Sentinel 768 MB, IntelX 768 MB and Futuris 768 MB. Those values add to approximately **12.06 GB**, not the ~11 GB claimed in the specification. They already exceed the 12 GB host target before accounting for the OS, Docker, reverse proxy, page cache, sidecars or spikes.

Do not copy these caps as the final plan. On the target ARM server:

- Measure memory/CPU after each stack is started; capture idle and peak RSS, restarts, OOM kills, queue depth and response latency.
- Reserve a realistic amount for Linux/Docker, caches and transient spikes. Start with a conservative service cap budget around 8–9 GB total and tune from measurements, not as a guarantee.
- Keep one global heavy-job slot for CPU-intensive builds, forecasting/fitting, deep scans/crawls and FFmpeg-like work where relevant. Do not let all agents spawn heavy workers at once.
- Use bounded process/thread pools, queue maximums, job deadlines and cancellation.
- Prefer API-hosted LLMs through Inference. Do not attempt to host large LLMs locally on 2 OCPUs.
- Start with one PostgreSQL instance and only supporting services whose measured need justifies them.

## 8.3 ARM64 compatibility

Before migration, build and smoke-test `linux/arm64` images. Check native Python wheels, `psycopg`, `asyncpg`, NumPy/SciPy/statsmodels, browser tools, scanner binaries, Qdrant, Redis and any system packages. Do not assume a successful AMD64 image is ARM-compatible.

Keep configuration and deployment manifests architecture-aware. Pin versions and lockfiles; do not upgrade every dependency to “latest” during an infrastructure cutover. Test a disposable copy first.

## 8.4 Dokploy deployment discipline

For each application record:
- repository and exact branch bound to Dokploy;
- build context and Dockerfile;
- environment/config source (secrets outside Git);
- volumes and network attachments;
- health/readiness check;
- exact deployed commit/image digest;
- log locations and rollback target.

A merge to `main` may automatically trigger deployment. Therefore, before any merge, determine whether it will affect live production. CI success is necessary but not sufficient. Prefer a deliberate staged rollout, one service at a time, starting with low-risk services and verifying status after each deployment.

Avoid publishing backend ports. Internal services must be reachable by service DNS on the private network. Only the reverse proxy should serve the required public HTTPS endpoints. Do not expose PostgreSQL 5432, Redis 6379 or Qdrant ports to the internet.

# 9. Backup, storage and disaster recovery

The user asked to avoid backing up to the interim AMD VM because its local storage is limited and wants backups on separate OCI-managed storage. The intended destination is a private OCI Object Storage bucket, which is separate from the VM's boot/block-volume allocation. Confirm the real tenancy/region/allowance and existing bucket before using a bucket name found in docs.

Do not assume Object Storage capacity is unlimited or that MySQL/NoSQL databases are good general backup-file destinations. Object Storage is the better fit for encrypted database dumps and archive objects; a database service is not a backup file store.

Backup design:

1. Periodically create consistent PostgreSQL backups for each application DB and for required cluster-level globals/roles. Prefer separate artifacts per service plus a documented full-recovery procedure.
2. Encrypt before upload using a key controlled separately from the storage bucket. Keep key material out of the repository and out of chat.
3. Use versioned/unique object names and include timestamp, database identifier, schema/migration version, compression, checksum and backup type in a manifest.
4. Verify object upload, checksum and expected size. Upload success alone does not establish that a backup is restorable.
5. Define retention based on actual storage quota and database growth; use lifecycle rules only after a successful restore test and retention review.
6. Weekly (or on a defined schedule) restore the backup into an isolated scratch instance/container, run database integrity/application smoke tests, and record evidence. Never restore over production as a test.
7. Include PostgreSQL data, Memora's Qdrant index if still used, required config/manifests and non-regenerable application artifacts in the recovery design. Keep secrets themselves in a separate secure configuration source.
8. Back up Dokploy/application volume mappings and note which volumes are persistent; don't accidentally restore data into an ephemeral container filesystem.
9. Define RPO/RTO (acceptable data loss and recovery time) with the user if not already specified.
10. The AMD host can be retired after ARM cutover; it is not required to be the only backup target.

Storage sizing sequence:
- inspect `df -h`, `du` by persistent volume, PostgreSQL growth, Qdrant size, Docker image cache, logs and local artifacts;
- verify OCI boot/block-volume quota in the console;
- verify Object Storage quota separately;
- size volume and retention based on measurements;
- increase storage only when required, and never delete the old boot volume before a tested restore and cutover acceptance.

# 10. Local laptop-to-ChatGPT MCP bridge

## 10.1 Reported connection architecture

Antigravity reported it created `D:\ChatGPT\server.py`, launched it using `D:\ChatGPT\.venv\Scripts\python.exe`, exposed localhost port 8000 through an ngrok URL, and created a bridge report. It said the MCP endpoint was:

- Reported MCP endpoint: `https://kite-trouble-decency.ngrok-free.dev/mcp`
- Reported health endpoint: `https://kite-trouble-decency.ngrok-free.dev/health`
- Reported launcher: `C:\Users\Surendra\Desktop\Start_ChatGPT_Bridge.bat`
- Workspace root: `D:\FRIDAY Universe`
- User's plugin page (not the MCP endpoint): `https://chatgpt.com/plugins/plugin_asdk_app_6ad3d28abed48191bfaaea36dc03ee8e`

The actual runtime connection failed with an `UNAVAILABLE: Connection failed` error during preparation of this handoff. Therefore the endpoint, tunnel, authentication and tool discovery must be tested in the new chat before assuming local edit or server access works. A permanent plugin-page URL is not the same as the underlying MCP URL; verify both independently.

## 10.2 Tools Antigravity reported as implemented

- System diagnostics: `get_system_info`.
- Workspace files: `list_workspace`, `read_workspace_file`, `edit_workspace_file`, `search_workspace`.
- Git: `git_status`, `git_branch_info`, `git_diff`, `git_log`, `git_fetch_remote`.
- Tests: `run_workspace_test`.
- OCI: `oci_check_auth`, `oci_list_instances`, `oci_get_instance_details`.
- SSH: `ssh_run_diagnostic` with named read-only profiles such as summary, memory, disk, Docker services.
- Dokploy/fleet: `dokploy_check_health`, `dokploy_list_apps`.
- Action gate: `request_action_authorization`.

The later tool interface visible to ChatGPT exposed generic tools such as `get_system_info`, `list_directory`, `read_file`, `write_file`, `execute_terminal_command`, and `run_python_code`; do not assume the larger 15-tool inventory is currently callable. Test every tool in the active connector session and distinguish AVAILABLE / FAILED / NOT CONFIGURED / NOT TESTED.

The reported bridge said it blocks traversal outside `D:\FRIDAY Universe`, protects backup ZIPs, redacts secrets, and requires authorization before state changes. Treat those as reported implementation claims until tests against the current `server.py` confirm them. Regex redaction is not sufficient by itself to guarantee secrets can never leak; tools must avoid reading/returning credential values in the first place.

## 10.3 Startup and connection recovery checklist

On the user's return:

1. Do not immediately start a source-code edit. First ask whether Antigravity is stopped and confirm no agent is writing the same repositories.
2. Check whether the bridge process is running and the ngrok tunnel is active.
3. Test the health endpoint from Windows and test the MCP tool discovery from ChatGPT.
4. Invoke a harmless read-only `get_system_info`, list the workspace and read a benign file.
5. Use a harmless terminal command to verify exit code/output.
6. Inspect the ten-repository Git state without editing anything.
7. Verify access to OCI, SSH and Dokploy separately. Local MCP success alone does not prove cloud tools are connected.
8. If disconnected, inspect bridge logs, process state, port 8000, ngrok URL/auth configuration and plugin server URL. Do not paste bearer tokens or private keys into chat.
9. Confirm path confinement and authorization gate with benign negative tests; do not attempt destructive operations as a “test”.
10. Confirm bridge uses a stable trusted URL/tunnel and is authenticated; avoid public unauthenticated shell/management endpoints.

The user does not need to grant unrestricted access to the entire laptop. Workspace-scoped file access, approved commands and explicitly authorized infrastructure tools should be enough.

# 11. Local working tree and recovery snapshot

An earlier successful bridge inspection ran read-only Git commands over all ten local repositories. It found every repo dirty and several branches behind `origin/main`. A pre-reconciliation snapshot was created:

- `D:\FRIDAY Universe\state_backups\pre-reconciliation-20261018-010125.zip`
- matching snapshot directory: `D:\FRIDAY Universe\state_backups\pre-reconciliation-20261018-010125`

The snapshot includes tracked working-tree patches, status records, a manifest and copies of untracked files. Never delete or overwrite it without a verified independent backup.

Observed at the initial check (this is historical, not guaranteed current):

| Repo | Local branch | Dirty status entries then | Local vs GitHub observation then |
|---|---|---:|---|
| FRIDAY | `main` | 86 | 6 commits behind `origin/main` |
| Inference | `main` | 6 | same commit as fetched `origin/main` |
| Memora | `main` | 31 | same commit as fetched `origin/main` |
| Stratex | `main` | 7 | 191 commits behind `origin/main` |
| Forge | `main` | 4 | same commit as fetched `origin/main` |
| Cortex | `main` | 84 | 1 commit behind `origin/main` |
| Sentinel | `main` | 27 | 1 commit behind `origin/main` |
| IntelX | `main` | 18 | same commit as fetched `origin/main` |
| Futuris | `main` | 16 | same commit as fetched `origin/main` |

Later, Antigravity's report contained different change counts and claimed 100% preservation. Because local edits continued and the bridge became unavailable, neither count set should be assumed current. The next chat must run fresh `git status --short`, `git diff`, `git ls-files --others --exclude-standard`, fetch refs safely, and compare against the snapshot before reconciling anything.

Important local actions to inspect:
- `docs/RECONCILIATION_AUDIT_REPORT.md` was created by Antigravity.
- Antigravity also reported creating `docs/FRIDAY_UNIVERSE_MASTER_CREDENTIALS.pdf` and `.md` that may contain sensitive secrets/connection details. **Do not attach these files to a new chat or commit them.** Inspect Git tracking and history without dumping the secrets into output. If actual secrets were ever pushed or exposed to untrusted systems, rotate the affected credentials. A `.gitignore` entry does not remove secrets already present in Git history.
- Preserve any untracked files, including reported capacity-sniper workflow and Sentinel gatekeeper files, until their purpose and status are understood.

# 12. GitHub state and work already performed

The following is the latest status queried through the connected GitHub integration for this handoff on 18 October 2026. Always refresh it on resume.

## 12.1 Ten-repository PR matrix

| Repository | PR | Current state at last query | Latest associated CI observed | Next action |
|---|---:|---|---|---|
| FRIDAY | [#3](https://github.com/surendra2304/FRIDAY/pull/3) | Merged | Success | Review the merged diff; verify no conflict with local uncommitted work; confirm whether fix still matches intended behavior. |
| Inference | [#3](https://github.com/surendra2304/Inference/pull/3) | Merged | Success | Review exact merged code/tests; run local contract/regression tests. |
| Memora | [#3](https://github.com/surendra2304/Memora/pull/3) | Merged | Success | Do NOT assume live SQLite/Turso data was migrated. Inspect current DB policy/migrations and test a data-preserving PostgreSQL cutover. |
| Stratex | [#8](https://github.com/surendra2304/Stratex/pull/8) | Merged | Success | This was a separate branch for PostgreSQL OMS order-intent storage. Inspect actual order path integration; continue coordinated with PRs #7 and #9. |
| Forge | [#3](https://github.com/surendra2304/Forge/pull/3) | Merged | Success | Review result: missing workspace must fail verification rather than false-pass. Run whole Forge test suite locally. |
| Cortex | [#3](https://github.com/surendra2304/Cortex/pull/3) | Open, draft | Failure | **Do not merge.** Resolve latest CI failures and re-run against exact final head. Do not silence vulnerability audits. |
| Sentinel | [#3](https://github.com/surendra2304/Sentinel/pull/3) | Merged | Success | Review TLS and approval-route diff. Verify all remaining TLS bypasses, authorization and API behavior; one PR does not close all security findings. |
| IntelX | [#3](https://github.com/surendra2304/IntelX/pull/3) | Merged | Success | Review configuration change, then plan actual DB/search migration and data validation separately. |
| Futuris | [#3](https://github.com/surendra2304/Futuris/pull/3) | Open, ready for review | Success | Review and decide merge only after diff/test inspection. It hardens the echoed request ID; it is not the full worker-isolation change. |
| VyralX | — | Added to the ten-agent architecture after this historical snapshot | Not checked in this historical matrix | Refresh current PRs, task-3 patch status and CI before changing code. |

The CI statuses above were fetched for the associated PR head SHAs, not proof of production runtime health. For Cortex's open PR, the CI run was explicitly failed; the next chat must inspect its failing logs and exact SHA. For Futuris, CI was successful but the PR remained unmerged. Do not say it merged unless live GitHub confirms it.

## 12.2 Stratex PRs managed by another workstream

The Stratex handoff says:
- PR #5 and #6 were previously merged (documentation/CI fix related to a testnet-gate error).
- PR #7 remains open: [portfolio-wide risk gate for demo OMS](https://github.com/surendra2304/Stratex/pull/7). At the last query it had head SHA `2231f456792a9d3fd146d248d934fac7dc67be61`; the GitHub workflow-run connector returned no PR-triggered run associated with that exact SHA. Do not infer green.
- PR #8 is merged: [PostgreSQL-backed order-intent ledger](https://github.com/surendra2304/Stratex/pull/8).
- PR #9 is open: [continuation handoff and upgrade roadmap](https://github.com/surendra2304/Stratex/pull/9), with a successful CI run at the observed head, but it is a documentation PR.

Another FRIDAY Universe ChatGPT session has also been working on Stratex. Therefore, inspect recent commits, PR #7/#9, and branch ownership before editing. Never overwrite its branch or re-implement its work blindly. Keep any further Stratex code work on a new branch from current `main` and coordinate through explicit status updates.

## 12.3 Scope of the merged changes

The merged code from this session consists of narrow safety/reliability fixes, not complete agent upgrades:

- FRIDAY: disabled a legacy upgrade path that could rewrite source files, upgrade dependencies unpinned, overwrite workflows and push directly to `main`; added regression tests (review actual main after merge).
- Inference: rejects bad/impossible rate-limiter costs to avoid hangs and concurrency-slot leaks.
- Memora: hardens production database authority and fallback/legacy hosted DB selection. This must be followed by safe migration/verification.
- Stratex: adds PostgreSQL-backed order intent ledger foundations and fail-closed config when OMS/reconciliation enabled without its PostgreSQL URL. The full existing trading path may still bypass this store.
- Forge: no workspace evidence is a failed verification, not a pass.
- Sentinel: default-on TLS policy and safer POST-only approval decisions were added in the PR. Review the merged diff and test link-preview/expired-token behavior.
- IntelX: removes an implicit remote Turso database URL. It does not move existing SQLite data or port all SQLite-only query/search operations.
- Cortex: attempted Compose/auth/CI hardening is in a draft with failing CI; do not merge.
- Futuris: bounded request ID validation was added in an open PR with successful CI; do not call it merged until confirmed.

Do not count PRs or lines of code as the success metric. The target is working and tested behavior, correct integration and safe deployment.

# 13. Mistakes made in the previous work and how not to repeat them

1. **Small patches were mistaken for the requested full upgrade.** The user asked for a coordinated engineering implementation across all ten repositories. A few targeted fixes and PRs are not the complete deliverable.
2. **PR creation became a proxy for completion.** A PR is just a review container. Each phase must have scope, acceptance tests, change summary, dependency map, validation and runtime evidence as relevant.
3. **Changes were made through GitHub without a full local reproduction loop.** This caused CI failures and limited confidence in integrations. Now that a local MCP is configured, use it to inspect exact code, run tests, inspect diffs and verify changes. However, the current bridge is failing; do not assume access is live.
4. **Repositories were edited before the entire call path was mapped.** This is especially dangerous for Stratex, Memora migration, Cortex/Inferences contract and service deployment. Map existing entry points and call sites first.
5. **CI checks were sometimes made red by changes and not all failures were resolved before reporting.** Fix errors introduced by the PR first, inspect baseline failures separately, and do not relax blocking security/testing rules to get green.
6. **The current local worktree contains uncommitted changes.** Any generic pull/rebase/reset can lose local work or create a dangerous merge. Back up, inspect and reconcile one repo at a time.
7. **Memory/DB guidance risked duplicating storage.** Keep operational data authoritative in each agent DB; Memora stores selected cross-agent memory, not every raw row.
8. **PostgreSQL version upgrade was too casually described.** A major image-tag change must be backed by a proper data migration and verified restore, not just a healthy container.
9. **Infrastructure validation was claimed from an Antigravity report.** The bridge's current failure means live OCI/SSH/Dokploy facts are not independently verified in this chat. Clearly label claims and test each connection.
10. **Resource budgets in the source specification are overcommitted.** The container caps listed in the spec sum to about 12.06 GB while the target host has 12 GB. Rebudget with host headroom and measured workloads.
11. **Sensitive credentials dossier risk.** Antigravity reported a local credentials PDF/Markdown with passwords/API keys/tokens. It must never be placed in a handoff PDF, copied into prompts or committed. Keep secrets in private configuration and rotate if exposed.
12. **Changes from a second Stratex session can overlap.** Coordinate, inspect current branches and avoid simultaneous ownership of `Stratex` shared files or migrations.

# 14. Prioritized upgrade roadmap and acceptance criteria

Execute in phases. Each phase ends in a reviewable diff, explicit test evidence and a checkpoint; do not ask the agent to “upgrade everything” in one unbounded run.

## Phase 0 — Recovery and truth baseline (first task on resume)

- Confirm MCP health and callable tools.
- Inspect all ten local `git status --short`, `git diff`, untracked files and current `HEAD`.
- Check the recovery ZIP is present and readable. Make a second backup before reconciliation if any further actions have happened.
- Fetch GitHub refs safely; compare local/main with origin/main without changing working files.
- Read current merged PR diffs and refresh all open PRs/CI, especially Cortex #3, Futuris #3, Stratex #7/#9.
- Confirm no Antigravity or other chat is editing simultaneously.
- Audit credential files/tracking without displaying their contents.
- Verify OCI, SSH, Dokploy and MCP separately.

Acceptance: a repository-by-repository manifest with exact SHAs, dirty counts and paths, divergence, open PRs, latest CI and an explicit backup/restore path. No source changes yet.

## Phase 1 — Security blockers and deterministic safety

Fix the actual high-risk code/config issues confirmed by latest main:

- Remove hard-coded credentials, insecure default tokens and mock-mode defaults from production deployment config.
- Fix all tenant-scoped query/mutation paths in Cortex and add cross-tenant regression tests.
- Verify outbound TLS by default in Sentinel and remove unjustified `verify=False` paths; authorize controlled exceptions explicitly.
- Ensure Sentinel's approval action cannot be triggered by link preview GET; only explicit POST with proper CSRF/auth semantics should mutate approval.
- Harden Forge sandbox path confinement and subprocess isolation; no Docker socket, unrestricted host mount or shell escape.
- Ensure IntelX blocks SSRF/redirect/DNS rebinding cases and handles robots/policy uncertainty safely.
- Bound Futuris heavy operations and secure expensive/mutating endpoints.
- Make the FRIDAY legacy updater safe and prevent automatic source rewrites/direct push.
- Ensure secrets are not in files, history, logs or CI artifacts; rotate actual leaked credentials where evidence indicates exposure.

Acceptance: security tests cover denial cases, no critical known default credentials, sensitive endpoints auth-tested, CI security scans are blocking or explicitly triaged with a reviewed documented exception. Do not silence audits via `|| true` or blanket allow-failure.

## Phase 2 — Common API contracts and orchestration reliability

- Document and standardize authenticated service-to-service APIs.
- Add correlation/task IDs and consistent response/error shapes.
- Use bounded timeouts, retries with jitter, circuit breakers, queue backpressure, idempotency and cancellation.
- Keep FRIDAY as orchestrator/user approval layer and Inference as reasoning/router.
- Keep specialist domain gates authoritative and test failure behavior when an agent is unavailable.
- Add cross-agent contract tests and malformed/untrusted payload tests.

Acceptance: contract tests run in CI; bounded failure tests demonstrate no infinite retry, task duplication or falsely reported success.

## Phase 3 — PostgreSQL 18 and Memora migration

- Confirm actual current PostgreSQL version, cluster, volume mount, databases, roles and extensions on OCI.
- Create ten logical databases and least-privilege roles.
- Port application-specific schema/query behavior and migration tests.
- Migrate existing SQLite data without loss, including actual user memories/records. Do not only change `.env` examples.
- Keep Memora as the sole long-term memory authority with ACLs and provenance; disable production SQLite/legacy DB fallback after validated cutover.
- Keep Qdrant or migrate vector search intentionally; test retrieval precision/latency and deletion propagation.
- Test backup/restore, row counts, uniqueness, foreign keys, idempotent migration and rollback.

Acceptance: no production write can silently go to SQLite; actual rows and key invariants match; all apps connect using distinct roles; no public DB port; rollback tested.

## Phase 4 — Specialist database and domain correctness

For each agent verify its operational state is authoritative and persistent in its own DB. For Stratex inspect the real end-to-end order lifecycle and close/reconciliation flows. For IntelX port FTS/search behavior deliberately. For Cortex validate every tenant. For Forge verify artifact evidence. For Futuris verify outcome/calibration records.

Acceptance: per-agent integration tests against disposable PostgreSQL; persistence after restart; duplicate/retry semantics; migrations; health/readiness; domain invariants.

## Phase 5 — OCI/Dokploy deployment and resource rebudgeting

- Build images for ARM64, test dependencies and run integration smoke tests.
- Centralize deployment topology where practical but preserve individual repos and deployment identities.
- Keep only proxy ports public; private network for internal APIs/data services.
- Apply CPU/memory/pid/queue limits and one global heavy-job slot.
- Set logs rotation and volume retention.
- Back up to private OCI Object Storage and run restore test.
- Deploy only the exact merged/approved commit, staged one service at a time; observe live health and rollback if needed.

Acceptance: deployed commit SHA matches GitHub; every app is healthy; actual API-to-API calls work; memory/CPU stable under test load; backup restore proven; no credentials in Git or logs; no unexpected public ports.

## Phase 6 — Stratex detailed roadmap (do not skip)

A. Refresh PR #7/#9 and inspect PR #8 merged store. Map every strategy entry/fill/SL/TP/trailing/modification/close/fee/funding/ledger path. Identify direct exchange calls bypassing OMS.

B. Complete the Binance USD-M Futures Demo lifecycle: explicit Demo-vs-Testnet endpoints/credentials, symbol filters (tick/lot/min-notional), position mode, margin/leverage policy, market entry, fill reconciliation, conditional Algo Order SL/TP, protective order verification, sibling cancel/reconcile, restart recovery and ambiguous submit behavior.

C. Complete IC Markets MT5 Demo through an authenticated private bridge to an always-on Windows host. Verify demo account on startup and before orders, exact broker symbol/contract metadata, tick/lot steps, stop-distance, margin/PnL calculations using broker API, ticket-specific close/modify, partial/pending fills and restart reconciliation.

D. Portfolio/risk gate: timestamped account equity/positions, max exposure, currency conversion with rate source and max age, daily loss/drawdown baseline, concentration/margin checks, kill switch and append-only risk decision audit. Missing/stale context means deny new entry.

E. Agent integrations: IntelX evidence/citations, Futuris forecast horizon/uncertainty, Inference explanation and Memora summaries through its API. None can directly authorize execution.

F. Demo soak test with disconnect/reconnect, timeouts, restarts, partial fills, protected exits and reconciled ledger. Live money remains disabled.

Acceptance: verified non-production demo account, full lifecycle tests and logs/screens without secrets; no duplicate orders; protective exits verified; order ledger matches venue truth; restart safe. Do not call this production-ready without a separate explicit risk review.

## Phase 7 — Final ecosystem acceptance

Run a full cross-agent flow in staging, e.g. FRIDAY asks IntelX for cited research, Futuris returns a timestamped forecast, Inference performs bounded reasoning, Sentinel policy is checked, Stratex runs only safe paper/demo simulation, Memora stores only approved summaries, Forge produces/test-verifies a patch, Cortex performs a tenant-scoped workflow, and all statuses/trace IDs flow back to FRIDAY.

Test service failures, invalid auth, stale evidence, malformed payloads, duplicated requests, database outage, queue overload, container restart and rollback.

Acceptance: all required tests and CI pass on exact commits, all service contracts work, memory ACLs pass, database restore works, deployed version matches the approved source and all high-risk action flags remain disabled unless separately authorized.

# 15. GitHub and release rules

For every repository change:

1. Fetch remote refs. Check branch protection and whether CI triggers deployment.
2. Identify files/call paths that need changes and define exact acceptance criteria.
3. Make a feature branch. Never make competing edits to shared manifests/migrations.
4. Implement the smallest cohesive code change that delivers one verifiable behavior.
5. Add regression tests for the failure, positive case, and related edge cases.
6. Run formatting, lint, typing, unit tests, integration tests as available and build checks locally.
7. Inspect complete `git diff`, `git status`, file deletions and generated artifacts. Confirm no secret or data file is staged.
8. Push branch and open/update a PR with changed behavior, tests actually run, limitations, migration plan and rollback.
9. Inspect CI on exact head SHA. Fix introduced failures; distinguish baseline failures, but do not hide security failures.
10. Merge only when checks and review pass. For any merge that triggers deployment, ensure the deploy binding and maintenance/rollback plan is known.
11. After merge, fetch `main` and verify the merge commit, CI, deployment and runtime separately.

No unbounded background promise. If the session ends, leave a durable handoff containing branch, SHA, file list, test output, open issues and next exact task.

# 16. First-hour resume checklist

- [ ] Refresh current default-branch SHAs for all ten GitHub repositories.
- [ ] Inventory open, closed and merged PRs, including the closed Task 1/2/3 work, and inspect exact patches before restoring any code.
- [ ] Review all latest workflow runs and required checks on their exact head SHAs.
- [ ] Confirm mirroring opens reviewable PRs and never force-pushes or writes directly to standalone `main`.
- [ ] Check tracked paths and commit history for possible secret exposure without printing secret values.
- [ ] Record verified progress, PR URLs, tests and unresolved tasks in the repository handoff.
- [ ] Do not access laptop files or Oracle Cloud/Dokploy for this GitHub-only execution.

# 17. Required reporting format at every checkpoint

For each unit of work report:

- **Repo/service:**
- **Branch and base SHA:**
- **Issue / expected behavior:**
- **Changed files:**
- **Implementation summary:**
- **Tests run (commands) and exact results:**
- **CI workflow and head SHA:**
- **Security/migration risks:**
- **PR URL and state:**
- **Local state / remote synchronization:**
- **Deployment status (if applicable):**
- **What is still unverified:**
- **Next action:**

Never report only “done,” “all fixed,” “100% complete,” or “working” without observable proof.

# 18. Master continuation prompt for the next ChatGPT session

Paste this prompt after attaching this PDF, the master specification Markdown, and the Stratex handoff PDF. Do not attach the credentials dossier.

> You are resuming the FRIDAY Universe engineering upgrade. Read the entire `FRIDAY Universe — Complete Engineering Handoff`, the user's `FRIDAY_UNIVERSE_MASTER_SPECIFICATION(2).md`, and the Stratex engineering handoff before acting.
>
> The ecosystem has exactly ten repositories: FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX and Futuris. FRIDAY is the orchestrator; Inference is the canonical model gateway; Memora is the only long-term cross-agent memory authority. Each agent owns its operational DB; all memory sharing goes through Memora's authenticated scoped API. Target data layer is PostgreSQL 18, one server with ten logical databases/least-privilege roles, only after verified data migration and restore tests.
>
> Do not make any blind pull, reset, clean, force-push, bulk merge or direct-main edit. The local workspace had many uncommitted changes and a recovery snapshot at `D:\FRIDAY Universe\state_backups\pre-reconciliation-20261018-010125.zip`. The current MCP tool call failed at the time this handoff was prepared. Restore the local connection and run a read-only audit before editing.
>
> Recheck all GitHub PRs and CI because the status table in this handoff is only as current as 18 October 2026. At last check, PRs #3 were merged for FRIDAY, Inference, Memora, Forge, Sentinel and IntelX; Stratex #8 was merged; Cortex #3 was open/draft with failed CI; Futuris #3 was open with successful CI; Stratex #7 and #9 were open. Reconfirm each exact SHA/check now. Another chat has worked on Stratex, so avoid conflicting edits and start any new Stratex work from refreshed `main` on a new branch.
>
> First restore and verify the FRIDAY Universe MCP, then inventory all local working trees, fetch refs safely, inspect the recovery snapshot, and compare with GitHub. Independently verify OCI, SSH, Dokploy, live PostgreSQL version/data/volume/backup, deployed commit and ARM instance allocation. Do not believe Antigravity's infrastructure report until confirmed live. Treat the Antigravity credentials PDF/Markdown as sensitive: never open its secrets into output, commit it, or attach it to chat; check Git tracking/history and rotate credentials if they were exposed.
>
> Work as a coordinated engineering effort, not as ten tiny PRs. Map complete code paths, implement by phased goals, add meaningful unit/integration/contract tests, run them locally, inspect the full diff, push feature branches, create PRs, and merge only after the exact CI head is green and the change is reviewed. Keep deployment separate from code merge and validate it afterwards. Prioritize security/correctness, API contracts, PostgreSQL/Memora migration, full Stratex OMS lifecycle and risk gate, ARM64 deployment, resource budget, backups/restore, and final cross-agent tests. Keep all trading flags disabled and no live-money execution.
>
> The target host has 2 OCPUs / 12 GB RAM, so profile memory and CPU. The resource caps listed in the old spec sum to around 12.06 GB and must be re-budgeted with OS headroom. Use one global CPU-heavy-job slot. Keep internal services and DB ports private and only the reverse proxy public. Back up to encrypted private OCI Object Storage and actually test restores.
>
> At each checkpoint, report branch/SHAs, changed files, exact commands/test results, CI status, PR URLs, deployment status, risks and what remains unverified. If access is missing, ask for the specific secure connection or action needed; do not ask the user to paste secrets. Do not claim the ecosystem is upgraded until every phase's acceptance criteria have been demonstrated.

# Appendix A. Repository quick links

- FRIDAY: https://github.com/surendra2304/FRIDAY
- Inference: https://github.com/surendra2304/Inference
- Memora: https://github.com/surendra2304/Memora
- Stratex: https://github.com/surendra2304/Stratex
- Forge: https://github.com/surendra2304/Forge
- Cortex: https://github.com/surendra2304/Cortex
- Sentinel: https://github.com/surendra2304/Sentinel
- IntelX: https://github.com/surendra2304/IntelX
- Futuris: https://github.com/surendra2304/Futuris
- VyralX: https://github.com/surendra2304/VyralX

Relevant PRs at last check:

- FRIDAY #3: https://github.com/surendra2304/FRIDAY/pull/3
- Inference #3: https://github.com/surendra2304/Inference/pull/3
- Memora #3: https://github.com/surendra2304/Memora/pull/3
- Stratex #7: https://github.com/surendra2304/Stratex/pull/7
- Stratex #8: https://github.com/surendra2304/Stratex/pull/8
- Stratex #9: https://github.com/surendra2304/Stratex/pull/9
- Forge #3: https://github.com/surendra2304/Forge/pull/3
- Cortex #3: https://github.com/surendra2304/Cortex/pull/3
- Sentinel #3: https://github.com/surendra2304/Sentinel/pull/3
- IntelX #3: https://github.com/surendra2304/IntelX/pull/3
- Futuris #3: https://github.com/surendra2304/Futuris/pull/3

