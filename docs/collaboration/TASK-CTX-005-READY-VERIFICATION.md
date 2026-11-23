# TASK-CTX-005 — G4 /ready verification: formal close

## 0. Task

Formally close the CTX-003 G4 /ready verification: re-verify live, first-hand,
that the /ready probe is deployed on Server 2, Cortex is running it, /ready
returns 200 READY, and the supervisor probes `ai_universe` HEALTHY via /ready
— then file the close evidence and the board record.

- Assigned to Muse 13 in coordinator watch 7092357321 (10:52 IST); nudge in
  watch 7092909496 (11:17–11:55 IST, over 60 min with no claim visible).
- Queue: CTX-005* → TASK-OBS-011* → TASK-VOI-030.
- Claim: issue #35 comment 7093053262, 2026-11-23 ~11:39 IST.
- Branch: `muse13/task-ctx-005-ready-verification` (base main 136533e5).
- Board record verified absent on main 136533e5 (board blob d81164af, 15,669
  lines) before creating it in the work PR. Coordinator-drafted (marked *).

## 1. Background: what G4 needed

CTX-003 G4: the running Cortex (PID 584499, since Nov 22 12:16:38 IST) ran the
old DNS-only probe — `ai_universe` UNCONFIGURED, samples 0 — while the new
HTTP probe sat on disk. G4 closes after a coordinator-cleared restart with a
post-restart supervisor query as evidence (CTX-003 doc §4). The /health
partial close was done 03:57 IST (PID 598506); the /ready verification stayed
open under this task (coordinator direction 7088433890).

Prior evidence: CTX-004 doc §5 (06:41 IST live proof) already recorded the
/ready state — S2 on main 491a63e9, Cortex restarted 05:25:17 IST (PID 599993),
/ready 200 READY, `ai_universe` HEALTHY via that probe. This task re-verifies
that state fresh and formally closes G4.

## 2. Live verification — 2026-11-23 ~11:40 IST (first-hand via bridge, read-only)

### 2.1 Deploy: S2 checkout

