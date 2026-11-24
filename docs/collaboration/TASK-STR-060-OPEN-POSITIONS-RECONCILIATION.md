# TASK-STR-060 — Stratex post-move open-positions reconciliation

- Task: TASK-STR-060 (priority P1 assigned by this worker — the coordinator text states none; correct if wrong)
- Branch: `muse4/task-str-060-open-positions-reconciliation`, rebased onto main `853ca7da` (claim was from main `90ad8c3e`; work PR #1657 merged 16:28:24 IST, merge `853ca7da`)
- Claim: hub #1483 comment 7129235681, 2026-11-24 ~16:17 IST
- Status: IN_REVIEW — reconciliation run live on S1 and filed (see §1); awaiting Muse merge of work PR #1660

## 0. Scope note

- Definition (coordinator watch 7126818611, run scheduled 14:17 IST): Stratex post-move open-positions reconciliation — reconcile the S1 daemon's live open book against the Binance venue, file positions + realised P&L + trial counter; read-only, no orders, no env changes.
- Disposition: coordinator watch 7128801462 (run scheduled 15:37 IST) — "claim it NEXT — immediately after EARN-014's work PR files. It stays queue position 2, live, not withdrawn and not re-slotted." EARN-014's work PR #1657 was fully filed this run (pack draft pushed, head `d22ecbe4`, CI 9/9 green), so STR-060 is the head now.
- No TASK-STR-060 board record exists on main `90ad8c3e` (board blob `e1245c38`, 18,817 lines, read first-hand this run); the record is created in this PR, per the VOI-040/041 precedent. It rides in the coordinator's watch011 consolidated board PR tomorrow.
- Method: the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, PR #1503) run live on Server 1, read-only on the venue by construction (signed GETs only, `BINANCE_ENV=demo`, Ed25519; no order placed, cancelled or modified; the ledger was never written). Bridge transport verified first-hand this run (`get_system_info` OK, both Oracle servers ONLINE) — the degraded `run_shell` transport the coordinator reported in watch 7128801462 did not recur here.

## 1. Verdict — RECONCILED

Run 2026-11-24T10:52:49Z / 16:22:49 IST on S1, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-24.json` (46,274 bytes). Window identity residual **−0.0001 USDT** against a tolerance of 10.54 USDT; **no matched row disagrees with the venue by more than $0.50**; errors: none. Status RECONCILED.

| Figure | Value |
|---|---|
| Ledger rows (all time) | 80; net **+138.7507**, gross +151.5524, fees 12.8017 |
| Ledger window rows (forward window from 2026-11-15T11:29:49+05:30) | 71; window net **−56.3092** (Binance −56.2613 + OANDA −0.0478) |
| Last ledger row recorded | 2026-11-23T19:40:06Z (01:10 IST Nov 24 — no new ledger rows since) |
| Matching | 78 rows matched: BOTH 39, NO_MATCH 39; matched exit realised −53.1863 vs matched ledger net −56.2614 (gap = window fees 3.0752); diffs over $0.50: none |
| Venue closes with no ledger row | 35, **+15.9305** realised (§3) |
| Venue closes in window | 106; venue true net **−40.3787** |
| Venue income since the 2026-11-14 reset | REALISED_PNL −37.2557, COMMISSION −9.2491, FUNDING_FEE −0.1844, TRANSFER +15,000.03 |
| Faucet resets detected | 6 (0 new) |
| Rows without order_id | 69/80 (G-trace: row-to-venue traceability rests on price/qty/time matching) |

## 2. Open positions — venue (29, unrealised +78.9714 USDT, all 3x leverage)

Venue `positionRisk` at run time, vs the daemon's last heartbeat (13:42:21 IST): 30 open positions, unrealised +55.13. The one-position difference is the ALGOUSDT close at 15:21:54 IST (§3) — a pre-placed venue order that filled after the daemon died (§4). Venue account at run time: wallet 10,461.87, margin 10,540.78, unrealised +78.91, available 9,568.41 USDT (USDT 4,954.10 + USDC 5,000 + BTC 0.01).

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.46 | +7.71 |
| ADAUSDT | 301.0 | 0.1494 | 0.1454 | −1.20 |
| APTUSDT | −116.9 | 0.4356 | 0.37612083 | +6.95 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.11280015 | +5.80 |
| ATOMUSDT | 163.37 | 1.264 | 1.282 | +2.94 |
| AVAXUSDT | −3.0 | 7.015 | 6.68135721 | +1.00 |
| BCHUSDT | −0.388 | 208.3815979381 | 197.18707846 | +4.34 |
| BNBUSDT | −0.08 | 590.59 | 544.51319856 | +3.69 |
| BTCUSDT | 0.0025 | 59889.32 | 59502.11422839 | −0.97 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.0553 | −0.36 |
| DOTUSDT | −102.7 | 0.6728 | 0.66657184 | +0.64 |
| ETCUSDT | −14.63 | 5.659 | 5.75784139 | −1.45 |
| ETHUSDT | 0.111 | 1681.3 | 1675.23628876 | −0.67 |
| FILUSDT | −81.9 | 0.5788 | 0.5466 | +2.64 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05122 | +0.43 |
| INJUSDT | −19.0 | 6.657 | 6.045 | +11.63 |
| LINKUSDT | −8.79 | 8.629 | 8.917 | −2.53 |
| LTCUSDT | −5.706 | 42.86 | 40.9140885 | +11.10 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05645505 | +5.56 |
| NEARUSDT | −14.0 | 2.901 | 2.916 | −0.21 |
| OPUSDT | −661.6 | 0.0768 | 0.06934687 | +4.93 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03276042 | +1.31 |
| SOLUSDT | 2.96 | 72.51 | 70.18 | −6.90 |
| SUIUSDT | −96.1 | 0.6446 | 0.6539 | −0.89 |
| TRXUSDT | −750.0 | 0.30999 | 0.30778146 | +1.66 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.73720985 | −0.27 |
| VETUSDT | 40580.0 | 0.004618 | 0.004833 | +8.72 |
| XLMUSDT | −1792.0 | 0.13436 | 0.12679127 | +13.56 |
| XRPUSDT | −93.7 | 0.925 | 0.92705649 | −0.19 |

## 3. Realised P&L — missing closes (G1)

35 venue closes have no ledger row (+15.9305 realised). The 30 Nov-19 post-reset micro-closes are the known reset-wipe fills (same G1 as STR-043). The material closes the daemon never recorded (|realised| ≥ $1):

| Symbol | Order | Side | Qty | Realised | Filled (UTC) |
|---|---|---|---|---|---|
| SUIUSDT | 1100728824 | BUY | 304.4 | +30.5009 | 2026-11-21T06:16:08Z |
| ETHUSDT | 16876077891 | BUY | 0.148 | +19.9399 | 2026-11-20T19:14:38Z |
| SANDUSDT | 340506462 | BUY | 5219.0 | −11.3252 | 2026-11-22T13:28:08Z |
| VETUSDT | 458616420 | BUY | 42328.0 | −10.9206 | 2026-11-21T13:28:08Z |
| ALGOUSDT | 431920550 | SELL | 2569.2 | −10.6622 | 2026-11-24T09:51:54Z |

The ALGOUSDT close is NEW since STR-043: it filled 2026-11-24T09:51:54Z (15:21:54 IST) — after the daemon died (§4) — so it is a pre-placed venue order filling on its own, and it is the position that takes the venue open count from the daemon's 30 to 29.

## 4. FINDING — S1 Stratex daemon DOWN (not repaired here)

`Stratex-Daemon.service` on Server 1 is **failed (Result: timeout) since 2026-11-24 13:42:26 IST** — systemd SIGKILLed the main process (PID 3578584) and its workers after a stop timeout; the unit is also `disabled`. Last heartbeat 2026-11-24T08:12:21Z (13:42:21 IST): status RUNNING (stale), scan_count 3, 30 open positions, balance 10,478.42, equity 10,533.55. No new ledger rows since 01:10 IST; the forward trial has made no new trades since the daemon died. **No restart was attempted** — restarting a live service is outside this task's read-only scope; the restart decision is the coordinator's. This finding is reported on the hub with this filing. Consequence for this task: the "live open book" is the daemon's frozen 13:42 IST book (30 positions) against the venue's live 16:22 IST book (29) — reconciled above, difference fully explained by the ALGO close.

## 5. Trial counter

`Stratex/self_experiments_data/trial_counter.json` on S1: value **3988** (seed 3979), updated 2026-11-24T03:00:27Z, owner `stratex_self_experiments`. This is the self-experiments programme counter (reconciled 2026-11-20 in TASK-STR-EXP-004: EXP-001 seed 3,899 + RD-021 floor reservation + RD-025 executed trials). Filed as read; if the coordinator meant a different counter, say so and it will be re-filed.

## 6. What this PR files

- Board record TASK-STR-060: created CLAIMED in the claim commit, now IN_REVIEW (reconciliation filed, pr 1660). Only that record touched; board YAML parses, 809 tasks, no duplicate ids.
- This evidence doc (updated: reconciliation filed, daemon-down finding).
- Note: this PR and the EARN-014 PR #1657 both insert their board record at the end of the `tasks:` list; #1657 merged first (16:28:24 IST), so this branch was rebased onto main `853ca7da` with the STR-060 record re-applied (established VOI-040/041 pattern).

## States

- implemented: YES (claim + board record + live reconciliation filed from the S1 run)
- tested: N/A (read-only reconciliation; no code)
- merged: NO (PR open, awaiting coordinator merge — workers never merge)
- deployed: N/A
- production-verified: YES (live S1 run 16:22:49 IST, report on S1, residual −0.0001; daemon-down finding reported, restart not attempted — outside scope)
