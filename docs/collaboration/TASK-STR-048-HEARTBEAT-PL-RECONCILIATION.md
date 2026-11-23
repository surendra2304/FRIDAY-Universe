# TASK-STR-048 — Stratex heartbeat P&L (+130.27) vs move-verified P&L (+140.90) reconciliation (evidence)

- **Assignment:** Muse (coordinator) — drafted in watch 7108903950 (2026-11-23 ~23:10 IST, pool floor 10); named as Muse 4's corrected next task in watch 7112708807 and restated in watch 7113514319 (~02:40 IST): "FUT-019 is merged — TASK-STR-048 is now claimable. Claim it (hub claim comment + branch push) and start work."
- **Claim:** hub #1483 comment 7113770615, 2026-11-24 ~02:26 IST. Board record verified AVAILABLE, owner muse_19, pr null, branch null on main 855f2515 (board blob c217c91c, verified first-hand this run before claiming); the owner flip to muse_4 rides in this PR, per the standing no-claim-PR pattern. The coordinator's board PR watch003 flip (STR-048 owner Muse 4) is the same change.
- **Branch:** `muse4/task-str-048-heartbeat-pl-reconciliation`, base main `855f2515`.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). Read-only throughout — signed GETs only (`/fapi/v1/userTrades` via the merged STR-044 reader); no order placed, cancelled or modified; the ledger was never written.

## Verdict

**RECONCILED — the gap is timing, not a miss or a double-count.** The two figures are the same running counter read at two moments straddling exactly one close:

| Figure | Value (USDT) | What it is |
|---|---|---|
| Move-verified | +140.89575037 | Counter value immediately **before** the ALGOUSDT close (2026-11-23 11:59:12Z) |
| Heartbeat (`daemon_heartbeat.json` + `realized_pnl.json`, read 2026-11-23 13:42:51Z) | +130.27280441 | Counter value **after** that close |
| Difference | **10.62294596** | Exactly \|ALGOUSDT close net\| — the single close that landed between the two reads |

Both figures decompose, to 8 decimals, as **carried pre-reset baseline 134.79416134 + post-reset fill-ledger nets** (see §1). The heartbeat missed no close and double-counted none relative to the move-verified ledger: the trade-by-trade table in §2 lists all 64 post-reset closes, and the only row between the two snapshots is the ALGO close. Recomputing the move-verified total at the audit read gives 130.27280441 — the two sources agree afterwards, exactly. Re-checked live this run: the heartbeat now reads 78.53277575 (2026-11-23 20:59:56Z) and the same construction gives 134.79416134 + (−56.26138559) = 78.53277575 — still exact after 5 further closes.

## §1 — The construction (baseline + post-reset ledger nets)

**Counter mechanism (code, live on S1).** `Stratex/autonomy/multi_venue_engine.py`: `update_realized_pnl` (lines 1038–1044) and `book_reconciled_pnl` (lines 1046–1055) each do `self.realized_pnl += net; self.daily_realized_pnl += net`, then `save_state()` persists to `Stratex/state/realized_pnl.json`; the state is restored from that file on start (lines 541–576). The counter is therefore a persisted running total, incremented once per close by the broker-side net. It survived the 2026-11-19 faucet reset with its value intact (the reset wiped positions, not the state file) — hence a carried baseline.

**Baseline identification (three independent anchors, all from live reads).**

| Anchor | Heartbeat read | Post-reset ledger sum to that moment | Implied baseline |
|---|---|---|---|
| LEDGER-001 read, 2026-11-22 ~14:29 IST | 151.62 (reported to 2dp) | +16.82537823 | 134.7946 (within the 2dp rounding) |
| Audit read, 2026-11-23 13:42:51Z | 130.27280441 | −4.52135693 | **134.79416134** |
| This run, 2026-11-23 20:59:56Z | 78.53277575 | −56.26138559 | **134.79416134** |

