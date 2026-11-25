# TASK-STR-078 — CHECKPOINT 7: live-trial design bounded by the demo-only audit + AutoHedge static leg closed

- **Task:** TASK-STR-078 — REPO-IMPLEMENT: Stratex repos (FinRL, Lumibot, Vibe-Trading, AutoHedge, QATS), wave 1, P1
- **Owner:** Muse 11
- **Filed:** 2026-11-25 ~15:40 IST
- **Branch:** `muse11/task-str-078-repo-implement` (head before this file: `227a7865`, checkpoint 6)
- **Main verified:** `a5de35d7` (merge #1814 REL-096 fix7; parent per merge message)
- **Board:** `docs/collaboration/WORK_BOARD.yaml`, blob `2bf7a136`, 22,748 lines — STR-078 CLAIMED/muse_11, branch `muse11/task-str-078-repo-implement`, pr null. Queue STR-078 → FRG-030 → FRG-021 stands.

## 1. Assignment and hub — no new direction

- Hub #1483 read through latest comment `7159136605` (Muse 20, STR-082 CI fix, 15:32:15 IST).
- **WATCH092 read in full (7159034308, ~15:35 IST): no direction to Muse 11, no live-trial/restart clearance.** Items noted: merges #1806 (INF-041) + #1794 (INT-044); board PR #1817 open (INF-035/036/041 MERGED flips; FRD-054 → muse_15; STR-086 → muse_tp6; NEW TASK-STR-087 Lumibot fix, Muse 18, PR #1815); STR-086 ruling (TP6's, watch090 "released" reading withdrawn); TP6 execution-gate ruling (local build/test authorised; one-real-chart leg read-only); #1805/#1815/#1811 HELD; M8 STR-083 final demand; M15 FRD-054 queue head.
- WATCH092 follow-up (7159054713): queue top-ups for Muse 2 (FRG-028) and Muse 20 (FRG-025, SEN-033) only — nothing for Muse 11.
- No hub post this run per owner order 7143628341 rule 7 (checkpoint only, no claim/completion/block).

## 2. M18 Lumibot standalone PR #1815 — test green, contracts still red

- PR #1815 open, head `acf32277`, merged False, mergeable unknown (stale).
- Check runs on head `acf32277` (9 total): **test now SUCCESS** (was still running at watch092); **contracts still FAILED**; docker/voice-regressions skipped; monorepo-policy, detect-voice-changes, secrets scan, fleet layout, entrypoint imports all success.
- Merge stays held by the coordinator pending the contracts fix — that fix is Muse 18's job per watch092. Muse 11 does not touch it (watch089 ruling stands). STR-078's Lumibot trial (see §3.2) depends on this fix landing first.

## 3. Live-trial design, adapted with the checkpoint-6 demo-only audit bounds

Checkpoint 6 proved at the engine level that no order path in STR-078 scope can reach a real venue. This checkpoint folds those bounds into the checkpoint-2 trial designs, so each trial states what it can and cannot prove, and what must wait for clearance.

### 3.1 Vibe-Trading adapt trial — bound: simulated engines only

- Target: `POST /vibe/alphas` + `POST /vibe/portfolio` in `Stratex/api/real_trading_routes.py` (L202/L242), NOT the trading-hub engine list (docstring only).
- Bound: the routes call simulated engines; even a misrouted call cannot reach a real venue (CP6 §2). Trial risk is limited to market-data handling and ledger behaviour.
- Trial (held): real market-data input through the routes, one end-to-end use filed with a failure case. Precondition: Stratex.service restart — held under the owner stop order.

### 3.2 Lumibot trial — bound: live config never fills, never calls a broker

- Target: `BrokerConfig.is_paper` paper-broker gate (paper fills in-memory; live config leaves orders `"submitted"`, cash unchanged, no external broker call anywhere in the class — CP6 §2).
- Trial (held): paper-fill assertion + live-config no-fill assertion, provable without any broker credential.
- **Dependency:** the pre-fix code on main never trades (M18 defect, CP2 §2). The trial is meaningful only after PR #1815 merges (contracts still red, §2) or, if the coordinator directs, against the M18 branch with provenance recorded. Until then the trial cannot distinguish "fix works" from "defect present".

### 3.3 FinRL / QATS (reference-only) — bound: nothing to execute

- Trial leg is the production-path scan only: zero refs in `Stratex/` (re-verified by M18, CP2). No execution leg exists for these repos. Trial = re-run the scan on current main and file the zero-hit evidence.

### 3.4 AutoHedge trial — static leg CLOSED this run

- **New evidence (GitHub code search, main `a5de35d7`):** `autohedge_rebalance` and `autohedge_backtest` have exactly 2 repo-wide references each — the route definitions in `Stratex/api/real_trading_routes.py` and `tests/test_e2e_real_repo_integration.py` (blob `97af5694`, 622 lines). **Zero production callers.**
- The test file's use, read first-hand: `test_autohedge_rebalance` POSTs positions/prices/target-weights/cash and asserts only on the response (`status == "success"`, `total_value == 100000.0`, `"orders" in data`); `test_autohedge_backtest` POSTs trades/prices/returns and asserts only on the response (`final_value > 50000.0`, `sharpe_ratio > 0`). **Neither test executes the returned orders list.**
- Bound confirmed: `/autohedge/rebalance` returns a computed `"orders"` list and never executes it; `/autohedge/backtest` runs an in-memory simulated ledger. No in-repo code consumes the rebalance output as orders.
- Trial (held, live leg only): run the four AutoHedge routes (`/autohedge/consensus`, `/position-size`, `/rebalance`, `/backtest`) against the live daemon and file the ledger outputs. The static leg is DONE — no further static work is owed for AutoHedge.
- **Prefix note:** the e2e test mounts these routes at `/api/v1/trading/engines/*`; checkpoint 4's public-gateway probe found no `/api/v1/trading/engines/*` route (405/404). Reachability depends on the dashboard registration, not the handler — the live trial must record the actually-mounted prefix when run.

### 3.5 Scope boundary flagged, not audited

- `submit_order` has 12 repo-wide hits. In STR-078 scope: `Stratex/app/agents/real_lumibot.py` (definition) + `Stratex/api/real_engines_routes.py` (route caller). The other hits (`Stratex/stratex_backtrader_adapter/*`, `Stratex/stratex_upgrade/execution.py`, `Stratex/execution/live_execution_engine.py`, etc.) are **outside STR-078 scope** — flagged here, not audited, no claim made about them.

### 3.6 Held under the owner stop order (unchanged)

- Demo-daemon cycle, failure injection (venue disconnect, stale feed), full-allowlist load scan, and all live route trials above. Live-trial/restart clearance still owed from Muse/owner. No live moves made this run: no restart, no deploy, no probe executed beyond the read-only checks in §4.

## 4. Live state re-verified this run (~15:36–15:38 IST)

- Both Oracle servers ONLINE (`get_system_info`, bridge v1.30.0; S2 git `2c960cb7`).
- FRIDAY `/health` 200 overall `"healthy"` (checked 15:36:46 IST, friday_core v2.0.0) — **honesty note:** this is the public-gateway surface. M15's FRD-054 checkpoint 1 (7159042528) found S1 `FRIDAY.service` dead since Nov 24 13:42:13 IST and the public health answering from an AWS host; that matches my standing record (S1 FRIDAY.service inactive by design). My /health check therefore verifies the public surface, not S1 directly — recorded as such.
- Memora 401 fix HOLDS — **full 200-line window this run** (15:34:09–15:37:06 IST): **0×401**, 396× `200 OK` (incl. cursor 200s), Memora.service active (running) since Nov 24 18:49:06 IST, Main PID `3747325` unchanged.
- Stratex.service inactive (dead) since Nov 24 13:42:11 IST, PID 3578170 TERM — no restart under the owner stop order. Last activity shadow-mode advisory, SHADOW_LOG_ONLY.
- All six STR-078 file SHAs re-verified unchanged on main `a5de35d7`: Vibe-Trading `c5a184a1`, AutoHedge `5457505e`, Lumibot `505d8943`, trading_hub `79e51b74`, routes `e4b682ba`, tests `1afe1e73`.

## 5. States, blockers, next

- States: implemented PARTIAL / tested PARTIAL / merged NO / deployed N/A / production-verified NO.
- Blockers unchanged: owner stop order holds the live legs (demo-daemon cycle, failure injection, load scan, live route trials); live-trial/restart clearance owed. PR #1815 contracts failure is M18's, not a Muse 11 blocker.
- Next WORK run: checkpoint 8 — run the §3 live legs the moment clearance lands, or the next static leg (route-prefix registration audit in `Stratex/dashboard.py`: which blueprints mount where, and whether `/api/v1/trading/engines/*` is reachable anywhere in the fleet).

— Muse 11
