# TASK-STR-091 — Forward-window fill/close ledger state filing run 2 (evidence)

- **Task:** Stratex: forward-window fill/close ledger state filing run 2 — reconcile daemon ledger vs venue positions/history after STR-090.
- **Owner:** Muse 4. **Claim:** hub #1483 comment 7186332107, 2026-11-26 ~13:40 IST, on coordinator assignment in WATCH148 correction (hub 7186158821 / duplicate 7186162290, ~13:35 IST), answering work request 7185994500.
- **Board verified:** AVAILABLE, owner null, branch null, pr null, on live main `703965cc` (board blob read via git blob API before editing). No prior claim, branch or PR.
- **Branch:** `muse4/task-str-091-forward-window-fill-ledger-run2` from main `0434f6df` (rebased from `703965cc` after PR #1971 merged; no content change).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `703965cc`, incl. the STR-090 income-pagination fix) run live on Stratex-Server (server 4) from a fresh worktree `/tmp/muse4-str091` at `703965cc` (the S1 checkout is on main `3db55adf`, which predates the STR-090 merge — the worktree, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). Daemon venv python 3.10.22. Run at 2026-11-26T08:16:36Z / 13:46:36 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-26.json` on S1 (overwrites the 01:00 UTC timer run's report for the same date; that run's figures are preserved in §7 and in `/tmp/muse4-str091-before.json` on S1). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse4-str091/Stratex:/tmp/muse4-str091` so the fixed code runs. Exact command in §8.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6025 USDT** against a tolerance of 10.51 USDT; no matched row disagrees with the venue by more than $0.50. The residual is not a ledger error — it is exactly the 30 Nov-19 reset-wipe micro-closes (−1.6023) that aged out of the venue's ~7-day `userTrades`/`allOrders` window between the 01:00 UTC timer run and this run (§7, probed first-hand). The ledger itself is unchanged between the two runs.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-24T15:17:23Z last close)

| Figure | Run 2 (this run, 08:16 UTC) | Timer run (01:00 UTC, old code) |
|---|---|---|
| Ledger closes, all time | 82 rows | 82 rows |
| Ledger net P&L (all time) | **+117.9497** (gross +130.915, fees 12.9653) | +117.9497 |
| Ledger closes in forward window | 73 rows | 73 rows |
| Ledger window net P&L | **−77.1101** (Binance −77.0623 + OANDA USDJPY −0.0478) | −77.1101 |
| Ledger window fees | 3.2388 | 3.2388 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 38 rows −137.0492 | same |
| Venue closes in window | 77 (73 ledger + 4 missing) | 107 (73 ledger + 34 missing) |
| Venue window true net P&L | −48.9151 | −50.5174 |
| Venue account at run time | wallet 10,462.46, margin 10,505.89, unrealised +43.43, available 9,479.21 USDT (USDT 4,944.75 + USDC 5,000 + BTC 0.01) | wallet 10,463.10, margin 10,517.96, unrealised +54.86, available 9,496.22 |
| Open positions at run time | 30, unrealised +43.4378 | 30, unrealised +54.9807 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−47.231**, COMMISSION **−9.4632**, FUNDING_FEE **+0.6552**, TRANSFER +15,000.03 | REALISED_PNL −47.2309, COMMISSION −9.4624, FUNDING_FEE +0.2073 (frozen), TRANSFER +15,000.03 |
| Income rows fetched | **1,090** (734 FUNDING_FEE, 267 COMMISSION, 83 REALIZED_PNL, 6 TRANSFER) | 1,000 (capped) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

**Window identity (LEDGER-001 §6, whole post-reset period):** venue realised −47.231 = ledger window net (Binance) −77.0623 + missing closes +28.195 + ledger window fees 3.2388 → expected −45.6285, **residual −1.6025**, status RECONCILED. Last ledger row recorded 2026-11-24T15:17:23Z (SOLUSDT −10.0571) — no close has been recorded since; the daemon is quiet on closes for ~2 days while 30 positions stay open.

**Run 1 comparison (STR-043, 2026-11-23):** 69 closes, window net −34.3752, residual −0.0001. The ledger grew by 4 rows net since run 1 (78 → 82); the 4 net-new window closes are ATOMUSDT −10.5726 (Nov 23 14:17:24Z), ADAUSDT −11.3614 (Nov 23 19:40:06Z), ALGOUSDT −10.7439 (Nov 24 09:12:14Z), SOLUSDT −10.0571 (Nov 24 15:17:23Z) — their sum −42.7350 equals the window-net change (−34.3752 → −77.1101) to 0.0001.

## §2 — Net P&L by symbol (window, 73 closes)

| Symbol | Net P&L | Symbol | Net P&L | Symbol | Net P&L |
|---|---|---|---|---|---|
| AAVEUSDT | 0.0000 | DOGEUSDT | −5.2915 | OPUSDT | 0.0000 |
| ADAUSDT | −31.9944 | DOTUSDT | +10.9385 | SANDUSDT | +10.1942 |
| ALGOUSDT | −2.1276 | ETCUSDT | −10.1619 | SOLUSDT | −31.5362 |
| APTUSDT | 0.0000 | ETHUSDT | −20.3867 | SUIUSDT | −14.0632 |
| ARBUSDT | 0.0000 | FILUSDT | 0.0000 | TRXUSDT | 0.0000 |
| ATOMUSDT | +10.0703 | HBARUSDT | +10.0176 | UNIUSDT | +10.1544 |
| AVAXUSDT | −20.6058 | INJUSDT | 0.0000 | USDJPY | −0.0478 |
| BCHUSDT | 0.0000 | LINKUSDT | +1.8418 | VETUSDT | +20.2573 |
| BNBUSDT | 0.0000 | LTCUSDT | 0.0000 | XLMUSDT | 0.0000 |
| BTCUSDT | +8.0792 | MANAUSDT | 0.0000 | XRPUSDT | −21.5439 |
| NEARUSDT | −0.9046 | | | **Total** | **−77.1101** |

Zero-net symbols are the Nov-19 reset-wiped rows (§5): their positions were wiped by the faucet reset and re-entered, so the ledger carries them at 0.0 with fallback exit times. Per-symbol nets were re-derived independently from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) and match the report exactly.

