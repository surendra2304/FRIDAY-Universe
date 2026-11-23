# TASK-VAL-012 — Fleet post-fix capability re-probe — 2026-11-23

Task: Fleet — after VAL-006's map fixes landed (PR #1404 merged `3f9cec0c`),
re-run the full 10-agent capability probe and prove zero false-down AND zero
false-up. Worker: Muse 14. Claim: issue #35 comment 7085474289; work PR
(to be opened on branch `muse14/task-val-012`).

Assignment: coordinator queue 7084110569 + watch 7084948379 (~01:42 IST,
"VAL-006 merged → claim TASK-VAL-012 next") + watch 7085314708 (~02:00 IST,
VAL-012 as queue head). Queue after VAL-012: SEN-023 → REL-079*. Note:
while VAL-012 was on hold, the coordinator also assigned SEN-022 and WF-002
to Muse 14 (board commit 551eaa05); those are queued behind VAL-012.

Hold note: a system safety flag on the `git fetch` result paused this task
02:13–11:28 IST (no checkout, no claim PR, no validation dispatch, no
bridge calls). Surendra lifted the hold in plain words 11:28 IST
2026-11-23 ("Yes, go ahead and resume VAL-012"); resume posted on issue
#35 (comment 7092910078). The fetch that was flagged had brought in three
ordinary commits (Muse 13's TASK-CTX-003 merge, PR #1416); nothing in it
was an instruction.

## Method (read-only throughout; no credentials used, no state changed)

1. **Public-gateway probe** from this VM, 2026-11-23 06:01:00–06:01:20Z
   (11:31 IST): `scripts/validate_fleet_live.py` (canonical validator)
   plus a `/ready` sweep for all 10 agents (companion script
   `val012_ready.py`, IntelX falls back to `/readyz`). Raw JSON kept out
   of the repo (workspace `friday-bridge/val012/`).
2. **First probe** 2026-11-23 ~02:13 IST (before the hold): all 10 agents
   `/health` 200 + `/ready` 200 via the gateway; fleet-status degraded, 7
   ONLINE / 2 UNREACHABLE (Stratex `127.0.0.1:8003`, VyralX
   `10.0.0.120:8010`). Raw JSON lost when /tmp was cleared; results
   preserved in the daily log (`~/memory/2026-11-23.md`). The fresh
   11:31 IST probe below supersedes it — and differs from it (see §1).
3. **Fleet Live Validation workflow** dispatched 2026-11-23 06:03:13Z from
   branch `muse14/task-val-012`, run
   https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45121575640
   (head `a8c6fea2`): public-gateway job 137516321206, Server 1 job
   137516321531, Server 2 job 137516321480. Job logs quoted in §2.
4. **Server-side arbitration** via the engineering bridge
   (`https://friday-universe.duckdns.org/bridge/mcp`, FRIDAY-Cloud-
   Engineering-Bridge v1.30.0): `get_system_info`,
   `oracle_fleet_health`, `oracle_check_service`, read-only `run_shell`
   (listeners, unit states, deployed FRIDAY `.env` URL values only,
   deployed code heads). No restarts, no writes, no deploys.

## Headline verdict

**Zero false-down and zero false-up — with one honest exception that
fails the validator's crude criterion.** All 10 agents are live at their
deployed upstreams. FRIDAY's fleet-status answer now shows **UNREACHABLE
0** (VAL-006's 2 false-down are gone). The two agents that answer
`/health` 503 — Futuris and IntelX — are **not down**: they are live,
`/ready` 200, databases connected, units active, and the 503 is the new
capability contract reporting their core capabilities as unknown
(NO_LIVE_PROBE / CONFIG_ONLY / NO_MODEL_PROBE). The Fleet Live
Validation run concluded `failure` solely because the validator equates
"healthy" with HTTP 200 — its public-gateway job exits 1 on 8/10 while
every server-side job is green and no agent is down.

- **F1 — Futuris + IntelX `/health` 503 "degraded" is the capability
  contract working, not an outage.** Both serve `evidence_class:
  capability_report` now (REL-006 landing): Futuris `forecasting`
  unknown (NO_MODEL_PROBE), IntelX `research` unknown (NO_LIVE_PROBE)
  and `model_provider` unknown (CONFIG_ONLY). Their databases and
  storage are live-checked ok; `/ready` is 200; units are active
  (Futuris NRestarts=1 since 09:53:36 IST, IntelX NRestarts=0 since
  09:04:39 IST). FRIDAY's fleet-status marks them DEGRADED, not
  UNREACHABLE — the honest label. But the validator's `healthy =
  HTTP 200` rule fails the public-gateway job on exactly these two.
  Follow-up for Muse: either the validator learns the contract's
  degraded-vs-down distinction, or Futuris/IntelX get live capability
  probes (the REL-006 follow-ups VAL-005 named).
- **F2 — the VAL-006 `.env` deploy happened; the 2 false-down are
  gone.** Deployed FRIDAY `.env` mtime 2026-11-23 09:40:57 IST:
  `STRATEX_URL` = `127.0.0.1:18003` and `VYRALX_URL` =
  `http://16.176.9.247:8010` (both fixed); FRIDAY restarted 10:38:50
  IST and loaded them. Fleet-status now probes Stratex at `18003` and
  VyralX at the AWS address; UNREACHABLE 0. `SENTINEL_URL` is still
  `10.0.0.121:8008` — it works (S1 listens on 0.0.0.0) but is not the
  deployed form (`127.0.0.1:8008`); cosmetic, one value, worth fixing
  with the next `.env` touch.
- **F3 — REL-006 is landing live.** Memora now serves a
  `capability_report` (`memory_store` ok, live) and FRIDAY's
  fleet-status scope is now `health_capability_report` with the
  ONLINE / REACHABLE / DEGRADED taxonomy (Memora ONLINE, 6 REACHABLE
  honestly labelled capability-unknown, 2 DEGRADED). VAL-005's F3
  (design-only contract) is becoming real, agent by agent.
- **F4 — the D-023 auth gate now holds.** Unauthenticated `POST
  /friday/api/chat` returns HTTP 401 (VAL-005 F2 was HTTP 200 + live
  reply). Fixed elsewhere (see TASK-VAL-007-AUTH-GATE-FIX); verified
  here, not claimed as VAL-012 work.
- **F5 — validator TLS evidence is unavailable (script defect).**
  `scripts/validate_fleet_live.py::probe_tls` raises `NameError:
  name 'socket' is not defined` (missing import); the probe degrades
  gracefully but no TLS evidence is produced. One-line fix, out of
  this task's scope; noted for Muse.
- **F6 — deployed code lags main.** S1 head `705ab92d`, S2 head
  `ff84c7ff` (both from this morning's restart/deploy window); repo
  main is `136533e5`. Normal — deploys are separate — but the
  capability-contract behaviour above is the deployed code's, not
  main's.

## 1. Public-gateway probe (this VM, 06:01:00–06:01:20Z)

| Agent | /health | /ready | Top-level status | `evidence_class` |
|---|---|---|---|---|
| FRIDAY | 200 (1.893 s) | 200 (1.009 s) | `ok` | (pre-contract) |
| Inference | 200 (0.852 s) | 200 (1.164 s) | `healthy` | `process_liveness` |
| Memora | 200 (0.929 s) | 200 (1.616 s) | `ok` | `capability_report` |
| Stratex | 200 (1.492 s) | 200 (5.951 s) | `ok` | `process_liveness` |
| Futuris | **503 (0.976 s)** | 200 (0.973 s) | `degraded` | `capability_report` |
| IntelX | **503 (0.982 s)** | 200 (1.095 s, `/readyz`) | `degraded` | `capability_report` |
| Forge | 200 (0.977 s) | 200 (1.214 s) | `ok` | `process_liveness` |
| Sentinel | 200 (1.041 s) | 200 (1.335 s) | `ok` | `process_liveness` |
| Cortex | 200 (1.237 s) | 200 (1.424 s) | `healthy` | `process_liveness` |
| VyralX | 200 (1.430 s) | 200 (5.829 s) | `ok` | `process_liveness` |

Functional probes (all PASS): FRIDAY `fleet_status` (HTTP 200, agents
dict present), `friend_persona_greeting` (HTTP 401 — D-023 gate live),
`control_session_requires_key` (HTTP 401 — TASK-SEC-005 live); Memora
`health_detail` (HTTP 200, `capability_report`). Bridge MCP
`initialize`: HTTP 200, FRIDAY-Cloud-Engineering-Bridge v1.30.0.
Summary: **8/10 agents healthy; bridge OK; all functional probes
PASS. /ready sweep: 10/10 ready.**

Full bodies (the two that matter — verbatim, truncated only where
noted):

- **Futuris** `{"status": "degraded", "service": "futuris", "agent":
  "futuris", "evidence_class": "capability_report", "version":
  "2.0.0", "capabilities": {"storage": {"state": "ok", "evidence":
  "live schema inspection: 13/13 required tables present"},
  "forecasting": {"state": "unknown", "evidence": "no
  forecasting-model probe exists; storage readiness is not
  forecasting ability", "detail": "NO_MODEL_PROBE"}}, "dependencies":
  {"database": {"state": "ok", "evidence": "live round-trip (schema
  inspection over a fresh connection) + all required tables
  present"}}}` — up, DB live, storage live; only `forecasting` is
  unknown, and the body says so honestly.
- **IntelX** `{"status": "degraded", "evidence_class":
  "capability_report", "service": "intelx", "version": "2.0.0",
  "mock_mode": false, "database": "connected", "capabilities":
  {"research": {"state": "unknown", "detail": "NO_LIVE_PROBE",
  "evidence": "no live research probe exists; research ability is not
  verified by this endpoint"}, "model_provider": {"state": "unknown",
  "detail": "CONFIG_ONLY", "evidence": "provider config present; no
  live probe"}}, "dependencies": {"database": {"state": "ok",
  "evidence": "live check_database_health() round-trip (SELECT 1 /
  SELECT 1 FROM DUAL)"}, "storage": {"state": "ok", "evidence":
  "writable data-dir probe (tempfile write, as /readyz)"}}}` — up,
  DB live, storage live; only the two capabilities are unknown.
- **Memora** `health_detail`: `{"status": "ok", "service": "memora",
  "evidence_class": "capability_report", "capabilities":
  {"memory_store": ...}}` — the first agent besides Futuris/IntelX
  serving a capability report; FRIDAY's fleet-status calls it ONLINE
  ("capabilities ok").

The 503s are stable, not flapping: identical at 06:01:00Z (validator),
06:02:13Z (direct curl), and 06:03:36Z (workflow run), and the units
have been up since 09:53:36 IST (Futuris) and 09:04:39 IST (IntelX).
At 02:13 IST both answered `/health` 200 — the change landed with
this morning's restart/deploy window (09:04–10:39 IST), i.e. the
capability contract went live on these two agents between the two
probes.

**FRIDAY `/api/agents/status`** (06:01:57Z): `status: degraded`,
`scope: health_capability_report`, `agent_count: 9`, counts ONLINE 1 /
REACHABLE 6 / DEGRADED 2 / UNREACHABLE 0 / OFFLINE 0. ONLINE: Memora
("capabilities ok"). REACHABLE: Inference (`127.0.0.1:8001`),
Stratex (`127.0.0.1:18003` — the fixed tunnel address), Cortex
(`10.0.0.120:8009`), Forge (`127.0.0.1:8006`), Sentinel
(`10.0.0.121:8008` — the `.121` form, works), VyralX
(`16.176.9.247:8010` — the fixed AWS address). DEGRADED: IntelX
(`10.0.0.120:8005`, "research unknown (NO_LIVE_PROBE);
model_provider unknown (CONFIG_ONLY)"), Futuris (`10.0.0.120:8004`,
"forecasting unknown (NO_MODEL_PROBE)"). Every endpoint probed is
the deployed address; **UNREACHABLE 0** — VAL-006's 2 false-down are
gone, and no new false-down replaced them.

## 2. Workflow run 45121575640 (dispatched by this task, 06:03:13Z)

Run concluded `failure` — entirely because of the two 503s:

- Public-gateway job 137516321206: `failure` (exit 1). Validator
  output identical to §1: `SUMMARY: 8/10 agents healthy; bridge OK;
  all functional probes PASS` — Futuris FAIL(503), IntelX FAIL(503),
  the other eight OK, bridge 200. The job fails because the script
  exits 1 unless all ten are HTTP 200.
- Server 1 job 137516321531: `success` (stamp 06:03:26Z). FRIDAY /
  Inference / Memora / Forge / Sentinel active, NRestarts 0, all
  since 10:38:50–10:39:26 IST; Stratex-Daemon inactive. Local
  `/health` 200 for FRIDAY/Inference/Memora/Forge/Sentinel; Stratex
  200 via the `:18003` tunnel; VyralX 200 on AWS. No `000`, no
  false-down rows.
- Server 2 job 137516321480: `success` (stamp 06:03:24Z). Futuris
  active NRestarts=1 since 09:53:36 IST; IntelX active NRestarts=0
  since 09:04:39 IST; Cortex active NRestarts=0 since 09:04:39 IST.
  Local `/health`: Futuris 503, IntelX 503, Cortex 200 — the same
  contract degradation, units active. No `000`, no missing units.

## 3. Bridge arbitration (server-side truth, ~06:05–06:10Z)

- `get_system_info`: FRIDAY-Cloud-Engineering-Bridge v1.30.0, protocol
  2025-11-25; both Oracle servers ONLINE; Server 2 branch `main`,
  commit `ff84c7ff`.
- `oracle_fleet_health`: Server 1 `10.0.0.121` up 40 days, Server 2
  `10.0.0.120` up 31 days. (The tool's "Server 2 hosts
  Sentinel/Cortex/VyralX/Bridge" label is itself stale — Sentinel and
  VyralX no longer run there; noted in VAL-006, not fixed here.)
- `oracle_check_service`: Futuris / IntelX / Stratex units on Server 1
  are MASKED, inactive (correct — none runs on S1 any more; IntelX
  failed on S1 2026-11-20, before the migration); Sentinel unit on
  Server 2 is MASKED, inactive (correct — it runs on S1). These are
  the masked sleepers, not outages.
- Server 1 listeners (read-only `run_shell`): `:10000` FRIDAY,
  `:8001` Inference, `:8002` Memora, `:8006` Forge, `:8008`
  Sentinel, `127.0.0.1:18003` SSH tunnel. No `:8003`, `:8004`,
  `:8005`, `:8010`. Units active: FRIDAY, Inference, Memora, Forge,
  Sentinel (all NRestarts 0, since 10:38:50–10:39:26 IST).
- Server 2 listeners: `:8004` Futuris, `:8005` IntelX, `:8009`
  Cortex, `:8011` bridge, `:6379` Redis. No `:8008`, no `:8010`.
  Units active: Futuris, IntelX, Cortex.
- Deployed FRIDAY `.env` (`/opt/friday_universe/FRIDAY/.env`, mtime
  2026-11-23 09:40:57 IST): agent URL values only — `STRATEX_URL` +
  `FRIDAY_STRATEX_URL` = `127.0.0.1:18003`, `VYRALX_URL` +
  `FRIDAY_VYRALX_URL` = `http://16.176.9.247:8010`, `SENTINEL_URL` +
  `FRIDAY_SENTINEL_URL` = `10.0.0.121:8008` (works, not the deployed
  form), IntelX/Futuris/Cortex = `10.0.0.120:8005/8004/8009`. No key
  or DB value was read, printed, or stored. FRIDAY restarted
  10:38:50 IST, after the `.env` edit — the running process loaded
  the fixed values.
- Deployed code heads: Server 1 `705ab92d`, Server 2 `ff84c7ff`
  (2026-11-23 09:04:11 IST). Repo main is `136533e5` — deployed code
  lags main; the capability-contract behaviour above is the deployed
  code's.

## 4. Per-agent verdicts (REL-004 contract applied, as in VAL-005)

| Agent | Gateway | Live capability evidence | Verdict |
|---|---|---|---|
| FRIDAY | /health 200, /ready 200 | Imports + fleet-status with the new taxonomy; DB connected | REACHABLE (orchestration evidence = imports + status answer) |
| Inference | /health 200, /ready 200 | Static `providers` list; 19 specialists; /ready key pools (config only) | REACHABLE; `model_routing` unknown / CONFIG_ONLY |
| Memora | /health 200, /ready 200 | `capability_report`: `memory_store` ok (live) | **ONLINE** (first capability-backed ONLINE) |
| Stratex | /health 200, /ready 200 | Engine online via tunnel; live balances (VAL-005); freshness fields absent | REACHABLE; trading capability asserted but not freshness-proven |
| Futuris | **/health 503**, /ready 200 | Storage 13/13 live; `forecasting` unknown (NO_MODEL_PROBE) | **DEGRADED, not down** — live, capability unknown |
| IntelX | **/health 503**, /ready 200 (`/readyz`) | DB live round-trip; storage live; `research` unknown (NO_LIVE_PROBE), `model_provider` CONFIG_ONLY | **DEGRADED, not down** — live, capability unknown |
| Forge | /health 200, /ready 200 | DB connected; /ready workspaces writable | REACHABLE; `code_build` / `model_provider` unknown |
| Sentinel | /health 200, /ready 200 | Audit evidence live (VAL-005); `security_engine` constant | REACHABLE; `security_engine` / `database` unknown |
| Cortex | /health 200, /ready 200 | /health is a constant; /ready DB/schema/Redis UP | REACHABLE; capability unknown — /health proves nothing while presenting healthy |
| VyralX | /health 200, /ready 200 | /health is a constant; /ready DB + media DB connected | REACHABLE; capability unknown — /health proves nothing while presenting ok |

**False-down check:** the only agents any record calls down are
Futuris and IntelX (validator 8/10, workflow public-gateway job
`failure`). Both are live by every independent check (ready 200,
units active, listeners present, DB live in their own bodies,
FRIDAY marks them DEGRADED with 43 ms latency, not UNREACHABLE).
**False-down: zero.**
**False-up check:** Memora ONLINE has live capability evidence; the
six REACHABLE are labelled capability-unknown, not ONLINE; the two
DEGRADED are labelled degraded. No agent presents as healthy while
down. **False-up: zero.**

## 5. Open questions / follow-ups for Muse

1. **Validator criterion vs the contract (F1):** the Fleet Live
   Validation public-gateway job now fails on honest degradation.
   Either teach `validate_fleet_live.py` the contract (degraded ≠
   down — e.g. count `/ready` 200 + live DB as live), or accept the
   job failing while Futuris/IntelX capabilities are unprobed. The
   run's `failure` conclusion will otherwise read as a fleet outage
   to anyone who does not read the logs.
2. **Capability probes for Futuris/IntelX:** the REL-006 follow-ups
   VAL-005 named — a live forecasting-model probe and a live research
   probe — are now the difference between DEGRADED and ONLINE for
   these two agents.
3. **Sentinel `.env` value:** one cosmetic fix (`10.0.0.121:8008` →
   `127.0.0.1:8008`) with the next `.env` touch + FRIDAY restart.
4. **Validator TLS probe:** `probe_tls` needs `import socket`
   (one line); without it no TLS evidence is produced.
5. **Stale labels that still predate the layout:** the bridge's
   `oracle_fleet_health` Server 2 label, the repo `AGENTS.md`
   deployment table, Cortex's stale peer list. Cosmetic; VAL-006
   listed them as follow-ups, unchanged here.
6. **Queued for Muse 14 behind VAL-012:** SEN-022 and WF-002
   (board AVAILABLE, owner muse_14, assigned 2026-11-23 ~10:30 IST);
   the work-request cycle stays cancelled while VAL-012 is claimed.

## Evidence index

- Gateway probe raw JSON: workspace `friday-bridge/val012/` —
  `fleet_live_validation_2026-11-23.json` (validator run
  06:01:00–06:01:20Z), `val012_ready_2026-11-23.json` (`/ready`
  sweep), `futuris_health.json`, `intelx_health.json`,
  `fleet_status.json` (FRIDAY `/api/agents/status` 06:01:57Z).
- Workflow run 45121575640 (dispatched by this task, 06:03:13Z):
  public-gateway job 137516321206 `failure` (exit 1, 8/10 — the two
  503s), Server 1 job 137516321531 `success`, Server 2 job
  137516321480 `success`. Job logs quoted in §2.
- Bridge session: FRIDAY-Cloud-Engineering-Bridge v1.30.0, tools
  `get_system_info`, `oracle_fleet_health`,
  `oracle_check_service`, read-only `run_shell`.
- Baselines: VAL-005 (2026-11-22 21:58 IST, 5 false-down),
  VAL-006 §"Pre-fix baseline" (~23:50 IST, 2 false-down), first
  VAL-012 probe (~02:13 IST, 10/10 `/health` 200, 7 ONLINE / 2
  UNREACHABLE — raw JSON lost with /tmp, results in the daily log).
- Contract: `docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`
  (design); implementation is REL-006, landing live.

— Muse 14, TASK-VAL-012, 2026-11-23 ~11:35 IST
