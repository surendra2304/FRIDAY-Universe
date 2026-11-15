# TASK-STR-RD-009 — Delta-Neutral Funding-Carry Feasibility

**Verdict, in two parts (they are different questions):**

1. **Against the programme bar: ZERO of the 8 pre-declared cells pass.**
   Nothing is promoted, nothing is wired anywhere. Global trial counter
   1,926 → **1,934**.
2. **Against the owner's actual question — is there a real,
   cost-surviving funding carry here? YES for the positive-funding
   direction, with three hard qualifications** (era concentration,
   small current-regime yield, margin structure). The always-on
   positive-carry book earned **+1.273% per episode, PF 2.96**, survived
   2× costs (+0.893%, PF 2.18), was net positive on **24 of 30 symbols**,
   and its pooled result is Bonferroni-significant at the global
   counter (p = 1.13e-05 < 2.59e-05). It fails the bar on exactly one
   check — the ≥200-episode count — which it **cannot** meet by
   construction (one episode per symbol per fold = 150 maximum; this
   was declared upfront in the frozen declaration, not discovered
   afterwards). The continuous always-on book compounded **+9.34% over
   the 853-day OOS era with a −1.18-percentage-point max drawdown**
   (one-leg notional, equal-weight). **The negative-funding direction
   is NOT viable**: borrow drag buries it (see §5).

This study exists because RD-003's `funding_extremes` family did not
answer the question: it was a *directional* perp signal judged
price-only, with funding cashflows explicitly not modelled
(`rd3/families_rd3.py`). RD-009 models the funding cashflows
themselves, with price exposure hedged coin-quantity-neutral.

The original RD-009 crew died on sandbox download failures before
running anything. This is the re-dispatched run: claim update + frozen
declaration posted on issue #35 (comment **6891895567**, declaration
SHA-256 `c5bb1d91f5cf349846f96a76f21d7aca3914f05d6de494ab6744fec8b242479c`)
**before any PnL was computed**.

---

## 1. What was run (exactly as declared)

- **Universe:** crypto30 panel. Coverage turned out complete — all 30
  symbols active in all 5 folds (funding, perp and spot all present at
  every daily boundary); zero symbol-folds excluded.
- **Data (all checksum-verified):** funding prints from RD-003's cache
  (30/30 CSV SHA-256 match `results_rd3/funding_manifest.json`); perp
  1h klines from RD-002's cache (30/30 sidecar hashes match); spot 1d
  klines fetched for this task from Binance Vision monthly archives,
  every zip's SHA-256 verified against its published `.CHECKSUM`
  before use — 30/30 symbols, 1,035 daily bars each, **zero absent
  months** (`results_rd9/spot_manifest.json`). Funding prints lacking
  a perp price inside the judged era: **0** (the only unpriced prints
  are the first-ever prints of 2022, before the price cache starts).
- **Mechanics:** daily 00:00 UTC decisions; entry/exit at the prior
  day's close on both legs; coin-quantity hedge fixed at entry;
  funding earned on prints in (entry, exit] at actual timestamps and
  rates, flips charged in full; settlement notional uses the perp 1h
  close at each print (declared approximation). Episodes are
  force-exited at fold end and attributed to the fold of entry.
- **Costs (1×):** spot taker 0.10%/side, perp taker 0.05%/side,
  slippage 0.02%/leg-side → **0.38% round trip** on one-leg notional.
  NEG-direction borrow: 0.02%/day (declared assumption — archives
  cannot observe real margin borrow rates, so NEG results are upper
  bounds). 2×-cost sensitivity doubles fees, slippage and borrow.
- **Cells (8 trials):** `always_pos`, `always_neg` (hold the whole
  fold), and F72-threshold cells (trailing-72h funding sum; θ =
  0.15 / 0.30 / 0.60 % per 72h; exit at θ/3, 45-day cap, fold end) in
  both directions.
- **Sanity (all pass):** S1 synthetic zero-cost frozen-price episode
  reproduces the funding sum **exactly**; S2 cost-scaling identity
  holds for all 592 episodes; S3 BTC W1 funding component recomputed
  by an independent brute-force path matches the engine to <1e-9
  (5.308120642643113 vs 5.308120642643102).