The audit→now step is exactly the 5 closes in between (AVAX −10.05484520, ADA −10.19941296, DOT −9.55176745, ATOM −10.57263049, ADA −11.36137256 = −51.74002866; 130.27280441 − 51.74002866 = 78.53277575). The Nov-22 anchor agrees to the rounding of the reported figure. One fixed baseline explains all three reads — the counter and the ledger move together 1:1 over the whole post-reset window.

**The two named figures, constructed:**

- Move-verified: 134.79416134 + Σ post-reset ledger nets for the 63 rows exited by 11:59:12Z (+6.10158903) = **+140.89575037**.
- Heartbeat at audit: 134.79416134 + Σ post-reset ledger nets for the 64 rows exited by 13:42:51Z (−4.52135693) = **+130.27280441**.
- The 63-row and 64-row sets differ by exactly one row: ALGOUSDT, exit 2026-11-23T11:59:12.956Z, net −10.62294596. No other row exited between 11:59:12Z and 13:42:51Z (next close after ALGO is AVAX 13:57:01Z).

**Daily counter cross-check.** `daily_realized_pnl` at the audit read was −21.34673516 = SOL −10.72378920 + ALGO −10.62294596 exactly — the heartbeat's daily counter absorbed both of the day's closes, and only those two.

## §2 — Trade-by-trade table (all 64 post-reset closes to the audit read)

Window: exit > 2026-11-19T07:35:00Z (faucet reset) and ≤ 2026-11-23T13:42:51Z (audit read). Baseline 134.79416134. The 30 rows at 07:36–07:42Z on Nov 19 are the known reset-wipe rows, recorded at net 0.0 by design (STR-043 §3); they contribute 0.00 to both sums. The running counter column is the heartbeat value implied after each close — the final row lands on 130.27280441, the heartbeat figure; the row before ALGO lands on 140.89575037, the move-verified figure.

