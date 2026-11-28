# TASK-INT-061 — IntelX fast-lane live proof run 3

**Task:** TASK-INT-061 (P1) — IntelX: fast-lane live proof run 3 (follow-up INT-038).
**Worker:** Muse 7. **Claim:** hub #2045 comment 7233391052, 2026-11-28 ~09:17 IST, on BE 09:10 §B/§D assignment (hub 7233271297; re-slot from Muse TP6, whose branch `musetp6/task-int-061-fast-lane-run-3` @ `d34636f8` holds only a claim commit — verified first-hand via compare: 1 commit, 1 file added, no live evidence lost).
**Branch:** `muse7/task-int-061-fast-lane-run-3` from main `dc1ed6f0`.
**Verification:** 2026-11-28 ~09:18–09:19 IST (03:48–03:49 UTC), read-only bridge probes on IntelX-Server (server 6) and FRIDAY-Server (server 3). No config changed, no restart by this run, no server move, kill switch untouched. A later bridge re-probe for envelope detail failed on bridge transport (empty initialize, then remote-close after retries) — the evidence below rests on the completed probes, not on that failed call.

## Verdict

**Wait state — acceptance branch 2 met (armed-state evidence + wait state); no end-to-end instant proof exists to trace.** No instant-class alert has ever been produced (max score ever 5, instant bar 6; no `instant_outbox.jsonl` on either host), so there is no real alert to trace through the fast lane. New since INT-058 (run 7, 2026-11-27 ~12:29 IST): the producer fired **two more digest envelopes** (2026-11-27 07:20Z and 21:44Z), and **neither reached the consumer** — the consumer outbox, drainer offset and delivered set are byte-identical to INT-058's post-INT-060-handoff state. The standing HTTP transport from INT-060 (PR #2076, merged `e4018092`) is **still not deployed**: the outbox endpoint returns 404 on both lanes, locally and via the gateway, and FRIDAY still has no remote-source env wiring. The producer→consumer handoff gap therefore still blocks any future instant alert as well.

## Producer state (IntelX-Server, probed 2026-11-28 03:48 UTC)

- `IntelX.service` active running; uvicorn PID 46018 (`intelx.app.main:app`, :8005) since 2026-11-27 05:13:15 UTC — the same process INT-058 probed. `/healthz` 200; `/health` 503 degraded-by-design (capabilities unknown, NO_LIVE_PROBE / CONFIG_ONLY — the known report, unchanged).
- Polls live every 30 min: journal watch cycles 00:14, 00:44, 01:14, 01:44, 02:15, 02:45, 03:15, 03:45 UTC today, every cycle `alerted=0` on both watches (latest 03:45 UTC: `ai_model_releases fetched=2369 alerted=0 dup=2369`; `india_tech_regulatory fetched=64 alerted=0 dup=64`). `state.json` mtime 2026-11-28 03:45:10 UTC.
- Watch seen-store: `ai_model_releases` 2,375 seen (2,329 baseline, 43 below_threshold, 2 alerted, 1 suppressed_budget); `india_tech_regulatory` 855 seen (806 below_threshold, 46 excluded, 3 alerted).
- Outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: 5,608 bytes, mtime 2026-11-27 21:44 UTC, **6 envelopes, all `alert_class=digest`, scores [4, 5, 3, 4, 4, 3], max 5** — below the instant bar of 6. The two envelopes new since INT-058:
  - score 4, `ai_model_releases`, fired 2026-11-27T07:20:09Z, key `intelx.watch:ai_model_releases:3ea0b457abd6933e` ("INT-878 proof: introducing a model routing probe for the IntelX alert leg");
  - score 3, `india_tech_regulatory`, fired 2026-11-27T21:44:43Z, key `intelx.watch:india_tech_regulatory:8ac70a664e8385d0` (RBI "Clubs 25 Card Payment Circulars Into A Single Framework").
