# TASK-STR-078 — Checkpoint 1: claim verification + repo-side mapping (2026-11-25 ~13:45 IST)

REPO-IMPLEMENT: Stratex repos — FinRL (reference-only), Lumibot (reference-only),
Vibe-Trading (adapt), AutoHedge (reference-only), QATS Trader API (reference-only).
Target Stratex, wave 1, P1.

Claim: hub #1483 comment 7138261614 (Muse 11, 2026-11-24 ~22:13 IST), central-pool
pull model (owner directive 7136890552). Claim PR #1686 MERGED 23:07:08 IST
(merge 4904bdd7). Branch `muse11/task-str-078-repo-implement`, head `5adf4373`
(claim commit only — verified via API this run). Board on main `768e18da`
(22,649 lines, verified 13:13 IST): STR-078 CLAIMED/muse_11/pr null/P1. Main has
since moved to `36e2e2c9` (PR #1797 REL-096, merged by Surendra 13:20 IST); the
four files mapped in §2 were re-verified blob-for-blob against that main this
run — SHAs match, STR-078 entry unaffected. No competing claim. This checkpoint
answers the watch086 demand (hub 7156322977): STR-078 is moving — repo leg now,
live legs gated as §3.

## §1 Registry evidence — the five repos (read first-hand)

Source: `IntelX/intelx/registries/scouted_repos.json` (102 entries, schema
`intelx.scouted_repos/v1`, generated from 102 verified spec cards).

| Repo | Fit | Why (registry `fit_rationale`, condensed) |
|---|---|---|
| AI4Finance-Foundation/FinRL | reference-only | Env/reward design (state features, turbulence index, transaction-cost modelling in the Gym env) is the reference if Stratex ever opens an RL research track. DRL training is not hostable: no GPU, ~956 MB RAM per VM, PyTorch/Stable-Baselines3 stack; WRDS/premium feeds are paid or account-gated, against the free-only rule. "Read the env design; do not integrate." |
| Lumiwealth/lumibot | reference-only | Backtest = paper = live single-strategy-class discipline, and the hybrid guardrail (agent proposes with `allow_trading=False`, deterministic code executes), are patterns worth copying. Adopting it would duplicate Stratex's existing engine; broker set is US-centric (no OANDA, Binance only indirectly via CCXT); serious backtesting leans on paid data, against the free-only rule. "Learn the guardrail pattern; do not integrate." |
| HKUDS/Vibe-Trading | adapt | Direct deployment is out: needs Python 3.11+ (fleet is 3.10) and the full FastAPI/React/agent stack is far over the ~180 MB service cap. What adapts is the research layer: the MIT alpha-factor library (~478 factors, Alpha Zoo), the plain-English backtest workflow and the committee-style research pattern — mined selectively, run off-fleet or post-ARM. Live trading is unvalidated upstream, and the +243.6% figure in the carousel is a backtest screenshot. |
| The-Swarm-Corporation/AutoHedge | reference-only | The role-specialised agent pipeline (thesis → quant check → risk sizing → execution) is a useful reference mirror for Stratex's own design. Nothing else transfers: Solana memecoin execution is irrelevant to Stratex's Binance/OANDA demo programme, there is no demo/paper safety mode, it demands a live wallet key, and the repo has been stale since spring 2026. |
| QuantityProject/qats-trader-api | reference-only | Docs-only repo — there is no code; the trading system is proprietary and hosted at prop.qats.us. Using the API means opening a QATS Prop account, and its evaluations are a paid product: paid spend under the FREE-only rule and a new venue outside Stratex's demo-only programme on Binance demo and OANDA practice. No QATS account without an explicit owner decision. The research value is the API design, genuinely well-shaped and worth copying into Stratex's own venue layer: idempotency keys on every write, confirming an uncertain order result by command ID instead of resending it, server-side risk checks a bot cannot bypass, and a free sandbox with a virtual $100,000 account and keys kept separate from any real evaluation. |

## §2 Repo-side mapping — what exists in Stratex today (verified against main 36e2e2c9)

| Repo | In-repo artefact (blob SHA on main `36e2e2c9`) | Live-path wiring | Status |
|---|---|---|---|
| Vibe-Trading (adapt) | `Stratex/app/agents/real_vibe_trading.py` (26,096 B, sha `c5a184a1…`) — `AlphaFactor` / `MomentumFactor` / `GTJAFactorLibrary` (26 GTJA-numbered factor expressions, named alpha-factor registry), factor z-score / IC / rotation, portfolio construction, backtest evaluation. A pure-Python re-implementation of the research layer, not the upstream library. | Engine 10 in `Stratex/app/trading_hub.py` (sha `79e51b74…`); alpha-factor references in `Stratex/api/real_trading_routes.py` | ADAPT PRESENT in-repo as the mined research layer. NOT yet proven in the live production path — the live trial is checkpoint 2/3. |
| Lumibot (reference-only) | `Stratex/app/agents/real_lumibot.py` (14,478 B, sha `505d8943…`) — `LumibotManager`; the upstream import is best-effort (`try: import lumibot`, `HAS_REAL_LUMIBOT` flag). Upstream is NOT vendored. | Engine 6 in `trading_hub.py` | Wrapper exists; the guardrail pattern (`allow_trading=False`) is NOT yet demonstrated as a live guardrail — checkpoint 2. |
| AutoHedge (reference-only) | `Stratex/app/agents/real_autohedge.py` (11,986 B, sha `5457505e…`) — `SwarmAgent` / `SwarmConsensus` / `KellyPositionSizer`; a pure-Python re-implementation of the swarm-consensus + Kelly-sizing concepts. | Engine 9 in `trading_hub.py` | Concepts re-implemented; no upstream code runs. |
| FinRL (reference-only) | None — zero references to "finrl" anywhere in `Stratex/` (grep, this run) | None | ABSENT from every repo-side production path (guardrail proof of absence, repo-side). Live-tree confirmation is checkpoint 2. |
| QATS (reference-only) | None — zero references to "qats" anywhere in `Stratex/` (grep, this run) | None | ABSENT from every repo-side production path (guardrail proof of absence, repo-side). Live-tree confirmation is checkpoint 2. |

## §3 What "implemented" requires — and what is HELD

Per the board acceptance: the adapt (Vibe-Trading) must run in Stratex's live
production path, proven by one real end-to-end use filed as evidence incl. a
failure case; each reference-only entry needs a live trial or guardrail proof of
absence from every production path, filed per repo; plus a live demo-daemon cycle
on Stratex-Server on real market data + failure injection (venue disconnect,
stale feed) + full-allowlist load scan, with results filed from the live ledger.

HELD — owner stop order (ALL server moves FROZEN, ~16:42 IST 2026-11-24, still
in force per watch086): the demo-daemon cycle, failure injection and load scan
are live server moves and are HELD. CLEARED — 21:57 watch ruling 3: Stratex-Server
READ-ONLY live legs. Checkpoint 2 uses read-only legs only (live-tree grep for
FinRL/QATS absence, service state, ledger reads) plus the Vibe-Trading adapt
live-trial design. The live trial and the daemon cycle need Muse/owner clearance
— requested in this run's hub post.

Note: `PRODUCTION-VERIFICATION-PROGRAMME.md` is missing from the repo (confirmed
again this run — no such file in the checkout; ruling 6, 22:17 watch 2026-11-24);
the board record governs.

Live state (last verified 13:13 IST self-check, ~30 min before this run): FRIDAY
`/health` 200 overall "healthy"; both Oracle servers ONLINE; Memora 401 fix holds
(0×401, PID 3747325); S1 FRIDAY.service inactive by design. The S2 tree restore
is authorised (owner order, watch086 correction 7156364219); no service restarts
under the stop order.

## §4 Plan

- Checkpoint 2: read-only live verification (Stratex-Server tree grep, service
  state, ledger reads) + Vibe-Trading adapt live-trial design (one real
  end-to-end use of the GTJA factor path in the live path + failure case) +
  Lumibot guardrail-pattern trial design. No live moves.
- Checkpoint 3+: live trial + demo-daemon cycle once Muse/owner clearance lands.
- Queue: STR-078 (current) → FRG-030 → FRG-021 (STR-083 claimed by Muse 8 per
  watch083 re-slot; FRG-021 named pos-3 in watch085).

## §5 States (reported separately, per the implementation standard)

- implemented: NO — the adapted component exists in-repo but has no proven
  live-path run yet.
- tested: NO — no live trial run yet.
- merged: NO — this branch is not yet PR'd (one work PR when DONE/BLOCKED,
  rule 1, owner order 7143628341).
- deployed: NO.
- production-verified: NO.
- Usage: 24% of free weekly limit (checked this run via `subscription-status
  status`; reset Nov 29, 6:00 PM IST; additional tokens 0% used). Not nearly
  exhausted — no wrap-up, no schedule changes.

— Muse 11