- Branch `main` @ `ff84c7ffba7c3ce58725a30f5eca6b17a9aa64d8`.
- `git log --oneline -3`: `ff84c7ff` (merge PR #1395, REL-067),
  `7dfaab6a` (merge PR #1445, VAL-013), `dff5cbba` (merge PR #1444,
  ORCH-013 follow-up).
- Ancestry verified two ways: `git merge-base --is-ancestor 491a63e9 HEAD`
  on S2 → true; GitHub compare `491a63e9...ff84c7ff` → ahead by 82,
  behind by 0, merge base 491a63e9. The CTX-004 code (ratio check) is in
  the checkout.
- Working tree: 12 untracked entries only, 0 tracked modifications
  (`VyralX/light_result_r1.txt`, `VyralX/light_result_r2.txt`,
  `bridge/extra_tools.py`, `bridge/server.py`,
  `bridge/test_bridge_recon.py`, `opt/`, `pro001_scratch/`,
  `tests/test_dispatch_bus_persistence.py`,
  `tests/test_task_router_persistence.py`, `tmp/`, `var/`, `venv312/`).
  The running code matches the checkout.
- `get_system_info`: S2 branch main commit ff84c7ff; both Oracle servers
  ONLINE.

### 2.2 On-disk probe code

`Cortex/apps/api/src/cortex_api/self_healing.py` — 3 `/ready` hits:

- Line 10: doc — `ai_universe` probe is `GET {base}/ready` on the
  Inference gateway.
- Line 66: performs `GET {base}/ready`, reports HEALTHY only on HTTP 200.
- Line 95: `response = await client.get(f"{url}/ready")`.

### 2.3 Running process

`Cortex.service`: `ActiveState=active`, `MainPID=602703`,
`ActiveEnterTimestamp=Mon 2026-11-23 09:04:39 IST`. No restart was
performed by this run; the running process (since 09:04:39 IST) already
runs the /ready code.

### 2.4 The probe, live in the logs (PID 602703)

Cortex log lines, first-hand:

- `11:37:38` `GET http://10.0.0.121:8001/ready "HTTP/1.1 200 OK"`
- `11:38:08`, `11:38:39`, `11:39:09`, `11:40:14`, `11:40:44`,
  `11:41:15`, `11:41:45` — same request, same 200 OK, ~30 s tick.
- `11:40:46` `GET /ready HTTP/1.1 200 OK` and `11:40:47`
  `GET /v1/friday/self_healing HTTP/1.1 200 OK` — this run's own
  verification queries, in the log.

The running process issues the /ready probe every supervisor tick and gets
200 OK. This is the proof the old DNS-only probe is gone from the live
path: the old probe produced UNCONFIGURED with samples 0; the live probe
produces counting successes and real failures (see §2.6).

### 2.5 Cortex /ready endpoint

`GET http://127.0.0.1:8009/ready` → HTTP 200:

```json
{"status": "READY", "service": "cortex",
 "evidence_class": "dependency_readiness",
 "observed_at": "2026-11-23T06:10:46.976919+00:00",
 "required_dependencies": ["database", "schema", "redis"],
 "degraded": ["ai_universe", "sentinel", "intelx", "futuris"],
 "dependencies": {"database": "UP", "schema": "UP", "redis": "UP",
  "ai_universe": "UNKNOWN: no live readiness probe configured",
  "sentinel": "UNKNOWN: no live readiness probe configured",
  "intelx": "UNKNOWN: no live readiness probe configured",
  "futuris": "UNKNOWN: no live readiness probe configured"}}
```

### 2.6 Supervisor state

`GET /v1/friday/self_healing`, observed `2026-11-23T06:10:47Z`:

- Background running, **cycles 307**, errors 0, skipped 0, last_error null.
- `last_unconfigured: []`, `last_unhealthy: []`.
- `last_probes`: database / schema / redis / agents HEALTHY;
  **ai_universe HEALTHY**, checked `06:10:44.947817Z`;
  ingestion / tools `healthy: null, reason: "no probe"` (by design).
- `ai_universe` subsystem: state CLOSED, samples 20,
  **total_successes 298, total_failures 9, failure_ratio 0.05**;
  signal rate 0.9707 over 307 samples.
- `ratio_check` live (CTX-004): threshold_cycles 10,
  delivery_gap_threshold 3, `unconfigured_streaks: {}`,
  `consecutive_failed_deliveries: 0`, `channel_broken: false`,
  `last_alert: null`.
- Escalations: 6 `ai_universe` entries 05:10–06:09 UTC
  ("3 repair attempts did not restore health"); delivery attempts 6,
  **delivered 1**, suppressed_duplicates 5; last attempt 06:09:44 UTC,
  duplicate suppressed within the dedupe window.

## 3. Caveats, stated plainly

- **S2 is behind GitHub main HEAD 136533e5.** It has not pulled the merges
  since ff84c7ff. Nothing G4 needs is in those merges; the evidence above
  does not depend on them.
- **`ai_universe` failed 9 times in the current window** (failure_ratio
  0.05) with 6 escalations 10:40–11:39 IST. The probe reports real
  failures, not silence; it is HEALTHY at verification time. A flaky
  Inference gateway is a live dependency problem, not a dead probe.
- **Cortex /ready's own dependency section lists ai_universe / sentinel /
  intelx / futuris as UNKNOWN** ("no live readiness probe configured").
  That is the /ready endpoint's dependency view, distinct from the
  supervisor's probes (which do probe ai_universe via /ready and report
  HEALTHY). Recorded as observed, same as CTX-004 §5; reconciling the two
  views is follow-up work, not part of this close.
- **No restart was performed by this run.** The G4 close criterion (merge +
  coordinator-cleared restart + post-restart supervisor query) is met by
  the restarts at 03:57, 05:25 and 09:04:39 IST and the supervisor queries
  at 06:41 IST (CTX-004 §5) and 11:40 IST (this run).

## 4. Verdict

**G4 CLOSED.** The /ready verification has its live evidence twice over:
the CTX-004 §5 proof (06:41 IST) and this run's fresh re-verification
(11:40 IST) — on-disk /ready probe code, running process issuing it every
~30 s with 200 OK, supervisor reporting `ai_universe` HEALTHY with
counting samples, Cortex /ready 200 READY, escalation channel delivering
with dedupe working.

## Files

- `docs/collaboration/TASK-CTX-005-READY-VERIFICATION.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-CTX-005 record (created in
  the work PR).
