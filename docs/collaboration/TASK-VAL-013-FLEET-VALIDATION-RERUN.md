# TASK-VAL-013* — Fleet validation re-run — 2026-11-23

Task: full fleet validation re-run — (1) server-side systemctl half across
the deployed 6/4 layout, (2) public-gateway half against live public
endpoints. Per-agent evidence, capability state cited. Worker: Muse 1.
Claim: issue #35 comment 7090012579; work PR #1445 (branch
`muse1/task-val-013-fleet-validation-rerun`, base main `d6a92978`).

Assignment: coordinator watch 7089537118 (~07:25 IST, 2026-11-23) —
blocked-head rule; TASK-SEN-022 is held on 3 CI failures and moves to
queue tail. Queue: VAL-013* → REL-080* → SEN-022. No board record is
filed in this PR — the VAL-013* queue filing rides in the coordinator's
next consolidated board PR, per the same direction as Muse 13's ORCH-013.

Method (read-only throughout; no credentials used, no state changed;
follows Muse 14's VAL-012 probe and Muse 13's VAL-005 evidence format):

1. **Public-gateway probe** from this VM, main pass 2026-11-23
   08:02:46–08:03:53 IST (02:32:46–02:33:53Z): full `/health` + `/ready`
   bodies for all 10 agents via `https://friday-universe.duckdns.org`,
   plus FRIDAY `/api/agents/status` and bridge MCP `initialize`. Re-probes
   of the two FRIDAY routes that failed mid-pass at ~08:04:30 IST and
   08:06:36 IST (see F1 — the failures coincide with a live OOM kill).
   Probe script `/tmp/probe_val013.py`; raw JSON kept in the run workspace
   (`~/workspace/val-013/val013_probe.json`, `val013_fleetstatus.json`,
   `val013_authgate.json`).
2. **Fleet Live Validation workflow** dispatched 2026-11-23 ~08:02 IST,
   run https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45100800749
   (head main `d6a92978`, completed `success`, all 3 jobs green):
   public-gateway job 137450960308, Server 2 job 137450960385, Server 1
   job 137450960723. Job logs are sign-in-gated in the browser; only the
   run/job conclusions are cited — the per-agent evidence below is from
   my own first-hand probes, not from the workflow's green tick.
3. **Server-side arbitration** via the engineering bridge
   (`https://friday-universe.duckdns.org/bridge/mcp`, FRIDAY-Cloud-
   Engineering-Bridge v1.30.0): `oracle_fleet_health`, read-only
   `run_shell` (systemctl states + NRestarts + ActiveEnterTimestamp,
   listeners, processes on Server 2; SSH hop to Server 1 `10.0.0.121`
   for the same, plus local /health, FRIDAY journal, and the deployed
   `/etc/caddy/Caddyfile`). No restarts, no writes, no deploys.

## Headline verdict

**No agent is down.** All 10 agents answer live at their deployed
upstreams. Final state after the transient below: 10/10 `/health` 200,
10/10 `/ready` 200, bridge initialize 200, workflow 3/3 jobs success.

- **F1 — FRIDAY was OOM-killed mid-probe and auto-restarted (caught
  live).** S1 `free` showed 68 MB free at ~08:08 IST; FRIDAY's own
  proactive monitor had warned at 07:59:54 IST that RAM was at 91.4%
  (0.85/0.93 GB). At 08:02:57 IST the dying FRIDAY process logged an
  oracledb `Connection disconnected` traceback; at 08:03:47 IST the
  kernel OOM-killed python pid 2704298 in the FRIDAY cgroup
  (`Memory cgroup out of memory`, total-vm 761,972 kB); systemd recorded
  `FRIDAY.service: Failed with result 'oom-kill'` at 08:03:55 and
  auto-restarted it at 08:04:01 (restart counter 1, new pid 2707381,
  uvicorn up 08:04:17, startup complete 08:04:18). My gateway probe
  straddled the kill exactly: FRIDAY `/health` 200 at 08:02:49, `/ready`
  read-timeout (15 s) at ~08:02:50, `/api/agents/status` 502 (empty body)
  at ~08:03:52, both routes 502 again at ~08:04:30, both 200 again by
  08:06:36 (re-verified 08:07:00). The 502s were the dead/restarting
  upstream, not a gateway fault and not a FRIDAY outage — FRIDAY is
  `active` with NRestarts=1 and serves `/ready` 200 locally and via the
  gateway now. One caveat, stated plainly: the 08:04:30 502s arrived
  ~12 s after uvicorn reported "Application startup complete" (08:04:18),
  so the sub-minute 502 mechanism after the new process was listening
  is not isolated — Caddy upstream recovery lag is the likely cause, not
  proven. No other OOM kill occurred on either server today (journal
  sweep 00:00–08:08 IST: S1 only this FRIDAY kill; S2 none).
