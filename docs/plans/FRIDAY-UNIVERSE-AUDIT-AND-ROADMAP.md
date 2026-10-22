# FRIDAY Universe — Repository Audit and Practical Roadmap

**Prepared: 25 September 2026**  
**Purpose:** Replace conflicting aspirational blueprints with a repository-grounded plan that can be delivered incrementally at near-zero cost.

> This is a dated audit snapshot. Its repository heads and working-tree counts are superseded by the [30 September 2026 Phase 0 baseline](reports_and_data/stage0-baseline-2026-09-30.md); consult that report and the current master plan for later evidence and unresolved deployment gaps.

## Executive summary

You have substantial working software across nine repositories: FRIDAY (voice, desktop, orchestration), Inference (multi-provider gateway), Memora (memory API and retrieval), Stratex (paper/testnet trading with live-money blockers), IntelX (evidence-based research), Futuris (forecasting), Cortex (web operations/CRM), Forge (software engineering), and Sentinel (security controls). Most repositories have meaningful tests and APIs. The immediate problem is not a lack of agents; cross-repository plans and deployment claims overstate integration and production readiness.

**Recommended objective:** Make FRIDAY useful and dependable for Surendra first. The first major outcome is full local laptop assistance plus FRIDAY coordinating the other eight agents and speaking naturally with ongoing Universe updates. Keep this as the product destination, then deliver it in evidence-backed slices: local control, secure coordination, shared memory, event-driven intelligence, and progressively wider autonomy. Do not mark any capability complete from a health ping, mock result, or generated report alone.

## Audit scope

- Read the user-provided brief, root README and architecture/plan/report files, all nine repositories' READMEs, deployment manifests, entrypoint/dependency-file locations, and major integration/configuration paths.
- `rg --files` counts: FRIDAY 799, Inference 302, Memora 155, Stratex 561, IntelX 286, Futuris 219, Cortex 302, Forge 266, Sentinel 332. Counts include tests/docs/assets and do not measure completeness.
- All nine are Git repositories. FRIDAY and Inference have commits from 24 September; other checked HEADs are 18 September. Forge, IntelX, Memora, Sentinel, and Stratex have uncommitted local state. Preserve and review those files before cleanup or broad edits.
- No tests were run and no agent code was changed. Existing reports are dated 18–19 September and were not regenerated.

## Repository map

| Repository | What is actually there | Main gap to resolve |
|---|---|---|
| FRIDAY | Python app with voice, Windows screen/device control, cognitive workflows, provider fallbacks, service registry, fleet client, local memory adapter, Render Docker service. | A cloud process cannot provide local Windows control. Integration defaults and public deployment configuration need a supported mode. Remote Memora sync defaults off. |
| Inference | FastAPI model/provider gateway with Gemini, Groq, OpenRouter, NVIDIA and other integrations; provider tests and Render service. | Key rotation is not extra quota. Measure privacy, budget, timeouts, fallback and real-provider behavior. |
| Memora | FastAPI multi-tier memory, FTS5/hybrid search, adapters, migrations, tests and Turso settings. | Render blueprint points SQLite at an ephemeral file. Prove one durable backend and authenticated namespace/write/recall/delete for each agent. |
| Stratex | Quantitative system with paper forward validation, Binance spot testnet, risk gates and dashboard; README explicitly says live orders blocked. | Trading edge is unproven; Render blueprint conflicts with testnet/paper-only design and sets a risky flag. Do not promise a win rate. |
| IntelX | Research workflow with evidence/provenance, connectors, APIs, tests and Turso hooks. | Broad world coverage requires source-by-source design, rate-limit handling, freshness tracking and a durable push channel; no single crawler literally sees everything. |
| Futuris | Forecast APIs, scenarios, calibration/evaluation, evidence snapshots and Memora/Inference integrations. | Score forecasts by horizon; predictions must not authorize changes or trades. |
| Cortex | API + worker + dashboard monorepo, event-based web operations, governed tools, CRM direction. README defines an operations layer, not a site builder. | Render sets `MOCK_MODE=true`, SQLite and a hardcoded JWT secret. SaaS needs durable Postgres, isolation, auth, billing, privacy and tenant tests. |
| Forge | FastAPI software-engineering pipeline, DAG/workspaces/recovery/verification and security tests. | Render writes data, workspaces and artifacts under `/app` without persistent storage. Use disposable workspaces and owner approval before publish/deploy. |
| Sentinel | Security API/orchestration, scoped assessment, evidence/audit structures and extensive tests. | Render config uses in-memory storage and a predictable signing key. Require real secrets, durable audit and fail-closed action policy before relying on it. |

