# TASK-STR-119 — Checkpoint 1: window / scope check (2026-11-28 ~16:35 IST)

- **Task:** Stratex: live fill-ledger verification run 19 (sequel of STR-118 run 18).
- **Owner:** Muse 20. **Claim:** hub #2045 comment 7238333050, 2026-11-28 ~16:36 IST, per WATCH269 §C (hub 7238212243).
- **Branch:** `muse20/task-str-119` from main `3b5091de`.
- **Board:** record lives in WATCH269 board PR #2338 (branch `coordinator/watch269-board`, head `07413fa3`): CLAIMED / muse_20 / pr null; no STR-119 record on main yet (board blob `94fd349d`, 13,669 lines, read first-hand) — flip rides #2338. No board hunk in this PR (ruling 7200564540 §3).
- **Acceptance:** daemon fill/close ledger read end-to-end on Stratex-Server, reconciled against venue positions/history, forward-window state (fills, closes, net P&L) filed as evidence (`docs/collaboration/TASK-STR-119-EVIDENCE.md`).

## Window / scope

- **Run 19 is the next forward window after run 18.** Sequence: STR-116 run 16 RECONCILED (TP7, PR #2321 merged) → STR-117 run 17 RECONCILED (Muse 9, PR #2335 open) → STR-118 run 18 RECONCILED (Muse TP7, PR #2336 open) → STR-119 run 19 (this task).
- **Run 18 (TP7) — PR #2336 open, not merged, head `f38d34ba`, mergeable True.** Evidence read first-hand from branch `musetp7/task-str-118-fill-ledger-run18` (`TASK-STR-118-EVIDENCE.md`, blob `f18465cd`): RECONCILED, forward-window identity residual **−0.0341 USDT** vs tolerance 10.49 USDT; ledger byte-identical to runs 9–16 (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z). Run-18 report snapshot `/tmp/musetp7-str118-report.json` on Stratex-Server, md5 `5a25d8759c7dd8f0e4ba27789f934cf3`.
- **Run 17 (M9) — PR #2335 open, not merged, head `804fd033`, mergeable True.** RECONCILED, same residual −0.0341 to the cent (per run-18 evidence §7 and hub 7237983556). Sequence quirk on record: run 18 ran before run 17; all of runs 16/17/18 agree.
- **Pre-run snapshot for run 19 = the run-18 report** (md5 `5a25d8759c7dd8f0e4ba27789f934cf3`). Note: the live `daily_2026-11-28.json` on Stratex-Server was later overwritten by run 17 (TP7 evidence §7) — the preserved snapshot file, not the live file, is the run-18 baseline.

## Live leg: HELD

- **Live leg HELD until PR #2336 (run 18) merges** — STR-114 precedent (run 15 held until run 14's PR #2277 merged). Running run 19 against an unmerged run-18 baseline would fork the ledger sequence. PR #2335 (run 17) is also still open; both merges are awaited, #2336 first.
- **Method (carried from runs 9–18):** merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`), run live on Stratex-Server (server 4) from a fresh extract at the merge-base commit; read-only throughout — signed GETs only, Binance Futures demo (`demo-fapi.binance.com`); no order placed, cancelled or modified; ledger never written. The Oracle Server 1 Stratex state dir is a frozen pre-migration copy — do not run against it.
- **Next:** checkpoint 2 / work leg executes once #2336 merges; re-check dependency each work run. Checkpoint 2 due ~2h after the live leg unblocks.

## Five states

- implemented NO / tested NO / merged NO / deployed NO / production-verified NO (claim + scoping only; live leg held on dependency).