- **F2 — FRIDAY's fleet-status probe map is STILL stale for
  Stratex/VyralX.** `/api/agents/status` (200, 08:07:00 IST) reports
  `degraded`, ONLINE 7 / UNREACHABLE 2 — the same 2 as VAL-012 (02:13
  IST): Stratex `http://127.0.0.1:8003` ConnectError and VyralX
  `http://10.0.0.120:8010` ConnectError. Both agents are live at their
  deployed upstreams (Stratex via the 127.0.0.1:18003 SSH tunnel,
  VyralX on AWS 16.176.9.247:8010 — both /health 200 from Server 1).
  VAL-006 fixed the repo maps and the workflow lists, but the deployed
  FRIDAY — restarted 08:04 IST, after the VAL-006 merge — still probes
  the old addresses. Which map the served FRIDAY actually reads is not
  established by this run; that is the follow-up, not a new outage.
- **F3 — REL-004 is still design-only everywhere.** Every agent's
  `/health` still carries `evidence_class: process_liveness` and no
  agent has a `capabilities` block, so per contract §4 rule 2 no agent
  may be called ONLINE — all are REACHABLE (capability unknown) except
  where the body's own fields give live capability evidence (noted per
  agent). Cortex and VyralX `/health` are still pure constants that
  prove nothing while presenting `healthy`/`ok` + HTTP 200. Same
  finding as VAL-005, unchanged.
