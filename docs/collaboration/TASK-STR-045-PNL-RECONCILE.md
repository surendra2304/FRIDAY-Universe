# TASK-STR-045 — Heartbeat vs move-verified P&L reconciliation

- **Task:** Stratex: reconcile the heartbeat P&L (+130.27) vs move-verified P&L (+140.90) gap — find the cause and file the reconciled figure.
- **Owner:** Muse 9. **Claim:** hub #1483 comment 7119204891, 2026-11-24 ~07:00 IST, queue head after TASK-INT-035 merged.
- **Board verified:** AVAILABLE, owner muse_9, on main `1c75482` (board blob `f0b6e0ad`, 18,506 lines). No prior claim, branch or PR.
- **Branch:** `muse9/task-str-045` from main `1c75482`.
- **Prior art:** the gap already had a filed reconciliation — merged STR-AUDIT-001 evidence doc §4 (PR #1506, commit 025c11a, 2026-11-23 19:18 IST, before STR-045 was drafted ~20:40 IST). This task independently re-derives it first-hand from the live ledger and heartbeat; it does not assume the audit's numbers.

## Method (read-only, no live-fleet change)

Probe script `str045_probe.py` (workspace `friday-bridge/`, delivered to Server 1 via the bridge `run_shell`, same pattern as the INT-033 probes): reads the live Stratex state on S1 through the service's own repository layer (`measurement.fill_ledger.read_fills()`, `Stratex/state/fill_ledger.jsonl`) plus `daemon_heartbeat.json` and `realized_pnl.json`. No writes, no venue calls, no orders, no restarts. Sums compared at 8-decimal rounding (the ledger stores floats; raw float sums carry ~5e-9 representation noise).

Probe run 2026-11-24 ~07:06 IST; live heartbeat fresh at the read (`timestamp 2026-11-24T01:36:14Z`, `realized_pnl 78.53277575`).

## Result: 13/13 checks PASS — the reconciliation is exact

| Check | Expected | Live value | Verdict |
|---|---|---|---|
| Audit-slice rows (exit ≤ 2026-11-23T13:42:51Z) | 75 | 75 | PASS |
| Audit-slice net sum | +190.49068657 | +190.49068657 (raw 190.490686574999978077) | PASS |
| ALGOUSDT SHORT close 2026-11-23T11:59:12Z exists once | 1 row | 1 row | PASS |
| ALGO net | −10.62294596 | −10.62294596 | PASS |
| ALGO gross / fees | −10.5908 / 0.03214596 | −10.5908 / 0.03214596 | PASS |
| ALGO exit_reason | SL_TP_BROKER | SL_TP_BROKER | PASS |
| ALGO row detail | qty 962.8, entry 0.07247, exit 0.08347 | identical, `strategy_volume_breakout`, `recorded_at 2026-11-23T11:59:12.956772+00:00` | PASS |
| SOLUSDT SHORT close 2026-11-23T09:05:57Z net | −10.72378920 | −10.72378920 | PASS |
| Nov-23 closes up to the audit read | 2 | 2 (SOL + ALGO) | PASS |
| Nov-23 daily realized P&L | −21.34673516 | −21.34673516 | PASS |
| Lineage: current cumulative = 130.27280441 + post-audit closes | 78.53277575 | 78.53277575 (heartbeat and realized_pnl.json agree) | PASS |
| Move-verified recomputed | 140.89575037 | 140.89575037 | PASS |

## The reconciliation (one line)

**Heartbeat realized P&L +130.27280441 (audit read 13:42:51Z, 2026-11-23) already includes the 11:59Z ALGO close (net −10.62294596); the move-verified +140.89575037 = heartbeat − (ALGO net), i.e. the pre-ALGO-close total. The two figures reconcile exactly through that single close — no unexplained residual.**

- Difference: 140.89575037 − 130.27280441 = **10.62294596** = |ALGOUSDT close net|.
- The heartbeat's daily counter proves it absorbed the close: `daily_realized_pnl` −21.34673516 = SOL −10.72378920 + ALGO −10.62294596 exactly (the only two closes in the UTC day up to the audit read).
- **Reconciled figure:** +130.27280441 is the current figure as of the audit read; +140.89575037 is the correct total before the ALGO close landed. Both are right for their timestamps; no correction is owed to either source.

## Lineage across the audit boundary (independent confirmation)

The heartbeat counter and the ledger agree after the audit, not just at it. Five closes landed after the 13:42:51Z read (ledger now 80 rows, was 75):

| Close (UTC 2026-11-23) | Net |
|---|---|
| AVAXUSDT SHORT 13:57:01Z | −10.05484520 |
| ADAUSDT SHORT 13:58:24Z | −10.19941296 |
| DOTUSDT SHORT 14:00:33Z | −9.55176745 |
| ATOMUSDT SHORT 14:17:24Z | −10.57263049 |
| ADAUSDT LONG 19:40:06Z | −11.36137256 |
| **Sum** | **−51.74002866** |

130.27280441 + (−51.74002866) = **78.53277575** = the live cumulative in both `daemon_heartbeat.json` and `realized_pnl.json` at 01:36:14Z Nov 24. (The first four are the 19:27–19:47 IST SL_TP_BROKER exits already noted in STR-046, net −40.38. The ADA LONG close is also exactly the current `daily_realized_pnl` −11.36137256 for `daily_start_date` 2026-11-24.) The full UTC Nov-23 day is 7 closes, net −73.08676382 = −21.34673516 (pre-audit) + −51.74002866 (post-audit).

## Scope note (carried from the audit, O1 — not a discrepancy)

The 75-row ledger slice sums to +190.49068657 while the heartbeat counter reads +130.27280441: the ledger includes 3 `LEGACY-UNATTRIBUTED` rows (+195.7066) and venue income since the 2026-11-14 reset (+24.7149) — ledger, heartbeat counter, and venue income cover different scopes. That scope difference is still undocumented in the daemon's accounting docs; it is not a discrepancy in this reconciliation, which is exact on the two figures the assignment named.

## Flags for Muse

- **Duplicate:** TASK-STR-048 (owner muse_19, AVAILABLE) is the same gap with the same acceptance. Ruling owed: close STR-048 as a duplicate once this verification merges, or keep it for a second independent re-derivation.
- **Queue note:** TASK-STR-052 does not exist on main `1c75482` (no record in the board or docs) — the "STR-052" queue item from my earlier status was stale. After STR-045, my queue is INT-023 only (IN_REVIEW, final 7-day compilation due 2026-11-27).

## States

- **implemented:** YES — reconciliation re-derived live and filed here.
- **tested:** YES — 13/13 probe checks PASS against the live S1 ledger + heartbeat, 2026-11-24 ~07:06 IST.
- **merged:** NO — work PR open for review (merge by Muse).
- **deployed:** N/A — no code change; read-only verification.
- **production-verified:** YES — the ledger rows and heartbeat counter were read back from the live Server 1 state, not assumed from the audit doc.
