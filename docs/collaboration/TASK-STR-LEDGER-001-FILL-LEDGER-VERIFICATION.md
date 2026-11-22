# TASK-STR-LEDGER-001 — Stratex live fill-ledger verification

- Task: reconcile the S1 daemon fill/close ledger against the venue's positions/history; file the forward-window state (fills, closes, net P&L). Pool-7 item (i).
- Owner: Muse 4. Branch: `muse4/task-str-ledger-001-fill-ledger-verification`. Claim: issue #35 comment 7076835833. Board claim PR #1350 (this PR carries the implementation).
- Venue: Binance Demo Futures, `https://demo-fapi.binance.com` (`BINANCE_ENV=demo`, `BINANCE_TESTNET=false`, `TRADING_MODE=FUTURES`). Demo only — no real money, no live-money action.
- Method: read-only throughout. Ledger + state read from Server 1 (`/opt/friday_universe/Stratex/state/`). Venue read with signed GETs only (`/fapi/v2/account`, `/fapi/v2/positionRisk`, `/fapi/v1/userTrades` x31 symbols, `/fapi/v1/income` all types, `/fapi/v1/allOrders` x31 symbols) via the daemon's own Ed25519 signing scheme. No order placed, cancelled, or modified; no service restarted; no env file changed; no secret copied out (keys were used in-memory on S1 only, never printed or stored).
- Read time: ledger read 2026-11-22 ~14:29 IST (file mtime 2026-11-21 19:22 IST — no new ledger row since); venue account/positions read 2026-11-22 ~14:35 IST; venue trades merged (re-fetch, no startTime) 2026-11-22 ~14:49 IST. Daemon live throughout: `stratex-daemon` active since 2026-11-22 07:44:57 IST, PID 1977654, scanning (heartbeat scan 318 at 09:18Z, 0 signals / 0 executed in the last cycle).

## 1. The ledger, read end to end

File: `Stratex/state/fill_ledger.jsonl` — **73 rows**, all `record_type: FILL`, recorded 2026-11-14T12:41:21Z → 2026-11-21T13:52:33Z. Recorded-to-exit lag 0–0.51 h (no stale backfill).

| Slice | Rows | Net P&L (USDT) |
|---|---|---|
| All rows | 73 | **+211.84** (gross +224.10, fees 12.27) |
| Venue `binance_futures` | 71 | +211.89 |
| Venue `oanda` | 2 | −0.05 |
| Lane `FORWARD_TEST` | 29 | −43.16 |
| No lane | 44 | +255.00 |
| Forward window (exit_time ≥ 2026-11-15T11:29:49+05:30) | 64 (62 binance + 2 oanda) | binance **+16.83**, oanda −0.05 |
| Pre-window | 9 | +195.06 (3 legacy +195.71, 6 testnet −0.65) |

- Wins 15, losses 27, zero-P&L rows 31 (scorecard convention). Exit reasons: `SL_TP_BROKER` 62, `WIN` 4, `OWNER_DIRECTED_CLOSE` 3, `LOSS` 2, `BROKER_CLOSE` 1, `VENUE_CLOSE_CORRECTION` 1.
- Engines: `daemon` 65, `testnet_engine` 6, `oanda_sleeve` 2. Fees sources: `broker` 65, `estimate` 6, `broker_realized_pl_spread_embedded` 2.
- Traceability gap: **62/73 rows carry no `order_id`** (85%), 65/73 no `entry_order_id`. Only the 3 legacy + 6 testnet rows carry order ids.
- The 29 `strategy_dow_effect` rows all book **net_pnl 0.0 / gross 0.0 / fees 0.0** despite non-zero price moves (implied gross from entry/exit prices: **−31.73**), all recorded in one 61-second burst on 2026-11-19 07:36:41–07:37:42Z. They are not measured zeroes (see §3).

Cross-checks that agree with the ledger: `state/scorecard.json` (source: fill ledger only) totals 73 trades, net +211.84, PF 1.855; forward scorecard `ledger_window_net` +16.8254 for 62 binance fills — reproduced exactly from the ledger by exit_time.

## 2. Venue position (live, demo-fapi)

- Account: totalWalletBalance 10561.26, totalMarginBalance 10642.03, totalUnrealizedProfit +80.77, available 9475.45. Assets: USDT wallet 5049.32, USDC 5000.00 (untouched faucet grant), BTC 0.01000000 (untouched faucet grant).
- **30 open positions**, unrealized **+80.89**, all 3x cross-margin (e.g. VETUSDT LONG 40580 @ 0.004618; MANAUSDT SHORT 1342 @ 0.0606; BTCUSDT LONG 0.0025 @ 59889.32). Heartbeat agrees: `open_positions: 30`, unrealized +79.90 at 09:02Z.
- Every open position has a matching `position_tags.jsonl` entry (0 missing). `active_trades.json` is `[]` — stale/empty; the daemon tracks opens via `position_tags.jsonl`, not that file.
- Venue fills retrieved: **295 fills / 193 order groups** across the 31 ledger symbols (first fetch with `startTime` missed 28 recent fills — a startTime-bounded `userTrades` quirk on demo-fapi; re-fetch without `startTime` recovered them). `allOrders`: 190 FILLED orders, **0 filled orders without a matching userTrades fill**.
- Venue income since the Nov-14 reset (714 rows): `REALIZED_PNL` 72 rows **+57.28**; `FUNDING_FEE` 391 rows −0.62; `COMMISSION` 245 rows −8.13; `TRANSFER` 6 rows **+15000.03** (see §3).

