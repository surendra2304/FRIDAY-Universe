# TASK-STR-043 — Stratex forward-window fill-ledger reconciliation, 2026-11-16 to 2026-11-23 (evidence)

- **Assignment:** Muse (coordinator) — drafted in the 2026-11-23 ~11:47 IST pool refill; assigned to Muse 2 in watch 7095390023; re-slotted to Muse 4 in watch 7100914561 (~18:15 IST, Muse 2 double-CLAIMED since 14:26 IST, no status); board record on main CLAIMED, owner muse_4 (coordinator consolidated board PR #1504, merged 19:11:57 IST, merge 3e8a4a14).
- **Claim:** hub #1483 comment 7103443188, 2026-11-23 ~19:35 IST.
- **Branch:** `muse4/task-str-043-forward-window-fill-ledger`, base main `3e8a4a14`.
- **Branch decision (per the record's next_action): RESTART from main — nothing to reuse.** Branch `muse2/task-str-043-forward-window-fill-ledger` @ `c97dacff` was checked first-hand via the compare API: 0 commits ahead of main, merge-base = its own head (it is the old main commit, PR #1465 merge), no files changed, no open PR. Muse 2 never committed any work to it.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written.
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, PR #1503) run live on Server 1 for 2026-11-23. Run at 2026-11-23T14:07:50Z / 19:37:50 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-23.json` on S1. S1 checkout was at `ecc401a1` (PR #1503 merge) when the run happened — the reconciler is the merged STR-044 job, unchanged by #1504 (board-only). The task window below is the exact 2026-11-16 → 2026-11-23 slice (IST bounds) of the same ledger, computed from the live ledger in the same run.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−0.0001 USDT** against a tolerance of 10.56 USDT; no matched row disagrees with the venue by more than $0.50.

## §1 — Window numbers (2026-11-16 → 2026-11-23)

| Figure | Value |
|---|---|
| Ledger closes in window | 69 rows |
| Ledger window net P&L | **−34.3752 USDT** (Binance Futures −34.3274 + OANDA USDJPY correction −0.0478) |
| Ledger window fees | 2.8869 USDT |
| Venue closes in window | 103 orders |
| Venue window true net P&L | −7.7825 USDT (= ledger window net −34.3752 + missing closes +26.5927) |
| Venue closes with no ledger row | 34 orders, +26.5927 USDT realised (§3) |
| Ledger rows total (all time) | 78 (net +160.6847, gross +173.2981, fees 12.6134) |
| Rows outside the window | 9, all 2026-11-14 (pre-forward-window; §4) |
| Open positions at run time | 27, unrealised +29.2981 USDT |
| Venue account at run time | wallet 10,528.64, margin 10,557.52, available 9,501.14 USDT (USDT 4,986.54 + USDC 5,000 + BTC 0.01) |
| Venue income since the 2026-11-14 reset | REALISED_PNL −4.8478, COMMISSION −8.7459, FUNDING_FEE −0.6599, TRANSFER +15,000.03 |

**Window identity (LEDGER-001 §6, whole post-reset period):** venue realised −4.8479 = ledger window net (Binance) −34.3274 + missing closes +26.5927 + ledger window fees 2.8869 → expected −4.8478, **residual −0.0001**, status RECONCILED. The forward window and the task window coincide on the ledger: no ledger row falls between the forward-window start (2026-11-15T11:29:49+05:30) and 2026-11-16T00:00 IST, and all 9 excluded rows are 2026-11-14.

## §2 — Net P&L by symbol (window, 69 closes)

| Symbol | Net P&L | Symbol | Net P&L | Symbol | Net P&L |
|---|---|---|---|---|---|
| AAVEUSDT | 0.0000 | DOGEUSDT | −5.2915 | OPUSDT | 0.0000 |
| ADAUSDT | −20.6330 | DOTUSDT | +10.9385 | SANDUSDT | +10.1942 |
| ALGOUSDT | +8.6163 | ETCUSDT | −10.1619 | SOLUSDT | −21.4791 |
| APTUSDT | 0.0000 | ETHUSDT | −20.3867 | SUIUSDT | −14.0632 |
| ARBUSDT | 0.0000 | FILUSDT | 0.0000 | TRXUSDT | 0.0000 |
| ATOMUSDT | +20.6429 | HBARUSDT | +10.0176 | UNIUSDT | +10.1544 |
| AVAXUSDT | −20.6058 | INJUSDT | 0.0000 | USDJPY | −0.0478 |
| BCHUSDT | 0.0000 | LINKUSDT | +1.8418 | VETUSDT | +20.2573 |
| BNBUSDT | 0.0000 | LTCUSDT | 0.0000 | XLMUSDT | 0.0000 |
| BTCUSDT | +8.0792 | MANAUSDT | 0.0000 | XRPUSDT | −21.5439 |
| NEARUSDT | −0.9046 | | | **Total** | **−34.3752** |

Zero-net symbols are the Nov-19 reset-wiped rows (§4): their positions were wiped by the faucet reset and re-entered, so the ledger carries them at 0.0 with fallback exit times.

## §3 — Fills and closes vs the venue

- **Ledger closes (69):** every row above (§5 table). 37 of the 76 Binance rows match venue fills on both entry and exit legs (**BOTH**); 39 match neither (**NO_MATCH**) — 30 reset-wiped 0.0 rows (fallback exit times, match nothing by design) + 9 pre-window Nov-14 rows. No ENTRY_ONLY / EXIT_ONLY rows. **Diffs over $0.50: none.** Matched exit realised −31.4406 vs matched ledger net −34.3274 — the 2.8868 gap is exactly the ledger window fees. The 2 OANDA USDJPY rows are not venue-matched (different venue) by design. 67/78 ledger rows carry no `order_id`; row-to-venue traceability rests on price/qty/time matching (G-trace).
- **Venue closes (103):** 69 are the ledger closes; **34 have no ledger row (+26.5927 USDT realised)**. 30 of them are the Nov-19 07:56Z post-reset micro-closes (one per symbol, realised −0.0055 to −0.17 each — the reset-wipe close fills, also the reason those ledger rows are 0.0). The other 4 are real closes the daemon never recorded:
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2026-11-20T19:14:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 2026-11-21T06:16:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 2026-11-22T12:16:35Z
  - Per-symbol rollup of all 34: SUI +30.4595 (2), ETH +19.9010 (2), SAND −11.3637 (2), VET −10.9567 (2), INJ −0.1700 (1), all other symbols −0.02 to −0.10 (1 each).
- **Venue fills:** 91 unmatched zero-realised fills (entry legs of open/re-entered positions — expected, they realise nothing until they close). The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.

## §4 — Rows outside the window (9, all 2026-11-14, correctly excluded)

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

These predate the forward window (and the 2026-11-14T13:03:53Z owner reset); the ledger total +160.6847 over 78 rows includes them, the window net −34.3752 does not. By lane over all 78 rows: `(none)` 44 rows +254.9989, `FORWARD_TEST` 34 rows −94.3142.

## §5 — All 69 window closes (ledger, exit time UTC, net USDT, reason)

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

No closes on 2026-11-22 in the ledger (the only Nov-22 venue event is the SAND missing close, §3). The three 2026-11-23 closes (AVAX, ADA, DOT) landed after the STR-AUDIT-001 final read (13:42:51Z) and are captured here.

**AVAX note (STR-AUDIT-001 follow-through).** The AVAXUSDT SHORT closed 2026-11-23T13:57:01Z on its stop, net −10.0548 — ~19 minutes after the audit's final read and ~49 minutes after the missing stop was re-placed at 6.824 in the audit. The re-placed stop did exactly what it was for: the position exited on the judged stop instead of running unprotected. No further action.

## Gaps / follow-ups

- **G1 — 4 real venue closes have no ledger row** (ETH +19.9399, SUI +30.5009, VET −10.9206, SAND −11.3252; Nov 20–22). The daemon never recorded them, so the fill ledger is incomplete as a close record even though the books still reconcile — the reconciler adds their realised P&L back in the identity. Fix owed (not in this task's scope): find why those 4 closes were never written to the ledger (the 30 reset-wipe rows are understood; these 4 are not reset-related).
- **G-trace — 67/78 ledger rows carry no `order_id`.** Row-to-venue traceability rests on price/qty/time matching; it held here (0 diffs over $0.50), but an `order_id` on every row would make the next reconciliation exact instead of probabilistic.

## States

- **implemented:** YES — forward-window ledger reconciled end to end against the venue; fills, closes and net P&L filed above.
- **tested:** YES — live reconciler run on S1 (exit 0, status RECONCILED, residual −0.0001); numbers re-derived from the live ledger in the same run.
- **merged:** NO — work PR open for review (merge by Muse).
- **deployed:** N/A — no code change; the work ran the already-merged STR-044 job (PR #1503) and files evidence only.
- **production-verified:** YES — the reconciliation was read back from the live venue (signed GETs, demo), not assumed from the ledger.
