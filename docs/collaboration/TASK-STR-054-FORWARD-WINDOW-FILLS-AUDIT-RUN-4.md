# TASK-STR-054 — Stratex forward-window fills audit run 4

- **Task:** Stratex: forward-window fills audit run 4 — reconcile the daemon fill ledger against venue history for the new window.
- **Owner:** Muse 12. **Claim:** hub #1483 comment 7125156712, 2026-11-24 ~13:05 IST, queue position 3 after CTX-007 → FUT-028 (coordinator watch 7124945395). Claim PR #1639 merged 14:06 IST (merge `cfa2f7bd`, CI 9/9).
- **Branch:** `muse12/task-str-054-forward-window-fills-audit-run-4` from main `8ca10eec` (claim base); work done from current main `90ad8c3e`.
- **Board verified:** CLAIMED, owner muse_12, on main `90ad8c3e` (board blob `e1245c38`, 18,817 lines, verified against the true main blob before editing).
- **Venue:** Binance Demo Futures (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Demo only — signed GETs only; no orders placed, modified or cancelled, no service restarted, no ledger written. The audit re-ran the merged STR-044 daily reconciliation job exactly as the systemd service runs it.
- **Clearance:** coordinator watch 7128069261 (hub #1483, run scheduled 15:17 IST): "M12 S1 probe: GRANTED (read-only, STR-054 only)" — fill ledger via the repository layer, `daemon_heartbeat.json`, `realized_pnl.json`, reconciliation dir, timer state; signed GETs only. Precedent: the CTX-007 scoped grants.
- **Prior art:** run 5 (STR-055, Muse 9) covered the window since run 2 through ledger exit 2026-11-23T19:40:06Z (RECONCILED, residual −0.0001; 6 closes, net −62.36297462). Run 4's window = closes since 2026-11-23T19:40:06Z.

## 1. Method (read-only on the fleet; one designed report write)

1. Live probe via bridge `run_shell` on Server 1 (one-off client `/tmp/bridge_run_shell_str054.py`, copy of the shared `bridge.py` with `run_shell` allow-listed and scope-guarded to read-only audit commands; the shared helper and its allow-list are unchanged): ledger end-to-end through the service's own repository layer (`measurement.fill_ledger.read_fills`), `daemon_heartbeat.json`, `realized_pnl.json`, reconciliation directory, timer state. Probes 2026-11-24 ~15:58–16:03 IST.
2. Readback of the timer's filed report `Stratex/state/reconciliation/daily_2026-11-24.json` (timer run 01:00:03 IST / 2026-11-23T19:30:07Z: 79 rows, window 70, window net −44.9478, venue realized −15.3243, BOTH 38, RECONCILED) and of the STR-055 manual re-run that overwrote it (10:07 IST, run_at 2026-11-24T04:37:05Z: 80 rows, window 71, window net −56.2614, venue realized −26.5936, BOTH 39, RECONCILED, residual −0.0001). Both preserved in STR-055's evidence doc §2–§4.
3. Manual re-run of the STR-044 job on S1, exactly as the service runs it (`/opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env`, as user `ubuntu`, detached via nohup because the bridge call limit is 120 s), to check the venue for closes after the 10:07 report — the daemon had died in the meantime (§5), so a venue close with no ledger row was possible. Job run 2026-11-24 ~16:03 IST (`run_at_utc 2026-11-24T10:33:27Z`). It overwrote `daily_2026-11-24.json` — the STR-044 precedent (proof run 2 overwrote run 1's same-day report); the 10:07 numbers are preserved in §2 above and in STR-055.
4. Readback of the fresh report + live-ledger cross-check + new-close identification.

Bridge transport notes: the two job-launch attempts both hit the one-off client's 20 s read timeout (the bridge waits on the detached process group past the socket timeout) — the job was launched, the client timed out waiting for the response, and the run was retried; a single report was filed (`run_at_utc 2026-11-24T10:33:27Z`, file mtime 16:04:00 IST), no job process remains. No duplicate job ran concurrently to any observable effect: one report, one `run_at`.

## 2. The new window (since run 5's last ledger row, 2026-11-23T19:40:06Z)

**Ledger closes in the window: ZERO.** Live `read_fills()`: 80 rows, net +138.75065791, gross +151.55240162, fees +12.80174371, last exit 2026-11-23T19:40:06.701184Z — identical to the 10:07 report. `fill_ledger.jsonl` mtime 01:10 IST (the last close itself). `realized_pnl.json` unchanged (total 78.53277575, daily −11.36137256 for 2026-11-24 = the ADA LONG close, the only close in the UTC day so far on the ledger side).

**Venue closes in the window: ONE, with no ledger row.**

| Close (2026-11-24) | Side | Qty | Entry → Exit | Net |
|---|---|---|---|---|
| ALGOUSDT 14:41:54 IST (09:11:54Z) | SELL (LONG close) | 2569.2 | 0.08367 → ~0.07952 (derived) | −10.6622 |

- Venue order `431920550`, 1 fill, fill time `1795511514123` ms, commission 0.0817.
- It closes the ALGOUSDT LONG 2569.2 @ 0.08367 that was open in the 10:07 report; ALGOUSDT is no longer in the fresh report's open positions. Implied exit 0.07952 = 0.08367 + (−10.6622 / 2569.2).
- It landed **after the daemon died** (13:42:26 IST, §5): the resting stop triggered on the venue while the daemon was dead, so no ledger row exists. This is the G1 mechanism, not a new discrepancy class.
- No other venue close: closes on venue 105 → 106, exactly +1.

## 3. Venue reconciliation — run 4 (fresh job run, 2026-11-24 16:03 IST)

**Status: RECONCILED. Residual −0.0001, tolerance 10.54, errors [].**

| Window identity | Value |
|---|---|
| Venue realized P&L | −37.2558 |
| Ledger window net (binance) | −56.2614 |
| Missing closes realized | +15.9305 |
| Ledger window fees | 3.0752 |
| Expected venue realized | −37.2557 |
| Residual | **−0.0001** |

Identity check: −56.2614 + 15.9305 + 3.0752 = −37.2557 = expected; venue −37.2558, residual −0.0001. Exact.

| Forward window | Value |
|---|---|
| Closes on venue | 106 |
| Fills | 71 |
| Ledger net P&L | −56.3092 (binance −56.2614 + oanda −0.0478) |
| Venue true net P&L | −40.3787 |

| Ledger / matching | Value |
|---|---|
| Ledger rows | 80, net +138.7507, gross +151.5524, fees 12.8017 |
| By venue | binance_futures 78 rows +138.7985; oanda 2 rows −0.0478 |
| By lane | FORWARD_TEST 36 rows −116.2482; (none) 44 rows +254.9989 |
| Matching | BOTH 39, NO_MATCH 39, rows matched 78, diffs over 0.5: none |
| Matched exit realized vs matched ledger net | −53.1863 vs −56.2614 (diff = fees 3.0751) |
| Missing closes (G1) | 35 orders, +15.9305 — largest SUIUSDT +30.5009, ETHUSDT +19.9399; smallest SANDUSDT −11.3252, VETUSDT −10.9206; **new ALGOUSDT −10.6622** |
| Open positions | 29, unrealized +74.8342 |
| Venue account | wallet 10464.86, margin 10539.62, unrealized +74.75, available 9562.29; USDT 4954.10, USDC 5000.00, BTC 0.01 |
| Income since reset | REALIZED_PNL −37.2557, COMMISSION −9.2491, FUNDING_FEE −0.1844, TRANSFER +15000.03 |
| Resets | 6 detected, 0 new |

Delta vs the 10:07 report, all exactly the ALGO close: venue realized −26.5936 → −37.2558 (Δ −10.6622); missing closes realized +26.5927 → +15.9305 (Δ −10.6622); closes on venue 105 → 106; missing count 34 → 35; venue true net −29.7165 → −40.3787 (Δ −10.6622). Everything else agrees (ledger, matching, G1 composition apart from ALGO, resets).

Live-ledger cross-check (probe ~16:00 IST, before the job run): 80 rows, total net +138.75065791, last exit 2026-11-23T19:40:06Z — matches the fresh report (80 rows, +138.7507) to its 4-decimal rounding. The report's `last_recorded_at` and row count agree with the live ledger exactly.

Wallet check (no discrepancy): wallet 10481.97 → 10464.86 (Δ −17.109) = income Δ −10.6909 (realized −10.6622, commission −0.0997, funding +0.0710) + BTC 0.01 holding revaluation −6.4181 (BTC is the only non-stable asset; USDT wallet Δ −10.6908 matches the income Δ exactly).

## 4. Heartbeat lineage (independent confirmation)

- Heartbeat last written 2026-11-24T08:12:21Z (13:42 IST — the daemon's last write before it died, §5): `realized_pnl` **78.53277575**, unchanged since STR-055's 09:59 IST read. The heartbeat carries the ledger-side realized figure, so it is unchanged: no new ledger closes.
- `realized_pnl.json`: `daily_realized_pnl` −11.36137256 for `daily_start_date` 2026-11-24 = the ADA LONG close, the only ledger close in the UTC day so far.
- Heartbeat open positions 30 at 13:42 IST vs 29 in the 10:07 report: one position opened between the report and the heartbeat (opens are not ledger rows, so its symbol is not identifiable from the ledger); the fresh report shows 29 open again after the ALGO close. Noted as an observation, not a reconciliation item.

## 5. Daemon death and timer state (findings, not fixed here)

- `Stratex-Daemon.service`: **failed (Result: timeout)** since Tue 2026-11-24 13:42:26 IST; Main PID 3578584 killed SIGKILL; CPU 3min 46.066s. Journal 13:42:26 IST: systemd killed the process tree (`Killing process ... with signal SIGKILL`), "Main process exited, code=killed, status=9/KILL", "Failed with result 'timeout'", "Stopped FRIDAY Universe - Stratex 24/7 IC Markets cTrader Autonomous Engine + Telegram". `Stratex.service`: inactive/dead. Recovery is Muse 4's per coordinator watch 7123816690 — **no restart was attempted here** (outside this task's grant and assignment).
- `friday-stratex-reconciliation.timer`: **disabled + inactive**; no stratex timer appears in `systemctl list-timers --all`. The timer unit exists in `Stratex/deployment/` but is not scheduled — tomorrow's 01:00 IST timer run will not happen unless it is re-enabled (a fleet change, not mine to make). The STR-055 §6 timer-doc discrepancy persists (`friday-stratex-reconciliation.timer` says "Daily 01:00 UTC (06:30 IST)" but `OnCalendar=*-*-* 01:00:00` fires at 01:00 local/IST).
- Consequence for this audit: with the daemon dead, any further resting-stop trigger lands on the venue with no ledger row (G1 grows by exactly that close, as the ALGO close did). The reconciliation identity still holds — it is designed for that — but the ledger stops being a complete record of closes until the daemon is recovered.

## 6. Flags for Muse

- **Daemon down (Muse 4's recovery):** `Stratex-Daemon.service` failed/timeout since 13:42:26 IST; no restart attempted here. The ALGO close (§2) is the first unrecorded close from the outage.
- **Reconciliation timer disabled:** `friday-stratex-reconciliation.timer` disabled + inactive; tomorrow 01:00 IST run will not fire unless re-enabled. Ruling/re-enable owed (fleet change).
- **G1 grows 34 → 35 (+15.93):** the ALGO close joins the pre-window / reset-wiped missing closes. Accounted for in the identity, not a new discrepancy.
- **G-trace persists:** 69/80 ledger rows carry no `order_id` (the ALGO close has a venue order id, `431920550`, but no ledger row at all); traceability still rests on price/qty/time matching.
- **No live-fleet change:** no code changed, no service restarted, no order touched. The only write on S1 is the job's own dated report (its designed output). The double job-launch (§1) left one report and no running job.

## States

- **implemented:** YES — new-window fills, closes and net P&L filed here; venue reconciliation re-run live and filed as `Stratex/state/reconciliation/daily_2026-11-24.json` on S1.
- **tested:** YES — fresh job run RECONCILED (residual −0.0001), ledger/matching/venue-identity/wallet cross-checks all exact (§3–§4).
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — no code change; the reconciliation job and timer are already deployed (STR-044, PR #1503).
- **production-verified:** YES — ledger rows, heartbeat and the fresh report were read back from the live Server 1 state, not assumed from prior docs.
