# TASK-INT-058 — Fast-lane live proof run 7

**Task:** TASK-INT-058 (IntelX: fast-lane live proof run 7 — one real alert end-to-end)

**Claim:** hub #2045 comment 7211990747; branch `muse7/task-int-058-fast-lane-run-7`

**Verification:** 2026-11-27 ~12:28–12:31 IST, read-only bridge probes on the live hosts under standing clearance 7200564540. No config changed by this run, no restart by this run, no server move, kill switch untouched. Bridge `run_shell` was verified working on FRIDAY-Server and IntelX-Server (`hostname` probes succeeded at 12:28 IST).

## Outcome

**Wait state — no instant-class alert exists to trace, and INT-060's standing HTTP transport is merged but not deployed.** The acceptance alternative is satisfied: armed-state evidence and the exact wait state are filed below. No real instant alert has traversed end-to-end in run 7.

## INT-060 deploy state (checked first)

- PR #2076 is merged (merge `e4018092`): IntelX `GET /v1/watches/outbox?lane=main|instant` plus the FRIDAY drainer remote source (`INTELX_WATCH_OUTBOX_URL` / `INTELX_WATCH_API_KEY`).
- **IntelX-Server:** `IntelX.service` active (PID 46018, since 2026-11-27 05:13:15 UTC); `/healthz` 200. The new endpoint is **not live**: local probes of `/v1/watches/outbox?lane=main` and `?lane=instant` both returned HTTP 404 `{"detail":"Not Found"}`. Deployed IntelX code grep found no `v1/watches/outbox` route and no `read_outbox_envelopes`.
- **FRIDAY-Server:** `FRIDAY.service` active (PID 89534, since 2026-11-27 06:44:24 UTC). Deployed FRIDAY code contains the remote-source `INTELX_WATCH_OUTBOX_URL` lines, but the live process environment and `.env` both lack `INTELX_WATCH_OUTBOX_URL`, `INTELX_WATCH_API_KEY`, and `INTELX_WATCH_INSTANT_OUTBOX_URL` (presence checked by name only; no values read or printed). The gateway endpoint also returned HTTP 404 for both lanes while gateway `/healthz` returned 200. The drainer therefore still uses the local-file source.
- **Blocker:** deploy of the IntelX endpoint plus FRIDAY env wiring/restart. INT-060's evidence doc reserves that deploy to the coordinator after merge. WATCH208 §2 notes the post-merge deploy leg proceeds under standing clearance, but no explicit deploy assignment to Muse 7 for env wiring/restarts was found on hub #2045 through comment 7212032053. No deploy was attempted in this proof leg.

## Producer state (IntelX-Server, probed 2026-11-27 12:29 IST)

- `IntelX.service` active running; `/healthz` 200.
- Polls live every 30 min. Journal watch cycles at 05:13:29, 05:43:31, 06:13:34, and 06:43:36 UTC (10:43–12:13 IST) all reported `alerted=0` on both watches. Latest cycle (06:43:36 UTC): `ai_model_releases fetched=2368 alerted=0 dup=2368 below=0`; `india_tech_regulatory fetched=64 alerted=0 dup=62 below=2`.
- Outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: 3,782 bytes, mtime 2026-11-24T21:30:34Z; 4 envelopes, all `alert_class=digest`, scores `[4, 5, 3, 4]`, max score 5 — below the instant bar of 6.
- No `instant_outbox.jsonl` on the producer: no instant-class envelope has ever been produced.

## Consumer state (FRIDAY-Server, probed 2026-11-27 12:29 IST)

- `FRIDAY.service` active running. Watch state is enabled (kill switch OFF; watch on), untouched. No `INTELX_WATCH_OUTBOX_PATH` override in process env or `.env`.
- Drainer state `/opt/friday_universe/FRIDAY/state/proactive_intelx_watch.json` is live (mtime 2026-11-27T06:59:10Z): `baseline_done=true`, `instant_baseline_done=true`, `offset=6571`, `instant_offset=0`, `delivered_keys=7`, `held=0`, `alert_log=10`.
- Local consumer outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: 6,571 bytes, 7 lines, mtime 2026-11-27T05:04:41Z — the INT-060 manual handoff state. No `instant_outbox.jsonl` on the consumer either.
- Journal confirms the INT-060 drain receipt already filed (2026-11-27 05:05:35 UTC: `posted=3`, `duplicates=0`, `source_errors=[]`). No new IntelX drain/post lines appeared after the 06:44 UTC FRIDAY restart in the recent journal window; consumer offsets remain `offset=6571`, `delivered_keys=7`.

## End-to-end verdict

- No instant-class alert fired, so there is no run-7 alert trail to file. The producer is polling with `alerted=0`; the consumer is armed and current on the local outbox after INT-060's manual handoff.
- The standing producer→consumer transport is still not live: the endpoint returns 404 and FRIDAY has no remote-source env wiring. A future producer envelope still cannot reach the consumer automatically until the INT-060 deploy lands.
- Run 8 can produce an end-to-end proof only after (a) the INT-060 endpoint + env wiring deploy is completed and verified live, and (b) a real instant-class envelope fires (score at/above the instant bar) and is delivered by the drainer.

## Five states (TASK-INT-058)

- implemented: N/A (verification task; evidence doc only)
- tested: YES (armed-state + wait-state verified first-hand 2026-11-27 ~12:29 IST)
- merged: NO
- deployed: N/A
- production-verified: NO — no real instant alert traversed, and the standing HTTP transport is not deployed

## Five states (INT-060 transport, for context)

- implemented: YES
- tested: YES (CI + INT-060 live handoff receipt)
- merged: YES (PR #2076, merge `e4018092`)
- deployed: NO (endpoint 404; FRIDAY env wiring absent)
- production-verified: NO for the standing HTTP transport until deploy + live probe

— Muse 7
