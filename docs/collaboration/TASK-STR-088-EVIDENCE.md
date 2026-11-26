# TASK-STR-088 — Stratex forward-window fills audit run 6

- **Task:** Stratex: forward-window fills audit run 6 — reconcile the daemon fill ledger against venue positions/history.
- **Owner:** Muse 1. **Claim:** hub #1483 comment 7180443538, 2026-11-26 ~07:35 IST, queue position 2 after parked IG-FRD-010-RETEST-01, under the blocked-head rule (WATCH132, hub #1483 comment 7180339294).
- **Board verified:** AVAILABLE, owner null, branch null, pr null, on main `9392738d` (board blob `917698ea`, verified via the contents API before editing). No prior claim, branch or PR.
- **Branch:** `muse1/task-str-088-fills-audit-run-6` from main `9392738d44ff6d29baf05ed46f2ab5eece72a282`.
- **Venue:** Binance Demo Futures (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Demo only — signed GETs only; no orders placed, modified or cancelled, no service restarted, no ledger written. The audit re-ran the merged STR-044 daily reconciliation job exactly as the systemd service runs it.
- **Clearance basis (stated plainly):** WATCH132 assigns this task, whose board acceptance criterion is "Read the Stratex daemon fill/close ledger on S1 end-to-end, reconcile against the venue positions/history" — the assignment itself directs the read-only S1 probe and job re-run that runs 4–5 performed. No separate explicit probe grant was in WATCH132 (unlike STR-054's watch 7128069261 grant); if Muse wants a separate grant per run, run 7 should get one. The live leg here was read-only throughout: ledger/heartbeat/timer reads plus the STR-044 job's own signed GETs; the only write on S1 is the job's own dated report (its designed output).
- **Prior art:** run 5 (STR-055, Muse 9, PR #1624 **MERGED** `29db8c08`, 2026-11-24T05:32:10Z — the task brief's "still open/CLAIMED" is stale) covered the window through ledger exit 2026-11-23T19:40:06Z (RECONCILED, residual −0.0001). Run 4 (STR-054, Muse 12, PR #1658 merged) covered through its job run 2026-11-24 ~16:03 IST (RECONCILED, residual −0.0001; found the ALGO close with no ledger row after the daemon died). Run 6's window = venue/ledger state since run 4's job run.

## 1. Method (read-only on the fleet; one designed report write)

1. Live probe via the FRIDAY bridge `run_shell` on Server 1 (one-off client `bridge_run_str088.py`, copy of the shared bridge driver, scope-guarded to read-only audit commands; the shared helper is unchanged): ledger end-to-end through the service's own repository layer (`measurement.fill_ledger.read_fills`), `daemon_heartbeat.json`, `realized_pnl.json`, reconciliation directory, daemon + timer state. Probes 2026-11-26 ~07:40–07:56 IST.
2. Readback of the timer's filed reports `Stratex/state/reconciliation/daily_2026-11-25.json` (timer run 01:00:01 IST / 2026-11-24T19:30:01Z) and `daily_2026-11-26.json` (timer run 01:00:07 IST / 2026-11-25T19:30:08Z) — the timer is firing daily again (§7).
3. Manual re-run of the STR-044 job on S1, exactly as the service runs it (`/opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env`, as user `ubuntu`, `WorkingDirectory=/opt/friday_universe/Stratex`, detached via nohup because the bridge call limit is 120 s), to check the venue for closes after the 01:00 IST timer run. Job run 2026-11-26 ~07:48 IST (`run_at_utc 2026-11-26T02:18:54Z`). It overwrote `daily_2026-11-26.json` — the STR-044 precedent (proof run 2 overwrote run 1's same-day report); the timer run's numbers are preserved in §4 below.
4. Readback of the fresh report + live-ledger cross-check + new-close identification + a direct income-stream probe (same job client, signed GETs only) to resolve a wallet-check finding (§6, §8).

Bridge transport notes: one initialize `RemoteDisconnected` and one `IncompleteRead` (7173 bytes) during this run, each recovered on retry / by keeping partial bodies — transport flakiness, not a job or S1 issue. Same class as the STR-044/055 notes.

## 2. The new window (since run 4's job run, 2026-11-24 ~16:03 IST)

**Ledger closes in the window: ZERO.** Live `read_fills()`: 80 rows, net +138.75065791, gross +151.55240162, fees +12.80174371, last exit 2026-11-23T19:40:06.701184Z — identical to run 4. `fill_ledger.jsonl` mtime 01:10 IST Nov 24 (the last close itself). `realized_pnl.json` unchanged (total 78.53277575, daily −11.36137256 for 2026-11-24 = the ADA LONG close, the only close in the UTC day so far on the ledger side).

**Venue closes in the window: ONE, with no ledger row.**

| Close (2026-11-24) | Side | Qty | Entry → Exit | Net |
|---|---|---|---|---|
| SOLUSDT 15:17:00Z (20:47 IST) | SELL (LONG close) | 2.96 | 72.51 → ~69.14 (derived) | −9.9752 |

- Venue order `4250536607`, 1 fill, fill time `1795533420099` ms, commission 0.0819.
- It closes the SOLUSDT LONG 2.96 @ 72.51 that was open in run 4's re-filed report (unrealized −6.8968 at 16:22 IST); SOLUSDT now shows only the SHORT −2.1 (§7). Implied exit 69.14 = 72.51 + (−9.9752 / 2.96) — derived, the missing-close record carries no price.
- It landed **after the daemon died** (13:42:26 IST Nov 24, §7): the resting stop triggered on the venue while the daemon was dead, so no ledger row exists. This is the G1 mechanism, not a new discrepancy class — the second such close after run 4's ALGO.
- No other venue close: closes on venue 106 → 107, exactly +1. No close between the 01:00 IST timer run and the 07:48 IST fresh run (§4).

## 3. Venue reconciliation — run 6 (fresh job run, 2026-11-26 07:48 IST)

**Status: RECONCILED. Residual −0.0001, tolerance 10.50, errors [].**

| Window identity | Value |
|---|---|
| Venue realized P&L | −47.231 |
| Ledger window net (binance) | −56.2614 |
| Missing closes realized | +5.9553 |
| Ledger window fees | 3.0752 |
| Expected venue realized | −47.2309 |
| Residual | **−0.0001** |

Identity check: −56.2614 + 5.9553 + 3.0752 = −47.2309 = expected; venue −47.231, residual −0.0001. Exact. (Full-precision re-derivation from the venue income stream: realized −47.23100001; the identity holds on true figures too — §6.)

| Forward window | Value |
|---|---|
| Closes on venue | 107 |
| Fills | 71 |
| Ledger net P&L | −56.3092 (binance −56.2614 + oanda −0.0478) |
| Venue true net P&L | −50.3539 |

| Ledger / matching | Value |
|---|---|
| Ledger rows | 80, net +138.7507, gross +151.5524, fees 12.8017 |
| By venue | binance_futures 78 rows +138.7985; oanda 2 rows −0.0478 |
| By lane | FORWARD_TEST 36 rows −116.2482; (none) 44 rows +254.9989 |
| Matching | BOTH 39, NO_MATCH 39, rows matched 78, diffs over 0.5: none |
| Matched exit realized vs matched ledger net | −53.1863 vs −56.2614 (diff = fees 3.0751) |
| Missing closes (G1) | 36 orders, +5.9553 — largest SUIUSDT +30.5009, ETHUSDT +19.9399; smallest SANDUSDT −11.3252, VETUSDT −10.9206; **new SOLUSDT −9.9752** |
| Open positions | 30, unrealized +33.2056 (mark at 07:48 IST; +65.0195 at the 01:00 IST timer run — mark movement only, same 30 symbols/amounts) |
| Venue account | wallet 10467.23, margin 10500.42, unrealized +33.19, available 9468.86; USDT 4944.56, USDC 5000.00, BTC 0.01 |
| Income since reset | REALIZED_PNL −47.2309, COMMISSION −9.4624, FUNDING_FEE +0.2073 (**stale — true +0.4581, §6**), TRANSFER +15000.03 |
| Resets | 6 detected, 0 new |

Delta vs run 4's re-filed report, all exactly the SOL close: venue realized −37.2558 → −47.231 (Δ −9.9752); missing closes realized +15.9305 → +5.9553 (Δ −9.9752); closes on venue 106 → 107; missing count 35 → 36; venue true net −40.3787 → −50.3539 (Δ −9.9752). Everything else agrees (ledger, matching, G1 composition apart from SOL, resets).

Live-ledger cross-check (probe ~07:45 IST, before the job run): 80 rows, total net +138.75065791, last exit 2026-11-23T19:40:06Z — matches the fresh report (80 rows, +138.7507) to its 4-decimal rounding. The report's `last_recorded_at` and row count agree with the live ledger exactly.

G1 composition (36 orders): 30 Nov-19 reset-wiped closes (all tiny, −0.0055 to −0.17, fills 2026-11-19T07:56:38–07:56:56Z), then ETHUSDT +19.9399 (Nov 20), SUIUSDT +30.5009 (Nov 21), VETUSDT −10.9206 (Nov 21), SANDUSDT −11.3252 (Nov 22), ALGOUSDT −10.6622 (Nov 24, run 4's find), SOLUSDT −9.9752 (Nov 24, this run's find).

## 4. Timer runs vs run 6 — the two timer reports, preserved

The timer fired daily while run 4 believed it disabled (§7). Both timer reports agree with the fresh run on every non-mark figure:

| Report | run_at_utc | Venue realized | Missing | Closes | Ledger rows | Open (unrealized) |
|---|---|---|---|---|---|---|
| Timer 2026-11-25 | 2026-11-24T19:30:01Z | −47.231 | 36 / +5.9553 | 107 | 80 | 30 (+93.6622) |
| Timer 2026-11-26 | 2026-11-25T19:30:08Z | −47.231 | 36 / +5.9553 | 107 | 80 | 30 (+65.0195) |
| **Run 6 (fresh)** | **2026-11-26T02:18:54Z** | **−47.231** | **36 / +5.9553** | **107** | **80** | **30 (+33.2056)** |

- The SOL close (−9.9752) was already in the Nov-25 01:00 IST timer run: it landed 20:47 IST Nov 24, after run 4's 16:03 IST job run but before the Nov-25 timer run. Missing-close order-id sets are identical across all three reports (verified set-equal).
- No close landed between the Nov-25 and Nov-26 timer runs (identity figures identical; only funding moved +0.2863 and marks moved), and none between the Nov-26 01:00 IST timer run and the 07:48 IST fresh run (identity figures identical; funding reported unchanged — but see §6, the reported funding is frozen by the income cap).
- Run 4 baseline note: STR-054's doc quotes its job run at `run_at_utc 2026-11-24T10:33:27Z` (16:03 IST), but the file on disk is a re-file at `run_at_utc 2026-11-24T10:52:49Z` (16:22:49 IST, file mtime 16:23 IST) — re-run by an unattributed actor after run 4. Its income/ledger/matching/missing figures are identical to run 4's doc; only mark-dependent figures differ (wallet 10461.87 vs the doc's 10464.86; open unrealized +78.9714 vs the doc's +74.8342). The re-file is used here as the run-4 baseline because it is the file on disk; the 16:03→16:22 IST delta is mark movement only (income identical), so no close hides in it.

## 5. Heartbeat lineage (independent confirmation)

- Heartbeat last written 2026-11-24T08:12:21Z (13:42:21 IST — the daemon's last write before it died, §7): `realized_pnl` **78.53277575**, unchanged since run 4's read. The heartbeat carries the ledger-side realized figure, so it is unchanged: no new ledger closes.
- `realized_pnl.json`: `daily_realized_pnl` −11.36137256 for `daily_start_date` 2026-11-24 = the ADA LONG close, the only ledger close in the UTC day so far.
- Heartbeat open positions 30 at 13:42 IST vs 29 in run 4's re-filed report: one position opened between the report and the heartbeat (opens are not ledger rows); the fresh report shows 30 open again after the SOL close and the two after-death entries (§7). Noted as an observation, not a reconciliation item.

## 6. FINDING — the STR-044 job's income fetch is capped at 1000 rows (no pagination); funding now stale, next close will false-DISCREPANCY

The wallet check (§8) showed a +0.2520 USDT drift between the venue wallet and the tracked income since run 4. A direct probe with the job's own client (`DemoFuturesReader`, signed GETs only) found the cause:

- `income(RESET_MS)` returns **exactly 1000 rows** — the `limit: 1000` cap, no pagination. Rows span 2026-11-16T15:33Z → **2026-11-25T08:00:00Z**. The venue has more than 1000 income rows since `RESET_MS` (2026-11-14T13:03:53Z); Binance returns the oldest 1000 first, so **every income row after 2026-11-25T08:00:00Z is silently dropped** — the cutoff is frozen at the 1000th row.
- Rows after the cutoff (direct fetch, `startTime` past the cutoff): **58 rows, all FUNDING_FEE, +0.23675746** — 29 rows at 2026-11-25T16:00:00Z (+0.08658404) and 29 at 2026-11-26T00:00:00Z (+0.15017342). Plus the 08:00Z Nov-25 payment was cut mid-payment: the capped fetch holds 26 of its 29 rows (+0.15897142 of the full +0.17386191), so **+0.01489049** of that payment is missing too.
- **True funding total now: +0.45814086** (capped sum 0.20649291 − partial 08:00Z 0.15897142 + full 08:00Z 0.17386191 + 0.08658404 + 0.15017342). The reports show **+0.2073 — stale by +0.2508**, frozen since Nov 25 08:00Z. The +0.2520 wallet drift is fully explained by the missing funding (+0.2516) plus per-row rounding (§8).
- **Impact on this run's verdict: none.** Funding is not in the window identity, and all realized/commission rows predate the cutoff (last realized row: SOL close, Nov 24 15:17Z; last commission rows: the Nov-24 entries/close), so the identity still closes at −0.0001 on true figures. Full-precision re-derivation: realized −47.23100001, commission −9.46322266, funding +0.45814086 (true), transfer +15000.03.
- **Forward impact (the reason this is flagged, not buried): the next venue close will false-DISCREPANCY.** Its realized row will be dropped by the cap, so the report's venue realized will be understated by exactly that close's realized and the identity residual will equal it. The cap also freezes the funding figure permanently (90 funding rows/day keep arriving, all dropped). The 08:00Z cut shows the cap bites mid-payment, not on a clean boundary.
- **Second, minor bug in the same path:** `income_sums` rounds to 4 decimals after **every** row addition, accumulating ~0.001 error in the reported income totals (observed on identical row sets: commission reported −9.4624 vs true −9.46322266; funding reported +0.2073 vs true capped +0.20649291; realized −47.2309 vs true −47.23100001). Round once at the end instead.
- **Smallest safe fix proposal (for Muse to task, not implemented here):** paginate `DemoFuturesReader.income()` (loop with `startTime` advancing past the last returned row's time, or fetch in day-windows) and round once in `income_sums`. Job-only change; no venue writes, no ledger writes, no service changes. Until it lands, every audit run must re-derive funding from a post-cutoff fetch as done here, and any DISCREPANCY verdict must first be checked against the cap.
- BNBUSDT note: no funding row for BNBUSDT at the last three settlements (29 rows per payment vs 30 open positions; the missing symbol is BNBUSDT each time). Its funding is evidently exactly 0.00000000 at those settlements (tiny $44 notional short). Not a discrepancy — the venue simply emits no row.

## 7. Daemon death, after-death entries, and timer state (findings, not fixed here)

- `Stratex-Daemon.service`: **failed (Result: timeout)** since Tue 2026-11-24 13:42:26 IST (1 day 18h at probe); Main PID 3578584 killed SIGKILL; CPU 3min 46.066s. Journal 13:42:26 IST: systemd killed the process tree (`Killing process ... with signal SIGKILL`), "Main process exited, code=killed, status=9/KILL". The unit is also **disabled**. Recovery is Muse 4's per coordinator watch 7123816690 — **no restart was attempted here** (outside this task's scope).
- **Timer re-enabled (change since run 4, actor unattributed):** run 4 found `friday-stratex-reconciliation.timer` disabled + inactive. It is now **enabled + active (waiting)**, next elapse Fri 2026-11-27 01:00:00 IST; journal shows it was deactivated Nov 24 10:33:34 IST and **started Nov 24 17:28:43 IST**. That re-enable is why the Nov-25 and Nov-26 01:00 IST timer runs exist. Run 4's "tomorrow's 01:00 IST run will not happen" finding is now obsolete. No ruling/re-enable is owed from this task, but Muse may want to know who re-enabled it (not determinable from the journal alone).
- **Two positions opened after the daemon died** (resting orders filling on the venue with no daemon, no ledger row, no position tag): ALGOUSDT SHORT −2293.4 @ 0.08004, entry fill 2026-11-24T12:00:16Z (17:30:16 IST, order `431960721`); SOLUSDT SHORT −2.1 @ 69.02, entry fill 2026-11-24T16:00:38Z (21:30:38 IST, order `4250554513`) — opened ~43 minutes after the SOL LONG stopped out at ~69.14. Both are still open in the fresh report. When the daemon recovers (Muse 4), it will find positions it did not open; the ledger has no rows for them. The reconciliation identity still holds — it is designed for that — but the ledger stops being a complete record of venue activity until the daemon is recovered.
- Consequence for this audit: with the daemon dead, any further resting-stop trigger lands on the venue with no ledger row (G1 grows by exactly that close, as the SOL close did).

## 8. Wallet check (run 4 → run 6, full precision)

- USDT wallet 4954.10223748 → 4944.55739748 (Δ −9.5448). Tracked income Δ (report figures): realized −9.9752, commission −0.2133, funding +0.3917 → −9.7968. Apparent gap **+0.2520** — fully explained by §6 (missing funding +0.2516 + per-row rounding ~0.0004).
- True income Δ (full precision, missing funding restored): realized −9.9753, commission −0.2141, funding +0.6425 → −9.5469 ± 0.0024 (band = per-row rounding in the run-4 baseline figures). Residual **+0.0021, inside the rounding band — EXACT**.
- Total wallet Δ run-4→fresh: 10461.86547547 → 10467.22612783 (Δ +5.3607) = true income Δ −9.5469 + BTC-implied revaluation +14.9055 (BTC 0.01 holding, from the account's own wallet arithmetic: implied 507.7632 → 522.6687). Residual **+0.0021, inside the rounding band**. The wallet movement is fully explained by income + BTC revaluation; no unexplained balance movement.

## 9. Flags for Muse

- **STR-044 income cap (new, §6):** the job's `limit=1000` income fetch without pagination has been silently dropping rows since Nov 25 08:00Z. Funding in every report since is stale (reported +0.2073, true +0.4581). The next venue close will false-DISCREPANCY unless the job is paginated first. Smallest safe fix proposed in §6; a fix task is owed (not implemented here — this task is the audit).
- **Daemon still down (Muse 4's recovery):** `Stratex-Daemon.service` failed/timeout since 13:42:26 IST Nov 24; no restart attempted here. The SOL close (§2) is the second unrecorded close from the outage; two new positions opened on resting orders (§7).
- **Timer re-enabled (unattributed):** `friday-stratex-reconciliation.timer` active again since Nov 24 17:28:43 IST; daily 01:00 IST runs are filing. Run 4's disabled-timer finding is obsolete.
- **G1 grows 35 → 36 (+5.96):** the SOL close joins the pre-window / reset-wiped missing closes. Accounted for in the identity, not a new discrepancy.
- **G-trace persists:** 69/80 ledger rows carry no `order_id` (the SOL close has a venue order id, `4250536607`, but no ledger row at all); traceability still rests on price/qty/time matching.
- **Correction to the brief:** STR-055's PR #1624 is MERGED (`29db8c08`, 2026-11-24T05:32:10Z), not "still open/CLAIMED".
- **No live-fleet change:** no code changed, no service restarted, no order touched. The only write on S1 is the job's own dated report (its designed output). The income probes were signed GETs only, through the job's own fail-closed demo-only client.

## States

- **implemented:** YES — new-window fills, closes and net P&L filed here; venue reconciliation re-run live and filed as `Stratex/state/reconciliation/daily_2026-11-26.json` on S1.
- **tested:** YES — fresh job run RECONCILED (residual −0.0001), ledger/matching/venue-identity/wallet/heartbeat cross-checks all exact (§3–§5, §8); income-cap finding verified by direct reads (§6).
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — no code change; the reconciliation job and timer are already deployed (STR-044, PR #1503).
- **production-verified:** YES — ledger rows, heartbeat and the fresh report were read back from the live Server 1 state, not assumed from prior docs.

— Muse 1
