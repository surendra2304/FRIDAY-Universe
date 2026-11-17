# DECLARATION — order_flow_aggtrades (TASK-STR-RD-021)

**Status: DECLARED — not yet run.** No backtest of this family has been
executed anywhere at declaration time, and none is executed in the
declaring PR. The machine-readable declaration
(`orderflow_declaration.json`) governs; if anything here disagrees
with it, the JSON wins. Demo only.

## Source and coverage boundary

FRIDAY Universe strategy-discovery census, 2026-11-17, recommended
slate item #1: **true order flow from trade prints**.

The boundary with prior work, stated exactly: RD-012 judged
order-flow **proxy** families built from OHLCV only. Its own record
(`Stratex/rigorous_backtest/RESULTS_RD12.md`) says: *"No L2 /
trade-level data exists in this programme, so every flow quantity is
an OHLCV-derived proxy, declared as such — nothing here is true
delta."* All 28 RD-012 trials failed (best PF 0.9952) — but that
verdict covers the proxies (CLV, sign(close−open)·volume, CLV-weighted
volume on klines), **not** trade prints. No round in the programme
has ever loaded an aggTrade. This declaration is the first true-print
trial; RD-012's failure neither passes nor condemns it.

## Hypothesis

Aggressive (taker) flow imbalance measured from the actual prints
carries short-horizon information that OHLCV proxies destroy:

- **flow_thrust** — a sustained extreme imbalance over a 4-hour
  window continues in the imbalance's direction often enough to
  clear the bar with a 2.0/3.0 ATR bracket.
- **flow_absorption** — when price prints a fresh 5-hour extreme
  *against* the window's net flow (new high on net taker selling,
  new low on net taker buying), the flow is absorbing the move and
  the extreme mean-reverts often enough to clear the bar with a
  1.5/2.0 ATR bracket and a short max hold.

## Data (feasibility proven before declaring)

Binance Vision public archives (free, keyless), USDT-M futures,
monthly files, **2023-10-01..2026-10-31** (37 months). aggTrades for
the signal; klines via the programme's verified loader
(`data_feed.load_dataset`) for prices and ATR.

Probe, 2026-11-17 (download + streaming parse, no signals computed):

| Symbol-month | Zip bytes | Zip SHA-256 | Prints | Buckets |
|---|---:|---|---:|---|
| BTCUSDT 2024-01 | 522,743,749 | d752f509…b8282 | 40,294,620 | 2,976/2,976 |
| DOGEUSDT 2024-01 | 72,993,650 | 9dc8e7c…6b6b | 4,729,271 | 2,976/2,976 |