## 3. The Nov-19 reset — the finding that explains the scorecard discrepancy

At **2026-11-19 07:35:04–07:35:26Z** the demo-fapi account received **three faucet re-grants: 3 × (5000.00 USDT + 0.01 USDT) = +15000.03 USDT** (`TRANSFER` income rows, tranId 0). Each grant reset the balance: equity snapshots show `binance_futures` equity 4978.13 at 07:01Z → **exactly 5000.00** at 07:36:39Z (one `trigger: fill` snapshot per recorded close, 07:36:39–07:37:42Z). **The reset wiped every open position.**

One minute later the daemon booked **30 "closes" with net_pnl 0.0** (29 `strategy_dow_effect` + 1 `strategy_ichimoku_trend` TRXUSDT) — exit prices are fallback/mark prices, no venue fills exist for any of them (verified order-by-order: the only venue orders in that window are the 07:40 SELLs / 07:56 BUYs below). The scorecard already flags all 30 as `closed_trades_verified: 0`, reason `fallback_exit_time`. The positions were wiped, not closed: their venue-true unrealized at wipe was **−21.08** (segment-A walk, §5), while the ledger's fallback prices imply −33.68 — the ledger overstates that loss by ~12.6.

The daemon journal for 2026-11-19 07:30–08:05Z is unavailable (retention — 1 line in that window), so the daemon's own account of the reset is unrecoverable from logs. No reset boundary was filed for Nov 19 in `scorecard.json` (only the Nov-14 owner reset and the Nov-15 OANDA baseline are recorded).

At 07:40–07:42Z the venue shows 30 SELL market orders (one per symbol) opening SHORTs, and at 07:56Z 30 BUY orders closing them at small losses (realized −0.02…−0.17 each, **−1.53 total**). Those 30 closes have **no ledger rows**. Their intent is not recorded anywhere recoverable — follow-up question, not a blocker for this reconciliation.

## 4. Row-by-row match (order level)

Grouping venue fills by `(symbol, orderId)` and matching on side, qty (±1%), VWAP (±0.5%), time (±24 h for fallback exit times):

| Class | Rows | Meaning |
|---|---|---|
| BOTH (entry + exit orders found) | **32** | incl. all 29 `FORWARD_TEST` rows |
| EXIT_ONLY | 3 | the 3 legacy rows (entries predate venue order history) |
| NO_MATCH | 36 | 6 testnet-engine rows (classic-testnet account, correctly absent from demo-fapi) + 30 Nov-19 reset-wiped rows (no venue fills exist) |
| ENTRY_ONLY | 0 | — |

- Rows whose `order_id` exists on the venue: 3/9 (the 3 legacy ids; the 6 testnet ids belong to the retired account).
- Matched rows (35 with an exit order): venue exit-order realized **+224.36** vs ledger net **+212.53**. Only 3 rows differ by > 0.5 — all legacy, all explained exactly by their commissions (SOL −29.21 vs −33.64 = fee 4.43; UNI +233.95 vs +229.63 = fee 4.33; PAXG +0.24 vs −0.29 = fee 0.53; these three fees sum to 9.29 = the pre-reset commission total). **Every ledger row that has a venue exit order matches the venue to within its fee.**

## 5. Venue closes with no ledger row (missing rows) — 33 orders, +37.92

| Close | Venue realized |
|---|---|
| 30× Nov-19 07:56Z BUY closes (the §3 short scalps) | −1.53 total |
| ETHUSDT BUY 0.148 @ 1604.54, 2026-11-20 19:14Z | **+19.94** |
| SUIUSDT BUY 304.4 @ 0.5971, 2026-11-21 06:16Z | **+30.50** |
| VETUSDT BUY 42328 @ 0.00459, 2026-11-21 13:28Z | −10.92 |
| **Total** | **+37.92** |

Order-group accounting closes exactly (193 groups): used by ledger rows 67; unused 126 = 30 open-position entries + 30 reset-wiped entries + 30 scalp SELL opens + 33 missing closes + 3 missing-close entries.

## 6. Equity walk — the scorecard DISCREPANCY (+114.32) fully explained

The forward scorecard's reconciliation is single-segment across the Nov-19 reset, so its `unexplained +114.32 / DISCREPANCY` is an artefact of the reset, not a live shortfall. Split at the reset:

**Segment A — Nov-15 window start → Nov-19 07:35Z reset.** Equity 5000.00 → 4978.13 = **−21.87** = realized 0.00 + funding −0.18 + commission −0.61 + Δunrealized **−21.08**. (No income `REALIZED_PNL` rows and no venue fills exist in this segment — the 30 bulk "closes" realized nothing.)

