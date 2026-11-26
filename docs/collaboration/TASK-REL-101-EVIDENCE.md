# TASK-REL-101 — Evidence: Futuris FUT-030 calendar-test date rollover

**Task:** TASK-REL-101 (P0) — Fix the Futuris FUT-030 calendar-test date rollover that fails contracts on main.
**Owner:** Muse 4. **Claim:** hub #1483 comment 7182014034 (WATCH136 re-slot TP10 → Muse 4).
**Branch:** `muse4/task-rel-101-futuris-contracts-date-rollover` (from main `036fb2da`).

## Root cause

`Futuris/tests/api/test_market_calendar_context.py` pinned the feed store to a
fixed date (`TODAY = date(2026, 11, 25)`; feed refreshed with `today=TODAY`),
while the router (`Futuris/futuris/api/routers/market.py`, `_generate_market_prediction`)
calls `build_calendar_context(feed, requested=...)` with no `today`, so the feed
filters on the real UTC date (`today <= e.date <= horizon` in
`Stratex/research/economic_calendar.py::upcoming`). From 2026-11-26 UTC the
stored 2026-11-25 events fell out of the window: the outlook reported
`none_upcoming` instead of `available`, failing the available / 3-events /
CPI-headline assertions. The production code is correct (real-UTC-date default);
only the test pinned a fixed date.

## Before evidence (failing)

- Contracts on main: workflow run **45728251068** (head `875504ffd5`, branch main),
  single job `contracts`, conclusion **failure** — verified first-hand via the API.
  Every contracts run since 2026-11-26 00:00 UTC failed; all 2026-11-25 runs passed.
- Local reproduction (venv `rel101-venv`, `PYTHONPATH=Futuris`,
  `DATABASE_URL=oracle+oracledb://mock:mock@localhost:1521/FREE`, same file list as
  the contracts step): **17 passed, 1 failed** —
  `test_calendar_release_is_cited_in_response_and_named_in_rationale`:
  `assert 'none_upcoming' == 'available'`.

## Fix (test-only; no production code changed)

- `Futuris/tests/api/test_market_calendar_context.py`: `TODAY`/`NOW` now track the
  real current UTC date, re-anchored per test by the autouse `_patch_connectors`
  fixture (so the stored feed events and the router's real-UTC-date window can
  never straddle a midnight rollover). The `08:30` rationale assertion uses
  `TODAY.isoformat()` instead of a literal date.
- `Futuris/tests/test_fut030_calendar_context.py`: same unpinning (`TODAY` from the
  real UTC date; `DAY = TODAY.isoformat()`; the "Tomorrow" event is
  `TODAY + 1 day`). This file was self-consistent before (refresh and query both
  took the explicit date) and passed throughout; unpinned to meet the acceptance
  criterion that no test in the Futuris calendar path pins a fixed calendar date.
- No other file in the Futuris calendar path pins a fixed date (verified by grep;
  `Futuris/tests/models/test_fut007_event_wiring.py` pins 2026-11-25 but is the
  event-wiring path, not the calendar path, and is not in the contracts step).

## After evidence (passing, local)

- The two calendar files: **18/18 passed** (was 17 passed / 1 failed).
- Full contracts-step file list (the "Futuris health-capability contracts" step
  of `.github/workflows/owner-workflows.yml`, 11 files): **103/103 passed**,
  exit 0. CI proof on the work PR to follow (contracts job).

## Acceptance

- [x] Date-rollover failure fixed: the failing test passes; no test in the
  Futuris calendar path pins a fixed calendar date.
- [ ] Contracts green on current main after the fix (CI on the work PR — pending).
- [ ] Held PRs (#1787/#1920/#1921/#1925/#1927) green once they rebase (their owners'
      step, after this merges).

## Files

- `Futuris/tests/api/test_market_calendar_context.py` (fix)
- `Futuris/tests/test_fut030_calendar_context.py` (unpinning)
- `docs/collaboration/TASK-REL-101-EVIDENCE.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (board flip, rides in the work PR)

## Five states

implemented YES / tested YES (local 18/18 + full contracts-step list 103/103) /
merged NO / deployed N/A / production-verified NO (contracts green on main pending CI).
