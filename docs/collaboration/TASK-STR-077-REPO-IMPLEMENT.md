# TASK-STR-077 — REPO-IMPLEMENT Stratex repos (Freqtrade, VectorBT, Backtrader, Hummingbot, CCXT) — checkpoint 1: scoping

**Task:** REPO-IMPLEMENT (owner order 2026-11-24: implement ALL 102 scouted repos) — Freqtrade (reference-only), VectorBT (adapt), Backtrader (reference-only), Hummingbot (reference-only), CCXT (adapt), target Stratex. Wave 1, P1.
**Owner:** muse_17. **Branch:** `muse17/str-077` (from main `cc66b42d`).
**Claim:** hub #1483 comment 7138103574 (2026-11-24 ~22:00 IST), per the central pool pull model (7136890552); next free Wave 1 Stratex task per the 21:37 watch pool list (7137935600). **Pre-staged next:** TASK-STR-078.
**Checkpoint 1:** repo-side scoping, filed 2026-11-24 ~22:15 IST (this doc).
**Status:** implemented NO / tested NO / merged NO / deployed NO / production-verified NO — checkpoint 1 is scoping only. No server move made or attempted this run. All live reads below are read-only.

## 1. Board record — verified first-hand on main `cc66b42d` (21,022 lines)

- `TASK-STR-077`: AVAILABLE / owner null / branch null / pr null / P1. Title: 'REPO-IMPLEMENT: Stratex repos - Freqtrade (reference-only), VectorBT (adapt), Backtrader (reference-only), Hummi... (wave 1)'.
- Acceptance: (a) adapt entries must run in the target agent's live production path, proven by one real end-to-end use filed as evidence incl. a failure case; (b) reference-only/reject entries: a paper judgement is NOT a result — prove with live evidence whether it works in the agent or not (live trial or guardrail proof of absence from every production path), file that evidence per repo; (c) live demo-daemon cycle on Stratex-Server on real market data + failure injection (venue disconnect, stale feed) + full-allowlist load scan; results filed from the live ledger.
- `blockers: []`, `next_action` is the pull-model claim instruction. Evidence key cites the programme doc as source (see §3 flag).

## 2. Registry — verified first-hand on main `cc66b42d`

Source: `IntelX/intelx/registries/scouted_repos.json` — `count: 102`, `entries: 102`. All five fits confirmed:

| Repo | Fit | Licence | Registry rationale (short) |
|---|---|---|---|
| Freqtrade (`freqtrade/freqtrade`) | reference-only | GPL-3.0 | Dry-run → backtest → hyperopt discipline is the model for the forward-measurement rig. As a runtime it does not fit: min 2GB RAM (VM ~956MB, per-service cap ~180MB), needs Python 3.12+ (fleet 3.10); adopting it would replace Stratex's engine. Study the workflow + FreqAI retraining pattern; do not run it. |
| VectorBT (`polakowo/vectorbt`) | adapt | Apache-2.0 + Commons Clause | Build Stratex's offline parameter-sweep research on the community edition's vectorized pattern; pip-installable library, free for internal use. Constraints: sweeps off-fleet or on small universes only (RAM-hungry); never depend on PRO-only features (limit orders, leverage) — fleet stays free-only. |
| Backtrader (`mementum/backtrader`) | reference-only | GPL-3.0 | Cerebro/analyzer design is the textbook reference for event-driven backtest structure. Unmaintained, pandas/NumPy compat drifting; Stratex already has its own engine. Read for patterns; do not integrate. |
| Hummingbot (`hummingbot/hummingbot`) | reference-only | Apache-2.0 | V2 executor pattern (one component owning an order's full lifecycle, triple-barrier exits) is a design lesson for order management. Market making out of scope; full client (conda/Docker) far beyond the ~180MB cap. Learn the executor lifecycle; do not adopt the runtime. |
| CCXT (`ccxt/ccxt`) | adapt | MIT | Use the Python build selectively when adding a new crypto venue instead of hand-rolling another exchange client; copy its unified-API shape for Stratex's venue layer. Limits: no OANDA coverage (Stratex's FX venue); do not churn the working direct Binance integration; on builder-code exchanges CCXT routing can add ~1bp — check per-venue before routing real flow. |

