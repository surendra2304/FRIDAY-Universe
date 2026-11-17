# Forward scorecard (TASK-STR-FWD-005)

`measurement/forward_scorecard.py` is the phase-3 forward-measurement
job. The all-time `measurement/scorecard.py` answers "what has the
ledger recorded?"; this one answers, for every strategy in governed
forward trading: **how far from proving itself, how close to being
killed, and does the money reconcile?**

## What it computes (per entrant, window = fills at/after its start)

- Closed trades, wins/losses, win rate, gross/net P&L, fees (estimated-
  fee fills counted and shown), expectancy, profit factor, max
  drawdown of the cumulative net curve ($ and % of account equity).
- **Distance to the bar:** trades and days remaining to *8 weeks AND
  ≥100 closed trades*, plus a projected 100-trade date at the current
  rate.
- **Distance to each kill criterion** (semantics imported from
  `measurement/forward_guard.py` — the same code the daemon enforces
  with, so the scorecard cannot drift from the enforcer):
  expectancy < 0 or PF < 1.0 once ≥50 trades are in (below 50 the
  criterion reports `NOT_ACTIVE` with trades-to-go); drawdown > 5% of
  account equity (no trade-count gate). Sleeves are drawdown-only,
  exactly as `forward_guard.evaluate_sleeves` judges them.
- **Portfolio daily breaker:** realized net per UTC day vs 3% of that
  day's start equity (from the snapshot stream), worst day named.
- **Reconciliation per venue:** baseline equity at window start
  (post-reset boundary values — USDT-only for Binance per the faucet
  rule — else the snapshot at/before the start) + ledger net inside
  the window, checked against current exchange equity (live read-only
  probe when supplied; otherwise the engines' snapshot stream,
  labelled). The unexplained remainder is printed with a status —
  `RECONCILED` / `DISCREPANCY` / `UNRECONCILABLE` — never absorbed.
  The composite supervision figure is never an input; if supplied it
  appears as a labelled cross-reference with its delta.
- Active measurement alerts (e.g. `unrecorded_close`) are surfaced on
  the face of the scorecard, and any strategy with fills inside the
  window that no entrant claims is scored as `UNREGISTERED` — visible,
  never dropped.

Entrants resolve from `state/forward_entrants.json` if present, else
from `config_strategy.PRODUCTION_STRATEGY_REGISTRY` entries flagged
`forward_protocol: True` (plus `FORWARD_SLEEVES`), else the built-in
TASK-STR-FWD-002 defaults.

## Open positions and close verification (TASK-STR-FWD-013)

The generator also reads `state/position_tags.jsonl` — the same tag
stream the forward audit reads — and reports, per entrant:

- **Open positions.** Tags and fills are walked per (venue, symbol):
  a tag opens an episode, a fill closes it, a later tag re-opens it.
  Entrants gain `open_positions[]` (symbol, side, qty, entry, venue,
  opened-at) and `open_positions_count`. An entrant holding opens but
  no closes gets verdict `OPEN_POSITIONS`; `NO_TRADES_YET` is
  reserved for entrants with neither. (Before FWD-013 the card read
  only closed fills, so the three forward positions opened on
  2026-11-16/17 were invisible and every entrant read
  `NO_TRADES_YET`.)
- **Close verification.** Every booked close is classified
  `ledger_booked` vs `unverified`, distinctly. A close is
  `unverified` when either signal fires:
  - `fallback_exit_time` — the row's `exit_time` sits within 2s of
    the ledger append instant (`recorded_at`), the signature of a
    fallback-stamped exit (the sleeve's `_book_close` `time.time()`
    fallback and `append_fill`'s own missing-`exit_time` default
    both produce it; trade 470's gap was 12.9µs), or
  - `contradicted_by_position_tag` — a position tag carrying the
    close's exact fingerprint (strategy / side / qty / entry) is
    stamped *after* the claimed exit: the venue-side position was
    still being observed alive after it supposedly closed.

  Entrants gain `stats_basis: "ledger_booked"`, `closed_trades_booked`,
  `closed_trades_verified`, `closed_trades_unverified`,
  `verified_net_pnl`, and `unverified_closes[]` (with reasons).
  Headline stats stay over booked rows (parity with `forward_guard`,
  which enforces on the ledger); the verified subset is reported
  alongside, never silently substituted. An entrant whose closes are
  all unverified gets verdict `UNVERIFIED_CLOSES_ONLY`.

  Why this design: the scorecard's live probe carries venue *equity*
  only — there is no live position feed to verify closes against.
  The position-tag stream is the venue-observation record that
  exists (the daemon re-stamps a tag whenever it adopts a live
  position), and the fallback signature is detectable from the
  ledger row itself. A booked-but-false close is therefore flagged
  on the face of the card instead of being presented as a close.

## Running it

From `Stratex/` on Server 1 (read-only; demo data only):

```bash
python3 -m measurement.forward_scorecard            # writes state/forward_scorecard.json + prints
python3 -m measurement.forward_scorecard --stdout   # print only
python3 -m measurement.forward_scorecard --probe-json /path/to/probe.json
```

`probe.json` shape: `{"binance_futures": {"equity": 5000.0,
"unrealized": 0.0, "source": "…", "ts": "…"}, "oanda": {…}}`.
Without a probe file, the job tries the daemon heartbeat and falls
back to the snapshot stream — the method used is printed per venue.

Cadence (TASK-STR-FWD-013): `deploy/stratex-forward-scorecard.service`
(oneshot) + `deploy/stratex-forward-scorecard.timer` regenerate the
card every 15 minutes on Server 1. Activation is a coordinator step
after merge: install both units into `/etc/systemd/system/`,
`systemctl daemon-reload`, `systemctl enable --now
stratex-forward-scorecard.timer`. The generator itself is a
standalone job — no service restart is involved, and the first timer
run regenerates the card. (Before FWD-013 nothing invoked the
generator in production; the card on the server dated from a single
manual run on 2026-11-16T00:16Z.)

Tests: `Stratex/tests/test_forward_scorecard.py` (server-side pytest
is the operative gate for Stratex suites).
