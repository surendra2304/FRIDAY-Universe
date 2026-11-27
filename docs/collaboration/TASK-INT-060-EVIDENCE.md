# TASK-INT-060 — Handoff fix run 2: producer envelopes reach the consumer

**Task:** TASK-INT-060 (IntelX: INT-057 handoff fix run 2 — producer envelopes reach the consumer)
**Worker:** Muse 7 · **Branch:** `muse7/task-int-060-handoff-fix-run-2`
**Grant:** WATCH197 §3 (hub #2045 comment 7208403062) under standing clearance 7200564540
**Claim:** hub #2045 comment 7209403589

## Root cause (traced first-hand, 2026-11-27)

The handoff assumed a shared filesystem. The producer (`IntelX/intelx/watches/engine.py`)
appends envelopes to its local `data/watches/outbox.jsonl`; the consumer
(`FRIDAY/src/friday/proactive/intelx_watch.py`) tails a **local sibling path**
(`INTELX_WATCH_OUTBOX_PATH` or the sibling IntelX checkout default). The fleet
split (IntelX on IntelX-Server, FRIDAY on FRIDAY-Server) removed the shared
filesystem, and no transport replaced it:

- Producer outbox (IntelX-Server, `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`,
  3,782 bytes): 4 envelopes — `f7f7b3f3…` (2026-11-20, already delivered),
  `cc3ea0fa…` (2026-11-23 16:33 UTC), `72b58fb0…` (2026-11-24 14:30 UTC),
  `8ca3ca25…` (2026-11-24 21:30 UTC). No `instant_outbox.jsonl` (no instant-class
  envelope has ever fired).
- Consumer outbox (FRIDAY-Server, same path): 3,644 bytes, frozen since
  2026-11-20 13:46 UTC; drainer state `offset=3644` (whole file consumed),
  `delivered_keys` = the 4 pre-split envelopes, `alert_log` last entry
  2026-11-20 19:16 IST. The three 2026-11-23/24 producer envelopes were
  absent — fired, never delivered, nothing recorded the loss.
- TASK-INT-040's SSH shipper (`intelx/watches/outbox_shipper.py`, repo-side
  only) was never installed on IntelX-Server (no module, timer, state, or log
  present), and its transport cannot work across the current fleet split:
  `ssh ubuntu@172.26.12.144` from IntelX-Server returns **No route to host**.
  FRIDAY-Server reaches IntelX over the gateway instead
  (`INTELX_URL=https://friday-universe.duckdns.org/intelx`, `/healthz` 200).

## Live handoff run (2026-11-27, consumer receipt)

One live handoff run under clearance 7200564540: the three missing producer
envelopes were appended to the consumer outbox (append-only; server-side
dedupe-key check before append; kill switch untouched; no config change):

| | Before | After |
|---|---|---|
| Consumer outbox size / sha256 | 3,644 B / `75161e4f…` | 6,571 B / `f9ac90ad…` |
| Drainer offset | 3,644 | 6,571 |
| delivered_keys | 4 | 7 |
| alert_log entries | 7 | 10 |
| held / malformed_total | 0 / 0 | 0 / 0 |

Consumer receipt (drainer cycle 2026-11-27 10:35:35 IST, journal-verified
`posted=3, duplicates=0, source_errors=[]`):

- `cc3ea0fa…` `intelx.watch:india_tech_regulatory:f0b33be871050a14` — posted
- `72b58fb0…` `intelx.watch:india_tech_regulatory:9eb418492e182ffd` — posted
- `8ca3ca25…` `intelx.watch:ai_model_releases:ac2f786b30f6d457` — posted

All three 2026-11-23/24 producer envelopes reached the consumer and were
delivered exactly once. Acceptance leg 1 (envelopes reach the consumer) and
leg 2 (one live handoff run + consumer receipt) are met.

## Standing fix (this PR)

HTTP pull replaces the dead file/SSH assumptions — no new credential beyond
the existing Friday API-key auth, no change to envelope semantics:

- **Producer:** `GET /v1/watches/outbox?lane=main|instant`
  (`IntelX/intelx/api/router.py`, behind `Depends(get_friday_api_key)`)
  returns `{lane, size, envelopes, malformed}` via
  `intelx.watches.engine.read_outbox_envelopes` (missing file = empty
  snapshot, the normal watches-not-enabled state).
- **Consumer:** when `INTELX_WATCH_OUTBOX_URL` is set, the drainer pulls
  envelopes over HTTP (`INTELX_WATCH_API_KEY` sent as `X-API-Key`; instant
  lane via `INTELX_WATCH_INSTANT_OUTBOX_URL` or `lane=instant`). Validation,
  silent baseline, quiet-hours and dedupe semantics are unchanged — dedupe
  rests on the persisted `delivered_keys`, the same guard that covers a
  rebuilt local outbox. Fetch failures are source errors, never a wedge.
  Unset URL = today's local-file behaviour, byte-identical.
- **Tests:** FRIDAY remote-source tests (baseline, exactly-once across
  refetches, fetch failure, malformed rows) in
  `FRIDAY/tests/test_pro002_intelx_watch.py`; producer snapshot tests in
  `IntelX/tests/test_int040_outbox_shipper.py`.

## Deploy steps still owed (coordinator, after merge)

1. Deploy IntelX (new endpoint) and FRIDAY (remote drainer source).
2. Set on FRIDAY-Server: `INTELX_WATCH_OUTBOX_URL=https://friday-universe.duckdns.org/intelx/v1/watches/outbox`
   and `INTELX_WATCH_API_KEY` (FRIDAY's existing IntelX API key; value stays
   server-side). Restart FRIDAY.
3. INT-058 (fast-lane run 7) is unblocked once the endpoint is live.

## Five states

- implemented: YES (HTTP handoff transport, both ends)
- tested: YES (unit tests in CI; live handoff run receipt above)
- merged: NO (this PR)
- deployed: NO (endpoint + env wiring deploy after merge)
- production-verified: YES for the live handoff run (consumer receipt);
  the standing HTTP transport is production-verified only after deploy
