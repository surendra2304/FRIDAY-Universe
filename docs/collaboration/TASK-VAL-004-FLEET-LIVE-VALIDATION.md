# TASK-VAL-004 — Fleet Live Validation, server-side systemctl half — 2026-11-22

Task: VAL-001 re-verification — capture and file the server-side systemctl half of
the full fleet validation (per-agent ActiveState / NRestarts / ActiveEnterTimestamp
+ local /health probes on BOTH servers, with timestamps); close VAL-001's open
next_action. Worker: Muse 8. Claim: issue #35 comment 7074990475; claim PR #1326
merged (merge ef1470d9).

## Dispatch

- Workflow: `Fleet Live Validation` (`.github/workflows/fleet-live-validation.yml`)
- Run: https://github.com/surendra2304/FRIDAY-Universe/actions/runs/44995483145
- Event: `workflow_dispatch`, ref `main`, head `a81a0dc3f8f332990859d84948d230bf67973aad`
  (= main HEAD at dispatch)
- Dispatched: 2026-11-22T06:49:54Z (12:19:54 IST) by Muse 8; completed `success`.
- Jobs (all `success`):
  - Server 1 systemctl evidence — job 137125490107, 06:49:57–06:52:52Z
  - Server 2 systemctl evidence — job 137125490014, 06:49:57–06:50:46Z
  - Public gateway validation — job 137125490112, 06:49:57–06:52:23Z
- Job logs downloaded by Muse 8 from the run (per-job log endpoints) and quoted
  verbatim below; log lines carry their own UTC timestamps.

## Server 1 — systemctl + local /health (stamp 2026-11-22T06:50:12Z)

| Unit | ActiveState | NRestarts | ActiveEnterTimestamp | Local /health |
|---|---|---|---|---|
| FRIDAY | active | 1 | Sun 2026-11-22 11:15:20 IST | 200 |
| Inference | active | 0 | Sun 2026-11-22 06:09:33 IST | 200 |
| Memora | active | 0 | Sun 2026-11-22 11:30:34 IST | 200 |
| Stratex | active | 0 | Sun 2026-11-22 07:44:41 IST | 200 |
| Futuris | **inactive** | 0 | n/a | **000** (connection failed) |
| IntelX | **failed** | 0 | Fri 2026-11-20 23:48:27 IST | **000** (connection failed) |
| Forge | active | 0 | Sat 2026-11-21 22:43:14 IST | 200 |
| Stratex-Daemon | active | 0 | Sun 2026-11-22 07:44:57 IST | (no probe — daemon has no /health in the workflow) |

Log lines (job 137125490107):
`FRIDAY: active=active NRestarts=1 since='Sun 2026-11-22 11:15:20 IST'` (06:50:37Z),
`Inference: active=active NRestarts=0 since='Sun 2026-11-22 06:09:33 IST'` (06:50:59Z),
`Memora: active=active NRestarts=0 since='Sun 2026-11-22 11:30:34 IST'` (06:51:17Z),
`Stratex: active=active NRestarts=0 since='Sun 2026-11-22 07:44:41 IST'` (06:51:38Z),
`Futuris: active=inactive NRestarts=0 since='n/a'` (06:51:59Z),
`IntelX: active=failed NRestarts=0 since='Fri 2026-11-20 23:48:27 IST'` (06:52:15Z),
`Forge: active=active NRestarts=0 since='Sat 2026-11-21 22:43:14 IST'` (06:52:34Z),
`Stratex-Daemon: active=active NRestarts=0 since='Sun 2026-11-22 07:44:57 IST'` (06:52:48Z).
Health: FRIDAY 200, Inference 200, Memora 200, Stratex 200, Futuris 000000
(`##[warning]Futuris local /health returned 000000`), IntelX 000000
(`##[warning]IntelX local /health returned 000000`), Forge 200 (06:52:49–06:52:50Z).
No `NRestarts > 5` crash-loop warning fired on Server 1.

## Server 2 — systemctl + local /health (stamp 2026-11-22T06:50:08Z)

| Unit | ActiveState | NRestarts | ActiveEnterTimestamp | Local /health |
|---|---|---|---|---|
| VyralX | **inactive** | 0 | n/a | **000** (connection failed) |
| Sentinel | **inactive** | 0 | n/a | **000** (connection failed) |
| Cortex | active | 0 | Sun 2026-11-22 12:16:38 IST | 200 |
| VyralX-Daemon | **inactive** | 0 | n/a | (no probe — daemon has no /health in the workflow) |

Log lines (job 137125490014):
`VyralX: active=inactive NRestarts=0 since='n/a'` (06:50:18Z),
`Sentinel: active=inactive NRestarts=0 since='n/a'` (06:50:26Z),
`Cortex: active=active NRestarts=0 since='Sun 2026-11-22 12:16:38 IST'` (06:50:35Z),
`VyralX-Daemon: active=inactive NRestarts=0 since='n/a'` (06:50:44Z).
Health: Sentinel 000000 (`##[warning]Sentinel local /health returned 000000`),
Cortex 200, VyralX 000000 (`##[warning]VyralX local /health returned 000000`)
(06:50:44Z). No `NRestarts > 5` crash-loop warning fired on Server 2.

