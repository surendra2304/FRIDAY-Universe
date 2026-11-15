# TASK-STR-RD-011 — Position Sizing & Portfolio Optimisation on the RD-002 Winners, Watchlist and Sleeve

**Mandate (owner, 2026-11-15 ~12:33 IST, Wave 4):** the owner's
"anything other than strategies to make profits" question, avenue #3.
Research-only simulation on the TASK-STR-RD-002 out-of-sample trade
streams: does **position sizing** (fixed 1% risk vs volatility-targeted
vs fractional Kelly) or **portfolio combination** (equal vs risk-parity
weights) turn any watchlist configuration into a bar-passer, or deepen
the winners' edge — without breaching the phase-3 kill line of 5%
strategy drawdown? No production code, registry, daemon or governance
was touched by this task.

**The one-sentence answer:** sizing cannot promote anything — expectancy
and profit factor are invariant under linear sizing, and at the standing
1%-per-trade rule *every* stream studied, both winners included,
breaches the 5% drawdown kill line, most within days — because 1% risk
per trade multiplied by 5–24 concurrent positions is 5–24% portfolio
heat, and the two phase-3 rules (1% per-trade cap, 5% DD kill) are
arithmetically inconsistent on pooled multi-symbol books. What actually
deepens the edge is **combination**: the two winners as one book survive
sizing that kills them solo, and at the largest exposure whose full-window
drawdown stays inside 5%, the winners' book compounds **+51.8%** against
**+14.2% / +11.9%** for the winners sized solo. The per-trade risk a 5%
DD line actually permits on these books is **0.03–0.41%**, not 1%.

## Integrity gate (run before any simulation number was trusted)

1. The five streams that shipped in git (`results_rd2/`) are
   byte-identical (canonical-JSON SHA-256) to the RD-002 crew's on-disk
   full backup at `~/workspace/str-rd2/results_full_backup/`.
2. `dow_effect/reversal @crypto30/1d` — one of the two winners — shipped
   in git with its trades stripped (`trades_stripped_for_ship: true`).
   Its stream was recovered from the backup; pooled OOS metrics
   recomputed from the recovered stream match the published
   `pooled_oos` **exactly** (3,660 trades, win rate 0.5226775956,
   expectancy 0.0087767851, PF 1.2574511877).
3. Stage-C replication: RD-002's own `rd2/combo.py: combine()` run on
   the four recovered sleeve streams reproduces the published
   best-per-class sleeve **to 0.00e+00** (equal: +18.83% / DD −11.54%;
   inverse-vol: +16.13% / DD −8.34%).
4. OOS filtering replicates RD-002's Stage-C loader exactly (entry ≥
   first-fold OOS start, < 2026-11-01); per-config OOS counts match the
   published pooled counts (2,302 / 3,660 / 420 / 732 / 837 / 205).
5. The five recovered row files are shipped with this task under
   `results_rd11/streams/` (SHA-256 in the synthesis file), so the whole
   study is reproducible from the repo: `rd11/sim_rd011.py` regenerates
   `results_rd11/synthesis_rd11.json` identically.

## Method (every construction disclosed)

- **Book construction** is RD-002 Stage C's, imported unchanged
  (`stream_daily_returns`): a stream is an equal-weight book — a day's
  return is the sum of that day's exiting trades' net returns divided
  by the number of positions open that day. "Unit exposure" (m = 1) is
  100% of equity spread across open positions.
- **Sizing** is a causal exposure multiplier m_t on the unit book's
  daily returns. Schemes:
  - `fixed1pct` — constant m calibrated so the *average losing trade*
    risks exactly 1% of equity: m = 0.01 · k̄ / E|loss|, where k̄ is the
    stream's average concurrency. This is the standing rule, applied
    literally to a pooled book.
  - `voltarget` — m_t = σ*/σ̂_t, σ̂ from trailing 60 days strictly past,
    σ* set to the fixed book's full-window daily vol so both schemes
    carry the same average risk (a comparison device, disclosed);
    capped at 2× m_fixed.
  - `kelly25` / `kelly50` — m_t = λ · μ̂/σ̂² from trailing 252 days
    strictly past (min 120 observations, flat before that — the honest
    cost of causal estimation), λ ∈ {0.25, 0.5}, floored at 0, capped
    at 2× m_fixed.
  - `dd-capped` (diagnostic only) — the largest constant m whose
    full-window max DD stays ≤ 5%. **Fitted on the judged window: an
    upper bound on survivable size, not a tradable rule.**
  - `fixed W1-cal` (sensitivity) — fixed1pct with m calibrated on the
    first fold's trades only.
