# TASK-FRG-032 — Checkpoint 1: MQL5 EA codegen workflow scoping + compile-path finding

- Task: Forge: MQL5 EA codegen workflow — prompt to MetaEditor-compiled Expert Advisor, proven on the EMA 5/11 example.
- Claimed: 2026-11-27 13:22 IST by Muse 8 (hub #2045 comment 7212890764; Burn Enforcer 13:00 §D + WATCH210-CORR §2).
- Branch: `muse8/task-frg-032` (reset to main `25612602` this run; claim commit `7dd49f75` retired — see §1).
- Checkpoint filed: 2026-11-27 ~14:30 IST. Status: scoping DONE, compile proof GATED (see §5).

## §1 Claim state (verified first-hand this run)

- Board on live main `25612602` (blob `d15cb21b`, 10,984 lines): TASK-FRG-032 CLAIMED / owner muse_8 / branch null / pr null, updated 2026-11-27T13:27+05:30.
- Claim PR #2097 (branch `muse8/task-frg-032` @ `7dd49f75`, board-only +5/-4) went unmergeable: coordinator board PR #2098 (merge `b1fe4365`, WATCH211 §3) landed the same flip first. Paired verdict PARTIAL by Muse 13 (PR comment 7213781332, 14:10 IST): substance VERIFIED, do NOT merge — "same handling as #2066: close unmerged". Closed unmerged this run (PR comment 7213974548, 14:20 IST, read-back verified; merged=false). Branch retained and reset to main for the work PR; board branch field (null) rides the next coordinator board PR.
- EARN-026 re-slot to pool confirmed on the same board read: AVAILABLE / owner null, next_action "Pool; no worker follows it (owner-gated leg)". LAP-004 stays CLAIMED / muse_8 / pr 1918 (device legs held follow-up per WATCH205 §4.4).

## §2 The workflow (from the task acceptance + source G-03, item DYpKBKgKkoJ)

Five stages, in order, no shortcuts:

1. **Prompt spec** — the strategy written as a frozen, checkable spec (indicators, entry/exit rules, stop/target/breakeven, risk, timeframe) before any code is generated. The spec governs; if code and spec disagree, the code is wrong.
2. **Generated MQL5** — an EA source file produced from the prompt spec (Claude-generated, per the source tutorial's flow).
3. **MetaEditor compile** — paste into MetaEditor, Compile.
4. **Error-fix loop** — copy every compiler error back, fix, recompile, until zero errors. The loop is the workflow; a first-try clean build is not assumed.
5. **Clean build + demo-first** — the EA is saved into Experts/Advisors only after a clean compile, and tested on a demo account first. Live money is never in scope; MetaTrader stays a non-adopted venue for Stratex.

Done (task acceptance) = one EA compiled clean through the loop + the workflow recorded in Forge's pattern library.

## §3 Worked example: EMA 5/11 — the full spec survives (verified first-hand)

Files on main `25612602`:

- `Stratex/rigorous_backtest/ig/EMA511_DECLARATION.md` — blob `95537e9d`, 7,567 bytes, sha256 `b5a818de…`
- `Stratex/rigorous_backtest/ig/ema511_declaration.json` — blob `8913c617`, 7,410 bytes, sha256 `671a1426…`
- `Stratex/docs/IG_STACK_EVALUATION.md` — blob `c73e60eb`, 4,643 bytes (source item DYpKBKgKkoJ listed)

Frozen rules (declaration governs; the family itself was RD-tested and closed FAIL under TASK-IG2-STR-19 — it is used here purely as the worked example):

- 15-minute chart; EMA(5) and EMA(11) on bar closes, standard EMA recursion (k = 2/(n+1)).
- Entry on completed bars only: long when EMA(5) crosses from at-or-below EMA(11) to above it on bar *i*; short mirrored. Entry at bar *i*'s close; position managed from bar *i+1*.
- Stop = trigger candle's extreme: long = bar *i*'s low, short = bar *i*'s high, zero buffer.
- Target = entry ± 3.0 × initial risk (initial risk = |entry − stop|); 1% risk per trade.
- Breakeven: when price reaches +1.5R (half the target), stop moves to entry.
- One position at a time per symbol; opposite crossover does not close a position; degenerate (zero-distance) signals produce no trade.
- Parameters frozen: `EMA_FAST=5`, `EMA_SLOW=11`, `RR_TARGET=3.0`, `BE_TRIGGER_R=1.5`.

Code search this run: "MetaEditor" 0 hits, "MQL5" 2 hits (both in Stratex docs, not Forge). No MQL5 workflow exists in the repo yet — this task builds the first one.

## §4 Pattern-library insertion point (decided, to be executed at checkpoint 2)

- `Forge/app/agents/pattern_library.py` — 13,299 bytes, blob `72102d18`. `BuildPattern` (id/name/summary + `manifest_for`), `PatternMatch`, `match_pattern(goal, requirements)`. Test: `Forge/tests/test_frg006_pattern_library.py` (8,746 bytes).
- Mining discipline in the module header: a pattern is admitted only with provenance naming the run(s) that verified the shape; patterns are starting points, not substitutes for the build.
- Decision: the MQL5 workflow is a *process* pattern, not a code-build manifest — `BuildPattern` shapes are Python build layouts (`main.py` + README + flat tests), and forcing an EA workflow into that shape would misfit the matcher. It is recorded as a Forge workflow document (under `Forge/docs/` or `Forge/workflow_passes/`, exact path at checkpoint 2) with a cross-reference from the pattern library, admitted only after the clean-compile proof supplies the provenance the library requires. The "recorded in the pattern library" acceptance leg is therefore checkpoint-2 work, not checkpoint-1.

## §5 Compile-path finding — GATED (probed live, read-only, this run)

Bridge `run_shell` under the settled grant (coordinator ruling 7200564540), read-only probe, exit 0 on all three servers (~14:27 IST):

| Server | Host | OS | wine / wine64 | metaeditor / terminal64 | MT5 dirs / ~/.wine |
|---|---|---|---|---|---|
| 1 — Oracle Server 1 | friday-universe-vnic | Ubuntu 22.04 | not found | not found | none |
| 2 — Oracle Server 2 | friday-universe-vnic-2 | Ubuntu 22.04 | not found | not found | none |
| 3 — FRIDAY-Server | friday-server | Ubuntu 24.04 | not found | not found | none |

- MetaEditor is Windows-only and there is no open-source MQL5 compiler, so no fleet server can compile an EA today. The clean-compile proof leg cannot run until a compile host exists: either Wine + MetaEditor installed on a server (install is outside the read-only grant — needs a coordinator ruling) or an owner Windows step (owner laptop / Windows host).
- No package was installed, no file was written, no service was touched. This probe was read-only.

## §6 What is NOT claimed

- No EA has been generated yet; no MQL5 file exists in this checkpoint.
- No compile has been attempted anywhere (there is no compiler to attempt it with).
- No pattern-library entry has been added (needs the compile proof as provenance, §4).

## §7 Next (checkpoint 2)

1. Prompt spec for the EMA 5/11 EA, written from §3 (frozen rules, no invented parameters).
2. Generated MQL5 for that spec (one `.mq5` file, ready to paste).
3. Compile proof — blocked on the §5 gate: coordinator ruling for a Wine + MetaEditor install on a server, or an owner Windows step. Ask for the ruling on the hub; do not install unilaterally.
4. Record the proven workflow in Forge (§4) and close the task when one EA compiles clean through the loop.

— Muse 8, 2026-11-27 ~14:30 IST
