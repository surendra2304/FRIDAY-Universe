# TASK-STR-044 — Stratex daily fill-ledger reconciliation job

- Task: recurring form of the STR-LEDGER-001 one-off verification (merged PR #1350): a scheduled job reconciles the daemon fill/close ledger against Binance Demo Futures once a day and files fills, closes and net P&L evidence for the forward window. Acceptance: "Scheduled reconciliation runs once and files fills, closes and net P&L evidence for the forward window."
- Owner: Muse 4. Branch: `muse4/task-str-044-daily-fill-ledger-reconciliation`. Claim: successor hub #1483 comment 7100668035. Board claim rides in this PR (claim PRs abolished — coordinator push 7100469274).
- Venue: Binance Demo Futures, `https://demo-fapi.binance.com` (`BINANCE_ENV=demo`, `BINANCE_KEY_TYPE=ed25519`). Demo only — no real money, no live-money action. Signed GETs only; no POST/DELETE/PUT anywhere in the job.
- Base: main `237667b6` (PR #1499 merged during the run; the branch was rebased from `7345f64a` — that merge touched only a Futuris doc + the board, no STR-044 path).

## 1. What was built

- `Stratex/scripts/daily_fill_ledger_reconciliation.py` — the job, stdlib-only at import (lazy `cryptography` import inside the venue reader). Reads the ledger + daemon state, reads the venue (`/fapi/v2/account`, `/fapi/v2/positionRisk`, `/fapi/v1/userTrades` per symbol with no `startTime`, `/fapi/v1/income`, `/fapi/v1/allOrders`), matches every `binance_futures` ledger row against venue fills (side, qty ±1%, VWAP ±0.5%, time ±5 min) into BOTH / ENTRY_ONLY / EXIT_ONLY / NO_MATCH, lists venue closes with no ledger row + realized P&L, detects faucet resets via TRANSFER income rows, and files a dated report `state/reconciliation/daily_YYYY-MM-DD.json` (atomic write) plus measurement alerts latched on DISCREPANCY / new reset / venue-unavailable. Exit 0 = report filed (DISCREPANCY is a finding, not a job failure); 2 = venue unreachable, no report; 1 = usage error. Reuses `measurement.forward_scorecard`'s `GLOBAL_FORWARD_START` (`2026-11-15T11:29:49+05:30`) and tolerance rule (max $2.00, 0.1% of baseline).
- `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — 24 tests (matching, split-fill order matching, missing closes, reset detection, LEDGER-001 §6 identity numbers, demo-only guards, offline run, binance-only identity).
- `Stratex/deployment/friday-stratex-reconciliation.{service,timer}` — daily `01:00 UTC` (06:30 IST), `Persistent=true`, oneshot, demo `.env`.
- `.github/workflows/deploy-monorepo.yml` — guarded timer-install block in the S1 job (markers `# BEGIN/END STR-044 TIMER INSTALL (TASK-STR-044)`); installs + enables the timer when `Stratex/**` changes; install-only, never restarts the daemon.
- `.github/workflows/owner-workflows.yml` — new test added to the "Stratex forward-test and self-experiment contracts" pytest list (REL-068 collection).
- `tests/test_fleet_cd_str044_timer_install.py` — 8 tests; the timer block is extracted from the workflow and executed with fake sudo/systemctl.

## 2. Live proof run 1 — 2026-11-23 12:29:43Z: DISCREPANCY, and the diagnosis

First run (commit `f094257b`, worktree `/tmp/muse4-str044` on S1, daemon venv python 3.10.12): ledger **75 rows**, window 66 rows, window net **−4.57**, venue realized **+24.71**, missing closes 36 orders **+43.79**, fees 2.64, expected 41.86, **residual −17.15** (tolerance 10.59) → status **DISCREPANCY**. Matching: BOTH 28, EXIT_ONLY 4, ENTRY_ONLY 2, NO_MATCH 39.

Diagnosis (verified from the income stream the same day): the income fetch is complete and correct — single call 807 rows; per-type calls agree (REALIZED_PNL 75 rows +24.71; FUNDING_FEE 476, −0.66; COMMISSION 250, −8.42; TRANSFER 6, +15000.03). Venue realized fell 57.28 → 24.71 exactly because of 3 new realized rows since LEDGER-001's read (SAND −11.33, SOL −10.65, ALGO −10.59 = −32.57). The −17.15 residual was **explained, not a venue shortfall**:

- The NEAR +20.58 close is **2 fills of one order** (ledger row confirmed on S1: NEARUSDT SHORT qty 44.0, entry 3.206 @ Nov 20 00:01:17Z, exit 2.739 @ Nov 21 03:05:40Z, net +20.5298; venue fills +4.70 / +15.88 at 03:05:24Z). No single fill carries qty 44.0, so per-fill matching missed it and the close was re-listed as missing — double-counted while its realized P&L was already in the ledger.
- The SUI −3.38 close is **5 fills of one order** (ledger row confirmed on S1: SUIUSDT SHORT qty 80.0, entry 0.5961 @ Nov 21 06:23:46Z, exit 0.6384 @ Nov 21 13:08:02Z, net −3.4019; venue fills totaling −3.3815 at 13:07:31Z). Same double-count.
- NEAR +20.58 and SUI −3.38 net to +17.20; the oanda row (−0.0478) sat inside the binance-only identity. 17.1965 − 0.0478 = 17.1488 = the residual, exact to 0.0001.

## 3. The fix (commit `0659a224`)

1. **Order-level matching fallback** (`match_ledger_rows`): when per-fill matching fails for a side, match the ledger row against an order group (total qty ±1%, VWAP ±0.5%, any fill within 5 min) and consume all of its fills. A group is available only when none of its fills is already used, so a fill still explains exactly one row (a twin-row test guards this).
2. **Binance-only identity**: the window identity now uses `binance_futures` rows only (oanda leg reconciles separately per LEDGER-001 §7).
3. **Binance-only venue reads**: venue symbols come from `binance_futures` rows only — `userTrades("USDJPY")` answers 400 and polluted the errors list.

## 4. Live proof run 2 — 2026-11-23 12:46:01Z: RECONCILED

Re-run from a refreshed worktree at `0659a224` (same S1 paths; overwrites the run-1 report for 2026-11-23 — the run-1 numbers above are preserved here). Filed: `Stratex/state/reconciliation/daily_2026-11-23.json`.

- **Status: RECONCILED.** Window identity: venue realized **+24.7149**, ledger window net (binance) **−4.5214**, missing closes **+26.5927**, fees **2.6437**, expected **24.715**, **residual −0.0001**, tolerance 10.59.
- Ledger: 75 rows, net +190.4907 (gross +202.8609, fees 12.3702); window 66 rows, window net −4.5692 (binance −4.5213, oanda −0.0478); binance 73 rows +190.5385, oanda 2 rows −0.0478; FORWARD_TEST 31 rows −64.5082, no lane 44 rows +254.9989; first recorded 2026-11-14T12:41:21Z, last 2026-11-23T11:59:12Z; **64/75 rows carry no `order_id`** (traceability still rests on price/qty/time matching).
- Matching: **BOTH 34** (was 28), EXIT_ONLY 0, ENTRY_ONLY 0, NO_MATCH 39 (unchanged: the 30 Nov-19 reset-wiped rows + 6 testnet rows + 3 legacy rows). Rows matched 73; matched exit realized −1.8778 vs matched ledger net −4.5214; **diffs over 0.5: none** — every matched row agrees with its venue exit to within its fee. The six recovered rows are the split-fill orders (NEAR/SUI confirmed row-by-row in §2; the class movement accounts for the other four).
- Missing closes: **34 orders, +26.59** (was 36 / +43.79 — the 17.20 difference is exactly NEAR +20.58 and SUI −3.38 leaving the list). These are the known G1 gap: venue closes with no ledger row, listed individually in the report (largest: SUIUSDT +30.50, ETHUSDT +19.94, SANDUSDT −11.33, VETUSDT −10.92). They are accounted for in the identity, not new discrepancies.
- Venue account: wallet 10541.51, margin 10592.16, unrealized +50.65, available 9448.69; USDT wallet 5016.43, USDC 5000.00 (untouched faucet grant), BTC 0.01. **29 open positions**, unrealized +50.76.
- Resets: the 6 Nov-19 TRANSFER rows (3 × (5000.00 + 0.01)) detected again, `new_resets: []` — already filed by run 1, correctly not re-alerted. Errors: `[]`.
- Tests on S1 (daemon venv, pytest 8.4.2): **24 passed, 1 warning** for the new Stratex test file; timer-install + branch-guard + S2-health-gate root tests exit 0. REL-068 collection audit **PASS** (2 test files in scope). Local (this VM, pytest 9.2.0): 24/24, ruff F821 clean; both deploy scripts pass `bash -n`.

## 5. States and what remains

- Implemented: YES. Tested: YES (24/24 local + S1, live proof run 2 RECONCILED). Merged: NO (PR follows this commit). Deployed: PARTIAL — the timer install rides post-merge CD (guarded S1 block); one live proof run has filed real evidence. Production-verified: PARTIAL — the recurring scheduled run awaits merge + CD timer install + the next day's run; the job itself is proven against live venue data.
- Open gaps carried forward (not blockers): G1 — 34 venue closes with no ledger row (+26.59), the pre-window / reset-wiped closes the daemon never logged; G-trace — 64/75 ledger rows lack `order_id`.
- Note: two bridge calls during the readbacks timed out at the 120 s HTTP limit and succeeded on retry — bridge transport slowness, not a job or S1 issue; all numbers above were read back from the filed report and the S1 proof log.
