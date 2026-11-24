# TASK-STR-064: BSM-vs-market option mispricing scan — checkpoint 1

## Task

Stratex: BSM-vs-market option mispricing scan — ranked research report, no
trading. Scan runs over the existing options-pricing module's instruments
(TASK-IG-STR-01) and flags options whose market price breaks from the
Black-Scholes-Merton model price. A ranked mispricing report is emitted in
research; no trading is placed from this signal.

## Assignment

- Coordinator watch054 (hub #1483 comment 7142399844), ruling 1: **STR-064 →
  Muse 15** (M16 pre-staged first but holds STR-065; reserve order if this
  claim lapses: M16, then M12). Watch055 nudge (7142822375) restated it.
- Board verified first-hand on main `b0276946`: TASK-STR-064 AVAILABLE,
  owner null, pr null. Hub read through 1047 comments (2026-11-25 ~01:58
  IST): no competing claim. Branch
  `muse15/task-str-064-bsm-mispricing-scan` from main `b0276946`.
- Queue: STR-064 (head) → FRD-043 (held under the owner stop order) →
  VOI-033 (gated).

## Checkpoint 1 — scanner implemented + tested (this PR)

New module `Stratex/rigorous_backtest/ig/mispricing_scan.py` (stdlib only,
offline, deterministic), built on TASK-IG-STR-01
(`Stratex/rigorous_backtest/ig/options_pricing.py`: `bs_price`,
`implied_vol`, `put_call_parity_residual` — VERIFIED LIVE in STR-070):

- `scan_mispricing(instruments, r, sigma_ref, flag_threshold=0.05, q=0.0)`:
  per instrument, model price at the reference vol; absolute + relative
  deviation; implied vol solved from the market price; IV-vs-reference
  deviation; moneyness. Market prices are caller-supplied data — the
  module connects to no venue, so it stays testable offline.
- Statuses: `OK` (|rel dev| < threshold); `FLAGGED` (|rel dev| >= 5%
  default, configurable); `INVALID_PRICE` (market price violates
  no-arbitrage bounds, so no implied vol exists — the strongest break);
  `ERROR` (malformed instrument record — recorded, scan continues).
- `ranked_report(results)`: by |rel deviation| descending (invalid-price
  rows carry inf, so they rank first), ties by |abs deviation|.
- `render_markdown(results, title)`: ranked research report (counts +
  table) for the evidence record.

Design decisions (recorded, not hidden): the model price uses one
reference vol per scan (caller picks it — ATM IV or historical vol — so
the report states its assumption); the IV cross-check is per instrument
and independent of that choice; at T == 0 the model is intrinsic value
and IV is undefined (row stays scannable); a worthless-by-model option
trading above zero carries rel dev inf and ranks first.

## Test evidence (run first-hand this run, 2026-11-25 ~02:15 IST)

No pytest exists on this VM (`python3 -m pytest`: no module), so both
suites were run with a stdlib runner that imports each test module and
calls every `test_*` function:

- `ig/tests/test_mispricing_scan.py` (new, 8 tests): **8 passed, 0 failed**
  — zero deviation at model prices; +20% flagged and ranked first;
  below-bound ITM put recorded INVALID_PRICE without killing the scan;
  put/call IV consistency; ranking order; malformed rows recorded ERROR
  and ranked last; markdown render counts; threshold configurable.
- `ig/tests/test_options_pricing.py` (existing IG-STR-01, 7 tests):
  **7 passed, 0 failed** — no regression.
- `python3 -m py_compile` on both new files: OK.
- Smoke render: a +10% call flags correctly (IV 0.2219 vs ref 0.20);
  a model-priced put reports +0.00%, IV 0.2000.

Caveat (stated plainly): these ig tests were **not collected by any
PR-triggered workflow** when first filed, and the `contracts` CI job
failed on it first-hand (guard `scripts/ci_test_collection_audit.py`,
TASK-REL-068: "1 test file shipped in this PR collected by NO
PR-triggered workflow"). Fixed in this PR by adding the new test file to
the Stratex tier-1 pytest invocation in
`.github/workflows/friday-universe-ci.yml`; the guard re-run passes
("374 covered, 1 checked, PASS"). The suite also passed 8/8 under a
pytest-style import run locally (no pytest installed on this VM).

## Checkpoint 2 — live chain + ranked report (next)

- Fetch a real option chain (Deribit public API, no auth — dominant
  crypto options venue; Binance options as fallback) and run the scan on
  live market prices; file the ranked report from the live data.
- Route: direct fetch from here if reachable, else on Stratex-Server
  via the proven S2→ssh read-only route (STR-073 precedent). No deploy,
  no venue writes, no trading — research read-only.
- No live moves made in checkpoint 1; no orders placed; no secrets in
  the code or this doc.

## Board

TASK-STR-064: AVAILABLE → CLAIMED (owner muse_15, branch
`muse15/task-str-064-bsm-mispricing-scan`, this PR).

— Muse 15
