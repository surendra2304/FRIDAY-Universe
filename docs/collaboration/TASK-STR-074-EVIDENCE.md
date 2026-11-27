# TASK-STR-074 — Evidence: production-verify wave 1 (checkpoint 1 — scoping + live S4 baseline)

- **Task:** PRODUCTION-VERIFY wave 1 — live extreme-condition verification of TASK-IG2-STR-09, -10, -11, -12, -13 (Stratex corpus items).
- **Filed:** 2026-11-28 ~04:15 IST, by Muse 3 (claim hub #2045 comment 7228374022; BE 02:38 §B, hub 7228172325).
- **Branch:** `muse3/task-str-074-production-verify-wave1` off main `e5adbc89`.
- **Board:** TASK-STR-074 CLAIMED / owner muse_3 / branch `muse3/task-str-074-production-verify-wave1` / pr null / P1 on live main (blob `35b6b1ef`). No board hunk in this PR per the coordinator-only flip rule.
- **Stall note:** claimed 02:41 IST; paired verdict #2203 filed 02:53 IST; paired verdict #2209 (WATCH244 §D, due ~04:42) filed 04:09 IST (review 6094011749, VERIFIED). No branch commit between claim and this checkpoint — this checkpoint 1 repairs the stall with scoping + live baseline.

## Scope — the five items (code locations found by first-hand code search)

| item | what it is | code |
|---|---|---|
| IG2-STR-09 | tax ledger export | `Stratex/reporting/tax_ledger_export.py` (+ `Stratex/tests/test_ig2_str09_tax_export.py`) |
| IG2-STR-10 | market-data fallback chain | `Stratex/market_data_fallback.py` (+ `Stratex/tests/test_ig2_str10_fallback_chain.py`) |
| IG2-STR-11 | economic calendar | `Stratex/research/economic_calendar.py` (+ `Futuris/futuris/features/calendar_context.py`) |
| IG2-STR-12 | Bayesian uncertainty | `Stratex/rigorous_backtest/ig/bayesian_uncertainty.py` (+ `Stratex/rigorous_backtest/ig/tests/test_bayesian_uncertainty.py`) |
| IG2-STR-13 | Box Theory RD | board VERIFIED 2026-11-16 (Muse, TASK-IG2-STR-13 landing) — backtest record only |

- **Flag (coordinator's call):** IG2-STR-13 already reads VERIFIED on the board from its backtest landing. This wave's live leg for it is a live re-check, not a first verification; if the board VERIFIED stands, the item needs a live run recorded here, not a re-verdict.
- **Acceptance (board):** for EACH item, run it in the live agent on a real task and file live evidence (what ran, on which server, with what result, incl. the failure case). Extreme-condition test: live demo-daemon cycle on Stratex-Server on real market data + failure injection (venue disconnect, stale feed) + full-allowlist load scan, results filed from the live ledger. A code-only report is rejected; any item that fails live gets a named fix task, never a verified mark.

## Live S4 baseline (bridge run_shell, read-only, 2026-11-27T22:40Z / 04:10 IST)

- Daemon RUNNING, PID 74531 (`run_daemon.py`), scan_count 1343, 15 s interval; last evaluation 22:40:06Z; last cycle: scanned 2310, signals 0, executed 0, errors 0, 30 symbols (30 1d).
- `forward_scorecard.json` mtime 22:39:57Z, `daemon_heartbeat.json` 22:40:21Z — fresh at probe time (22:40:25Z). Scorecard parses, 9 keys.
- Equity $10,473.91, balance $10,436.11, unrealized +$37.80, realized +$46.87, 30 open positions, daily breaker NOT hit, daily start equity $10,485.85.
- `fill_ledger.jsonl`: 84 lines; latest fills ATOMUSDT LONG exit (net −10.78) and LTCUSDT SHORT exit; live hash identical to the backup copy.
- Backup cross-check (same run, #2209 verdict probes): dated set `20261128T023026Z` complete, verify 4159 OK / 0 failed on S1 and S2; all four spot hashes match the filed table. The live ledger is therefore backed up before the failure-injection leg — nothing here changes S4 state.

## Next (checkpoint 2)

- IG2-STR-10 first: the failure-injection leg (venue disconnect, stale feed) maps directly onto the fallback chain — run it live on S4 and file the ledger result.
- Then IG2-STR-09 (tax export from the live ledger), IG2-STR-11 (calendar context in a live cycle), IG2-STR-12 (Bayesian uncertainty on live fills), IG2-STR-13 (live re-check; see flag above).
- Full-allowlist load scan last, results from the live ledger. No server moves (owner stop order 7130069033); no deploys/restarts without hub clearance; demo only.

## Five states

- implemented NO, tested NO, merged NO, deployed n/a, production-verified NO.

— Muse 3
