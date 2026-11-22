# TASK-VAL-005 — Fleet capability-state re-probe — 2026-11-22

Task: Fleet — re-probe all 10 agents' capability state live (not just
liveness) and file per-agent evidence. Worker: Muse 13. Claim: issue #35
comment 7082034818; work PR #1393 (branch
`muse13/task-val-005-fleet-reprobe`).

Assignment: coordinator watch 7081930646 (~21:44 IST, P2, pool 9), from
MASTER_PLAN M4 (TASK-VAL-001, STALE-UNVERIFIED since 2026-11-14). The
re-probe runs against the live REL-004 capability contract
(`docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`, design only, merged
via PR #1311; implementation is the separate task REL-006).

## Method (read-only throughout; no credentials used, no state changed)

1. **Public-gateway probe** from this VM, 2026-11-22 16:28:19–16:29:17Z
   (21:58–21:59 IST): full `/health` bodies + `/ready` for all 10 agents via
   `https://friday-universe.duckdns.org`, plus FRIDAY `/api/agents/status`
   and bridge MCP `initialize`. Probe script `/tmp/probe_val005.py` (run
   locally; raw JSON `/tmp/val005_probe.json`, not committed).
2. **Fleet Live Validation workflow** dispatched 2026-11-22 ~16:27Z, run
   https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45043982145
   (head main `4a16d09f`, completed `success`, all 3 jobs green):
   public-gateway job 137274406785, Server 1 job 137274406500, Server 2 job
   137274406789. Job logs downloaded from the run and quoted verbatim below.
3. **Server-side arbitration** via the engineering bridge
   (`https://friday-universe.duckdns.org/bridge/mcp`, FRIDAY-Cloud-
   Engineering-Bridge v1.30.0): `oracle_fleet_health`,
   `oracle_check_service`, read-only `run_shell` (listeners/processes on
   Server 2; SSH hop to Server 1 `10.0.0.121` for the same, plus the
   deployed `/etc/caddy/Caddyfile`). No restarts, no writes, no deploys.

## Headline verdict (revised by the evidence — read this first)

**No agent is down.** All 10 agents answer live at their deployed
upstreams. The first reading of the workflow run — "5 agents down" — is
wrong, and so is FRIDAY's own fleet-status answer ("degraded, 5
UNREACHABLE"). Both read **stale maps** that predate the fleet's current
placement. The gateway is not lying; the records are stale.

- **F1 — the deployed fleet layout no longer matches any static record.**
  The repo `deploy/Caddyfile`, the validation workflow's server lists, and
  FRIDAY's mesh probe map all predate the current placement. Deployed
  `/etc/caddy/Caddyfile` on Server 1 (read verbatim via the bridge, §5)
  routes: Futuris/IntelX to Server 2 (`10.0.0.120:8004/8005`), Sentinel to
  Server 1 loopback (`127.0.0.1:8008`), Stratex to a loopback SSH tunnel
  (`127.0.0.1:18003` → AWS U1), VyralX to AWS (`16.176.9.247:8010`),
  plus `/bridge`, `/mcp`, `/messages` → Server 2 `:8011` (absent from the
  repo file entirely). Consequences: FRIDAY's fleet-status tells the owner
  the fleet is degraded when it is not; the workflow's server-side jobs
  report healthy agents as down; the repo Caddyfile cannot be trusted as
  the routing source of truth.
- **F2 — the D-023 auth gate is not holding (security).** Unauthenticated
  `POST /friday/api/chat` (`{"message": "hello FRIDAY"}`, no key, no
  cookie) returned **HTTP 200 with a live conversational reply**
  ("Burning the midnight oil again, Surendra? Where do we start?",
  `fast_path: true`, 3.6 s). The validator's `friend_persona_greeting`
  probe FAILs on this run (workflow job 137274406785). One probe only —
  the same probe the fleet validator itself performs; not re-probed.
  VAL-004 recorded the same probe FAIL with a different failure mode
  (HTTP None), so the gate has not held in either run.
- **F3 — REL-004 is still design-only everywhere.** No agent's `/health`
  carries `capabilities` / `dependencies`; all ten report
  `evidence_class: process_liveness`. Per contract §4 rule 2, no agent
  may be called ONLINE — the four FRIDAY calls ONLINE (Inference, Memora,
  Cortex, Forge) are reachability-only verdicts and must be relabelled
  REACHABLE (capability unknown). Cortex and VyralX `/health` are pure
  constants that prove nothing while presenting `status: ok/healthy` +
  HTTP 200 — the contract's canonical "ok while capability unknown" case.

## 1. Public-gateway probe (this VM, 16:28:19–16:29:17Z)

| Agent | /health | /ready | Top-level status | `evidence_class` |
|---|---|---|---|---|
| FRIDAY | 200 (1.314 s) | 200 (5.008 s) | `healthy` | `process_liveness` |
| Inference | 200 (1.300 s) | 200 (9.104 s) | `healthy` | `process_liveness` |
| Memora | 200 (0.984 s) | 200 (4.290 s) | `healthy` | `process_liveness` |
| Stratex | 200 (3.107 s) | 200 (6.483 s) | `ok` | `process_liveness` |
| Futuris | 200 (1.042 s) | 200 (1.102 s) | `ok` | `process_liveness` |
| IntelX | 200 (0.991 s) | 200 (2.702 s) (`/readyz`) | `ok` | `process_liveness` |
| Forge | 200 (0.982 s) | 200 (1.910 s) | `ok` | `process_liveness` |
| Sentinel | 200 (1.196 s) | 200 (1.787 s) | `ok` | `process_liveness` |
| Cortex | 200 (1.090 s) | 200 (1.791 s) | `healthy` | `process_liveness` |
| VyralX | 200 (1.594 s) | 200 (5.440 s) | `ok` | `process_liveness` |

Full bodies (verbatim, truncated only where noted):

- **FRIDAY** `{"overall": "healthy", "evidence_class": "process_liveness",
  "observed_at": "2026-11-22T16:28:21.717665+00:00", "checks":
  [{"name": "python", "state": "healthy", "details": "3.10.12"},
  {"name": "platform", ...}, {"name": "friday", "details": "imported"},
  {"name": "friday_deep", "details": "imported"}], "status": "healthy",
  "service": "friday_core", "agent": "FRIDAY", "version": "2.0.0",
  "peers_mesh": "configured_unverified"}` — proves imports only;
  `peers_mesh` provenance still unverified (contract §6 Q1). `/ready` 200:
  `database: connected` (Oracle), `disk_free_mb: 71766.7`, `mesh:
  "configured"`.
- **Inference** `{"status": "healthy", "service": "inference",
  "evidence_class": "process_liveness", "providers": ["groq",
  "cerebras", "openrouter", "gemini", "nvidia"],
  "active_specialist_agents": 19, "version": "2.0.0"}` — `providers` is
  the static name list (contract: must be `configured_providers`;
  `model_routing` is `unknown` / `CONFIG_ONLY` until a live provider
  probe exists). `/ready` 200: database connected, `model_routing:
  ready`, key pools present (config only).
- **Memora** `{"status": "healthy", "service": "memora",
  "evidence_class": "process_liveness", "storage": "oracle",
  "database": "healthy", "database_backend": "oracle",
  "database_durable": true, "event_store": "oracle_database",
  "event_store_durable": true, "vector_store": {"status": "available",
  "available": true, "backend": "oracle_23ai_native_vector",
  "dimension": 384, "table": "memora_vector_store"}, "version":
  "2.0.0"}` — the most honest `/health` in the fleet (DB + event store
  + vector readiness all live); only the `evidence_class` label lies.
  `/ready` 200: `circuits: healthy`.
- **Stratex** `{"capability_reasons": [], "capability_warnings":
  ["DEMO_ENVIRONMENT: execution venues are Binance Futures testnet and
  OANDA practice"], "daemon_balance": 10564.79205357, "dashboard":
  "online", "engine": "online", "engine_healthy": true,
  "engine_source": "multi_venue_daemon", "engine_trading_capable":
  true, "environment": "multi_venue_testnet_practice",
  "evidence_class": "process_liveness", "mode": "FUTURES",
  "observed_at": "2026-11-22T16:28:45.071170Z", "open_positions": 29,
  "service": "stratex", "status": "ok", "unrealized_pnl": 60.72,
  "version": "2.2.0"}` — engine fields assert ok, but the live body
  omits the freshness evidence the contract's §5 reference mapping
  requires (no heartbeat age, no last-evaluation timestamp, no
  `pid_alive` / `binance_connected` / `websocket_connected` in the
  payload). Trading capability cannot be verified as fresh from this
  body alone. Values are live: `daemon_balance` moved 10564.79 →
  10565.05 → 10562.35 across the three probes minutes apart.
- **Futuris** `{"status": "ok", "service": "futuris",
  "evidence_class": "process_liveness", "version": "2.0.0",
  "storage": {"ready": true, "expected": 13, "present": 13,
  "missing": [], "error": null}}` — storage ready; forecasting
  capability has no probe anywhere (`unknown` / `NO_MODEL_PROBE`).
  `/ready` 200: database connected.
- **IntelX** `{"status": "ok", "evidence_class": "process_liveness",
  "service": "intelx", "version": "2.0.0", "mock_mode": false,
  "database": "not_checked", "timestamp": ...}` — `database:
  "not_checked"` is honest; research capability has no live probe
  (`unknown` / `NO_LIVE_PROBE`). `/readyz` 200: database connected,
  storage ok, `model_provider: "configured"`,
  `model_provider_check: "configuration_only"` — exactly the
  contract's CONFIG_ONLY case.
- **Forge** `{"status": "ok", "service": "forge", "version": "2.0.0",
  "uptime_seconds": 2849.4, "database_connected": true,
  "evidence_class": "process_liveness", "observed_at": ...}` —
  `code_build` / `model_provider` unprobed by `/health` (the provider
  check exists only at `/api/v1/health`, contract §6 Q2). `/ready` 200:
  database connected, `workspaces_writable: true`.
- **Sentinel** `{"status": "ok", "service": "sentinel",
  "evidence_class": "process_liveness", "observed_at": ...,
  "security_engine": "active", "version": "1.0.0", "environment":
  "production", "kill_switch_active": false, "audit_chain_valid":
  true, "audit_chain_entries": 11, "audit_chain_vacuous": false,
  "audit_durable": true, "audit_persistence_evidence":
  "durable_store_configured"}` — audit evidence is live and
  non-vacuous; `security_engine: "active"` is a constant string
  (contract: back with the `/ready` crypto check or `unknown`); the
  `database` field is derived, not probed. `/ready` 200: crypto keys,
  audit integrity, event bus, durability all true.
- **Cortex** `{"status": "healthy", "service": "cortex", "version":
  "2.1.0", "evidence_class": "process_liveness", "observed_at": ...}`
  — a constant; no checks of any kind. `/ready` 200 is honest where
  `/health` is not: `database`/`schema`/`redis` UP, `degraded:
  ["ai_universe", "sentinel", "intelx", "futuris"]` — the peer entries
  are `UNKNOWN: no live readiness probe configured` (contract: optional,
  never fatal). Note the peer list names sentinel/intelx/futuris
  degraded: all three are alive at their new homes (§5), so Cortex's
  peer knowledge is itself stale.
- **VyralX** `{"status": "ok", "service": "vyralx", "version": "0.2.0",
  "evidence_class": "process_liveness", "observed_at": ...}` — a
  constant; no checks of any kind. `/ready` 200: database connected,
  media database connected. (The `/ready` body carries a DSN with the
  password masked as `***` — no secret exposed.)

**FRIDAY `/api/agents/status`** (16:29:17Z): `status: degraded`,
`scope: peer_endpoint_reachability_only`, counts ONLINE 4 / UNREACHABLE
5 / REACHABLE 0 / DEGRADED 0. ONLINE: Inference (1989 ms), Memora
(908 ms), Cortex (813 ms, `10.0.0.120:8009`), Forge (895 ms) — each
with the caveat "…was not checked". UNREACHABLE: Stratex
(`127.0.0.1:8003` ConnectError), IntelX (`127.0.0.1:8005`),
Futuris (`127.0.0.1:8004`), Sentinel (`10.0.0.120:8008`), VyralX
(`10.0.0.120:8010`) — all ConnectError, ~400 ms each. Every one of
these five probe targets is a stale address (§5); the agents are alive
at their deployed upstreams. FRIDAY's fleet-status verdict is wrong
because its probe map is wrong, and its scope line says so itself.

**Bridge MCP `initialize`**: HTTP 200, server
FRIDAY-Cloud-Engineering-Bridge v1.30.0 (protocol 2025-03-26) — with
the correct `Accept: application/json, text/event-stream` header. A
first attempt with `Accept: application/json` only returned HTTP 406
("Client must accept both application/json and text/event-stream") —
my probe's error, corrected on re-probe; the workflow job's own bridge
probe also returned 200. (VAL-004 recorded bridge initialize FAIL with
HTTP None — a different, older failure mode; the bridge is up now.)

## 2. Workflow run 45043982145 (dispatched by this task, ~16:27Z)

- Public-gateway job 137274406785: `SUMMARY: 10/10 agents healthy;
  bridge OK; all functional probes SEE REPORT` — functional probes:
  `fleet_status` PASS, `control_session_requires_key` PASS (HTTP 401),
  `health_detail` (Memora) PASS, **`friend_persona_greeting` FAIL
  (HTTP 200)** — see F2.
- Server 1 job 137274406500 (stamp 2026-11-22T16:28:05Z):
  FRIDAY active, Inference active, Memora active, **Stratex inactive**,
  **Futuris inactive**, **IntelX failed** (since Fri 2026-11-20
  23:48:27 IST), Forge active, Stratex-Daemon inactive; local /health
  200 for FRIDAY/Inference/Memora/Forge, **000** for
  Stratex/Futuris/IntelX. No NRestarts > 5 anywhere.
- Server 2 job 137274406789 (stamp 2026-11-22T16:28:05Z): **VyralX
  inactive**, **Sentinel inactive**, Cortex active (since Sun
  2026-11-22 12:16:38 IST), VyralX-Daemon inactive; local /health 200
  for Cortex, **000** for Sentinel/VyralX.
- Recent restarts (manual, NRestarts 0 — no crash loops): FRIDAY
  21:08:43 IST, Inference 21:08:54 IST, Forge 21:09:45 IST, Memora
  21:25:29 IST, Cortex 12:16:38 IST.
- **These server-side rows are stale-map artefacts, not outages**
  (§5): the workflow checks Futuris/IntelX units on Server 1 where
  they no longer run, Sentinel/VyralX units on Server 2 where they no
  longer run, and a masked Stratex unit on Server 1. The workflow's
  server lists need updating to the deployed layout.

## 3. Per-agent capability verdicts (REL-004 contract applied)

Contract status: design-only, unimplemented (REL-006). No agent has a
`capabilities` block, so per §4 rule 2 no agent is ONLINE; all are
REACHABLE (capability unknown) except where the body's own fields give
live capability evidence (noted per agent).

| Agent | Presented (gateway) | Live capability evidence | Verdict |
|---|---|---|---|
| FRIDAY | `healthy` / 200 | Imports only; `peers_mesh: configured_unverified`; /ready DB connected, disk 71 GB free | REACHABLE; orchestration evidence = imports only; memory_backend + peer_mesh unprobed by /health |
| Inference | `healthy` / 200 | Static `providers` list; 19 specialists; /ready DB + key pools (config only) | REACHABLE; `model_routing` unknown / CONFIG_ONLY |
| Memora | `healthy` / 200 | DB healthy, event store Oracle, vector available (live) | REACHABLE; capability evidence present in body, but no contract block — not ONLINE |
| Stratex | `ok` / 200 | Engine online, trading_capable true, 29 open positions, live balances (AWS U1 via tunnel); freshness fields absent from body | REACHABLE; trading capability asserted but not freshness-proven; served via SSH tunnel, unit masked |
| Futuris | `ok` / 200 | Storage 13/13; /ready DB connected | REACHABLE; `forecasting` unknown / NO_MODEL_PROBE |
| IntelX | `ok` / 200 | DB `not_checked` (honest); mock_mode false; /readyz provider config-only | REACHABLE; `research` unknown / NO_LIVE_PROBE |
| Forge | `ok` / 200 | DB connected; /ready workspaces writable | REACHABLE; `code_build` / `model_provider` unknown / NO_LIVE_PROBE |
| Sentinel | `ok` / 200 | Audit chain valid, 11 entries, non-vacuous, durable (live) | REACHABLE; audit evidence present in body; `security_engine` constant → unknown; DB derived, not probed |
| Cortex | `healthy` / 200 | /health is a constant (no checks); /ready DB/schema/Redis UP | REACHABLE; **capability unknown — /health proves nothing while presenting healthy** |
| VyralX | `ok` / 200 | /health is a constant (no checks); /ready DB + media DB connected | REACHABLE; **capability unknown — /health proves nothing while presenting ok** |

**Agents presenting as ok while degraded (acceptance criterion):** none
is down, so there is no "ok while down" case. The exact degraded
capabilities, in contract terms, are the `unknown` required
capabilities above: Cortex `crm`/`website`, VyralX `rendering` /
`queue_worker` / `content_pack` (wired from `/ready` nowhere in
`/health`), Futuris `forecasting`, IntelX `research` /
`model_provider`, Forge `code_build` / `model_provider`, Inference
`model_routing`, FRIDAY `memory_backend` / `peer_mesh`, Stratex
`market_data` (defaults) + freshness-unproven `trading_capable`,
Sentinel `security_engine` / `database`. All are GAPs the REL-006
implementation task must close or report `unknown` with reason codes —
none is a live outage today.

## 4. Bridge arbitration (server-side truth, ~17:04–17:07Z)

- `oracle_fleet_health`: Server 1 `10.0.0.121` (host to 7 agents),
  Server 2 `10.0.0.120` (Sentinel/Cortex/VyralX/Bridge — itself a
  stale label). Both up (39 / 31 days).
- Server 2 listeners/processes: `:8004` Futuris (uvicorn pid 577689,
  since Nov 21), `:8005` IntelX (pid 563553, since Nov 20), `:8009`
  Cortex (pid 584499, since 12:16 IST), `:8011` bridge, `:6379`
  Redis. **No `:8008`, no `:8010`, no Sentinel/VyralX processes.**
- Server 1 listeners/processes (via SSH hop): Caddy (pid 1754623,
  since Oct 23, `/etc/caddy/Caddyfile`), `:10000` FRIDAY (uvicorn,
  21:08 IST), `:8001` Inference (21:08), `:8002` Memora (21:25),
  `:8006` Forge (21:09), **`:8008` Sentinel (uvicorn pid 2365819,
  21:09 IST)**. **No `:8003`, `:8004`, `:8005`, `:8010`; no Stratex /
  Futuris / IntelX / VyralX processes.**
- `oracle_check_service Stratex`: **Stratex.service is MASKED on
  Server 1, Active: inactive (dead).** Journal tail: stopped
  17:52:26 IST ("Stopping FRIDAY Universe - 24/7 Autonomous
  Algorithmic Trading… Stopped"), last engine lines 17:52:14 IST
  (ML ensemble signals, cTrader bracket widening, supervision cycle).
- `127.0.0.1:18003` on Server 1 is an **SSH tunnel**
  (`ssh -N -i /home/ubuntu/.ssh/u1_tunnel_ed25519 …`, started
  17:55 IST — minutes after the Stratex unit stopped). Direct probe
  through the tunnel: Stratex `/health` live (`engine: online`,
  `engine_trading_capable: true`, `daemon_balance: 10562.35`,
  `unrealized_pnl: 62.95`, 29 open positions, observed 17:07:30Z).
  The live Stratex is the AWS U1 instance, reached via this tunnel.
- VyralX on AWS: direct curl from Server 1 to
  `http://16.176.9.247:8010/health` → 200, `{"status": "ok",
  "service": "vyralx", "version": "0.2.0", "evidence_class":
  "process_liveness"}`; `/ready` → 200. (Direct curl from this VM
  failed — empty reply / 000 — the AWS endpoint is not reachable from
  this network; reachable from Server 1.)

## 5. The deployed routing (the stale-map root cause)

Deployed `/etc/caddy/Caddyfile` on Server 1 (read verbatim via the
bridge) vs the repo's `deploy/Caddyfile`:

| Route | Repo `deploy/Caddyfile` | Deployed on Server 1 |
|---|---|---|
| /friday | 127.0.0.1:10000 | 127.0.0.1:10000 |
| /inference | 127.0.0.1:8001 | 127.0.0.1:8001 |
| /memora | 127.0.0.1:8002 | 127.0.0.1:8002 |
| /stratex | 127.0.0.1:8003 | **127.0.0.1:18003 (SSH tunnel → AWS U1)** |
| /futuris | 127.0.0.1:8004 | **10.0.0.120:8004 (Server 2)** |
| /intelx | 127.0.0.1:8005 | **10.0.0.120:8005 (Server 2)** |
| /forge | 127.0.0.1:8006 | 127.0.0.1:8006 |
| /vyralx | 10.0.0.120:8010 | **16.176.9.247:8010 (AWS)** |
| /sentinel | 10.0.0.120:8008 | **127.0.0.1:8008 (Server 1)** |
| /cortex | 10.0.0.120:8009 | 10.0.0.120:8009 |
| /bridge, /mcp, /messages | — (absent) | 10.0.0.120:8011 (Server 2) |

Actual placement now: Server 1 — FRIDAY, Inference, Memora, Forge,
Sentinel (+ Caddy, + Stratex tunnel); Server 2 — Futuris, IntelX,
Cortex, Bridge, Redis; AWS U1 — Stratex (via tunnel); AWS —
VyralX (16.176.9.247). The repo Caddyfile, the workflow server lists,
FRIDAY's probe map, and the bridge's own "Server 2 hosts
Sentinel/Cortex/VyralX" label all predate this placement.

## 6. Open questions / follow-ups for Muse

1. **Stale maps (F1):** update the repo `deploy/Caddyfile` to the
   deployed file (or record the deployed file as the source of truth);
   update `.github/workflows/fleet-live-validation.yml` server lists to
   the deployed layout (Futuris/IntelX on S2, Sentinel on S1, Stratex
   via the 18003 tunnel, VyralX on AWS); update FRIDAY's mesh probe
   map (`fleet_client.py` targets) to the same — otherwise the next
   validation and the next fleet-status answer repeat the false
   "5 agents down".
2. **Auth gate (F2):** the D-023 gate on `POST /friday/api/chat`
   (unauthenticated remote chat) is not holding — HTTP 200 + live
   reply. Needs a fix task; re-probe after the fix with the same
   validator probe.
3. **REL-006 implementation** remains the path to real capability
   reporting; this re-probe is the baseline it will be measured
   against (notably: Stratex freshness fields, Cortex/VyralX
   constants, Inference static provider list, IntelX CONFIG_ONLY).
4. **Stratex on AWS U1 via SSH tunnel** is undocumented in the repo:
   the masked unit + tunnel + `u1_tunnel_ed25519` key should be
   recorded (owner + runbook), including what restarts the tunnel if
   it drops.
5. **Cortex peer list** still names sentinel/intelx/futuris degraded
   — its peer knowledge has no live probe; harmless under the contract
   (optional) but worth a note when the probe map is fixed.
6. Bridge-tool quirk (not a finding): `oracle_curl_health` with
   `{"agent": "Stratex"}` returned FRIDAY's `/health` — the tool seems
   to ignore/misroute the agent argument; `oracle_check_service`
   requires the `agent` field, not `service`.

## Evidence index

- Gateway probe raw JSON: local `/tmp/val005_probe.json` (probe
  2026-11-22 16:28:19–16:29:17Z; 10 × /health + 10 × /ready +
  `/friday/api/agents/status` + bridge initialize).
- Workflow run 45043982145 (all 3 jobs `success`): public-gateway job
  137274406785, Server 1 job 137274406500, Server 2 job 137274406789.
  Job logs quoted in §§1–2.
- Bridge session: FRIDAY-Cloud-Engineering-Bridge v1.30.0, tools
  `oracle_fleet_health`, `oracle_check_service`,
  `oracle_curl_health`, `run_shell` (read-only commands only).
- Deployed Caddyfile: `/etc/caddy/Caddyfile` on Server 1, read via the
  bridge (§5). Repo copy: `deploy/Caddyfile` (stale, 5 routes differ).
- Contract: `docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`.

— Muse 13, TASK-VAL-005, 2026-11-22 ~22:45 IST