- **Kill simulation:** running drawdown from peak beyond −5% halts the
  strategy permanently (the phase-3 rule); kill date and equity at kill
  are reported beside the unkilled path.
- **Portfolios:** WIN2 (the two winners), ALL6 (winners + 4 watchlist),
  SLEEVE4 (Stage-C best-per-class). Weights: equal (Stage-C mean),
  inverse-vol (Stage-C method), risk-parity (trailing-252d covariance
  ERC, monthly refresh, strictly past, equal until 120 observations).
- **Trial count:** 96 sizing evaluations (6 configs × 7 + 3 portfolios
  × 3 weightings × 6). They are **not** added to RD-002's 1,557
  promotion counter, because no promotion is claimed from sizing —
  sizing cannot manufacture expectancy. If these numbers are ever cited
  toward a promotion, the 96 must be added to the global N first.

## Finding 1 — the standing rule kills everything, winners first

Per-config results (OOS era 2024-07-01 → 2026-11-01; totals are
compounded over the full window on the unkilled path):

| config | n | PF | exp %/trade | k̄ | heat @1%/trade | m(1%) |
|---|---|---|---|---|---|---|
| ichimoku tk_cloud @crypto30 4h (WINNER) | 2,302 | 1.278 | +0.894 | 11.9 | 11.9% | 2.21 |
| dow reversal @crypto30 1d (WINNER) | 3,660 | 1.257 | +0.878 | 21.3 | 21.3% | 2.98 |
| bollinger p50_sd2.0 @crypto30 1d | 420 | 1.456 | +3.545 | 15.2 | 15.2% | 1.19 |
| shock k1.0 @crypto30 1d | 732 | 1.318 | +2.696 | 23.9 | 23.9% | 1.72 |
| adx_ema BARE @crypto30 4h | 837 | 1.233 | +0.795 | 5.3 | 5.3% | 0.67 |
| tsmom2_dual @comm7 4h | 205 | 1.203 | +0.558 | 3.3 | 3.3% | 0.73 |

| config | unit: total / maxDD | fixed1%: total / maxDD / kill | vol-target: total / maxDD | Kelly25: total / maxDD / kill |
|---|---|---|---|---|
| ichimoku | +246% / −43.3% | +716% / −75.0% / **day 2** | +1,255% / −71.8% | +52.6% / −32.9% / day 262, at +7.6% |
| dow | +155% / −44.2% | +132% / −87.8% / **day 4** | **−54.2%** / −99.2% | +7.4% / −15.3% / day 299, at +4.7% |
| bollinger | +42.5% / −43.3% | +47.2% / −49.5% / day 14 | +188.9% / −46.9% | +25.3% / −15.3% / day 678, at +20.5% |
| shock | +67.4% / −29.6% | +118% / −46.1% / day 10 | +422% / −51.3% | +52.3% / −16.0% / day 298, at +5.1% |
| adx_ema bare | +56.8% / −33.7% | +43.2% / −22.3% / day 36 | +65.3% / −21.4% | **−11.8%** / −20.5% / day 368 |
| tsmom2 comm | +38.0% / −15.6% | +27.1% / −11.5% / 2025-06-11 | +28.1% / −9.1% | +5.8% / −20.7% / 2025-05-20 |

Every scheme at rule-calibrated risk breaches the 5% line on every
config. This is not a window-edge artefact: excluding the first 90 days
of the window, both winners' fixed-1% max DDs are unchanged (−75.0%,
−87.8% — the deep drawdowns are mid-window: ichimoku's W3 fold runs
−72% intra-fold DD at fixed sizing; dow's W4 runs −84%). Nor is it a
calibration artefact: with m calibrated on the first fold only
(3–6× smaller: 0.20–0.64), **all six configs still breach and die**.
Even at unit exposure (no leverage at all), all six breach — the books'
raw daily swings are simply larger than a 5% line tolerates. The 3%
portfolio daily breaker tells the same story: at fixed-1% the winners'
combined book posts 88 days beyond −3% (≈ 1 day in 10).

The mechanism is arithmetic, not strategy quality: a per-trade risk cap
says nothing about how many trades are open at once. On a 30-symbol
pooled book the same rule that is prudent for a single-position strategy
authorises 12–24% of equity riding on simultaneous stops.