Context (not a finding of this task): Cortex `ActiveEnterTimestamp` 12:16:38 IST is
a restart minutes before this dispatch — Muse 1's TASK-API-005 Cortex key re-sync
work was in progress at the time (claim PR #1332 merged ~12:05 IST). No action taken
here.

## Public-gateway half — same run (job 137125490112, 06:50:01–06:52:21Z)

`scripts/validate_fleet_live.py` via `https://friday-universe.duckdns.org`:

| Agent | /health | Latency |
|---|---|---|
| FRIDAY | OK 200 | 17.419s |
| Inference | OK 200 | 9.296s |
| Memora | OK 200 | 1.217s |
| Stratex | OK 200 | 14.099s |
| Futuris | OK 200 | 2.618s |
| IntelX | OK 200 | 3.6s |
| Forge | OK 200 | 11.777s |
| Sentinel | OK 200 | 7.945s |
| Cortex | OK 200 | 1.178s |
| VyralX | OK 200 | 1.679s |

Functional probes:
- FRIDAY `fleet_status`: PASS (HTTP 200, agents dict present).
- FRIDAY `friend_persona_greeting`: **FAIL (HTTP None)** — remote chat without owner
  key did NOT return a clean block; the probe got no HTTP response at all.
- FRIDAY `control_session_requires_key`: PASS (HTTP 401, unauthenticated remote mint
  blocked — TASK-SEC-005 live).
- Memora `health_detail`: PASS (HTTP 200).
- Bridge `initialize`: **FAIL (HTTP None)** — no HTTP response.
- Script summary line: `SUMMARY: 10/10 agents healthy; bridge FAIL; all functional
  probes SEE REPORT`.

VAL-001 baseline (2026-11-10, `docs/validation/FLEET_LIVE_VALIDATION_2026-11-10.md`):
10/10 healthy, latencies 0.27–0.86s, bridge initialize 200 (v1.30.0), all functional
probes PASS (friend_persona_greeting 401, control-session mint 401). The 2026-11-10
run is the public half VAL-001 filed; this run re-probes it.

## Findings

- **F1 — Gateway health does NOT reflect systemd state for 4 agents.** The public
  gateway reports Futuris, IntelX, Sentinel and VyralX all OK (200) in the same run
  where systemctl on their home servers reports Futuris `inactive`, IntelX `failed`,
  Sentinel `inactive`, VyralX `inactive`, and their local /health probes fail
  (000). A gateway 200 for these four agents is therefore not evidence the agent
  process is running. The gateway health path for these agents needs a follow-up
  (what answers /futuris, /intelx, /sentinel, /vyralx health when the unit is down).
- **F2 — Bridge initialize FAIL (HTTP None) in this run.** VAL-001 (2026-11-10) had
  bridge initialize 200 (v1.30.0). In this run the probe got no HTTP response. Not
  determined here whether transient (runner network) or a live bridge problem; the
  bridge is separately reachable for other work, so this is filed as observed, not
  as a bridge outage.
- **F3 — `friend_persona_greeting` FAIL (HTTP None).** VAL-001 had a clean PASS
  (HTTP 401 block). This run got no HTTP response, so the D-023 gate block was not
  demonstrated in this run. `control_session_requires_key` still PASSED with 401.
- **F4 — Gateway health latencies much slower than 2026-11-10.** FRIDAY 17.4s,
  Stratex 14.1s, Forge 11.8s, Inference 9.3s, Sentinel 7.9s — versus 0.27–0.86s on
  2026-11-10. Observed, not diagnosed; possibly load or cold paths.
- **F5 — No crash-loop signal.** NRestarts is 0 on every unit except FRIDAY (1).
  No unit crossed the workflow's `NRestarts > 5` warning threshold. IntelX
  `failed` since Fri 2026-11-20 23:48:27 IST with NRestarts 0 reads as a unit that
  failed and was not restarted (not a loop) — consistent with the supervision
  re-probe finding that IntelX is a stale probe target / not running (TASK-ORCH-011).
  Futuris / Sentinel / VyralX / VyralX-Daemon `inactive` with NRestarts 0 are
  stopped units, not crash loops.

## Verdict

- **Server-side half: captured and filed.** This document + run 44995483145 satisfy
  the capture part of TASK-VAL-004's acceptance: per-agent ActiveState / NRestarts /
  ActiveEnterTimestamp + local /health on both servers, with timestamps.
- **Full-fleet VERIFIED: NOT claimed.** VAL-001's next_action said "after that, close
  as VERIFIED citing both halves" — but the two halves disagree: the gateway says
  10/10 healthy while systemctl says 4 agents down, and the bridge initialize and
  one functional probe failed in this run. Claiming VERIFIED on this evidence would
  be false. VAL-001's record is left untouched (MERGED, owner zai) for Muse to
  decide; the dispatch it asked for is done, the VERIFIED close is not earned.
- **Recommended follow-ups for Muse's pool:** (a) explain/fix the gateway-health vs
  systemd mismatch for Futuris / IntelX / Sentinel / VyralX (F1); (b) re-probe the
  bridge initialize + `friend_persona_greeting` paths (F2/F3); (c) look at the slow
  gateway health latencies (F4). None of these were actioned here — this task is
  evidence capture only, and no live service was changed.

No live service was restarted, reconfigured, or written to by this task. The only
write was the workflow dispatch itself. No secret was read, printed, logged, stored,
or posted.
