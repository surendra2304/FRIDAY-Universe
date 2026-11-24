# TASK-STR-055 — Stratex forward-window fills audit run 5

- **Task:** Stratex: forward-window fills audit run 5 — reconcile the daemon fill ledger against venue history for the new window.
- **Owner:** Muse 9. **Claim:** hub #1483 comment 7122045347, 2026-11-24 ~10:00 IST, queue position 2 after INT-023, under the blocked-head rule (INT-023 IN_REVIEW, final 7-day compilation due 2026-11-27; STR-052 IN_REVIEW, work PR #1615 merged). Same precedent as the STR-052 claim (comment 7120261042).
- **Board verified:** AVAILABLE, owner muse_9, on main `ec78a623` (board blob `a17d1904`, 18,726 lines, verified against the true main blob before editing). Assigned by coordinator watch 2026-11-24 ~07:53 IST (board PR watch010, merge `518bad42`). No prior claim, branch or PR.
- **Branch:** `muse9/task-str-055` from main `ec78a623`.
- **Venue:** Binance Demo Futures (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Demo only — signed GETs only; no orders placed, modified or cancelled, no service restarted, no ledger written. The audit re-ran the merged STR-044 daily reconciliation job exactly as the systemd service runs it.
- **Prior art:** STR-044 proof run 2 (2026-11-23 12:46:01Z, RECONCILED, residual −0.0001) is the last completed audit; STR-045 (2026-11-24 ~07:06 IST) independently re-derived the heartbeat lineage. Runs 3 (STR-053, Muse 18) and 4 (STR-054, Muse 12) are still AVAILABLE/unclaimed — run 5 covers the window since run 2, so no closes are uncovered; runs 3–4's drafts are superseded in coverage terms.

## 1. Method (read-only on the fleet; one designed report write)

1. Live probe `str055_probe.py` (workspace `friday-bridge/`, delivered to Server 1 via the bridge `run_shell`, same pattern as the STR-045 probe): ledger end-to-end through the service's own repository layer (`measurement.fill_ledger.read_fills`), `daemon_heartbeat.json`, `realized_pnl.json`, reconciliation directory, timer state. Run 2026-11-24 ~10:00 IST.
2. Readback of the timer's filed report `Stratex/state/reconciliation/daily_2026-11-24.json` (timer run 01:00:03 IST / 2026-11-23T19:30:07Z).
3. Manual re-run of the STR-044 job on S1, exactly as the service runs it (`/opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env`, as user `ubuntu`, detached via nohup because the bridge call limit is 120 s), to include the one close that landed after the timer run. Job run 2026-11-24 ~10:07 IST (`run_at_utc 2026-11-24T04:37:05Z`). It overwrote `daily_2026-11-24.json` — the STR-044 precedent (proof run 2 overwrote run 1's same-day report); the timer run's numbers are preserved in §2 below.
4. Readback of the fresh report + live ledger cross-check (probes `str055_report_probe.py`, `str055_report_probe2.py`).

## 2. The new window (since run 2's last ledger row, 2026-11-23T11:59:12Z)

Six closes, net **−62.36297462**, all `SL_TP_BROKER`, all without `order_id`:

| Close (UTC 2026-11-23) | Side | Qty | Entry → Exit | Net |
|---|---|---|---|---|
| ALGOUSDT 11:59:12Z | SHORT | 962.8 | 0.07247 → 0.08347 | −10.62294596 |
| AVAXUSDT 13:57:01Z | SHORT | 29.0 | 6.453 → 6.797 | −10.05484520 |
| ADAUSDT 13:58:24Z | SHORT | 1329.0 | 0.1397 → 0.1474 | −10.19941296 |
| DOTUSDT 14:00:33Z | SHORT | 312.4 | 0.6583 → 0.6886 | −9.55176745 |
| ATOMUSDT 14:17:24Z | SHORT | 190.48 | 1.208 → 1.263 | −10.57263049 |
| ADAUSDT 19:40:06Z | LONG | 1549.0 | 0.1558752098128 → 0.1486 | −11.36137256 |
| **Total** | | | | **−62.36297462** |

- The ALGO close was already inside run 2's heartbeat figure (the heartbeat had absorbed it by the 13:42:51Z audit read); the five later closes are the post-audit lineage in STR-045. The window is defined from run 2's last ledger row, so ALGO is listed once here and counted once in the lineage (§4).
- No new closes since 2026-11-23 19:40:06Z: ledger last exit unchanged, heartbeat fresh at 2026-11-24T04:29:53Z.

## 3. Venue reconciliation — run 5 (fresh job run, 2026-11-24 10:07 IST)

**Status: RECONCILED. Residual −0.0001, tolerance 10.52, errors [].**

| Window identity | Value |
|---|---|
| Venue realized P&L | −26.5936 |
| Ledger window net (binance) | −56.2614 |
| Missing closes realized | +26.5927 |
| Ledger window fees | 3.0752 |
| Expected venue realized | −26.5935 |
| Residual | **−0.0001** |

Identity check: −56.2614 + 26.5927 + 3.0752 = −26.5935 = expected; venue −26.5936, residual −0.0001. Exact.

| Forward window | Value |
|---|---|
| Closes on venue | 105 |
| Fills | 71 |
| Ledger net P&L | −56.3092 (binance −56.2614 + oanda −0.0478) |
| Venue true net P&L | −29.7165 |

| Ledger / matching | Value |
|---|---|
| Ledger rows | 80, net +138.7507, gross +151.5524, fees 12.8017 |
| By venue | binance_futures 78 rows +138.7985; oanda 2 rows −0.0478 |
| By lane | FORWARD_TEST 36 rows −116.2482; (none) 44 rows +254.9989 |
| Matching | BOTH 39, NO_MATCH 39, rows matched 78, diffs over 0.5: none |
| Matched exit realized vs matched ledger net | −53.1863 vs −56.2614 (diff = fees 3.0751) |
| Missing closes (G1) | 34 orders, +26.5927 — largest SUIUSDT +30.5009, ETHUSDT +19.9399; smallest SANDUSDT −11.3252, VETUSDT −10.9206 |
| Open positions | 29, unrealized +42.7311 |
| Venue account | wallet 10481.97, margin 10524.69, unrealized +42.71, available 9478.37; USDT 4964.79, USDC 5000.00, BTC 0.01 |
| Income since reset | REALIZED_PNL −26.5935, COMMISSION −9.1494, FUNDING_FEE −0.2554, TRANSFER +15000.03 |
| Resets | 6 detected, 0 new |

Live-ledger cross-check (probe ~10:00 IST, before the job run): 80 rows, total net +138.75065791, last exit 2026-11-23T19:40:06Z — matches the fresh report (80 rows, +138.7507) to its 4-decimal rounding. The report's `last_recorded_at` and row count agree with the live ledger exactly.

## 4. Timer run vs run 5 — the one-close delta, verified

The timer's own run filed `daily_2026-11-24.json` at 01:00:03 IST (run_at 2026-11-23T19:30:07Z): 79 rows, window 70, window net −44.9478, venue realized −15.3243, BOTH 38, status RECONCILED, residual −0.0001. The ADA LONG close landed 19:40:06Z, ten minutes after it.

- Venue realized delta: −15.3243 → −26.5936 = **−11.2693** = ADA LONG net −11.3614 + its fees +0.0921. Exact.
- Ledger window net delta: −44.9 → −56.2614 = −11.3614 = the ADA LONG net. Exact.
- Window rows 70 → 71, closes on venue 104 → 105, BOTH 38 → 39 (the ADA LONG matched its venue fills), open positions 28 → 29.
- The timer run and the run-5 re-run agree on everything else (missing closes 34 / +26.5927, G1, resets 6 / 0 new).

## 5. Heartbeat lineage (independent confirmation)

- Heartbeat fresh at 2026-11-24T04:29:53Z: `realized_pnl` **78.53277575**, unchanged since STR-045's 07:06 IST read.
- 130.27280441 (audit-read heartbeat) + (−51.74002866, the five post-audit closes) = **78.53277575**. Exact — same as STR-045.
- `realized_pnl.json`: `daily_realized_pnl` −11.36137256 for `daily_start_date` 2026-11-24 = the ADA LONG close, the only close in the UTC day so far.

## 6. Flags for Muse

- **Timer schedule doc discrepancy (minor, not a blocker):** `Stratex/deployment/friday-stratex-reconciliation.timer` says "Daily 01:00 UTC (06:30 IST)", but `OnCalendar=*-*-* 01:00:00` fires at 01:00 **local** time and S1's clock is IST — verified first-hand: last run Tue 2026-11-24 01:00:03 IST, next Wed 2026-11-25 01:00:00 IST; the filed report's `run_at_utc` is 19:30:07Z. The run still files daily; only the comment (and the STR-044 doc's "01:00 UTC" line) is wrong. Doc fix, not a fleet change.
- **G1 unchanged:** 34 venue closes with no ledger row (+26.59) — the pre-window / reset-wiped closes the daemon never logged. Accounted for in the identity, not a new discrepancy.
- **G-trace persists:** 69/80 ledger rows carry no `order_id` (all six new-window closes included); traceability still rests on price/qty/time matching.
- **Runs 3–4 unclaimed:** STR-053 (Muse 18) and STR-054 (Muse 12) still AVAILABLE. Run 5 covers the window since run 2, so nothing is uncovered; coordinator may close or re-scope them.
- **Bridge transport:** three initialize timeouts during this run (60 s read timeout on `friday-universe.duckdns.org`), each recovered on retry — transport flakiness, not a job or S1 issue. Same class as the STR-044 note.
- **No live-fleet change:** no code changed, no service restarted, no order touched. The only write on S1 is the job's own dated report (its designed output).

## States

- **implemented:** YES — new-window fills, closes and net P&L filed here; venue reconciliation re-run live and filed as `Stratex/state/reconciliation/daily_2026-11-24.json` on S1.
- **tested:** YES — fresh job run RECONCILED (residual −0.0001), ledger/matching/venue-identity cross-checks all exact (§3–§5).
- **merged:** NO — work PR open for review (merge by Muse).
- **deployed:** N/A — no code change; the reconciliation job and timer are already deployed (STR-044, PR #1503).
- **production-verified:** YES — ledger rows, heartbeat and the fresh report were read back from the live Server 1 state, not assumed from prior docs.
