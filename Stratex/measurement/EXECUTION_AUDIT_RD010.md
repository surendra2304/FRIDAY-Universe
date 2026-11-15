# TASK-STR-RD-010 — Execution Quality Audit (measured cost report)

Date: 2026-11-15. Scope: how much net edge Stratex loses between a
strategy's judged (backtest) economics and what the demo venues actually
charge and fill — split into (a) fees, (b) spread/slippage, (c) timing
delay in the daemon loop — and whether TASK-STR-RD-002's cost
assumptions survive contact with the exchange's own records.

Method: read-only against production. Sources: the strategy-tagged
fill ledger (`Stratex/state/fill_ledger.jsonl`, all 9 rows), position
tags, `state/legacy_close_records.json`, daemon heartbeat + `.env`,
and the demo-fapi account itself through the *deployed*
`BinanceFuturesAdapter` (signed GETs only: `/fapi/v1/commissionRate`,
`/fapi/v1/userTrades`). All figures below are computed from those
records; the analysis script and raw pulls are reproducible from the
task workspace.

**Sample-size honesty, up front.** The phase-3 forward window opened
today (2026-11-15 11:29:49 IST) and the account was flat at audit time:
zero forward fills exist, and a userTrades sweep of all 30 judged
symbols for today returned zero fills. Every fill-level measurement
below therefore comes from the pre-governance / legacy record (115
exchange fills pulled) plus the account's *live* fee schedule. Where
the sample is thin, the report says so.

## Verdict summary

| Channel | Verdict |
|---|---|
| (a) Fees | The venue charges **less** than RD-002 assumed (demo taker 4 bps/side vs 5 assumed) — but two accounting defects overstate results: legacy rows book **exit-side fees only** (−$9.37 missing), and the engine close path books **fees = 0**. Both fixed in this PR. |
| (b) Spread/slippage | **No leak proven on fills.** Observed adverse slippage on closes averaged 1.27 bps/side (n=3, ~$11k notionals) vs the 3 bps/side allowance; the real book's half-spreads fit that allowance for 28/30 judged symbols (ATOM/ADA are thin). But demo fills execute near the reference price despite wide quoted demo spreads — **demo understates live slippage**. Entry-side slippage is *unmeasurable* from current records (no signal reference price is stored) — instrumentation follow-up recommended. |
| (c) Timing delay | **Not a leak at the judged timeframes.** Measured scan period ≈ 20.8 s (loop saturated); worst-case signal→fill ≈ 21 s after bar close = 0.14% of a 4h bar, ~3 bps of zero-mean drift. It *was* material in the retired 15-minute scalping era. |

## (a) Fees

**The account's actual schedule** (live from `/fapi/v1/commissionRate`,
2026-11-15): maker 2.0 bps, taker 4.0 bps on BTC/SOL/UNI; PAXGUSDT
taker 5.0 bps. Across all **115 userTrades fills** pulled (SOL/UNI/PAXG,
2026-11-01 → 11-14): **115/115 are taker** (`maker=false` — market
entries + algo STOP/TAKE_PROFIT market exits, as designed), and
**115/115 commissions equal taker-rate × notional exactly**. There is
no hidden fee channel: no maker fills, no odd commission assets, no
rate drift.

**Against RD-002's model** (5 bps/side fee + 3 bps/side slippage =
16 bps round trip, `rigorous_backtest/rd2/costs2.py`):

- The fee term is **conservative on demo** by 1 bp/side (4 actual vs 5
  assumed) and **exactly realistic for live**: the standard Binance
  USDT-M taker tier is 5 bps/side, which is what RD-002 charges. Keep
  the assumption. Corollary worth stating wherever demo results are
  quoted: demo fills are ~2 bps/round-trip cheaper than the same
  trades would be live — forward-demo net figures flatter live net by
  that much, before any slippage difference.
- **Defect 1 — legacy rows book exit-side fees only.** The three
  LEGACY-UNATTRIBUTED rows (the +$195.71 headline) were staged from the
  close orders' fills alone (`legacy_close_records.json` lists only
  the close order id per record). Proof is arithmetic-exact: each
  row's `fees` equals exit-notional × taker-rate to machine precision
  (SOL 4.42938196, UNI 4.32598640, PAXG 0.52987896), and userTrades
  shows the unbooked entry commissions: SOL 4.41769956 (order
  4245384745), UNI 4.41956800 (495993093), PAXG 0.53000094
  (613822668) — **$9.3673 missing**. Corrected legacy record:

  | Symbol | Ledger net | Corrected net |
  |---|---|---|
  | SOLUSDT | −33.64 | **−38.05** |
  | UNIUSDT | +229.63 | **+225.21** |
  | PAXGUSDT | −0.29 | **−0.82** |
  | **Legacy total** | **+195.71** | **+186.34** |

  Whole-ledger consequences (the figures STR-ANS-001 serves): 9-trade
  net **+195.06 → +185.69**; profit factor **6.445 → 5.554**. The
  ledger is append-only and its rows are never edited; this PR stamps
  fee scope at import time and surfaces it in the scorecard (Fix C),
  and these corrected figures are the ones to quote. Stamping the
  three already-imported production rows needs a coordinator-approved
  annotation mechanism — deliberately not improvised here.