- **FIXED since VAL-005 — the auth gate holds.** VAL-005's F2
  (unauthenticated `POST /friday/api/chat` returned 200 + live reply)
  is closed: the same probe now returns **HTTP 401** (`"A valid FRIDAY
  control API key is required."`, 1.29 s, 08:0x IST). VAL-007's fix
  (PR #1405) verified live. One probe only — the same probe the fleet
  validator itself performs.

## 1. Public-gateway probe (this VM, 08:02:46–08:03:53 IST)

| Agent | /health | /ready | Top-level status | `evidence_class` |
|---|---|---|---|---|
| FRIDAY | 200 (3.121 s) | TIMEOUT 15 s, then 502, then **200** (08:06:36, 1.142 s) | `healthy` | `process_liveness` |
| Inference | 200 (1.694 s) | 200 (1.564 s) | `healthy` | `process_liveness` |
| Memora | 200 (1.139 s) | 200 (10.260 s) | `healthy` | `process_liveness` |
| Stratex | 200 (2.437 s) | 200 (6.052 s) | `ok` | `process_liveness` |
| Futuris | 200 (1.366 s) | 200 (1.077 s) | `ok` | `process_liveness` |
| IntelX | 200 (1.144 s) | 200 (1.152 s) (`/readyz`) | `ok` | `process_liveness` |
| Forge | 200 (1.631 s) | 200 (2.794 s) | `ok` | `process_liveness` |
| Sentinel | 200 (1.259 s) | 200 (2.314 s) | `ok` | `process_liveness` |
| Cortex | 200 (1.293 s) | 200 (1.202 s) | `healthy` | `process_liveness` |
| VyralX | 200 (1.124 s) | 200 (5.877 s) | `ok` | `process_liveness` |

Full bodies (verbatim, truncated only where noted; full JSON in the run
workspace):

- **FRIDAY** `{"overall": "healthy", "evidence_class":
  "process_liveness", "observed_at": "2026-11-23T02:32:49.815602+00:00",
  "checks": [{"name": "python", "state": "healthy", "details":
  "3.10.12"}, {"name": "platform", ...}, {"name": "friday", "details":
  "imported"}, {"name": "friday_deep", "details": "imported"}],
  "status": "healthy", "service": "friday_core", "agent": "FRIDAY",
  "version": "2.0.0", "peers_mesh": "configured_unverified"}` — imports
  only; `peers_mesh` provenance still unverified (contract §6 Q1).
  `/ready` 200 (08:06:36): `{"status": "ready", "ready": true,
  "service": "friday_core", "database": "connected",
  "database_backend": "oracle", "mesh": "configured", "disk_free_mb":
  71724.4, "disk": "healthy"}`.
- **Inference** `{"status": "healthy", "service": "inference",
  "evidence_class": "process_liveness", "providers": ["groq",
  "cerebras", "openrouter", "gemini", "nvidia"],
  "active_specialist_agents": 19, "version": "2.0.0"}` — `providers` is
  the static name list (contract: must be `configured_providers`;
  `model_routing` is `unknown` / `CONFIG_ONLY` until a live provider
  probe exists). `/ready` 200: `evidence_class: service_readiness`,
  database connected (Oracle).
- **Memora** `{"status": "healthy", "service": "memora",
  "evidence_class": "process_liveness", "storage": "oracle",
  "database": "healthy", "database_backend": "oracle",
  "database_durable": true, "vector_store": {"status": "available",
  "backend": "oracle_23ai_native_vector", "dimension": 384}}` — the
  most honest `/health` in the fleet (DB + vector readiness live);
  only the `evidence_class` label lies. `/ready` 200:
  `evidence_class: readiness_probe`, `circuits: healthy`.
- **Stratex** `{"capability_reasons": [], "capability_warnings":
  ["DEMO_ENVIRONMENT: execution venues are Binance Futures testnet and
  OANDA practice"], "daemon_balance": 10556.70536508, "dashboard":
  "online", "engine": "online", "engine_healthy": true,
  "engine_source": "multi_venue_daemon", "engine_trading_capable":
  true, "open_positions": 30, "unrealized_pnl": 90.92, "service":
  "stratex", "status": "ok", "version": "2.2.0"}` — engine fields assert
  ok, but the live body still omits the freshness evidence the
  contract's §5 reference mapping requires (no heartbeat age, no
  last-evaluation timestamp). Values are live: balance 10556.71,
  30 open positions. `/ready` 200: `evidence_class: engine_readiness`,
  database connected.
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
  (`unknown` / `NO_LIVE_PROBE`). `/readyz` 200: `evidence_class:
  dependency_readiness`, database connected, `model_provider:
  "configured"`, `model_provider_check: "configuration_only"` —
  exactly the contract's CONFIG_ONLY case.
- **Forge** `{"status": "ok", "service": "forge", "version": "2.0.0",
  "uptime_seconds": 13098.8, "database_connected": true,
  "evidence_class": "process_liveness"}` — `code_build` /
  `model_provider` unprobed by `/health`. `/ready` 200: database
  connected, `workspaces_writable: true`.
- **Sentinel** `{"status": "ok", "service": "sentinel",
  "evidence_class": "process_liveness", "security_engine": "active",
  "version": "1.0.0", "environment": "production",
  "kill_switch_active": false, "audit_chain_valid": true,
  "audit_chain_entries": 13, "audit_chain_vacuous": false}` — audit
  evidence is live and non-vacuous (13 entries, up from 11 in VAL-005);
  `security_engine: "active"` is a constant string (contract: back
  with the `/ready` crypto check or `unknown`). `/ready` 200:
  `evidence_class: local_readiness_checks`, crypto keys, audit
  integrity, event bus, durability all true.
- **Cortex** `{"status": "healthy", "service": "cortex", "version":
  "2.1.0", "evidence_class": "process_liveness"}` — a constant; no
  checks of any kind. `/ready` 200: `evidence_class:
  dependency_readiness`, `database`/`schema`/`redis` UP, `degraded:
  ["ai_universe", "sentinel", "intelx", "futuris"]` — the peer entries
  are `UNKNOWN: no live readiness probe configured` (contract: optional,
  never fatal). The peer list still names sentinel/intelx/futuris
  degraded: all three are alive at their deployed homes, so Cortex's
  peer knowledge is itself stale (same as VAL-005).
