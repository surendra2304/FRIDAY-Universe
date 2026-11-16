# TASK-IG2-STR-14 — Pre-declaration: SRS (School Run Strategy) family

**Declared 2026-11-16, before any backtest of this family has been run.**
Frozen declaration: `srs_declaration.json` in this directory
(its SHA-256 is stated in the PR and in the completion comment on
issue #35). The declaration governs; if the code and the declaration
disagree, the declaration wins and the code is wrong.

## Source

IG reference corpus item `DZ_aHrWuF49` (erickjablonski) — "81% win
rate day trading strategy explained for 5 year olds": a 15-minute
opening-range breakout the creator describes as a variation of a
profitable strategy he learned from Tom Hougaard. The strategy spent
the whole IG programme unregistered (wave-1 baseline item A7:
ABSENT) because its rules existed only in the reel's spoken /
on-screen content and no route could extract them verbatim. On
2026-11-16 the reel was watched in full in a browser: the burned-in
subtitle transcript was read frame by frame and the machine-heard
audio was captured as a **separate** source; the two agree on every
rule below (record: `srs-transcribe/BROWSER_TRANSCRIPT.md` in the
coordinator workspace). The creator's "81% win rate" is an
**unverified marketing claim** and is treated as such: it bought
this family a pre-declared test, nothing more.

## The hypothesis

On TSLA's 15-minute chart, a candle close beyond the first-two-
candles (opening) range of the US session, traded in the direction
of the break with the stop at the opposite end of the range and a
fixed 10-point target, wins often enough — the creator's framing is
small wins at a high win rate offsetting occasional full-range
losses — to clear the RD programme bar net of costs.

## Exact rules (as stated in the source video)

1. **Range** — high = max high, low = min low of the **first two**
   15-minute candles of the US regular session (09:30–09:45 and
   09:45–10:00 ET). A session missing those candles, or with a
   zero-height range, produces no signals. (An earlier secondhand
   summary claimed a first-candle range with pending orders; the
   video itself contradicts it — subtitle and audio both say
   "first two candles".)
2. **Entry** — wait for a later 15-minute candle to **close** above
   the range high (buy) or below the range low (sell); entry at
   that candle's close. The qualifying close must occur on a candle
   closing by 15:45 ET so at least one bar remains to manage the
   position; no qualifying close means no trade that session.
3. **Stop** = the opposite end of the range (range low for a long,
   range high for a short).
4. **Target** = entry ± 10 points (see the convention on units
   below). "Just let the trade play out" — no trailing, no partial
   exits, no other management is in the source or in this
   declaration.
5. **No lookahead** — the range uses only the session's first two
   candles; an entry uses only its own candle's close; stop and
   target are evaluated from the next bar onward.
6. Parameters are frozen (`TP_POINTS=10`) — variants require a new
   declaration and raise the trial count.

## Declared conventions (NOT in the source — read this before citing the rules)

The video does not state everything a backtest needs. Each gap is
resolved here, before any run, and is a **convention of this
declaration, not a fact from the video**:

- **Position sizing — not stated in the video** (no size, % risk or
  $ risk appears anywhere in it). Sizing is not part of this
  family's identity; if the candidate ever reaches forward testing
  it inherits the fleet-standard decided risk package (FWD-006)
  unchanged.
- **Re-entry — not stated in the video.** Convention: at most ONE
  trade per session per instrument — the range is by construction
  the session's first two candles, so the setup exists once per
  session.
- **Session-end exit — not stated in the video** ("just let the
  trade play out" is all it says). Convention: if neither stop nor
  target has triggered by the session close (16:00 ET), exit at
  the session close; positions are never held overnight. This is a
  day-trading strategy whose setup is defined by one session's
  open.
- **"10 points" unit / instrument — never named in words in the
  video.** The chart shown throughout — including at the "ten
  points" moment — is TSLA 15-minute, with a target box reading
  9.70 at that moment, so v1 reads 10 points as **10 dollars on
  TSLA** and tests TSLA only. The secondhand "ES futures points"
  reading has no support in the video itself and is **out of scope
  for v1**; testing it would require its own declaration.

## The bar (unchanged from the programme)

- expectancy_net > 0 and profit_factor_net ≥ 1.2 (strict, OOS)
- ≥ 200 OOS trades; ≥ 4 of 5 walk-forward folds positive
- programme cost model **and** a 2×-cost shadow, both passing;
  exits under the harness convention (entry at the breakout
  candle's close, position managed from the next bar, stop-before-
  target worst case within any bar)
- Bonferroni against the programme trial floor at run time
  (≥ 1,980 trials as of 2026-11-15, rising — the run states its floor)
- `rd.common.holdout_check` passes
- Data: TSLA 15-minute bars, US regular session only. The current
  operative panels (forex_cross41, crypto30) do not carry US
  equities, so the run must source a provenance-verified TSLA 15m
  panel and state its exact source and date range. With at most
  one trade per session, the OOS split alone needs ≥ 200 sessions
  with a qualifying close; if the panel cannot support that, the
  run reports the shortfall honestly instead of relaxing the bar.

## Status

DECLARED, NOT RUN. This declaring PR ships the frozen declaration
only — no signal module and no backtest. The signal module is built
to this declaration in the run step (a separate PR), and the
declared run is the board entry's next_action. Passing the bar
would make this a forward-test *candidate* under the Phase-3
protocol — demo only, like everything else. Failing it closes the
family.
