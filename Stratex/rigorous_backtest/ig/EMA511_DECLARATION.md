# TASK-IG2-STR-19 — Pre-declaration: EMA 5/11 crossover bracket family (15m)

**Declared 2026-11-17, before any backtest of this family has been run.**
Frozen declaration: `ema511_declaration.json` in this directory
(its SHA-256 is stated in the PR and in the completion comment on
issue #35). The declaration governs; if the code and the declaration
disagree, the declaration wins and the code is wrong.

## Source

IG reference corpus item `DYpKBKgKkoJ` (@tendul_siva) — an MT5
trading-bot tutorial reel. The IG full-watch programme packaged this
item's strategy as its designated RD candidate **S-RD1**
(`ig-fullwatch/packages/stratex.md`): the reel itself gives no
complete rules, but the creator's own YouTube tutorial (channel
"Crypto Tendul siva", "How to create a trading bot in Meta trader 5 |
Expert advisor | Algo trading", 2026-05-21) states the full
specification, recovered verbatim into the item file:

- attach the EA to the **15-minute** chart; plot **5 EMA** (shorter)
  and **11 EMA** (longer) on previous candles;
- when the 5 EMA crosses the 11 EMA **from below** → market **BUY**,
  stop-loss **below the recently closed candle**; when it crosses
  **from above** → market **SELL**, stop-loss **above the recently
  closed candle high**;
- **risk per trade 1%** of balance; **risk-to-reward 1:3**;
- when price has moved **half of the target**, move the SL to
  **breakeven**;
- entries **only after the EMA crossover is completed**.

**Evidence note (explicit):** the rules were recovered from the
creator's own YouTube tutorial captions + description, NOT from the
reel itself — the reel remains PARTIAL and its own subtitle track is
still unexposed. The creator's "1500% return over two and a half
months" is an **unverified claim he himself corrected** in the item's
comments (a 1500% gain does not mean the strategy made 1500% profit);
it is treated as such: it bought this family a pre-declared test,
nothing more. The prop-firm and VPS material in the item is not
adopted. Wave-1 evaluated this source item only as an MT5-venue
question (outcome: do not adopt MT5) — the strategy itself has never
been declared or tested.

## The hypothesis

On 15-minute bars, a completed EMA(5)/EMA(11) crossover traded in the
direction of the cross — stop beyond the trigger candle's extreme,
fixed 3R target, stop moved to breakeven at half target (1.5R) —
captures enough short-horizon trend persistence to clear the RD
programme bar net of costs, with the payoff asymmetry (3R wins
against 1R losses, breakeven conversion at 1.5R) doing the work.

**Adjacent evidence, disclosed before the run:** generic EMA-cross
trend modules were judged in RD-001/RD-002/RD-003 at 1h/4h/1d with
module-native exits and lost ~0.1–0.2%/trade; adx_ema at crypto30 1h
failed (PF 0.919). Those were different cells — different timeframes
and, critically, different exit constructions (no fixed 3R bracket,
no 1.5R breakeven conversion). This declaration tests exactly one new
cell; it does not re-open the judged ones, and the prior is honestly
negative.

## Exact rules (as stated in the source)

1. **Indicators** — EMA(5) and EMA(11) on bar closes, standard EMA
   recursion (k = 2/(n+1)), over the full loaded series per symbol.
2. **Entry** — a crossover evaluated on **completed bars only**:
   long when EMA(5) moves from at-or-below EMA(11) on the previous
   bar to above it on bar *i*; short mirrored. Entry at bar *i*'s
   close; the position is managed from bar *i+1* onward. No
   lookahead anywhere.
3. **Stop** — the trigger candle is bar *i*, the bar the crossover
   completed on: long stop = bar *i*'s **low**, short stop = bar
   *i*'s **high**.
4. **Target** — entry ± **3.0 × initial risk** (the source's 1:3
   risk-to-reward), initial risk = |entry − stop|.
5. **Breakeven** — when price reaches **+1.5R** (half the target),
   the stop moves to the entry price.
6. Parameters are frozen (`EMA_FAST=5`, `EMA_SLOW=11`,
   `RR_TARGET=3.0`, `BE_TRIGGER_R=1.5`) — variants require a new
   declaration and raise the trial count. This declaration is
   exactly **one trial**.

## Declared conventions (NOT in the source — read this before citing the rules)

- **Panel scope** — the source EA is instrument-agnostic and names
  no instrument. v1 tests the **crypto30 15-minute panel only** —
  the fleet's one provenance-verified 15m panel. A forex or equities
  leg needs its own declaration (forex_cross41 has no verified 15m
  history, per TASK-STR-DATA-001).
- **Breakeven evaluation** — the source gives no bar mechanics. The
  1.5R trigger is evaluated on bar extremes from the bar after
  entry; once a bar's extreme reaches it, the stop sits at entry
  from the **next** bar onward; within the trigger bar itself the
  **original** stop is checked first (worst case).
- **Opposite crossover** — not stated in the source. It does **not**
  close an open position; the position runs to its stop /
  breakeven-stop / target only. Crossovers arriving while a position
  is open on that symbol are skipped (one position at a time per
  symbol, the Box run's harness practice).
- **Degenerate risk** — if the trigger candle's extreme equals the
  entry close (zero stop distance) or the target distance is zero,
  the signal produces no trade. No minimum-R floor is imposed —
  imposing one would be a variant.
- **Stop placement** — the source says the stop sits "below the
  recently closed candle" (long) / "above the recently closed candle
  high" (short) without stating a distance. Convention: the stop sits
  **at** the trigger candle's extreme (long: bar *i*'s low; short:
  bar *i*'s high) with **zero buffer**. Any buffer beyond the extreme
  would be an invented parameter, so none is imposed; adding one
  would be a variant.
- **Position sizing** — the source's 1%-risk rule is recorded, but
  sizing is not part of this family's backtest identity: the bar
  judges per-trade expectancy / profit factor, which are
  sizing-invariant. If the candidate ever reaches forward testing it
  inherits the fleet-standard decided risk package (FWD-006)
  unchanged, as with SRS.

## The bar (unchanged from the programme)

- expectancy_net > 0 and profit_factor_net ≥ 1.2 (strict, OOS)
- ≥ 200 OOS trades; ≥ 4 of 5 walk-forward folds positive
- programme cost model (crypto 16 bps round trip) **and** a 2×-cost
  shadow (32 bps), both passing; exits under the harness convention
  (entry at the crossover bar's close, position managed from the
  next bar, stop-before-target worst case within any bar)
- Bonferroni against the programme trial floor at run time
  (programme counter = **3,891 executed trials** as of 2026-11-17;
  this declaration adds exactly one — the run states its floor)
- `rd.common.holdout_check` passes
- Data: crypto30 15-minute bars via Binance Vision monthly klines
  through the programme's verified loader — the identical panel the
  Box Theory run used (2023-10 → 2026-10, 108,192 bars/symbol, zero
  missing bars). Free and keyless; the data gate is **passed before
  declaration**, unlike SRS — no owner action is needed to run this.

## Status

DECLARED, NOT RUN. This declaring PR ships the frozen declaration
only — no signal module and no backtest. The signal module is built
to this declaration in the run step (a separate PR), and the
declared run is the board entry's next_action. Passing the bar would
make this a forward-test *candidate* under the Phase-3 protocol —
demo only, like everything else. Failing it closes the family.
