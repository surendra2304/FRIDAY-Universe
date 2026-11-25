# TASK-FUT-030 — Futuris-side economic-calendar module for outlook generation

- Task: TASK-FUT-030 (P2, owner muse_4 — re-slot from muse_1; see §6) — Futuris outlook generation consumes
  the economic-calendar feed directly (the feed TASK-IG2-STR-11 built
  Stratex-primary), evidenced in one outlook.
- Claim: hub #1483 comment 7150603395, 2026-11-25 ~07:50 IST, on coordinator
  watch069 (7150299573).
- Re-slot claim: hub #1483 comment 7153341361 by Muse 4, 2026-11-25 ~10:30 IST,
  pool-head re-slot per coordinator watch076 (7152691227).
- Branch: `muse4/task-fut-030-econ-calendar-outlook` from main `55027430`
  (replacement for `muse1/task-fut-030-econ-calendar-outlook`, PR #1766
  superseded — Muse 1 to close #1766 when this replacement PR opens).
  Board flip rides in the work PR. Never merge own PR — merge is Muse's.

## 1. What was built

- New `Futuris/futuris/features/calendar_context.py` — the Futuris-side
  consumer of the IG2-STR-11 feed, mirroring the `event_context.py`
  (TASK-IG-FUT-02) discipline:
  - The feed is consumed **directly**: its own module
    (`Stratex/research/economic_calendar.py`) is loaded by file path and
    its own `EconomicCalendar` class, classification, parsers and store do
    the work. Nothing about the feed is re-implemented. (`Stratex/` has no
    `__init__.py`, so the module cannot be imported as a package; the
    loader walks up from the Futuris package to the repo root, which works
    in the monorepo and in the fleet layout where Futuris and Stratex sit
    as siblings under `/opt/friday_universe`.)
  - `CalendarFeed` wraps the feed's class; the store defaults to next to
    the feed module (`Stratex/research/economic_calendar.jsonl`) and is
    refreshed through the feed's own `refresh()` only when stale (missing
    or older than 24h, mtime-gated). A failed refresh keeps serving the
    last stored events, flagged via `last_refresh_ok`.
  - The feed's default transport is `requests` (a Stratex dependency
    Futuris does not carry — Futuris is httpx throughout), so the module
    supplies an httpx transport through the feed's own injectable
    `fetch_json` hook. Parsing, classification, storage and queries stay
    the feed's own code.
  - `CalendarContext` statuses: `available` / `none_upcoming` /
    `source_unavailable` / `not_requested` — stated, never filled in.
    Headline = soonest high-impact event. Explanatory only: moves no
    forecast number, names no event the feed did not publish.
- Wired into `Futuris/futuris/api/routers/market.py`
  (`_generate_market_prediction`, the outlook path): new
  `MarketForecastRequest.include_calendar` (default true), new
  `calendar_context` block on `MarketForecastResponse`, headline folded
  into the rationale as
  `Calendar [macro/high]: <name> (<date> <time>, Nasdaq economic calendar).`
  Refresh runs via `asyncio.to_thread` so the sync Nasdaq calls never
  block the event loop. `calendar_feed` is injectable for tests.
- Settings (`Futuris/futuris/infra/config.py`): `ECON_CALENDAR_MODULE_PATH`,
  `ECON_CALENDAR_STORE_PATH`, `ECON_CALENDAR_REFRESH_MAX_AGE_HOURS` (24.0)
  — all optional overrides.

## 2. Verification (this run, first-hand)

- New tests, all green (venv from `Futuris/requirements.txt` + pytest +
  pytest-asyncio + aiosqlite; dummy Oracle `DATABASE_URL`; repo-root
  `PYTHONPATH`, same shape as CI tier-1):
  - `Futuris/tests/test_fut030_calendar_context.py` — 14 tests: loader
    resolves the real feed module; default transport is httpx; refresh /
    upcoming / stale-gate with a fake transport; all four context
    statuses; headline selection; headline formatting. No network.
    (Count correction, Muse 4 re-run: the file holds 14 tests, not 13 —
    the 22-test total below was already right: 14 + 4 + 4.)
  - `Futuris/tests/api/test_market_calendar_context.py` — 4 router-level
    tests mirroring `test_market_event_context.py`: available -> block +
    rationale names the release; feed missing -> `source_unavailable`;
    no high-impact release -> `none_upcoming`; not requested ->
    `not_requested`.
  - `Futuris/tests/api/test_market_event_context.py` — 4 tests re-run,
    still green (no regression in the IntelX event path).
  - Total: **22 passed, 0 failed.**
- `python -m py_compile` on all touched files: OK.
- Registry validator `scripts/validate_collaboration.py` on the edited
  tree: valid (975 tasks, 5 pre-existing file conflicts).
- Note found during evidence: the sandbox `NO_PROXY` list contains
  bracketed IPv6 literals (`[::1]` etc.) that break httpx's proxy-URL
  parsing (`Invalid port: ':1]'`). With a clean `NO_PROXY` the httpx
  transport works through the sandbox proxy (Nasdaq 200, 39 rows). The
  fleet has no such proxy, so this is a sandbox-only quirk; the refresh
  failure mode is safe anywhere (serve stored data, `last_refresh_ok`
  false).

## 3. Evidence: one outlook (live feed, real release)

Probe: `~/workspace/fut-030/evidence_probe.py`, run 2026-11-25 ~08:17 IST
(02:47 UTC). Store: `~/workspace/fut-030/evidence/economic_calendar.jsonl`;
full outlook JSON: `~/workspace/fut-030/evidence/outlook.json`.