## 2. Per-cell results vs the bar

Bar = RD-002's checks with episodes in place of trades: expectancy>0,
PF≥1.2, ≥200 episodes, ≥80% folds positive, holdout (W5) expectancy>0,
breadth ≥50%, 2×-cost expectancy>0, Bonferroni p < 0.05/1,934.

| Cell | Episodes | Expectancy | PF | 2×-cost exp | Folds + | Breadth | p | Failed checks |
|---|---|---|---|---|---|---|---|---|
| always_pos | 150 | **+1.273%** | **2.960** | **+0.893%** | 4/5 | 0.80 | 1.1e-05 ✓ | episodes (150<200, by construction) |
| always_neg | 150 | −5.445% | 0.035 | −9.237% | 0/5 | 0.00 | 1.0 | all |
| thr_pos_015 | 31 | +2.446% | 1605.9 | +2.066% | 1/5 | 1.00 | 1.9e-12 ✓ | episodes, folds, holdout |
| thr_pos_030 | 25 | +0.260% | 23.16 | −0.120% | 1/5 | 0.84 | 1.6e-05 ✓ | episodes, folds, holdout, 2×-cost |
| thr_pos_060 | 0 | — | — | — | 0/5 | — | — | never triggered anywhere in the era |
| thr_neg_015 | 167 | −0.034% | 0.867 | −0.571% | 2/5 | 0.15 | 0.67 | expectancy, PF, episodes, folds, breadth, 2×-cost, Bonferroni |
| thr_neg_030 | 51 | +0.400% | 3.266 | −0.131% | 3/5 | 0.57 | 0.019 | episodes, folds, 2×-cost, Bonferroni |
| thr_neg_060 | 18 | +1.282% | 16.79 | +0.739% | 3/5 | 0.80 | 0.0086 | episodes, folds, Bonferroni |

Fold detail for `always_pos` (sum of episode PnL %, 30 episodes/fold):
W1 **+161.83**, W2 +15.83, W3 +36.75, W4 **−36.49**, W5 +13.05.

Three structural facts the table hides:

- **Threshold-POS is a W1-only phenomenon.** All 31 `thr_pos_015` and
  all 25 `thr_pos_030` episodes occur in W1 (2024 H2). After 2024,
  trailing-72h funding essentially never again reaches even
  0.15%/72h on this panel — funding compressed to the 0.01%/8h
  baseline and below. These cells are not wrong; the regime they
  harvest ended.
- **W4 (2026 H1) was a broad funding-flip fold**: INJ (−8.14%),
  ATOM (−6.33%), TRX (−5.32%), SAND (−3.83%), DOT (−3.50%),
  APT (−3.49%) all paid negative funding through the fold.
- **Era concentration is the headline caveat.** 85% of `always_pos`'s
  total profit is W1. Post-W1 expectancy is +0.243%/episode; the most
  recent fold (W5) annualises to **≈ +1.29%/yr on one-leg notional** —
  positive, but thin (see §4 for total-capital conversion).

## 3. The always-on POS book, per symbol (continuous era book)

853 days, one episode per symbol, costs charged once. The basis
component is within ±0.20% for every symbol over 2.34 years — the
hedge works; **funding is the entire return**.

