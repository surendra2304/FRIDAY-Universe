# TASK-STR-RD-013-CONV — RD-013 Best Config in Trade Units: Results

**Mandate:** RD-013 (cross-asset momentum rotation) recorded its metrics
in rotation *periods*, not trades, so its best config could not be judged
against the FORWARD_TEST demo-admission tier (which is stated in trades).
This study re-derives that ONE config's metrics in trade units, using the
judged harness and the provenance-verified data. Research only — no
wiring, no trading, no production change. Claim: issue #35, comment
6974274733. Base main at claim time: `9f1d187d90a784c7a940c64258758d57970e97e4`.

**Config:** `lookback_days=63, top_k=1, cadence=weekly, mode=long_only`
(the best row of `results_rd13/synthesis.json`).

## Verdict (stated first, plainly)

**FAIL — does not meet the second tier.** Judged against the FORWARD_TEST
tier (OOS expectancy > 0 AND PF ≥ 1.05 AND ≥ 200 OOS trades,
pre-Bonferroni):

| Leg | Required | In trade units | Result |
|---|---|---|---|
| Expectancy | > 0 | **+3.528% / trade** | PASS |
| Profit factor | ≥ 1.05 | **1.9663** | PASS |
| Trade count | ≥ 200 | **29** | **FAIL** |

The count leg is not close, and it is structural: the config has only
122 weekly OOS periods, so no weekly top_k=1 rotation of this form could
ever produce 200 trades; merging consecutive same-asset weeks into runs
(the pre-declared trade definition) yields 29. The config does **not**
join the wiring queue.

## Pre-declared trade definition (declared by the coordinator BEFORE any run; not altered after seeing results)

- Data: `~/workspace/str-rd2/cache2`, loaded ONLY via
  `Stratex/rigorous_backtest/rd13/rotation.py` `load_closes` (it SHA-256-
  verifies every series against its sidecar and refuses mismatches).
- Periods: `rotation.py run_config(closes, 63, 1, "weekly", "long_only")`.
  OOS periods are those attributed by period START date to folds W1–W5
  (OOS era 2024-07-01 → 2026-11-01); exactly 122 weekly OOS periods.
- A TRADE = a maximal run of consecutive OOS periods holding the same
  single asset. Periods holding cash (no asset) are not trades and break
  runs. Trade net return = Π(1 + period_net_return) − 1 over the run's
  periods. (The harness charges turnover inside period returns: the
  switch-in charge sits in the run's first period, the switch-out charge
  in the successor run's first period — costs were NOT re-charged or
  moved.)
- A run that starts before the OOS era and continues into it counts
  ONCE, with its return computed over its OOS periods only.
- Metrics: trade count, expectancy (mean trade net return), profit
  factor (sum of positive trade returns / |sum of negative trade
  returns|), win rate, folds positive in trade units (a trade belongs to
  the fold of its first OOS period), and the compounded trade-sequence
  max drawdown.

**Holdings extraction (minimal, arithmetic-preserving):** `run_config`'s
period records do not carry an explicit holdings field, but each record's
`contrib` dict maps held asset → weighted return contribution. For
top_k=1 the single key is the held asset; an empty dict is a cash period.
Holdings were read from `contrib` keys only — no harness arithmetic was
changed, added, or re-run differently. Full trade list: `conversion.json`.

## Sanity anchor (mandatory, run before the conversion)

Recomputation through `load_closes` + `run_config` + `summarise`
reproduced the recorded period metrics for this config **exactly**
(bit-for-bit on every figure):

| Metric | Recomputed | Recorded (synthesis.json) |
|---|---|---|
| OOS periods | 122 | 122 |
| Period PF | 1.4104631243693715 | 1.4104631243693715 |
| Mean period return | +0.8311546% | +0.8311546% |
| Compounded | +89.3362% | +89.3362% |
| Folds positive (period units) | 3/5 | 3/5 |
| OOS max drawdown (period level) | −39.9743% | −39.9743% |

All 7 series passed SHA-256 verification inside `load_closes`
(BTCUSDT/ETHUSDT/SOLUSDT/BNBUSDT from Binance Vision 1h→daily, SOL with
the known 5 incomplete days dropped; GOLD/SPX/NDX from Yahoo daily).
Full hashes are in `conversion.json`.

**Correction to the commissioning brief, on the record:** the brief and
`~/workspace/str-nearmiss/REPORT.md` §5 cite this config's OOS max
drawdown as −57.6%. That figure belongs to a different row of the same
grid (lookback 21 / top_k 1 / weekly / long_only, `oos_max_drawdown`
−0.5763). For THIS config, `results_rd13/synthesis.json` and
`RESULTS_RD13.md` both record **−39.97%**, and the recomputation
confirms −39.97%. The verdict above does not depend on the drawdown
figure, but the record should not carry the wrong one.

## Trade-unit results

- **Trades: 29** (16 wins, 13 losses, 0 zero), partitioning all 122 OOS
  periods — there were **0 cash OOS periods** (long_only is always
  invested), so the trades' compounded product equals the period
  compounded return exactly (+89.34%), an internal consistency check.
- **Boundary runs: 1** — an NDX run of 3 periods total whose first period
  starts before 2024-07-01; counted once, return +2.90% computed over
  its 2 OOS periods only.
- **Expectancy: +3.528% per trade. Profit factor: 1.9663.
  Win rate: 55.17%.**
- **Trade-sequence max drawdown: −39.82%** (equity curve compounding the
  29 trade returns in chronological order).
- **Folds positive in trade units: 4/5** (period units: 3/5). Per fold
  (trades assigned by first OOS period; compounded over that fold's
  trades): W1 10 trades, −0.16%; W2 7 trades, +54.22%; W3 2 trades,
  +1.16%; W4 5 trades, +1.63%; W5 5 trades, +19.61%. W1 is the negative
  fold. Note the fold picture flatters the config relative to period
  units: long runs that start in one fold harvest later folds' periods
  (e.g. the 16-period ETHUSDT run starting 2025-06-02, +60.77%, is
  booked to W2). This is a property of the pre-declared attribution,
  disclosed here, not a reason to re-attribute.
- Concentration is visible in trade units too: the two largest trades
  (ETHUSDT +60.77%, ETHUSDT +44.88%) supply most of the profit, and the
  worst trade is the single SOLUSDT week of 2024-07-29 at −29.02% — the
  same rotation-into-a-top event dissected in `RESULTS_RD13.md`.

## Drawdown honesty

- Recorded OOS max drawdown at period level for this config: **−39.97%**
  (see the correction above re the −57.6% figure in the brief).
- Trade-sequence max drawdown: **−39.82%**.
- Either figure is far beyond the FORWARD_TEST lane's kill rule (MTM
  drawdown > 5% of venue equity kills a forward run). Had this config
  been admitted on the other two legs, the lane kill rule would have
  applied to any forward run — the drawdown character that failed
  RD-013's own full bar has not changed in trade units.

## Trial counting

This study is exactly **1 trial**. Record: global counter 3,899 through
RD-020 (per `~/workspace/str-nearmiss/REPORT.md`); this conversion is +1;
RD-021 is running in parallel under another crew and its trials are
counted by that crew.

## Bottom line

In trade units the RD-013 best config is profitable per trade
(+3.53% expectancy, PF 1.97) but produces only **29 trades** against a
200-trade admission floor, with a ~−40% drawdown that the forward lane's
5% kill rule would not tolerate. **FAIL — does not meet the second
tier.** No wiring, no forward entrant, no further action owed on this
config.