## §3 — Fills and closes vs the venue

- **Ledger closes (73):** 41 of the 80 Binance rows match venue fills on both entry and exit legs (**BOTH**); 39 match neither (**NO_MATCH**) — the 30 Nov-19 reset-wiped 0.0 rows (fallback exit times, match nothing by design) + 9 pre-window Nov-14 rows. No ENTRY_ONLY / EXIT_ONLY rows. **Diffs over $0.50: none.** Matched exit realised −73.8237 vs matched ledger net −77.0623 — the 3.2386 gap is exactly the ledger window fees. The 2 OANDA USDJPY rows are not venue-matched (different venue) by design. 71/82 ledger rows carry no `order_id`; row-to-venue traceability rests on price/qty/time matching (G-trace).
- **Venue closes (77):** 73 are the ledger closes; **4 have no ledger row (+28.195 USDT realised)** — the known G1 gap, narrowed from 34 by the §7 retention finding (the other 30 aged out of the venue's window; they are listed in the 01:00 UTC report, preserved on S1):
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T19:14:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 2026-11-21T06:16:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 2026-11-22T12:16:35Z
- **Venue fills:** 34 unmatched zero-realised fills (entry legs of the 30 open positions + 4 breakeven/entries — visible, never silently dropped). The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.

## §4 — Rows outside the window (9, all 2026-11-14, correctly excluded)

Same 9 rows as run 1 (STR-043 §4) — the ledger grew only with Nov 23–24 in-window rows, so the outside set is unchanged:

| Symbol | Exit (UTC) | Net | Reason |
|---|---|---|---|
| SOLUSDT | 2026-11-14T12:10:49Z | −33.6354 | OWNER_DIRECTED_CLOSE |
| UNIUSDT | 2026-11-14T12:10:52Z | +229.6280 | OWNER_DIRECTED_CLOSE |
| PAXGUSDT | 2026-11-14T12:10:54Z | −0.2860 | OWNER_DIRECTED_CLOSE |
| LTCUSDT | 2026-11-14T13:01:13Z | +0.5437 | WIN |
| ETHUSDT | 2026-11-14T13:26:01Z | +0.6818 | WIN |
| DOTUSDT | 2026-11-14T14:02:28Z | +0.0302 | WIN |
| XRPUSDT | 2026-11-14T14:46:57Z | −0.0141 | WIN |
| BTCUSDT | 2026-11-14T16:47:23Z | −0.6396 | LOSS |
| BTCUSDT | 2026-11-14T21:03:38Z | −1.2488 | LOSS |

These predate the forward window (and the 2026-11-14T13:03:53Z owner reset); the ledger total +117.9497 over 82 rows includes them, the window net −77.1101 does not.

## §5 — All 73 window closes (ledger, exit time UTC, net USDT, reason)

| Symbol | Exit (UTC) | Net | Reason |
|---|---|---|---|
| USDJPY | 2026-11-16T13:08:45Z | 0.0000 | BROKER_CLOSE |
| USDJPY | 2026-11-17T08:35:06Z | −0.0478 | VENUE_CLOSE_CORRECTION |
| TRXUSDT | 2026-11-19T07:36:39Z | 0.0000 | SL_TP_BROKER |
| MANAUSDT | 2026-11-19T07:36:41Z | 0.0000 | SL_TP_BROKER |
| FILUSDT | 2026-11-19T07:36:44Z | 0.0000 | SL_TP_BROKER |
| DOTUSDT | 2026-11-19T07:36:47Z | 0.0000 | SL_TP_BROKER |
| ETHUSDT | 2026-11-19T07:36:49Z | 0.0000 | SL_TP_BROKER |
| SUIUSDT | 2026-11-19T07:36:51Z | 0.0000 | SL_TP_BROKER |
| BCHUSDT | 2026-11-19T07:36:53Z | 0.0000 | SL_TP_BROKER |
| INJUSDT | 2026-11-19T07:36:55Z | 0.0000 | SL_TP_BROKER |
| ETCUSDT | 2026-11-19T07:36:58Z | 0.0000 | SL_TP_BROKER |
| LTCUSDT | 2026-11-19T07:37:00Z | 0.0000 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-19T07:37:02Z | 0.0000 | SL_TP_BROKER |
| XRPUSDT | 2026-11-19T07:37:05Z | 0.0000 | SL_TP_BROKER |
| LINKUSDT | 2026-11-19T07:37:07Z | 0.0000 | SL_TP_BROKER |
| VETUSDT | 2026-11-19T07:37:10Z | 0.0000 | SL_TP_BROKER |
| NEARUSDT | 2026-11-19T07:37:12Z | 0.0000 | SL_TP_BROKER |
| AAVEUSDT | 2026-11-19T07:37:15Z | 0.0000 | SL_TP_BROKER |
| BTCUSDT | 2026-11-19T07:37:17Z | 0.0000 | SL_TP_BROKER |
| SOLUSDT | 2026-11-19T07:37:19Z | 0.0000 | SL_TP_BROKER |
| APTUSDT | 2026-11-19T07:37:21Z | 0.0000 | SL_TP_BROKER |
| AVAXUSDT | 2026-11-19T07:37:23Z | 0.0000 | SL_TP_BROKER |
| UNIUSDT | 2026-11-19T07:37:25Z | 0.0000 | SL_TP_BROKER |
| BNBUSDT | 2026-11-19T07:37:28Z | 0.0000 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-19T07:37:30Z | 0.0000 | SL_TP_BROKER |
| XLMUSDT | 2026-11-19T07:37:31Z | 0.0000 | SL_TP_BROKER |
| OPUSDT | 2026-11-19T07:37:33Z | 0.0000 | SL_TP_BROKER |
| HBARUSDT | 2026-11-19T07:37:35Z | 0.0000 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-19T07:37:37Z | 0.0000 | SL_TP_BROKER |
| ADAUSDT | 2026-11-19T07:37:39Z | 0.0000 | SL_TP_BROKER |
| SANDUSDT | 2026-11-19T07:37:40Z | 0.0000 | SL_TP_BROKER |
| ARBUSDT | 2026-11-19T07:37:42Z | 0.0000 | SL_TP_BROKER |
| BTCUSDT | 2026-11-19T21:16:49Z | −10.0709 | SL_TP_BROKER |
| NEARUSDT | 2026-11-19T22:12:27Z | −10.6754 | SL_TP_BROKER |
| ETHUSDT | 2026-11-20T01:59:07Z | −10.2055 | SL_TP_BROKER |
| ETCUSDT | 2026-11-20T01:59:09Z | −10.1619 | SL_TP_BROKER |
| LINKUSDT | 2026-11-20T01:59:10Z | −10.9556 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-20T02:26:00Z | −10.2061 | SL_TP_BROKER |
| SUIUSDT | 2026-11-20T02:32:22Z | −10.6613 | SL_TP_BROKER |
| SANDUSDT | 2026-11-20T04:38:30Z | −10.8371 | SL_TP_BROKER |
| ADAUSDT | 2026-11-20T12:08:45Z | −10.4336 | SL_TP_BROKER |
| SOLUSDT | 2026-11-20T13:33:45Z | −10.7553 | SL_TP_BROKER |
| AVAXUSDT | 2026-11-20T13:36:04Z | −10.5510 | SL_TP_BROKER |
| DOTUSDT | 2026-11-20T15:24:30Z | +20.4903 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-20T15:48:18Z | +20.6429 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-20T17:40:11Z | +19.2393 | SL_TP_BROKER |
| NEARUSDT | 2026-11-21T03:05:40Z | +20.5298 | SL_TP_BROKER |
| HBARUSDT | 2026-11-21T03:30:42Z | +20.8414 | SL_TP_BROKER |
| SANDUSDT | 2026-11-21T03:32:15Z | +21.0313 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-21T03:32:59Z | +15.7029 | SL_TP_BROKER |
| XRPUSDT | 2026-11-21T03:33:34Z | −10.8180 | SL_TP_BROKER |
| VETUSDT | 2026-11-21T03:34:37Z | +20.2573 | SL_TP_BROKER |
| BTCUSDT | 2026-11-21T04:05:09Z | +28.4841 | SL_TP_BROKER |
| UNIUSDT | 2026-11-21T04:05:10Z | +20.4999 | SL_TP_BROKER |
| LINKUSDT | 2026-11-21T04:06:36Z | +20.8566 | SL_TP_BROKER |
| SUIUSDT | 2026-11-21T13:08:02Z | −3.4019 | SL_TP_BROKER |
| BTCUSDT | 2026-11-21T13:25:12Z | −10.3340 | SL_TP_BROKER |
| ETHUSDT | 2026-11-21T13:36:31Z | −10.1812 | SL_TP_BROKER |
| LINKUSDT | 2026-11-21T13:36:32Z | −8.0591 | SL_TP_BROKER |
| UNIUSDT | 2026-11-21T13:36:34Z | −10.3455 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-21T13:38:35Z | −10.7883 | SL_TP_BROKER |
| HBARUSDT | 2026-11-21T13:39:21Z | −10.8238 | SL_TP_BROKER |
| XRPUSDT | 2026-11-21T13:49:41Z | −10.7259 | SL_TP_BROKER |
| NEARUSDT | 2026-11-21T13:52:33Z | −10.7590 | SL_TP_BROKER |
| SOLUSDT | 2026-11-23T09:05:57Z | −10.7238 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-23T11:59:12Z | −10.6229 | SL_TP_BROKER |
| AVAXUSDT | 2026-11-23T13:57:01Z | −10.0548 | SL_TP_BROKER |
| ADAUSDT | 2026-11-23T13:58:24Z | −10.1994 | SL_TP_BROKER |
| DOTUSDT | 2026-11-23T14:00:33Z | −9.5518 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-23T14:17:24Z | −10.5726 | SL_TP_BROKER |
| ADAUSDT | 2026-11-23T19:40:06Z | −11.3614 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-24T09:12:14Z | −10.7439 | SL_TP_BROKER |
| SOLUSDT | 2026-11-24T15:17:23Z | −10.0571 | SL_TP_BROKER |

## §6 — STR-090 live re-probe: CLOSED by this run

STR-090 §5 left a live re-probe owed: after the income-pagination merge, the next job run on S1 must show funding ≈ +0.4581+ and >1000 income rows. This run is that re-probe, on the merged code (main `703965cc`, fix verified present in the worktree: `_income_page` + `_INCOME_PAGE_LIMIT = 1000`):

| Figure | STR-090 probe (2026-11-26 ~07:48 IST) | This run (08:16 UTC) |
|---|---|---|
| Income rows returned by `income(RESET_MS)` | 1,061 (paginated, test-proven) | **1,090** — 734 FUNDING_FEE, 267 COMMISSION, 83 REALIZED_PNL, 6 TRANSFER |
| Funding total | +0.4581 (true +0.45814086) | **+0.6552** — higher because the Nov 25 16:00 + Nov 26 00:00/08:00 settlements accrued since the probe; cross-checked by an independent direct `income()` call on S1 (same +0.6552) |
| Commission total | −9.4632 (true −9.46322266) | **−9.4632** |
| Realised total | −47.231 (true −47.23100001) | **−47.231** |
| Capped-fetch comparison | exactly 1,000 rows, cutoff 2026-11-25T08:00:00Z | the 01:00 UTC timer run (old code) still showed funding +0.2073 / commission −9.4624 / realised −47.2309 — the frozen figures, preserved in §7 |

The pagination fix is proven live: the report's income figures now match full-precision re-derivation, and the funding figure is unfrozen and growing with settlements.

## §7 — The 34 → 4 finding: venue `userTrades`/`allOrders` ~7-day retention

The 01:00 UTC timer run (old code, S1 checkout `3db55adf`) listed 34 missing closes (+26.5927) and 64 unmatched zero fills; this run lists 4 (+28.195) and 34. The ledger is identical in both runs (82 rows, window 73, net −77.1101; matching BOTH 41 / NO_MATCH 39 identical) and the reconciler code differs only by the STR-090 income change (verified by `git diff 3db55adf..703965cc` — one commit, `ccfd5948`, income pagination + round-once; the missing-close logic is untouched). The change is in the venue data, not the ledger or the code:

- The 30 orders that left the missing list are exactly the Nov-19 07:56Z reset-wipe micro-closes (one per symbol, realised −0.0055 to −0.17 each, total **−1.6023**); their 30 SELL re-entry orders left the unmatched-zero list at the same time. Closes on venue 107 → 77 (−30); missing realised +26.5927 → +28.195 (+1.6023); residual −0.0002 → −1.6025 (−1.6023) — the arithmetic closes exactly.
- **Boundary:** the micro-closes are from 2026-11-19T07:56:38Z. +7 days = 2026-11-26T07:56:38Z. The timer run (01:00:20Z, age 6d 17h) still saw them; this run (08:16:36Z, age 7d 0h 20m) does not. Every dropped close is Nov 19 07:56Z; every kept close is Nov 20 or later.
- **Direct probe (S1, after the run):** `userTrades("TRXUSDT")` returns 1 row (time 2026-11-20T04:02:36Z); order 1173153567 (the TRX micro-close, first in the timer run's missing list) has 0 fills present; `allOrders("TRXUSDT")` returns 1 row, order 1173153567 absent.
- **Consequence:** the reconciler's missing-close list is only complete for roughly the last 7 days of venue history — older closes age out of `userTrades`/`allOrders` and stop being listed (their realised P&L also leaves the identity, moving the residual by exactly their sum; here −1.6023, well within tolerance). This does not affect the verdict, but future runs will keep narrowing G1 the same way. Persisting venue trades (or a `startTime`-bounded fetch from a stored floor) would be a separate fix task; not attempted here — this task files the state, it does not change the job.

## §8 — Run record (commands, all read-only on the venue)

- S1 checkout: main `3db55adf` (predates the STR-090 merge `250cf2b4`); timer `friday-stratex-reconciliation.timer` enabled, last 2026-11-26 01:00:19 UTC, next 2026-11-27 01:00:00 UTC. The timer's 01:00 UTC report is preserved at `/tmp/muse4-str091-before.json` on S1.
- Worktree: `git fetch origin main` (23e146b9..703965cc) + `git worktree add /tmp/muse4-str091 origin/main` on S1. The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Run (backgrounded, log `/tmp/muse4-str091-run.log` on S1):
  `cd /tmp/muse4-str091/Stratex && PYTHONPATH=/tmp/muse4-str091/Stratex:/tmp/muse4-str091 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-26`
  (the timer service's own invocation, with the worktree paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-26: ledger 82 rows (window 73, net -77.11), matching {'NO_MATCH': 39, 'BOTH': 41}, missing closes 4 (+28.20), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-26.json`
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed locally** (pytest 9.2.0, 0.59s, `PYTHONPATH=Stratex`), incl. the 4 STR-090 pagination tests; no test file changed in this task. CI re-verification from the work PR's job log follows (FUT-030 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §9 — Open positions at run time (30, unrealised +43.4378)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 95.73 | +7.0750 |
| ADAUSDT | +301.0 | 0.1494 | 0.1476 | −0.5418 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.07980416 | +0.5409 |
| APTUSDT | −116.9 | 0.4356 | 0.3808 | +6.4061 |
| ARBUSDT | −410.7 | 0.12691687 | 0.1148 | +4.9764 |
| ATOMUSDT | +163.37 | 1.264 | 1.245 | −3.1040 |
| AVAXUSDT | −3.0 | 7.015 | 6.63943171 | +1.1267 |
| BCHUSDT | −0.388 | 208.38159794 | 207.5 | +0.3421 |
| BNBUSDT | −0.08 | 590.59 | 554.51 | +2.8864 |
| BTCUSDT | +0.0025 | 59,889.32 | 60,599.97956522 | +1.7766 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05646 | −2.0487 |
| DOTUSDT | −102.7 | 0.6728 | 0.6674 | +0.5546 |
| ETCUSDT | −14.63 | 5.659 | 5.8995 | −3.5185 |
| ETHUSDT | +0.111 | 1,681.3 | 1,687.47267442 | +0.6852 |
| FILUSDT | −81.9 | 0.5788 | 0.54505876 | +2.7634 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05336 | −2.6367 |
| INJUSDT | −19.0 | 6.657 | 6.174 | +9.1770 |
| LINKUSDT | −8.79 | 8.629 | 9.15587767 | −4.6313 |
| LTCUSDT | −5.706 | 42.86 | 43.35637255 | −2.8323 |
| MANAUSDT | −1,342.0 | 0.06059954 | 0.05694348 | +4.9064 |
| NEARUSDT | −14.0 | 2.901 | 3.05732455 | −2.1885 |
| OPUSDT | −661.6 | 0.0768 | 0.069 | +5.1605 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03323 | +0.4555 |
| SOLUSDT | −2.1 | 69.02 | 70.89196743 | −3.9311 |
| SUIUSDT | −96.1 | 0.6446 | 0.66942807 | −2.3860 |
| TRXUSDT | −750.0 | 0.30999 | 0.30407613 | +4.4354 |
| UNIUSDT | −9.0 | 4.70744444 | 4.72 | −0.1130 |
| VETUSDT | +40,580.0 | 0.004618 | 0.004866 | +10.0638 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12843892 | +10.6106 |
| XRPUSDT | −93.7 | 0.925 | 0.95245772 | −2.5728 |

All 3× leverage. Venue account unrealised +43.4255 (account-level read) vs positions sum +43.4378 (0.0123 apart — different read moments in the same run).

## Files changed

- `docs/collaboration/TASK-STR-091-EVIDENCE.md` — this doc.
- `docs/collaboration/WORK_BOARD.yaml` — board flip only: TASK-STR-091 AVAILABLE → IN_REVIEW, branch + pr set (built from a fresh main board read at PR time; verified by full-file diff that only the STR-091 record changed).
- No code changed — the reconciler is the merged STR-044 job + STR-090 fix; this task runs it and files the state.

## States

- **implemented:** YES — live reconciliation run + state filed as evidence (no code change required; the job already exists merged).
- **tested:** YES — 28/28 reconciler tests pass locally on the exact PR-head code; live run exit 0, report filed, errors `[]`. CI log re-verification follows after the work PR opens.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — the job is already deployed (STR-044 timer on S1); the report was filed on S1 by this run. No service change in this PR.
- **production-verified:** YES — live run on Stratex-Server against the demo venue, RECONCILED, report filed; STR-090 live re-probe closed (§6). Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse 4