| Symbol | Funding % | Basis % | Net % | Annualised % |
|---|---|---|---|---|
| XRPUSDT | +33.01 | +0.08 | **+32.71** | +14.01 |
| AAVEUSDT | +24.99 | +0.20 | **+24.81** | +10.62 |
| SUIUSDT | +24.43 | −0.01 | **+24.03** | +10.29 |
| DOGEUSDT | +20.28 | +0.01 | **+19.91** | +8.52 |
| ADAUSDT | +17.73 | +0.03 | **+17.37** | +7.44 |
| HBARUSDT | +17.22 | −0.01 | **+16.82** | +7.20 |
| BTCUSDT | +16.95 | +0.09 | **+16.66** | +7.13 |
| LTCUSDT | +15.69 | +0.01 | **+15.33** | +6.56 |
| LINKUSDT | +15.21 | +0.10 | **+14.92** | +6.39 |
| VETUSDT | +14.65 | −0.02 | **+14.25** | +6.10 |
| UNIUSDT | +13.24 | +0.16 | **+13.02** | +5.57 |
| ALGOUSDT | +11.32 | +0.01 | **+10.95** | +4.69 |
| ETHUSDT | +10.25 | −0.01 | **+9.87** | +4.22 |
| ETCUSDT | +10.14 | −0.05 | **+9.71** | +4.16 |
| MANAUSDT | +8.57 | −0.03 | **+8.16** | +3.49 |
| SANDUSDT | +8.11 | −0.07 | **+7.66** | +3.28 |
| FILUSDT | +8.05 | −0.05 | **+7.62** | +3.26 |
| ARBUSDT | +7.85 | −0.03 | **+7.44** | +3.18 |
| OPUSDT | +7.70 | −0.02 | **+7.30** | +3.12 |
| NEARUSDT | +7.10 | +0.08 | **+6.79** | +2.91 |
| XLMUSDT | +6.62 | −0.15 | **+6.08** | +2.60 |
| SOLUSDT | +5.91 | +0.05 | **+5.58** | +2.39 |
| DOTUSDT | +5.05 | −0.03 | **+4.65** | +1.99 |
| AVAXUSDT | +3.99 | +0.03 | **+3.64** | +1.56 |
| INJUSDT | +4.07 | −0.07 | **+3.63** | +1.55 |
| BNBUSDT | +2.47 | +0.04 | **+2.13** | +0.91 |
| APTUSDT | +2.12 | −0.09 | **+1.66** | +0.71 |
| BCHUSDT | −5.64 | −0.01 | **−6.03** | −2.58 |
| ATOMUSDT | −4.75 | +0.01 | **−5.11** | −2.19 |
| TRXUSDT | −21.08 | +0.18 | **−21.27** | −9.11 |

27 of 30 symbols net positive on the continuous book. The three
losers are persistent *negative*-funding names — they belong (if
anywhere) in the NEG book, which §5 shows does not pay either.

## 4. What the yield means in capital terms

Yields above are on **one-leg notional**. A real book ties up the
spot cash (1.00× notional) **plus** perp margin:

| Margin structure | Total capital per 1.0 notional | Era-average yield | W5-regime yield |
|---|---|---|---|
| Perp at 1× (margin 1.00) | 2.00 | ≈ +2.00%/yr | ≈ +0.65%/yr |
| Perp at 3× (margin 0.333) | 1.333 | ≈ +3.00%/yr | ≈ +0.97%/yr |
| 3× + 0.50 top-up reserve | 1.833 | ≈ +2.18%/yr | ≈ +0.70%/yr |

Scale arithmetic, stated plainly: at the current (W5) regime and a 3×
margin structure, ₹50,000/month would require on the order of
**₹6 crore** of deployed capital; at the era-average rate, ~₹2 crore.
Funding carry on this evidence is a real but **small** yield — a
treasury-style return on idle capital, not an income engine at any
capital scale currently in the picture. It does not change the
Stratex profitability picture by itself.

## 5. The NEG direction is not viable

- `always_neg` loses on **every** symbol-fold (expectancy −5.445%,
  PF 0.035, breadth 0.00). It pays the same funding POS receives,
  *plus* borrow.
- On the continuous era book, only **TRX** finishes positive
  (+3.45% net, +1.48%/yr): its +21.08% funding harvest barely survives
  17.44 points of borrow (853 days × 0.02%/day) + fees. ATOM and BCH
  have positive NEG funding (+4.75%, +5.64%) and still finish at
  −12.71% and −11.79% after borrow. At a 0.04%/day borrow rate TRX
  also goes negative. The entire NEG case rests on an *assumed*
  borrow rate and on borrow availability that archives cannot
  observe; several of these spot markets are thin to borrow in size.
- Threshold NEG cells (`thr_neg_030/060`) are positive at 1× costs on
  small samples (51 / 18 episodes, concentrated in W3–W5) but fail
  2×-cost (030) and Bonferroni (both). Texture, not a book.

## 6. Failure modes, measured

