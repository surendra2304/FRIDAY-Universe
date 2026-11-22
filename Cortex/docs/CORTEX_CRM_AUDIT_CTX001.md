# Cortex CRM/website-operations audit — TASK-CTX-001 (2026-11-22)

Author: Muse 9. Scope: MASTER_PLAN §6, pool 2 item 10. Base: branch
`muse9/task-ctx-001` @ `3342bb0` (claim commit; parent `ecea58e`).
Verified that none of the 33 commits between `ecea58e` and main `254c2df1`
touch `Cortex/`, so every finding below applies to main `254c2df1` as well.

Method and limits: static code read only. This VM has no FastAPI, SQLAlchemy,
pytest or PyJWT installed, so no server was booted, no test was run, and no
live request was made; the route inventory was produced by AST-walking all 303
route functions in `Cortex/apps/api/src/cortex_api/` (every file parsed
cleanly). Tests were read, not executed. Anything not confirmed from the code
is marked **unverified**. No live timing was measured; bounds below are read
from the code, not from runs.

## 1. What Cortex is (verified tree, not the scope notes)

The scope notes in the assignment are mostly right, with four corrections:

- There is no `enhanced_analytics.py`. The analytics module is
  `advanced_analytics.py`. Likewise `attribution.py` is
  `multi_channel_attribution.py` and `demand_forecaster.py` is
  `predictive_demand_forecaster.py`.
- The schema is **17 tables, not 16** (`Cortex/apps/api/src/cortex_api/
  db_models.py`: profiles, visitors, sessions, events, leads, audit_records,
  tenants, api_keys, sentinel_scans, sentinel_findings, identity_links,
  lead_scores, memory_entries, workflow_runs, approval_queue,
  strategy_performance, agent_budget_state). Alembic has 9 versions
  (`Cortex/infra/alembic/versions/001`–`009`) covering all 17; the parity test
  `Cortex/tests/unit/test_alembic_parity.py` asserts exactly that.
- `Cortex/docs/` already exists (AGENT_ARCHITECTURE.md, DATA_MODEL.md,
  DEPLOYMENT.md, PRODUCTION.md, SECURITY.md, …), so this audit lives there.
- The dashboard source is `Cortex/apps/dashboard/src/` (Next.js); the
  committed `apps/dashboard/out/` is a static export served by the API.

Layout: API `Cortex/apps/api/src/cortex_api/` (50 modules, 303 route
functions), worker `Cortex/apps/worker/src/cortex_worker/main.py`,
`cortex_upgrade/` (cross-cutting: auth, rate limit, dedupe, DLQ, webhook,
persistence), `packages/` (core, identity, analytics, integrations,
intelligence, policy_engine, workflow_engine, sdk, …), dashboard
`Cortex/apps/dashboard/`, migrations `Cortex/infra/alembic/`.

Data flow (verified from the code):

```
browser SDK (packages/sdk) ──POST /v1/events(+/batch), X-Cortex-Public-Key──▶ API
API ──persist EventModel + SessionModel (Oracle CORTEX schema)──▶ DB
API ──xadd cortex:events:stream──▶ Redis ──xreadgroup──▶ worker
worker ──10-phase cognitive loop (Orchestrator)──▶ actions / approvals / DLQ
dashboard (Next.js) ──GET/POST /v1/*, Bearer JWT──▶ API
FRIDAY ──X-Friday-Api-Key──▶ /v1/friday/*, /execute, /plan, /decompose
Stripe ──signed webhook──▶ /v1/webhooks/stripe ──xadd──▶ Redis stream (never persisted)
```

## 2. Per-operation surface

