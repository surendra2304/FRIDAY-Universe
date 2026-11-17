# TASK-STR-RD-018 — Pre-declaration: FX Asia-Range Fade family (fxsession)

**Declared 2026-11-17, before any backtest of this family has been
run.** Frozen declaration: `fxsession_declaration.json` in this
directory (its SHA-256 is stated in the PR and in the claim comment
on issue #35). The declaration governs; if the code and the
declaration disagree, the declaration wins and the code is wrong.

## Coverage — what was considered, and what is NOT being declared

This family was prepared for the Stratex discovery wave as "FX
session range" with two candidate variants. The coverage check
against the judged record (origin/main @ eb6d74ca, read first-hand)
found one of the two already judged, and it is **dropped before
declaration**:

- **Variant A — Asian-range BREAKOUT into London/NY: ALREADY
  JUDGED, dropped.** RD-003's `london_drive`
  (`rd3/families_fx.py::sig_london_drive`) is exactly this
  mechanism: the 00:00–07:00 UTC Asia range, a 07:00-bar close
  outside it traded directionally, ATR brackets (SL 2.0 / TP 4.0,
  max 9 bars) at 1h. Judged on forex12 + comm7: drive_plain
  1,632 OOS trades, expectancy −0.058%, PF 0.595; drive_narrow
  PF 0.922; comm7 PF 0.822 / 0.467 — all FAIL (RESULTS_RD3.md).
  RD-016 then re-judged the byte-identical signal code on
  forex_cross41 @1h (41 crosses): 0 passers (RESULTS_RD16.md).
  RD-002's `session_breakout` (rolling pre-session range break,
  @1h) covers the same hypothesis space a third way. No fourth
  asking of this question is declared.

The declared family is the remaining, unjudged variant only:

- **Variant B — Asian range FADE.** No judged family conditions an
  entry on a touch of the Asian-session range extremes with
  reversion exits. The nearest neighbours differ mechanically:
  RD-003 `overnight_drift/drift_fade` holds a fixed 21:00→07:00 UTC
  window (no range anchor); RD-005's REV variants reverse the prior
  session/window move at fixed clock anchors (no range condition —
  RESULTS_RD5.md draws this boundary itself); RD-007
  `vwap_reversion` fades a session-VWAP stretch (different anchor);
  `fx_mr_v4` (forward book) is Connors RSI(2) mean reversion on
  daily bars with an EMA(200) filter (no session element). RD-001
  `session_effects` and RD-005 SOI/HOD judged session *timing*
  (momentum/reversal at opens and hours), not range-extreme fades.

Distinction from SRS (TASK-IG2-STR-14): SRS is a US-equities
(TSLA, Alpaca SIP) *breakout* of the session's own first-two-candle
opening range. This family is FX (OANDA), a *fade*, and its range
belongs to a different session (Asia) than the trading window
(late-Asia/London). Different asset class, mechanism, range and
venue; the only shared element is the programme bar.

## The hypothesis

In the late-Asian and early-London hours, probes beyond the
completed Asian range are disproportionately false moves —
liquidity grabs and stop runs ahead of the London session's real
direction. Fading the first touch of an Asian extreme, targeting
the range midpoint with invalidation a half-range beyond the
extreme, earns positive expectancy net of the programme's FX-major
cost model.

## Exact rules

1. **Instruments / panel.** EURUSD, GBPUSD, USDJPY, AUDUSD
   (OANDA: EUR_USD, GBP_USD, USD_JPY, AUD_USD). M15 candles,
   mid price (OANDA `price=M`), complete candles only. Panel:
   bars with start time in
   **[2023-01-01T00:00Z, 2026-11-01T00:00Z)**. Source: OANDA
   practice API (`api-fxpractice.oanda.com`, v3 candles) — the
   forward venue itself. Provenance: on 2026-11-17 a probe against
   the practice API returned M15 candles from **2005-01-02** for
   all four instruments (archive start; 5,000 candles per request,
   chained on `from`), so the declared panel sits well inside the
   free obtainable span. No synthetic data; no filling or
   interpolation, ever.
2. **Asian range window.** For a UTC calendar date D, the bars
   starting in **[00:00, 06:00) UTC** — 24 M15 bars. Range high =
   max high, range low = min low over those bars, computed only
   from those completed bars and frozen at 06:00 UTC. A
   zero-height range produces no setup.
3. **DST handling.** All windows are **fixed UTC clock times and
   never shift** for any local daylight-saving change. Disclosed
   consequences: the London local open falls at 07:00 UTC during
   BST and 08:00 UTC during GMT, so the fade window's first hour
   precedes the London open in winter and contains it in summer;
   Tokyo observes no DST. This is the same fixed-UTC construction
   RD-003's `london_drive` was judged under, keeping the family
   comparable to the judged record; a local-time-anchored variant
   would be a different declaration.
4. **Fade window.** Bars starting in **[06:00, 10:00) UTC** of
   date D — 16 M15 bars (late-Asian hour plus the London open and
   its first hours).
5. **Touch (signal).** The **first** fade-window bar whose
   high ≥ range high (→ SHORT fade) or whose low ≤ range low
   (→ LONG fade). A bar touching **both** extremes produces no
   setup that day (direction is ambiguous). The signal uses only
   the frozen range and completed bars up to and including the
   touch bar.
6. **Entry.** At the **open of the bar immediately following the
   touch bar**. Mechanical guards — a failed guard voids the
   day's single setup, no second attempt:
   - the following bar must start before 10:00 UTC (a touch on
     the 09:45 bar has no in-window entry bar → no trade);
   - SHORT: `stop_price > entry_open > target_price` must hold;
   - LONG: `stop_price < entry_open < target_price` must hold.
