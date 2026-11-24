# TASK-STR-064: BSM-vs-market option mispricing scan — complete, in review (PR #1720)

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

## Checkpoint 2 — live chain + ranked report (DONE, this run, 2026-11-25 ~03:01 IST)

Full ranked report: `docs/collaboration/TASK-STR-064-LIVE-CHAIN-REPORT.md`
(146 lines, 3 per-expiry tables, rendered by the repo scanner's
`render_markdown` from live data — no hand-written numbers).

- **Fetch:** Deribit public API, direct from this VM (no auth, no venue
  account), 2026-11-24 21:31 UTC (= 2026-11-25 03:01 IST). Spot (Deribit
  BTC index) S = 59,888.55. No Stratex-Server leg needed — direct fetch
  worked. No orders, no venue writes, no trading.
- **Method:** three expiries — 25NOV26 (daily, T≈0.001y), 27NOV26
  (weekly, T≈0.007y), 25DEC26 (monthly, T≈0.083y). Per expiry,
  sigma_ref = that expiry's ATM call implied vol solved from its live
  mark price (0.4797 / 0.5376 / 0.4861). Strikes within ±15% of spot;
  mark prices in BTC converted at the index. r = 0.05 (assumption,
  stated), q = 0. Flag threshold 5% (default).
- **Results (scanned / OK / FLAGGED / INVALID_PRICE / ERROR):**
  - 25NOV26: 50 / 24 / 22 / 4 / 0. ATM call +0.00% by construction.
  - 27NOV26: 48 / 28 / 20 / 0 / 0.
  - 25DEC26: 24 / 14 / 10 / 0 / 0.
- **Reading the flags (the research answer):** the flags are the vol
  smile, not arbitrage.
  - *Near expiry (25NOV26, 27NOV26):* flags concentrate in far-OTM
    options where the flat-vol model price is ~$0.00 while the market
    charges $0.17–$130 for gap risk the model cannot carry — e.g.
    BTC-25NOV26-51000-P market $0.17 vs model $0.00, IV 1.339 vs ATM
    0.480; BTC-27NOV26-51000-P market $22.72 vs model $0.07, IV 0.913
    vs ATM 0.538. The billion-% relative deviations in the table are
    an artifact of dividing by a ~zero model price; the IV column is
    the meaningful signal there.
  - *Monthly (25DEC26):* the clean signal. Downside puts trade
    +17% to +70% above the flat-vol model (IV 0.53–0.59 vs ATM 0.486:
    BTC-25DEC26-52000-P +70.31%, 54000-P +36.00%, 55000-P +25.79%,
    56000-P +17.08%); upside calls trade −9% to −17% below it (IV
    0.45–0.46: 68000-C −16.87%, 67000-C −15.42%, 66000-C −13.51%).
    A downside skew — the market prices downside protection richer
    and upside cheaper than one flat vol allows.
  - *INVALID_PRICE (4, all 25NOV26):* deep-ITM calls (51000–54000)
    trading $1.43–$2.67 (0.02–0.04%) below the discounted-intrinsic
    lower bound — genuine bound violations per the pricer, but
    trivially small on options expiring in ~10 hours; read as stale
    marks / settlement rounding, not tradeable arbitrage.
- **Verdict: no tradeable mispricing found.** The scanner works live
  end-to-end (fetch → scan → ranked report), and the market is not
  leaving BSM arbitrage on the table in this sample. What it leaves is
  the smile/skew a single-vol BSM cannot express — which is exactly
  what the IV cross-check in the scanner is for. No trading signal is
  placed from this; Stratex trades no options today.
- **Minor observation (IG-STR-01 pricer, not this scanner):**
  `bs_price` returns a tiny negative (~−1e-12) for deep-OTM
  near-expiry calls, rendering as model "−0.00" (BTC-25NOV26-68000-C).
  Floating-point artifact at the 1e-12 scale; immaterial to any
  decision, but it is why `rel_dev=inf` rows at T≈0 are numerical
  noise — read the IV column instead. Not fixed here (out of scope
  for this task; named for a future IG-STR-01 touch-up).

## Board

TASK-STR-064: AVAILABLE → CLAIMED → IN_REVIEW (owner muse_15, branch
`muse15/task-str-064-bsm-mispricing-scan-r2`, PR #1720). Task complete:
scanner + tests + live chain report filed; awaiting peer review + merge.

— Muse 15