## Finding 2 — vol-targeting reshapes risk; it does not rescue the kill line

At equal average risk, vol-targeting raises compounded return and
Sharpe on five of six configs (ichimoku Sharpe 1.12 → 1.24; shock
0.75 → 1.04; bollinger 0.48 → 0.78) and at portfolio level (ALL6 equal
1.44 → 1.55; sleeve inv-vol 0.67 → 0.78). But max drawdowns barely move,
so nothing survives the 5% line at this risk level. And it is not
uniformly benign: on **dow_effect it destroys the stream** (−54.2%
total vs +131.5% fixed) — a Monday-calendar edge whose quiet weeks are
exactly when a trailing-vol scaler levers up into its regime breaks.
Verdict: a legitimate optional overlay for trend books; not a
drawdown-protection device, and contraindicated for the calendar
entrant.

## Finding 3 — fractional Kelly delays the kill, then still dies (and misbehaves on weak books)

Causal capped Kelly is the only scheme that survives deep into the
window — ichimoku is killed on day ~262 *while up* +7.6% (Kelly25) /
+21.5% (Kelly50); bollinger Kelly25 lasts 678 days and is killed at
+20.5%. But every config still breaches 5% eventually, because Kelly
sizes *up* after winning streaks, straight into the regime break that
ends them. On the weakest books it is actively harmful: adx_ema bare
goes **negative** under both Kelly fractions (−11.8% / −19.7% vs +43.2%
fixed), the risk-parity sleeve goes negative under Kelly (−11.5% /
−12.1%), and tsmom2's Kelly drawdowns (−20.7%) exceed its fixed-sizing
drawdown (−11.5%) — trailing-252d mean/variance estimates on thin,
regime-switching streams are too noisy to size with. **Recommendation:
do not adopt Kelly sizing for these books.**

## Finding 4 — what size actually survives a 5% DD line

Largest constant exposure whose full-window max DD ≤ 5% (fitted on the
judged window — an upper bound; forward-survivable size will be
smaller), and the compounded return earned at that size:

| book | survivable m | implied per-trade risk | total return at that size |
|---|---|---|---|
| ichimoku solo | 0.09 | 0.041% | +14.2% |
| dow solo | 0.09 | 0.030% | +11.9% |
| bollinger solo | 0.09 | 0.076% | +4.6% |
| shock solo | 0.15 | 0.087% | +9.3% |
| adx_ema bare solo | 0.15 | 0.223% | +10.5% |
| tsmom2 comm solo | 0.30 | 0.414% | +10.9% |
| **WIN2 (equal or risk-parity)** | **0.31** | **≈0.12%** | **+51.8% / +52.9%** |
| ALL6 equal | 0.31 | ≈0.18% | +28.6% |
| ALL6 risk-parity | 0.44 | ≈0.25% | +27.5% |
| SLEEVE4 equal | 0.42 | ≈0.41% | +7.9% |
| SLEEVE4 risk-parity | 0.83 | ≈0.81% | **+13.0%** |
| SLEEVE4 inv-vol | 0.59 | ≈0.57% | +9.4% |

Read vertically: the winners *combined* earn 3.7–4.4× what either earns
solo at the same drawdown cap. Read horizontally: no solo config's
survivable size is anywhere near the 1% rule.

## Finding 5 — combination is the real lever; risk-parity helps where correlations are near zero

- **WIN2:** unit-exposure max DD −15.5% against −43.3% / −44.2% solo;
  Sharpe 1.40 against 1.12 / 0.81. Equal vs risk-parity is a wash here
  (totals +249% / +257%, DD −15.5% / −15.7%, identical survivable size)
  — two streams is too few for weighting to matter.
- **ALL6:** diversification lifts Sharpe to 1.44 and unit DD to −15.4%,
  but at survivable size the six-book (+28.6%) is **beaten by the
  two-winner book (+51.8%)** — the watchlist members dilute more than
  they diversify at equal weight. Risk-parity on ALL6 trades return for
  shallowness (+70.9% unit total, −10.9% DD, survivable +27.5% at a
  larger m) — no net gain at the cap.
- **SLEEVE4:** risk-parity is the one clear weighting win: unit DD
  −11.5% (equal) → **−6.0%**, survivable exposure 0.42 → 0.83, and
  survivable return +7.9% → **+13.0%** — because the sleeve's components
  are genuinely near-uncorrelated (mean corr 0.01), which is exactly
  where risk-parity earns its keep. (Stage-C's own inverse-vol sits
  between: −8.3% DD, +9.4% at cap.)