| Exit (UTC) | Symbol | Side | Qty | Net (USDT) | Running post-reset sum | Heartbeat counter (baseline + sum) |
|---|---|---|---|---|---|---|
| 2026-11-19T07:36:39Z | TRXUSDT | SHORT | 521.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:41Z | MANAUSDT | LONG | 838.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:44Z | FILUSDT | LONG | 51.9 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:47Z | DOTUSDT | LONG | 60.3 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:49Z | ETHUSDT | LONG | 0.036 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:51Z | SUIUSDT | LONG | 60.9 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:53Z | BCHUSDT | LONG | 0.245 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:55Z | INJUSDT | LONG | 5.1 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:36:58Z | ETCUSDT | LONG | 9.12 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:00Z | LTCUSDT | LONG | 1.221 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:02Z | ATOMUSDT | LONG | 34.56 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:05Z | XRPUSDT | LONG | 61.9 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:07Z | LINKUSDT | LONG | 5.52 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:10Z | VETUSDT | LONG | 9666.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:12Z | NEARUSDT | LONG | 10.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:15Z | AAVEUSDT | LONG | 0.3 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:17Z | BTCUSDT | LONG | 0.0014 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:19Z | SOLUSDT | LONG | 0.57 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:21Z | APTUSDT | LONG | 74.5 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:23Z | AVAXUSDT | LONG | 6.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:25Z | UNIUSDT | LONG | 6.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:28Z | BNBUSDT | LONG | 0.14 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:30Z | DOGEUSDT | LONG | 946.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:31Z | XLMUSDT | LONG | 401.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:33Z | OPUSDT | LONG | 153.1 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:35Z | HBARUSDT | LONG | 921.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:37Z | ALGOUSDT | LONG | 580.8 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:39Z | ADAUSDT | LONG | 295.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:40Z | SANDUSDT | LONG | 779.0 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T07:37:42Z | ARBUSDT | LONG | 257.2 | +0.00000000 | +0.00000000 | +134.79416134 |
| 2026-11-19T21:16:49Z | BTCUSDT | LONG | 0.0054 | -10.07090647 | -10.07090647 | +124.72325487 |
| 2026-11-19T22:12:27Z | NEARUSDT | LONG | 43.0 | -10.67543800 | -20.74634447 | +114.04781687 |
| 2026-11-20T01:59:07Z | ETHUSDT | LONG | 0.152 | -10.20546547 | -30.95180994 | +103.84235140 |
| 2026-11-20T01:59:09Z | ETCUSDT | LONG | 43.56 | -10.16190331 | -41.11371325 | +93.68044809 |
| 2026-11-20T01:59:10Z | LINKUSDT | LONG | 27.15 | -10.95561144 | -52.06932469 | +82.72483665 |
| 2026-11-20T02:26:00Z | DOGEUSDT | LONG | 4178.0 | -10.20611867 | -62.27544336 | +72.51871798 |
| 2026-11-20T02:32:22Z | SUIUSDT | LONG | 300.5 | -10.66133132 | -72.93677468 | +61.85738666 |
| 2026-11-20T04:38:30Z | SANDUSDT | LONG | 6286.0 | -10.83706400 | -83.77383868 | +51.02032266 |
| 2026-11-20T12:08:45Z | ADAUSDT | LONG | 1311.0 | -10.43356728 | -94.20740596 | +40.58675538 |
| 2026-11-20T13:33:45Z | SOLUSDT | LONG | 2.69 | -10.75534092 | -104.96274688 | +29.83141446 |
| 2026-11-20T13:36:04Z | AVAXUSDT | LONG | 30.0 | -10.55095200 | -115.51369888 | +19.28046246 |
| 2026-11-20T15:24:30Z | DOTUSDT | SHORT | 364.3 | +20.49025993 | -95.02343895 | +39.77072239 |
| 2026-11-20T15:48:18Z | ATOMUSDT | SHORT | 201.36 | +20.64294394 | -74.38049501 | +60.41366633 |
| 2026-11-20T17:40:11Z | ALGOUSDT | SHORT | 3299.5 | +19.23926572 | -55.14122929 | +79.65293205 |
| 2026-11-21T03:05:40Z | NEARUSDT | SHORT | 44.0 | +20.52980560 | -34.61142369 | +100.18273765 |
| 2026-11-21T03:30:42Z | HBARUSDT | SHORT | 4160.0 | +20.84141696 | -13.77000673 | +121.02415461 |
| 2026-11-21T03:32:15Z | SANDUSDT | SHORT | 6457.0 | +21.03127550 | +7.26126877 | +142.05543011 |
| 2026-11-21T03:32:59Z | DOGEUSDT | SHORT | 4189.0 | +15.70290216 | +22.96417093 | +157.75833227 |
| 2026-11-21T03:33:34Z | XRPUSDT | LONG | 98.3 | -10.81797398 | +12.14619695 | +146.94035829 |
| 2026-11-21T03:34:37Z | VETUSDT | SHORT | 46011.0 | +20.25726297 | +32.40345992 | +167.19762126 |
| 2026-11-21T04:05:09Z | BTCUSDT | SHORT | 0.0054 | +28.48408611 | +60.88754603 | +195.68170737 |
| 2026-11-21T04:05:10Z | UNIUSDT | SHORT | 31.0 | +20.49987840 | +81.38742443 | +216.18158577 |
| 2026-11-21T04:06:36Z | LINKUSDT | SHORT | 27.13 | +20.85659369 | +102.24401812 | +237.03817946 |
| 2026-11-21T13:08:02Z | SUIUSDT | SHORT | 80.0 | -3.40188776 | +98.84213036 | +233.63629170 |
| 2026-11-21T13:25:12Z | BTCUSDT | SHORT | 0.0032 | -10.33396404 | +88.50816632 | +223.30232766 |
| 2026-11-21T13:36:31Z | ETHUSDT | SHORT | 0.129 | -10.18123986 | +78.32692646 | +213.12108780 |
| 2026-11-21T13:36:32Z | LINKUSDT | SHORT | 16.74 | -8.05914489 | +70.26778157 | +205.06194291 |
| 2026-11-21T13:36:34Z | UNIUSDT | SHORT | 30.0 | -10.34546400 | +59.92231757 | +194.71647891 |
| 2026-11-21T13:38:35Z | DOGEUSDT | SHORT | 3489.0 | -10.78826712 | +49.13405045 | +183.92821179 |
| 2026-11-21T13:39:21Z | HBARUSDT | SHORT | 3595.0 | -10.82376848 | +38.31028197 | +173.10444331 |
| 2026-11-21T13:49:41Z | XRPUSDT | SHORT | 222.2 | -10.72593174 | +27.58435023 | +162.37851157 |
| 2026-11-21T13:52:33Z | NEARUSDT | SHORT | 42.0 | -10.75897200 | +16.82537823 | +151.61953957 |
| 2026-11-23T09:05:57Z | SOLUSDT | SHORT | 2.45 | -10.72378920 | +6.10158903 | +140.89575037 |
| 2026-11-23T11:59:12Z | ALGOUSDT | SHORT | 962.8 | -10.62294596 | -4.52135693 | +130.27280441 |

