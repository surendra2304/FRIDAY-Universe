# TASK-STR-DISC-004 — Pre-declaration: ORB/VWAP US-equity intraday family

**Declared 2026-11-17, before any backtest of this family has been run,
before any panel for this family has been downloaded, and before any
trade of this family has been computed anywhere.**
Frozen declaration: `orb_vwap_declaration.json` beside this file
(its SHA-256 is stated in the ship PR and in the claim comment on
issue #35). The declaration governs; if the code and the declaration
disagree, the declaration wins and the code is wrong.

## Source

Strategy-discovery census 2026-11-17 (`str-discovery-census/CENSUS.md`),
recommended slate **#4: "US-equity intraday ORB + VWAP, per-symbol,
Alpaca SIP, full history"**. The census records (§3c) that full-bar
US-equity intraday families have **zero coverage** in the entire RD
record. The census re-audit (2026-11-17, `str-census-reaudit/`)
confirmed that coverage verdict — on a corrected record, set out in
the Lineage section below, because the census itself misstated the
nearest relative's universe. No creator claim is under test here;
the hypothesis is the canonical opening-range-breakout construction
itself, judged on a full-history, per-symbol SIP panel for the
first time.

**Which ORB/VWAP construction this is (read before citing the census).**
The census slate names the cell "ORB + VWAP-reversion". This
declaration freezes the **breakout-with-VWAP-filter** reading: trades
are opening-range breakouts, taken only when the breakout direction
agrees with the session VWAP. A **VWAP-reversion** construction
(fading extensions back toward VWAP) is a different mechanism and is
**NOT** this family; it would require its own declaration and its own
cell. Nothing in this declaration judges, or may be cited as judging,
VWAP reversion. One disclosure belongs here, not buried: a family
named `vwap_reversion` **was** judged in RD-007 — on GOLD/SILVER/WTI
1-hour bars — and failed with every other row of that batch (see
Lineage). It was never judged on equities, and it is still not this
family.

## Lineage — the judged neighbours, on the corrected record

The census (Table 1 and §3c) described RD-007's universe as crypto.
The census re-audit (2026-11-17, `str-census-reaudit/STATE.md` +
`JUDGED_FAMILY_INDEX.md`) corrected that from the RD-007 record
itself. This declaration follows the corrected record:

- **RD-007 judged `orb_breakout` — and `vwap_reversion` — on GOLD,
  SILVER and WTI, 1-hour bars, per-instrument (Yahoo futures).**
  The same batch also judged `bb_rsi_reversion`, `donchian_intra`
  and `prevday_breakout` on that universe. **All 45 rows were
  negative-expectancy; best PF 0.979; zero passers.** So the ORB
  mechanism, and VWAP-reversion, have both been judged — on
  metals/oil futures at 1h — and both are dead there.
- **RD-002 batch 3 judged a `session_breakout` neighbour** (london /
  newyork session configurations) on forex12 and idx3 at 1h: best
  PF 0.782 (newyork@idx3, 1,029 trades), zero passers.
- **RD-008's index intraday cells** (SPX/NDX, 15m/1h/1d) were
  screening-capped at ~60 days of data — a single regime, never a
  full-bar judgement.

**Why this family is nevertheless uncovered — the differentiation.**

1. **Session structure.** GOLD/SILVER/WTI futures, FX and index
   feeds have no single exchange-session open; an "opening range"
   there is an arbitrary clock window. This family is defined by
   the NYSE regular session: the range is the first 30 minutes
   after the 09:30 ET exchange open, entry eligibility and the
   hard flat-by-close are bounded by the exchange calendar
   (including 13:00 ET early closes), and no position ever crosses
   a session boundary.
2. **Panel.** RD-007 ran on Yahoo futures 1-hour bars. This family
   runs on Alpaca SIP consolidated-tape (CTA+UTP) 15-minute bars
   behind the 5-check verification gate (gap audit, 10M-share
   median-volume feed check, split checks, cross-source spot
   check, hash freeze).
3. **Construction.** RD-007 judged `orb_breakout` and
   `vwap_reversion` as separate families. This family is neither:
   entries are opening-range breakouts **gated by a session-VWAP
   veto** — VWAP never generates a trade here, it only vetoes the
   session's first break — with a 2.0R range-relative target,
   judged **pooled across 15 symbols** with a breadth gate and a
   temporal holdout, not per-instrument.

The honest prior this lineage sets: the nearest judged relatives
all lost, under this same programme bar. This declaration proceeds
because the slate's claim is precisely that the equity-session
construction on a verified SIP panel is a different cell — and it
will be judged by the bar that killed its relatives.

## Distinction from SRS (TASK-IG2-STR-14) — stated in full

SRS is the programme's other equity-intraday ORB family and the two
must never be conflated:

1. **Universe.** SRS judges **TSLA only**. This family judges a frozen
   **15-symbol universe, pooled** (one cell), with a per-symbol
   breadth gate SRS cannot express.
2. **Filter.** SRS has **no VWAP component at all** — the first close
   beyond its range enters, unconditionally. This family's first
   close beyond the range is only a *candidate*: the session VWAP
   vetoes it or not, and a veto ends the symbol-session.
3. **Target.** SRS: a fixed **$10** on TSLA (a unit read from its
   source video). This family: **2.0 × R**, where R is the entry's
   distance to the opposite range end — a range-relative target that
   pools across symbols and prices.
4. **Source and claim.** SRS tests one creator's marketed claim
   ("81% win rate", unverified) recovered verbatim from a reel. This
   family tests no one's claim; it is a programme-discovery
   construction from the census slate.
5. **What coincides.** Both use the **first two 15-minute candles**
   (09:30–10:00 ET) as the opening range, the opposite range end as
   the stop, at most one trade per session, and a flat-by-close exit.
   The range window is deliberately the same; everything downstream
   of the range — filter, target, universe, judging — differs. TSLA
   appears in this family's universe as one of fifteen pooled names;
   its trades here are part of a pooled cell under different rules,
   not a re-judgement of SRS's TSLA-only cell.

## The hypothesis

On liquid US equities, the first 15-minute close beyond the 30-minute
opening range, taken only when the close sits on the VWAP-consistent
side of the session (above VWAP for a long, below for a short), with
the stop at the opposite end of the range and a 2R target, carries
enough intraday continuation — net of the programme cost model — to
clear the RD programme bar on a pooled, full-history, per-symbol
basis. The VWAP veto is the family's identity: it is the claim that
the unfiltered first break (the mechanism class RD-007 judged on
GOLD/SILVER/WTI 1h, where every row lost) is not the same trade as
the VWAP-confirmed first break on equities.

## Exact rules (frozen)

1. **Universe** — the 15 symbols listed under "Declared conventions",
   frozen. 15-minute bars, US regular session only
   (09:30–16:00 America/New_York; 13:00 close on early-close days).
2. **Opening range** — high = max high, low = min low of the **first
   two** 15-minute bars of the session (bar-starts 09:30 and 09:45
   ET). A symbol-session missing either bar, or with a zero-height
   range, produces no trade.
3. **Session VWAP** — computed from the session's own 15-minute bars
   only: `VWAP_t = Σ (TP_i × V_i) / Σ V_i` over bars `i = 1..t` of
   the session, with typical price `TP_i = (H_i + L_i + C_i) / 3`
   and `V_i` the bar's share volume as served by the panel. The
   vendor's per-bar `vwap` field is **not** used. If cumulative
   volume through the candidate bar is zero, VWAP is undefined and
   the candidate is rejected.
4. **Entry candidate** — the **first** bar after the two range bars
   whose **close** is beyond the range: close > range high (long
   candidate) or close < range low (short candidate). The candidate
   bar may **not be the session's final bar** (on a full session this
   is exactly SRS's "closes by 15:45 ET" rule; on a 13:00 early-close
   session the candidate must close by 12:45 ET). No close beyond the
   range → no trade that symbol-session.
