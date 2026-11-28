# TASK-STR-107 — Evidence: fix IG2-STR-09 live tax-export CSV shape

- **Task:** TASK-STR-107 — Stratex: fix IG2-STR-09 live tax-export CSV shape (6 columns empty or zero on live daemon records).
- **Worker:** Muse 13. **Branch:** `muse13/task-str-107-tax-export-csv-shape` @ `cad9ea19` (main, merge #2246 WATCH250 board).
- **Assignment:** WATCH249 §B / BE 07:05 §B (hub #2045, 7231716845 / 7231776459). IG2-FRD-01-ACTIVATE-01 BLOCKED owner-gated; skip per blocked-head rule.
- **Source defect:** Muse 3 checkpoint 3 (hub 7231107638, evidence `docs/collaboration/TASK-STR-074-EVIDENCE.md`): 84 trades reconcile exactly, but 6 CSV columns empty/zero on live daemon records.

## Fix

`Stratex/reporting/tax_ledger_export.py` — `build_tax_rows` now accepts the
live daemon ledger shape while keeping the testnet shape working (no change
to testnet output — the 6 pre-existing tests pass unmodified):

| CSV column | Before (live) | Fix | After (live) |
|---|---|---|---|
| quantity / proceeds / cost_basis | 0.0 for all 84 rows | read `qty` when `quantity` is absent | 0 zero rows; proceeds sum 38196.18922217, cost basis sum 38698.935606 |
| date_open / date_close | empty for all 84 rows; `--year 2026` returned 0 trades | epoch `entry_time`/`exit_time` → UTC ISO (ms auto-detected; epoch ≤ 0 treated as unset, never 1970); `recorded_at` as close fallback | date_close empty 0/84; `--year 2026` returns 84/84 |
| venue | `Unknown` for all 84 rows | explicit `venue` field first, normalised through the marker map (`binance_futures` → `Binance`); else derive from `source` | Binance 82, OANDA 2 (matches ledger) |
| side | empty for all 84 rows | `side` first, then `direction`, then `action` | LONG 47, SHORT 35, BUY 2 (matches ledger) |
| trade_id | empty for 73/84 rows | `trade_id` → `exit_order_id` → `order_id` → `entry_order_id` → deterministic `LEDGER-<sha12>` derived from the record (stable across runs) | empty 0/84; 73 derived ids; 11 venue order ids kept |

`Stratex/tests/test_ig2_str09_tax_export.py` — 4 new tests (daemon-shape rows,
entry_order_id preference, `--year` filter on daemon rows, mixed shapes):
**10 passed** locally (scratch venv) and **10 passed on Stratex-Server**
(S4 venv python, 0.08s).

## Live before/after (Stratex-Server, server 4)

- **When:** 2026-11-28 ~07:44–07:49 IST (≈02:14–02:19 UTC).
- **Method (read-only, daemon untouched):** live ledger copied to
  `/tmp/str107/fill_ledger.jsonl`; the live module copy (9,202 bytes, Nov 16)
  ran on the copy for BEFORE; the fixed module (copied to
  `/tmp/str107/tax_ledger_export_fixed.py`, live tree never written) ran on
  the same copy for AFTER. No trading endpoint, no credentials, no restart.
- **Ledger:** `/opt/friday_universe/Stratex/state/fill_ledger.jsonl`, 84 rows,
  sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21` —
  identical before, during and after every run (same hash as M3 checkpoints
  1–3; no new fills since 2026-11-27T02:26Z).
- **Daemon:** PID 74531 running throughout (elapsed 10:51:48 at the final
  check); never touched, never restarted.
- **Reconciliation (before = after, exact):** 84 rows; total fees
  13.04361348; total realised P&L +107.08898814. Per-row (fees, gross,
  realised) multiset identical before/after — the fix changes no money
  figure, only the 6 shape columns. Summary `by_venue` moves from
  `Unknown: 84` to `Binance: 82, OANDA: 2`; `by_year` 2026 moves from 0 to 84.
- **Live ledger shape confirmed first-hand** (differs from M3's table in two
  details): `entry_order_id` exists (non-empty on 8 rows) and `side` is
  `BUY` on the 2 OANDA rows (passed through, not remapped). `entry_time` is
  epoch seconds with a fractional part (e.g. 1794658249.801).

## Honest caveats (not hidden)

- **date_open still empty on 3/84 rows.** Those 3 ledger rows carry
  `entry_time: 0.0` (unset at the source). Emitting 1970-01-01 would be a
  lie; the export leaves them blank. `date_close` is populated on all 84
  (exit_time present throughout). Fixing the 3 missing entry times is a
  daemon-ledger source issue, out of scope here.
- **trade_id unique 83/84, not 84/84.** The value `470` appears twice: two
  ledger rows (indices 9, 10) share one entry order — same entry_time and
  entry_price, different exits (`BROKER_CLOSE` vs `VENUE_CLOSE_CORRECTION`).
  The duplicate is inherited from the ledger (one entry order, two close
  legs), not created by the export; the id is kept faithful to the venue
  order id rather than invented. Rows stay distinguishable by date_close
  and exit_reason.
- **Derived ids are export ids, not venue ids.** The 73 `LEDGER-<sha12>`
  values are deterministic hashes of the record (symbol, times, side, qty,
  prices) — stable for a given ledger, clearly prefixed so no one mistakes
  them for a venue order id.

## Files changed

- `Stratex/reporting/tax_ledger_export.py` (+helpers `_epoch_to_iso`,
  `_derived_trade_id`, `_venue`; daemon-field fallbacks in `build_tax_rows`).
- `Stratex/tests/test_ig2_str09_tax_export.py` (+4 tests).
- `.github/workflows/friday-universe-ci.yml` — `tests/test_ig2_str09_tax_export.py`
  added to the Stratex tier-1 run so the REL-068 collection guard passes
  (contracts job failed PR #2249 while the file was uncollected; same
  precedent as STR-065/STR-078/STR-082/STR-083/STR-086). Workflow file is a
  shared contract — coordinator review owed at merge.
- This evidence file.

## Repro (Stratex-Server, read-only)

```sh
cp /opt/friday_universe/Stratex/state/fill_ledger.jsonl /tmp/str107/fill_ledger.jsonl
cd /opt/friday_universe/Stratex
/opt/friday_universe/venv/bin/python -m reporting.tax_ledger_export \
  --ledger /tmp/str107/fill_ledger.jsonl --out /tmp/str107/after.csv \
  --summary /tmp/str107/after.summary.json --year 2026   # 84 trades
```
