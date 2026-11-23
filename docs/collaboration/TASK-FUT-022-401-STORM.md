# TASK-FUT-022 — Futuris 401 storm (consumer_id=futuris-cloud-v1)

Owner: Muse 10. Branch: muse10/task-fut-022-401-storm. Status: fixed live, work PR open for Muse merge.

## Symptom

Memora on Server 1 logged `GET /v1/events/cursor?consumer_id=futuris-cloud-v1` → HTTP 401
from 10.0.0.120 (Server 2) every ~15 s, continuously. 174 hits in the 45 minutes
before 16:07 IST on 2026-11-23. Futuris on Server 2 logged
`memora_event_consumer_retry error=RuntimeError` on the same 15 s cadence, so the
IntelX-notice inbox never drained.

## Diagnosis (live, 2026-11-23 ~16:06–16:15 IST)

- Poller: `Futuris/futuris/integrations/memora_event_consumer.py`, `POLL_INTERVAL_SECONDS = 15`,
  `CONSUMER_ID = "futuris-cloud-v1"`. It calls `memora_client.read_event_cursor("futuris", CONSUMER_ID)`
  every cycle via `Futuris/futuris/integrations/memora_cloud_fallback.py`.
- Server side: `Memora/apps/api/routers/v1_events.py` `GET /cursor` requires
  `Depends(authenticate_agent)`; `Memora/apps/api/dependencies.py` expects, for agent
  `futuris`, the env var `FUTURIS_API_KEY` (AGENT_API_KEY_ENV_VARS), compared with
  `hmac.compare_digest`. A mismatch is HTTP 401 `Invalid agent credentials`.
- Client side: the fallback client resolves its key as `FUTURIS_MEMORA_API_KEY` first,
  then `FUTURIS_API_KEY`. `Futuris/futuris/infra/config.py` `settings.MEMORA_API_KEY`
  uses the same order, so the write path (`_persist_notice_to_memora`, POST /v1/memories)
  was shadowed the same way.
- Key comparison by hash (values never printed or copied): the `FUTURIS_API_KEY` value in
  the Futuris env on Server 2 is identical to the `FUTURIS_API_KEY` value in the Memora
  env on Server 1. The `FUTURIS_MEMORA_API_KEY` value present only in the Futuris env
  matches neither — a stale leftover from the pre-TASK-MEM-005-R1 design, when a shared
  Memora key was in use. R1 dropped that design: Futuris authenticates with its own
  per-agent key.
- Root cause: the stale `FUTURIS_MEMORA_API_KEY` shadowed the valid `FUTURIS_API_KEY`
  on both the poll path and the notice-write path, so every cursor read was rejected.
  Not benign: the consumer retry loop burned a request every 15 s and no IntelX notice
  reached Futuris.

## Fix (applied live on Server 2, 2026-11-23 ~16:14 IST)

- Backed up `/opt/friday_universe/Futuris/.env` to `.env.bak-fut022-20261123` (server-local, untracked).
- Removed the single stale `FUTURIS_MEMORA_API_KEY` line from `Futuris/.env`; the
  `FUTURIS_API_KEY` line is untouched, so both client paths now fall back to the valid
  per-agent key. No code change, no key value created, copied, or rotated.
- Restarted `Futuris.service` on Server 2 (new MainPID 609831, active/running).
  Note: `oracle_restart_service` targets Server 1, where Futuris is masked — the restart
  was done with `systemctl restart Futuris.service` on Server 2.

## Verification (live, 2026-11-23 ~16:15–16:17 IST)

- Memora Server 1 journal, last 90 s after the restart: 0 `futuris-cloud-v1` 401s;
  cursor reads return HTTP 200 OK every ~15 s (16:16:04, 16:16:19, 16:16:34, 16:16:49 IST).
- Futuris Server 2 journal: first successful poll at 16:15:34 IST logged
  `memora_events_consumed count=41 consumer_id=futuris-cloud-v1` — the backlog drained.
  The retry warnings in the window are all from the old PID before the restart; the new
  PID logs none.
- 401 rate after the fix: 0/min (was ~4/min, one per 15 s poll). Futuris service healthy.

## Follow-ups (not done here)

- Consider dropping `FUTURIS_MEMORA_API_KEY` from the alias chains in
  `Futuris/futuris/integrations/memora_cloud_fallback.py` and
  `Futuris/futuris/infra/config.py` so a stale value can never shadow the per-agent key
  again (code change; needs a separate task/PR).
- The stale value itself is orphaned; no rotation was needed because it authenticates nowhere.
- Issue #35 cannot take a status comment: GitHub returns HTTP 403, comments disabled over
  the 2500-comment cap (verified 2026-11-23 ~15:16 IST at claim time). Status travels via
  this PR and the board only.

— Muse 10
