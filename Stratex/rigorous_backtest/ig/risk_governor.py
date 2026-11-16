"""Risk governor for backtest engines — RESEARCH ONLY.

TASK-IG2-STR-16 (IG corpus item DZ-QETCTygV; package S-15). The item's
screen shows a 'RiskGovernor' class in the creator's backtest code. The
browser re-watch recovered the component's delta beyond the fleet's
decided FWD-006 risk package: alongside the familiar per-trade risk cap
and portfolio heat cap, the class enforces a PER-ENGINE TRADE-COUNT CAP
and fires a BREACH CALLBACK when an engine hits that cap — the two
elements FWD-006 does not have (the live daemon caps concurrent
positions per venue, not trades per engine, and has no breach hook).

This module implements that component pattern for the research side: a
backtest harness wraps each engine (strategy variant) with a governor
and asks before booking a trade. The governor tracks, per engine, the
trades taken and the currently-open risk, and enforces:

* a per-trade risk cap (one trade may not risk more than a fixed
  fraction of the equity base),
* a total heat cap (the sum of open risk across ALL engines may not
  exceed a fixed fraction of the equity base),
* a per-engine trade-count cap (the corpus delta): once an engine has
  taken its cap of trades it is BLOCKED — the breach is recorded and
  the caller's breach callback fires exactly once per blocking. The
  latch is deliberate: a count cap that silently resets mid-run would
  let an over-trading engine keep going; a research session clears it
  explicitly via reset_engine() (e.g. at a session/day boundary).

The default cap fractions below mirror the decided FWD-006 package
(0.1% of equity per trade, 2% heat) so research runs are comparable
with the forward protocol. They are DEFAULTS OF THIS RESEARCH MODULE
ONLY: nothing here imports, reads, or changes any production value,
and the live daemon never imports this module. Callers pass explicit
values when a study needs different ones.

The item's own strategy stays OUT, exactly as packaged: no entry,
exit, instrument, timeframe, sizing or stop rules are in evidence —
only the creator's outcome statistics (143 trades, 59.4% winners,
Profit Factor 1.76, 75.54% return on capital), which are UNVERIFIED
promotional claims from an unregistered signal seller and are not
adopted anywhere in this module. Only the component pattern — caps
plus a breach hook — is implemented.

Stdlib only, Python 3.10-compatible. No I/O, no clocks, no randomness:
breach events are plain dicts the caller can journal as it sees fit.
"""

DEFAULT_RISK_PER_TRADE_PCT = 0.001  # FWD-006 parity default (research only)
DEFAULT_MAX_HEAT_PCT = 0.02         # FWD-006 parity default (research only)

REASON_OK = "ok"
REASON_INVALID_RISK = "invalid_risk"
REASON_PER_TRADE_CAP = "per_trade_cap"
REASON_HEAT_CAP = "heat_cap"
REASON_TRADE_COUNT_CAP = "trade_count_cap"
REASON_ENGINE_BLOCKED = "engine_blocked"