5. **VWAP filter (the veto)** — a long candidate is taken only if its
   close is **above** the session VWAP computed through the candidate
   bar inclusive; a short candidate only if its close is **below**
   that VWAP. **If the first candidate fails the filter, there is no
   trade that symbol-session** — no later breakout is considered
   (declared convention, see below).
6. **Entry** — at the candidate bar's close. At most **one** trade
   per symbol per session.
7. **Stop** = the opposite end of the opening range (range low for a
   long, range high for a short). **R** = |entry − stop|.
8. **Target** = entry ± **2.0 × R** (TARGET_R = 2.0, frozen). No
   trailing, no partial exits, no breakeven move, no other
   management.
9. **Exits** — stop and target are evaluated **from the next bar
   onward** (no lookahead: the entry bar's own extremes never trigger
   an exit). Within any bar, the **stop is assumed hit before the
   target** (programme worst-case convention). A bar that **opens**
   beyond a level fills at that open (simulator gap convention).
10. **Flat by close (hard)** — if neither stop nor target has
    triggered by the session's final bar, exit at that bar's close.
    Positions are **never** held overnight, on any symbol, for any
    reason.

## Declared conventions (choices this declaration makes, stated openly)

- **Universe (frozen list).** AAPL, MSFT, NVDA, AMZN, GOOGL, META,
  AVGO, TSLA, AMD, NFLX, XOM, BAC, MU, INTC, PLTR. Selection rule:
  US-listed common stocks **continuously listed for the entire panel
  span** (2023-01-01 → 2026-10-31), drawn from the S&P 500 /
  Nasdaq-100 liquidity leaders, each with full-span median daily
  share volume above the programme's 10M-share SIP floor (the floor
  is enforced per symbol by panel check 2, on split-adjusted shares
  as served). Two honest notes: (a) a "continuously listed" universe
  carries a **mild survivorship tilt by construction** — it is
  declared here, not hidden, and it is the same construction the
  programme's other panels use; (b) **no name may be added, dropped
  or substituted after this declaration for any reason** — if a name
  fails the panel gate, the panel is INCOMPLETE, not the universe
  editable. (High-price, low-share-volume names such as COST, MA,
  UNH, HD were excluded at declaration time precisely because their
  median daily share volume sits below the 10M floor.)