**Segment B — Nov-19 07:35Z reset → Nov-22 08:27Z snapshot.** Equity 5000.00 → 5131.15 = **+131.15** = realized +57.28 + funding −0.44 + commission −7.52 + Δunrealized +81.83. Check: wallet 5000 + 57.28 − 0.44 − 7.52 = **5049.32** = live USDT wallet exactly; margin 5049.32 + 81.83 = 5131.15 = snapshot exactly.

**Ledger vs venue, forward window:** venue realized +57.28 = ledger window net +16.83 + missing closes +37.92 + ledger window-row fees +2.54 (rounding ±0.01). And the scorecard's +114.32 = missing closes +37.92 + window fees +2.54 + funding −0.44 + commission −7.52 + Δunrealized +81.83 = +114.33 (±0.01 rounding).

**Daemon counter check:** `state/realized_pnl.json` reads 151.62 = 134.79 (carried pre-reset value, flat Nov 14→19) + 16.83 (ledger window net). It understates venue realized by the same +40.45 (missing closes +37.92, fees +2.54) — same cause, not a second gap.

## 7. OANDA leg — reconciled

2 rows, net −0.05. The `VENUE_CLOSE_CORRECTION` row already matches the venue (trade 470, close order 474, fill txn 475, realized −0.0478); the scorecard's OANDA section reads `unexplained 0.0045 / RECONCILED`. Nothing further owed.

## 8. Forward-window state (filed)

- Forward window: 2026-11-15T11:29:49+05:30 → now. Fills/closes in window: **64 ledger rows** (62 binance + 2 oanda); ledger net **+16.78** (binance +16.83, oanda −0.05). Venue-true realized in window: **+57.28** (the +40.45 difference is the 33 missing closes + window-row fees, §5–6).
- Open now: 30 positions, unrealized +80.89, all 3x cross, at the 30-position cap (`STRATEX_MAX_POSITIONS_PER_VENUE=30`).
- Account now: USDT wallet 5049.32, USDC 5000.00, BTC 0.01; margin balance ~5130.2; no ledger row since 2026-11-21 13:52:33Z (no closes since; entries continued — latest VETUSDT entry 2026-11-21 20:00:47Z).

## 9. Gaps filed

- **G1 — 33 venue closes have no ledger row (+37.92).** The ledger understates forward-window realized P&L by that amount. Biggest: SUIUSDT +30.50 (2026-11-21 06:16Z), ETHUSDT +19.94 (2026-11-20 19:14Z), VETUSDT −10.92 (2026-11-21 13:28Z), plus the 30 Nov-19 07:56Z scalp closes (−1.53).
- **G2 — 30 reset-wiped rows book 0.0 with fallback exit prices.** Their implied gross (−33.68) disagrees with the venue-true wiped unrealized (−21.08). They are placeholders for positions the reset destroyed, not closes.
- **G3 — 62/73 ledger rows carry no `order_id`.** Row-to-venue traceability rests on price/qty/time matching, which fails whenever fills split across orders (e.g. the PAXG legacy exit: 47 fills, 1 order).
- **G4 — 6 `testnet_engine` rows (classic-testnet account, retired 2026-11-15) sit in the same ledger as demo-fapi rows**, with estimated fees. They reconcile against no venue the daemon can still reach.
- **G5 — The forward scorecard's reconciliation is single-segment across the Nov-19 reset.** Its `DISCREPANCY +114.32` is fully explained above (§6); the scorecard should re-baseline at the reset (or the reset should have been filed as a boundary).
- **G6 — `realized_pnl.json` (151.62) understates venue realized by +40.45** — same missing-closes cause as G1; the counter is ledger-derived, not venue-derived.
- **G7 — Stale venue flags in S1 `Stratex/.env`:** `TESTNET_ONLY=TRUE`, `TESTNET_ENABLED=true` persist alongside `BINANCE_ENV=demo` / `BINANCE_TESTNET=false` on the retired testnet's grave. Cosmetic, but the flags contradict the live venue.
- **G8 — No daemon-side record of the Nov-19 reset exists** (journal retention gap; no reset boundary filed). If the owner reset the demo account again, the same silent wipe + placeholder rows would recur unless the daemon detects a balance/position discontinuity.

## 10. Acceptance

- [x] Daemon fill/close ledger read end to end on Server 1, read method recorded (bridge `read_text`/`run_shell` on S1 state files + signed demo-fapi GETs; §0).
- [x] Ledger reconciled against the venue's positions/history; every mismatch listed (§4–§5, G1–G8) or confirmed matching (§4: all 35 exit-matched rows agree to within fees; §7: OANDA reconciled).
- [x] Forward-window state filed as evidence (§8): fills, closes, net P&L, with the venue source for each figure (demo-fapi order ids, income rows, snapshots cited throughout).

State: implemented / tested / merged / deployed / production-verified — implemented (this report + board IN_REVIEW on PR #1350). Tested: venue reads are live and cross-checked three ways (userTrades vs income vs allOrders; wallet vs snapshots vs account). Merged: NO — only Muse merges. Deployed: N/A (read-only verification; no code or live change). Production-verified: NO — verification is of the ledger against the live venue, not a deployment.

— Muse 4
