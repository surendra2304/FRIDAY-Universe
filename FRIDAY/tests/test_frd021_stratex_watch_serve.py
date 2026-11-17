"""TASK-FRD-021: read-only Stratex status served from FRIDAY's stratex_watch snapshot.

Stratex's /v1/task/execute status path does 0-7 ms of its own work (the
FRD-011 keeper snapshot) but the round trip episodically walls 1-10 s on
in-process contention inside Stratex's swapped Werkzeug process (FRD-005
re-run #8: ~9.7 s of the 20.20 s delegation turn). FRIDAY therefore
answers read-only portfolio/status questions from the Stratex state
files its PRO-001 watch family already reads, composed exactly as
Stratex's supervision status composes them (STALE-STATE fix, coupled
with the Stratex-side supervision PR — this pin targets Stratex's NEW
composition, per ~/workspace/stale-portfolio-state/SCOPE.md §5/§6-S2):

- aggregates (balance, unrealized P&L, open count) from
  daemon_heartbeat.json — the multi-venue daemon's combined totals;
- position rows from forward_scorecard.json's per-entrant
  open_positions projection, flattened across ALL entrant cards;
- the ledger scorecard from fill_ledger.jsonl scored with
  measurement.scorecard's arithmetic;
- freshness gates: the heartbeat at 60 s (Stratex's own telemetry
  bound) and the scorecard's generated_at at 30 min.

The retired cloud_portfolio_state.json (frozen 2026-11-08 MT5 state:
balance 10792.8, ZERO positions while the daemon ran a live book) is
never read on this path — a poison copy of it sits in the fixture
world and must never be served. A missing/stale/divergent snapshot
falls back to the live dispatch, unchanged.

Rules pinned here:
- a fresh snapshot serves WITHOUT any execute round trip;
- receipt-exactness: snapshot-served figures byte-match the figures
  the live path serves from the same state (new-composition shape:
  balance 20,560.19 / 4 open / 10 closed / net +195.06 / win rate
  40% / unrealized -0.27). The pin's live side is Stratex's REAL
  composition — the actual measurement.scorecard.build_scorecard()
  output for the ledger block, whose strategies map carries the
  governed zero-trade registry entries and puts the one-trade
  sleeve beyond the formatter's six-line window, and the daemon
  leg composed from the same heartbeat + scorecard files with
  SCOPE.md §5's field mapping — never a hand-grouped model of the
  ledger (the first version's hand-built payload shared the
  implementation's wrong assumption and the supervisor review
  rejected it);
- the formatter's per-strategy window counts strategies that
  actually traded: zero-trade padding can never window-hide a
  trading strategy from either render;
- a stale heartbeat (>60 s), a missing heartbeat, a non-RUNNING
  daemon, a missing or stale (>30 min) scorecard, a
  scorecard/heartbeat count divergence, or a non-numeric heartbeat
  aggregate all fall back to the live dispatch — a partial
  position list is never served;
- per-row unrealized P&L is OMITTED, never zero-filled (the
  scorecard carries no marks); the headline unrealized comes from
  the heartbeat, never summed from rows; the scorecard's
  account_equity_usd (a different, snapshot-window basis) is never
  the balance;
- the halt state is snapshot-served too (TASK-FRD-021 follow-up):
  panic_state.json + KILL_SWITCH_ACTIVE.lock at the Stratex root —
  Stratex's panic_state.py resolves its default relative filenames
  against the Stratex services' WorkingDirectory (the root), not
  the state dir — composed exactly as the live summary composes
  them (kill_switch_active = the lock file exists; panic_active =
  the panic flag or the lock; the flag read fails CLOSED on a
  corrupt file, as Stratex's own reader does), so the rendered
  answer carries the HALTED line byte-identically on both paths;
- "analyze" always dispatches live; the tool's sendable surface
  stays ("status", "analyze") — the snapshot path sends nothing,
  so no mutation-shaped intent can ever take it.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from friday.proactive import stratex_watch as sw
from friday.tools.builtin import stratex_portfolio as sp
from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool


# ---------------------------------------------------------------------------
# fixture world — a synthetic Stratex state dir in the production shape
# ---------------------------------------------------------------------------

#: Production-shaped fixture (production ledger, 2026-11-17): the
#: same strategy names and the same totals Stratex's scorecard
#: serves — LEGACY-UNATTRIBUTED 3 trades / +195.71, bb_reversion
#: 6 trades / -0.65, strategy_sleeve_tsmom2_dual 1 trade / +0.00
#: (trade 470, the sleeve's breakeven first forward trade) ->
#: 10 closed trades, net +195.06, win rate 0.4 (4 wins). The
#: individual rows are synthetic, so the fixture's profit factor
#: (6.319) is a FIXTURE number — production's real rows give
#: 6.445; every other total above is production's own.
FIXTURE_FILLS: list[dict[str, Any]] = [
    {"record_type": "FILL", "strategy": "LEGACY-UNATTRIBUTED", "symbol": "BTCUSDT",
     "net_pnl": 150.0, "exit_time": 1763000001.0},
    {"record_type": "FILL", "strategy": "LEGACY-UNATTRIBUTED", "symbol": "ETHUSDT",
     "net_pnl": 80.88, "exit_time": 1763000002.0},
    {"record_type": "FILL", "strategy": "LEGACY-UNATTRIBUTED", "symbol": "SOLUSDT",
     "net_pnl": -35.17, "exit_time": 1763000003.0},
    {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
     "net_pnl": 0.50, "exit_time": 1763000010.0},
    {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
     "net_pnl": 0.35, "exit_time": 1763000011.0},
    {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
     "net_pnl": -0.50, "exit_time": 1763000012.0},
    {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
     "net_pnl": -0.50, "exit_time": 1763000013.0},
    {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
     "net_pnl": -0.25, "exit_time": 1763000014.0},
    {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
     "net_pnl": -0.25, "exit_time": 1763000015.0},
    {"record_type": "FILL", "strategy": "strategy_sleeve_tsmom2_dual", "symbol": "USDJPY",
     "net_pnl": 0.0, "exit_time": 1763000020.0},
]


#: The daemon heartbeat's combined multi-venue totals — under the NEW
#: composition these ARE the served aggregates (the premise of the
#: original pin, that they "must never leak", inverts: the frozen
#: cloud file was the leak). unrealized is total_equity - total_balance.
FIXTURE_TOTAL_BALANCE = 20560.19
FIXTURE_TOTAL_EQUITY = 20559.92
FIXTURE_UNREALIZED_PNL = -0.27
FIXTURE_OPEN_COUNT = 4

#: forward_scorecard.json's per-entrant open-position projection, in
#: the real generator's row shape (measurement/forward_scorecard.py
#: _open_positions_by_strategy: venue, symbol, side LONG/SHORT, qty,
#: entry_price, opened_ts, opened_at, strategy,
#: source="position_tags+fill_ledger"). Four open positions across
#: three entrant cards — two registered entrants plus the discovered
#: UNREGISTERED card (a position with no forward-protocol tags, the
#: trade-470-shaped USDJPY leg on OANDA): the flattening must cross
#: ALL cards, or the count diverges from the heartbeat and nothing
#: serves.
FIXTURE_SCORECARD_CARDS: list[dict[str, Any]] = [
    {
        "id": "dow_effect",
        "label": "Dow-effect daily rotation",
        "lane": "forward",
        "sleeve": False,
        "strategies": ["dow_effect"],
        "open_positions": [
            {"venue": "binance_futures", "symbol": "BTCUSDT", "side": "LONG",
             "qty": 0.01, "entry_price": 91234.5, "opened_ts": 1763300000.0,
             "opened_at": "2026-11-16T09:00:00+00:00",
             "strategy": "dow_effect", "source": "position_tags+fill_ledger"},
            {"venue": "binance_futures", "symbol": "BNBUSDT", "side": "LONG",
             "qty": 0.5, "entry_price": 912.34, "opened_ts": 1763300100.0,
             "opened_at": "2026-11-16T09:01:40+00:00",
             "strategy": "dow_effect", "source": "position_tags+fill_ledger"},
        ],
        "open_positions_count": 2,
    },
    {
        "id": "ichimoku_trend",
        "label": "Ichimoku trend",
        "lane": "forward",
        "sleeve": False,
        "strategies": ["ichimoku_trend"],
        "open_positions": [
            {"venue": "binance_futures", "symbol": "TRXUSDT", "side": "SHORT",
             "qty": 250.0, "entry_price": 0.3052, "opened_ts": 1763300200.0,
             "opened_at": "2026-11-16T09:03:20+00:00",
             "strategy": "ichimoku_trend", "source": "position_tags+fill_ledger"},
        ],
        "open_positions_count": 1,
    },
    {
        "id": "UNREGISTERED",
        "label": "Discovered (unregistered) positions",
        "lane": "discovered",
        "sleeve": False,
        "strategies": [],
        "open_positions": [
            {"venue": "oanda", "symbol": "USDJPY", "side": "LONG",
             "qty": 15.0, "entry_price": 159.691, "opened_ts": 1763300300.0,
             "opened_at": "2026-11-16T09:05:00+00:00",
             "strategy": "UNATTRIBUTED", "source": "position_tags+fill_ledger"},
        ],
        "open_positions_count": 1,
    },
]


def _expected_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """measurement.scorecard._stats, re-derived from the spec."""
    nets = [float(r.get("net_pnl") or 0.0) for r in rows]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(rows),
        "net_pnl": round(sum(nets), 2),
        "win_rate": round(len(wins) / len(rows), 4) if rows else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
    }


def _real_live_payload(
    fills: list[dict[str, Any]] | None = None,
    *,
    panic_active: bool = False,
    kill_switch_active: bool = False,
) -> dict[str, Any]:
    """The live payload as Stratex ACTUALLY composes it — NEW composition.

    The ledger scorecard is Stratex's own generator —
    Stratex/measurement/scorecard.py ``build_scorecard()`` — whose
    strategies map is seeded with the governed zero-trade registry
    entries (config_strategy.PRODUCTION_STRATEGY_REGISTRY, status
    VALIDATED / OBSERVE_ONLY) and sorted by name; on the production
    shape that puts the one-trade sleeve at index 8 of 9. The block
    shaping replicates Stratex/api/friday_supervision.py
    ``_ledger_scorecard_block()`` field-for-field.

    The daemon leg mirrors ``_compute_engine_status_summary()``
    with the STALE-STATE fix's ``_real_trading_data`` daemon branch
    (SCOPE.md §5, the coupled Stratex-side PR): balance/cash from
    the daemon heartbeat's ``total_balance``, unrealized from the
    heartbeat, position rows from forward_scorecard.json's entrant
    cards flattened in document order and translated per §5
    (position_id "{venue}:{symbol}", quantity <- qty, side kept
    LONG/SHORT, per-row unrealized OMITTED — the scorecard has no
    marks), source markers engine_source / positions_source /
    positions_as_of attached. The translation is written out here,
    independently of stratex_watch's own — a pin that imported the
    implementation's translator could not catch a translation bug.
    The summary's remaining fields mirror the same function
    (ACTIVE_STRATEGIES empty, TRADING_MODE upper-cased from config
    — NOT the daemon branch's internal mode string — and the halt
    flags as that function composes them: kill_switch_active is
    the lock file's existence, panic_active is the panic flag OR
    the lock — _real_trading_data folds the lock in). The first
    version of this pin hand-grouped only the ledger strategies —
    a model sharing the implementation's wrong assumption about
    the map — and so could not see the sleeve fall outside the
    formatter's six-line window; the supervisor review rejected
    it for exactly that.
    """
    stratex_dir = Path(__file__).resolve().parents[2] / "Stratex"
    if str(stratex_dir) not in sys.path:
        sys.path.insert(0, str(stratex_dir))
    from measurement import scorecard as _real_scorecard

    card = _real_scorecard.build_scorecard(
        list(FIXTURE_FILLS if fills is None else fills)
    )
    totals = card.get("totals") or {}
    strategies: dict[str, Any] = {}
    for name, stats in (card.get("strategies") or {}).items():
        if not isinstance(stats, dict):
            continue
        strategies[str(name)] = {
            "trades": stats.get("trades"),
            "net_pnl": stats.get("net_pnl"),
            "profit_factor": stats.get("profit_factor"),
            "win_rate": stats.get("win_rate"),
        }
    # The daemon leg (SCOPE.md §5 translation, written out here —
    # deliberately NOT imported from stratex_watch): flatten every
    # entrant card's rows in document order.
    positions: list[dict[str, Any]] = []
    for card_ in FIXTURE_SCORECARD_CARDS:
        for row in card_["open_positions"]:
            venue = str(row.get("venue") or "")
            symbol = str(row.get("symbol") or "")
            positions.append(
                {
                    "position_id": f"{venue}:{symbol}",
                    "symbol": symbol,
                    "side": str(row.get("side") or ""),
                    "quantity": row.get("qty"),
                    "entry_price": row.get("entry_price"),
                    "opened_at": row.get("opened_at"),
                    "strategy": str(row.get("strategy") or ""),
                    "venue": venue,
                }
            )
    return {
        "engine": "Stratex",
        "engine_source": "multi_venue_daemon",
        "positions_source": "forward_scorecard",
        # The live value is the scorecard's generated_at; the
        # formatter never renders it, so the pin leaves it None.
        "positions_as_of": None,
        "trading_mode": "PAPER",
        "balance": FIXTURE_TOTAL_BALANCE,
        "cash_balance": FIXTURE_TOTAL_BALANCE,
        "current_positions": positions,
        "position_count": FIXTURE_OPEN_COUNT,
        "unrealized_pnl": FIXTURE_UNREALIZED_PNL,
        "active_strategies": [],
        "panic_active": panic_active,
        "kill_switch_active": kill_switch_active,
        "ledger_scorecard": {
            "generated_at": card.get("generated_at"),
            "source": card.get("source"),
            "total_fills": card.get("total_fills"),
            "totals": {
                "trades": totals.get("trades"),
                "net_pnl": totals.get("net_pnl"),
                "win_rate": totals.get("win_rate"),
                "profit_factor": totals.get("profit_factor"),
                "expectancy_net_per_trade": totals.get("expectancy_net_per_trade"),
                "max_drawdown": totals.get("max_drawdown"),
                "fees": totals.get("fees"),
            },
            "strategies": strategies,
            "reset_boundaries": len(card.get("reset_boundaries") or []),
        },
    }


class _World:
    """A synthetic Stratex checkout + state dir, wired via the same env
    overrides production resolution honours."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self.root = tmp_path / "Stratex"
        self.state = self.root / "state"
        self.state.mkdir(parents=True)
        monkeypatch.setenv("FRIDAY_STRATEX_STATE_DIR", str(self.root))
        monkeypatch.setenv("STRATEX_STATE_DIR", str(self.state))

    def write_heartbeat(self, *, age_s: float = 5.0, status: str = "RUNNING",
                        epoch: bool = True,
                        total_balance: Any = FIXTURE_TOTAL_BALANCE,
                        unrealized_pnl: Any = FIXTURE_UNREALIZED_PNL,
                        open_positions: Any = FIXTURE_OPEN_COUNT) -> None:
        ts = time.time() - age_s
        payload: dict[str, Any] = {
            "status": status,
            "pid": 2690391,
            "scan_interval_seconds": 15.0,
            # The daemon's combined multi-venue totals — under the
            # NEW composition these ARE the served aggregates (the
            # heartbeat is both the freshness pulse and the figure
            # source). realized_pnl is the daemon's own running
            # figure; it is NOT served (the ledger block comes from
            # the fill ledger).
            "total_balance": total_balance,
            "total_equity": FIXTURE_TOTAL_EQUITY,
            "unrealized_pnl": unrealized_pnl,
            "open_positions": open_positions,
            "realized_pnl": 134.79416134,
            "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        if epoch:
            payload["updated_at"] = ts
        (self.state / "daemon_heartbeat.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def write_scorecard(self, *, age_s: float = 5.0,
                        cards: list[dict[str, Any]] | None = None) -> str:
        """forward_scorecard.json in the real generator's document
        shape. Returns the generated_at written. account_equity_usd
        is the scorecard's snapshot-window basis (14,990.55 —
        deliberately DIFFERENT from the heartbeat's combined
        total_balance): it must never become the served balance."""
        generated = datetime.fromtimestamp(
            time.time() - age_s, tz=timezone.utc
        ).isoformat()
        payload = {
            "generated_at": generated,
            "source": (
                "state/fill_ledger.jsonl + state/equity_snapshots.jsonl "
                "+ state/position_tags.jsonl + live probe (if supplied)"
            ),
            "global_forward_start": "2026-11-15T05:59:49+00:00",
            "account_equity_usd": 14990.55,
            "account_equity_source": "snapshot",
            "entrants": FIXTURE_SCORECARD_CARDS if cards is None else cards,
            "daily_breaker": {},
            "reconciliation": [],
            "active_measurement_alerts": {},
        }
        (self.state / "forward_scorecard.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return generated

    def write_poison_cloud(self) -> None:
        """The retired cloud_portfolio_state.json, frozen at its
        real 2026-11-08 production contents PLUS a poison position
        the frozen file never had: if any code path still reads
        this file, the served balance (10792.8) or the POISONUSDT
        row gives it away."""
        payload = {
            "balance": 10792.8,
            "updated_at": "2026-11-08T11:11:21.617205Z",
            "positions": {
                "POISONUSDT": {
                    "side": "LONG",
                    "entry_price": 1.0,
                    "unrealized_pnl": 999.0,
                }
            },
        }
        (self.state / "cloud_portfolio_state.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def write_fills(self, rows: list[dict[str, Any]] | None = None) -> None:
        rows = FIXTURE_FILLS if rows is None else rows
        (self.state / "fill_ledger.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
        )

    def write_panic(self, payload: Any) -> None:
        """The panic flag — at the Stratex ROOT (panic_state.py's
        default relative filename resolves against the Stratex
        services' WorkingDirectory), never in the state dir. A str
        payload is written raw (corrupt-file cases)."""
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (self.root / "panic_state.json").write_text(text, encoding="utf-8")

    def write_kill_lock(self) -> None:
        """The kill-switch lock — existence is the signal; content is
        the marker JSON panic_state.engage_order_block writes."""
        (self.root / "KILL_SWITCH_ACTIVE.lock").write_text(
            json.dumps({"kill_switch_active": True, "actor": "test"}),
            encoding="utf-8",
        )

    def write_all(self, **heartbeat_kw: Any) -> None:
        self.write_heartbeat(**heartbeat_kw)
        self.write_scorecard()
        self.write_fills()


# ---------------------------------------------------------------------------
# fake fleet clients
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, result: dict[str, Any]):
        self.status = "success"
        self.result = result
        self.error = None
        self.task_id = "task_frd021"
        self.execution_time_ms = 9688


class _RecordingFleetClient:
    """Records every dispatch; returns the payload it was given."""

    def __init__(self, result: dict[str, Any]):
        self._result = result
        self.envelopes: list[Any] = []

    async def dispatch_task(self, envelope: Any) -> _FakeResult:
        self.envelopes.append(envelope)
        return _FakeResult(self._result)


#: A live payload whose figures are visibly WRONG vs the fixture state —
#: if a snapshot test ever dispatches, the content gives it away.
_MARKER_PAYLOAD: dict[str, Any] = {
    "engine": "Stratex",
    "trading_mode": "PAPER",
    "balance": 1.0,
    "cash_balance": 1.0,
    "current_positions": [],
    "active_strategies": [],
}


# ---------------------------------------------------------------------------
# the snapshot composer
# ---------------------------------------------------------------------------


class TestReadStatusSnapshot:
    def test_fresh_world_composes_the_served_figures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(age_s=5.0)

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert 0.0 <= snap.age_seconds <= 60.0
        # Aggregates from the daemon heartbeat (the new composition).
        assert snap.data["balance"] == FIXTURE_TOTAL_BALANCE
        assert snap.data["cash_balance"] == FIXTURE_TOTAL_BALANCE
        assert snap.data["unrealized_pnl"] == FIXTURE_UNREALIZED_PNL
        assert snap.data["position_count"] == FIXTURE_OPEN_COUNT
        assert len(snap.data["current_positions"]) == FIXTURE_OPEN_COUNT
        # Source markers label the daemon basis.
        assert snap.data["engine_source"] == "multi_venue_daemon"
        assert snap.data["positions_source"] == "forward_scorecard"
        assert snap.data["positions_as_of"]
        # Neither the frozen file's balance nor the scorecard's
        # snapshot-window equity basis may surface as the balance.
        assert snap.data["balance"] != 10792.8
        assert snap.data["balance"] != 14990.55
        totals = snap.data["ledger_scorecard"]["totals"]
        assert totals == {"trades": 10, "net_pnl": 195.06,
                          "win_rate": 0.4, "profit_factor": totals["profit_factor"]}
        assert totals["profit_factor"] == _expected_stats(FIXTURE_FILLS)["profit_factor"]

    def test_position_rows_are_translated_from_the_scorecard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all()

        snap = sw.read_status_snapshot()

        assert snap is not None
        rows = snap.data["current_positions"]
        # Flattened across ALL entrant cards, in document order —
        # including the discovered UNREGISTERED card's USDJPY row.
        assert [r["symbol"] for r in rows] == [
            "BTCUSDT", "BNBUSDT", "TRXUSDT", "USDJPY",
        ]
        assert rows[0] == {
            "position_id": "binance_futures:BTCUSDT",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "quantity": 0.01,
            "entry_price": 91234.5,
            "opened_at": "2026-11-16T09:00:00+00:00",
            "strategy": "dow_effect",
            "venue": "binance_futures",
        }
        assert rows[3]["position_id"] == "oanda:USDJPY"
        assert rows[3]["strategy"] == "UNATTRIBUTED"
        for row in rows:
            # The scorecard carries no marks and no stops: omitted,
            # never zero-filled or fabricated.
            assert "unrealized_pnl" not in row
            assert "stop_loss" not in row
            assert "take_profit" not in row
        # The headline unrealized is the heartbeat's, never a row sum.
        assert snap.data["unrealized_pnl"] == FIXTURE_UNREALIZED_PNL

    def test_poisoned_cloud_state_is_never_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # SCOPE.md §10 poison test: the frozen file sits in the state
        # dir with a different balance and a poison position; the
        # snapshot must compose from heartbeat + scorecard regardless.
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        world.write_poison_cloud()

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["balance"] == FIXTURE_TOTAL_BALANCE
        assert snap.data["balance"] != 10792.8
        symbols = [r["symbol"] for r in snap.data["current_positions"]]
        assert "POISONUSDT" not in symbols
        assert len(symbols) == FIXTURE_OPEN_COUNT
        assert snap.data["unrealized_pnl"] == FIXTURE_UNREALIZED_PNL

    def test_iso_timestamp_without_epoch_is_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(age_s=5.0, epoch=False)

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.age_seconds <= 60.0

    def test_stale_heartbeat_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(age_s=3600.0)

        assert sw.read_status_snapshot() is None

    def test_daemon_not_running_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(status="STOPPED")

        assert sw.read_status_snapshot() is None

    def test_missing_heartbeat_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_scorecard()
        world.write_fills()

        assert sw.read_status_snapshot() is None

    def test_missing_scorecard_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_fills()

        assert sw.read_status_snapshot() is None

    def test_stale_scorecard_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Fresh heartbeat, scorecard older than the 30 min bound:
        # the position list cannot be proven — nothing serves.
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_scorecard(age_s=3600.0)
        world.write_fills()

        assert sw.read_status_snapshot() is None

    def test_count_divergence_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Heartbeat says 5 open, scorecard projects 4 rows (and the
        # mirror image): a partial list is never served.
        world = _World(tmp_path, monkeypatch)
        world.write_all(open_positions=5)
        assert sw.read_status_snapshot() is None

        world.write_all(open_positions=3)
        assert sw.read_status_snapshot() is None

    def test_non_numeric_balance_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(total_balance="not-a-number")

        assert sw.read_status_snapshot() is None

    def test_missing_unrealized_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(unrealized_pnl=None)

        assert sw.read_status_snapshot() is None

    def test_empty_ledger_is_a_valid_zero_trade_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_scorecard()
        # no fill ledger file at all

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["ledger_scorecard"]["totals"]["trades"] == 0

    def test_empty_book_is_a_valid_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Heartbeat count 0 with zero scorecard rows AGREE — an
        # honestly empty book serves (it is divergence, not
        # emptiness, that blocks).
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat(open_positions=0)
        world.write_scorecard(cards=[])
        world.write_fills()

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["current_positions"] == []
        assert snap.data["position_count"] == 0


# ---------------------------------------------------------------------------
# the halt state (TASK-FRD-021 follow-up) — panic_state.json +
# KILL_SWITCH_ACTIVE.lock at the Stratex root, composed with the
# live summary's semantics
# ---------------------------------------------------------------------------


class TestReadStatusSnapshotHaltState:
    def test_no_halt_files_means_not_halted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all()

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["panic_active"] is False
        assert snap.data["kill_switch_active"] is False

    def test_unified_writer_schema_trips_panic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        # panic_state.write_panic_state's unified schema (both keys).
        world.write_panic(
            {"active": True, "panic_active": True, "actor": "owner",
             "reason": "manual halt"}
        )

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["panic_active"] is True
        assert snap.data["kill_switch_active"] is False

    def test_legacy_single_key_schemas_trip_panic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The pre-unification writers disagreed on the schema (the
        # reason panic_state.py exists): /api/panic wrote only
        # "active", the FRIDAY supervision panic only "panic_active".
        # Stratex's reader accepts either key; the snapshot must too.
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        for payload in ({"active": True}, {"panic_active": True}):
            world.write_panic(payload)

            snap = sw.read_status_snapshot()

            assert snap is not None
            assert snap.data["panic_active"] is True, payload
            assert snap.data["kill_switch_active"] is False

    def test_released_panic_file_is_not_halted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        world.write_panic(
            {"active": False, "panic_active": False, "actor": "owner",
             "released_at": "2026-11-17T00:00:00+00:00"}
        )

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["panic_active"] is False
        assert snap.data["kill_switch_active"] is False

    def test_corrupt_panic_file_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # panic_state.read_panic_state: a flag file that exists but
        # cannot be parsed means panic ASSUMED — a corrupt halt flag
        # must never read as "safe". The snapshot mirrors it.
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        for raw in ("{not json", "[1, 2]", "true"):
            world.write_panic(raw)

            snap = sw.read_status_snapshot()

            assert snap is not None
            assert snap.data["panic_active"] is True, raw
            assert snap.data["kill_switch_active"] is False

    def test_non_utf8_panic_file_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F1 (supervisor review of PR #877): bytes that are not valid
        # UTF-8 make read_text raise UnicodeDecodeError — a ValueError,
        # not an OSError — out of the flag read. Stratex's reader
        # catches Exception around open+load and fails closed; the
        # snapshot must fail closed in-function too: the flag exists,
        # so panic is assumed and the snapshot still serves.
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        (world.root / "panic_state.json").write_bytes(
            b'{"active": true, "actor": "\xff\xfe"}'
        )

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["panic_active"] is True
        assert snap.data["kill_switch_active"] is False

    def test_kill_lock_trips_both_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The live composition folds the lock into panic_active
        # (_real_trading_data: is_panic_active() OR
        # is_kill_switch_locked()) and reports the lock itself as
        # kill_switch_active; the lock's content is irrelevant —
        # existence is the signal.
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        world.write_kill_lock()

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["panic_active"] is True
        assert snap.data["kill_switch_active"] is True

    def test_halt_files_in_state_dir_do_not_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The files live at the Stratex ROOT (the services'
        # WorkingDirectory). Namesakes inside the state dir are not
        # the flag — reading them would invent a halt Stratex does
        # not have (and miss the real one).
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        (world.state / "panic_state.json").write_text(
            json.dumps({"active": True, "panic_active": True}),
            encoding="utf-8",
        )
        (world.state / "KILL_SWITCH_ACTIVE.lock").write_text(
            "{}", encoding="utf-8"
        )

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["panic_active"] is False
        assert snap.data["kill_switch_active"] is False


# ---------------------------------------------------------------------------
# the tool: snapshot serve, fallback, and the read-only surface
# ---------------------------------------------------------------------------


class TestToolSnapshotServe:
    def test_snapshot_hit_serves_without_any_execute_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        client = _RecordingFleetClient(_MARKER_PAYLOAD)
        tool = StratexPortfolioTool(fleet_client=client)

        result = tool.execute(question="how is my portfolio", kind="portfolio")

        assert client.envelopes == [], "snapshot hit must not dispatch"
        assert not result.is_error
        assert "Balance: 20,560.19" in result.content
        assert "Open positions: 4" in result.content
        assert "LONG BTCUSDT @ 91234.5" in result.content
        assert "SHORT TRXUSDT @ 0.3052" in result.content
        assert "LONG USDJPY @ 159.691" in result.content
        assert "Unrealized P&L: -0.27" in result.content
        assert "10 closed trade(s)" in result.content
        assert "net P&L +195.06" in result.content
        # Neither the frozen file's balance nor the marker payload's.
        assert "10,792.80" not in result.content
        assert "1.00" not in result.content  # the marker payload never rendered
        meta = (result.metadata or {}).get("stratex") or {}
        assert meta.get("source") == "stratex_watch_snapshot"
        assert meta.get("balance") == FIXTURE_TOTAL_BALANCE
        assert meta.get("position_count") == FIXTURE_OPEN_COUNT
        assert 0.0 <= float(meta.get("snapshot_age_seconds")) <= 60.0

    def test_snapshot_figures_byte_match_live_figures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Receipt-exactness: same state, two sources — the figure lines
        of the composed answers are byte-identical. The live side is
        Stratex's REAL composition (the actual build_scorecard()
        output, registry-seeded map and all), not a hand-built model
        of it. The ONLY tolerated difference is the header's mode
        word: the live summary carries Stratex's config TRADING_MODE
        ("PAPER"), for which FRIDAY has no truthful local source, so
        the snapshot answer takes the formatter's own default
        ("demo"). No figure differs."""
        world = _World(tmp_path, monkeypatch)
        world.write_all()

        live_payload = _real_live_payload()
        # The production composition this pin exists to hold: the real
        # scorecard map carries the governed zero-trade registry
        # entries, and the one-trade sleeve sorts BEYOND the
        # formatter's six-line window — the shape whose live render
        # silently dropped the sleeve line in the rejected version.
        served_names = list(live_payload["ledger_scorecard"]["strategies"])
        assert served_names.index("strategy_sleeve_tsmom2_dual") >= 6, (
            f"real scorecard map no longer exercises the window: {served_names}"
        )
        assert live_payload["ledger_scorecard"]["totals"]["win_rate"] == 0.4

        snap_client = _RecordingFleetClient(_MARKER_PAYLOAD)
        snap_result = StratexPortfolioTool(fleet_client=snap_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert snap_client.envelopes == []

        # Same figure files; only the freshness pulse is stale, so the
        # tool takes the live path and renders the execute payload
        # Stratex builds from this identical state.
        world.write_heartbeat(age_s=3600.0)
        live_client = _RecordingFleetClient(live_payload)
        live_result = StratexPortfolioTool(fleet_client=live_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert len(live_client.envelopes) == 1

        for literal in (
            "Balance: 20,560.19",
            "Open positions: 4",
            "LONG BTCUSDT @ 91234.5",
            "SHORT TRXUSDT @ 0.3052",
            "Unrealized P&L: -0.27",
            "10 closed trade(s)",
            "net P&L +195.06",
            "win rate 40%",
            "strategy_sleeve_tsmom2_dual: 1 trade(s), net +0.00",
        ):
            assert literal in snap_result.content
            assert literal in live_result.content

        snap_lines = snap_result.content.splitlines()
        live_lines = live_result.content.splitlines()
        assert snap_lines[1:] == live_lines[1:], (
            "figure lines differ:\n"
            + "\n".join(
                f"  snap={a!r} live={b!r}"
                for a, b in zip(snap_lines, live_lines)
                if a != b
            )
        )
        assert snap_lines[0].replace("demo", "PAPER") == live_lines[0]

    def test_snapshot_figures_byte_match_live_figures_when_panicked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Receipt-exactness in the HALTED state (TASK-FRD-021
        follow-up): with the panic flag set at the Stratex root, the
        snapshot render and the live render both carry the HALTED
        line and stay byte-identical below the header. The live side
        is the real composition with the flags as
        _compute_engine_status_summary sets them (panic flag set,
        no lock: panic_active=True, kill_switch_active=False). The
        sleeve line stays in BOTH renders — the window fix and the
        halt wiring compose."""
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        world.write_panic(
            {"active": True, "panic_active": True, "actor": "owner",
             "reason": "manual halt"}
        )

        live_payload = _real_live_payload(panic_active=True)
        assert live_payload["ledger_scorecard"]["totals"]["win_rate"] == 0.4

        snap_client = _RecordingFleetClient(_MARKER_PAYLOAD)
        snap_result = StratexPortfolioTool(fleet_client=snap_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert snap_client.envelopes == [], "halted snapshot must still serve locally"

        world.write_heartbeat(age_s=3600.0)
        live_client = _RecordingFleetClient(live_payload)
        live_result = StratexPortfolioTool(fleet_client=live_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert len(live_client.envelopes) == 1

        for literal in (
            "Balance: 20,560.19",
            "Open positions: 4",
            "10 closed trade(s)",
            "win rate 40%",
            "strategy_sleeve_tsmom2_dual: 1 trade(s), net +0.00",
            "- Trading HALTED: Stratex's panic/kill switch is active.",
        ):
            assert literal in snap_result.content
            assert literal in live_result.content

        snap_lines = snap_result.content.splitlines()
        live_lines = live_result.content.splitlines()
        assert snap_lines[1:] == live_lines[1:], (
            "figure lines differ:\n"
            + "\n".join(
                f"  snap={a!r} live={b!r}"
                for a, b in zip(snap_lines, live_lines)
                if a != b
            )
        )
        assert snap_lines[0].replace("demo", "PAPER") == live_lines[0]

    def test_snapshot_figures_byte_match_live_figures_when_kill_locked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The kill-switch lock variant: the live composition folds
        the lock into panic_active AND reports kill_switch_active,
        so both flags are True on both sides and the HALTED line
        renders identically."""
        world = _World(tmp_path, monkeypatch)
        world.write_all()
        world.write_kill_lock()

        live_payload = _real_live_payload(
            panic_active=True, kill_switch_active=True
        )

        snap_client = _RecordingFleetClient(_MARKER_PAYLOAD)
        snap_result = StratexPortfolioTool(fleet_client=snap_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert snap_client.envelopes == []

        world.write_heartbeat(age_s=3600.0)
        live_client = _RecordingFleetClient(live_payload)
        live_result = StratexPortfolioTool(fleet_client=live_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert len(live_client.envelopes) == 1

        halted = "- Trading HALTED: Stratex's panic/kill switch is active."
        assert halted in snap_result.content
        assert halted in live_result.content
        assert "strategy_sleeve_tsmom2_dual: 1 trade(s), net +0.00" in snap_result.content
        assert "strategy_sleeve_tsmom2_dual: 1 trade(s), net +0.00" in live_result.content
        snap_lines = snap_result.content.splitlines()
        live_lines = live_result.content.splitlines()
        assert snap_lines[1:] == live_lines[1:]
        assert snap_lines[0].replace("demo", "PAPER") == live_lines[0]

    def test_stale_snapshot_falls_back_to_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(age_s=3600.0)
        client = _RecordingFleetClient(_real_live_payload())
        tool = StratexPortfolioTool(fleet_client=client)

        result = tool.execute(question="how is my portfolio", kind="portfolio")

        assert len(client.envelopes) == 1
        assert client.envelopes[0].action == "status"
        assert not result.is_error
        assert "Balance: 20,560.19" in result.content
        meta = (result.metadata or {}).get("stratex") or {}
        assert meta.get("source") is None  # live serve carries no snapshot mark

    def test_stale_scorecard_falls_back_to_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spec §10 item 5, second half: a stale scorecard withholds
        the snapshot, the tool dispatches live, and the live answer
        carries the SAME daemon figures a fresh snapshot serves."""
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_scorecard(age_s=3600.0)
        world.write_fills()
        client = _RecordingFleetClient(_real_live_payload())
        tool = StratexPortfolioTool(fleet_client=client)

        result = tool.execute(question="how is my portfolio", kind="portfolio")

        assert len(client.envelopes) == 1
        assert client.envelopes[0].action == "status"
        assert not result.is_error
        assert "Balance: 20,560.19" in result.content
        assert "Open positions: 4" in result.content

    def test_missing_snapshot_falls_back_to_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_scorecard()
        world.write_fills()
        # no heartbeat file at all
        client = _RecordingFleetClient(_real_live_payload())
        tool = StratexPortfolioTool(fleet_client=client)

        result = tool.execute(question="any open positions", kind="portfolio")

        assert len(client.envelopes) == 1
        assert not result.is_error
        assert "Balance: 20,560.19" in result.content

    def test_analysis_always_dispatches_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all()  # fresh snapshot exists — analysis must ignore it
        client = _RecordingFleetClient(
            {"signals": [], "signal_count": 0, "symbols_analyzed": []}
        )
        tool = StratexPortfolioTool(fleet_client=client)

        result = tool.execute(question="market signals", kind="analysis")

        assert len(client.envelopes) == 1
        assert client.envelopes[0].action == "analyze"
        assert "Stratex market analysis:" in result.content

    def test_sendable_surface_stays_read_only(self) -> None:
        assert sp._ALLOWED_ACTIONS == ("status", "analyze")
        tool = StratexPortfolioTool(fleet_client=_RecordingFleetClient({}))
        with pytest.raises(AssertionError):
            tool._dispatch("panic", "close everything")


# ---------------------------------------------------------------------------
# the formatter's per-strategy window (supervisor-review regression)
# ---------------------------------------------------------------------------


class TestFormatPortfolioStrategyWindow:
    """The six-line per-strategy window counts strategies that
    actually traded. Stratex's real scorecard map interleaves
    governed zero-trade registry entries; if the window is sliced
    before the trades>0 filter, that padding consumes the window
    and a trading strategy beyond it vanishes from the render —
    on the production map the one-trade sleeve sat at index 8 and
    the live render silently omitted its (truthful) line while
    the snapshot's ledger-only map showed it."""

    @staticmethod
    def _payload(strategies: dict[str, Any]) -> dict[str, Any]:
        return {
            "engine": "Stratex",
            "trading_mode": "PAPER",
            "balance": FIXTURE_TOTAL_BALANCE,
            "cash_balance": FIXTURE_TOTAL_BALANCE,
            "current_positions": [],
            "unrealized_pnl": 0.0,
            "active_strategies": [],
            "ledger_scorecard": {
                "totals": {"trades": 10, "net_pnl": 195.06,
                           "win_rate": 0.4, "profit_factor": 6.319},
                "strategies": strategies,
            },
        }

    def test_zero_trade_padding_cannot_window_hide_a_trading_strategy(self) -> None:
        zero = {"trades": 0, "net_pnl": 0.0, "win_rate": 0.0, "profit_factor": None}
        # The production map shape: >6 entries, governed zero-trade
        # entries ahead of a real one-trade strategy at the tail.
        live_shaped = {
            "LEGACY-UNATTRIBUTED": {"trades": 3, "net_pnl": 195.71,
                                    "win_rate": 0.6667, "profit_factor": 6.564},
            "adx_ema": dict(zero),
            "bb_reversion": {"trades": 6, "net_pnl": -0.65,
                             "win_rate": 0.3333, "profit_factor": 0.567},
            "dow_effect": dict(zero),
            "fx_mr_v4": dict(zero),
            "ichimoku_trend": dict(zero),
            "sleeve_shock_breakout": dict(zero),
            "sleeve_tsmom2_dual": dict(zero),
            "strategy_sleeve_tsmom2_dual": {"trades": 1, "net_pnl": 0.0,
                                            "win_rate": 0.0, "profit_factor": None},
        }
        snapshot_shaped = {
            name: live_shaped[name]
            for name in (
                "LEGACY-UNATTRIBUTED",
                "bb_reversion",
                "strategy_sleeve_tsmom2_dual",
            )
        }

        live_render = sp._format_portfolio(self._payload(live_shaped))
        snap_render = sp._format_portfolio(self._payload(snapshot_shaped))

        assert "strategy_sleeve_tsmom2_dual: 1 trade(s), net +0.00" in live_render
        assert live_render == snap_render