- **VyralX** `{"status": "ok", "service": "vyralx", "version": "0.2.0",
  "evidence_class": "process_liveness"}` — a constant; no checks of
  any kind. `/ready` 200: database connected, media database connected.

**FRIDAY `/api/agents/status`** (200, 08:07:00 IST): `status: degraded`,
`scope: peer_endpoint_reachability_only`, counts ONLINE 7 / UNREACHABLE
2 / REACHABLE 0 / DEGRADED 0, `agent_count: 9` (FRIDAY herself is not
counted). ONLINE: Inference (44 ms), Memora (22 ms), IntelX (37 ms,
`10.0.0.120:8005`), Futuris (39 ms, `10.0.0.120:8004`), Cortex (39 ms,
`10.0.0.120:8009`), Forge (39 ms), Sentinel (34 ms, `10.0.0.121:8008`)
— each with the caveat "…was not checked". UNREACHABLE: Stratex
(`127.0.0.1:8003` ConnectError, 10 ms), VyralX (`10.0.0.120:8010`
ConnectError, 8 ms). Both probe targets are stale addresses (F2); the
agents are alive at their deployed upstreams. Note the probe map has
improved since VAL-005 (IntelX/Futuris/Cortex/Sentinel now probe their
deployed addresses — VAL-006's fix did land for those four); only
Stratex and VyralX still point at dead addresses.

**Bridge MCP `initialize`**: HTTP 200, server
FRIDAY-Cloud-Engineering-Bridge v1.30.0 (protocol 2024-11-05).

**Auth gate** (VAL-005 F2 re-probe, one probe): unauthenticated `POST
/friday/api/chat` (`{"message": "hello FRIDAY"}`, no key, no cookie)
returned **HTTP 401** (`"A valid FRIDAY control API key is required."`,
1.29 s). The gate holds — VAL-007's fix verified live.

## 2. Workflow run 45100800749 (dispatched by this task, ~08:02 IST)

- Public-gateway job 137450960308: `success` (02:32:32–02:33:46Z).
- Server 2 job 137450960385: `success` (02:32:33–02:32:55Z).
- Server 1 job 137450960723: `success` (02:32:32–02:34:06Z).
- Run conclusion `success` on head main `d6a92978`. Job logs are
  sign-in-gated, so no log lines are quoted; the server-side rows below
  are from my own bridge arbitration, which ran in parallel and agrees
  with the workflow's success (the Server 1 job ran 02:32:32–02:34:06Z —
  straddling the FRIDAY OOM kill at 02:33:47Z — yet concluded success,
  because it probes the tunnel/AWS routes and the S1 units that stayed
  up; FRIDAY's own local /health would have failed only in the seconds
  around the kill).

## 3. Server-side systemctl evidence (bridge, ~08:04–08:08 IST)

Server 1 `10.0.0.121` — up 39 days, 20:46; load 2.22/2.12/1.35;
Mem 956 MB total, 544 used, 68 free, 343 buff/cache; disk 97G, 27G
used (71G avail). Server 2 `10.0.0.120` — up 31 days, 13:38; load
0.02/0.04/0.08; Mem 956 MB total, 558 used, 83 free; disk 49G, 26G
used (23G avail). (Bridge's own labels still call S2 the host of
"Sentinel/Cortex/VyralX/Bridge" — stale label, same as VAL-005;
Sentinel runs on S1 now.)

| Unit | Server | Active | NRestarts | Since (IST) |
|---|---|---|---|---|
| FRIDAY | S1 | active | **1** | 2026-11-23 08:04:01 (OOM auto-restart, F1) |
| Inference | S1 | active | 0 | 2026-11-23 07:37:33 |
| Memora | S1 | active | 0 | 2026-11-23 04:23:06 |
| Forge | S1 | active | 0 | 2026-11-23 04:23:13 |
| Sentinel | S1 | active | 0 | 2026-11-23 04:23:25 |
| Stratex-Daemon | S1 | inactive (masked, by design) | 0 | n/a |
| Futuris | S2 | active | 0 | 2026-11-23 04:22:25 |
| IntelX | S2 | active | 0 | 2026-11-23 07:37:19 |
| Cortex | S2 | active | 0 | 2026-11-23 05:25:17 |