## §3 — Venue verification of the four key closes

Read live from demo-fapi with the merged STR-044 reader (`DemoFuturesReader`, signed GET `/fapi/v1/userTrades` only). Each ledger net below is reproduced from the venue's own fills — entry leg and exit leg, quantities, VWAP, broker commission — to 8 decimals. (Ledger rows carry no `order_id` — 67/78 at the STR-044 run — so matching is by symbol + side + qty + price + time, the STR-043/STR-044 method.)

| Close | Ledger net | Venue fills (exit leg) | Venue net from fills | Match |
|---|---|---|---|---|
| **ALGOUSDT** SHORT 962.8, entry 0.07247, exit 2026-11-23 11:59:12.956Z | −10.62294596 (gross −10.5908, fees 0.03214596) | 1 BUY fill, order 431585753, 962.8 @ 0.08347, realized −10.5908, comm 0.03214596, 11:57:59.067Z | −10.62294596 | Exact |
| **SOLUSDT** SHORT 2.45, entry 68.19195918367, exit 2026-11-23 09:05:57.820Z | −10.72378920 (gross −10.6527, fees 0.0710892) | 1 BUY fill, order 4249869822, 2.45 @ 72.54, realized −10.6527, comm 0.0710892, 09:05:56.087Z | −10.72378920 | Exact |
| **ADAUSDT** SHORT 1329, entry 0.1397, exit 2026-11-23 13:58:24.026Z | −10.19941296 (gross −10.1211, fees 0.07831296) | 2 BUY fills, order 1342291233, 102 @ 0.1463 + 1227 @ 0.1474, VWAP 0.1473155756, realized −10.1211, comm 0.07831296 | −10.19941296 | Exact |
| **NEARUSDT** SHORT 44, entry 3.206, exit 2026-11-21 03:05:40.111Z | +20.52980560 (gross +20.578, fees 0.0481944) | 2 BUY fills, order 663437400, 10 @ 2.736 + 34 @ 2.739, VWAP 2.7383181818, realized +20.578, comm 0.0481944 | +20.52980560 | Exact |

Entry legs confirmed for all four (ALGO SELL 962.8 @ 0.07247, order 430563530; SOL SELL 0.24 @ 68.21 + 2.21 @ 68.19, order 4248528781 — VWAP 68.19195918, which is why the ledger stores the entry at full precision; ADA SELL 1329 @ 0.13970, order 1341082038; NEAR SELL 44 @ 3.2060, order 662962656). The ADA and NEAR closes were executed as two fills each — the stored exit price is one fill's price, so a single-price recomputation looks off by $0.11 / $0.03; the two-fill VWAP reproduces the ledger net exactly (§4).