class RiskGovernor:
    """Per-engine trade gating for a backtest run.

    equity: the equity base all fractions apply to (must be > 0).
    risk_per_trade_pct / max_heat_pct: fractions of equity in (0, 1]
    and [0, 1] respectively. max_trades_per_engine: None (uncapped)
    or an int >= 1. on_breach: optional callable invoked once per
    blocking with the breach event dict; exceptions it raises
    propagate to the caller (a broken hook must not pass silently).
    """

    def __init__(self, equity, risk_per_trade_pct=DEFAULT_RISK_PER_TRADE_PCT,
                 max_heat_pct=DEFAULT_MAX_HEAT_PCT,
                 max_trades_per_engine=None, on_breach=None):
        if equity <= 0:
            raise ValueError("equity must be > 0")
        if not 0 < risk_per_trade_pct <= 1:
            raise ValueError("risk_per_trade_pct must be in (0, 1]")
        if not 0 <= max_heat_pct <= 1:
            raise ValueError("max_heat_pct must be in [0, 1]")
        if max_trades_per_engine is not None:
            if int(max_trades_per_engine) != max_trades_per_engine \
                    or max_trades_per_engine < 1:
                raise ValueError("max_trades_per_engine must be None or an int >= 1")
            max_trades_per_engine = int(max_trades_per_engine)
        if on_breach is not None and not callable(on_breach):
            raise ValueError("on_breach must be callable or None")
        self.equity = float(equity)
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.max_heat_pct = float(max_heat_pct)
        self.max_trades_per_engine = max_trades_per_engine
        self.on_breach = on_breach
        self._engines = {}
        self.breaches = []

    # -- internal -----------------------------------------------------

    def _state(self, engine):
        return self._engines.setdefault(
            engine, {"trades": 0, "open_risk": 0.0, "blocked": False})

    def _register_breach(self, engine, state, risk_amount):
        event = {
            "engine": engine,
            "kind": REASON_TRADE_COUNT_CAP,
            "trades_taken": state["trades"],
            "cap": self.max_trades_per_engine,
            "rejected_risk_amount": risk_amount,
        }
        state["blocked"] = True
        self.breaches.append(event)
        if self.on_breach is not None:
            self.on_breach(event)
        return event

    # -- queries --------------------------------------------------------

    def trades_taken(self, engine):
        state = self._engines.get(engine)
        return 0 if state is None else state["trades"]

    def trades_remaining(self, engine):
        """Trades left before the count cap; None when uncapped."""
        if self.max_trades_per_engine is None:
            return None
        return max(0, self.max_trades_per_engine - self.trades_taken(engine))

    def open_risk(self, engine=None):
        """Open risk for one engine, or the total across engines."""
        if engine is not None:
            state = self._engines.get(engine)
            return 0.0 if state is None else state["open_risk"]
        return sum(s["open_risk"] for s in self._engines.values())

    def heat(self):
        """Total open risk as a fraction of the equity base."""
        return self.open_risk() / self.equity

    def is_blocked(self, engine):
        state = self._engines.get(engine)
        return False if state is None else state["blocked"]

    # -- decisions ------------------------------------------------------

    def check_trade(self, engine, risk_amount):
        """Would a trade risking `risk_amount` be allowed right now?

        Returns (allowed, reason); never mutates state. Reasons:
        invalid_risk, engine_blocked, trade_count_cap, per_trade_cap,
        heat_cap, ok — checked in that order.
        """
        if risk_amount <= 0:
            return False, REASON_INVALID_RISK
        state = self._engines.get(engine)
        if state is not None and state["blocked"]:
            return False, REASON_ENGINE_BLOCKED
        if self.max_trades_per_engine is not None \
                and self.trades_taken(engine) >= self.max_trades_per_engine:
            return False, REASON_TRADE_COUNT_CAP
        if risk_amount > self.risk_per_trade_pct * self.equity:
            return False, REASON_PER_TRADE_CAP
        if self.open_risk() + risk_amount > self.max_heat_pct * self.equity:
            return False, REASON_HEAT_CAP
        return True, REASON_OK

    def approve_trade(self, engine, risk_amount):
        """Book a trade if allowed; returns True iff it was booked.

        On success the engine's trade count rises by one and its open
        risk by `risk_amount`. A rejection on the trade-count cap is a
        BREACH: the engine latches blocked, the breach is recorded in
        self.breaches, and on_breach fires (once per blocking; later
        attempts report engine_blocked and do not re-fire). Other
        rejections change nothing — heat frees up as trades close, and
        an oversize single trade is a caller error, not a breach.
        """
        allowed, reason = self.check_trade(engine, risk_amount)
        if not allowed:
            if reason == REASON_TRADE_COUNT_CAP:
                self._register_breach(engine, self._state(engine), risk_amount)
            return False
        state = self._state(engine)
        state["trades"] += 1
        state["open_risk"] += risk_amount
        return True

    def register_close(self, engine, risk_amount):
        """Release open risk when a trade closes; returns the amount
        actually released (never more than the engine has open)."""
        if risk_amount < 0:
            raise ValueError("risk_amount must be >= 0")
        state = self._engines.get(engine)
        if state is None:
            raise ValueError("unknown engine: %r" % (engine,))
        released = min(risk_amount, state["open_risk"])
        state["open_risk"] -= released
        return released

    def reset_engine(self, engine):
        """Clear an engine's count, open risk, and blocked latch —
        the explicit session boundary. Breach history is kept."""
        state = self._engines.get(engine)
        if state is not None:
            state["trades"] = 0
            state["open_risk"] = 0.0
            state["blocked"] = False

    def snapshot(self):
        """Plain-dict view of the governor, for run reports."""
        return {
            "equity": self.equity,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_heat_pct": self.max_heat_pct,
            "max_trades_per_engine": self.max_trades_per_engine,
            "heat": self.heat(),
            "engines": {
                name: {
                    "trades": s["trades"],
                    "open_risk": s["open_risk"],
                    "blocked": s["blocked"],
                }
                for name, s in sorted(self._engines.items())
            },
            "breaches": list(self.breaches),
        }
