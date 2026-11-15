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

Suggested cadence: daily (e.g. a systemd timer alongside the existing
weekly all-time scorecard regeneration). Deployment of the timer is a
coordinator step after merge.

Tests: `Stratex/tests/test_forward_scorecard.py` (server-side pytest
is the operative gate for Stratex suites).