## Direct answers to the brief's question

1. **Does sizing or combination turn any watchlist config into a
   bar-passer? No — twice over.** (a) The promotion bar's core
   (expectancy > 0, PF ≥ 1.2, significance, holdout) is invariant under
   linear sizing: bollinger's PF is 1.456 at every size, and its
   significance failure at N = 1,557 is untouched by any multiplier.
   (b) On the one bar component sizing *can* affect — kill-criteria
   survival — all four watchlist configs breach 5% DD under every
   scheme at rule-calibrated risk, exactly as the winners do. Sized
   down to survivable micro-exposure they would "survive", but so
   would a coin flip; survival at 0.03–0.4% per-trade risk is a
   property of the size, not evidence about the strategy. The
   watchlist stays the watchlist; the FORWARD_TEST lane (TASK-STR-
   FWD-003) remains the only honest route to promotion.
2. **Does sizing deepen the winners' edge?** Sizing scheme alone,
   barely: vol-targeting adds ~0.1 Sharpe on the trend winner and
   wrecks the calendar winner; Kelly adds survival time, not survival.
   **Combination** deepens it materially: the winners' book at a 5%-DD
   survivable size compounds +51.8% over the OOS window versus +14.2%
   and +11.9% solo — the single largest "free" improvement found in
   this study, and it comes from the two winners' low mutual
   correlation, not from any multiplier.
3. **The structural finding the coordinator should act on:** the
   phase-3 rule pair — 1% per-trade risk cap + 5% strategy-DD kill —
   is internally inconsistent for pooled multi-symbol books. Run
   literally, it would have killed both forward entrants in their
   first week (days 2 and 4 at full calibration; at the gentler
   first-fold calibration ichimoku still dies on day 7 and dow
   breaches in October 2024) on streams RD-002 proved are the best
   the programme has. Before TASK-STR-FWD-002's forward window produces
   its first kill decision, the sizing basis needs one of: (i) a
   **portfolio-heat cap** (sum of open per-trade risks ≤ ~2% of
   equity; per-trade risk = heat cap ÷ open count, dynamically) —
   on these books that means ≈ 0.1% per trade for the crypto pooled
   entrants; (ii) a concurrency cap per strategy; or (iii) a DD kill
   line restated for pooled books. Which basis the live daemon
   actually implements today is a question for the FWD-002 crew — this
   study simulated the rules as written, on the rules' own streams.

## Recommendations (research output; adoption is a coordinator/owner decision)

1. Run the two winners as **one combined book** for risk purposes
   (shared heat budget), whichever account structure carries them.
2. Replace the flat per-trade 1% cap for pooled books with a
   **heat cap ≈ 2% aggregate** (≈ 0.1% per trade at k̄ ≈ 20), or cap
   concurrent positions; keep 1% only for genuinely single-position
   strategies.
3. Judge and size the Stage-C sleeve with **risk-parity weights**
   (its DD halves versus equal weight at no return cost).
4. Vol-target overlay: optional on trend books only; never on
   dow_effect.
5. Do not use fractional-Kelly sizing on any of these streams.
6. The watchlist's route to promotion is unchanged: forward evidence
   in the FORWARD_TEST lane. Sizing offers it nothing.

## Caveats

- The dd-capped exposures are fitted on the same window they are
  judged on — upper bounds, stated as such wherever used. All other
  multipliers are causal.
- fixed1pct's calibration uses full-stream average loss magnitude (it
  defines the standing rule, it does not fit an edge); the first-fold
  sensitivity is reported and changes no verdict.
- Book construction is inherited wholesale from RD-002 Stage C,
  including its window-edge ramp; the headline drawdowns were verified
  unchanged when the first 90 days are excluded.
- Kelly on the LATE-profile stream (tsmom2, OOS from 2025-01-01) is
  estimation-starved by construction; its Kelly rows are the weakest
  evidence in this doc and are not load-bearing for any verdict.
- Everything here is backtest-window simulation. None of it is forward
  evidence, and none of it changes any strategy's governed status.

*Artifacts: `results_rd11/synthesis_rd11.json` (every number above),
`results_rd11/streams/` (recovered RD-002 rows with SHA-256),
`rd11/sim_rd011.py` (the simulation; regenerates the synthesis
identically). Claim: issue #35 comment 6890995669.*
