# TASK-STR-090 — Paginate the STR-044 income fetch + round once in income_sums

- **Task:** Stratex: paginate the STR-044 reconciliation job income fetch (limit=1000 cap drops rows; funding stale, next close false-DISCREPANCY) + round once in income_sums.
- **Owner:** Muse 1. **Claim:** hub #1483 comment 7182164745, 2026-11-26 ~09:27 IST, queue position 3, WATCH135 assignment (hub #1483 comment 7181402891).
- **Board verified:** AVAILABLE, owner muse_1, branch null, pr null, on main `7e4dea62` (board blob `89253513`, verified via the git blob API before editing). No prior claim, branch or PR.
- **Branch:** `muse1/task-str-090-income-pagination` from main `7e4dea6200f3699ff802bba2976b4103287c214f`.
- **Fix task for:** the STR-088 run-6 finding (`docs/collaboration/TASK-STR-088-EVIDENCE.md` §6) — the smallest safe fix proposed there, implemented here, nothing more.
- **Venue:** Binance Demo Futures (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Demo only — signed GETs only; no orders placed, modified or cancelled, no service restarted, no ledger written. No live leg was attempted in this task (owner stop order gates live legs); the live re-probe is owed after merge (§5).

## 1. The bug (STR-088 §6, recapped with its numbers)

`DemoFuturesReader.income(RESET_MS)` in `Stratex/scripts/daily_fill_ledger_reconciliation.py` made a single `/fapi/v1/income` call with `limit: 1000` and no pagination. The venue returns the oldest 1000 rows first, so once more than 1000 income rows existed since `RESET_MS` (2026-11-14T13:03:53Z), every newer row was silently dropped:

- The capped fetch returned **exactly 1000 rows**, spanning 2026-11-16T15:33Z → **2026-11-25T08:00:00Z** — the cutoff frozen at the 1000th row.
- Rows after the cutoff (direct probe, `startTime` past the cutoff): **58 rows, all FUNDING_FEE, +0.23675746**. The 08:00Z Nov-25 payment was cut mid-payment: the capped fetch held 26 of its 29 rows (+0.15897142 of the full +0.17386191), so **+0.01489049** more was missing.
- **True funding total at probe time: +0.45814086. Every report since showed +0.2073 — stale by +0.2508**, frozen since Nov 25 08:00Z.
- **Forward impact:** the next venue close's realized row would be dropped by the cap, so the report's venue realized would be understated by exactly that close's realized and the identity residual would equal it — a false DISCREPANCY. The cap also froze the funding figure permanently (90 funding rows/day keep arriving, all dropped).
- **Second, minor bug in the same path:** `income_sums` rounded to 4 decimals after **every** row addition, accumulating ~0.001 error: commission reported −9.4624 vs true −9.46322266; funding reported +0.2073 vs true capped +0.20649291; realized −47.2309 vs true −47.23100001.

## 2. The fix (smallest safe change, job-only)

Two changes in `Stratex/scripts/daily_fill_ledger_reconciliation.py`, no venue writes, no ledger writes, no service changes, no call-site change (`reader.income(RESET_MS)` is unchanged):

### (a) `DemoFuturesReader.income()` now paginates

A new `_income_page()` helper makes one capped call; `income()` loops:

- Each call starts at the **last returned row's time** (not +1 ms) and rows already seen are skipped via a stable row key (`_income_row_key`: time, incomeType, symbol, asset, income, tranId).
- Advancing past the time (+1 ms) would drop the same-timestamp rows the cap cuts mid-payment — the 08:00Z payment's 3 missing rows share the cutoff timestamp with the 26 held rows. Starting at the last row's time re-fetches them; dedup removes the 26 already held.
- The loop ends when a page returns fewer than 1000 rows (the venue's complete tail). A full page with **no** new row means more than 1000 rows share one timestamp, which no `startTime` pagination can pass — it raises `RuntimeError` instead of spinning or silently dropping rows. (Real venue data: at most ~29 funding rows share a settlement timestamp; the guard is fail-loud for a shape that cannot occur on this venue. The job's venue-read `try` records it as a venue error and still files a report.)
- `income_type` filtering is preserved (passed through to every page).

### (b) `income_sums()` rounds once at the end

Totals accumulate in full precision and are rounded to 4 decimals once, on return. Every other sum in the job already rounds once (`venue_realized`, window nets); this brings `income_sums` in line.

## 3. Before / after evidence

Reference figures are the STR-088 §6 probe (2026-11-26 ~07:48–07:56 IST, direct reads with the job's own client); the paginated column is what the fixed code returns for the same row set, proven by the new test on a dataset with the exact §6 shape (§4).

| Figure | Before (capped, 1 call) | After (paginated) |
|---|---|---|
| Rows returned by `income(RESET_MS)` | exactly 1000, cutoff 2026-11-25T08:00:00Z | all rows (1061 at probe time: 1000 + 61; grows ~90 funding rows/day) |
| Funding rows dropped | 58 after cutoff + 3 of the 08:00Z payment = 61 rows, +0.2516 | none |
| Funding total reported | +0.2073 (stale, frozen since Nov 25 08:00Z) | +0.4581 (true +0.45814086) |
| Commission total reported | −9.4624 (per-row rounding) | −9.4632 (true −9.46322266, rounded once) |
| Realized total reported | −47.2309 | −47.231 (true −47.23100001) |
| Next venue close | realized row dropped → false DISCREPANCY | row fetched → identity closes |
| Calls to `/fapi/v1/income` | 1 | 2 at probe-time volume (one full page + the tail); grows only as rows accumulate |

## 4. Tests (new, in `Stratex/tests/test_daily_fill_ledger_reconciliation.py`)

Pure-core, no venue, no keys, no network — the reader is built with `object.__new__` and `signed_get` is stubbed with a fake that emulates the venue's observed semantics (oldest first, `startTime` filter, 1000-row cap):

- **`test_income_paginates_past_1000_rows`** — a 1061-row dataset in the exact §6 shape (974 rows at distinct times, a 29-row funding payment sharing one timestamp with the 1000th row as its 26th, 58 rows after the cutoff). Asserts all 1061 rows returned exactly once, in order, in **2 calls**, and `income_sums` gives FUNDING_FEE 0.232, REALIZED_PNL 487.0, COMMISSION 243.5. The capped fetch drops 61 rows on this dataset.
- **`test_income_single_page_and_type_filter`** — fewer than 1000 rows: exactly 1 call, `limit: 1000` passed, `incomeType` passed through.
- **`test_income_sums_rounds_once`** — 100 rows of 0.00006: true sum 0.006. Per-row rounding (the old behaviour) gives 0.01; the fix gives 0.006.
- **`test_income_pagination_stall_fails_loud`** — a venue that keeps returning the same full page raises `RuntimeError` after exactly 2 calls (no spin).

**CI wiring — no workflow change needed.** The file is already collected in PR CI: `owner-workflows.yml` ("Owner Workflow Contracts", runs on `pull_request` to main with paths including `Stratex/**`) runs this file in its "Stratex forward-test and self-experiment contracts" step. The FUT-030 lesson is satisfied by that existing invocation — but the new tests' execution must still be verified from the CI job log before this task is called tested (the log must list the four new test names).

## 5. Live re-probe — OWED, not attempted here

No live leg was attempted: the owner stop order gates live fleet moves, and the demo signing key lives on S1, not here. After merge, the next STR-044 timer run (01:00 IST) or a fresh job run on S1 will show the fix live: the report's `income_since_reset` funding should read ≈ +0.4581 (plus funding accrued since the probe) instead of the frozen +0.2073, and the income row count should exceed 1000. Until that run, this task is implemented + tested (CI), merged by the coordinator, and **not** production-verified.

## 6. Files changed

- `Stratex/scripts/daily_fill_ledger_reconciliation.py` — `income()` paginates (`_income_page` + `_income_row_key`, `_INCOME_PAGE_LIMIT = 1000`); `income_sums()` rounds once at the end. No other file touched in the job.
- `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — 4 new tests (§4); no existing test changed.
- `docs/collaboration/TASK-STR-090-EVIDENCE.md` — this doc.
- `docs/collaboration/WORK_BOARD.yaml` — board flip only: TASK-STR-090 AVAILABLE → IN_REVIEW, branch set (built from a fresh main board read at PR time; verified by full-file diff that only the STR-090 record changed).

## States

- **implemented:** YES — pagination + round-once, with tests, in the work PR.
- **tested:** PENDING — new tests must be verified as actually executed from the PR's CI job log (the FUT-030 lesson) before this is called tested. The file is collected by the existing owner-workflows invocation (§4); the log must list the four new test names.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — the job is already deployed (STR-044, PR #1503); the fix rides the next CD. No service change in this PR.
- **production-verified:** NO — live re-probe owed after merge (§5): next timer/fresh job run must show funding ≈ +0.4581+ and >1000 income rows.

— Muse 1
