# TASK-STR-084 — Scope (indicator-ranking evaluation, the open S-20 gap)

**Claim:** hub #1483 comment 7158821992 (~15:18 IST, 2026-11-25), under the blocked-head rule (watch090 ruling 3; watch091 demand).
**Board verified first-hand on main c554c54f:** STR-084 AVAILABLE / owner null / branch null / pr null; no prior claim, branch or PR.
**Branch:** muse8/task-str-084 from main c554c54f. Board flip AVAILABLE → CLAIMED rides in the work PR.

## What the task asks

- Source: stratex package S-20, item DYhkjyHii9g (wave-2 cluster #91). The reel ranks Order Flow, Volume Profile, Liquidity Sweep and Anchored VWAP at 9–10/10 and RSI, MACD and raw chart patterns at 0/10, but no module on main ranks or comparatively evaluates the four named indicators, and "liquidity sweep" has zero code hits.
- Build: the scored comparative evaluation under the frozen research bar on the RD-002 panels — implement what is missing (liquidity-sweep detection first), run all approaches head to head, persist the ranked results. Any family clearing the bar follows the normal RD admission path; families under PF 1.2 are deleted per the standing rule.
- Done = the ranked results table persisted with a verdict per approach.

## Code state verified first-hand on main c554c54f

- `liquidity_sweep` / `liquidity sweep`: ZERO implementation hits in `Stratex/` (exact-phrase code search: 1 hit, the disposition doc itself). The gap is real.
- Order-flow features exist: `Stratex/rigorous_backtest/ig/dom_features.py` (sha 55cc3e0b, 4,235 B; TASK-IG-STR-02; spread / mid / microprice / imbalance / depth-within-band / wall detection). Research inputs only — they describe a snapshot, they are not signals.
- Legacy VWAP / volume-profile strategy exists: `Stratex/strategies/vwap_volume_profile.py` (sha ff43a0e5, 10,942 B; VWAP + SD bands, Volume Profile, POC / Value Area, Anchored VWAP from session open and swing highs/lows, order-flow imbalance). Note: it carries `_OOS_WIN_RATE_PRIOR = 0.57` and `_RR_RATIO = 2.0` as unproven priors, not evidence.
- Baselines exist: `Stratex/strategy_macd_trend.py` (MACD), `Stratex/strategy_rsi_momentum_forex.py` (RSI).
- RD-002 panels exist: `Stratex/rigorous_backtest/rd2/panels.py` (sha 1d1a6d3e, 6,848 B; crypto30/12/6, forex28/12, comm7, idx7/3; fold profiles STANDARD W1..W5, LATE W2..W5; data ONLY from verified caches — Binance Vision monthly archives + Yahoo Finance chart API, per-zip / canonical CSV SHA-256 + gap audit).
- Frozen research bar (per the disposition §4): >=200 OOS trades, PF >= 1.2, fold consistency, 2x costs, Bonferroni; strict OOS PF < 1.2 → deleted.

## The conflict — prior SKIP disposition found in scoping (first-hand)

- TASK-IG2-STR-18 is CLOSED on the board (owner muse_ai, PR #792): "S-20 indicator-ranking item CLOSED as SKIP — opinion ranking, no spec, not mechanically specifiable". Disposition doc `Stratex/rigorous_backtest/ig/S20_INDICATOR_RANKING_DISPOSITION.md` (sha b2c89d92, 5,653 B, 2026-11-16) — read in full.
- Its grounds: the reel is a ranked opinion list with one-line slogans. For liquidity sweep — and equally for every other named concept — the item states NO level reference, sweep trigger, entry rule, stop-loss, target, instrument, timeframe, session or sizing. "There is nothing to freeze." A pre-declared RD candidate must freeze source-stated rules (SRS PR #742 / Box Theory PR #729 standard); any rule set would be 100% invented by the fleet and falsely attributed to the source — fabrication.
- Its reopen condition: "Reopen only if a source states mechanical liquidity-sweep rules (defined level reference, sweep trigger, entry, SL/TP, instrument, timeframe) that can be pre-declared verbatim through the normal RD route at the full bar."
- The STR-084 board record (filed 2026-11-25, re-audit batch 3, under the owner's DEFAULT = IMPLEMENT correction) does NOT cite IG2-STR-18 or the disposition.

## Ruling owed (coordinator) — no build until it lands

- **(A) STR-084 supersedes the SKIP as a fleet-defined evaluation:** the reel supplies only the concept shortlist; all sweep / entry rules are labelled fleet-defined conventions (NOT the creator's), evaluated head to head under the frozen bar. The disposition's fabrication objection is about false attribution; honest labelling answers that part — but the "100% invented" core remains, and the disposition explicitly says no capability is lost by the closure (the fleet already ranks methods by evidence under the full bar).
- **(B) STR-084 is a duplicate / stale re-audit filing of an already-dispositioned item** → close STR-084 as already-dispositioned (IG2-STR-18 SKIP stands), no build.
- I will not invent sweep rules unilaterally and will not build until the coordinator rules. This is the REL-001 pattern: verify the ticket against the board and the record first; the defect may be stale.
- If (A): implementation plan is (1) a fleet-defined liquidity-sweep detector (level reference = prior swing high/low; sweep = wick beyond the level + close back inside; entry / stop / target frozen in a declaration BEFORE any run), (2) wire the four approaches + the RSI/MACD baseline to the RD-002 panels via rd2 families / combo / modrun, (3) a ranked results table with a per-approach verdict. Local-execution gate: watch090 ruling (1) authorizes local runs; if the runtime gate still demands a tap, the exact refusal text gets posted (ruling 2).
- If (B): close with a board flip + this scope doc as the record.

## Queue

STR-084 (head, blocked on ruling) → EARN-009 → STR-047 (IN_PROGRESS, wiring leg held on coordinator clearance + owner stop order). STR-083 stays blocked-head (execution gate; coordinator re-slots / unblocks next run).

— Muse 8, 2026-11-25 ~15:20 IST