7. **Stop.** Fixed at entry: SHORT stop = range high + 0.5 × W;
   LONG stop = range low − 0.5 × W, where W = range high −
   range low.
8. **Target.** The range midpoint, (range high + range low) / 2.
9. **Exit.** The first of: (a) target touched, (b) stop touched,
   (c) time exit at the **open of the bar starting at 10:00 UTC**.
   Stop/target are evaluated on bars from the entry (fill) bar
   onward; within any bar touching both, the **stop fills first**
   (worst case). Exit price is the target/stop level for (a)/(b)
   and the 10:00 bar's open for (c).
10. **One position per session.** At most one trade per
    instrument per UTC date; the first touch defines the day's
    only setup; no re-entry after any exit.
11. **Tradeable day.** A date D is tradeable for an instrument
    only if all 40 bars starting in [00:00, 10:00) UTC are
    present, marked complete, and contiguous (each exactly
    15 minutes after the previous), **and** the bar starting at
    10:00 UTC is present (the time-exit price must exist). Any
    missing or incomplete bar → no setup that day for that
    instrument. (Holiday-thinned days fail this rule mechanically
    and are skipped, never patched.)
12. **Costs.** The programme FX-major model (`rd2/costs2.py`
    FX_MAJOR): **6 bps round trip** — 3 bps per side
    spread+slippage, no separate commission (OANDA practice
    model) — applied adversely in price space on entry and exit.
    The 2×-cost shadow is 12 bps round trip (6 bps per side).
13. **Sizing.** Not part of this family's identity; judging is on
    per-trade net returns. If the family ever reaches forward
    testing it inherits the FWD-006 package (0.1% per-trade risk
    on venue equity, 2% heat cap) unchanged. Demo only; live
    trading is prohibited.

## The bar (unchanged from the programme)

Sets, by entry time (UTC): **development segment**
2023-01-01 → 2024-07-01 (mechanics and synthetic debugging only;
no judging, no parameter may be fitted on it — this family's
parameters are frozen above); **OOS** = walk-forward folds
W1–W5 of `walkforward.FOLDS` (W1 2024-07-01→2025-01-01,
W2 →2025-07-01, W3 →2026-01-01, W4 →2026-07-01,
W5 →2026-11-01); **D** = trades entered in W1–W4; **H** = trades
entered in W5 (the temporal holdout).

Passing requires **ALL** of:

1. Pooled OOS expectancy_net > 0 **and** PF_net ≥ 1.2 at 1× costs.
2. ≥ 200 pooled OOS trades.
3. ≥ 4 of 5 folds with positive expectancy_net (a fold with zero
   trades is not positive).
4. 2×-cost shadow: pooled OOS expectancy_net > 0 **and**
   PF_net ≥ 1.2 at 12 bps round trip.
5. Bonferroni: one-sided t-test on pooled OOS per-trade net
   returns, p < 0.05 / N_run, where **N_run = the programme
   executed-trial counter at run time + 1** (this family's single
   cell). Freeze-time floor, from the SRS run-prep records:
   3,889 executed trials with SRS's declared cell queued ahead
   of this family — the run states its own floor; the method,
   not the freeze-time number, is what is frozen here.
6. **Temporal holdout v1** (the SRS addendum's construction,
   adopted verbatim): H1 |H| ≥ 20 trades; H2 expectancy_net(H)
   > 0; H3 expectancy_net(D) > 0; H4 fold concentration — no
   single fold contributes more than 80% of total positive fold
   profit; H5 **burn clause** — the holdout is judged exactly
   once, in the single declared run; if H's trades or metrics
   are computed or inspected before that evaluation, or the
   family is re-run after H has been evaluated with any change
   to rules, parameters, conventions, costs, panel, simulator
   or judging code, the holdout is burned and this element
   FAILS permanently under this declaration.
7. **Breadth** (the `rd.common.holdout_check` construction,
   applied to this panel's instruments, since that check itself
   is hardwired to RD-001's crypto symbols): expectancy_net > 0
   on at least 2 of the 4 instruments, each with ≥ 20 OOS
   trades, **and** no single instrument contributing more than
   80% of total net profit.

**Verdicts.** All elements pass → **PROVEN**: a forward-test
candidate under the Phase-3 protocol (demo only). Pooled OOS
PF_net < 1.2 (strict) → the family **FAILS and is deleted
completely**, per the owner's removal rule. Pooled OOS trades
< 200 → the verdict is exactly **"insufficient OOS trades"**:
not proven, not promoted, and the bar is never relaxed to fit
the panel — a longer panel requires a new declaration and a new
cell. Any other element failing → FAIL, the family closes.

**Cell count: exactly 1** — one variant × one pooled
four-instrument panel × one timeframe (M15). Any variant
(different windows, stop fraction, target, or instrument set)
requires a new declaration and raises the trial count.

**Run queue.** The programme runs one declared run at a time.
This family's run executes only on coordinator order, behind
the already-declared SRS (TASK-IG2-STR-14) and S-RD1
(TASK-IG2-STR-19) runs. The exact run command is in the board
entry's next_action and the run-prep record.

## Status

DECLARED, NOT RUN. This PR ships the frozen declaration, the
pinned harness (`fxsession.py`, `run_fxsession.py`,
`fetch_fxsession_panel.py`) and its synthetic tests
(`test_fxsession.py`) — no backtest has been executed, no panel
has been staged, and no live-trading code is touched.
