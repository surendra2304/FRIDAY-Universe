# TASK-STR-RD-023 — Pre-declaration: Grid / passive market-making family (15m, pre-declared fill haircut)

**Declared 2026-11-17, before any backtest of this family has been run.**
Frozen declaration: `grid_mm_declaration.json` in this directory
(SHA-256 `2b5d807a5b00c893b1dd28af4d23b943a7fb587c15dc9a7e6cf8a5bdd8a7d66c`).
The declaration governs; if the code and the declaration disagree,
the declaration wins and the code is wrong.

## Source

The FRIDAY Universe strategy-discovery census of 2026-11-17
(`~/workspace/str-discovery-census/CENSUS.md`), recommended slate
**#7: Grid / passive MM, crypto 15m, with pre-declared fill
haircut**. Two census findings frame this family:

- (§3b) The repo module `Stratex/strategies/grid_trading.py` is
  **NOT_EVALUABLE** — no callable `get_signal` through the standard
  path — and is one of only two never-evaluated repo modules that
  are not re-skins. The grid / passive-market-making **mechanism**
  has never been declared or judged by any RD round.
- (§3c) "Kline-simulated grid fills are systematically optimistic
  (no queue position, no adverse selection). A bar run needs a
  declared fill haircut or it proves nothing."

That caveat is adopted as this declaration's core design: **the
fill haircut is frozen here, before any run, and it is the family's
honesty mechanism.** With too little haircut the run measures the
simulator; with too much, nothing survives. That tension is the
test.

### Disposition of the repo module (read in full from origin/main)

The harness **replaces** `grid_trading.py`; it does not reuse it:

1. It has no callable signal path — the reason it was never
   evaluable. The programme harness cannot drive it at all.
2. Its fill rule is the fantasy this declaration exists to kill:
   `execute_grid_check` fills a buy level when a single price print
   is `<=` the level — a **touch fill**, with no queue model, no
   trade-through requirement, and **no fees or costs anywhere**.
   Profit is booked only on sell fills as a % distance; buys are
   never marked; there is no inventory accounting.
3. Its levels alternate buy/sell by **index parity** rather than
   resting buys below / sells above an anchor with paired exits —
   not a functional grid book.
4. Its `adapt_grid` re-centres bounds on the **current** price with
   no causal placement rule and no resting-order persistence.
5. It has no inventory limits or exposure accounting of any kind.

The module is left untouched in the repo. (Arithmetic level spacing
is the standard grid construction and the new harness also uses it —
a generic technique, not code reuse.)

## The hypothesis

On 15-minute bars, a causally-placed long-only grid — trailing
7-day P10–P90 range, 10 arithmetic intervals, re-placed every 24h,
one unit per line, paired one-step exits — harvests enough range
oscillation on the three most liquid Binance USDT-M pairs to clear
the RD programme bar **even after** a pre-declared fill haircut that
removes the two known simulator fantasies: touch fills (excluded by
a 10 bps trade-through requirement) and free fills (every fill pays
programme fees plus a 5 bps adverse-selection allowance).

**Adjacent evidence, disclosed before the run:** directional and
reversion families in this programme have overwhelmingly failed the
bar (RD-001..RD-016; cointegration pairs died gross-of-costs in
RD-006). No grid or liquidity-provision family has ever been
judged, so there is no direct prior — but the honest prior for a
new OHLCV-derived family in this programme is negative, and grid
backtests in particular are known to flatter themselves. This
declaration tests exactly one new cell; it does not re-open any
judged one.

## Exact rules (frozen)

1. **Universe / timeframe** — BTCUSDT, ETHUSDT, SOLUSDT (the
   `rd/common.py` SYMBOLS triple), 15-minute bars.
2. **Placement** — first placement at the close of bar index 671,
   then every **96 bars (24h)** at that bar's close. The grid placed
   at bar *j* is active for bars *j+1 .. j+96*.
3. **Range (causal)** — lower = **10th percentile**, upper = **90th
   percentile** of the **trailing 672 bar closes** (7 days of
   completed bars ending AT the placement bar; type-7
   linear-interpolation percentiles). Never a future range, never a
   full-sample range, never hand-set. If P90 ≤ P10, no grid is
   placed for that epoch.
4. **Lines** — 11 lines, arithmetic: `L_k = lower + k × (upper −
   lower) / 10`, k = 0..10. Lines are frozen for the whole epoch —
   no intra-epoch adaptation, no re-centring.
