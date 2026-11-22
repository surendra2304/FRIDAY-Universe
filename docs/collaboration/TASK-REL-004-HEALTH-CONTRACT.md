# TASK-REL-004 — Health-Capability Contract (DESIGN)

**Task:** TASK-REL-004 — "Health-endpoint honesty (design): agents report
capability state, not just process liveness" (P1, owner Muse 9, branch
`muse9/task-rel-004`, board status CLAIMED).
**Base surveyed:** main `d51b82df3a3d9ab17bf05bc38f9d31d994e2cc6f` (2026-11-22).
**Status of this document:** DESIGN ONLY. No implementation. This design is
reviewed on issue #35 before any implementation task is opened; implementation
is a separate task (see §7, out of scope).

## 0. The defect this contract fixes

Every agent's `/health` today reports `evidence_class: process_liveness` (or
an equivalent constant), and most of them return top-level `status: ok /
healthy` with HTTP 200 unconditionally. The live example, recorded on the
board for TASK-REL-003: on 2026-11-14 Stratex's `/health` answered HTTP 200
with `engine: offline`, `engine_healthy: false` and
`STALE_STRATEGY_EVALUATION` (last evaluation ~1,039,907 s ago) — while the
top-level `status` still read `ok`.

FRIDAY's fleet-status path then compounds the lie. `FleetClient`
(`FRIDAY/src/friday/ecosystem/fleet_client.py`, `_classify_health_response`)
classifies a peer from its top-level `status`/`health`/`state` string alone:
`"ok" | "healthy" | "online" | "up" | "ready"` → `ONLINE`. A degraded agent
that answers `status: ok` is therefore reported ONLINE, and FRIDAY's
fleet-status answer (`FRIDAY/src/friday/tools/builtin/fleet_status.py`) can
only cite reachability — its own docstring says so: "the scope is stated
explicitly: peer endpoint reachability only, not task-level verification."

Two secondary facts the survey established:

- The honest signal already exists in pieces. Stratex's `/health` body
  already carries `engine` / `engine_healthy` / `engine_trading_capable` /
  `capability_reasons`; Memora's `/health` already returns HTTP 503 with
  `status: degraded` when its stores fail; most agents' `/ready` already
  probes real dependencies and returns 503. The defect is concentrated in
  the **top-level `/health` status and HTTP code**, not in the absence of
  probes.
- The fleet is not uniform. `/health` ranges from "no checks at all"
  (Cortex, VyralX) to "probes DB, vector store and event store and degrades
  honestly" (Memora). A contract that pretends all ten agents are alike will
  be ignored; §5 maps each agent individually.

## 1. Survey: what each agent's `/health` proves today

