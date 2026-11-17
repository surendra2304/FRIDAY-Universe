# TASK-STR-RD-022 — Pre-declaration: OI-surge follow-through family (crypto 4h + 1d)

**Declared 2026-11-17, before any backtest of this family has been run.**
Frozen declaration: `oi_declaration.json` in this directory
(its SHA-256 is stated in the PR and in the completion comment on
issue #35). The declaration governs; if the code and the declaration
disagree, the declaration wins and the code is wrong.

## Source

The FRIDAY Universe strategy-discovery census of 2026-11-17
(`~/workspace/str-discovery-census/CENSUS.md`), slate item #2, from
its table 3c — family classes with NO coverage in the entire RD
record:

> **Open-interest / positioning** — OI surges, OI-price divergence,
> long/short-ratio extremes. "No RD round ever loaded a metrics
> series; every round is price/volume only." Feasibility: "Binance
> Vision metrics archives (OI, L/S ratios) are free, daily files
> back to 2021 for majors (alt coverage thinner — declare the
> universe accordingly)."

This declaration takes exactly that cell: a directional signal built
on the **open-interest** series. What it deliberately does NOT take
from the slate line — the long/short-ratio leg and the OI-collapse
tail — is recorded under "Declared exclusions" below, with reasons.

## The hypothesis

Open interest is the **quantity** of open perpetual contracts — a
stock of committed capital, not a price. When open interest surges
to an extreme (top 5% of its own trailing year of bar-over-bar
changes), new positions are being opened at an abnormal rate; the
concurrent price direction identifies which side the new capital is
on (price up + OI up = new longs; price down + OI up = new shorts).
Freshly committed capital does not reverse on the next bar — it
persists. This family therefore **follows** the price direction on
OI-surge bars, under a fixed ATR bracket, and claims that
surge-bar direction carries enough short-horizon persistence to
clear the RD programme bar net of costs.

**Adjacent evidence, disclosed before the run:**

- RD-003 judged `funding_extremes` — fading extreme **funding** —
  and refuted it across 4 cells (OOS PF 0.889/0.894 at 4h,
  0.837/0.738 at 1d; 806–4,398 trades per cell), concluding that
  "extreme funding persists/trends rather than reverting". That
  persistence finding is the prior FOR this family's direction
  choice: it follows extremes instead of fading them. It is not
  evidence that this family passes — it is evidence about which
  side of an extreme to stand on.
- RD-009 measured post-2024 funding compression to the ~0.01%/8h
  baseline. That bounds funding-based signals; it says nothing
  about OI quantities, which did not compress (BTCUSDT open
  interest on 2026-10-31 was ~96–97k BTC vs ~35–38k BTC on
  2021-01-01, in the prep-time probe files).
- Every other judged family in the programme is price/volume only.
  No round has ever loaded a metrics series, so there is no
  same-data prior, positive or negative.

## Why this is not RD-003's funding fade (the reduction check)

The prep brief required this check explicitly, because RD-003
already judged a superficially similar idea. The two families
differ on every load-bearing dimension:

1. **Different series.** Funding is a *price* — the periodic rate
   longs pay shorts, a flow cost of leverage. Open interest is a
   *quantity* — the stock of open contracts. This family reads
   `sum_open_interest` from the metrics archives and nothing else.
   Funding is never an input, in any form, at any stage.
2. **Opposite direction logic.** RD-003 **faded** its extreme
   (extreme positive funding → short). This family **follows** the
   price direction on surge bars (surge + up bar → long). Even on a
   bar where both states fire, the two families take opposite
   sides; one cannot be a re-skin of the other.
3. **Different entry state.** RD-003 required a funding-percentile
   extreme AND price extension vs EMA50. This family requires an
   OI-change percentile extreme AND the sign of the same bar's
   close-to-close return. There is no EMA gate and no funding term.
4. **Empirical overlap, measured at prep time.** On BTCUSDT +
   ETHUSDT daily bars over folds W1–W2 (2024-07-01 → 2025-07-01;
   737/737 metrics days loaded per symbol, zero missing), the
   declared OI-surge trigger fired on 40 days. RD-003's
   funding-extreme state (trailing-540-print percentile rank
   ≥ 0.90 or ≤ 0.10, asof at the day open) covered 33.1% (BTC) /
   36.7% (ETH) of all evaluable days in that window, and 40.0%
   (16/40) of the trigger days — the two states are correlated,
   as leverage-cycle phenomena are, but **60% of this family's
   triggers fire entirely outside RD-003's state**. On the 16
   coincident days, this family's FOLLOW direction opposed
   RD-003's FADE direction on 10 and agreed on 6 (before RD-003's
   additional EMA50 gate, which this check does not evaluate).
   A signal that mostly fires elsewhere, on a different input
   series, with opposite-signed logic on the majority of shared
   days, is not the funding fade re-skinned. Prep record:
   `~/workspace/str-oi/overlap_out.json`.