- **Defect 2 — `MultiVenueEngine.close_position` books fees = 0.**
  Closes routed through the engine (the live-execution API path) wrote
  `fees=0.0, net_pnl=gross_pnl` ("fees are unknown on this path").
  They are not unknown: the same adapter `get_realized_pnl` userTrades
  sum the reconciler uses for SL/TP exits applies verbatim. Every
  close through this path overstated net by the full round-trip
  commission (~8 bps of notional at the demo taker schedule). Fixed
  (Fix A): broker figures first, taker-schedule estimate as fallback —
  never zero — and the daily-loss breaker now books net on this path,
  matching the reconciler. The autonomous daemon exit paths (broker
  SL/TP reconcile, forward time exits, trend exits) already book
  through userTrades and were verified correct by construction.
- Minor: the retired testnet engine's estimate model charged a flat
  10 bps round trip on its 6 ledger rows (verified per-row) — between
  the demo actual (8) and the judged model (16); labelled "estimate",
  acceptable, venue retired. The Binance adapter's hardcoded
  `fee_paid = qty × price × 0.0004` matches the demo taker rate for
  most symbols (not PAXG's 5 bps, not the live 5 bps) but feeds no
  ledger or PnL path — cosmetic only, noted, not changed.
- Observation: the reconciler books `pnl_info` whenever the adapter
  returns a dict, and the Binance adapter returns a *zeros* dict
  (trades=0) when its userTrades lookup fails — a vanished position
  could then book a phantom 0.00 "broker" row instead of the
  fee-blind estimate fallback. Fix A guards its own path with
  `trades > 0`; the reconciler's identical edge is flagged here for
  its owner rather than changed in this PR.

## (b) Spread / slippage

Direct evidence is the three legacy closes, the only fills with a
recorded pre-trade reference (`mark_before_close`):

| Symbol | Mark | Fill | Adverse slippage |
|---|---|---|---|
| SOLUSDT | 75.82177 | 75.83 | +1.09 bps |
| UNIUSDT | 5.49952 | 5.501 | +2.69 bps |
| PAXGUSDT | 3867.72 | 3867.73 | +0.03 bps |

Mean **1.27 bps/side adverse**, max 2.69 — inside RD-002's 3 bps/side
spread+slippage allowance, at ~$11k notionals. Forward positions are
capped near ~$1k notional (max_position_pct 0.10 × ~$10.5k equity), an
order of magnitude smaller, so per-fill market impact should be no
worse. Verdict: the 3 bps/side allowance is adequate for the judged
universe at governed sizes; no order-type change is justified by this
evidence (limit entries would trade fill certainty for ~1–3 bps and
break the judged next-bar-open semantics).

**Spread snapshot (bookTicker, 2026-11-15, both venues).** On the
*real* fapi book, the judged universe's median full spread is
1.42 bps (widest: ATOM 7.83, ADA 6.69, MANA 3.31, NEAR 3.21). A
market order pays roughly the half-spread plus impact, so against
the 3 bps/side allowance the spread component fits for 28/30
symbols — but for **ATOM (half-spread 3.9 bps) and ADA (3.3 bps)
the half-spread alone exceeds the whole per-side allowance** in
this snapshot, before any impact. The flat 3 bps is a universe average,
not a per-symbol truth; per-symbol costs belong in future judging
rounds for those names (single-instant snapshot — spreads vary).

On the *demo* book the quoted spreads are far wider (median 10.1 bps
full; NEAR 67, XLM 53, DOT 49) — yet the 115 real demo fills did not
pay them (the UNI close filled 2.69 bps from mark against a quoted
32 bps spread). The demo matching engine evidently fills market
orders near the reference/mark price rather than walking its own
displayed book. Consequence for the forward programme: **demo
execution is artificially clean** — forward-demo results will
understate the slippage the same strategies would pay live,
particularly on the wide-spread tail. That is a property of the
venue, not a defect in the daemon, and it is one more reason demo
net is an upper bound on live net, never an estimate of it.

**Instrumentation gap (the real finding in this section):** entry-side
slippage cannot be measured at all today — no record stores the
signal reference price (the judged entry is the next bar's open; the
daemon stores only the fill). Recommendation, deliberately *not* in
this PR because it threads through the forward-entry path its owning
crew is actively extending: stamp the signal bar's close and the
sizing ticker's bid/ask into the position tag at entry
(`measurement/fill_ledger.append_position_tag` already carries the
row), making slippage a ledger-computable field for every future
trade instead of an archaeology project.

## (c) Timing delay

Measured from the production daemon (heartbeat, run started
2026-11-15 12:27:10 IST): **69 scan cycles in 1,432 s → 20.75 s per
cycle** against `SCAN_INTERVAL_SECONDS=15` — the scan itself takes
~20 s (61 symbols × 2 timeframes, 182 strategy evaluations plus
candle prefetch on a shared 956 MB host), so the loop is saturated
and the sleep floors at 1 s. Signals evaluate the last *closed* bar
(`df.index[-2]`, latched per bar), so worst-case signal→fill delay is
≈ one cycle (~21 s) plus sub-second order RTT after the bar closes.

At the judged timeframes this is noise: 21 s is 0.14% of a 4h bar
(0.024% of a 1d bar); at BTC-like volatility the 1σ drift over 21 s
is ~3 bps and zero-mean — there is no systematic adverse component
for close-of-bar strategies. Judged-bracket time exits are enforced
on a 60 s cadence against daily bars — likewise immaterial. SL/TP
booking lags the exchange fill by ≤ 1 cycle; that is reporting
latency only, the fills themselves are exchange-side.

Context, not a current defect: the same ~21 s loop on the retired
15-minute scalping configuration was 2.3% of a bar (~19 bps 1σ) —
part of why that era bled. If sub-hourly strategies are ever
re-judged, the scan architecture (sequential, whole-universe) is the
binding constraint, and the saturated loop is also a host-contention
fact for the seven co-resident agents — flagged for the coordinator,
not an execution leak in the current configuration.

**Daemon gate inconsistency (fixed, Fix B):** the expectancy gate in
`_execute_signal` charged `STRATEX_FEE_ROUNDTRIP=0.0008` — 8 bps,
fees only, no slippage — while the strategies it gates were judged at
16 bps and `config_strategy` itself records `total_friction_bps=16.0`
for both forward entrants. The gate now charges
`friction_rate_roundtrip` (env `STRATEX_FRICTION_ROUNDTRIP`, default
0.0016 = the judged model). Effect, stated from the gate's own
formula: at a 1% stop the cost term rises 0.08R → 0.16R, so setups
whose judged-cost expectancy is negative — previously approved on a
fees-only basis — are now skipped; at the governed ~$1,050 notional
cap that band is worth up to ~$0.84 of avoided negative expectancy
per marginal trade. (Deploy note: the production `.env`'s
`STRATEX_FEE_ROUNDTRIP=0.0008` line becomes documentation-only for
the gate; no env change is required for the new default to apply.)

## RD-002 cost assumptions — final verdicts

| Assumption (costs2.py) | Measured | Verdict |
|---|---|---|
| Crypto fee 5 bps/side | Demo 4 (PAXG 5); live standard tier 5 | **Realistic** — keep; conservative on demo |
| Crypto spread+slippage 3 bps/side | Close slippage mean 1.27, max 2.69 bps (n=3, $11k notionals); real-book half-spreads ≤3 bps for 28/30 symbols (ATOM 3.9, ADA 3.3 exceed) | **Adequate** as a universe average at governed sizes; thin for ATOM/ADA; demo fills flatter it (venue fills near reference, not its quoted book); entry side unmeasured (instrumentation gap) |
| FX majors 6 bps RT, minors 10, commodities 10–20, indices 8 | No OANDA fills exist in the ledger to test against | **Unverified** — see caveat |

## Caveats

- **OANDA execution cost is currently unmeasured, full stop.** The
  OANDA engine (`oanda_demo.trader`, 300 s loop) writes nothing to
  the fill ledger as of this audit; the only OANDA record is the
  pre-ledger SMT-v2 history from the phase-1 audit. TASK-STR-FWD-004
  (in flight today) is wiring OANDA closes into the ledger — until
  its rows exist, the FX cost rows above cannot be verified, and any
  OANDA forward claim should be treated as cost-unproven.
- **Ledger completeness:** the `unrecorded_close` measurement alert
  is latched (5 events, latest 2026-11-15T06:06Z, "fill rejected,
  missing ['qty']: BTCUSDT"). The daemon journal shows no rejections;
  the pattern matches the retired testnet engine's mirror path. Up to
  5 closes from that era may be missing from the ledger — the
  bb_reversion scorecard rows (6 recorded) are a floor, not a census.
  The venue is retired; no fix is proposed for retired code, but the
  caveat belongs next to any use of those rows.
- Slippage n=3 and entry-side n=0: section (b)'s "no leak" verdict is
  bounded by that sample. The forward window itself is the instrument
  that will grow it — provided the reference-price instrumentation
  lands.

## Fixes in this PR (each with tests in
## `Stratex/tests/test_execution_quality_rd010.py`)

- **Fix A** (`autonomy/multi_venue_engine.py`): `close_position`
  books broker round-trip fees via `get_realized_pnl` when the
  adapter reports fills, else a taker-schedule estimate labelled
  "estimate"; books net (not gross) to the breaker; records the real
  `entry_time`. Removes a phantom ~8 bps-of-notional overstatement
  per close on this path.
- **Fix B** (`autonomy/run_daemon.py`): expectancy gate charges the
  judged 16 bps round-trip friction (`STRATEX_FRICTION_ROUNDTRIP`,
  default 0.0016) instead of fees-only 8 bps.
- **Fix C** (`measurement/import_legacy_closes.py`,
  `measurement/scorecard.py`): imports stamp `fees_scope`
  (exit_only / round_trip / unknown) with a loud warning on
  exit-only records; the scorecard counts `exit_only_fee_fills` so
  the caveat is machine-visible wherever the numbers travel.