5. **Units (long-only)** — line `L_k` (k = 0..9) may hold **one**
   long unit. It opens when a bar trades through it downward;
   entry price = `L_k`. `L_10` never buys. No short inventory is
   ever opened; the sell side exists only as paired exits.
6. **Exit** — a unit on `L_k` exits when a **later** bar trades
   through `L_(k+1)` upward; exit price = `L_(k+1)`, exit_reason
   `GRID_SELL`. There is no stop-loss and no other take-profit —
   that absence is the strategy; its risk is carried by the
   inventory cap and the teardown.
7. **Teardown** — at every placement bar's close, all open units
   are force-closed at that close (exit_reason `TEARDOWN`, full
   costs) before the new grid is placed. **No inventory carries
   across epochs.** Units open after the final bar close at the
   final close (exit_reason `END_OF_DATA`).
8. **Inventory cap** — at most one open unit per buy line, at most
   **10 open units per symbol** at any time (structural).
9. Parameters are frozen (`TRAILING_WINDOW_BARS=672`,
   `RANGE_LOW_PCT=10`, `RANGE_HIGH_PCT=90`, `GRID_INTERVALS=10`,
   `EPOCH_BARS=96`, `TRADE_THROUGH_MARGIN=0.001`,
   `ADVERSE_SELECTION_BPS_PER_FILL=5.0`) — variants require a new
   declaration and raise the trial count. This declaration is
   exactly **one trial**.

## The fill model (the haircut — frozen, argued)

- **Trade-through rule** — a resting BUY at level P fills in bar i
  **only if** bar i's range **spans** the level and trades
  **through** it downward: high ≥ P **and** low ≤ P × (1 − 0.001);
  a resting SELL at P only if low ≤ P **and** high ≥ P × (1 +
  0.001). Price must reach the level and trade **through** it by
  **10 bps**, not merely touch it. A touch without the
  through-margin is **no fill**; touches are counted in the run's
  stats (`touch_no_fill`) as the rejected fantasy fills.
  *Argument:* top-of-book spreads on these three books are ~1–3
  bps. A resting order at a merely touched level fills only if the
  whole queue ahead of it clears, which a touch does not imply —
  naive grid simulators that fill on touch manufacture most of
  their apparent edge exactly here. 10 bps (≈3–10× the spread, a
  substantial fraction of a typical 15m bar's range) means
  aggressive flow demonstrably consumed the level and printed
  beyond it. The span requirement closes the opposite hole: a
  level the bar never reached cannot have been crossed within it,
  and filling there would manufacture trades at unvisited prices.
  Gap-through bars (range entirely beyond the level) therefore do
  **not** fill — a deliberately conservative miss, since a real
  resting order would fill at the gap open; missed fills bias
  against the family, phantom fills would bias for it.
- **Fill price** — the level price exactly (limit-order semantics:
  a real limit order fills at its limit or better once its level
  trades through).
- **Fees on every fill** — the programme model
  (`simulator.Costs`): 5 bps taker fee + 3 bps spread/slippage per
  fill (16 bps round trip); the 2× shadow doubles both (32 bps
  round trip). Applied adversely in price space, as in
  `simulator._net_return`.
- **Adverse-selection allowance** — **+5 bps per fill**, on every
  fill (buys, grid sells, teardown and end-of-data exits — one
  rule, no exceptions), at **both** cost stacks. *Argument:* a
  passive fill is information — you are filled disproportionately
  when flow is pushing through your level and the move continues
  against you. Published markout estimates for passive BTC fills at
  minute horizons sit in the low single digits to ~10 bps; 5 bps —
  exactly the programme's own taker fee — cannot be dismissed as a
  token allowance. The allowance is a haircut, not a fee, so the 2×
  shadow doubles only the fee/slippage component.
- **Effective stacks** — programme: 13 bps/fill = **26 bps round
  trip**; 2× shadow: 21 bps/fill = **42 bps round trip**. Both must
  pass the bar. For scale: a trailing 7-day P10–P90 range on these
  symbols is typically ~4–12%, so one grid step (the gross of a
  round trip) is typically ~40–120 bps against 26 bps of programme
  costs — the family lives or dies on that geometry, which is the
  honest test the census asked for.

## Declared conventions (read this before citing the rules)

- **Fill sequencing** — within any bar, exits are evaluated only
  for units open at that bar's **start** (a unit bought in bar i is
  managed from bar i+1 — the programme's no-same-bar-exit
  convention). A line whose unit sold in bar i **cannot re-buy in
  bar i** (the intra-bar path is unknowable; re-buying after a sale
  in the same bar would assume the favourable ordering). Buys on
  different lines in the same bar are independent and all may fill
  (a cascading bar genuinely sweeps every resting level it trades
  through). Placement bars are processed in this order: fills under
  the old grid → teardown at the placement bar's close → placement
  of the new grid.
