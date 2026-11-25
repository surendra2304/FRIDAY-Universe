# TASK-INT-043 — Checkpoint 1: production activation checklist

**Owner:** Muse 14. **Branch:** `muse14/task-int-043-activation`.
**Base:** main `c4b64284` (2026-11-25 ~18:05 IST). **Claim PR #1786 merged** (scope
only); this checkpoint is the repo-side activation leg. **No PR yet** — per the
owner order, one work PR carries finished work + live evidence; the live leg
is blocked (see below), so this checkpoint stands on the branch.

## Verified first-hand on main `c4b64284`

Activation points — the only reason HeadlineWatch / AiRadar / Stratex delivery
do not run in production is the settings defaults:

| Setting | Default | Location |
|---|---|---|
| `ENABLE_HEADLINE_WATCH` | `False` | `IntelX/intelx/core/settings.py:418` |
| `HEADLINE_STRATEX_DELIVERY` | `False` | `IntelX/intelx/core/settings.py:426` |
| `HEADLINE_STRATEX_MIN_SCORE` | `35` | `IntelX/intelx/core/settings.py:430` |
| `ENABLE_AI_RADAR` | `False` | `IntelX/intelx/core/settings.py:434` |
| `HEADLINE_WATCH_INTERVAL_S` | `60.0` | `IntelX/intelx/core/settings.py:420` |
| `AI_RADAR_INTERVAL_S` | `900.0` | `IntelX/intelx/core/settings.py:438` |

Lifespan gates (`IntelX/intelx/app/lifespan.py`): `headline_hook.start()` only
if `ENABLE_HEADLINE_WATCH` (:284); `ai_radar_hook.start()` only if
`ENABLE_AI_RADAR` (:288). Hooks: `HeadlineWatchHook` (:105), `AiRadarHook`
(:145), singletons :183–184.

Routes, all mounted (`IntelX/intelx/api/v1/__init__.py`: `v1_router` includes
`osint_tools_router` :24 and `feeds_router` :34):

- `GET /api/v1/feeds/headlines`, `POST /api/v1/feeds/headlines/poll`,
  `GET /api/v1/feeds/ai-radar`, `POST /api/v1/feeds/ai-radar/poll`
  (`intelx/api/v1/feeds.py`)
- `GET /api/v1/tracking/snapshot`, `POST /api/v1/osint/footprint-audit`,
  `GET /api/v1/osint/social-link` (`intelx/api/v1/osint_tools.py`)

Ungated callers (no env var gates them — already consumed, only the evidenced
use is owed):

- `SocialLinkReader().read()` — `intelx/agents/retriever.py:140` and
  `intelx/api/v1/osint_tools.py:106`
- `TrackingService().snapshot()` — `intelx/api/v1/osint_tools.py:58`
- `FootprintAudit().run()` — `intelx/api/v1/osint_tools.py:84`
- `deliver_headlines_to_stratex()` — `intelx/ingestion/feed_service.py:64`,
  attached only when `HEADLINE_STRATEX_DELIVERY`
  (`feed_service.py:46–51`)

## Wiring tests re-run first-hand on current main

`pytest -q tests/test_ig_intelx_wiring_feeds.py
tests/test_ig_intelx_wiring_consumers.py` — **17 passed in 137.87s**
(venv `/tmp/muse14-int043b/.venv`, from `IntelX/`; `requirements.txt` +
`aiosqlite` + `pytest` + `pytest-asyncio`). Up from 15/15 at 08:09 IST on main
`f73bddd7` — two tests added by intervening merges; no failures.

## Production activation checklist (the single deliberate live step)

When the owner stop order lifts, on IntelX-Server only:

1. Set `ENABLE_HEADLINE_WATCH=true` — headline sweeps every 60 s.
2. Set `HEADLINE_STRATEX_DELIVERY=true` (keep `HEADLINE_STRATEX_MIN_SCORE=35`
   unless directed otherwise) — headlines at/above the score are forwarded
   via the IntelX signal webhook to Stratex; each delivery also publishes a
   Memora research notice.
3. Set `ENABLE_AI_RADAR=true` — AI-radar sweeps every 900 s.
4. Restart the IntelX service (systemd) so the lifespan hooks start.
5. Verify live: `GET /api/v1/feeds/headlines` and `/api/v1/feeds/ai-radar`
   return fresh data; then one evidenced end-to-end production use per
   capability — SocialLinkReader, TrackingService and FootprintAudit need no
   env change, only a direct route call with recorded evidence.

## Live leg — BLOCKED with reason

- Owner stop order (~16:42 IST 2026-11-24, "Don't move anything now") still
  in force per WATCH096 and WATCH098 — no lift seen. Enabling the hooks /
  delivery means changing the live server's env and restarting the service:
  a server move. **No server move taken; no env changed; nothing deployed.**
- Fleet CD is also broken (CD run 45597748463: both deploy jobs failed —
  S1 dirty checkout, S2 `.git/objects` permissions); a deploy would need the
  CD repair route + owner word in any case.

## Five states

- Implemented: PARTIAL (callers exist in code and are tested; activation env
  still off by default).
- Tested: YES — wiring suites re-run first-hand on current main: **17/17
  passed in 137.87s**.
- Merged: YES (claim/scope PR #1786 only — this activation checkpoint is on
  the branch, no work PR yet).
- Deployed: NO (IntelX lives on IntelX-Server; the hooks/delivery are off).
- Production-verified: NO (one evidenced end-to-end production use per
  capability is the live leg; gated by the stop order).

## Queue

- Head: TASK-INT-043 (this leg).
- Queue pos 2: TASK-INT-046 (IntelX: Telegram topic-search source discovery
  for the standing watches) — assigned by the coordinator in WATCH098 (hub
  #1483 comment 7161941236); accepted this run. Board on main still reads
  AVAILABLE / owner null — the flip rides in the coordinator's board PR
  #1833. Pos 3 top-up owed by the coordinator next run.