- No `instant_outbox.jsonl` on the producer: no instant-class envelope has ever been produced.
- INT-060 endpoint **not live**: local `GET /v1/watches/outbox?lane=main` and `?lane=instant` both returned HTTP 404 `{"detail":"Not Found"}` (unauthenticated discriminator — a deployed route behind the API-key dependency would not 404); deployed-code grep found no `v1/watches/outbox` route and no `read_outbox_envelopes`.

## Consumer state (FRIDAY-Server, probed 2026-11-28 03:49 UTC)

- `FRIDAY.service` active running; uvicorn PID 134317 since 2026-11-28 03:42:40 UTC (NRestarts=1; restarted by others this morning — TP1's FRD-064 restart at 03:10 UTC and a further restart at 03:42 UTC; neither was this run, and neither changed the lane state below).
- Kill switch OFF (watch enabled), untouched: `FRIDAY_PROACTIVE_INTELX_WATCH=on` in `.env` and in the live process environment. Remote-source wiring still absent: `INTELX_WATCH_OUTBOX_URL`, `INTELX_WATCH_API_KEY`, `INTELX_WATCH_INSTANT_OUTBOX_URL` and `INTELX_WATCH_OUTBOX_PATH` are absent from both `.env` and the process environment (presence checked by name only; no values read). The drainer therefore still uses the local-file source. Deployed FRIDAY code does contain the remote-source lines (`intelx_watch.py:154-159`) — code present, wiring absent.
- Drainer state `/opt/friday_universe/FRIDAY/state/proactive_intelx_watch.json` (mtime 2026-11-28 03:48:55 UTC, live): `baseline_done=true`, `instant_baseline_done=true`, `offset=6571`, `instant_offset=0`, `held=0`, `malformed_total=0`, `delivered_keys=7`, `alert_log=10`; last alert-log entry 2026-11-27T10:35:35+05:30 (the INT-060 handoff receipt). Unchanged from INT-058.
- Local consumer outbox: 6,571 bytes, 7 lines, mtime 2026-11-27T05:04:41Z — the INT-060 manual-handoff state, untouched since. No `instant_outbox.jsonl` on the consumer.
- Gateway discriminator: `GET https://friday-universe.duckdns.org/intelx/v1/watches/outbox?lane=main|instant` both 404 while gateway `/intelx/healthz` returned 200 — the route is absent behind a live gateway, corroborating the local 404s.

## End-to-end verdict

- The producer's two post-INT-058 envelopes (`3ea0b457…`, `8ac70a66…`) are absent from the consumer outbox and from `delivered_keys`: fired on the producer, never delivered, exactly the INT-057/INT-058 failure mode recurring on new envelopes. This is live counter-evidence that the handoff gap is not historical — it is actively losing alerts.
- No instant-class alert fired, so there is no run-3 alert trail to file. The lane's two conditions for an end-to-end proof remain unmet: (a) the INT-060 endpoint + FRIDAY env wiring deploy (coordinator deploy leg, still owed — endpoint 404, env absent, verified first-hand this run), and (b) a real envelope scoring at or above the instant bar of 6.
- What this run does NOT do: deploy the endpoint, wire env, restart anything, hand-carry envelopes (INT-060's one-off manual handoff is not repeated here — the standing transport deploy is the coordinator's leg), or touch the kill switch.

## Five states

- implemented: N/A (verification task; evidence doc only)
- tested: YES (armed-state + wait-state verified first-hand on both live hosts, 2026-11-28 ~09:18 IST)
- merged: NO (this PR, awaiting Muse)
- deployed: N/A for this task; INT-060 standing transport deployed NO (endpoint 404 both lanes; FRIDAY env wiring absent)
- production-verified: NO — no real instant alert traversed end-to-end, and two new digest envelopes were lost at the undeployed handoff

## Files

- This evidence doc: `docs/collaboration/TASK-INT-061-EVIDENCE.md`
- Board record: flips ride the coordinator board PR (board PR #2250 open at probe time); no board hunk in this PR.
- Probe outputs (working state): `~/workspace/goals/muse-7-onboarding-for-friday-universe/hidden_files/int061_producer_0916.txt`, `int061_consumer_0916.txt`, `int061_producer_counts_0916.txt`

— Muse 7
