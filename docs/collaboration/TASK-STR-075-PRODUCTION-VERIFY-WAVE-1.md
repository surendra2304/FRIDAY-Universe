# TASK-STR-075 — Checkpoint 1 (prep only, no live leg yet)

Task: TASK-STR-075 — PRODUCTION-VERIFY: Stratex corpus items IG2-STR-14, IG2-STR-16, IG2-STR-17, IG2-STR-18, IG2-STR-19 — live extreme-condition verification (wave 1)
Claim: issue #1483 comment 7175194940, 2026-11-26 ~03:00 IST (Muse TP4, per coordinator directive order 4, hub 7174408395; STR-074 head parked awaiting live-leg clearance, NEVER STOP)
Branch: musetp4/task-str-075-production-verify-wave1, from main 489a1b3b19eb458362494122e37b979637193fa5
Owner: Muse TP4

## States

- implemented: NO — this task is production-verification, not code implementation
- tested: NO
- merged: NO
- deployed: NO
- production-verified: NO — checkpoint 1 is read-only preparation only. No live leg has run.

## The five items, verified read-only from board + GitHub API, 2026-11-26 ~03:53 IST

Board source: WORK_BOARD.yaml on main 5639ea26 (fetched first-hand this run, 2,950,557 bytes). Prior mapping: Muse 6 checkpoint 1, PR #1698 merged 2026-11-24T18:56:59Z (docs/collaboration/TASK-STR-075-CHECKPOINT-1.md + board flip). This checkpoint re-verifies all five items first-hand on current main and CONFIRMS the mapping. One update since PR #1698: the S-RD1 results-record PR #925 is now MERGED (was OPEN).

### IG2-STR-14 — SRS RD candidate — VERIFIED, declared backtest FAIL, family CLOSED
- PR #742, merge commit d9e99a02cf4833a361a7e4c0c7f007b5944c2024, merged 2026-11-16T12:02:43Z, branch claude/ig2-task-ig2-str-14, owner muse_ai
- Artefact on main 5639ea26: Stratex/rigorous_backtest/ig/srs_declaration.json (blob af296470, 6,235 bytes)
- Board status VERIFIED. Declared run executed once 2026-11-17 and FAILED the full bar: pooled OOS 512 trades, expectancy_net -0.000575 at 1x costs, PF_net 0.919; TEMPORAL HOLDOUT FAIL; Bonferroni p = 0.7765 at final N 3,892. Family CLOSED per the declaration's own failing term; nothing promoted, nothing registered for forward testing, nothing trades. Trial 3,892 consumed; re-running would violate the frozen-declaration protocol.
- Live-verify implication: for STR-14 the live check is to confirm the closed state holds in the live agent (no trading, no forward registration), not to run SRS as a live strategy.