- **Live refresh (real Nasdaq endpoints, feed's own `refresh()`):**
  `refresh_attempted=True`, `last_refresh_ok=True`, **453 events stored**,
  **78 high-impact** in the next 7 days. A second run minutes later
  correctly skipped the refresh (`refresh_attempted=False` — store fresh,
  mtime gate working).
- **One real outlook** (BTCUSDT, generated 2026-11-25T02:47:40Z, branch
  code, real calendar feed; telemetry via the repo's fake-telemetry
  harness and IntelX off — the live Stratex telemetry endpoint is not
  reachable from this VM, gateway curl returned 000; `forecast_repo=None`
  so nothing was persisted):
  - `calendar_context.status: available`, 78 events.
  - Headline: **CB Consumer Confidence — macro/high, 2026-11-25**
    (US, forecast 92.4, previous 91.9, actual 103.3 — the feed's own
    record, verbatim).
  - Rationale: *"BTCUSDT trading in consolidated regime with bounded
    drawdown risk. Calendar [macro/high]: CB Consumer Confidence
    (2026-11-25, Nasdaq economic calendar)."*
  - Regime RANGING / SIDEWAYS, vol_prob 0.35, dd_prob 0.17, confidence
    0.0 (uncalibrated — no resolved market forecasts yet, as before).

## 4. What is NOT claimed

- Implemented YES (code + tests, this PR) / tested YES (22 tests green,
  live refresh + outlook above) / merged NO (PR open, awaiting Muse) /
  deployed NO / production-verified NO.
- The live leg — a production outlook from the deployed Futuris service
  showing `calendar_context` — needs merge + fleet CD + Muse's hub
  clearance, and is not claimed here. The store the deployed service
  will read is the one next to the feed module; the first post-deploy
  outlook refreshes it through the feed's own `refresh()`.

## 5. Files

- `Futuris/futuris/features/calendar_context.py` (new, 300 lines)
- `Futuris/futuris/api/routers/market.py` (wiring: request flag, response
  block, rationale fold, injectable feed)
- `Futuris/futuris/infra/config.py` (3 new optional settings)
- `Futuris/tests/test_fut030_calendar_context.py` (new, 14 tests)
- `Futuris/tests/api/test_market_calendar_context.py` (new, 4 tests)
- `.github/workflows/owner-workflows.yml` (Muse 4: both new test files added
  to the Futuris contracts step — the CI-list fix; see §6)
- `docs/collaboration/TASK-FUT-030-ECON-CALENDAR-OUTLOOK.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (FUT-030 flip + STR-081 MERGED flip)

## 6. Re-slot / replacement PR (Muse 4, 2026-11-25 ~10:30–10:50 IST)

- Watch076 (7152691227) re-slotted FUT-030 to the pool head: PR #1766 stalled
  (head 4943a42c, CI-list fix never pushed, no PR activity since 08:30 IST).
  Muse 4 claimed it from the pool (hub #1483 comment 7153341361, same post
  as the STR-081 completion-with-evidence) after verifying AVAILABLE /
  owner-null first-hand on main 55027430.
- Cherry-picked Muse 1's 2 commits verbatim onto fresh branch
  `muse4/task-fut-030-econ-calendar-outlook` from main 55027430:
  `d745198b` (implementation) + `4943a42c` (board pr stamp #1766) — both
  applied cleanly, including the board auto-merge. A follow-up commit
  re-points the board record to muse_4 (M1's #1766 stamp superseded).
- CI-list fix (this run): both new test files added to the Futuris
  health-capability contracts step in `.github/workflows/owner-workflows.yml`
  — `Futuris/tests/test_fut030_calendar_context.py` and
  `Futuris/tests/api/test_market_calendar_context.py`. This is the fix the
  re-slot demanded; without it CI never ran the new tests.
- Re-run (this run, first-hand; venv from `Futuris/requirements.txt` +
  pytest + pytest-asyncio + aiosqlite; dummy Oracle `DATABASE_URL`;
  repo-root `PYTHONPATH`, same shape as CI tier-1; `NO_PROXY` sanitised
  to `localhost,127.0.0.1` — the sandbox value carries bracketed IPv6
  literals that break httpx proxy parsing, see §2 note):
  - CI-listed set (all 5 files): **51 passed, 0 failed** — the 3
    pre-existing contracts files plus the 2 new files (14 + 4 = 18 new
    tests now actually collected by the CI step).
  - `Futuris/tests/api/test_market_event_context.py` re-run: 4 passed
    (no regression in the IntelX event path).
  - `python -m py_compile` on all touched files: OK.
  - Registry validator `scripts/validate_collaboration.py` on the edited
    tree: valid (976 tasks, 5 pre-existing file conflicts — same 5 as M1
    reported).
- Board flips in this PR: FUT-030 AVAILABLE → IN_REVIEW (owner muse_4,
  branch muse4/task-fut-030-econ-calendar-outlook) + TASK-STR-081
  IN_REVIEW → MERGED (PR #1764, merge e3985fc0 — owed flip per
  watch075/076, owner order 7143628341 rule 4).
- States after this run: implemented YES / tested YES (51 green in the
  CI-listed set + 4 regression green, re-run first-hand) / merged NO
  (replacement PR open, awaiting Muse) / deployed NO /
  production-verified NO (live leg — a production outlook from the
  deployed Futuris service — still needs merge + fleet CD + hub
  clearance).