- **First-break-only.** The session's first close beyond the range is
  its only entry candidate (rule 5). Rationale, declared so it cannot
  be re-chosen later: the first break is the ORB event; admitting a
  later re-break after a veto would add a second, path-dependent
  entry rule and a second hypothesis. The filter is a pure gate on
  the first break — that is the single claim under test.
- **Candidate-not-final-bar.** Rule 4's form guarantees at least one
  bar remains to manage the position. It coincides with SRS's
  15:45 ET rule on full sessions and generalises it to early-close
  sessions, where SRS's literal time rule would admit a candidate on
  the final bar with no managing bar after it.
- **VWAP through the candidate bar inclusive.** The decision is made
  at the candidate bar's close, when that bar is complete; using its
  full OHLCV is causal (the SRS entry convention — an entry uses its
  own candle's close — applied to the filter).
- **Position sizing — not part of this family's identity.** The
  backtest judges per-trade net returns. If the candidate ever
  reaches forward testing it inherits the fleet-standard decided
  risk package (**FWD-006**) unchanged, exactly as SRS declares.
- **Borrow / short-sale constraints.** Shorts are judged as price
  series under the programme cost model, like every RD family; no
  borrow fee, SSR or locate constraint is modelled, and none may be
  added after the fact. This is stated so the limitation is on the
  record before any run: the bar's 16/32 bps cost model is the only
  friction charged.
- **Parameters are frozen** — OR window (2 bars), TARGET_R = 2.0,
  the VWAP formula, the universe. Variants (another window, another
  target multiple, a reversion reading, a different universe) each
  require a new declaration and raise the trial count.

## Data spec (frozen)

- **Source:** Alpaca Market Data, Basic plan ($0), historical bars
  endpoint, per symbol: `feed=sip` (consolidated CTA+UTP tape),
  `adjustment=split`, `timeframe=15Min`, `start=2023-01-01T00:00:00Z`,
  `end=2026-11-01T00:00:00Z` (end exclusive), `sort=asc`, paginated
  at `limit=10000`. Keys come from the environment only.
- **Panel:** one CSV per symbol, regular-session bars only (the pull
  keeps exactly the bars whose ET start is an expected session
  bar-start per the NYSE calendar — 26 bars per full session, 10 per
  early-close session). Expected per symbol: **961 sessions /
  24,842 bars**; expected panel total **372,630 bars** across the
  15 symbols. The raw panel is **never committed** (SIP licence);
  only the provenance record is committable.
- **Segments:** pre-OOS 2023-01-01 → 2024-06-30 (374 sessions) exists
  for mechanics debugging only (holdout procedure step 1); judgement
  is on folds W1–W5 (2024-07-01 → 2026-11-01, entry-time
  attribution, `walkforward.FOLDS` verbatim).
- **Verification gate — the SRS 5-check pattern, applied per symbol;
  the panel verdict is PASS only if every symbol passes all five:**
  1. **Gap audit** — every NYSE session has exactly its expected
     bars at exactly the expected bar-starts; no bars on
     non-sessions; no duplicate timestamps.
  2. **Feed check** — per-symbol median daily volume ≥ **10,000,000**
     shares (split-adjusted, as served). Below that the panel is
     consistent with a single-venue (IEX-like) feed and FAILS.
  3. **Split check** — no overnight open/prev-close or close/prev-close
     ratio in the split bands **[2.70, 3.30] / [0.303, 0.367]** (the
     SRS 3:1 bands) **or [9.0, 11.0] / [0.09, 0.111]** (the 10:1
     bands this universe needs: its in-window splits are 10:1).
     Extreme non-split overnight moves (> 50%) are findings to
     eyeball, not failures.
  4. **Cross-source spot check** — Yahoo Finance daily bars (chart
     API v8, `interval=1d`, keyless — the data-spec addendum v3
     instrument, adopted for this panel), one retrieved file per
     symbol, hash-pinned. Before comparison, the retrieved file is
     put on the panel's split-adjusted basis by the declared
     transform: rows dated before a declared split's ex-date are
     divided by that split's factor (declared splits: **NVDA 10:1,
     first split-adjusted session 2024-06-10; AVGO 10:1, 2024-10-14;
     NFLX 10:1, 2025-11-17**; all other universe names have no
     in-window split). Sampling is deterministic — 3 evenly spaced
     sessions per fold W1–W5 per symbol; closes must match within
     **$0.02**, highs/lows within **$0.05**; a sampled session absent
     from the file is a finding → FAIL; ≥ 10 compared per symbol
     required. No file → check NOT_RUN → panel **INCOMPLETE**, never
     PASS. A retrieved file whose hash differs from its pinned hash
     is a FAIL, not a re-pin (v3 discipline). The declared split list
     must be re-verified against Alpaca's corporate-actions data at
     pull time; a mismatch makes the panel INCOMPLETE — the list is
     never edited silently.
  5. **Freeze** — SHA-256 of every symbol's panel file, with full
     request provenance, written into `data_provenance.json`. A
     panel whose hash differs from its download-time draft is a
     FAIL, not a re-pin.