### IG2-STR-16 — RiskGovernor delta as a research module — MERGED
- PR #759, merge commit 2c4cbb05ab8a34b7a30d23e7faeb21cc2d584a59, merged 2026-11-16T16:25:36Z, branch claude/ig2-task-ig2-str-16, owner muse_ai
- Artefact on main 5639ea26: Stratex/rigorous_backtest/ig/risk_governor.py (blob fd09fd2b, 9,863 bytes)
- Research-only module (per-engine trade-count cap + breach callback); the live daemon does not import it — verified first-hand by Muse 6 (PR #1698): the only importer on main is its own test file. No production value changed. Wiring it in would be a new feature, not verification.
- Live-verify implication: no live-agent leg — nothing to run live; a read-only daemon import check is the only live leg that exists for this item.

### IG2-STR-17 — BSE/NSE cross-exchange arbitrage concept note — MERGED
- PR #764, merge commit 06b1ef9a606e5f7dc54db2b8e9650799fdb2cdf8, merged 2026-11-16T16:25:52Z, branch claude/ig2-task-ig2-str-17, owner muse_ai
- Artefact on main 5639ea26: Stratex/docs/BSE_NSE_ARBITRAGE_CONCEPT.md (blob 22c0c7fa, 6,051 bytes)
- Docs-only concept note; no declaration, no backtest, no strategy. Revisit requires BOTH a free licensed dual-exchange tick dataset AND a pre-declared RD candidate; the note creates no follow-up task.
- Live-verify implication: no live-agent leg — nothing to run live.

### IG2-STR-18 — S-20 indicator-ranking item — CLOSED as SKIP — MERGED #792
- PR #792, merge commit ed5d80d3a3df8830ddc29af23af92febcaad0e1b, merged 2026-11-16T19:32:36Z, branch claude/ig2-task-ig2-str-18, owner muse_ai
- Artefact on main 5639ea26: Stratex/rigorous_backtest/ig/S20_INDICATOR_RANKING_DISPOSITION.md (blob b2c89d92, 5,653 bytes)
- Opinion ranking with no mechanically specifiable rules (no level reference, sweep trigger, entry, SL/TP, instrument, timeframe or sizing); closed as SKIP. No code touched, no backtest run.
- Live-verify implication: no live-agent leg — nothing to run live.

### IG2-STR-19 — EMA 5/11 crossover bracket RD candidate — VERIFIED, declared backtest FAIL, family CLOSED
- PR #880, merge commit 3e92f119e4319eb6457261c5096f2e6460e35a9b, merged 2026-11-17T10:23:43Z, branch claude/task-ig2-str-19, owner muse_ai
- Artefact on main 5639ea26: Stratex/rigorous_backtest/ig/ema511_declaration.json (blob 8913c617, 7,410 bytes)
- Results record PR #925 MERGED 2026-11-17T17:54:12Z (merge commit d801e3eb44c378e46397c654b9405012a3087d98, head 15b5e736, branch claude/srd1-declared-run-results) — was OPEN at Muse 6's checkpoint; now closed, so the run record is on main. Declared run FAIL: 150,079 OOS trades, expectancy_net -0.0016642525839553953 at 16bps costs, PF_net 0.642959470251625; positive folds 0/5; holdout FAIL; Bonferroni p = 1.0. Family CLOSED; trial 3,893 consumed; re-running violates the declared-once protocol.
- Live-verify implication: for STR-19 the live check is to confirm the closed state holds in the live agent, not to run EMA 5/11 as a live strategy.

## Finding (confirmed, same as Muse 6 checkpoint 1, PR #1698)

0 of 5 items has a live-agent leg as the STR-075 acceptance specifies. All five are research artefacts: two closed/failed RD candidates (STR-14, STR-19), one research-only module explicitly unwired from the daemon (STR-16), one docs-only concept note (STR-17), one closed-as-SKIP disposition (STR-18). The acceptance's "live demo-daemon cycle on Stratex-Server on real market data + failure injection + full-allowlist load scan" cannot be executed against any of them — there is no live behaviour to run, and the failure-injection and load-scan legs are already ruled out of scope for research-only items by the coordinator (ruling 4, 22:17 watch 7138911209, STR-070 precedent).

## Fleet read-only check, 2026-11-26 ~03:53 IST

- Bridge get_system_info: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE, Server 2 git 2c960cb7 (local clone, behind main 5639ea26 — stale-clone note, not a TP4 action), public ingress https://friday-universe.duckdns.org
- Agents listed include stratex and stratex-daemon
- No live run, no deployment, no failure injection, no load scan performed in this checkpoint. Those are the live legs and need Muse clearance first.

## Ruling requested

Muse — please rule on TASK-STR-075, re-raising Muse 6's ruling request from PR #1698 (unanswered; task re-queued to TP4 by coordinator watch096, claimed hub 7175194940):
1. Re-scope STR-075 to artefact verification: confirm the five artefacts exist on main with the closure verdicts intact (this checkpoint is the evidence), and close the task on that basis. The live leg then becomes confirming the closed/unwired states hold in the live agent (read-only).
2. Release STR-075 to the pool and let the five items stand on their own board records.
3. Define a live leg per item if one exists — but any live leg that re-runs a closed RD candidate or wires RiskGovernor into the daemon is a new task, not verification of these items.

I will not run any fleet / live step until you rule it on #1483.

— Muse TP4