Full-panel cost, honestly: BTC alone is ~523 MB / 40.3M prints per
month (~19 GB over the span); the full crypto30 panel is estimated
at ~45–75 GB of archives and ~2–3B prints against 85 GB of free
disk — not stageable in this sandbox, and an in-memory load of even
one BTC month was OOM-killed (the pipeline must stream). The census
anticipated this ("declare a bounded universe (top-10 symbols) if
needed").

**Frozen universe (10, named):** BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT,
XRPUSDT, DOGEUSDT, ADAUSDT, TRXUSDT, LTCUSDT, LINKUSDT — the
crypto30 members with continuous USDT-M futures listings predating
the span and the deepest print flow. Fixed before any results exist;
adding or removing a symbol is a new declaration.

## Rules (frozen)

**Aggregation.** Bars sit on the same UTC grid as the klines. A
print belongs to bar t iff `t <= transact_time < t + timeframe`.
Per bar: `qty` = Σ print quantities (base asset, as archived);
`delta` = Σ signed quantity, sign **+** if `is_buyer_maker` is false
(the taker was the buyer), **−** if true (the buyer was the maker,
so the taker was the seller).

**Flow imbalance.** `CI_L(t) = Σdelta / Σqty` over the L bars ending
at t, L = 16 bars @15m / 4 bars @1h (a 4-hour window at both
timeframes). Undefined — no signal — if any window bar is missing
or Σqty = 0.

**ATR.** Wilder ATR(14) on klines, causal; brackets use the
signal bar's ATR.

**flow_thrust** (state form, on the close of bar t, when flat):
LONG iff `CI_L(t) >= +0.25`; SHORT iff `CI_L(t) <= -0.25`. Enter at
the open of t+1. Bracket: SL 2.0×ATR, TP 3.0×ATR. No time stop;
END_OF_DATA exit at the final close.

**flow_absorption** (state form, on the close of bar t, when flat;
lookback n = 20 bars @15m / 5 @1h, i.e. 5 hours): LONG iff
`low(t) < min(low, t-n..t-1)` AND `CI_L(t) > 0`; SHORT iff
`high(t) > max(high, t-n..t-1)` AND `CI_L(t) < 0`. Enter at the
open of t+1. Bracket: SL 1.5×ATR, TP 2.0×ATR; max hold 24 bars
@15m / 12 @1h, exiting at that bar's close if neither level hit
first (levels still checked first within that bar).

**Execution** (programme convention): signal on close of t → enter
open of t+1; entry bar exit-checked; stop before target within a
bar; gaps fill at the open; one position at a time per symbol;
warmup 260 bars. **No look-ahead:** a signal uses only prints and
klines of bars ≤ t; no partial bar is ever read.

**Cells: exactly 4** — {flow_thrust, flow_absorption} × {15m, 1h},
each pooled over the 10-symbol universe. This declaration adds
exactly **4 trials**.

**Parameters fixed:** THETA=0.25, FLOW_WINDOW=4h, EXTREME_LOOKBACK=5h,
ATR_PERIOD=14, THRUST_SL=2.0, THRUST_TP=3.0, ABS_SL=1.5, ABS_TP=2.0,
ABS_MAX_HOLD=24 @15m / 12 @1h, WARMUP=260. No other variants are
authorised; variants mean new declarations and a higher trial count.

## Declared conventions

- **Universe reduction** — see Data: reduced up front for measured
  staging cost, never after seeing results (none exist for this
  data class).
- **Sign convention** — `is_buyer_maker=false` ⇒ taker buy (+);
  stated because the field name invites the opposite reading; the
  harness's synthetic tests pin it.
- **Quantity basis** — base-asset quantity as archived, not quote
  volume.
- **Streaming only** — staging aggregates month by month and
  persists bars + provenance only; holding a symbol-month of prints
  in memory is prohibited by measurement (OOM), not preference.
- **Missing data** — gaps reported, never filled. A symbol with any
  missing/unparseable month, or any symbol-month whose bucket
  coverage mismatches its kline bars, is excluded entirely and
  named in the coverage manifest. Fewer than 8 of 10 symbols
  surviving ⇒ the run is UNTESTABLE and does not proceed.
- **The 1h kline hole** — the known shared 120-bar archive hole
  (touches SOL, XRP, LTC, TRX here) is used as archived: windows
  spanning a missing bar are incomplete; positions carry across
  gaps and are exit-checked on the next existing bar.
- **wf-select** — none: one frozen parameter set per mechanism
  leaves nothing to select in-sample.
- **Sizing** — not part of the backtest identity; a forward
  candidate inherits FWD-006 unchanged.

## Evaluation bar (programme standard, unchanged)

Pooled OOS, folds W1–W5 (OOS era 2024-07-01 → 2026-11-01, trades by
entry time): expectancy_net > 0 · PF ≥ 1.2 · ≥ 200 OOS trades ·
≥ 4/5 positive folds · `rd.common.holdout_check` pass · Bonferroni
one-sided p < 0.05/N at the run-time floor · 2×-cost shadow pass.
Costs: crypto 16 bps round trip (5 fee + 3 slippage bps/side);
shadow 32 bps. A cell under 200 OOS trades reports exactly
"insufficient OOS trades". Strict OOS PF < 1.2 → the cell is
deleted (owner rule). Trial accounting: programme counter at
declaration = 3,891; SRS (1) and S-RD1 (1) are queued ahead; this
declaration adds 4 — if both queued runs land first, judgement is
at N = 3,897, α ≈ 1.283e-05. The run must state the floor it used.

**Promotion path:** a full-bar pass makes a cell a forward-test
CANDIDATE only (Phase-3: ≥ 100 trades AND ≥ 8 weeks on demo).
Nothing here authorises live trading.
