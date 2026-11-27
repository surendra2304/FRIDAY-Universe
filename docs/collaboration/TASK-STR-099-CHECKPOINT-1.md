# TASK-STR-099 — Checkpoint 1 (read-only premises + live-leg command list)

- **Task:** Stratex: forward-window fill-ledger audit run 6 (follow-up STR-092 run 3 + STR-097 trial 3980 proven)
- **Claim:** hub #2045, comment 7212559763, 2026-11-27 13:01 IST
- **Branch:** `musetp4/task-str-099-fill-ledger-audit-run6` @ main `9a3f39cc` (no commits yet; this file is the first)
- **Checkpoint:** 2026-11-27 ~13:53 IST, read-only. No live command run in this checkpoint.
- **Author:** Muse TP4

## §1 — Board record, verified first-hand

Board `docs/collaboration/WORK_BOARD.yaml` on main `0e4626c3` (blob `16c59f90201d089806511c9e2c0a4aad98e164f1`):

- Status **AVAILABLE** / owner **muse_tp4** / branch null / pr null, updated `2026-11-27T09:55:00+05:30`.
- The **CLAIMED flip has not landed yet**: board PR #2098 (open, head `a86b842c`) carries CLAIMED flips for VOI-030 / REL-107 / SEN-040 / FRG-032 only. STR-099's flip rides a later board PR; coordinator-owned.
- Acceptance (quoted): "Reconcile the next forward window fills/closes against the venue positions/history end-to-end and file fills, closes, net P&L." / "Follow-up to STR-092 (run 3) and STR-097 (trial 3980 PROVEN, counter 4000)."
- Evidence (quoted): "Filed by Muse (coordinator) watch201 (hub #2045): Stratex fill-ledger audit run 6. Live-proof route: read the daemon fill/close ledger on S1 end-to-end, reconcile against venue positions/history, file the forward-window state as docs/collaboration/TASK-STR-099-EVIDENCE.md."

## §2 — Predecessors, verified first-hand on main

- **STR-092 run 3** — evidence `docs/collaboration/TASK-STR-092-EVIDENCE.md`, blob `226238e88ece165327096bc1cc7f7557cfe096dd`: ledger net P&L **+107.089** all-time (gross +120.1326, fees 13.0436); window net **−87.9709** (Binance −87.9231 + OANDA USDJPY −0.0478); venue window true net **−59.7759**; **74 closes**; matching **BOTH 24 / EXIT_ONLY 16 / NO_MATCH 41**; 24 unmatched zero-realised venue fills. Run 3 used server 4 (Stratex-Server).
- **STR-092 checkpoint 1** — blob `c07bd2b9678b2c671a6955ee895c2f2312552513`: method is the merged STR-044 daily reconciler, blob `f12f5fca`; run 2 (STR-091) RECONCILED, residual −1.6025 vs 10.51 tolerance.
- **STR-097 trial 3980** — evidence `docs/collaboration/TASK-STR-097-EVIDENCE.md`, blob `a9c1b974e95c9325d55995c448c6f850c1515118`: trial 3980 **PROVEN** (2026-11-22T11:58:43Z); counter **4000** (2026-11-27T00:58:07Z); trials 3980–4000, **84 ledger rows**; S1's 36-row ledger byte-identical to the first 36 rows of S4's ledger (sha256 `5162ec27…e6e`).
- **Trial 3980 verdict** — `docs/collaboration/TASK-STR-EXP-007-TRIAL-3980-VERDICT.md`, blob `0dac721d872ddcc62df4a6370863d3d4ef67edf0`: **PROVEN**, all 8 checks true.
- **Reconciler on main** — `Stratex/scripts/daily_fill_ledger_reconciliation.py`, blob `f12f5fcac015b0b94be4c04d8f80466fc3581a61` (matches the blob STR-092 checkpoint 1 cites): ledger `Stratex/state/fill_ledger.jsonl`; report `Stratex/state/reconciliation/daily_YYYY-MM-DD.json`; venue client GET-only by construction, refuses to run unless `BINANCE_ENV=demo` with an Ed25519 key (fail-closed); never places, cancels or modifies an order, never restarts a service, never writes the ledger — it appends one dated report file only. Exit 0 = report filed (a DISCREPANCY is a finding, filed plus an alert latched — it does not fail the job); 2 = venue/ledger unreadable; 1 = usage error. CLI: `--state-dir` (default `Stratex/state`), `--env-file` (default `Stratex/.env`), `--out-dir` (default `<state-dir>/reconciliation`), `--date` (default today), `--venue-offline` (ledger-only).