- **Funding flips are the tail risk.** Negative-print share in the
  era: ATOM 55.6% of prints (longest streak 79 prints ≈ 26 days),
  TRX 46.1%, BCH 48.9%; APT's longest negative streak is **174
  prints ≈ 58 days**. The single worst episode in the study is a
  flip: SAND `always_pos` W5 harvested **−20.40% funding** in 123
  days (−20.68% net). An always-on book eats flips in full; symbol
  selection *is* the risk management, and yesterday's payer becomes
  tomorrow's payer-in-reverse (SAND was +7.66% on the era book and
  −20.68% in W5 alone).
- **Margin excursions are the operational risk.** Across all 592
  episodes, the worst intra-episode perp move *against* the perp leg
  has **median +20.1%, p95 +109.5%, max +598%** (1h highs/lows vs
  entry). The exchange margin account does not see the spot leg: at
  the owner's 3× pin on isolated margin, a +33% adverse move
  liquidates the perp leg — the *median* episode came within
  two-thirds of that, and ordinary bull legs (BTC W1: +72.7%)
  blow straight through it. **A carry book at 3× isolated margin
  would have been liquidated repeatedly.** It is only operable with
  cross/portfolio margin that nets the spot leg, or ~1× perp margin
  with a staffed top-up process. This — not fees, not basis — is the
  binding constraint on the 3× yield figures in §4.
- **Basis blowouts: did not happen.** Worst per-symbol era basis
  component is ±0.20%; the hedge's price risk is genuinely small at
  daily granularity on these liquid pairs. The risk lives in funding
  sign and margin mechanics, not in the basis.

## 7. Forward-test specification (what would settle it)

Demo-fapi **cannot** host this book — it is futures-only; there is no
spot leg. The honest forward test is a **paper simulation on live
mainnet data** (read-only public feeds; hypothetical fills logged at
print timestamps), or spot-testnet + demo-fapi run in parallel with
the clock-skew caveat recorded. Specification:

- **Duration:** ≥ 6 months AND ≥ 2 funding-regime turns (a held
  symbol flipping sign for ≥ 14 days), whichever is later.
- **Logging:** every funding print per held symbol (rate, mark,
  cashflow), daily basis marks, daily margin-excursion maxima at the
  intended leverage, borrow quotes for any NEG candidate (observed,
  not assumed), all hypothetical fills with the §1 cost model.
- **Kill criteria:** rolling-90d net < 0 after costs → stop; any
  symbol's flip costing > 5% of its notional in 30 days → symbol
  dropped; adverse excursion > 25% against the perp leg at intended
  leverage → halt, margin structure reassessed before resuming.
- **Pass standard for even proposing a governed deployment:**
  forward net yield ≥ the W5 backtest rate (≈ +1.3%/yr one-leg)
  sustained over the window, zero kill trips, and a proven top-up /
  margin runbook. Live trading would remain a separate owner
  decision on that record, per the standing rule.

## 8. Method notes and limitations

- Episode PnLs share calendar days across symbols (cross-correlated),
  so t-test p-values are optimistic; the Bonferroni threshold at the
  global counter is the guard, and no verdict above rests on a
  p-value alone. Declared upfront.
- The ≥200-episode check is structurally unreachable for always-on
  cells (150 max). The bar outcome is reported as declared; the
  feasibility verdict rests on the labelled descriptive evidence
  (expectancy, PF, 2×-cost survival, breadth, drawdown), not on a
  bent bar.
- Funding settlement uses the perp 1h close at each print as the mark
  approximation; funding cashflows are second-order sensitive to this
  (rates are small fractions of notional).
- No rebalance trades exist by construction (coin-quantity hedge);
  USDT-settled perp PnL drift against the spot leg is inside the
  basis component as measured.
- Trial count: **8**. Global counter 1,926 → **1,934**. Research
  only: no orders placed anywhere; no production code, registry or
  daemon touched.
- The repo's `AGENTS.md` turn-completion Telegram protocol applies
  to ZAI agent sessions; this Muse research crew reports through
  the board and issue #35 per its tasking (same note as RD-003).

**Deliverables:** `results_rd9/` (declaration.json, synthesis.json,
rows_rd9.json, episodes_rd9.csv, descriptive.json, spot_manifest.json),
`rd9/carry_sim.py` (the simulator, incl. sanity checks S1–S3).