## 3. Source flag — programme doc absent on main

The board record's evidence key cites "source: PRODUCTION-VERIFICATION-PROGRAMME.md sections A/B/C". **No such file exists on main `cc66b42d`** (tree-wide search for `*VERIFICATION-PROGRAMME*` and `*CLASSIFICATION*` returns nothing). Same class of issue as Muse 20's CLASSIFICATION note (21:37 watch). The registry itself exists and carries the five fits (§2), so scoping proceeds from the registry + the board acceptance text — but the cited programme source is unverified. Flagged to the coordinator in the claim post; the doc should be located or the citation corrected before the work PR.

## 4. Prior art already in the repo — the adapt legs are not greenfield

- **CCXT:** already integrated. `stratex_ccxt_adapter` exists; `Stratex/docs/BINANCE_CCXT_PARITY_REPORT.md` records full parity vs the `python-binance` client (OHLCV schema, precision, min notional, ticker fields, rate limiting). CCXT mentions across Stratex code: `exchanges/exchange_implementations.py` (50), `data_client.py` (21), `dashboard.py` (12), `app/trading_hub.py` (10), `execution/live_execution_engine.py` (5). The STR-077 CCXT leg is therefore verification + selective extension (new venue via the adapter), not a first integration — the evidence must show one real end-to-end use through the adapter incl. a failure case, per acceptance.
- **Freqtrade:** `stratex_freqtrade_adapter` already exists (`parameters`, `optimizer` via Optuna, `walkforward`, `protections`, `stratex_bridge` to the authoritative `BacktestEngine`); `Stratex/docs/FREQTRADE_INTEGRATION.md` documents it. This is inspired-by adaptation, not the Freqtrade runtime. The reference-only leg is a live trial / guardrail proof that the Freqtrade runtime itself is absent from every production path (it cannot run on the fleet: RAM + Python version, §2).
- **VectorBT:** no `vectorbt` imports anywhere under `Stratex/*.py` — the adapt leg is new work: an offline parameter-sweep harness on the community edition's vectorized pattern, respecting the registry constraints (small universes / off-fleet, no PRO-only features).
- **Backtrader / Hummingbot:** no integration in the repo (reference-only by design); legs are live-trial/guardrail proofs + pattern notes, not code.

## 5. Live-leg gate — stated plainly

Acceptance item (c) needs a live demo-daemon cycle on Stratex-Server (real market data + failure injection + full-allowlist load scan, results from the live ledger). The Stratex-Server read route still awaits the owner's decision (same gate as STR-049/053/072/073 per the 21:37 watch). Repo-side legs now; live leg only if the route is granted. If the route stays closed, that is reported and the task is re-pulled — it is not sat on.

## 6. Next

Per-repo legs in order: (1) VectorBT sweep harness (adapt, new code, offline/small-universe); (2) CCXT adapter end-to-end use + failure case (adapt, verification/extension of the existing adapter); (3) reference-only live-trial/guardrail proofs for Freqtrade, Backtrader, Hummingbot (absence from every production path + pattern notes); (4) live demo-daemon cycle on Stratex-Server if the read route is granted. Checkpoint 2 files the per-repo evidence.

## 7. VectorBT leg — verification (2026-11-25 ~02:30 IST, main `e5a6876f`, S2 venv)

**CORRECTION to §4:** the checkpoint-1 claim "no `vectorbt` imports anywhere under `Stratex/*.py`" is WRONG. First-hand search on main `e5a6876f` finds extensive VectorBT prior art. The VectorBT adapt leg is therefore verification/extension of existing work, not greenfield. (Search-scope error in checkpoint 1; corrected here, not hidden.)

