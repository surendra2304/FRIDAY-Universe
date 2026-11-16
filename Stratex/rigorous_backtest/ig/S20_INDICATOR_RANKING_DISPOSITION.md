# S-20 Disposition — Indicator-Ranking Item (Wave-2 Cluster #91): CLOSED AS SKIP

**Item:** IG reel `DYhkjyHii9g` — @trading.ankush (Ankush Mangla), posted 2026-05-19.
**Package entry:** S-20, "Indicator-ranking evaluation (wave-2 cluster #91) — OPEN GAP"
(supervisor correction, Stratex lane, 2026-11-16).
**Board:** TASK-IG2-STR-18.
**Verdict: SKIP — closed.** No RD declaration, no backtest, no code. Grounds:
(1) not mechanically specifiable — the source contains no rules at all;
(2) opinion/promotional content with no testable spec.

---

## 1. What the source actually contains

The reel is a presenter rating trading tools on a 1–10 board. Caption (verbatim):
"Which indicator do you use ?" The complete substantive content, from the item
record's stored narrative (all ratings, verbatim verdicts):

- RSI Indicator — "0 Out Of 10 Too Fake"
- Trading Patterns — "0 Out Of 10 Too Easy"
- Supply and Demand — "3 Out Of 10 Too Basic" but "Beginner Friendly"
- Fair Value Gap — "6 Out Of 10 Good But Not Better"
- MACD — "0 Out Of 10 I Don't Use That"
- Fibonacci — "4 Out Of 10 Too Speculative"
- Liquidity Sweep — "Best 9 Out Of 10 Very Professional And Realistic Move In The Market"
- Order Flow — "Best 10 Out Of 10 Big Players Ishi Ko Use Karte"
- Anchored VWAP — "9 Out Of 10 Very Important Paired With Liquidity Sweep"
- Volume Profile — "Amazing 10 Out Of 10 Very Good With Order Flow"
- Moving Average — "Still Fake 2 Out Of 10 Better Than RSI"

That is the whole item: a ranked opinion list with one-line slogans. The creator's
fetched replies funnel viewers to a WhatsApp community ("WhatsApp community link
in bio join fast guys"), and the comment record is dominated by viewers disputing
the rankings.

The browser full-watch of this item (rounds 6+, 2026-11-16) is already on record
in the item file:

> "Classification: NONE — nothing implementable (entertainment / non-implementable
> content)." … "no implementable content recovered — NONE closure; the connector
> record above stands as the content record"

## 2. What the source does not contain

For "liquidity sweep" — and equally for every other named concept — the item
states **no** level reference (prior high/low, session level, pool definition),
**no** sweep trigger, **no** entry rule, **no** stop-loss, **no** target, **no**
instrument, **no** timeframe, **no** session, **no** sizing rule. The words are a
label plus a score. There is nothing to freeze.

## 3. Code state on main (independently re-verified 2026-11-16, main `0206c62a`)

The supervisor's finding stands exactly as recorded:

> "cluster #91 is PARTIAL, not COVERED — no module on main ranks or comparatively
> evaluates the four named indicators, and 'liquidity sweep' has zero code hits.
> What exists is components only: `ig/dom_features.py` order-flow features + a
> legacy VWAP/volume-profile strategy."

Re-verification: exact-phrase search for `liquidity sweep` / `liquidity_sweep`
over `Stratex/` on main returns zero hits (the only whole-repo hit is a
descriptive phrase, "flash liquidity sweeps", in an Inference document — not a
strategy and not Stratex). Components confirmed present:
`Stratex/rigorous_backtest/ig/dom_features.py` (order-flow features) and
`Stratex/strategies/vwap_volume_profile.py` (legacy VWAP/volume-profile
strategy). Neither ranks indicators, and neither implements a liquidity sweep.
The gap is real; the question is only whether the source justifies filling it.

## 4. Why this is a SKIP and not a pre-declared RD candidate

The fleet's declaration standard (SRS, PR #742; Box Theory, PR #729) is that a
pre-declared candidate freezes rules **stated in the source**, with any gap
filled only by explicitly labelled conventions. SRS's video stated its range
construction, entry trigger, stop and target; the declaration added four named
conventions and nothing else. Here there are no source-stated rules to freeze:
any "liquidity sweep strategy" declaration would be 100% invented by the fleet
and then falsely attributed to this source. That is fabrication, and it is
exactly what the pre-declaration discipline exists to prevent.

The same standard already closed sibling items in this package: S-10 ("stays out
as a strategy: no stop-loss, no target, no sizing and no breakout-confirmation
rule are in evidence") and S-15's strategy ("STAYS OUT (not an RD candidate): no
entry, exit, instrument, timeframe, sizing or stop rules are in evidence").
S-20's source has less than either — not even a partial rule fragment.

The ranking reading fails separately. "Order Flow 10/10, RSI 0/10" is one
creator's preference, stated with no metric, no instrument, no timeframe and no
evaluation protocol — there is no falsifiable claim to pre-declare and no spec
to implement. The fleet already performs the function the item gestures at —
ranking trading methods — by evidence, under the RD full bar (≥200 OOS trades,
PF ≥ 1.2, fold consistency, 2× costs, Bonferroni; strict OOS PF < 1.2 →
deleted). Substituting a creator's scores for that evidence bar would lower the
fleet's standard, not extend its coverage. No capability is lost by this closure.

## 5. Reopen condition

This closure is of **this item**, not of the liquidity-sweep concept. If any
source — this creator or another — states mechanical sweep rules (a defined
level reference, a sweep trigger, an entry rule, SL/TP, an instrument and a
timeframe), that source can be pre-declared verbatim through the normal RD
route at the full bar. Until then, cluster #91 / S-20 is closed.

**Disposition: SKIP. Closed 2026-11-16, TASK-IG2-STR-18.**
