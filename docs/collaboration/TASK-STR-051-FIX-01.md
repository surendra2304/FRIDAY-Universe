# TASK-STR-051-FIX-01 — G1: reconcile the 35 venue closes with no ledger row

- **Task:** TASK-STR-051-FIX-01 (G1: reconcile the 35 venue closes with no ledger row, +15.93 USDT on 2026-11-24 — match each close to a ledger row or file it as a genuine gap, then re-run the daily reconciliation).
- **Claim:** hub #1483 comment 7151603272 (2026-11-25 ~08:40 IST); branch `muse18/task-str-051-fix-01` from main `d2a40a6d`.
- **Assignment:** coordinator watch 7151431137 (run scheduled 07:57 IST) — Muse 18 queue head: STR-051-FIX-01 → FRD-050 → MEM-032. STR-053 merged, leaves the queue.
- **Filed:** 2026-11-25 ~09:15 IST, by Muse 18. Checkpoint 1 (prep): matcher + tests + this doc.

## §1 — Provenance: read this first

Every live number below comes from **Muse 13's first-hand S1 pull** (bridge `run_shell`, Oracle Server 1, cwd `/opt/friday_universe`, read-only), summarised in hub #1483 comment **7146269836** (2026-11-25 ~04:05 IST), and from the checkpoint `docs/collaboration/TASK-STR-051-WINDOW-STATE.md` (Muse 8, §1/§4). **Muse 18 has NOT read a single ledger row or daily report first-hand yet** — the live leg needs the per-task run_shell grant asked in hub #1483 comment **7151623500** (2026-11-25 ~08:50 IST). Figures are cited with M13's md5s so they are checkable; nothing below is presented as Muse 18-verified row data.

## §2 — What the pull establishes (M13, first-hand)

| File (S1 path) | Size / rows | mtime | md5 | Headline |
|---|---|---|---|---|
| `Stratex/state/fill_ledger.jsonl` | 38,809 bytes, 80 lines | 2026-11-24 01:10:06 IST | `5a8d43a3ef9f32c111280a615d6ceb35` | Range 2026-11-14T12:41:21Z → 2026-11-23T19:40:06Z. Net **+138.75** (gross +151.55, fees 12.80). Venues: binance_futures 78, oanda 2. No new fills since 2026-11-23 19:40 UTC. |
| `Stratex/state/reconciliation/daily_2026-11-23.json` | 45,641 bytes | — | `9a11563a666988f19ba293a80e1ffd43` | Status **RECONCILED**. 78 rows, net **+160.6847**. |
| `Stratex/state/reconciliation/daily_2026-11-24.json` | 46,274 bytes | — | `f54994b87973088006492f3a6ba6d25c` | Status **RECONCILED**. 80 rows, net **+138.7507**. |

- Gaps (both days, M13): **G1 — 35 venue closes have no ledger row** (+15.93 USDT realised on 11-24; was 34 / +26.59 on 11-23). **G-trace — 69/80 ledger rows carry no `order_id`.** Matched rows: zero diffs over 0.5 USDT.
- Q1 (open, from the window-state doc §3): a whole-ledger net cannot fall by 21.93 while gaining 2 rows unless the two reports use different windows or baselines (the 11-23 report likely slices from a different anchor, e.g. the STR-048 window). Needs the report files to resolve.
- G1 arithmetic (window-state doc §4): the 11-23 figure reconciles exactly (4 real closes +28.195 minus 30 Nov-19 post-reset micro-closes −1.6023 = +26.59 ✓). The 11-24 figure (+15.93, 35 closes) implies a **−10.66 move from one added/changed close** — WHICH close is UNVERIFIED without the venue-close list.

## §3 — Method (this task)

The daily job (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, STR-044) files each missing close under `missing_closes.orders`: symbol, order_id, side (BUY/SELL), aggregate qty, realized P&L, commission, fill count, first/last fill time. The offline matcher (`Stratex/scripts/g1_reconcile.py`, new in this PR) joins each close to a ledger row by the STR-043/STR-044 rule — symbol + side + qty (within max(0.001, 1%)) + time (ledger exit_time within 5 min of the close's first/last fill). A close with side SELL is the exit of a LONG row; side BUY is the exit of a SHORT row. Split fills match on the order aggregate.

Price leg: the filed report carries no per-fill prices for a missing close, so the exit price is checked indirectly — from the candidate row's entry price, the close's realized P&L implies an exit price (LONG: entry + realized/qty; SHORT: entry − realized/qty), which must agree with the row's exit_price within 0.5%. A candidate passing symbol/side/qty/time but failing the price check is filed MATCHED_PRICE_MISMATCH — a finding, never absorbed.

Verdicts per close: MATCHED / MATCHED_PRICE_MISMATCH / AMBIGUOUS (several candidates — listed) / GENUINE_GAP (none — filed with its realised P&L). The script also prints the Q1 side-by-side (ledger nets, window blocks, identity status, missing counts) and verifies the G1 arithmetic (sum of filed realized == reported realized) for both days.

## §4 — Limits (stated, not hidden)

- **No live venue read:** the matcher never touches Binance, needs no keys, and never places, cancels or modifies anything. Per-fill prices and VWAP for split fills cannot be recomputed from the filed report alone — the aggregate consistency check (§3) is the strongest price evidence available offline. If a live venue read is later granted, the fills for each matched order re-verify the VWAP directly.
- **Fallback exit times:** rows whose exit time is a fallback (the Nov-19 reset-wiped rows) match nothing by design; they surface as TIME_MISS with the delta so a reviewer can see them.
- **Already-matched state is invisible offline:** the daily report files only aggregate match classes, not per-row match results. A close whose fills the daily run already consumed cannot be a missing close by construction; candidates are reported with scores so the reviewer can judge.
- **Re-run leg:** acceptance asks the daily reconciliation to be re-run to RECONCILED. Re-running the daemon writes reports on S1, which the read-only grant does not cover. The re-run here is a read-only recomputation from the pulled rows via `g1_reconcile.py`; if it disagrees with the filed reports, a separate write-scoped grant for a daemon re-run will be asked for — not improvised.

## §5 — What remains for acceptance

1. Live leg (grant pending, comment 7151623500): pull the ledger + both daily reports from S1; verify md5s against §2.
2. Run `g1_reconcile.py` on the pulled files; file the per-close verdict table (35 closes) + the corrected/confirmed G1 figure.
3. Resolve Q1 from the two reports' window blocks.
4. File the read-only recomputation verdict (RECONCILED or the residual, filed as a finding).
5. Board flip (STR-051-FIX-01 → MERGED) rides in the work PR; work PR opens when the audit is filed.

## §6 — Prep done this run (checkpoint 1)

- `Stratex/scripts/g1_reconcile.py` — offline matcher + Q1 comparison (stdlib only, read-only, no venue, no keys).
- `Stratex/tests/test_g1_reconcile.py` — 11/11 pass locally (this VM, pytest 9.2.0, venv). Added to the Stratex contract list in `.github/workflows/owner-workflows.yml`.
- This doc. No live data read, no numbers invented, no shell use on any server.

## §7 — Five states

- Implemented PARTIAL (matcher + tests + doc; live reconciliation pending grant) / tested PARTIAL (11/11 local, no live data) / merged NO / deployed N/A / production-verified NO.

— Muse 18, 2026-11-25 ~09:15 IST
