# TASK-INT-043 — Scope: five shipped-but-unconsumed IntelX capabilities

**Owner:** Muse 14. **Claim:** hub #1483 comment 7150251910 (~07:32 IST 2026-11-25).
**Branch:** `muse14/task-int-043`. **Base:** main `f73bddd7` (rebased 2026-11-25 ~12:05 IST).

## Finding: the wiring exists in code; production activation is the gap

All five capabilities have a production caller wired in the repo, with
hermetic tests proving the paths (`IntelX/tests/test_ig_intelx_wiring_feeds.py`,
`IntelX/tests/test_ig_intelx_wiring_consumers.py`). What is missing is
**activation in production** and **one evidenced end-to-end production use**.

| Capability | Production caller (in code) | Gap |
|---|---|---|
| HeadlineWatch | Lifespan `HeadlineWatchHook` (scheduler) + `feed_service.deliver_headlines_to_stratex` (Stratex delivery) + `/api/v1/feeds/headlines` routes | `ENABLE_HEADLINE_WATCH` and `HEADLINE_STRATEX_DELIVERY` both default **False** — the hook never starts and delivery is never attached unless the env vars are set on IntelX-Server |
| SocialLinkReader | `retriever.py::_social_ingest_plan` calls `SocialLinkReader().read()` for social URLs (no setting gates it) + `/api/v1/osint/social-link` route | None in code — already consumed; needs one evidenced end-to-end production use |
| AiRadar | Lifespan `AiRadarHook` (scheduler) + `/api/v1/feeds/ai-radar` route (the referencing surface) | `ENABLE_AI_RADAR` defaults **False** — the hook never starts unless the env var is set on IntelX-Server |
| TrackingService | `/api/v1/tracking/snapshot` route calls the real `TrackingService`; 4 live layers — flight (OpenSky), satellite, ship (Digitraffic), event (USGS) — with per-layer isolation | None in code — already consumed; needs one evidenced end-to-end production use |
| FootprintAudit | `/api/v1/osint/footprint-audit` route calls the real `FootprintAudit` | None in code — already consumed; needs one evidenced end-to-end production use |

Routes are mounted: `v1_router` includes both `osint_tools_router` and
`feeds_router`, and `root_api_router` includes `v1_router`, so all five
routes are live in the app. The settings defaults above are the only
reason HeadlineWatch / AiRadar / Stratex delivery do not run.

## Repo-side work (this task)

1. Run the two wiring test files and record the result (the paths the
   acceptance names, proved in tests). **Done first-hand 08:09 IST
   2026-11-25:** `pytest -q tests/test_ig_intelx_wiring_feeds.py
   tests/test_ig_intelx_wiring_consumers.py` — **15 passed in 117.37s**
   (venv `/tmp/muse14-int043/.venv`, from `IntelX/`; required
   `requirements.txt` + `aiosqlite`, which the test DB session needs).
2. Produce the production activation checklist: the exact env vars that
   turn the five on (`ENABLE_HEADLINE_WATCH`, `HEADLINE_STRATEX_DELIVERY`,
   `HEADLINE_STRATEX_MIN_SCORE` (default 35), `ENABLE_AI_RADAR`) and what
   each enables, so the live leg is a single deliberate step.
3. File the live leg as blocked-with-reason if the stop order still
   stands: enabling the hooks/delivery on IntelX-Server means changing
   the live server's env and restarting the service, which is a server
   move under the owner stop order.

## Five states

- Implemented: PARTIAL (the callers exist in code; activation is the
  outstanding part).
- Tested: YES — wiring suites re-run first-hand: **15/15 passed in
  117.37s** (08:09 IST 2026-11-25).
- Merged: NO (this work PR, when filed).
- Deployed: NO (IntelX lives on IntelX-Server; the hooks/delivery are
  off by default).
- Production-verified: NO (one end-to-end production use per capability
  is the live leg; gated by the owner stop order).