No NRestarts > 0 anywhere except FRIDAY's single OOM auto-restart —
no crash loops. Restart waves observed this morning (S1
Memora/Forge/Sentinel ~04:23, S2 Futuris 04:22, Cortex 05:25,
Inference + IntelX both ~07:37): their causes are NOT established by
this run's evidence (no OOM kill on S2 today; S1's only OOM kill today
is FRIDAY 08:03:47) — recorded, not speculated.

Listeners/processes (read-only `ss` + `ps`):

- S1: `:10000` FRIDAY (uvicorn pid 2707381, since 08:04), `:8001`
  Inference (pid 2693809), `:8002` Memora (pid 2591767), `:8006` Forge
  (pid 2591888), `:8008` Sentinel (pid 2592081), `127.0.0.1:18003` SSH
  tunnel (ssh pid 2263571). No `:8003`, `:8004`, `:8005`, `:8010` — no
  Stratex/Futuris/IntelX/VyralX processes on S1, as deployed. Local
  /health 200 for FRIDAY/Inference/Memora/Forge/Sentinel. Stratex via
  tunnel 200; VyralX on AWS (`16.176.9.247:8010`) 200 from S1.
- S2: `:8004` Futuris (uvicorn pid 599030), `:8005` IntelX (pid
  601626), `:8009` Cortex (pid 599993), `:8011` bridge (pid 537376),
  `:6379` Redis. No `:8008`, no `:8010` — no Sentinel/VyralX processes
  on S2, as deployed. Local /health 200 for Futuris/IntelX/Cortex.

Deployed `/etc/caddy/Caddyfile` (S1) vs repo `deploy/Caddyfile`: the
`reverse_proxy` lines are identical, in the same order — no drift since
VAL-006: FRIDAY/Inference/Memora 127.0.0.1:10000/8001/8002, Stratex
127.0.0.1:18003 (tunnel), Futuris/IntelX 10.0.0.120:8004/8005, Forge
127.0.0.1:8006, bridge/mcp/messages 10.0.0.120:8011, VyralX
16.176.9.247:8010, Sentinel 127.0.0.1:8008, Cortex 10.0.0.120:8009.

## 4. Per-agent capability verdicts (REL-004 contract applied)

Contract status: design-only, unimplemented (REL-006). No agent has a
`capabilities` block, so per §4 rule 2 no agent is ONLINE; all are
REACHABLE (capability unknown) except where the body's own fields give
live capability evidence (noted per agent).

| Agent | Presented (gateway) | Live capability evidence | Verdict |
|---|---|---|---|
| FRIDAY | `healthy` / 200 (after OOM restart) | Imports only; `peers_mesh: configured_unverified`; /ready DB connected, disk 71.7 GB free | REACHABLE; OOM-killed 08:03:47, auto-restarted, serving again |
| Inference | `healthy` / 200 | Static `providers` list; 19 specialists; /ready DB connected | REACHABLE; `model_routing` unknown / CONFIG_ONLY |
| Memora | `healthy` / 200 | DB healthy, event store Oracle, vector available (live) | REACHABLE; capability evidence present in body, but no contract block — not ONLINE |
| Stratex | `ok` / 200 | Engine online, trading_capable true, 30 open positions, live balance 10556.71 (AWS U1 via tunnel); freshness fields absent | REACHABLE; trading capability asserted but not freshness-proven; served via SSH tunnel, unit masked |
| Futuris | `ok` / 200 | Storage 13/13; /ready DB connected | REACHABLE; `forecasting` unknown / NO_MODEL_PROBE |
| IntelX | `ok` / 200 | DB `not_checked` (honest); mock_mode false; /readyz provider config-only | REACHABLE; `research` unknown / NO_LIVE_PROBE |
| Forge | `ok` / 200 | DB connected; /ready workspaces writable | REACHABLE; `code_build` / `model_provider` unknown / NO_LIVE_PROBE |
| Sentinel | `ok` / 200 | Audit chain valid, 13 entries, non-vacuous, durable (live) | REACHABLE; audit evidence present in body; `security_engine` constant → unknown |
| Cortex | `healthy` / 200 | /health is a constant (no checks); /ready DB/schema/Redis UP | REACHABLE; **capability unknown — /health proves nothing while presenting healthy** |
| VyralX | `ok` / 200 | /health is a constant (no checks); /ready DB + media DB connected | REACHABLE; **capability unknown — /health proves nothing while presenting ok** |

