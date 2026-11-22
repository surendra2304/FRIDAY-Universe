# TASK-STR-HLT-001 — Stratex /health capability text: Binance Futures demo + Pepperstone-pending

- **Assignment:** coordinator POOL 8 (issue #35 comment 7077110975). **Claim:** comment 7078798978.
- **Board:** record verified AVAILABLE, owner muse_2, on main 61632838 (board blob 448227d1) before claiming; flipped to IN_REVIEW in this PR.
- **Merge-base:** main `b9123028`. **Work commit:** `79a5c5640f1826e9087f33d22903e43ce353e587`. **PR:** #1371.

## What was stale

OANDA was fully removed 2026-11-19 and the Binance testnet host was excised in TASK-STR-FWD-032, yet the live Stratex `/health` capability output still said `DEMO_ENVIRONMENT: execution venues are Binance Futures testnet and OANDA practice` (`Stratex/dashboard.py::_daemon_capability_warnings`). The same stale venue claim also appeared in the FRIDAY supervision payload (`venue: binance_futures+oanda_practice`) and the daemon startup Telegram pair — the propagation path into FRIDAY fleet-status answers named in the board evidence.

## Changes (work commit 79a5c564)

- `Stratex/dashboard.py` — `_daemon_capability_warnings` now returns `DEMO_ENVIRONMENT: execution venue is Binance Futures demo; Pepperstone pending-approval`; the daemon snapshot `environment` is `binance_futures_demo` (was `multi_venue_testnet_practice`); the `_multi_venue_daemon_snapshot` docstring corrected.
- `Stratex/api/friday_supervision.py` — supervision `venue` is `binance_futures_demo`.
- `Stratex/autonomy/run_daemon.py` — startup Telegram pair venues line and module docstring corrected to Binance Futures demo + Pepperstone pending-approval.
- `Stratex/tests/test_daemon_heartbeat_health.py` — updated the two pinned assertions (environment + capability warnings) and added a `TestDaemonCapabilityWarnings` regression class, including a no-OANDA assertion.
- `.github/workflows/owner-workflows.yml` — added `Stratex/tests/test_daemon_heartbeat_health.py` to the Stratex contracts list. A repo-wide search found ZERO references to that test file before this PR: no workflow collected it, so the assertions it pins never ran in CI. The import closure was checked before listing it: dashboard/data/quantum pull only numpy, pandas, flask, flask-cors, python-binance, python-dotenv and requests, all installed earlier in the same contracts job.

## Verification

- Edited files syntax-checked (py_compile) and the workflow file YAML-parsed.
- Repo-wide code search before the change confirmed the exact served strings: `capability_warnings` in `dashboard.py`, `binance_futures+oanda_practice` only in `friday_supervision.py`, `multi_venue_testnet_practice` only in `dashboard.py` + this test + one diagnosis doc.
- After the change: `dashboard.py` contains no OANDA mention; `friday_supervision.py` contains none.
- CI on the PR head is the test evidence (the regression now runs in the contracts job). CI status at filing: running — see PR #1371 checks.

## Not done here (honesty bounds)

- **Live probe/deploy:** NOT done in this PR. `/health` on S1 still serves the old text until Muse merges AND clears deployment; the live probe is owed after clearance.
- Internal OANDA references remain in `run_daemon.py` / `multi_venue_engine.py` (sleeve bookkeeping, venue branches, comments) and in historical docs/backtests — dead code paths for a retired venue, not served text; removal is a separate refactor.
- The heartbeat `venues` test fixture still lists `oanda` as an engine venue key (stub engine); it is not served text and the dashboard does not read it.

— Muse 2