| Operation | What it does | Website touchpoints | CRM touchpoints |
|---|---|---|---|
| POST /v1/events, POST /v1/events/batch (`events_router.py`) | Ingest browser events; public-key auth, tenant from credential, per-credential+site Redis sliding-window rate limit (1000/60s default, local in-process fallback), payload ≤256 KB, dedupe by `event_id` (in-process 1 h / 100 k-entry cache + DB uniqueness), auto-create session, persist `events` + `sessions`, xadd to `cortex:events:stream` | SDK `track`/`page`/`identify` calls; `POST /v1/events/batch` is the SDK's only write path | `events`, `sessions`, `api_keys` (last_used_at write per event) |
| POST /v1/identify (`public_gateway.py:38`) | Resolve visitor identity (email/user_id → profile + identity links); consent-gated pseudonymous fallback | None from the browser SDK — the SDK never calls it; it is an operator/JWT endpoint | `visitors`, `profiles`, `identity_links` |
| GET /v1/visitors/{id}, GET /v1/leads/{id}, GET /v1/leads, POST /v1/leads (`public_gateway.py:68–207`) | Tenant-scoped visitor/lead reads; lead create (operator-supplied score, default 50) | Dashboard leads/visitors pages (SWR, 15–30 s refresh) | `visitors`, `profiles`, `leads` |
| GET /v1/analytics/{metric} (`public_gateway.py:212`) | Hourly series from real events for 6 event-backed metrics; anything else returns `supported: false` | Dashboard analytics | `events` |
| POST /api/v1/leads/score (`enhanced_crm.py:394`) | Rule-score a lead (behavior ≤40 + firmographic ≤30 + engagement ≤20 + source ≤10), grade A–F, segment, persisted score history | None directly | `lead_scores` (history row); in-memory score dict |
| GET /api/v1/leads/{id}/follow-up, POST /api/v1/leads/{id}/clv (`enhanced_crm.py:472,490`) | Follow-up suggestion by grade; CLV = AOV × freq × years × (1−churn) × (score/50) | None | In-memory scores only — **not** the persisted history |
| POST /api/v1/crm/engagement, POST /api/v1/crm/ab-test, GET /api/v1/crm/report (`enhanced_crm.py:530,546,563`) | Cross-channel engagement arithmetic; A/B z-test; report over in-memory scores | None | In-memory only |
| GET /v1/leads/{id}/score (`understand_router.py:314`) | Current score + persisted score-history trend (tenant-scoped) | Dashboard | `leads`, `lead_scores` |
| GET /v1/identity/resolve, GET /v1/visitors/{id}/profile, GET /v1/sessions(+/{id}/replay) (`understand_router.py`) | Identity resolution, visitor profile, session list/replay | Dashboard | `profiles`, `visitors`, `sessions`, `events` |
| GET /v1/analytics/funnel|cohorts|attribution (`understand_router.py:337–`) | Funnel/cohort/attribution computed from stored events (≤500 events) | Dashboard analytics | `events` |
| POST /api/v1/cortex/marketing/* (`marketing_platform_integrator.py`) | Connect platform, create/send/schedule email, create/publish social, create/activate ads, create/update/query CRM records, track events | None — no real platform call is made anywhere in the file | **None durable**: all state in process-memory dicts; "CRM records" never reach HubSpot/Salesforce or Oracle (gap G5) |
| POST /api/v1/marketing/* (`marketing_automation.py`) | Campaigns, email sequences, lead journeys, social scheduling, funnel build, ROI | None | In-memory only; sequences/posts are never executed (gap G6) |
| POST /api/v1/analytics/* (`advanced_analytics.py`) | Cohort, funnel, churn, revenue forecast, cluster, anomaly, report | None | **None** — no DB read in the file; arithmetic on caller-supplied payloads (gap G13) |
| POST /api/v1/cortex/attribution/* (`multi_channel_attribution.py`) | Journeys, first/last/multi-touch/Markov attribution | None | In-memory journeys |
| POST /api/v1/cortex/demand/* (`predictive_demand_forecaster.py`) | Demand series, naive trend forecast, churn, campaign forecast, scenarios, ensemble (explicit no-data) | None | In-memory series |
| POST /api/v1/cortex/ab/* (`ab_experiment_framework.py`) | Experiment create/start/participants/analyze/complete, md5-hash variant assignment | None | In-memory experiments |
| GET /health, /v1/health, /status, /ready, /health/ready (`production_router.py`, `main.py`) | Liveness (process only); readiness = Oracle `SELECT 1 FROM DUAL` + schema completeness + Redis ping; peer integrations reported `UNKNOWN`, non-fatal | Caddy / Docker healthchecks | `SELECT 1 FROM DUAL`, schema table list, Redis ping |
| GET /metrics (`production_router.py:85`) | In-process Prometheus counters; token-gated only when `METRICS_TOKEN` is set | Scrapers | None (process memory) |
| WS /v1/ws/events, WS /ws/v1/live, GET /v1/stream/sse (`production_router.py:334`, `streaming_router.py`) | Authenticated live streams, tenant-isolated, 100 conns/tenant, 50-msg ring buffer, SSE keep-alive pings | Dashboard live telemetry | None — **no publisher exists** (gap G8) |
| POST /v1/tenants, GET /v1/tenant/settings|usage (`production_router.py:638,716,737`) | Tenant onboarding (provisions hashed public key, returns plaintext once); settings + real usage counts from DB | Dashboard settings | `tenants`, `api_keys`, `events`, `workflow_runs` |
| POST /privacy/export/{id}, POST /privacy/delete/{id}, GET /audit/export (`production_router.py:484,542,571`) | GDPR Art. 15 export (≤100 events, redacted), Art. 17 hard erasure, hash-chained audit export (≤100 records) | None | `visitors`, `profiles`, `events`, `audit_records` |
| POST /v1/sentinel/findings, GET /v1/sentinel/* (`production_router.py:918,944`) | Accept Sentinel findings for a registered site only; tenant resolved from api_keys/tenants, ambiguous ownership → 409; critical/high findings triaged | None | `sentinel_scans`, `sentinel_findings`, `api_keys`, `tenants` |
| POST /v1/friday/*, POST /execute|/plan|/decompose (`friday_router.py`, `main.py`) | FRIDAY service-key bridge: commands, health summary, priority leads, incidents, task envelope with approval gating for high-impact ops, outbound capability delegation | FRIDAY voice/OS | `leads`, `events`, `approval_queue`, `workflow_runs` |
| POST /v1/webhooks/{provider}, POST /v1/webhooks/stripe (`webhooks_router.py`, `stripe_webhook_router.py`) | Inbound webhooks: public key + HMAC-SHA256 signature, fail-closed in production; Stripe via `stripe.Webhook.construct_event`, only 2 event types forwarded | Stripe / HubSpot / etc. provider callbacks | `events` (generic provider), **not** for Stripe (gap G10) |
| Worker (`apps/worker/src/cortex_worker/main.py`) | Redis consumer group `cortex-worker-group`, at-least-once, bounded concurrency 4, PEL recovery every 30 s, DLQ after 5 attempts, approval auto-expiry every 60 s | None | Runs the 10-phase cognitive loop per event; `approval_queue` |
| Dashboard (`apps/dashboard/src/`, `lib/api.ts`) | Next.js pages (leads, visitors, analytics, experiments, funnels, automation, …) over real API via SWR + Bearer token from `localStorage` | The operator UI | All `/v1/*` reads/writes above |
| GET /, /dashboard, /sdk.js, /cortex.js (`main.py`) | Serve static dashboard export or fallback landing HTML; serve browser SDK (compiled bundle if present, else inline fallback that posts to `/v1/events`) | Every website embedding the SDK | None |

Dead surface (present in the tree, not reachable): `real_engines_router.py`
(7 routes under `/api/v1/real-engines/*`) is never imported by `main.py`, so
none of its routes exist in the app; the `.data/` JSON files
(`ab_tests.json`, `decision_history.json`, 417 KB) are read only by
`real_advanced_engines.py` / `real_decision_engine.py`, which are reachable
only through that unmounted router (gap G14).

## 3. Failure modes per operation

1. **Event ingestion, DB down.** Persist fails → production raises 500
   (`events_router.py:378–388`); non-production returns `status:
   "not_persisted"` instead of lying `accepted`. Dedupe claim is released so
   a retry is possible. Redis stream publish failure is **not** fatal: the
   event is persisted but `dispatched: false` (`events_router.py:262–267`) —
   the worker never sees it and nothing retries the publish.
2. **Event ingestion, Redis down.** Rate limit falls back to the in-process
   `AtomicSlidingWindow` (`events_router.py:124–138`); the fallback is
   per-process, so a multi-worker deployment enforces a higher effective
   limit. Dedupe cache is in-process (1 h TTL, 100 k entries,
   `cortex_upgrade/event_ingestion.py:65`); DB uniqueness is authoritative.
3. **Event ingestion, duplicate `event_id`.** Acknowledged as `duplicate`,
   not re-persisted, not re-dispatched. A batch containing a duplicate
   retries the rest individually (`events_router.py:486–506`).
4. **Event ingestion, oversized or cross-tenant payload.** 413 over 256 KB;
   403 when the payload names a tenant other than the credential's
   (`events_router.py:283–301`). Neutral placeholders (`default`,
   `tenant_default`, `unknown`, `self`) are treated as unspecified.
5. **Lead scoring, unknown lead.** `POST /api/v1/leads/score` computes and
   caches the score in memory, then the history insert hits the
   `lead_scores.lead_id → leads.id` FK and returns 404 — but the in-memory
   score **remains**, so follow-up/CLV then work for a lead that does not
   exist in the DB (`enhanced_crm.py:394–470`).
6. **Lead follow-up / CLV after restart.** Both read only the in-memory
   `_lead_scores` dict, so after any restart they 404 for every previously
   scored lead even though the history rows persist
   (`enhanced_crm.py:472,490`). A persisted read path already exists
   (`packages/analytics/.../__init__.py:158 get_score_history`, used by
   `understand_router.py:326`) and is simply not used here (gap G4).
7. **Marketing send/publish/activate.** Each flips a local `status` field
   and returns 200; no email, post or ad is ever delivered, and the record
   vanishes on restart (`marketing_platform_integrator.py:196,251,295`).
   An operator has no signal distinguishing "sent" from "marked sent".
8. **Marketing automation sequences / scheduled posts.** Nothing ever sends
   a sequence email (`send_email` has no route caller) and nothing polls
   for due scheduled posts; they sit in memory until restart
   (`marketing_automation.py`).
9. **Live streams.** Connections authenticate and then receive only
   pings/subscription acks — no event is ever broadcast, because no code
   calls `broadcast_to_channel` or `ws_manager.broadcast` (gap G8). A dead
   production-router connection is never removed on broadcast failure
   (`production_router.py:316–332` swallows the exception without
   disconnecting), so it occupies one of the 100 per-tenant slots until
   restart.
10. **Worker delivery.** At-least-once: a failed cognitive loop stays in the
    PEL and is reclaimed; after 5 attempts it is DLQ'd — except via the PEL
    recovery path, which acknowledges without DLQ (gap G9). A "partial" loop
    is acknowledged as delivered; a loop that fails every step is not
    (`apps/worker/src/cortex_worker/main.py:113–161`).
11. **Worker, Redis restart / FLUSHALL.** Consumer group is re-created on
    `NOGROUP` (`main.py:99–110`); events published while Redis is down are
    lost (ingestion already returned `dispatched: false`).
12. **Stripe webhook, Redis down.** Returns HTTP 200 with `status: "error"`,
    so Stripe never retries; the event is lost
    (`stripe_webhook_router.py:229–240`).
13. **Stripe webhook, replay.** Same Stripe event id maps to the same
    `event_id`, but the event is never persisted, so dedupe never applies;
    the worker re-runs the cognitive loop for the replay.
14. **Readiness, non-Oracle backend.** `/ready` runs `SELECT 1 FROM DUAL`
    (`production_router.py:240`), which fails on SQLite/PostgreSQL, so a
    dev-configured instance reports `NOT_READY` (503) even when healthy.
    Conversely `/health` and `/status` report only process liveness and say
    so (`evidence_class: process_liveness`).
15. **Tenant onboarding, key loss.** The plaintext public key is returned
    exactly once (`production_router.py:638–687`); there is no rotation or
    revocation endpoint in the API (only the `is_active` flag in the table).
16. **Dashboard, token storage.** The operator JWT lives in `localStorage`
    (`apps/dashboard/src/lib/api.ts:12–14`); any XSS in the dashboard origin
    can read it. No refresh flow exists.
17. **Approvals.** Pending approvals auto-expire after 24 h to `expired`
    with reason "Auto-rejected by platform safe-default policy"
    (`apps/worker/src/cortex_worker/main.py:274–303`); high-impact FRIDAY
    tasks wait for explicit approval (`friday_router.py:908,1067`).
18. **Privacy erasure, partial failure.** Erasure rolls back and returns 500
    with "nothing was reported as erased"
    (`production_router.py:542–570`) — fail-loud, correct.
19. **Public-key auth, DB down.** `authenticate_public_key` fails closed
    with 503 (`api_keys.py:52–60`). It also performs a `last_used_at` write
    + commit on **every** ingestion request, doubling write load per event.
20. **A/B test with no data.** `POST /api/v1/crm/ab-test` defaults to 50/1000
    vs 55/1000 conversions when no variant data is supplied
    (`enhanced_crm.py:329`) — a computed "result" from invented inputs
    (gap G18).

## 4. Real vs heuristic / simulated

| Surface | Verdict |
|---|---|
| Event ingestion, dedupe, rate limit, sessions, tenant scoping | Real (Oracle + Redis). |
| Lead scoring, grades, segments | Deterministic rule heuristic, honestly labelled with provenance (`enhanced_crm.py:130–230`; TASK-COR-002). `predicted_value = score × $100` is not revenue. |
| CLV, churn risk | Deterministic formulas over caller-supplied defaults, labelled as heuristic in the provenance block. |
| Follow-up suggestions | Template by grade. Real only while the process lives (gap G4). |
| `GET /v1/analytics/{metric}` | Real event counts. |
| `understand_router` funnel/cohort/attribution | Real, computed from stored events (≤500). |
| `advanced_analytics.py` | **Not real**: arithmetic on caller-supplied payloads; never reads the DB (gap G13). |
| Marketing send/publish/activate, CRM records | **Simulated**: local state flips / in-memory dicts; no provider call exists in the file (gap G5). Metrics honestly report `no_data` (TASK-REL-020). |
| Marketing automation ROI/funnels/journeys | Arithmetic on caller-supplied metrics; `spent` derived as 10% of any metric named `*spend*` (`marketing_automation.py:134`); conversion is a deterministic every-10th-lead rule (`:258`); unsubscribe rate hardcoded `1.0` (`:217`). |
| Demand forecast / ensemble | Naive trend extrapolation is implemented; ensemble honestly returns `no_data` (`predictive_demand_forecaster.py:377`). |
| A/B framework assignment | Deterministic md5-hash bucketing (standard). Results stored in memory only. |
| Competitive summary / market trends | IntelX-backed when configured, else an explicitly labelled deterministic baseline (`friday_router.py:734–793`). |
| FRIDAY outbound delegation | **Mock by default**: `MOCK_MODE` defaults to `true`, returns `accepted: true, "executed_by_friday"` without calling FRIDAY (`friday_router.py:677`, gap G15). |
| `/metrics` strategy gauge | Hardcoded `0.85` (`production_router.py:58`, gap G11). Counters are process-local and reset on restart. |
| Tenant plan limits | Display-only constants (enterprise: 10 sites, 5,000,000 events/mo, 365 d); never enforced (gap G12). Usage counts themselves are real DB counts. |
| Sentinel intake, privacy export/erase, audit export | Real, persisted, tenant-scoped. |
| Worker cognitive loop | Real orchestration; per-step outcomes recorded; see §3.10. |
| Dashboard | Real API calls (SWR); no mock data in `apps/dashboard/src/`. |

## 5. Gaps

Severity: **H** = data-loss / security / misleading-success; **M** = real
but broken or unenforced behaviour; **L** = hygiene / dead code.

- **G1 (H) — Platform credentials echoed in API responses.**
  `Cortex/apps/api/src/cortex_api/marketing_platform_integrator.py:442`
  (`connect_platform` returns `config.__dict__`, which contains the
  caller-supplied `api_key` and `api_secret` in plaintext) and `:455`
  (`get_connected_platforms` returns the same for every platform). The keys
  are also held in plaintext in process memory (`PlatformConfig`, `:24,134`).
  Fix: never return credential fields — return `connected` + a masked suffix
  only; store a hash/reference, not the secret; rotate any key ever returned
  by these endpoints.
- **G2 (H) — SSE stream auth is weaker than WebSocket auth.**
  `Cortex/apps/api/src/cortex_api/streaming_router.py:218–222` decodes the
  token with `jwt.decode(raw_token, secret, algorithms=["HS256","RS256"])`
  where `secret` is `JWT_SECRET` (`""` when unset — the `getattr(..., 
  "default_secret")` fallback is dead code because `auth.py` always defines
  `JWT_SECRET`). Unlike `ws_auth.py` it never fetches JWKS (so OIDC RS256
  tokens cannot verify), checks no audience/issuer, and a token with no
  `tenant_id` claim silently lands in `tenant_default`. Whether PyJWT
  accepts an empty HS256 key is **unverified** in this VM (PyJWT not
  installed); the RS256/audience/tenant-default defects are verified from
  the code. Fix: route SSE auth through
  `authenticate_websocket` (`ws_auth.py`) or an equivalent verifier.
- **G3 (H) — Enhanced-CRM scoring takes the tenant from the payload, and
  follow-up/CLV have no tenant check.**
  `Cortex/apps/api/src/cortex_api/enhanced_crm.py:408`
  (`tenant_id=payload.get("tenant_id", "")`) — an operator can score (and
  persist history) under any tenant, including `"unknown"` when omitted.
  `suggest_follow_up` (`:476`) and `predict_clv` (`:494`) look up the
  in-memory dict by `lead_id` alone with no tenant comparison, so any
  operator can read any tenant's scores. Fix: take `tenant_id` from the
  verified `user` dict on all three routes and scope lookups by
  `(tenant_id, lead_id)`, matching `public_gateway.py`.
- **G4 (H) — Scores, follow-up and CLV live only in process memory.**
  `enhanced_crm.py:100` (`_lead_scores` dict), `:102` (`_engagement_log`),
  `:284`. Restart (or a second worker) loses every score; follow-up/CLV
  then 404 for leads whose history rows persist. Fix: serve follow-up/CLV
  from `LeadScoreHistoryModel` via the existing `get_score_history`
  (`packages/analytics/src/cortex_analytics/__init__.py:158`); keep the
  dict as a cache at most.
- **G5 (H) — Marketing "send / publish / activate" deliver nothing; CRM
  records are phantoms.**
  `marketing_platform_integrator.py:196` (`status = "sent"`),
  `:251` (`status = "posted"`), `:295` (`status = "active"`) — no HTTP
  client exists in the file, so no SendGrid/Mailchimp/social/ad-platform
  call is ever made, yet the API returns 200 with the success status.
  `create_crm_record` (`:336`) stores HubSpot/Salesforce records only in
  the in-memory `_crm_records` dict — they never reach any external CRM
  and never reach the Oracle CORTEX schema. Fix: wire real provider
  clients with credentials from the secret store, or rename these
  endpoints to draft-only and return `data_status: "no_data"` (as the
  metrics already do); persist CRM records to Oracle or delete the
  endpoints.
- **G6 (M) — Marketing automation never executes.**
  `marketing_automation.py`: `send_email` has no route caller, nothing
  polls scheduled posts, journeys never advance on their own. IDs are
  sequential (`campaign_{len+1}`, `:111`, and the same pattern for
  sequences/journeys/posts/funnels), so a restart reuses IDs and silently
  overwrites earlier objects. `unsubscribe_rate` is hardcoded `1.0`
  (`:217`); journey conversion is a deterministic every-10th-lead rule
  (`:258`); `spent` is 10% of any metric named `*spend*` (`:134`). Fix:
  add a worker/scheduler or remove the execution-sounding endpoints; use
  uuid ids; drop the hardcoded metrics or label them simulated.
- **G7 (M) — Default datastore is SQLite, against the repo rule.**
  `config.py:83` (`postgres_dsn = "sqlite+aiosqlite:///./data/cortex.db"`)
  and `:132` (same fallback). Production is guarded (`:127–143` raises
  unless the DSN is Oracle), but any deployment where `APP_ENV` is unset
  or not `production` — including a staging box — silently persists CRM
  data (leads, visitors, tenants, audit chains) to a local SQLite file,
  and `CORTEX_SQLITE_TMPFS=true` can additionally move it to `/dev/shm`
  where it does not survive restart. `cortex_upgrade/persistence.py`
  (`DurableStore`, sqlite3 jobs/idempotency/outbox) is dead code — no
  caller — so it is not a live SQLite path. Fix: require an explicit
  opt-in (e.g. `CORTEX_ALLOW_SQLITE_DEV=true`) for the SQLite default and
  fail closed otherwise; verify the Server 2 unit sets `APP_ENV=production`
  (unverified — the unit file is not in the repo).
- **G8 (M) — Live streams have no publisher.**
  `streaming_router.py:89` (`broadcast_to_channel`) and
  `production_router.py:316` (`ConnectionManager.broadcast`) have zero
  callers anywhere in the repo. The authenticated WS/SSE endpoints accept
  connections and then deliver only pings and subscription acks. Fix: wire
  the worker (or the API post-persist) to fan events out to subscribers,
  or remove the endpoints rather than advertising live telemetry.
- **G9 (M) — PEL recovery drops exhausted events without DLQ.**
  `Cortex/apps/worker/src/cortex_worker/main.py:248`: when PEL recovery
  finds a message at `MAX_DELIVERY_ATTEMPTS` it `xack`s it and only logs.
  The normal delivery path DLQs first (`:189–190` poison,
  `:200–206` exhausted). Fix: call `route_to_dlq` before the ack at `:248`,
  same as `deliver_message`.
- **G10 (M) — Stripe webhooks are unattributed, unpersisted, and
  unretriable.**
  `stripe_webhook_router.py:163` hardcodes
  `tenant_id = CORTEX_DEFAULT_TENANT_ID` (default `"default"`) — every
  Stripe checkout/subscription lands in one tenant regardless of whose
  Stripe account sent it, and there is no per-tenant webhook secret.
  The event is pushed only to Redis, never to the `events` table, so
  replay dedupe cannot apply. On Redis failure it returns HTTP 200 with
  `status: "error"` (`:229–240`), so Stripe never retries. Fix: map the
  Stripe account/endpoint to a tenant, persist the event, return 5xx when
  enqueue fails.
- **G11 (M) — `/metrics` is open without a token; one gauge is fabricated.**
  `production_router.py:86–110`: when `METRICS_TOKEN` is unset the endpoint
  serves all counters to anyone. `strategy_performance_gauge` is hardcoded
  `0.85` (`:58`) and nothing in the repo ever updates it. Fix: require
  `METRICS_TOKEN` in production (or bind the endpoint to localhost);
  compute the gauge from `strategy_performance` or drop it.
- **G12 (M) — Tenant plan limits are displayed, never enforced.**
  `production_router.py:694–716` (`DEFAULT_TENANT_PLAN`: enterprise, 10
  sites, 5,000,000 events/mo, 365 d) — a grep confirms
  `monthly_event_limit`/`max_sites` are referenced nowhere else, so no
  ingestion path checks them. `GET /v1/tenant/usage` reports a `usage_pct`
  against a limit that does not exist as a control. Fix: enforce the
  monthly cap in `events_router.py` (or remove the limits from responses).
- **G13 (M) — Advanced analytics never reads the CRM store.**
  `advanced_analytics.py` contains no `select(`, no `db.execute`, no model
  read; the injected session (`:473`) is unused. Cohort/funnel/churn/
  revenue-forecast/cluster/anomaly all compute from caller-supplied
  payloads. Fix: compute from `EventModel`/`LeadModel` like
  `understand_router.py` does, or relabel the routes as calculators.
- **G14 (L) — Dead router and dead JSON persistence.**
  `real_engines_router.py` is never imported by `main.py` (7 routes
  unreachable); `apps/api/src/.data/ab_tests.json` and
  `decision_history.json` are read only by modules reachable through it.
  Fix: mount the router (with auth) or delete it and the `.data/` files.
- **G15 (M) — FRIDAY outbound delegation is mocked by default.**
  `friday_router.py:677`: `MOCK_MODE` defaults to `"true"`, so
  `POST /v1/friday/outbound/request` returns `accepted: true` with
  `"executed_by_friday"` without contacting FRIDAY (real call at `:694–
  696` has a 15 s timeout and is only reached when `MOCK_MODE=false`).
  Whether the Server 2 deployment sets `MOCK_MODE=false` is **unverified**
  — no `APP_ENV`/`MOCK_MODE` setting exists in the repo's Dockerfiles,
  deploy workflow or `docker-compose.yml` (which defaults it to `false`
  for the compose services only; production is systemd per `AGENTS.md`,
  and the unit file is not in the repo). Fix: default `MOCK_MODE` to
  `false`, and include `mocked: true/false` in the response.
- **G16 (L) — Identify defaults consent to granted; lead create accepts a
  caller-supplied score.** `public_gateway.py:60`
  (`consent_granted=payload.get("consent_granted", True)`) and `:194`
  (`score=payload.get("score", 50.0)`). Fix: default consent to `False`;
  do not accept `score` from the payload — score via the scoring engine.
- **G17 (L) — Dev-only auth escape hatches are live whenever
  `APP_ENV != production`.** `auth.py:38–40` (`CORTEX_DEV_AUTH_BYPASS`,
  opt-in flag, loudly logged — correctly off in production);
  `auth.py:201` (mock operator token `NEXT_PUBLIC_OPERATOR_TOKEN` default
  accepted when no JWT validates, non-production only);
  `main.py:131–157` (dev bootstrap key: plaintext logged once at boot).
  Fix: log only the key prefix at bootstrap; gate the mock-operator token
  behind the same explicit bypass flag. Verify the Server 2 unit does not
  set these flags (unverified — unit file not in repo).
- **G18 (L) — A/B test defaults fabricate inputs.**
  `enhanced_crm.py:329`: no variant data → 50/1000 vs 55/1000 conversions.
  Fix: require `variant_a_data`/`variant_b_data`, 400 otherwise.
- **G19 (L) — Unbounded in-memory engagement log.**
  `enhanced_crm.py:102,284`: `_engagement_log` appends forever, never
  read by any route. Fix: cap it or remove it. (Same pattern:
  `marketing_platform_integrator.py` `_analytics_events` list is
  unbounded.)
- **G20 (L) — `/ready` is Oracle-only.**
  `production_router.py:240` (`SELECT 1 FROM DUAL`) fails on
  SQLite/PostgreSQL, so dev instances report `NOT_READY`. Fix: use a
  dialect-appropriate probe (`SELECT 1` / connection ping).

## 6. PR #26 auth verification — route-level auth, current state

PR #26 itself is not locatable from this clone: no merge commit in local
history references `#26`, and no Cortex doc mentions it. What can be
verified is the **current** state, which is what the board asked for.

What was checked:

1. **Full route inventory by AST.** All 303 route functions in
   `Cortex/apps/api/src/cortex_api/` were enumerated with their
   per-function auth dependencies, and each router's mount in
   `main.py` was checked for a router-level dependency.
2. **Mount table in `main.py`.** Routers mounted with
   `dependencies=[Depends(require_cortex_route_access)]` — which requires
   JWT `cortex_viewer` for GET/HEAD/OPTIONS and `cortex_operator` for
   writes, or `X-Friday-Api-Key` as `friday_system` (`main.py`,
   `require_cortex_route_access`): marketing platform integrator, demand
   forecaster, agent budgets, attribution, A/B experiment framework,
   competitive intel, conflict resolver, decision recommendation, risk
   framework, recommendation engine, A/B test framework, predictive
   analytics, marketing automation, content creator, customer journey
   optimizer, segmentation, campaign optimizer, recommendation
   personalizer, decision impact, strategic foresight, partner network,
   decision tree, decision fatigue, real inbox. 145 route functions have
   no per-function auth dependency; of those, 119 are covered by these
   router-level mounts, 19 by documented credential-in-handler mechanisms
   (item 4), and 7 belong to `real_engines_router.py`, which is never
   mounted — unreachable dead code, not an exposure (gap G14).
3. **Routers mounted bare, relying on per-route deps — all verified
   guarded:** `enhanced_crm.py` (6/6 `require_role`), `advanced_analytics.py`
   (8/8), `advanced_operations_router.py` (43/43), `friday_router.py`
   (21/21 `verify_friday_token` / `require_role`), `public_gateway.py`
   (10/10, viewer read / operator write, tenant-scoped queries),
   `understand_router.py` (17/17), `production_router.py` (all operator
   endpoints `require_role`; see below for the deliberate exceptions),
   `events_router.py` (ingest via `X-Cortex-Public-Key` in-handler,
   `events_router.py:312,428`; query via viewer role).
4. **Credential-in-handler routes, verified against
   `tests/unit/test_route_authorization.py` (`CREDENTIAL_IN_HANDLER`):**
   `/` + `/dashboard` (static/SPA), `/v1/health` + `/health` + `/status`
   (liveness only), `/ready` + `/health/ready` (readiness, no principal by
   design), `/metrics` (optional token — gap G11), `/sdk.js` +
   `/cortex.js` (public SDK), `/{file_name:path}` (static export),
   `POST /v1/events(+/batch)` (public key), `POST /v1/webhooks/{provider}`
   (public key + HMAC, `webhooks_router.py`), `POST /v1/webhooks/stripe`
   (Stripe signature, `stripe_webhook_router.py`), `GET /v1/stream/sse`
   (JWT in-handler — gap G2), both WebSockets (`authenticate_websocket`,
   `ws_auth.py`, signature-verified, 1008 on failure).
5. **Auth primitives read end to end:** `auth.py` — JWT RS256 via OIDC
   JWKS with HS256 fallback, fail-closed in production when `JWT_SECRET`
   is missing/short; `verify_friday_token` constant-time compare;
   `require_role` hierarchy (`ROLE_HIERARCHY`); dev bypass opt-in only
   (`CORTEX_DEV_AUTH_BYPASS`, never in production); `api_keys.py` —
   SHA-256-hashed public keys, 401 unknown/inactive, 503 when the store
   is unreachable, site-scoped.
6. **Tenant isolation spot-checked in code:** visitor/lead reads scope by
   `auth["tenant_id"]` (`public_gateway.py:71–72,118–119`); session
   hijack → 403 (`events_router.py:167–174`); audit cross-tenant read
   requires admin (`public_gateway.py:303`); Sentinel tenant resolution
   rejects ambiguous ownership with 409
   (`production_router.py:816–847`). Isolation tests exist
   (`tests/unit/test_tenant_isolation_reads.py`,
   `test_tenant_isolation_mutations.py`,
   `tests/integration/test_multi_tenant_isolation.py`) — read, not run.

**Verdict: the route-level auth fix holds.** No unauthenticated route to
CRM data was found: every operator/mutation route requires JWT RBAC or the
FRIDAY service key, every public ingestion route requires a provisioned
public key (or a verified webhook signature), and the inventory test
`tests/unit/test_route_authorization.py` (which fails the build on any
unguarded route) covers the same surface. Two weaknesses remain inside
that verdict: the SSE auth gap (G2) and the unenforced `/metrics` token
(G11). The remaining auth-adjacent gaps are G3 (tenant from payload in
CRM scoring), G15/G17 (mock/default auth paths that are live whenever
`APP_ENV != production`), and the unverifiable production environment
variables (whether Server 2 actually runs with `APP_ENV=production` and
`MOCK_MODE=false` — the repo contains no systemd unit or env file to
confirm it).

## 7. Verification

- AST inventory of all 303 route functions in
  `Cortex/apps/api/src/cortex_api/` — every file parsed; 145 functions
  have no per-function auth dep, of which all are covered by router-level
  mounts or documented credential-in-handler mechanisms except the gaps
  listed (G2, G11).
- `git log ecea58e..254c2df1 -- Cortex/` — 0 commits: the audited tree is
  current with main for Cortex.
- Schema: 17 ORM tables in `db_models.py`, 17 `create_table` calls across
  `infra/alembic/versions/001`–`009`; the repo's own parity test asserts
  the match (not run — see below).
- `grep` sweeps: `sqlite` (15 files — only `config.py` default DSN and the
  dead `DurableStore` are live concerns), `broadcast_to_channel` /
  `ws_manager.broadcast` (zero callers), `monthly_event_limit` /
  `max_sites` (no enforcement), `real_engines_router` (never imported),
  `DurableStore` (no callers), `MOCK_MODE` / `APP_ENV` in deploy files
  (no production setting in repo).
- **Not verified / not run:** no test suite was executed (pytest, FastAPI,
  SQLAlchemy and PyJWT are not installed in this VM); no live server, DB
  or Redis was available, so no endpoint was exercised and no timing was
  measured; production environment variables on Server 2 (`APP_ENV`,
  `MOCK_MODE`, `JWT_SECRET`, `METRICS_TOKEN`, `STRIPE_WEBHOOK_SECRET`)
  could not be confirmed from the repo; whether PyJWT accepts an empty
  HS256 key (relevant to G2) was not testable here.

## 8. Follow-ups for the board

1. G1, G2, G5 — security / misleading-success; fix before advertising the
   marketing surface or the SSE stream as live.
2. G3, G4 — CRM tenant scoping and score durability; the persisted history
   already exists, the routes just do not use it.
3. G7, G15, G17 — confirm the Server 2 deployment environment
   (`APP_ENV=production`, `MOCK_MODE=false`, no dev bypass flags); the
   repo cannot prove any of these.
4. G8, G9, G10, G12, G13 — wire, enforce, or delete: live streams, DLQ
   parity, Stripe attribution, plan limits, analytics data source.
5. G14, G18, G19, G20 — small cleanups; G6 needs a product decision
   (scheduler vs removal).