## Exact rules

Parameters are frozen: `OI_PCT_WINDOW_DAYS=365`,
`OI_SURGE_RANK=0.95`, `WINDOW_MIN_COVERAGE=0.95`,
`SNAPSHOT_MAX_AGE_MIN=30`, `ATR_PERIOD=14`, `SL_ATR_MULT=2.0`,
`TP_ATR_MULT=4.0`, `MAX_HOLD_HOURS=120`. Variants require a new
declaration and raise the trial count. This declaration is exactly
**two trials** — one per cell (4h, 1d).

1. **Series.** Per symbol: price bars at the cell timeframe
   (4h or 1d) and the open-interest series from Binance Vision
   daily metrics archives. The OI value at a bar's close is the
   last metrics snapshot with `create_time` ≤ bar close (causal
   asof). If that snapshot is more than 30 minutes old at the bar
   close, the bar is **not evaluable** (metrics gap, not a signal).
2. **OI change.** `dOI_t = OI_t / OI_{t-1} − 1` over consecutive
   bars of the cell timeframe, where `OI_t` is the asof value at
   bar *t*'s close. If either endpoint is missing or
   `OI_{t-1} ≤ 0`, `dOI_t` is undefined.
3. **Extreme.** The percentile rank of `dOI_t` is its rank within
   the trailing window (bar *t* − 365 days, bar *t*] of `dOI`
   values at the same timeframe, the current bar included:
   `rank = #{window values ≤ dOI_t} / #{window values}`. A bar is evaluable only if its timestamp is
   ≥ 2023-01-01 (365 days after panel start) **and** ≥ 95% of the
   bars in its trailing window have defined `dOI`. A **surge** is
   `rank ≥ 0.95`.
4. **Entry.** On a surge bar *t* that the symbol spent entirely
   flat (see conventions): if the bar's close-to-close return
   `close_t / close_{t-1} − 1` is **positive → LONG**; if
   **negative → SHORT**; if exactly zero → no trade. Entry at the
   **open of bar t+1**.
5. **Bracket.** ATR is Wilder ATR(14) over the cell timeframe's
   bars, value at the signal bar *t* (seeded as the simple mean of
   the first 14 true ranges, then `ATR = (ATR·13 + TR)/14`).
   Stop = entry ∓ `2.0 × ATR_t`; target = entry ± `4.0 × ATR_t`
   (the programme BR24 bracket form RD-003 used). If `ATR_t ≤ 0`,
   no trade.
6. **Exit.** Exits are evaluated on every bar from the entry bar
   onward, in this order: a gap through the stop at the bar open
   fills at the open; then the stop; a gap through the target at
   the open fills at the open; then the target (stop before
   target within a bar — worst case). If no bracket exit has
   occurred by the close of the max-hold bar — the 30th bar of
   the hold at 4h, the 5th at 1d, the entry bar counting as bar
   1 — the position exits at that bar's close.