**Agents presenting as ok while degraded:** none is down, so there is
no "ok while down" case. The exact degraded capabilities, in contract
terms, are the `unknown` required capabilities above — unchanged from
VAL-005. The new live finding is F1 (FRIDAY OOM kill + recovery) and
the narrowed F2 (only Stratex/VyralX probe addresses still stale).

## 5. Open questions / follow-ups for Muse

1. **S1 RAM is the standing fleet risk (F1).** FRIDAY was OOM-killed
   at 91.4% RAM with 68 MB free; S2 is nearly as tight (83 MB free).
   The auto-restart saved the morning, but a 956 MB host running five
   agents plus Caddy has no headroom. A memory-raise, agent-move, or
   documented OOM watch is owed — this is the same failure class as
   TASK-FUT-015 (Futuris OOM-killed, zero fits). The 04:22–07:37
   restart waves are unexplained in this run; if the watcher or a
   coordinator run restarted them, that should be filed so the next
   validation does not re-open it.
2. **FRIDAY probe map (F2):** Stratex and VyralX still probe dead
   addresses after VAL-006. Establish which map the served FRIDAY
   reads and re-point those two entries (Stratex → tunnel 18003 or
   the AWS host; VyralX → 16.176.9.247:8010), then re-probe
   `/api/agents/status` — it should read `healthy` / 9 ONLINE, not
   `degraded` / 7+2.
3. **REL-006 implementation** remains the path to real capability
   reporting; this re-probe is the baseline it will be measured
   against (notably: Stratex freshness fields, Cortex/VyralX
   constants, Inference static provider list, IntelX CONFIG_ONLY).
4. **Cortex peer list** still names sentinel/intelx/futuris degraded —
   its peer knowledge has no live probe; harmless under the contract
   (optional) but worth a note when the probe map is fixed.
5. Bridge-tool quirk (not a finding): `oracle_fleet_health` still
   labels Server 2 as the host of "Sentinel/Cortex/VyralX/Bridge" —
   stale since the VAL-006 layout move.

## Evidence index

- Gateway probe raw JSON: run workspace `~/workspace/val-013/val013_probe.json`
  (probe 2026-11-23 08:02:46–08:03:53 IST; 10 × /health + 10 × /ready +
  `/friday/api/agents/status` + bridge initialize); re-probe samples
  recorded in §1; fleet-status full body
  `~/workspace/val-013/val013_fleetstatus.json` (08:07:00 IST);
  auth-gate probe `~/workspace/val-013/val013_authgate.json` (401).
- Workflow run 45100800749 (all 3 jobs `success`): public-gateway job
  137450960308, Server 2 job 137450960385, Server 1 job 137450960723.
  Job logs not quoted (sign-in-gated); conclusions cited from the API.
- Bridge session: FRIDAY-Cloud-Engineering-Bridge v1.30.0, tools
  `oracle_fleet_health`, `run_shell` (read-only commands only).
- FRIDAY journal (S1, read via bridge): OOM kill 08:03:47 IST,
  systemd `oom-kill` 08:03:55, auto-restart 08:04:01, uvicorn up
  08:04:17, startup complete 08:04:18 (new pid 2707381).
- Deployed Caddyfile: `/etc/caddy/Caddyfile` on Server 1, read via the
  bridge (§3). Repo copy: `deploy/Caddyfile` (identical reverse_proxy
  lines, no drift).
- Contract: `docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`.
- Precedents: `docs/collaboration/TASK-VAL-005-FLEET-CAPABILITY-REPROBE.md`
  (Muse 13), Muse 14's VAL-012 probe (02:13 IST, hub 7085474289 /
  7086113191 — same 7 ONLINE / 2 UNREACHABLE split).

— Muse 1, TASK-VAL-013*, 2026-11-23 ~08:15 IST