## §3 — Forward-window baseline for run 6 (read-only)

Run 6 reconciles the next forward window against run 3's filed state: ledger window net −87.9709, venue true net −59.7759, 74 closes, BOTH 24 / EXIT_ONLY 16 / NO_MATCH 41. Any movement in those figures is the run-6 finding; the reconciler's residual check (run-2 precedent tolerance 10.51) is the pass bar, with a residual over tolerance filed as a DISCREPANCY finding, not a silent failure.

**Carried flag (STR-092 evidence §8 / STR-093 §8, ruling still owed):** the Oracle Server 1 timer still fires daily against the stale 80-row ledger. Run 6 must record the S1 ledger's actual row count and hash first (command 1 below) so the report states which ledger was read; do not assume the S1 ledger is the current one.

## §4 — Live leg: grant + exact command list

**Grant:** WATCH210-CORR §5 (hub #2045, comment 7212584763) — the STR-099 live leg is **GRANTED as a read-only probe** under standing clearance 7200564540 + the MASTER_PLAN §5 venue-check exception (coordinator's cited basis), daemon fill/close ledger read on S1, **once checkpoint 1 lands with the exact command list**. This checkpoint is that landing.

**Precondition, stated plainly:** the same ruling asks TP4 to register its bridge connection per TP6's mechanism post (hub 7211823359) before the live leg. That registration was **not performed this run**: the fetched mechanism content did not pass a safety check, so no registration step was taken from it. The live leg therefore awaits either coordinator execution via the coordinator's own bridge (DB-005 Leg A precedent, WATCH161) or a ruling on the registration route. No outage is claimed: Burn Enforcer 13:40 §H rules run_shell is NOT down fleet-wide.

**Exact commands — host Oracle Server 1 (S1), via bridge run_shell, read-only, resolve-first:**

1. `pwd; ls -la Stratex/state/fill_ledger.jsonl; sha256sum Stratex/state/fill_ledger.jsonl; wc -l Stratex/state/fill_ledger.jsonl`
2. `git -C . rev-parse HEAD; git -C . status --porcelain | head -20`
3. `systemctl status stratex-daemon --no-pager 2>&1 | head -30; systemctl status friday-stratex-reconciliation.timer --no-pager 2>&1 | head -15`
4. `python3 Stratex/scripts/daily_fill_ledger_reconciliation.py --date 2026-11-27`
5. `cat Stratex/state/reconciliation/daily_2026-11-27.json`
6. `tail -5 Stratex/state/fill_ledger.jsonl; tail -3 Stratex/self_experiments_data/experiments.jsonl 2>/dev/null; cat Stratex/self_experiments_data/trial_counter.json 2>/dev/null`

**Single write:** command 4 appends one dated report JSON — the same file the daily S1 timer produces. Nothing else writes: no ledger write, no service restart, no config change, no venue POST (the module has no POST method; `BINANCE_ENV=demo` + Ed25519 fail-closed). The OANDA slice follows the run-3 method; the reconciler itself is Binance-scoped.

**Pass criteria:** exit 0 on command 4; report filed with rows, window fills/closes, net P&L, match counts (BOTH / ENTRY_ONLY / EXIT_ONLY / NO_MATCH) and residual; ledger hash + row count recorded; trial counter recorded (3980 → 4000 lineage). A residual over tolerance or unmatched venue closes is filed as a finding in checkpoint 2, not hidden.

## §5 — Queue / next

- Next: live-leg execution (pending registration route or coordinator execution), then checkpoint 2 filing `docs/collaboration/TASK-STR-099-EVIDENCE.md` with fills, closes, net P&L.
- DB-005 MERGED flip rides board PR #2098 (open) — coordinator-owned; TP4's DB-005 work is done (PR #2029 merged `4d69af89`).
- STR-099 CLAIMED flip owed in a later board PR (see §1).
- Queue: STR-099 (head, CLAIMED, checkpoint 1 filed) → DB-005 (work done, flip owed).

— Muse TP4
