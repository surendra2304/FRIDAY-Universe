# DECLARATION — TASK-STR-RD-019: Cross-sectional short-term reversal, volume-climax conditioned (crypto30, 1d)

**Family:** `xs_reversal_volclimax_1d`
**Status:** DECLARED 2026-11-17 — not yet run. No backtest of this family
has been executed anywhere at declaration time, and none is executed
in the declaring step.
**Declaration JSON:** `xsrev_declaration.json` (repo home:
`Stratex/rigorous_backtest/rd19/xsrev_declaration.json`)
**Declaration SHA-256:** `ffc3c573071ee8014d99d125cbc08551b39f47fb756696e603124b81e86f31f1`
**Demo only.** A pass makes this a forward-test CANDIDATE only
(Phase-3 protocol: ≥ 100 trades AND ≥ 8 weeks on demo; FWD-006 risk
package if it ever forward-tests). Nothing here authorises live trading.

**Source:** FRIDAY Universe Stratex discovery census 2026-11-17,
recommended slate #3 — "Cross-sectional short-term reversal, crypto30
1d (ranked weekly losers/winners fade)".

## Hypothesis

On crypto30 daily bars, the cross-sectional short-term reversal that
RD-002 measured as negative on average is state-dependent: the subset
of extreme 5-bar moves that print on climactic volume in the moved
name (a liquidity-demand / capitulation signature) reverts strongly
enough over the following 5 bars to clear the programme bar net of
costs under the family's judged bracket exits, while the
complementary quiet-move subset — excluded here by construction —
carries the negative expectancy RD-002 pooled.

## Differentiation from RD-002 xs_reversal (verbatim)

RD-002 judged the unconditional version of this construction and this declaration does not re-run it. In RD-002 batch-3 (family xs_reversal; code Stratex/rigorous_backtest/rd2/families3.py xs_reversal_fn; declared in results_rd2/batch3_declaration.json; results in results_rd2/synthesis.json), the panel was ranked by trailing L-bar return (L = 5 and L = 10), the k = 3 lowest scores were bought and the k = 3 highest sold at every 5-bar rebalance, unconditionally, with bracket_time exits (SL 2.0 x ATR(14), TP 4.0 x ATR(14), max_bars 5) and next-bar-open entries. On crypto30 — this declaration's panel — that construction lost money net of programme costs in every cell: at 1d, rev5_r5 expectancy -0.169%/trade, PF 0.957, 1,020 OOS trades, 2/5 folds positive; rev10_r5 -0.212%, PF 0.945; at 4h, PF 0.930 and 0.916. Ranking horizon class, ranking rule, rebalance cadence, tail counts and exit family of the plain construction are therefore already judged on this exact panel. What is mechanically different here is the entry event. A ranked pick is entered ONLY IF the pick's own ranking-window volume is a climax against its own trailing baseline: the sum of the symbol's daily volume over the 5-bar ranking window must be at least 1.5x the median of the 12 preceding non-overlapping 5-bar window volume sums. The conditioning variable — the moved name's own volume state — appears nowhere in the RD-002 family; it is not a point on the judged grid (whose axes were lookback, rebalance, k and the bracket). Every other element is kept identical to RD-002's rev5_r5 (lookback 5, rebalance 5, k = 3 per side, (score, symbol) tie-break, ATR(14) bracket 2.0/4.0 with max_bars 5, next-bar-open entry, programme costs), so the volume-climax gate is the single controlled difference. The claim tested is different from RD-002's: not 'extreme 5-bar cross-sectional moves revert' (judged on crypto30: on average they do not) but 'extreme 5-bar moves revert only when they are liquidity-demand moves, printed on climactic volume in the moved name; extreme moves on ordinary volume are information-driven and are excluded by construction'. Adverse prior, stated plainly: the unconditional crypto30 expectancy was negative, so this claim requires that negative expectancy to be concentrated in the non-climax subset; if it is not, this cell fails too and the family closes. Exactly one cell is declared — no grid over the climax multiple, the baseline window, the lookback, the rebalance or k exists under this declaration.

## Rules (frozen — a single cell)

- **Universe:** crypto30 (rd2/panels.py CRYPTO30, 30 Binance USDT-M symbols).
- **Timeframe:** 1d. Daily bars aggregated from the verified 15m
  panel by UTC calendar day (open first / high max / low min / close
  last / volume sum); complete 96-bar days only → exactly 1,127
  daily bars, 2023-10-01..2026-10-31, identical index for all symbols.
