# TASK-STR-RD-024 — Pre-declaration: US cross-sectional short-term reversal family (`us_xs_reversal`)

**Declared 2026-11-17, before any backtest of this family has been run,
before any US-equity panel for this family has been downloaded, and
before any Alpaca key for this project has been installed.** Frozen
twin: `usxsrev_declaration.json` in this directory (its SHA-256 is
stated in the completion comment on issue #35). The declaration
governs; if the code and the declaration disagree, the declaration
wins and the code is wrong.

## Lineage — read this first (the dead-mechanism disclosure)

This family is **not a new mechanism**. It is the cross-sectional
short-term reversal mechanism that the programme has already judged —
and that already failed — transplanted unchanged onto a panel it has
never touched. The judged record, stated in full:

- **RD-002 batch 3, family `xs_reversal`** (pre-declared in
  `results_rd2/batch3_declaration.json`; implemented in
  `rd2/families3.py::xs_reversal_fn`): score = trailing return
  `close / close.shift(L) − 1`; rank the panel; **long the lowest
  scorers, short the highest** (`long_low=True`); rebalance every
  5 bars; k = 3 per side; exits `bracket_time` — stop 2.0×ATR(14),
  target 4.0×ATR(14), time exit at 5 bars. Variants: `rev5_r5`
  (L = 5), `rev10_r5` (L = 10). Panels: crypto30, forex12, forex28,
  comm7 (the config's classes are exactly `["crypto", "forex",
  "comm"]`); timeframes 1d and 4h.
- **Verdict: 12 rows, all FAIL.** On crypto30 1d, the largest panel:
  rev5_r5 — 1,020 OOS trades, expectancy −0.169%, **PF 0.957**,
  2/5 folds positive; rev10_r5 — **PF 0.945**. The family's best cell
  anywhere was rev5_r5@comm7 1d at PF 1.196 (708 trades) — still
  below the 1.2 bar. Under the owner's standing rule (strict OOS
  PF < 1.2 → DELETE) the mechanism stands **deleted** on every panel
  it has touched.
- The family was **never run on any equity or index panel**: no
  cross-sectional ranker of any kind appears on an equity panel
  anywhere in RD-001…RD-017 (RD-008 judged single-name-style systems
  — ema_cross, tsmom, donchian, gaps, zrev, rsi_rev — on SPX/NDX
  index series, which is a different construction on a different
  object: two index series are not a cross-section).

**Why the equity panel is a genuinely different question** — the
argument for spending two trials on a dead mechanism, stated before
any data exists, with its counterweight:

1. **The mechanism is equity-native; the judged panels were the
   transplant.** Short-horizon cross-sectional reversal is one of
   the oldest documented US-equity effects (Jegadeesh 1990; Lehmann
   1990), and its standard explanation is liquidity provision:
   market makers and limit-order suppliers absorb temporary,
   non-informational order imbalance and are compensated as prices
   revert over the following days. Crypto perpetuals trade 24/7 with
   no designated market makers, no limit-order-book obligation of
   the equity kind, and a participant mix dominated by leveraged
   directional flow. A failure there measures the effect in a market
   whose microstructure lacks the very agent the theory says
   produces it.
2. **The overnight boundary does not exist in the judged panels.**
   US equities close for 17.5 hours a day (and over weekends). A
   material share of equity reversal is the overnight/intraday
   decomposition: names sold into the close rebound at and after the
   next open as overnight inventory is worked off. A 24/7 series has
   no close, no overnight gap, and therefore cannot contain this
   component at all — the judged cells are silent about it, not
   negative about it.
3. **Opening and closing auctions.** A large share of US volume
   executes in two auction prints per session, including mechanical
   index/ETF rebalancing and market-on-close imbalance flow that is
   price-moving but information-free — the canonical input to
   multi-day reversal. No judged panel has auctions.
4. **The short leg is a different trade in equities.** The judged
   cells short crypto/forex with futures-style symmetry. Shorting a
   US stock costs borrow, is subject to locate and short-sale-
   circuit-breaker constraints, and can be recalled. That asymmetry
   is part of why crowded winners can stay crowded — and it is
   priced into this declaration (§Costs) and reported separately
   (§Rules, reporting) instead of being assumed away.

**Counterweight, also declared:** the prior from the judged panels
is negative, and nothing above is evidence — it is a reason the
question is open, not a reason to expect a pass. The bar below is
the programme bar, unchanged. If both cells fail, this family is
closed on equities too, permanently, under the same deletion rule;
there will be no third panel and no parameter variant.

## The hypothesis

On a frozen 30-name panel of large, continuously listed US common
stocks, the judged `xs_reversal` construction — trailing 5- or
10-session return ranking, long the bottom 3 / short the top 3,
5-session rebalance, 2/4 ATR bracket with a 5-session cap — earns
positive expectancy net of the programme cost model, driven by
liquidity-provision reversal around the overnight boundary and
auction imbalances, sufficient to clear the full programme bar.

## Exact rules (frozen; the two cells differ ONLY in lookback)

- **Universe (frozen list — the binding artefact).** 30 tickers:
  AAPL, ABBV, ACN, AMD, AMZN, AVGO, BAC, COST, CRM, CVX, GOOGL, HD,
  JNJ, JPM, KO, LLY, MA, META, MCD, MRK, MSFT, NFLX, NVDA, PEP, PG,
  TSLA, UNH, V, WMT, XOM.
  Selection provenance (not a second, hidden rule): large US-listed
  common stocks, each with a market capitalisation above roughly
  $100B at 2022-12-30, each an S&P 500 constituent continuously over
  the span, one ticker per issuer (for the dual-class issuer,
  Alphabet, the more liquid class GOOGL), purely alphabetic ticker
  symbols only (which excludes Berkshire Hathaway's BRK.B), each
  continuously listed on NYSE or Nasdaq from 2023-01-01 through
  2026-10-31. The list was frozen before any panel data existed for
  this family; the run's gate verifies continuous listing and data
  completeness for exactly these names and **reports a failure
  rather than substituting a name** — substitution after the fact
  would break the freeze.
- **Timeframe.** Daily bars (one bar per NYSE regular session).
  No intraday data is used: entries are session opens, exits are
  session opens/closes, exactly as the judged daily cells were
  constructed.
- **Panel session calendar.** The sorted session dates of the
  verified panel (all 30 names share the NYSE calendar; the calendar
  is the union of session dates present in the verified panel).
  Session index j is 0-based over this calendar, j = 0 being the
  first session ≥ 2023-01-01.
- **Score.** For symbol s at signal session j, with L ∈ {5, 10}:
  `score(s, j) = C(s,j) / C(s,j−L) − 1 + Σ div(ex) / C(s, ex−1)`
  where C is the split-adjusted close and the sum runs over s's
  dividend ex-dates ex in (j−L, j] (see §Declared conventions —
  dividend adjustment). Closes are taken from the panel calendar
  with forward-fill alignment, under the judged stale-series
  discipline: a symbol whose last real close is more than 3 sessions
  before j has no valid score at j.
- **Signal sessions.** j = 60, 65, 70, … (warmup 60 sessions;
  rebalance step 5), with j ≤ (number of sessions − 2) so an entry
  session exists.
- **Ranking and picks.** Rank all symbols with a valid score at j,
  ascending. If fewer than 6 symbols (2k) have valid scores, there
  is no cohort at j. Otherwise: **LONG the 3 lowest scores, SHORT
  the 3 highest scores** (k = 3, as judged).
- **Entry.** At the **open of session j+1** in the symbol's own
  series (pad-located; if the symbol has no bar within 3 sessions
  after j, the pick is dropped — the judged discipline).
- **Bracket.** ATR = Wilder EWM ATR(14) (alpha = 1/14,
  adjust=False, on true range) of the symbol, **taken at the signal
  session j** (as judged). Stop = entry ∓ 2.0×ATR (long: below;
  short: above). Target = entry ± 4.0×ATR.
- **Exit management.** From the entry session onward, the entry
  session itself exit-checked (a live bracket would be live
  immediately — the judged convention): a session that gaps through
  a level fills at the session open; a level touched inside the
  session fills at the level; if stop and target are both inside
  one session's range, the **stop is assumed hit first** (worst
  case). **Time exit:** if neither level is hit by the close of the
  5th session counting the entry session as session 1, exit at that
  close (reason TIME). If the data ends first, exit at the last
  close — the judged engine's bracket_time path records this under
  the same TIME exit.
- **One position at a time per symbol.** A pick for a symbol with an
  open position is skipped (the judged discipline).
- **No lookahead.** The score at j uses closes and dividend
  ex-dates ≤ j only; entry is at the next session's open; the
  bracket is managed from the entry session onward. Dividend amounts
  are announced before their ex-dates, so the adjustment uses no
  future information.

## Declared conventions (read this before citing the rules)

- **Dividend adjustment (data convention, declared because the bar
  series is split-adjusted).** The data spec is `adjustment=split`
  (the SRS-adjudicated spec), so split-adjusted closes drop by
  approximately the dividend on each ex-date. Unadjusted, that books
  a phantom loss for longs held over an ex-date and a phantom gain
  for shorts (who in reality owe the dividend as payment in lieu).
  This declaration therefore adjusts mechanically, using the Alpaca
  corporate-actions dividend calendar for the 30 names over the
  span: (a) ranking scores add back each in-window dividend as
  written in §Rules; (b) a trade spanning an ex-date (ex-date in
  (entry session, exit session]) has its net return adjusted by
  `+ div / entry_price` (long) or `− div / entry_price` (short).
  Declared approximations: the add-back uses the announced amount,
  not the realised ex-date drop (the standard total-return
  approximation available from free data); tax/withholding effects
  are ignored. If the dividend calendar cannot be obtained and
  verified at the gate (§Data gate, check 5), **the run does not
  proceed** — running unadjusted after declaring the adjustment
  would be a silent rule change.
- **Short-side borrow (cost convention).** Borrow cannot be
  observed historically from free data. Declared charge: every
  SHORT trade's net return is reduced by
  `0.0025 × (calendar days from entry date to exit date) / 360`
  (25 bps per annum, ACT/360) — a general-collateral assumption
  appropriate to this universe of mega/large-cap, easy-to-borrow
  names, stated as an assumption, not a measurement. The charge
  applies identically at the 1× and 2× cost levels (the shadow
  doubles transaction costs only). Locate failures, short-sale
  circuit breakers and recalls are **not modelled** — disclosed
  here; the borrow charge and the mandatory separate short-leg
  reporting are the compensation, and the promotion path is
  demo-only in any case.
- **Position sizing — not part of this family's identity.** The bar
  judges per-trade expectancy / profit factor, which are
  sizing-invariant; positions are equal-notional within a cohort by
  construction of the return accounting. If a cell ever reaches
  forward testing it inherits the fleet-standard decided risk
  package (FWD-006) unchanged — 0.1% of venue equity risk per trade,
  2% heat cap per strategy with this whole book counting as one
  strategy — exactly as recorded for SRS and S-RD1.
- **Reporting (mandatory, declared).** The run record must state
  pooled OOS expectancy and PF at 1× costs for (a) the full book,
  (b) the LONG leg only, (c) the SHORT leg only, so a book carried
  by one leg is visible on the record. The bar judges (a) only.

## Costs

The programme cost model, per the SRS holdout addendum's recorded
reading (§6, frozen there and adopted here): `simulator.Costs()` as
shipped — 5 bps fee + 3 bps spread/slippage per side, applied
adversely in price space, **16 bps round trip** at 1×; the 2×-cost
shadow is the identical simulation at **32 bps round trip**. (That
this is a futures-venue cost model applied to equities is noted, not
hidden — it is the model the programme names, it is not generous to
the strategy, and the borrow charge above comes on top of it for
shorts.) Plus the declared borrow charge on shorts (§Declared
conventions).

## The bar (per cell — ALL elements required; unchanged from the programme)

Judgement is OOS only. Trades are attributed to folds by **entry
time** under `walkforward.FOLDS` (W1 2024-07-01→2025-01-01,
W2 →2025-07-01, W3 →2026-01-01, W4 →2026-07-01, W5 →2026-11-01,
end exclusive). The pre-OOS segment (2023-01-01→2024-06-30) is
warm-up / in-sample reporting only and is never blended into the
headline; nothing is fitted on it — parameters are frozen by this
declaration.

1. **Pooled OOS:** expectancy_net > 0 and profit_factor_net ≥ 1.2,
   with **≥ 200 pooled OOS trades**. If pooled OOS trades < 200 the
   cell's verdict is exactly **"insufficient OOS trades"** — not
   proven, not a pass, and not a deletion either; the bar is never
   relaxed to fit the sample.
2. **Folds:** ≥ 4 of 5 folds with positive expectancy_net, with
   trades present in ≥ 4 folds (the `check_bar2` construction).
3. **Panel holdout:** `rd2.stats2.holdout2` passes — breadth: ≥ 50%
   of symbols with ≥ 20 OOS trades have positive expectancy;
   concentration: no single symbol contributes > 50% of total
   positive profit; untouched subset (every 3rd symbol of the
   sorted universe from index 2 — `sorted(universe)[2::3]`, a set
   the selection process never optimises on) has pooled expectancy
   > 0 on ≥ 30 trades; ≥ 3 active symbols.
4. **Temporal holdout:** H1–H4 of SRS TEMPORAL HOLDOUT v1 pass
   (§Temporal holdout below), under its H5 burn clause.
5. **2×-cost shadow:** pooled OOS at 32 bps round trip (borrow
   unchanged): expectancy_net > 0 **and** profit_factor_net ≥ 1.2.
   (Fold, holdout and significance elements are judged at 1× only —
   this resolves, in advance, the ambiguity in the programme's
   "both passing" phrasing.)
6. **Significance at the final N:** Bonferroni one-sided
   p < 0.05 / N_final on the per-trade mean (the `stats2.trade_stats`
   construction), computed against the FINAL global trial counter at
   judgement time (§Trial accounting). The deflated Sharpe ratio
   (the `stats2` construction) is **reported, not judged**: RD-002's
   DSR gate was a synthesis-time construction over a 1,441-trial
   population (its `sr_std` is the cross-trial Sharpe dispersion),
   which a 2-cell family cannot support; SRS and S-RD1 likewise judge
   significance by Bonferroni alone. The run record states the DSR
   (with `sr_std` taken across this family's two cells) for the
   record, and no verdict turns on it.

**Verdict mapping.** All six elements pass → the cell **PASSES** and
becomes a forward-test candidate only (Phase-3 protocol: ≥ 100 demo
trades AND ≥ 8 weeks; demo only — nothing here authorises live
trading). A cell with ≥ 200 OOS trades and profit_factor_net < 1.2
**FAILS**; if both cells fail, the family is **DELETED** (closed)
under the owner's rule, on equities as it already is elsewhere.
"Proven" is reserved for a cell that passes everything.

## Temporal holdout — how TEMPORAL HOLDOUT v1 binds this family

TEMPORAL HOLDOUT v1 was frozen for SRS because `rd.common.
holdout_check` is structurally unpassable for a single-symbol
family. This family has 30 symbols, so the panel holdout
(`holdout2`, bar element 3) applies directly and is required. In
addition — because SRS established that equity families carry a
temporal holdout, and this declaration adopts the stricter combined
reading **before any data exists** — this family also adopts
H1–H4 of TEMPORAL HOLDOUT v1, with its sets defined identically:
**H** = trades entered in W5 (2026-07-01 ≤ entry < 2026-11-01);
**D** = trades entered in W1–W4.

- **H1 — Holdout size.** |H| ≥ 20 trades.
- **H2 — Holdout positive.** expectancy_net(H) > 0.
- **H3 — Non-holdout stands alone.** expectancy_net(D) > 0.
- **H4 — Fold concentration ≤ 80%.** Over folds W1–W5, no single
  fold contributes more than 80% of the summed positive fold profit.
- **H5 — Judged exactly once (burn clause), adopted in effect
  verbatim.** The W5 segment is evaluated once, in the single
  declared run. If H's trades or metrics are computed or inspected
  before that evaluation — during harness development, debugging or
  a trial run — or if, after evaluation, the family is re-run with
  any change to rules, parameters, conventions, costs, panel,
  simulator or judging code, the temporal holdout is **burned**:
  bar element 4 FAILS for this family under this declaration,
  permanently. Mechanics debugging uses synthetic bars or the
  pre-OOS segment only. A shortfall is a fail, not a waiver: if
  |H| < 20 the element fails as `FAIL (INSUFFICIENT_HOLDOUT_TRADES)`
  and the window is never extended.

If TEMPORAL HOLDOUT v1 and this declaration ever appear to disagree,
the stricter reading governs (the SRS addendum's own §7 principle).

## Data — spec and gate

- **Source:** Alpaca Market Data, Basic plan ($0), historical bars,
  `feed=sip` (consolidated CTA+UTP tape), `adjustment=split` — the
  SRS-adjudicated spec (SIP, not IEX: IEX carries only ~2.7% of
  consolidated volume). **Daily bars** for the 30 universe symbols,
  requests `start=2023-01-01T00:00:00Z`, `end=2026-11-01T00:00:00Z`
  (span 2023-01-01→2026-10-31; 961 NYSE sessions per the SRS
  provenance research — 374 pre-OOS + 587 OOS).
- **Dividend calendar:** Alpaca corporate-actions announcements for
  the 30 names over the span (cash dividends: ex-date + amount),
  used only for the declared dividend adjustment.
- **The raw panel is never committed to the public repo** (SIP
  licence); only the provenance record (parameters, per-symbol
  counts, SHA-256 of panel + dividend calendar) is committable, per
  SRS practice. Keys are installed with the SRS execution through
  the normal credential channel; this declaring package neither has
  nor seeks them.
- **Gate — the SRS 5-check verification pattern, adapted to this
  panel. ALL five must pass before any backtest; a panel that fails
  verification is not run.**
  1. **Session census.** Each symbol's bar count equals the panel
     session count (961 expected), or every shortfall is itemised
     by date with a named cause (e.g. a trading halt). Unexplained
     gaps fail the gate.
  2. **SIP feed check.** Every symbol's median daily share volume
     over the span is ≥ 2,000,000 shares — a floor every name in
     this universe clears by a wide margin on the consolidated
     tape and that an IEX-only pull would fail for most names;
     this is the panel-level form of the SRS SIP-vs-IEX check.
  3. **Split check.** Split-adjusted continuity on the known
     in-span split ex-dates (WMT 3:1, 2024-02-26; NVDA 10:1,
     2024-06-10; AVGO 10:1, 2024-10-14): no overnight close-to-close
     move ≈ the split ratio. Any single-session |close-to-close
     return| > 40% on any symbol anywhere in the span must be
     itemised with a named cause (split, or a genuine event).
  4. **Cross-source spot check.** ≥ 10 sampled symbol-sessions,
     spread across symbols and years and including one split
     ex-date week: closes within $0.02 and highs/lows within $0.05
     against Yahoo Finance daily data (the SRS addendum v3
     cross-source).
  5. **Dividend calendar check.** The pulled dividend calendar is
     cross-checked on ≥ 10 sampled ex-dates against Yahoo dividend
     history: dates exact, amounts within $0.005. The full calendar
     (count + SHA-256) is frozen into the provenance record.
- **Run procedure (frozen order).** (1) Build/verify the harness
  against this declaration; mechanics debugging on synthetic bars or
  the pre-OOS segment only. (2) Pull and gate the panel; a failed
  gate stops the run with zero trials consumed. (3) Execute the
  frozen code **once** over the full panel; hash-pin each cell's
  trade list (SHA-256) in the run record before any metric is
  computed from it. (4) Compute D-segment and pooled metrics not
  requiring H. (5) Evaluate H (H1–H4) exactly once. (6) Report pass
  or fail in full, including the leg-split reporting of §Declared
  conventions.

## Trial accounting (frozen method; numbers as of this declaration)

- This declaration adds **exactly 2 trials**: cells
  `us_xs_reversal/rev5_r5` and `us_xs_reversal/rev10_r5` — one
  panel, one timeframe (1d), the two judged lookbacks. Variants,
  re-runs with tweaks, a different k, a different universe or a
  second exit rule would each be additional trials under new
  declarations; none are authorised here.
- **Programme counter at declaration: 3,891 trials** (the
  rd-reconcile ledger figure cited by the S-RD1 declaration,
  2026-11-17).
- **Run-lane position (stated honestly):** equity runs queue behind
  SRS (1 trial; its board entry records entering floor 3,891 →
  final N 3,892), S-RD1 (1 trial) and the ORB family
  (census slate #4; its own declared cells). If the queue runs in
  that order, this family's judgement counter N_final ≥ 3,891 + 1 +
  1 + (ORB cells) + 2. What is frozen is the **method** (the SRS
  addendum §5 method): the run re-reads the ledger at run time and
  judges significance at the then-final N; a busier programme can
  only tighten the bar. α = 0.05 / N_final.
- **Expected sample (an estimate, not a promise):** ~180 signal
  cohorts over the full span, ~117 with entries in OOS, × 6 picks
  ≈ 700 OOS trades per cell before skips; the W5 holdout ≈ 100
  trades. The ≥ 200 and H1 floors are therefore reachable **if the
  panel verifies** — the run reports the actual counts and the
  verdict mapping above applies whatever they are.

## Status

DECLARED, NOT RUN. This declaring package ships the frozen
declaration, the harness built to it, and synthetic tests only — no
panel, no backtest, no signal module wired anywhere near production.
The declared run is the board entry's next_action, gated on the SRS
execution having installed the project's Alpaca keys (the same
unblock, via the normal credential channel). Passing the bar would
make a cell a forward-test *candidate* under the Phase-3 protocol —
demo only, like everything else. Failing it closes the family.

*Declaration authored 2026-11-17, following the SRS declaration +
TEMPORAL HOLDOUT v1 addendum pattern (frozen declaration, declared
conventions, recorded cost reading, frozen trial-accounting method)
and the census re-audit's corrected slate (TASK-STR-RD-024).*