- **Data-access state at declaration (honest).** The Alpaca key pair
  is **not yet installed** on the fleet (verified 2026-11-17 ~10:34
  IST by the SRS run crew: S2 CREDENTIALS.md carries no Alpaca
  entry; the S1 env install was never performed). Installation is
  step 1 of the SRS execution sequence. This declaration therefore
  records the access proof as **pending that install**: SIP itself
  is already proven servable in full on the free account (SRS probe
  2026-11-17: AUTH VERIFIED, account ACTIVE, 317 TSLA 15Min SIP bars
  at ~47M shares/day consolidated scale; IEX ≈ 2.7% of SIP). No
  panel pull for this family may occur before the install lands and
  this family's own one-symbol-month SIP proof pull is recorded in
  the run record.

## The bar (identical to the programme)

Judged on **pooled OOS trades** (all 15 symbols, folds W1–W5,
entry-time attribution), parameters frozen — nothing is selected
in-sample:

- expectancy_net > 0 under the programme cost model **and** under
  the 2×-cost shadow;
- profit_factor_net ≥ 1.2 (strict, at 1× costs);
- ≥ **200 pooled OOS trades** — below that the verdict is exactly
  **"insufficient OOS trades"**, never padded;
- ≥ **4 of 5** walk-forward folds with positive expectancy;
- **SRS TEMPORAL HOLDOUT v1 applies** (H1–H5, adopted verbatim as
  this family's holdout leg, on the pooled trade list): H1 holdout
  (W5) ≥ 20 trades — below that the verdict is
  `FAIL (INSUFFICIENT_HOLDOUT_TRADES)`, the window never extended;
  H2 holdout expectancy > 0; H3 development-OOS (W1–W4) expectancy
  > 0; H4 no fold contributes > 80% of total positive fold profit;
  H5 the holdout is judged **exactly once** under the §2.3 procedure
  (mechanics debugging on synthetic bars or the pre-OOS segment
  only; the trade list is hash-pinned before any metric is computed;
  any change after evaluation burns the holdout permanently).
  How it binds here: the holdout addendum was written for a
  single-symbol family because `rd.common.holdout_check`'s universe
  is hardwired to the RD-001 crypto symbols; for this pooled family
  the temporal construction is adopted as the holdout leg in the
  same spirit (the SRS run's own governance decision adopted it over
  the weaker vacuous reading), and the cross-sectional discipline
  the original check embodies is carried by the breadth gate below —
  the two are complements, not substitutes;
- **Breadth gate** — no single symbol contributes more than **50%**
  of the pooled total positive net profit (the census statement of
  the programme bar);
- **Costs** — the programme cost model (`simulator.Costs()`: 5 bps
  fee + 3 bps spread/slippage per side = **16 bps round trip**) and
  the identical simulation at **32 bps round trip**; both must pass,
  applied in price space exactly as the SRS harness applies them;
- **Bonferroni** — one-sided p < 0.05 / final_N at the run's final N
  (see trial accounting);
- **Owner's deletion rule** — a strict OOS profit factor < 1.2
  deletes the family completely; a failed bar closes the family.
  Passing the bar makes this a forward-test **candidate** only,
  under the Phase-3 protocol (≥ 100 trades AND ≥ 8 weeks on demo).
  Nothing here authorises live trading.

## Trial accounting

- This declaration is **ONE cell**: one frozen configuration
  (one rule set, one timeframe, one pooled universe panel), judged
  once — the SRS / S-RD1 accounting form.
- Programme counter at declaration: **N = 3,891 declared**
  (coordinator-verified; ledger-executed basis 3,885). Queue
  position, stated honestly: equity runs go in lane order — the SRS
  run takes the counter to **3,892**, the S-RD1 run to **3,893**,
  and this family's declared run, if both land first, is cell
  **3,894** (Bonferroni α ≈ 0.05 / 3,894 ≈ **1.2839e-05**).
- The frozen method governs over the frozen number: the run
  re-reads the programme ledger at run time and uses
  **final_N = entering_N + 1**; a busier programme can only tighten
  the bar. This declaration adds **0 trials** until its run executes.

## Status

DECLARED, NOT RUN. This declaration ships with its pinned harness
package (signal/judging module, panel pull, panel verifier, one-run
driver, synthetic tests — SHA-256s stated in the prep record) — no
backtest is executed by the declaring step, no panel is downloaded,
and the holdout is unburned. The declared run is the board entry's
next_action, gated on: (1) this declaration merged with its hash
intact, (2) the SRS and S-RD1 runs concluded ahead of it in the run
lane, (3) the Alpaca credential install landed (SRS execution
step 1), and (4) this family's panel pulled and verified PASS under
the 5-check gate above.