7. **Frequency.** One position at a time per symbol. Signals
   arriving while a position is open are skipped. A bar on which
   an exit occurred is not a signal bar (rule 4's "entirely
   flat" condition).

## Declared conventions (read this before citing the rules)

- **Panel scope** — the universe is the 25 CRYPTO30 symbols whose
  Binance Vision metrics coverage starts on or before 2022-01-01,
  established by a prep-time probe of the actual archives
  (2026-11-17): BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT,
  DOGEUSDT, ADAUSDT, LTCUSDT, LINKUSDT, DOTUSDT, TRXUSDT, AVAXUSDT,
  NEARUSDT, ATOMUSDT, UNIUSDT, ETCUSDT, BCHUSDT, FILUSDT, XLMUSDT,
  HBARUSDT, ALGOUSDT, VETUSDT, SANDUSDT, MANAUSDT, AAVEUSDT.
  Excluded by the same mechanical rule (first metrics file after
  2022-01-01 — later perp listings): OPUSDT (2022-07-01),
  INJUSDT (2022-10-01), APTUSDT (2023-01-01), ARBUSDT (2023-04-01),
  SUIUSDT (2023-07-01). The panel is **2022-01-01 → 2026-10-31**
  for both klines and metrics.
- **Panel verification gate (the run must pass it before any
  backtest).** For every universe symbol the run verifies: every
  daily metrics file in the panel span downloads and its SHA-256
  matches the published `.CHECKSUM`; a manifest of file hashes is
  recorded; klines load through the programme's verified loader
  (`data_feed.load_dataset`, months 2022-01..2026-10). A symbol
  with > 1% of its daily metrics files missing in the span is
  excluded **by this rule** and the exclusion is reported in the
  run record — it is not a post-hoc choice. Any other deviation:
  STOP and report; never patch, fill or substitute data.
- **Percentile construction** — the rank uses the window's defined
  `dOI` values only, current bar included, ties counted as ≤
  (rule 3's formula). The window is trailing and causal: no value
  after bar *t* can enter bar *t*'s rank. The ≥ 95% coverage gate
  is what makes the rank meaningful across the archive's small
  gaps; bars failing it are silent, never interpolated.
- **Asof discipline** — a metrics snapshot is used only at or
  after its own `create_time`. The 30-minute staleness cap is the
  enforcement: Binance publishes snapshots every ~5 minutes, so a
  snapshot older than 30 minutes at a bar close marks a feed gap.
- **Position sizing** — sizing is not part of this family's
  backtest identity: the bar judges per-trade expectancy / profit
  factor, which are sizing-invariant. If the candidate ever
  reaches forward testing it inherits the fleet-standard decided
  risk package (FWD-006) unchanged, as with SRS and S-RD1.

## Declared exclusions (part of the freeze)

- **The OI-collapse tail is NOT traded.** A rank ≤ 0.05 bar is
  positions *closing* — exhaustion of an existing move, the
  opposite mechanism to fresh capital committing. Fading or
  following collapses would be a second mechanism inside the same
  cell; it needs its own declaration if it is ever tested.
- **The long/short positioning ratios are NOT inputs.** The
  metrics files carry them (`count_long_short_ratio`,
  `sum_toptrader_long_short_ratio`), and the census slate names
  them — but a positioning-ratio extreme is the crowding state
  closest to RD-003's funding state, and this family's claim to
  independence rests on testing the quantity series alone.
  A positioning-ratio family is a separate declaration.
- **Funding is never an input** — no funding percentile, level or
  sign enters the signal, the gates or the exits. (Funding
  *cashflows* are likewise not modelled: the harness convention is
  price-only accounting with the programme cost model, exactly as
  RD-003 declared for its cells.)

## The bar (unchanged from the programme)

Judged **per cell** (4h and 1d separately), pooled across the
25-symbol universe, OOS only (walk-forward folds W1–W5,
2024-07-01 → 2026-11-01, entry-time attribution):

- expectancy_net > 0 and profit_factor_net ≥ 1.2 (strict, OOS)
- ≥ 200 OOS trades; ≥ 4 of 5 walk-forward folds positive
- programme cost model (crypto 16 bps round trip) **and** a
  2×-cost shadow (32 bps), both passing
- `rd.common.holdout_check` passes (expectancy > 0 on ≥ 2 symbols
  with ≥ 20 OOS trades each, and no symbol contributing > 80% of
  total net profit)
- Bonferroni one-sided p < 0.05/N at the run-time counter. Trial
  accounting: the declared programme counter is **3,891** as of
  2026-11-17; SRS's declared run adds 1 (→ 3,892) when it lands;
  this declaration adds exactly **2** (one per cell). The run
  states the floor it used; if both cells are judged in one run,
  both are judged at the final N (entering counter + 2) — the
  stricter reading.
- If a cell's pooled OOS trades < 200, that cell's verdict is
  exactly: **"insufficient OOS trades"**.
- Strict OOS PF < 1.2 fails a cell (owner's rule: such families
  are deleted). Both cells failing closes the family. Passing
  makes a cell a forward-test *candidate* only, under the Phase-3
  protocol (≥ 100 trades AND ≥ 8 weeks on demo, FWD-006 sizing).

## Data plan

- **Metrics:** Binance Vision daily archives
  (`data/futures/um/daily/metrics/<SYM>/<SYM>-metrics-<DATE>.zip`),
  free and keyless, each verified against its published
  `.CHECKSUM` (SHA-256). Prep-time proof (2026-11-17): BTCUSDT
  files for 2021-01-01 (576 rows) and 2026-10-31 (288 rows)
  downloaded, parsed and checksum-verified; earliest-file probe
  over all CRYPTO30 symbols; first-of-month continuity spot-checks
  for BTCUSDT/AAVEUSDT at 11 dates across 2022–2026, all present.
- **Klines:** Binance Vision monthly klines through the
  programme's verified loader — the same source and loader as the
  RD panels (1h base, resampled to 4h/1d per
  `rd/common.load_timeframe`).
- The run is a separate, later step and is NOT part of the
  declaring PR. No owner action is needed to run this — the data
  gate is passed before declaration.

## Status

DECLARED, NOT RUN. This declaring PR ships the frozen declaration,
the pinned harness and its synthetic tests only — no backtest is
executed. Passing the bar would make a cell a forward-test
*candidate* under the Phase-3 protocol — demo only, like
everything else. Failing it closes the family.