## Critical findings

1. **Your separate Render accounts and five-minute UptimeRobot checks change the uptime calculation.** Render Free web services sleep after 15 minutes without inbound traffic; a successful inbound health request every five minutes should keep each service awake. If each account/workspace has its own 750 free instance-hours and only one service consumes them, 24/7 use is nominally about 720 hours/month, leaving a narrow margin for deploys and other services. Confirm each monitor succeeds, each account has the expected quota, and usage stays below its limit. A ping proves only that an endpoint answered. It does not prove background jobs are running, peers can authenticate, or messages/data persist. Render filesystems remain ephemeral; SQLite, Forge artifacts and local audit state can disappear on restart/redeploy. Free Postgres expires after 30 days and free Key Value does not persist. See [Render free limits](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks), and [FAQ](https://render.com/docs/faq).
2. **Render manifests contain unsafe or misleading defaults.** Shared literal service keys are in blueprints; Cortex sets `MOCK_MODE=true` and a predictable JWT secret; Sentinel sets a predictable audit-signing key and in-memory storage; Stratex sets `PAPER_SAFE_MODE=FALSE`; multiple services store SQLite on ephemeral paths. Treat these as release blockers. Rotate any deployed credentials that used these values; never put real keys in Git or reports.
3. **Memora is not FRIDAY's shared live brain by default.** `FRIDAY_MEMORA_REMOTE_ENABLED` defaults to `false`; local SQLite is used for writes and recall. Other agents have adapters, but this does not prove every action, correction and outcome is ingested with shared scope.
4. **Health checks do not prove real task integration.** Reports claim 9/9 HTTP 200 and 20/20 contracts, but also describe Forge/Sentinel local or in-memory verification and provide no persistent evidence trace for a real cross-agent journey. The E2E report calls deterministic workflows “real” while recording zero external orders. Label evidence as `LIVE_HEALTH`, `REAL_PROVIDER_CALL`, `LOCAL_INTEGRATION`, `MOCK`, `PAPER`, or `BLOCKED`. Do not call health checks production certification.
5. **Routes and authentication vary.** Documents disagree on `/health`, `/healthz`, `/api/health`, `/api/status` and auth headers. Some clients guess fallback routes. Derive a versioned capability/auth/health contract from actual services and test authenticated operations.
6. **Configured key counts do not equal provider capacity.** Count effective local settings with `python -m app.core.key_inventory` from `Inference`; this reports counts only. It does not verify credentials, distinct provider accounts, deployed Render values, quota, or successful calls. Gemini limits apply per project/model; extra keys do not simply multiply quota. Track actual account quota/cost and impose a hard monthly cap. See [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and [pricing/data-use](https://ai.google.dev/gemini-api/docs/pricing).
7. **No fixed trading win rate can be guaranteed.** Stratex says live orders are blocked pending forward validation. Stay paper-only until fee/slippage-aware out-of-sample expectancy, drawdown and sample size meet pre-registered criteria. Do not let a blueprint enable live capital.
8. **Keep the nine-repository structure; simplify runtime topology.** Defer NATS/CRDT/Kafka/Redis/graph DB and nine always-running agents until a measured need exists. Signed HTTPS, idempotency, one durable Memora store and append-only action receipts are enough for the first version.

## Intended architecture and free-first constraints

- **FRIDAY desktop:** A local Windows companion provides voice, screen perception, app/file/browser/device control, and status/briefings. The cloud agent cannot directly control the laptop; a local authenticated connector must receive only explicitly enabled capabilities. Avoid repeated approval prompts for routine tasks Surendra has authorized, while preserving OS sign-in, explicit scope, and safeguards around destructive or externally consequential actions.
- **FRIDAY cloud:** Orchestrates cloud peers and continuous workflows. Given separate accounts and five-minute inbound monitors, the Render Free service may stay awake within its per-account monthly allowance. Monitor that allowance and request success. The cloud service never gains laptop control except through the local connector.
- **Inference:** One router with deterministic task, cost and privacy policies. Use providers/quotas already available; fail clearly on quota exhaustion. Show provider, model, data terms and usage; cap spend.
- **Memora:** Shared memory fabric for every agent, with agent-private, group-shared and universal scopes selected and enforced by Memora. Current [Turso pricing](https://turso.tech/pricing) lists a free tier of up to 100 DBs, 5 GB, 500M reads and 10M writes monthly; verify Surendra's current account and database settings. IntelX also keeps its own Turso database for collected source material/indexes, while sharing relevant verified intelligence with agents and Memora. A durable remote database is the source of truth; do not treat container SQLite fallback as synced memory.
- **Specialists and message flow:** Agents communicate both ways. IntelX publishes new, relevant intelligence to subscribed agents and answers pull queries. Futuris consumes market and ecosystem events, publishes timestamped probabilistic forecasts/threat notices to Stratex, FRIDAY, Sentinel, and other subscribers. Sentinel publishes verified security findings to affected agents and FRIDAY. Use a broker/stream or durable event log with HTTPS task APIs, versioned envelopes, signed caller identity, scoped subscribers, bounded messages, idempotency, evidence references, expiry, and replay. Define event ownership and prevent loops/duplicate broadcasts.
- **Durable state:** Keep outside sleeping Render containers. Use Memora for memory and owner-controlled durable storage for code/artifacts. Do not rely on Forge's container filesystem.
- **Safety:** Recommendations never authorize actions. Messages, production deployments, security write actions, purchases, tenant data exports and trades need approval. Autonomous repair may prepare a disposable branch with CI evidence and rollback.
- **Observability and anti-loop controls:** One task ledger records agent/provider/model, cost/quota, redacted inputs, evidence, approvals, outputs, status and lessons. Every task has an owner, deadline, bounded attempt/retry count, progress checkpoint and stop condition. A repeated unchanged plan/result is detected and halted as `STALLED`, never re-run forever or reported as success. Minimize personal data and provide memory view/export/delete.

## Delivery roadmap

### Stage 0 — Make the map truthful (1–2 sessions)

Mark existing production/health claims unverified; inventory environment variable names without values; rotate any deployed defaults; remove live-looking mock secrets; confirm per-account Render usage and monitor success; label deployment ownership. Preserve dirty repo files first.  
**Exit:** No production URL relies on known placeholder credentials. One status page shows mode, mock status, storage durability and health route.

### Stage 1 — FRIDAY local presence and laptop operation

Prioritize the local Windows companion: voice in/out, natural conversational replies, app/window/screen context, and a bounded set of laptop actions routed through FRIDAY's existing authorization and receipt paths. Continue FRIDAY's main service for cloud orchestration. Align model defaults/fallbacks and expose provider failure clearly. Make FRIDAY's status and briefings explain which peers, tasks and feeds are actually active.  
**Exit:** Demonstrate the agreed laptop-action catalog on the real Windows session; verify results from the OS/application state rather than spoken/model claims; recover from provider/network outage; keep an auditable action receipt. Full capability is the goal; avoid arbitrary repeated prompts for already-authorized routine operations.

### Stage 2 — Memora shared memory

Choose durable DB; version schema; enforce identity and namespaces; wire FRIDAY first with remote use explicit; record task/action/result/error/correction/approval/lesson with credentials redacted; recall before supported tasks; add idempotency and offline retry. Add other agent adapters one at a time. Track provenance, confidence, source and scope; provide user view/export/delete. Never promote model-generated lessons to trusted policy without review and confirmed outcomes.  
**Exit:** A new session recalls a stored fact; scope isolation passes; outages are visible; retry creates no duplicate; authorized agents read only permitted shared memory.

### Stage 3 — Connect agents and prove one multi-agent journey

First establish live service-to-service authentication and a durable event channel. Journey: IntelX ingests a relevant story and publishes a cited event → Futuris evaluates a specified market horizon and publishes probabilities/uncertainty → Stratex receives it as an advisory input while risk gates remain authoritative → FRIDAY tells Surendra what happened and why → Memora stores the event, forecast, decision, outcome and correction in proper scopes. Add pull queries so every agent can ask IntelX for fresh evidence when needed. Add Sentinel risk/threat events to the same governed pattern.  
**Exit:** Reproducible from clean deployments; one correlation ID and timestamps through all hops; each receiving agent acknowledges/records the event; real source/provider calls distinguished from mocks; retries, deduplication, replay, costs and latency visible.

### Stage 3B — Continuous intelligence and Universe monitoring

IntelX cannot literally observe every event worldwide. Build a broad, configurable registry of public/licensed news, market and security sources, prioritize by relevance to FRIDAY Universe, poll/subscribe according to source limits, and report coverage and freshness gaps honestly. Run scheduled source ingestion and event push continuously while each account's Render allowance permits; keep a durable queue/checkpoint so restarts resume without losing or duplicating stories. Futuris monitors service/task telemetry and produces calibrated ecosystem risk forecasts. Sentinel performs scheduled bounded audits and publishes evidence-backed findings. Agents subscribe to relevant topics and can query IntelX on demand. UptimeRobot remains endpoint availability monitoring, not proof these pipelines processed data.

**Exit:** For each source show last success/failure, lag, rate-limit state and provenance; demonstrate news-to-Futuris-to-Stratex and threat-to-Sentinel/FRIDAY alert paths with stored evidence; demonstrate restart and queue replay without duplicates.

### Stage 4 — Bounded self-correction and shared learning

All agents record work, failure, fix, upgrade proposal and measured outcome in Memora under the correct private/group/universal scope. Start with transient retries, verified reversible recovery and patch proposals in disposable branches. Agents can suggest improvements to peers; Sentinel checks changes/tests and rollback feasibility. FRIDAY cannot erase audit/memory or bypass owner-defined security constraints. Expand unattended action classes after measured reliability, with a transparent task ledger and stop control.  
**Exit:** Fault-injection evidence for retry, deduplication, rollback and escalation. Improvement is measured on a fixed evaluation set.

### Stage 5 — Add specialist products one at a time

- **IntelX:** broad public/licensed source coverage relevant to the Universe, citations, terms/rate limits, freshness, push subscriptions and query-on-demand retrieval.
- **Futuris:** timestamp, horizon, probability, assumptions and calibration history; advisory only.
- **Sentinel:** authorized passive assessment; real secrets, durable signed audit, explicit scope and evidence. Never scan unspecified systems autonomously.
- **Forge:** verified changes in throwaway workspaces; tests, diff and security scan; artifacts in durable owner storage; approval to publish/deploy.
- **Stratex:** frozen strategy, realistic costs, untouched forward validation and pre-registered gate; paper-only. Win rate alone is not success.
- **Cortex:** build a multi-tenant AI revenue operations SaaS: configurable agents grounded in each business's CRM/site/email/call context; prospecting and lead capture/qualification; CRM hygiene and routing; meeting preparation; drafts and, when explicitly configured/authorized, customer outreach by email, messaging or voice; booking and follow-up; analytics and audited actions. Start with one narrow end-to-end lead workflow; durable data, tenant isolation, integration permissions, opt-out/consent, provider costs and delivery evidence precede general availability. This matches the user's stated product direction, which is broader than the current Cortex README's “website operations” description. Do not claim the product is Salesforce-equivalent until capability-by-capability evidence exists.

### Stage 6 — Make an explicit uptime/budget choice

Keep the strict $0/month limit. Separate Render accounts can supply separate free quotas; a five-minute successful health request can keep a free web service from idling out, but each 750-hour monthly allowance has little headroom when the single service runs 24/7 (~720 hours/month before deploys/other usage). Avoid adding web services to the same account without recalculating hours. Use external durable storage for every important record because Render Free container files remain ephemeral. Build visible quota/uptime/storage checks and graceful recovery rather than assuming the monitor proves the agent is doing useful background work.

## First 30-day sequence

| Week | Result | Evidence |
|---|---|---|
| 1 | Truthful deployment/quota/storage inventory, safe credentials, local FRIDAY baseline | Masked env audit, successful inbound monitor checks, account-hour margin, real endpoint/auth checks |
| 2 | FRIDAY voice and first laptop-action catalog with verified outcomes | OS/application evidence, action receipts, latency/error traces |
| 3 | FRIDAY ↔ Memora durable write/recall and scope enforcement | New-session recall, isolation and outage/retry/restart traces |
| 4 | First live event: IntelX → Futuris → Stratex advisory → FRIDAY update | Cited event, prediction ledger, Stratex advisory/no order, Memora event history |

This is a target order, not a completion guarantee; quotas and free hosting limits can change the pace.

## Success measures

- **FRIDAY:** completion on a fixed 20–50 task set, correction rate, zero unapproved side effects, degraded-mode success and p50/p95 latency.
- **Memora:** write/read success, relevance on test queries, duplicate rate, zero scope leakage, export/delete correctness.
- **Inference:** provider/model success and latency by task class, cost per successful task, quota and privacy handling.
- **IntelX/Futuris:** citation coverage/freshness; forecast Brier score versus baseline by horizon.
- **Continuous services:** per-account Render hours, monitor success, last completed background cycle, feed lag/coverage, queue age and restart recovery.
- **Stratex:** net expectancy, drawdown, sample size and validation duration; no live trading until owner-defined gates pass.
- **Forge/Sentinel/Cortex:** verified patch/rollback, authorized scan evidence, tenant isolation and real workflow completion.

## Supersession notes

- `README.md`, `ECOSYSTEM_BLUEPRINT.md`, `FRIDAY-UNIVERSE-MASTER-PLAN.md`, `master_plan.md` and `goal_prompt.txt` conflict on topology, endpoints, persistence, roles and readiness. Treat as historical input until consolidated.
- The owner explicitly requires FRIDAY Universe terminology; this audit follows that rule.
- `integration_report.md/.json` and `e2e_test_report.md/.json` are historical snapshots, not current certification. Re-run after environment, authentication, durability and mock/real labels are fixed.

## Sources checked (25 September 2026)

- [Render free services](https://render.com/docs/free) — sleep, ephemeral files, monthly quota, datastore limitations.
- [Render persistent disks](https://render.com/docs/disks) — paid-plan and single-instance limitations.
- [Render FAQ](https://render.com/docs/faq) — restarts and storage guidance.
- [Turso pricing](https://turso.tech/pricing) — published free DB/storage/read/write allowances.
- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) — per-project/model quota behavior.
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) — free/paid access and data-use differences.
- [Salesforce Claudeforce](https://www.salesforce.com/claudeforce/) — current product reference: CRM-grounded assistant and sales workflows governed by business permissions.
- [Nex AI Grokbot for GTM teams](https://nex.ai/) — current product reference: prospecting, qualification, CRM hygiene, lead routing and revenue workflows.