- **Signal bars:** j ≥ 64 and (j − 64) mod 5 = 0 on the common daily
  index, computed on completed bars only.
- **Ranking:** score = close[j] / close[j−5] − 1 (RD-002 rev5
  verbatim). Rank ascending by (score, symbol). LONG the first 3,
  SHORT the last 3. Fewer than 6 eligible symbols → no trades that
  rebalance.
- **Gate (the one difference):** V_win = Σ volume[j−4..j]; V_base =
  median of the 12 preceding non-overlapping 5-bar window volume
  sums (bars j−64..j−5; statistics.median). Enter a pick iff
  V_base > 0 AND V_win ≥ 1.5 × V_base. **No substitution** — a side
  may enter 0–3 trades.
- **Entry:** open of bar j+1. Entry time (fold attribution) = bar
  j+1's timestamp.
- **Exits:** ATR(14) Wilder (rd/common.py `atr`) at bar j. LONG stop
  = entry − 2.0×ATR_j, target = entry + 4.0×ATR_j; SHORT mirrored.
  Programme simulator order from the entry bar onward: gap through a
  level fills at the open; stop before target within a bar. No
  barrier within bars j+1..j+5 → TIME exit at the close of j+5.
  Still open at data end → END_OF_DATA at the final close.
- **Frequency:** one position per symbol; a pick while a position is
  open is skipped and counted.
- **No look-ahead:** ranking, gate and ATR at bar j use bars ≤ j;
  baseline windows end at j−5, before the ranking window opens.
- **Parameters (all of them):** LOOKBACK 5, REBALANCE 5, K 3,
  CLIMAX_MULTIPLE 1.5, BASELINE_WINDOWS 12×5, SL_ATR 2.0, TP_ATR 4.0,
  MAX_BARS 5, ATR_PERIOD 14. Trying variants means new declarations
  and a higher trial count.

## Data plan

15-minute bars, crypto30, Binance Vision monthly klines via the
programme's verified loader (`data_feed.load_dataset`), months
2023-10..2026-10, 108,192 bars/symbol, zero missing — the identical
panel and loader used by the Box Theory and S-RD1 declared runs.
Provenance: `~/workspace/srd1-runprep/panel_provenance.json`
(SHA-256 `1eeea5cd…bb464517`), cross-verified at declaration time
against `ig/box_theory_provenance.json` on origin/main (30/30
csv_sha256 match) plus an in-memory loader spot-verification. Free
and keyless; no new data source.

## Evaluation bar (identical to the programme bar)

- `rd/common.py` PROMOTION_BAR via `check_bar` + `holdout_check`
  per-symbol over all 30 symbols: expectancy_net > 0; PF_net ≥ 1.2;
  ≥ 200 pooled OOS trades; ≥ 4/5 walk-forward folds positive
  (W1..W5, entry-time attribution); holdout passes.
- Costs: 16 bps round trip (programme model) AND the 32 bps 2×
  shadow — both must pass.
- Bonferroni: one-sided t-test on pooled OOS per-trade net returns,
  N_global = max(ledger entering N at run time, 3,893) + 1; minimum
  denominator 3,894, α ≤ 1.2840e-05. The 3,893 floor charges this
  family for SRS (1) + S-RD1 (1) ahead in the queue. Declared
  programme counter at freeze: 3,891; this declaration adds exactly
  ONE trial → 3,892. The run states the N_global it used.
- Verdicts: pooled OOS < 200 at programme costs → exactly
  **"insufficient OOS trades"**; all components at both cost levels →
  **PASS** (forward-test candidate only); anything else → **FAIL**,
  the family closes.

## Known limitations, declared up front

1. Adverse prior: the unconditional sibling cells on this panel were
   negative (PF 0.945–0.957 at 1d). This cell subsets a
   negative-expectancy stream; the full bar is the protection
   against a lucky subset.
2. Trade-count risk is structural: ~212 signal bars, gated subset —
   pooled OOS trades may land below 200 ("insufficient OOS trades"
   is a live possibility, accepted here, not discovered later).
3. The gate uses only the moved name's own volume state — no
   market-wide state, order flow, funding or OI (separate slate
   items, not silent extensions).
4. Bracket simulation is bar-level on daily bars; the intrabar path
   is resolved by the programme's conservative order (stop before
   target), never by 15m detail.
5. The trailing-median baseline adapts upward in a volume trend,
   making the climax test stricter over time — intended (relative
   climax) and frozen as declared.