- **Counting rule** — one completed round trip (one buy fill + its
  matching exit fill) is **one trade**, attributed to folds by its
  **entry (buy) time** — the programme convention. Every buy has
  exactly one matching exit (grid sell, teardown, or end-of-data),
  so no open inventory enters the judgement. Per-fill counts are
  reported alongside; the bar's ≥ 200 counts **round trips**.
- **Inventory carry** — none (see rule 7). A real grid bot could
  carry inventory into the next grid; flattening is the
  conservative choice (full round-trip costs on every unit at most
  24h after entry) and keeps every unit's target inside its birth
  grid. Adding carry would be a variant.
- **Long-only** — the classic spot-style grid construction applied
  to the futures panel's prices. A symmetric long/short grid is a
  different family and would need its own declaration.
- **Panel scope** — BTC/ETH/SOL only, so `rd.common.full_report` /
  `check_bar` / `holdout_check` apply verbatim, and the haircut is
  calibrated at its most favourable end (deepest books, tightest
  spreads): fail here means fail anywhere, and no wider universe
  may be shopped ex post. Extending the universe requires a new
  declaration.
- **Bar-resolution limit** — 15m OHLC cannot reveal the intra-bar
  path, queue position, or partial fills. The trade-through margin
  and the adverse-selection allowance are the compensation.
  Residual optimism is disclosed, not hidden: once a level is
  traded through by the margin, a unit is assumed filled **in
  full** at the level price; a live book could still leave a
  partial. Even a PASS therefore measures a haircut kline
  simulation, not a live book — it earns a forward-test candidate
  slot where real fills decide, nothing more.
- **Position sizing** — not part of this family's backtest
  identity: the bar judges per-unit expectancy / profit factor,
  which are sizing-invariant. If the candidate ever reaches forward
  testing it inherits **FWD-006** with this declared mapping: unit
  notional = 1% of venue equity; the 10-unit inventory cap
  therefore caps inventory at 10% of equity notional (= FWD-006
  `MAX_POSITION_PCT` 0.10); a full inventory taking a 20% adverse
  gap loses 2% of equity (= the FWD-006 strategy heat cap 0.02).
  FWD-006's per-trade 0.1% risk rule does **not** map onto passive
  fills — a grid unit has no stop; the inventory cap plus the 24h
  teardown are this family's risk controls. The mismatch is
  recorded here rather than papered over.

## The bar (unchanged from the programme)

- expectancy_net > 0 and profit_factor_net ≥ 1.2 (strict, OOS) —
  strict OOS PF < 1.2 closes and **deletes** the family per the
  owner's standing rule
- ≥ 200 OOS round-trip trades; ≥ 4 of 5 walk-forward folds positive
- both cost stacks pass (programme 26 bps effective RT **and** the
  2×-fee shadow at 42 bps effective RT), under the fill model above
- Bonferroni against the programme trial floor at run time
  (programme counter = **3,891 declared trials** as of 2026-11-17;
  SRS's declared cell takes it to 3,892 when run, S-RD1's to
  3,893; this declaration adds exactly one further trial — the run
  states its floor)
- `rd.common.holdout_check` passes
- Data: BTC/ETH/SOL 15-minute bars via Binance Vision monthly
  klines through the programme's verified loader — the identical
  panel the Box Theory and S-RD1 runs used (2023-10 → 2026-10,
  108,192 bars/symbol, zero missing bars). Free and keyless; the
  data gate is passed before the run — no owner action is needed.

## Status

DECLARED, NOT RUN. This declaring step ships the frozen declaration
plus the pinned harness and its synthetic tests — no backtest is
executed. The declared run is the board entry's next_action.
Passing the bar would make this a forward-test *candidate* under
the Phase-3 protocol — demo only, like everything else. Failing it
closes the family.