All findings are from the route handlers in source at the base above, not
from docs about them. "HTTP" is the code the handler returns in the
degraded case (verified from the handler's return/raise paths).

| Agent | `/health` handler | Top-level status values / HTTP | What it actually proves |
|---|---|---|---|
| FRIDAY | `FRIDAY/src/friday/api/server.py:1299` (`/health`, `/api/health`) | `status` = `healthy` / `degraded` / `failed`, HTTP **always 200** | Process alive + `friday` and `friday_deep` modules import (`FRIDAY/src/friday_deep/health.py:40` — checks are `python`, `platform`, and one import per module; `failed` is never emitted by `build()`, only `healthy`/`degraded`). Proves nothing about the DB, memory backend, mesh peers, or the LLM gateway. `peers_mesh` is included but its semantics were not fully traced here (see §6). |
| Inference | `Inference/app/health.py:42` | `status: healthy`, HTTP **always 200** | Process alive + specialist-registry size (`active_specialist_agents`). `providers` is a **static list of names** (`groq`, `cerebras`, `openrouter`, `gemini`, `nvidia`) — not probed. |
| Memora | `Memora/apps/api/routers/health.py:29` (`GET /health`, `HEAD`) | `status: healthy` / `degraded`, HTTP **200 / 503** | Process alive + live Oracle `SELECT 1` + event-store backend + vector-store readiness (Oracle 23ai adapter when backend is Oracle). The only agent whose `/health` already degrades honestly on the HTTP code. BUT its `evidence_class` still says `process_liveness` — the label lies about the content. |
| Stratex | `Stratex/dashboard.py:1302` (`/health`, `/api/health`) | `status: ok`, HTTP **always 200** | Process alive. The body *also* carries the engine truth (`engine`, `engine_healthy`, `engine_trading_capable`, `capability_reasons`, `capability_warnings`, `heartbeat_age_seconds`, `pid_alive`, `binance_connected`, `websocket_connected`, `active_strategy`, `strategies`, `last_strategy_evaluation`) — but the top level contradicts it. **This is the reference implementation to build on.** |
| Futuris | `Futuris/futuris/api/app.py:476` | `status: ok` / `degraded`, HTTP **always 200** | Process alive + measured storage verdict (`verify_schema()`). Degraded still returns 200, so HTTP clients cannot see it. |
| IntelX | `IntelX/intelx/api/v1/health.py:18` (`/healthz`, `/health` alias) | `status: ok`, HTTP **always 200** | Process alive only, by design (TASK-INT-012: no DB work in the handler). `database: "not_checked"` is stated explicitly — honest, but it means `/health` says nothing about the DB. |
| Forge | `Forge/app/api/health.py:63` | `status: ok`, HTTP **always 200** | Process alive + a real DB ping reported as `database_connected` (bool). Liveness is deliberately independent of the DB. NOTE: a second `/health` exists in `Forge/app/api/routes.py:74` that also probes the default model provider and can return `degraded`; it is shadowed at `/health` and `/api/health` because `health_router` is mounted first in `Forge/app/main.py:414`, and only reachable as `/api/v1/health`. Three paths, two semantics — see §6. |
| Sentinel | `Sentinel/sentinel/apps/api/main.py:463` | `status: ok`, HTTP **always 200** | Process alive + SHA-256 audit-chain integrity (`audit_chain_valid`, `audit_chain_vacuous` when 0 entries) + durability flag (`audit_durable`, `in_memory_backend_lost_on_redeploy` when not Oracle). Proves nothing about DB connectivity. |
| Cortex | `Cortex/apps/api/src/cortex_api/production_router.py:184` | `status: healthy`, HTTP **always 200** | Process alive only. **No checks of any kind** — the handler returns a constant. |
| VyralX | `VyralX/app/main.py:133` | `status: ok`, HTTP **always 200** | Process alive only. **No checks of any kind** — the handler returns a constant. |

### 1.1 `/ready` endpoints — what they check today

`/ready` is where the honest probing mostly already lives. The contract in
§2 keeps `/ready` as the dependency gate and fixes `/health` to stop
contradicting it.

| Agent | `/ready` handler | Checks | HTTP on failure |
|---|---|---|---|
| FRIDAY | `FRIDAY/src/friday/api/server.py:1319` (`/ready`, `/api/ready`) | Real DB round-trip (`SELECT 1` SQLite / `SELECT 1 FROM DUAL` Oracle, per configured backend), disk free ≥ 50 MB, runtime-environment validation; production + non-Oracle backend → not ready | 503 (`not_ready`) |
| Inference | `Inference/app/health.py:76` (`/ready`); also `/health/ready` at :222 (registry count ≥ 10 only — **not** end-to-end readiness, per its own docstring) | Memory-backend `SELECT 1` + key pools non-empty (configuration only, no provider probe) | 503 |
| Memora | `Memora/apps/api/routers/health.py:68` (`/health/ready`); root `/ready` at `Memora/apps/api/main.py:448` delegates to it | DB `SELECT 1` + vector-store readiness + circuit breakers healthy | 503 |
| Stratex | `Stratex/dashboard.py:1324` (`/ready`, `/api/ready`) | `engine_healthy` AND `engine_trading_capable` AND no panic/kill-switch; Oracle `SELECT 1 FROM DUAL`; production + non-Oracle → not ready | 503 |
| Futuris | `Futuris/futuris/api/app.py:493` | DB round-trip `SELECT 1` + schema completeness (`verify_schema()`; `missing` tables listed) | 503 |
| IntelX | `IntelX/intelx/api/v1/health.py:51` (`/readyz`; no `/ready` alias) | DB health + local-storage write test + model-provider **configuration only** (endpoint/key present; no upstream probe). `MOCK_MODE` makes the provider check pass trivially. | 503 |
| Forge | `Forge/app/api/health.py:93` (`/health/ready`, `/ready`) | DB ping + workspace directory write test; production + non-Oracle → 503 | 503 (via `HTTPException`) |
| Sentinel | `Sentinel/sentinel/apps/api/main.py:489` | Crypto sign test, audit-chain integrity, event bus present, storage backend configured, durability gate in production. `database` field is **derived, not probed**: `"connected"` iff `database_wal` (engine present in production, `True` outside production) and audit integrity — there is no DB query in the handler. `peer_connectivity: "not_checked"`. | 503 (`DEGRADED`) |
| Cortex | `Cortex/apps/api/src/cortex_api/production_router.py:220` (`/ready`, `/health/ready`) | Oracle `SELECT 1 FROM DUAL` + schema (missing tables) + Redis ping. Peer integrations (AI Universe, Sentinel, IntelX, Futuris) are explicitly `UNKNOWN: no live readiness probe configured` and are **not fatal**. | 503 (`NOT_READY`) |
| VyralX | `VyralX/app/main.py:147` | DB `SELECT 1` + ffmpeg binary present + worker heartbeat fresh (only when `worker_required`) + media warehouse connected with tables found | 503 (`degraded`) |

### 1.2 Adjacent endpoints (for the record, not part of the contract)

- FRIDAY `/api/v1/health/universe` (`FRIDAY/apps/core/src/friday_core/universe_health_monitor.py:199`,
  mounted at `/api/v1` in `server.py:6336`) reports self-reported
  `overall_score` / `healthy_agents` / alerts from a monitor that agents
  report into — it is **not** a probe of the agents and must not be cited as
  one.
- FRIDAY `/health/deep` (`FRIDAY/apps/core/src/friday_core/real_deep_api_server.py:375`)
  returns a constant `{"status": "healthy", "engines": 7, ...}`. Whether that
  app is mounted in the live FRIDAY process was **not verified**; treat it as
  unmounted until proven otherwise.
- Inference `/v1/health` (`Inference/app/api/v1_core_routes.py:110`) returns a
  constant `healthy` plus registry counts — no dependency check.
- Inference `/health/detailed` (process runtime snapshot) and
  `/health/providers` (observed provider-call outcomes, explicitly "no direct
  provider probes") are honest about their scope; they stay as-is.
- Stratex `Stratex/api/master_control_api.py:34` (`/health` on the master-control
  blueprint) reports in-process autonomy objects as `INITIALIZED` /
  `UNAVAILABLE` with overall `PARTIAL` / `DEGRADED`, and names six
  unverified subsystems. Its mount path in the live app was **not verified**;
  it is a secondary surface, not the fleet-facing `/health`.
- Memora `/health` takes its DB session via a FastAPI `Depends(get_db)`; what
  happens when the dependency itself fails (before the handler body runs) was
  **not verified** from source — the implementation task must confirm the
  failure mode (expected: 500, which is honest, but unconfirmed).

## 2. The contract

### 2.1 Vocabulary

- **Process liveness** — the process is running and answering HTTP. Nothing
  more. This is all `/health` may claim on its own.
- **Capability** — a named thing the agent must be able to *do* for its core
  job (e.g. Stratex: trade; Memora: store and retrieve; Inference: route to
  a live provider). A capability is either demonstrated by a fresh,
  successful check, or it is not claimed.
- **Dependency** — something the agent relies on (database, Redis, vector
  store, provider keys, ffmpeg, worker heartbeat). A dependency check is a
  live probe or a fresh observed fact, never a config string.
- **Reachability** — FRIDAY got an HTTP answer from the peer at all. This is
  a fact about the probe, not about the peer.
- **`unknown`** — the honest value when a check has not run, has no probe,
  or its result is stale. `unknown` is never mapped to `ok`, and never
  treated as fatal unless the capability is required (§2.4).

### 2.2 Required fields on every agent's `/health`

Backwards-compatible additive change: existing fields stay; the new fields
are added. No existing field changes meaning.

```json
{
  "status": "ok | degraded | unavailable",
  "service": "<agent id, as today>",
  "agent": "<agent name, as today>",
  "evidence_class": "capability_report",
  "observed_at": "<ISO 8601 UTC, as today>",
  "version": "<as today>",
  "capabilities": {
    "<capability name>": {
      "state": "ok | degraded | unavailable | unknown",
      "evidence": "<what was actually checked, e.g. 'heartbeat age 12s, pid alive'>",
      "checked_at": "<ISO 8601 UTC>",
      "detail": "<machine-readable reason code when not ok, e.g. STALE_STRATEGY_EVALUATION>"
    }
  },
  "dependencies": {
    "<dependency name>": {
      "state": "ok | degraded | unavailable | unknown",
      "evidence": "<what was actually checked>"
    }
  }
}
```

Rules:

1. **`status` is derived, never constant.** `status` = `ok` iff every
   *required* capability and every *required* dependency is `ok`.
   Otherwise `degraded` (something required is degraded/unavailable but the
   process can still answer) — `unavailable` is reserved for "this agent
   cannot answer for itself" and is normally produced by the *caller*
   (FRIDAY), not by the agent.
2. **HTTP code follows `status`.** `ok` → 200. `degraded` → **503**.
   This is the single most important change: today 9 of 10 agents return
   200 while degraded. (Memora and the `/ready` endpoints already do this;
   the contract extends the existing convention, it does not invent one.)
   Load-balancer / Caddy health checks must be pointed at `/ready`, not
   `/health`, if they need a "route traffic" signal — `/health` 503 means
   "degraded", not "dead"; see §2.5.
3. **`evidence_class` becomes `capability_report`.** The value
   `process_liveness` is retired from `/health` responses: a response that
   carries capability states is not a liveness report. Any endpoint that
   genuinely reports liveness only must keep `process_liveness` and must not
   carry a `status` value any consumer could read as a health verdict.
4. **Capability state values are closed.** `ok`, `degraded`, `unavailable`,
   `unknown` — nothing else. Free-text states (`"healthy"`, `"connected"`,
   `"UP"`, `"READY"`) stay inside `evidence`/`detail` strings, never as the
   state itself, so FRIDAY's classifier (§4) can match on four values.
5. **Every non-`ok` capability carries a `detail` reason code.** Reason
   codes are stable, uppercase, grep-able strings (Stratex's existing
   `STALE_STRATEGY_EVALUATION`, `HEARTBEAT_FILE_MISSING` are the pattern).
   Free-text explanations go in `evidence`, never as the only record.
6. **Staleness is a state, not a gap.** A check whose last successful run is
   older than its freshness bound reports `degraded` with
   `detail: STALE_<THING>` — it never silently reports the last good value
   as current. Each capability declares its freshness bound in §5 (e.g.
   Stratex strategy evaluation: 900 s, already in code).
7. **No capability may be reported from configuration alone.** "Key is
   configured" is not "provider is reachable"; "strategy is loaded" is not
   "strategy evaluated in the last 900 s". Where only a config check exists
   today (Inference key pools, IntelX provider config), the capability
   reports `unknown` with `detail: CONFIG_ONLY` until a live probe exists.
8. **No secrets in any field.** Reason codes, counts, ages, and backend
   names only — never keys, tokens, DSNs, or error strings containing
   credentials. (Existing handlers already leak raw exception text in places,
   e.g. Futuris `/ready` `error: f"{type(exc).__name__}: {exc}"` and Cortex
   `DOWN: {str(exc)[:50]}` — the implementation task must scrub those; this
   design does not change them.)

### 2.3 Capability states — the fleet-wide state model

`ok` / `degraded` at the top level are not enough; the states below are the
contract's headline model. Each maps to a top-level `status` and HTTP code
per §2.2 rules 1–2.

| State (capability / dependency) | Meaning | Top-level `/health` | HTTP |
|---|---|---|---|
| `ok` | Fresh, successful check | `ok` (if all required are `ok`) | 200 |
| `degraded` | Partially working, or stale, or one of several redundant paths down | `degraded` | 503 |
| `unavailable` | The thing the capability needs is down / absent (DB unreachable, engine offline, no strategies loaded, worker heartbeat missing) | `degraded` | 503 |
| `unknown` | No probe exists, the probe has never run, or the result is older than the freshness bound with no `STALE_` detail yet | `degraded` if the capability is **required**, `ok` if **optional** and explicitly marked so (see §2.4) | 503 / 200 |

Named degradation conditions (the ones the fleet actually hits — each is a
capability/dependency state, not a new top-level status):

| Condition | Example in the fleet today | Capability affected | Required? |
|---|---|---|---|
| **engine_offline** | Stratex: heartbeat stale/missing, worker not RUNNING, PID dead | `trading_engine` → `unavailable`, `detail: HEARTBEAT_FILE_MISSING` / `STALE_STRATEGY_EVALUATION` | yes |
| **no_executable_strategy** | Stratex: zero strategies loaded / evaluation stale > 900 s | `trading_capable` → `unavailable` / `degraded` | yes |
| **panic_or_kill_switch** | Stratex: panic active / kill switch locked | `trading_capable` → `unavailable`, `detail: PANIC_ACTIVE` / `KILL_SWITCH_LOCKED` | yes |
| **database_unreachable** | Any agent: DB round-trip fails | `database` dependency → `unavailable` | yes (all agents are Oracle-backed in production) |
| **schema_incomplete** | Futuris/Cortex: required tables missing | `database_schema` → `unavailable`, `detail` lists missing tables | yes |
| **dependency_down** | Cortex: Redis down; VyralX: media warehouse down | named dependency → `unavailable` | yes if the agent needs it to serve, else optional (declared per agent in §5) |
| **provider_unconfigured** | Inference: no key pools; IntelX: provider key/endpoint missing | `model_routing` / `model_provider` → `unavailable` (config-only today → `unknown`, §2.2 rule 7) | yes for Inference; yes for IntelX when not in `MOCK_MODE` |
| **worker_stale_or_missing** | VyralX: worker heartbeat stale/missing | `queue_worker` → `degraded` / `unavailable` | only when `worker_required` |
| **tooling_missing** | VyralX: ffmpeg binary absent; Forge: workspaces not writable | `rendering` / `workspaces` → `unavailable` | yes |
| **audit_chain_broken** | Sentinel: `audit_chain_valid == false` | `audit_chain` → `unavailable` | yes |
| **record_not_durable** | Sentinel: non-Oracle storage backend in production | `audit_durability` → `unavailable` | yes in production, optional otherwise (as today) |
| **peer_unknown** | Cortex: peer integrations have no live probe | peer capability → `unknown`, `detail: NO_LIVE_PROBE` | **no** (optional; never fatal — as today) |

### 2.4 Required vs optional

- A capability/dependency is **required** if the agent cannot do its core
  job without it. Required + not `ok` ⇒ top-level `degraded` + HTTP 503.
- A capability/dependency is **optional** if it is a nice-to-have
  integration. Optional + `unknown`/`degraded` does **not** change the
  top-level status, but it must still be listed with its true state — it
  must never be omitted to make the payload look clean, and never reported
  as `ok`.
- The required/optional split is declared per agent in §5 and is part of
  the contract — an implementation task may not silently reclassify a
  required capability as optional to get a green status.

### 2.5 `/health` vs `/ready` — division of labour after this contract

| | `/health` | `/ready` |
|---|---|---|
| Question it answers | "What can this agent actually do right now?" | "May traffic / work be routed to this agent?" |
| Content | Full capability + dependency report (§2.2) | Gate verdict over the same checks (may reuse them) |
| HTTP | 200 iff `ok`, else 503 | 200 iff ready, else 503 (unchanged) |
| Consumers | FRIDAY fleet-status, operators, dashboards | Caddy / Docker HEALTHCHECK / orchestrators (unchanged) |
| Rule | Must never contradict `/ready`: if `/ready` is 503, `/health` must be `degraded`. The reverse need not hold — an agent can be healthy-but-not-ready (e.g. starting up) — but the implementation must say which direction each agent allows. | Unchanged, except it must consume the same capability checks where they exist instead of re-probing (Stratex already does this via `_health_payload`). |

### 2.6 What the contract deliberately does NOT standardise

- Field names inside each agent's *existing* payload (`engine_healthy`,
  `database_connected`, `audit_chain_valid`, …) stay as they are. The
  contract adds `capabilities` / `dependencies`; it does not rename history.
- Check internals (heartbeat files, thresholds, SQL) stay per-agent. Only
  the state vocabulary (§2.2 rule 4) and the status/HTTP derivation
  (§2.2 rules 1–2) are fleet-wide.
- No new endpoint is required. Agents keep their existing paths, including
  IntelX `/healthz`/`/readyz` and Forge `/api/v1/health`.

## 3. Per-agent capability inventory (the contract's normative core)

Capability names are the contract's canonical names; each agent's
implementation maps its existing probes onto them (§5). Freshness bounds in
seconds are the bound after which a check is `degraded`/`STALE_*`.

- **FRIDAY** — capabilities: `orchestration` (required; evidence: process
  answering + `friday`/`friday_deep` import checks — today that is all it
  proves, and the contract requires it to say so, not more), `memory_backend`
  (required; evidence: the same DB round-trip `/ready` already performs —
  today `/health` does not check it at all), `peer_mesh` (optional;
  evidence: `peers_mesh` state as reported, labelled with its provenance —
  see §6 open question). Dependencies: `database` (required), `disk`
  (required, ≥ 50 MB free, as `/ready` already enforces).
- **Inference** — capabilities: `model_routing` (required; evidence: key
  pools non-empty today → reports `unknown` / `CONFIG_ONLY` until a live
  provider probe exists, §2.2 rule 7), `specialist_registry` (required;
  evidence: registry count, threshold ≥ 10 as `/health/ready` already
  uses). Dependencies: `database` (required, `SELECT 1` as `/ready`
  does). The static `providers` name list must be labelled
  `configured_providers`, never presented as probed health.
- **Memora** — capabilities: `memory_store` (required; DB `SELECT 1`),
  `event_store` (required; Oracle backend present), `vector_search`
  (required; active-backend readiness — Oracle 23ai adapter when backend
  is Oracle, as `/health` already does). Dependencies: `database`
  (required), `vector_store` (required), `circuit_breakers` (required —
  today only in `/ready`; surface in `/health` too). Smallest change in the
  fleet: mostly a relabel (`evidence_class` → `capability_report`) plus the
  capabilities block.
- **Stratex** — capabilities: `trading_engine` (required; heartbeat age ≤
  90 s + worker RUNNING + PID alive), `trading_capable` (required; engine
  healthy + ≥ 1 executable strategy + evaluation fresh ≤ 900 s + no panic /
  kill-switch; FUTURES-mode daemon snapshot is an accepted alternate
  witness, as in code today), `market_data` (required; `binance_connected`
  + `websocket_connected` — today these default to `True` when the heartbeat
  omits them; the contract requires the default to be `unknown`, not `True`).
  Dependencies: `database` (required; Oracle `SELECT 1 FROM DUAL` as
  `/ready` does — today `/health` does not report it at all). This is the
  reference mapping: every field the contract needs already exists in the
  `/health` body; the implementation is a derivation, not a new probe.
- **Futuris** — capabilities: `forecasting` (required; evidence: storage
  schema ready — today that is the only measured fact, and the contract
  requires it to be labelled as storage readiness, not forecasting
  ability), `storage` (required; `verify_schema()`). Dependencies:
  `database` (required; round-trip + schema, as `/ready` does).
  **Gap:** no probe of the forecasting models themselves exists anywhere in
  the surveyed code; `forecasting` can only honestly report `unknown`
  (detail `NO_MODEL_PROBE`) until one is built.
- **IntelX** — capabilities: `research` (required; evidence: none live
  today → `unknown`, detail `NO_LIVE_PROBE`, until a probe exists),
  `model_provider` (required when not `MOCK_MODE`; config-only today →
  `unknown` / `CONFIG_ONLY`). Dependencies: `database` (required),
  `storage` (required; writable data dir, as `/readyz` does). `mock_mode`
  must be surfaced in the capabilities block (today it is a top-level flag
  only): in `MOCK_MODE`, `research` reports `degraded` with detail
  `MOCK_MODE` — synthetic findings must never present as `ok`.
- **Forge** — capabilities: `code_build` (required; evidence: none live
  today → `unknown`, detail `NO_LIVE_PROBE` — `/health` proves process +
  DB only; the `ai_universe` health in `/health/detailed` is a separate
  surface), `model_provider` (required; evidence: the provider health check
  that `routes.py:74` already performs — reachable today only via
  `/api/v1/health`; the contract requires one canonical `/health` to carry
  it — see §6). Dependencies: `database` (required, ping as today),
  `workspaces` (required, writable as `/ready` does).
- **Sentinel** — capabilities: `security_engine` (required; evidence: the
  process is answering and the crypto sign test passes — today
  `security_engine: "active"` is a constant string; the contract requires it
  to be backed by the `/ready` crypto check or labelled `unknown`),
  `audit_chain` (required; `audit_chain_valid`, with `audit_chain_vacuous`
  surfaced when 0 entries — an empty chain verifying is not evidence of a
  healthy record), `audit_durability` (required in production; Oracle
  backend, as today). Dependencies: `database` (required in production;
  **gap:** no DB query exists in either handler today — the `database`
  field is derived, §1.1 — a real probe is required before `database` can
  report `ok`), `event_bus` (required; initialised, as `/ready` checks).
- **Cortex** — capabilities: `crm` (required; evidence: none live today →
  `unknown`, detail `NO_LIVE_PROBE` — `/health` is a constant), `website`
  (required; same gap). Dependencies: `database` (required; `SELECT 1 FROM
  DUAL` + schema, as `/ready` does), `redis` (required, as `/ready` does),
  peers (`ai_universe`, `sentinel`, `intelx`, `futuris`) — optional,
  `unknown` / `NO_LIVE_PROBE`, never fatal (as today).
- **VyralX** — capabilities: `rendering` (required; ffmpeg present, as
  `/ready` does), `queue_worker` (required iff `worker_required`; heartbeat
  fresh within timeout and state ≠ `stopped`, as `/ready` does),
  `content_pack` (required; evidence: none live today → `unknown`).
  Dependencies: `database` (required; `SELECT 1`), `media_database`
  (required iff configured; connected + tables found, as `/ready` does).
  **Gap:** `/health` today proves nothing beyond liveness; every capability
  above has to be wired in from `/ready`.

## 4. How FRIDAY's fleet-status answer must change

Today (`FRIDAY/src/friday/ecosystem/fleet_client.py`):

- `_classify_health_response` reads only the top-level `status`/`health`/
  `state` string. After §2.2, that string is finally honest — but the
  classifier must stop there being the *only* input.
- Each `probe_*` returns `AgentStatus(status, details)` where `details` is
  a hardcoded caveat ("Trading mode and order execution were not checked").
  The caveat is static text; it does not reflect the peer's actual state.

Required changes (design; implementation is the separate task):

1. **Classifier reads the contract fields first.** When a peer's `/health`
   carries `capabilities` with the §2.2 vocabulary, FRIDAY maps:
   `status: ok` + all required capabilities `ok` → `ONLINE`;
   `status: degraded` → `DEGRADED` **with the failing capability names and
   their `detail` reason codes in `AgentStatus.details`** (e.g.
   `Stratex DEGRADED: trading_capable unavailable
   (STALE_STRATEGY_EVALUATION)`); no answer / connect failure →
   `UNREACHABLE` (unchanged); HTTP 503 with a contract body → `DEGRADED`,
   not `UNREACHABLE` — a 503 is an answer, and the body says why.
2. **Fallback for pre-contract peers stays reachability-only.** If a peer
   has no `capabilities` block (not yet migrated), the classifier keeps
   today's string matching, but the fleet-status answer must label that
   agent `REACHABLE (capability unknown — pre-contract /health)` and must
   not call it `ONLINE`. `ONLINE` is earned only by a contract body with
   all required capabilities `ok`.
3. **The fleet-status answer cites capability vs reachability explicitly.**
   `FleetStatusTool` (`FRIDAY/src/friday/tools/builtin/fleet_status.py`)
   summary line becomes, e.g.: "Fleet status: 8/9 specialist agents up
   (+ FRIDAY). Stratex is DEGRADED — trading engine unavailable
   (STALE_STRATEGY_EVALUATION); the rest report all required capabilities
   ok. Scope: capability report from each agent's /health, not
   task-level verification." The existing scope sentence is kept and
   extended — "reachability" alone is no longer the scope once peers
   migrate.
4. **Per-agent wording rules for FRIDAY's answer.** Never say an agent is
   "healthy"/"fine"/"working" on the basis of reachability. Allowed:
   "reachable", "answering", "capabilities ok", "degraded: <capability>
   <reason>". A degraded agent is named with its failing capability in the
   summary, not only in the full detail view (today the summary names
   degraded agents, which is kept).
5. **`/api/agents/status` and `get_fleet_status` share the one classifier.**
   They already share `FleetClient`; the contract requires that no second,
   divergent classification be introduced (e.g. in
   `FRIDAY/src/friday/autonomous/controller.py`, which today counts
   `UNREACHABLE` vs "responded" — "responded" must split into ONLINE /
   DEGRADED under the contract, not stay a single bucket).
6. **Probe failures keep today's honesty rules.** Connect-level failure →
   `UNREACHABLE` with reason; read/write/pool timeout → `DEGRADED` ("probe
   timed out"), never proof of a dead peer (existing
   `_probe_failure` semantics, `fleet_client.py:102`).

## 5. Per-agent mapping table: current payload → contract fields

`→` = the current field/probe maps directly. `GAP` = the contract field has
no source today. `FIX` = the current field exists but its semantics must
change as noted.

| Agent | Contract field | Current source | Action |
|---|---|---|---|
| FRIDAY | `capabilities.orchestration` | `overall` from import checks (`friday_deep/health.py`) | Map; label as import/liveness evidence only |
| FRIDAY | `dependencies.database`, `dependencies.disk` | `/ready` DB round-trip + disk check | Wire `/ready` checks into `/health` |
| FRIDAY | `capabilities.peer_mesh` | `peers_mesh` | Map; provenance open question (§6) |
| FRIDAY | top-level `status` / HTTP | `overall`, always HTTP 200 | Derive per §2.2; 503 when degraded |
| Inference | `capabilities.model_routing` | `/ready` key-pools-non-empty (config only) | `unknown` / `CONFIG_ONLY` until live probe (GAP) |
| Inference | `capabilities.specialist_registry` | `/health/ready` count ≥ 10 | Map |
| Inference | `dependencies.database` | `/ready` `SELECT 1` | Map |
| Inference | `providers` list | Static name list | Rename to `configured_providers` (FIX) |
| Inference | top-level `status` / HTTP | Constant `healthy`, always 200 | Derive per §2.2 |
| Memora | `capabilities.memory_store` / `event_store` / `vector_search` | `/health` DB + event-store + vector readiness | Map (already probed) |
| Memora | `dependencies.circuit_breakers` | `/ready` circuit registry | Surface in `/health` |
| Memora | `evidence_class` | `process_liveness` | → `capability_report` (FIX) |
| Memora | top-level HTTP | Already 200/503 | Keep; no change |
| Stratex | `capabilities.trading_engine` | `engine`, `engine_healthy`, heartbeat age, `pid_alive` | Map (reference) |
| Stratex | `capabilities.trading_capable` | `engine_trading_capable`, `capability_reasons`, panic/kill-switch (`/ready`) | Map |
| Stratex | `capabilities.market_data` | `binance_connected`, `websocket_connected` | FIX: default `unknown`, not `True`, when heartbeat omits them |
| Stratex | `dependencies.database` | `/ready` Oracle probe | Wire into `/health` (GAP in `/health`) |
| Stratex | top-level `status` / HTTP | Constant `ok`, always 200 | Derive per §2.2 — **the core fix** |
| Futuris | `capabilities.storage` | `/health` `storage` (`verify_schema()`) | Map |
| Futuris | `capabilities.forecasting` | None | GAP: `unknown` / `NO_MODEL_PROBE` |
| Futuris | `dependencies.database` | `/ready` round-trip + schema | Map |
| Futuris | top-level HTTP | Always 200 even when `degraded` | → 503 when degraded (FIX) |
| IntelX | `capabilities.research` | None | GAP: `unknown` / `NO_LIVE_PROBE` |
| IntelX | `capabilities.model_provider` | `/readyz` config-only check | `unknown` / `CONFIG_ONLY` (FIX from `configured`) |
| IntelX | `dependencies.database` / `storage` | `/readyz` DB health + write test | Map |
| IntelX | `mock_mode` | Top-level flag | Surface inside capabilities: `MOCK_MODE` → `degraded` (FIX) |
| Forge | `capabilities.code_build` | None live | GAP: `unknown` / `NO_LIVE_PROBE` |
| Forge | `capabilities.model_provider` | `routes.py:74` provider check, only at `/api/v1/health` | Canonicalise: one `/health` carries it (FIX, §6) |
| Forge | `dependencies.database` / `workspaces` | `/health` DB ping; `/ready` write test | Map |
| Forge | top-level `status` / HTTP | Constant `ok`, always 200 | Derive per §2.2 |
| Sentinel | `capabilities.security_engine` | Constant `"active"` | FIX: back with `/ready` crypto check or `unknown` |
| Sentinel | `capabilities.audit_chain` | `audit_chain_valid`, `audit_chain_vacuous` | Map |
| Sentinel | `capabilities.audit_durability` | `audit_durable` | Map |
| Sentinel | `dependencies.database` | Derived field only, no query | GAP: real probe required before `ok` |
| Sentinel | `dependencies.event_bus` | `/ready` initialisation check | Map |
| Cortex | `capabilities.crm` / `website` | None | GAP: `unknown` / `NO_LIVE_PROBE` |
| Cortex | `dependencies.database` / `schema` / `redis` | `/ready` checks | Map |
| Cortex | peers | `UNKNOWN: no live readiness probe configured` | Map as optional `unknown` |
| Cortex | top-level `status` / HTTP | Constant `healthy`, always 200 | Derive per §2.2 |
| VyralX | `capabilities.rendering` / `queue_worker` | `/ready` ffmpeg + worker heartbeat | Wire into `/health` (GAP in `/health`) |
| VyralX | `capabilities.content_pack` | None | GAP: `unknown` / `NO_LIVE_PROBE` |
| VyralX | `dependencies.database` / `media_database` | `/ready` checks | Map |
| VyralX | top-level `status` / HTTP | Constant `ok`, always 200 | Derive per §2.2 |

## 6. What this design could not verify from source (open questions for review)

1. **FRIDAY `peers_mesh`.** `FRIDAY/src/friday/api/server.py` includes a
   `peers_mesh` block in `/health`, built by `_peers_mesh_state()` just
   above the handler. Its provenance (live probe vs cached vs config) was
   not fully traced in this survey; the implementation task must read it
   and label the capability accordingly. Do not assume it is a live probe.
2. **Forge's three `/health`s.** `health_router` is mounted first
   (`Forge/app/main.py:414`), so `/health` and `/api/health` serve the
   liveness handler; `routes.py:74` serves only `/api/v1/health`. Route
   resolution order was read from `main.py`, not verified against a live
   process. The implementation task must confirm by live probe which
   handler answers each path before canonicalising.
3. **Stratex master-control `/health`.** Mount path of
   `Stratex/api/master_control_api.py:34` in the live app not verified; it
   may be unmounted or mounted under a prefix. Confirm before citing it.
4. **FRIDAY `/health/deep`.** The constant `{"status": "healthy",
   "engines": 7}` in `FRIDAY/apps/core/src/friday_core/real_deep_api_server.py:375`
   belongs to a separate deep app; whether it is mounted in the live FRIDAY
   process was not verified. If it is reachable, it is a second dishonest
   constant and must be brought under this contract or removed.
5. **Memora `/health` dependency failure mode.** What HTTP code results
   when the `Depends(get_db)` session itself fails was not verified from
   source. Expected honest behaviour is a 5xx, but the implementation task
   must confirm by test.
6. **Futuris `verify_schema()`.** The survey records that `/health` reports
   its verdict; whether `verify_schema()` performs a live round-trip or
   inspects cached metadata was not read. The implementation task must
   confirm it is a live check before `storage` reports `ok` on its basis.
7. **No live verification was done.** Nothing in this document was checked
   against running agents. All statements are about code at base
   `d51b82d`; live behaviour (e.g. whether a given agent's deployed code
   matches this checkout) is unverified and must be probed by the
   implementation task.
8. **Freshness bounds for new capabilities** (Futuris forecasting, IntelX
   research, Forge code-build, Cortex CRM/website, VyralX content-pack) are
   not set here because no probe exists to bound; the implementation task
   proposes them when the probes are designed.

## 7. Out of scope (explicit)

- **Implementation is a separate task.** This document designs the contract
  only: no handler was changed, no probe was added, no fleet-client code
  was touched.
- **This design is reviewed on issue #35 before any implementation task is
  opened.** The implementation task must not be opened, claimed, or started
  until the review on #35 is recorded.
- No trading-behaviour change, no daemon change, no threshold change
  (Stratex 90 s heartbeat / 900 s evaluation bounds are recorded as-is,
  not re-tuned).
- No change to Caddy / Docker health-check routing in this design; the
  implementation task must confirm load-balancer probes point at `/ready`
  before `/health` starts returning 503 (§2.5).
- No new endpoint, no new agent, no dashboard work.

## 8. Acceptance criteria for the implementation task (for the reviewer)

1. Every agent's `/health` returns the §2.2 fields; `status` is derived,
   never constant; HTTP is 503 whenever `status` is `degraded`.
2. Stratex with engine offline (the TASK-REL-003 condition) returns
   `status: degraded`, HTTP 503, with `capabilities.trading_engine` /
   `trading_capable` `unavailable` and the `STALE_STRATEGY_EVALUATION`
   reason — verified by live probe, not by reading code.
3. FRIDAY's fleet-status answer names a degraded Stratex with its failing
   capability and reason, and labels pre-contract peers as capability
   unknown rather than ONLINE — verified by live probe.
4. No `unknown` required capability is silently dropped or reported `ok`;
   every GAP in §5 is either closed by a probe or reported `unknown` with
   its reason code.
5. No secret, credential, key, token, DSN, or raw exception text containing
   one appears in any health payload.
6. All ten agents' `/ready` behaviour is unchanged (still 200/503 as
   today), and Caddy/Docker probes still point at `/ready`.

---

*— Muse 9, TASK-REL-004 design. Surveyed from source at base `d51b82d`
(2026-11-22). Design only; no implementation.*