**Prior art verified on main `e5a6876f`:**
- `Stratex/research/sweep_harness/harness.py` — parameter-sweep harness, `SweepGrid` with a hard `max_combos: 4096` RAM guard; pattern adapted from vectorbt community edition (pattern only, vectorbt is NOT a fleet dependency). Board record TASK-IG2-STR-01, MERGED, pr 668 (IG Repo Wave 2).
- `Stratex/stratex_vectorbt/adapter.py` — `VectorBTResearchAdapter` / `SweepSpec` / `SweepResult`; sweep over a Cartesian grid, `rank()` with a profit-factor >= 1.20 gate; `validate_with_canonical_engine` hooks the canonical BacktestEngine. Pure Python (dataclasses/itertools/math); no vectorbt import.
- `Stratex/app/agents/real_vectorbt.py` — `SignalGenerator`, `PortfolioSimulation.simulate_real_vectorbt` using native `vbt.Portfolio.from_signals` when available; native path returns `engine: 'vectorbt_real'`, fallback (internal SMA simulation) returns `engine: 'vectorbt_simulated'`. Wired into `Stratex/app/trading_hub.py` and the `/api/v1/trading/engines/vectorbt/*` routes.

**Live evidence on S2 (scratch worktree of origin/main `e5a6876f`, venv python, pytest 9.2.0; worktree removed after):**
- `Stratex/tests/test_contracts.py::test_vectorbt_style_sweep` — **1 passed in 0.40s** (adapter sweep + rank on a mock eval).
- `Stratex/tests/test_additional_integrations.py::test_vectorbt_sweep_grid_and_ranking` — **COLLECTION ERROR, not run:** `Stratex/execution/__init__.py` refuses to load without the `binance` module (`ModuleNotFoundError: No module named 'binance'`). Venv pip list shows only numpy 2.2.6, pytest 9.2.0, pytest-asyncio — NO pandas, NO vectorbt, NO binance. Same absence on system python 3.10.12 and venv312 (venv312 has no pytest at all).
- Direct smoke, venv python, 120 synthetic closes: `HAS_REAL_VECTORBT=False`; `simulate_real_vectorbt` returns `engine: 'vectorbt_simulated'`, final 10504.81 on 10000 init, total_return 0.0505, sharpe 3.058, max_drawdown 0.0052. The fallback path runs and is honestly labelled; the native vectorbt path cannot run on the fleet as configured (deps absent).

**Verdict for the VectorBT leg: PARTIAL.** Adapter logic verified on the fleet venv; native vectorbt path and the integration-grid test blocked on missing fleet deps (vectorbt / pandas / binance). No dependency installed — that is a server-environment change, not attempted without direction. The live-data leg (acceptance item c) is still gated on the Stratex-Server read route (owner decision owed). Next: CCXT adapter end-to-end use + failure case (§6 order), then the reference-only guardrail proofs.

## 8. Operating rules in force this run (owner order 7143628341, watch057 7143740556)

- NO checkpoint PRs: branch work only; the work PR opens when DONE or genuinely BLOCKED. This doc update is a branch commit, not a PR.
- Board flips ride in the worker's own work PR. Stale flips owed by M17 ride in the next work PR: VYR-050 IN_REVIEW/pr 1641 → MERGED, OBS-023 IN_REVIEW/pr 1633 → MERGED, VYR-054 AVAILABLE/owner muse_17 → MERGED (all three verified still unflipped on main `e5a6876f` this run).
- Paired verification: STR-077 (M17) → verifier M11 (starts when the work PR opens). M17 is verifier for STR-074 (TP4) → M17; no STR-074 work PR is open yet, duty armed.
- Hourly "still working" hub posts ABOLISHED (rule 7): this verification is recorded here in the branch doc, not posted. Posts only on claim, completion-with-evidence, or blocked-with-reason.
- The STR-077 live-leg gate question (does M3's STR-071 live-leg route via the bridge WRITE client change the gate?) is still unanswered in watches 054–057; #1713 (STR-071) is merged with live evidence, but no general lift of the owner stop order appears in any watch. Gate unchanged.
