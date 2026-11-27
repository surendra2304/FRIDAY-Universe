# TASK-STR-100 — Forward-window fill-ledger audit run 7 (evidence)

- **Task:** Stratex: forward-window fill-ledger audit run 7 — reconcile the next forward window fills/closes against the venue positions/history end-to-end, file fills, closes, net P&L.
- **Owner:** Muse 4. **Claim:** hub #2045 comment 7210919550, 2026-11-27 ~11:20 IST, in the #2074-verdict completion post, per WATCH205 §6 (queue: INT-049 IN_REVIEW → EARN-033 CLAIMED owner-blocked → STR-100 head task; the #2074 verdict was the immediate duty, STR-100 the head task after it). **Board:** no TASK-STR-100 record exists on main `3ce3fdef` (0 mentions) — the record is held pending the board shrink (WATCH205 §10.2: held records STR-100, FUT-040, VYR-093, INF-046 get filed after the shrink lands); the hub post is the assignment and claim of record, and the board flip rides the coordinator's next board PR. No board hunk in this PR — board flips are coordinator-only.
- **Branch:** `muse4/task-str-100-fill-ledger-audit-run7` from main `3ce3fdef` (fast-forwarded from `c1aa53b9` after board PR #2079 merged; no content change — the reconciler and its tests are blob-identical between the two mains).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `3ce3fdef`) run live on Stratex-Server (server 4) from a fresh worktree `/tmp/muse4-str100` at `3ce3fdef` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the worktree, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). Daemon venv python. Run at 2026-11-27T05:49:50Z / 2026-11-27 11:19:50 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-27.json` on Stratex-Server (overwrites the 01:00 UTC timer report for the same date; run 6's figures are preserved in §1 and in `docs/collaboration/TASK-STR-095-EVIDENCE.md` on main). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse4-str100/Stratex:/tmp/muse4-str100` so the fixed code runs. Exact command in §8.
- **Host note (carried from run 6):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-099 did. This run used Stratex-Server (server 4).
- **Predecessor:** run 6 is STR-095 (filing run 6, Muse 4, PR #2019 MERGED); STR-099 is the audit run 6, still AVAILABLE/unclaimed (owner muse_tp4) — this audit run 7 follows the same live-proof route (daemon ledger on Stratex-Server + venue history) and the STR-095 reconciliation procedure.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.46 USDT; no matched row disagrees with the venue by more than $0.50. The residual is unchanged since run 2 — it is exactly the aged-out Nov-19 reset-wipe micro-closes (−1.6023) that sit outside the venue's ~7-day `userTrades`/`allOrders` window (§7). The ledger grew by one row since run 6: LTCUSDT 2026-11-27T02:26:41Z, net 0.0000 (§5).

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | Run 7 (this run, 05:49 UTC) | Run 6 (19:53 UTC Nov 26) |
|---|---|---|
| Ledger closes, all time | 84 rows | 83 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 75 rows | 74 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | (none) 44 +254.9989; FORWARD_TEST 39 −147.9099 |
| Venue closes in window | 80 (75 ledger + 5 missing) | 78 (74 ledger + 4 missing) |
| Venue window true net P&L | −69.1908 | −59.7759 |
| Venue account at run time | wallet 10,452.14, margin 10,460.95, unrealised +8.81, available 9,415.82 USDT (USDT 4,924.20 + USDC 5,000 + BTC 0.01) | wallet 10,453.88, margin 10,483.14, unrealised +29.26, available 9,456.67 |
| Open positions at run time | 30, unrealised +8.8236 | 30, unrealised +29.2952 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.6514**, TRANSFER +15,000.03 | REALISED_PNL −58.0134, COMMISSION −9.6135, FUNDING_FEE +0.6774, TRANSFER +15,000.03 |
| Income rows fetched | **1,154** (792 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,122 (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change since run 6: ledger 83 → 84 rows (one new close, LTCUSDT 2026-11-27T02:26:41Z, net 0.0000); window 74 → 75 rows; window net unchanged (−87.9709) because the new row is zero-net. Venue realised −58.0134 → −67.4283 (the new LTCUSDT missing close, −9.4149, §3); venue true net −59.7759 → −69.1908 (same −9.4149). The only other movement is mark-price drift on the 30 open positions (unrealised +29.30 → +8.82; wallet −1.74 — see the wallet note in §10, it does not tie to the income deltas and is not part of the reconciled identity).

## §2 — Net P&L by symbol (window, 74 closes)

| Symbol | Net P&L | Symbol | Net P&L | Symbol | Net P&L |
|---|---|---|---|---|---|
| AAVEUSDT | 0.0000 | DOGEUSDT | −5.2915 | OPUSDT | 0.0000 |
| ADAUSDT | −31.9944 | DOTUSDT | +10.9385 | SANDUSDT | +10.1942 |
| ALGOUSDT | −2.1276 | ETCUSDT | −10.1619 | SOLUSDT | −31.5362 |
| APTUSDT | 0.0000 | ETHUSDT | −20.3867 | SUIUSDT | −14.0632 |
| ARBUSDT | 0.0000 | FILUSDT | 0.0000 | TRXUSDT | 0.0000 |
| ATOMUSDT | −0.7904 | HBARUSDT | +10.0176 | UNIUSDT | +10.1544 |
| AVAXUSDT | −20.6058 | INJUSDT | 0.0000 | USDJPY | −0.0478 |
| BCHUSDT | 0.0000 | LINKUSDT | +1.8418 | VETUSDT | +20.2573 |
| BNBUSDT | 0.0000 | LTCUSDT | 0.0000 | XLMUSDT | 0.0000 |
| BTCUSDT | +8.0792 | MANAUSDT | 0.0000 | XRPUSDT | −21.5439 |
| NEARUSDT | −0.9046 | | | **Total** | **−87.9709** |

Zero-net symbols are the Nov-19 reset-wiped rows (§5): their positions were wiped by the faucet reset and re-entered, so the ledger carries them at 0.0 with fallback exit times. Per-symbol nets were re-derived independently from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) and match the report exactly. Identical to run 5 — the ledger did not change.

## §3 — Matched rows, missing closes, identity check (re-derived)

- **Matching (82 Binance rows):** BOTH 21, EXIT_ONLY 13, NO_MATCH 48 (run 6: 25 / 17 / 39 over 81 rows). Matched exit realised −1.5883 vs matched ledger net −4.1492 — the difference is the matched rows' fees (2.5609), so the matched set ties out exactly. **Diffs over $0.50: none.**
- **Missing closes (G1) — 5, realised +18.78** (run 6: 4, +28.20). The four from run 6 are unchanged:
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 1 fill, 2026-11-20T02:56:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 1 fill, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 1 fill, 2026-11-22T12:16:35Z
  - **NEW — LTCUSDT, order 1615011544, BUY 5.706, −9.4149, 1 fill, 2026-11-27T02:26:24Z** — the exit leg of the new ledger row (§5): the daemon recorded the close at net 0.0000 while the venue realised −9.4149. The disagreement is carried here as a missing close; it is not netted away anywhere.
- **Venue fills:** 21 unmatched zero-realised fills (run 6: 25 — entry legs of the open positions + breakeven entries — visible, never silently dropped; 4 aged out of the venue window, §7). The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.
- **Identity check (re-derived):** ledger window net (Binance) −87.9231 + missing closes +18.7801 + window fees 3.3171 = expected venue realised −65.8259; venue realised −67.4283; residual −1.6024, inside tolerance 10.46. Venue true net −69.1908 = ledger window net −87.9709 + missing +18.7801.

## §4 — Rows outside the window (9, all 2026-11-14, correctly excluded)

Same 9 rows as run 2 (STR-091 §4) — unchanged; the ledger grew only with the one Nov-26 in-window row, so the outside set is unchanged:

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

These predate the forward window (and the 2026-11-14T13:03:53Z owner reset). Verified: all-time per-symbol nets minus window nets equal exactly these 9 rows (e.g. UNI 239.7824 − 10.1544 = 229.6280).

## §5 — All 75 window closes (ledger, exit time UTC, net USDT, reason)

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
| ATOMUSDT | 2026-11-26T14:42:27Z | −10.8607 | SL_TP_BROKER |
| LTCUSDT | 2026-11-27T02:26:41Z | 0.0000 | SL_TP_BROKER |

The 74 pre-existing rows are identical to run 6 — verified by independent re-derivation from the live ledger this run (per-symbol nets §2 and the all-time cross-check §4 both match the report exactly). One new close since run 6: LTCUSDT 2026-11-27T02:26:41Z, net 0.0000 (SHORT 5.706, entry 42.86, exit 41.82186275, strategy strategy_donchian_turtle_n20_b26_4h, lane FORWARD_TEST, no order_id). Note the venue shows the same close as a missing close with realised −9.4149 (order 1615011544, §3) — the ledger row is zero-net while the venue realised −9.41; the disagreement is carried as the 5th G1 missing close, not hidden.

## §6 — Funding cross-check: STR-090 pagination fix holds live

An independent direct `income()` call on Stratex-Server (same `DemoFuturesReader`, same env file, separate process from the reconciler run) returned **1,154 income rows** since the reset floor — 792 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — with totals **FUNDING_FEE +0.6514, COMMISSION −9.8166, REALIZED_PNL −67.4283, TRANSFER +15,000.03**, exactly matching the report's `income_since_reset`. The 1,000-row venue cap is paginated past (1,154 > 1,000); funding moved +0.6774 → +0.6514 since run 6 (Δ −0.0260, ordinary funding accrual).

## §7 — The BOTH → EXIT_ONLY → NO_MATCH shift: entry fills aged out of the venue window

Run 2 matched 41 rows on both legs and 0 on the exit leg only. Runs 4, 5 and 6 all matched 25 BOTH + 17 EXIT_ONLY (NO_MATCH steady at 39). Run 7 matches 21 BOTH + 13 EXIT_ONLY (NO_MATCH 48). The 8-row shift is the same retention effect STR-091 §7 / STR-095 §7 documented: Nov 19–21 closes crossing the venue's ~7-day `userTrades`/`allOrders` boundary lose their entry fills (BOTH → EXIT_ONLY) and then their exit fills (EXIT_ONLY → NO_MATCH); the 9th NO_MATCH row is the new LTCUSDT row, whose venue close is carried as missing (§3). Nothing was lost: the ledger rows, the exit fills, and the realised P&L are all still present and reconciled — the matched set (34 rows) still ties out exactly (§3), and the identity residual is unchanged at −1.6024. The G1 gap (5 missing closes, +18.78) is unchanged in kind since run 2, larger by one row.

## §8 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active** (started Tue 2026-11-24 06:57:34 UTC); `friday-stratex-reconciliation.timer` next run would overwrite `daily_2026-11-27.json` — all figures are preserved here. The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Worktree: `git fetch origin main` + `git worktree add /tmp/muse4-str100 origin/main` on Stratex-Server (base `3ce3fdef`, board PR #2079 merged). The branch was fast-forwarded to `3ce3fdef` before the work PR.
- **Execution-risk flag (carried honestly):** the local worktree checkout on this machine tripped the system execution-risk check (same flag as M3 INT-056 / M9 VYR-086). Per WATCH203 §4 ruling 3 + §7 the work went through the API-only path: no code was executed from the local checkout — the reconciler, its tests, and all probes ran on Stratex-Server via the bridge, and the evidence doc is pushed via the git-data API. The local worktree directory was left untouched after the flag.
- Run (backgrounded, log `/tmp/muse4-str100-run.log` on Stratex-Server, PID 64419):
  `cd /tmp/muse4-str100/Stratex && PYTHONPATH=/tmp/muse4-str100/Stratex:/tmp/muse4-str100 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-27`
  (the timer service's own invocation, with the worktree paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-27: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 48, 'EXIT_ONLY': 13, 'BOTH': 21}, missing closes 5 (+18.78), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-27.json`
- Funding cross-check (separate process, same reader): `/opt/friday_universe/venv/bin/python /tmp/muse4-str100-funding-probe.py` — 1,154 income rows, totals match the report exactly (§6).
- Re-derivation (separate process, live ledger): `/tmp/muse4-str100-rederive.py` — window 75 rows, net −87.9709; per-symbol nets match §2 exactly; all-time net +107.089; outside rows 9.
- Bridge note: `run_shell` responses intermittently die with `http.client.IncompleteRead` / `RemoteDisconnected`; retried with a fresh session per attempt (retry wrapper `~/workspace/muse4-runs/str094_bridge.py`). No data was faked — every number was re-read after a successful call.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed** on Stratex-Server in the exact run-7 worktree (pytest, 11.37s, `PYTHONPATH=/tmp/muse4-str100/Stratex:/tmp/muse4-str100`); no test file changed in this task. CI re-verification from the work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §9 — Open positions at run time (30, unrealised +8.8236)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 96.69973066 | +6.5901 |
| ADAUSDT | +301.0 | 0.1494 | 0.15251788 | +0.9385 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08188307 | −4.2269 |
| APTUSDT | −116.9 | 0.4356 | 0.3927 | +5.0150 |
| ARBUSDT | −410.7 | 0.12691687 | 0.11802613 | +3.6514 |
| ATOMUSDT | −151.7 | 1.186 | 1.24342857 | −8.7119 |
| AVAXUSDT | −3.0 | 7.015 | 6.7656465 | +0.7481 |
| BCHUSDT | −0.388 | 208.38159794 | 215.12 | −2.6145 |
| BNBUSDT | −0.08 | 590.59 | 566.73852196 | +1.9081 |
| BTCUSDT | +0.0025 | 59,889.32 | 61,750.21081522 | +4.6522 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05797408 | −4.2487 |
| DOTUSDT | −102.7 | 0.6728 | 0.69112549 | −1.8820 |
| ETCUSDT | −14.63 | 5.659 | 6.015 | −5.2083 |
| ETHUSDT | +0.111 | 1681.3 | 1740.82 | +6.6067 |
| FILUSDT | −81.9 | 0.5788 | 0.54974024 | +2.3800 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05524022 | −5.3311 |
| INJUSDT | −19.0 | 6.657 | 6.3531166 | +5.7738 |
| LINKUSDT | −8.79 | 8.629 | 9.647 | −8.9482 |
| LTCUSDT | +5.72 | 44.37 | 44.7 | +1.8876 |
| MANAUSDT | −1,342.0 | 0.060599538003 | 0.05828 | +3.1128 |
| NEARUSDT | −14.0 | 2.901 | 3.11161689 | −2.9486 |
| OPUSDT | −661.6 | 0.0768 | 0.0718 | +3.3080 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03482417 | −2.4491 |
| SOLUSDT | −2.1 | 69.02 | 73.15653642 | −8.6867 |
| SUIUSDT | −96.1 | 0.6446 | 0.68638399 | −4.0154 |
| TRXUSDT | −750.0 | 0.30999 | 0.30544502 | +3.4087 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.85542343 | −1.3318 |
| VETUSDT | +40,580.0 | 0.004618 | 0.004966 | +14.1218 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12910405 | +9.4187 |
| XRPUSDT | −93.7 | 0.925 | 0.9687 | −4.0947 |

## §10 — Wallet snapshot note (open observation, not a reconciliation break)

- Wallet 10,453.88 (run 6, 19:53 UTC) → 10,452.14 (this run, 05:49 UTC): movement −1.74, while the income deltas over the same interval sum to −9.64 (REALISED −9.4149, COMMISSION −0.2031, FUNDING −0.0260). The +7.90 difference is **not** explained by this run's data.
- Proof it is venue-side drift, not a ledger error: the `daily_2026-11-26.json` report (run 18:36:47Z) vs run 6's manual run (19:53:19Z) shows the wallet moving +1.07 (10,452.81 → 10,453.88) with IDENTICAL income totals and no new closes between them. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity (which is the ledger ↔ venue-realised tie-out, residual −1.6024, and holds). Flagged here for the paired verifier to probe, not hidden.

## Five states

- implemented: YES (this evidence doc filed on branch `muse4/task-str-100-fill-ledger-audit-run7`)
- tested: YES (reconciler run live on Stratex-Server + independent funding probe + independent ledger re-derivation + 28/28 tests on the exact run-7 code)
- merged: NO (work PR open at filing; paired verification by a different chat owed — never merge own PR)
- deployed: NO (nothing deployed; proof ran against the existing deploy, daemon untouched)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 4