## §4 — Price-move recomputation of the whole ledger (80 rows)

Every ledger row's gross was recomputed from its stored entry/exit prices and qty, and its net as gross − fees. 47/80 rows reproduce exactly (≤ $0.01); 33 differ by more than $0.01, all explained:

- **30 rows — the Nov-19 07:36–07:42Z reset-wipe rows.** Recorded net 0.0 by design (positions wiped by the faucet reset, fallback exit times; STR-043 §3). A price-move recomputation gives small nonzero values (−0.08 to −2.80 each). They are in the counter window but contribute 0.00 to both figures, so they cannot move the gap. Their venue counterparts are the 30 post-reset micro-closes (see §5).
- **1 row — USDJPY (OANDA, exit 2026-11-17).** A forex pair: the (exit−entry)×qty formula does not apply (rates, not USDT prices; the row's net −0.0478 is the broker figure). It predates the reset and is outside the counter window either way.
- **2 rows — ADA 2026-11-23 13:58Z and NEAR 2026-11-21 03:05Z.** Split fills (§3): the stored exit price is one fill's price, not the VWAP. Two-fill VWAP reproduces the ledger net exactly ($0.1122 and $0.0300 apparent gaps explained, not errors).

No row is missed by the heartbeat relative to the ledger and none is double-counted: the counter's step at each of the 64 window closes equals that row's ledger net (three-anchor proof, §1).

## §5 — Scope boundary: what this reconciliation does and does not cover

- **This task** reconciles the two named figures — heartbeat vs move-verified. Both are built from the same ledger (baseline + post-reset ledger nets); the gap is one close's timing. Verdict: reconciled, no defect, no missing rows between the two sources.
- **Not this task — the ledger-vs-venue gap (STR-043 G1, already filed).** The counter is ledger-derived, not venue-derived: it only ever adds ledger nets. It therefore inherits the ledger's known blind spot — 34 venue closes with no ledger row, +26.5927 USDT (30 Nov-19 micro-closes, −1.6023, plus 4 real closes: ETH +19.9399 on 2026-11-20, SUI +30.5009 on 2026-11-21, VET −10.9206 on 2026-11-21, SAND −11.3252 on 2026-11-22). That gap is real, but it is between the ledger and the venue — it affects both named figures equally and is not the gap this task was asked to explain. Proof the counter excludes the missing closes: hypothesise the counter included them, and the implied baseline would be 96.88 at the Nov-22 anchor but 108.20 at the audit — inconsistent by exactly the SAND close (−11.3252) that landed between the anchors. The ledger-only baseline (134.79416134) is the only one consistent at all three anchors. LEDGER-001 G6 ("`realized_pnl.json` understates venue realized") is the same statement, now proven from the counter's own history.
- **O1 from the audit (counter scope undocumented) is closed by this doc:** counter = 134.79416134 carried pre-reset value + post-reset ledger nets; the ledger total (+190.49068657 at the audit read, 75 rows) additionally contains the 3 LEGACY-UNATTRIBUTED rows (+195.7066), 9 Nov-14 attributed rows and 2 OANDA rows, all pre-reset, which never entered the counter. The counter's scope and the ledger's scope are different by design, and the difference is now written down with the numbers.

## States

- **implemented:** YES — trade-by-trade reconciliation complete, evidence filed here.
- **tested:** YES — all figures re-derived live from S1 state and re-verified against venue fills this run (probes 1–4: heartbeat + realized_pnl + ledger reads, three-anchor baseline check, 4 venue fill-level verifications).
- **merged:** NO — work PR open for review (merge by Muse).
- **deployed:** N/A — no code change; read-only reconciliation.
- **production-verified:** YES — the four key closes were read back from the live venue (fills, order IDs, commissions), not assumed from the placement or the ledger.
