# TASK-STR-069 — Harden the research-to-backtest-to-incubate checklist

**Owner:** Muse 14. **Claim:** hub #1483 comment 7149912740 (~07:15 IST 2026-11-25).
**Branch:** `muse14/task-str-069`. **Base:** main `79431498`.

## What changed

`Stratex/rigorous_backtest/ig/research_desk.py` — `risk_checklist()` (stage 4)
gains the six named items from the board acceptance, each gated on
caller-supplied backtest `evidence` (new optional `evidence` parameter;
`min_trades=50` and `max_dd_to_return=0.5` defaults encode the acceptance):

1. `clean_data_retest` — a clean-data / unseen-data re-test ran after the
   big backtest.
2. `min_trades` — backtest trade count >= 50.
3. `drawdown_vs_return` — max drawdown <= 50% of total return (the strategy
   earns at least 2x its worst drawdown); a non-positive return fails.
4. `tiny_size_incubation` — tiny-size incubation ran before any scale-up.
5. `repainting_check` — a repainting signal fails with a recorded warning
   (the backtest cannot be trusted).
6. `bot_provenance` — the bot was built by us; otherwise it fails
   ("never run a bot you did not build").

`run_desk()` gains an optional `backtest_evidence` parameter (dict mapping
a setup symbol to its evidence dict), threaded into the per-symbol
checklist.

## Design: evidence-gated, not a separate stage

The acceptance says "the checklist gains the named items", so the six
items live inside `risk_checklist()`, not in a separate function. An item
with no evidence is recorded **unevaluated** (`ok` True, `evaluated`
False) and named in the result's `unevaluated` list, so a plan with no
backtest evidence keeps the pre-STR-069 behaviour — the existing test
(`risk_checklist(p, SETUP, ...)` with no evidence passes) is unchanged.
When evidence IS supplied, the item is evaluated and can fail the
checklist. This follows the desk's own rule: it reports what it does
not know instead of guessing (the same rule as `scan()`'s
`context_missing` flag). The source doc cited in the board evidence
(`CLASSIFICATION-2026-11-24.md`) is not in the repo; the work proceeds
from the board acceptance, which is fully specified.

## Live evidence (run, not just code)

`pytest -q ig/tests/test_research_desk.py` (venv `/tmp/muse14-str069`,
from `Stratex/rigorous_backtest/`): **15 passed in 0.12s** — the 10
pre-existing tests plus 5 new STR-069 tests (no-evidence unevaluated,
good-evidence pass, each item fails, boundaries, `run_desk` threading).

Live demo run of the hardened checklist (same venv, real module):

- Good evidence (120 trades, 8% drawdown / 24% return, re-test done,
  incubated, no repaint, built by us) → `passed: True`, `unevaluated: []`.
- Bad evidence (30 trades, 20% drawdown / 24% return, no re-test, no
  incubation, repainting, not built by us) → `passed: False`, all six
  items failing with the named details.
- No evidence → `passed: True`, all six named in `unevaluated`.

## Five states

- Implemented: YES (the six items are in the research desk, alongside
  the existing two-tier admission / self-experiment loop discipline).
- Tested: YES (15/15 pytest, plus the live demo run above).
- Merged: NO (this work PR).
- Deployed: NO (research-only module; no live agent leg — the desk
  produces memos, never orders; nothing is sent anywhere).
- Production-verified: NO (no live-agent leg applies; the verification
  is the test suite + the live demo run above).

## Notes

- No other caller of `risk_checklist()` / `run_desk()` exists outside
  `research_desk.py` and its test file, so the new optional parameters
  are backward-compatible.
- `test_research_desk.py` is already in the CI tier-1 file list
  (`.github/workflows/friday-universe-ci.yml`); no test file was added,
  so no contracts-workflow change is needed.
- No paired verifier was assigned for STR-069 (non-wave P2; watch057
  assigns verifiers for STR-070..078 / VYR-070..080). A peer review is
  requested on this PR.
