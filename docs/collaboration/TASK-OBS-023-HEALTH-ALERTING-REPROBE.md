# TASK-OBS-023 — Health-alerting re-probe run 2 (checkpoint 1: read leg + probe plan)

**Task:** health-alerting re-probe run 2 — verify the OBS-008 alerting path fires on a real fault.
**Acceptance:** a real induced fault produces a fleet health alert with the alert text filed;
no alert means the gap is named, not assumed.
**Owner:** muse_17. **Branch:** `muse17/obs-023`.
**Assignment:** coordinator watch 7116727904 (2026-11-24 ~04:45 IST, queue position 3).
**Claim:** hub #1483 comment 7118289110 (2026-11-24 ~06:10 IST) under the blocked-head rule
(OBS-015 merged #1556; VYR-050 head blocked on clearance 7111797017).
**Claim PR:** #1600 MERGED 2026-11-24T02:57:40Z (merge `06a7f5e3`); board on main `d9f514cb`
reads OBS-023 CLAIMED / muse_17 / branch `muse17/obs-023` (verified first-hand this run,
board file 18,722 lines). Note: the board record's `pr:` is still null and its
`next_action` still says the claim PR is owed — the flip rides in the work PR.
**Checkpoint 1:** read leg + probe plan, committed 2026-11-24 ~09:15 IST.
**Checkpoint 2:** live leg DONE, filed 2026-11-24 ~11:20 IST (section 7 below).
**Status:** implemented YES / tested YES (live fault) / merged NO (work PR now) /
deployed N/A / production-verified PARTIAL — alert path verified journal-only;
external delivery unproven (Gap 1 still open, see section 7).

## 1. OBS-008 baseline (2026-11-22, Muse 7, docs/collaboration/TASK-OBS-008-HEALTH-ALERTING-REPROBE.md)

- Watcher timer enabled + active on S1 and S2, 5-min cycles, state fresh.
- Drill proved the dispatch code path once: synthetic down service -> watcher
  `--alert-command` -> `notify_owner()` -> `NotifyResult.SENT`, exactly once.
- Gap 1 (production): `FLEET_ALERT_COMMAND` unset on both servers -> alerts
  journal-only, nothing leaves the server. Fix needs a Muse decision (which
  notify endpoint/command to wire). NOT implemented in OBS-008.
- Gap 2 (delivery): raw `<...>` in alert text broke the Telegram send
  (`parse_mode=HTML`, no escaping). Fix belongs in gateway or watcher.

## 2. Gap re-check against main (07:10 IST run, first-hand)

- Gap 2: CLOSED in code. `FRIDAY/src/friday/proactive/telegram_gateway.py`
  `send_message` now does `html.escape(text, quote=False)` (TASK-OBS-010).
- Gap 1: STILL OPEN in the repo unit. `deploy/fleet-health-watcher.service`
  still carries only the commented-out `FLEET_ALERT_COMMAND` example; the
  watcher still guards dispatch on `if alert_command:`
  (`scripts/fleet_health_watcher.py:331`). Live-server state (drop-in/env)
  still unknown — needs the bridge check in the probe below.

## 3. Probe plan (live leg — needs Muse clearance)

1. Bridge check, S1 + S2: timer enabled/active + last trigger; `systemctl show
   fleet-health-watcher.service -p Environment` and any drop-in for
   `FLEET_ALERT_COMMAND`; `--status` freshness; gateway configured +
   `FRIDAY_OWNER_NOTIFY` kill switch state (same gate as OBS-008).
2. Induce a REAL fault: stop one real watched fleet service briefly (pick a
   non-critical one; a service already known down/sleeping is NOT a fault —
   it must be a service that is up, then stopped by me, then restored).
   Record stop time, service, PID.
3. Observe the next watcher cycle(s): journal for the `[CRITICAL] SERVICE_DOWN`
   line; state file for the new alert; gate state (day_count, event keys)
   before/after; Telegram receipt if an alert is delivered.
4. Restore the service immediately after the alert (or after the cycle proves
   the raise); confirm the watcher reports healthy again next cycle.
5. Verdict per acceptance: alert text filed verbatim if delivered; if nothing
   is delivered, name the exact gap (expected: Gap 1 still unwired on the live
   servers) with the live evidence, not an assumption.

## 4. Clearance / decisions owed from Muse

- Live-server probe clearance (bridge read + induce + restore a real service).
  Requested this run on hub #1483 (see hourly self-check status post ~09:15 IST).
- Gap 1 decision (which notify endpoint/command to wire) — owed since OBS-008,
  still open. If Muse wires it first, this probe becomes a true end-to-end
  production proof; if not, the probe documents the journal-only outcome.

## 5. Blockers

- VYR-050 clearance (`sudo -n systemctl enable --now vyralx-metrics-sync.timer`
  on S2) still unanswered ~10h (request comment 7111797017, ~01:05 IST).
  Separate task; the OBS-023 live leg is NOT blocked on it.
- OBS-023 live leg: CLEARANCE RECEIVED (coordinator watch 7121813967, ~09:45 IST,
  "CLEARED WITH CONDITIONS") and DONE this run (section 7). No live-server
  touch remains for OBS-023 except the merge.
- Gap 1 decision (which notify endpoint/command to wire) — still owed since
  OBS-008. It is the only thing standing between this probe and a true
  end-to-end production proof.

## 6. Next

- Work PR open (this doc + board flip CLAIMED -> IN_REVIEW, `pr:` set) — merge owed.
- Queue after OBS-023: VYR-054 (AVAILABLE, owner muse_17, queue pos 3) —
  claim when it reaches the head (after OBS-023 merges; VYR-050 still blocked
  on clearance 7111797017).

## 7. Checkpoint 2 — live leg DONE (2026-11-24 ~11:00–11:20 IST)

Clearance: coordinator watch 7121813967 (~09:45 IST) — live leg CLEARED WITH
CONDITIONS (post the exact service + fault + revert plan on the hub before
inducing; fault window short; revert immediately after the alert fires, or
after a bounded window if no alert). Fault plan posted on #1483 as comment
7122468282 (~10:25 IST): service Memora.service on S1; fault
`sudo systemctl stop Memora.service` just after a watcher cycle; revert
`sudo systemctl start Memora.service` immediately after the `[CRITICAL]` raise
(bounded ~6-min window if no alert). Memora chosen: healthy in the 10:09:38 IST
cycle, watched, least-coupled. Bridge stalled ~10:11–11:01 IST, so the induction
waited for recovery; no live-server change was made before this run.

### 7.1 Pre-state (S1 + S2, first-hand via bridge, 11:02:37 IST)

- S1: watcher timer enabled + active; `systemctl show
  fleet-health-watcher.service -p Environment` EMPTY — `FLEET_ALERT_COMMAND`
  still unset, no drop-in (Gap 1 still open on S1). Memora.service active.
  State file fresh (modified 11:01, `last_cycle` 2026-11-24T05:31:09Z =
  11:01:09 IST). Open alerts: IntelX + Futuris `SERVICE_DOWN` (chronic
  sleeping copies), Stratex `SERVICE_DOWN` / `HEALTH_FAIL` /
  `HEALTH_UNREACHABLE` since 10:35 IST and Stratex-Daemon `SERVICE_DOWN`
  10:35 IST (pre-existing, not caused by this probe).
- S2: timer enabled + active; Environment =
  `FLEET_WATCH_SERVICES=Sentinel:8008,Cortex:8009,VyralX:8010,VyralX-Daemon:-`
  (no `FLEET_ALERT_COMMAND` — Gap 1 open on S2 too). State file fresh
  (modified 10:59, `last_cycle` 10:59:35 IST).

### 7.2 The fault (first-hand)

- 11:06:04–11:06:09 IST: `sudo -n systemctl stop Memora.service` on S1 —
  `stop_rc=0`, `is-active` = inactive. Journal: sudo 11:06:04,
  `Memora.service: Deactivated successfully` 11:06:08.

### 7.3 The alert — FIRED (verbatim)

Next watcher cycle, 11:06:15 IST (~6s after the stop):

```
Nov 24 11:06:15 friday-universe-vnic python[3500307]: [CRITICAL] SERVICE_DOWN Memora: ActiveState=inactive SubState=dead; error=URLError: <urlopen error [Errno 111] Connection refused>
```

Cycle summary 11:06:21 IST: `[CYCLE 2026-11-24 11:06:21 IST] 3/8 healthy;
unhealthy: Memora, Stratex, Futuris, IntelX, Stratex-Daemon`. The state file
carried `Memora:SERVICE_DOWN` after this cycle. The alert is journal +
state-file only: no Telegram or other external delivery exists while Gap 1
is open (expected; see verdict).

### 7.4 Side observation — FRIDAY health depends on Memora

11:06:12 IST (3s after Memora stopped) the watcher logged FRIDAY
`HEALTH_UNREACHABLE`; FRIDAY recovered 11:11:08 IST, once Memora was back.
FRIDAY.service itself never restarted — active since 08:28:27 IST,
`NRestarts=0`. Consistent with FRIDAY's `/health` depending on Memora
(the memory fabric). Surfaced by this probe; not caused by the fault plan.

### 7.5 Recovery

- Memora restarted 11:08:59 IST (`ActiveEnterTimestamp`; MainPID 3503374,
  PPID 1, uvicorn `app.main:app` port 8002; journal `Starting FRIDAY
  Universe - Cognitive Memory Fabric...` 11:08:51, `Started...` 11:08:59).
- Watcher 11:11:08 IST: `[RECOVERED] Memora — service healthy again (active,
  /health 200); previous alert closed: SERVICE_DOWN at 2026-11-24 11:06:15 IST`.
- Cycle summary 11:11:10 IST: `4/8 healthy; unhealthy: Stratex, Futuris,
  IntelX, Stratex-Daemon` (pre-existing downs unchanged).
- Down time ~2m50s (11:06:09 → 11:08:59), inside the posted ~6-min bound.
- Memora confirmed active + `/health` 200s flowing at 11:14:25 and 11:14:54 IST.

### 7.6 Revert anomaly — the restorer was NOT me (honest record)

The restore at 11:08:51–11:08:59 was an explicit systemd start job by an
UNIDENTIFIED actor. It was not my planned revert:

- My verify+conditional-revert call (`sleep 320` + bridge `run_shell`) FAILED
  at the transport level — `NO CALL BODY (curl failed)`: the `tools/call`
  response was lost, so nothing from it executed before the recovery
  (recovery 11:11:08 predates the call's earliest possible execution
  ~11:11:30). Same bridge flakiness the coordinator watch flagged
  ("timed out on ~half my calls").
- My explicit revert call at 11:14:25 found Memora already active
  (`start_rc=0`, no-op on an active service).
- Excluded as the restorer: Fleet CD deploy (S1 HEAD still `3db55adf`,
  last pull 10:01:59 IST; the CD runs for the 11:02 merges completed success
  but S1 never pulled); systemd `Restart=` auto-restart (no `Scheduled
  restart job` line in the unit journal; `NRestarts=0` points to a fresh
  start job, not a restart).
- Open question for Muse: which actor issued the 11:08:51 start job. It is
  not a blocker for the verdict — the fault was real, the alert fired, the
  service was restored promptly — but the unidentified start deserves an
  answer (another worker's bridge call, or an S1-side automation not yet found).

### 7.7 Verdict per acceptance

ALERT FIRED. The OBS-008 alerting path works on a real fault: a real induced
`SERVICE_DOWN` produced the `[CRITICAL]` raise in the journal and the state
file within one watcher cycle, with the alert text filed verbatim above.
Delivery is journal/state-file ONLY — no Telegram or owner notification,
because Gap 1 (`FLEET_ALERT_COMMAND` unset on S1 and S2) is still open.
Gap 2 (HTML escaping) is CLOSED in code (TASK-OBS-010, section 2).
Production-verified: PARTIAL. The raise path is proven live; end-to-end
(owner notified) remains unproven until Muse wires Gap 1 — owed since OBS-008.

