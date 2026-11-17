"""TASK-FRD-021: read-only Stratex status served from FRIDAY's stratex_watch snapshot.

Stratex's /v1/task/execute status path does 0-7 ms of its own work (the
FRD-011 keeper snapshot) but the round trip episodically walls 1-10 s on
in-process contention inside Stratex's swapped Werkzeug process (FRD-005
re-run #8: ~9.7 s of the 20.20 s delegation turn). FRIDAY therefore
answers read-only portfolio/status questions from the Stratex state
files its PRO-001 watch family already reads — cloud_portfolio_state
(balance/positions, the exact file the engine's served figures load
from) + fill_ledger.jsonl scored with measurement.scorecard's
arithmetic — gated on the daemon heartbeat's freshness (60 s,
Stratex's own telemetry bound). A missing/stale/unreadable snapshot
falls back to the live dispatch, unchanged.

Rules pinned here:
- a fresh snapshot serves WITHOUT any execute round trip;
- receipt-exactness: snapshot-served figures byte-match the figures
  the live path serves from the same state (keeper baseline shape:
  balance 10,792.80 / 0 open / 10 closed / net +195.06 / win rate
  40%). The pin's live side is Stratex's REAL composition — the
  actual measurement.scorecard.build_scorecard() output, whose
  strategies map carries the governed zero-trade registry entries
  and puts the one-trade sleeve beyond the formatter's six-line
  window — never a hand-grouped model of it (the first version's
  hand-built payload shared the implementation's wrong assumption
  and the supervisor review rejected it);
- the formatter's per-strategy window counts strategies that
  actually traded: zero-trade padding can never window-hide a
  trading strategy from either render;
- a stale heartbeat (>60 s), a missing heartbeat, a missing cloud
  state, a non-RUNNING daemon, or a non-numeric balance all fall
  back to the live dispatch;
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
  so no mutation-shaped intent can ever take it;
- the heartbeat is a freshness pulse ONLY: its own figures (the
  daemon's multi-venue view) never leak into the answer.
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
    """The live payload as Stratex ACTUALLY composes it from the fills.

    The scorecard is Stratex's own generator —
    Stratex/measurement/scorecard.py ``build_scorecard()`` — whose
    strategies map is seeded with the governed zero-trade registry
    entries (config_strategy.PRODUCTION_STRATEGY_REGISTRY, status
    VALIDATED / OBSERVE_ONLY) and sorted by name; on the production
    shape that puts the one-trade sleeve at index 8 of 9. The block
    shaping replicates Stratex/api/friday_supervision.py
    ``_ledger_scorecard_block()`` field-for-field, and the
    surrounding fields mirror ``_compute_engine_status_summary()``
    in the same file (balance/cash from the engine's cloud state,
    ACTIVE_STRATEGIES empty, TRADING_MODE upper-cased, and the
    halt flags as that function composes them: kill_switch_active
    is the lock file's existence, panic_active is the panic flag
    OR the lock — _real_trading_data folds the lock in). The first
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
    return {
        "engine": "Stratex",
        "trading_mode": "PAPER",
        "balance": 10792.8,
        "cash_balance": 10792.8,
        "current_positions": [],
        "unrealized_pnl": 0.0,
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
                        epoch: bool = True) -> None:
        ts = time.time() - age_s
        payload: dict[str, Any] = {
            "status": status,
            "pid": 2690391,
            "scan_interval_seconds": 15.0,
            # The daemon's OWN multi-venue figures — deliberately very
            # different from the served figures; they must never leak
            # into a snapshot answer (pulse only).
            "total_balance": 20560.19,
            "total_equity": 20559.92,
            "open_positions": 4,
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

    def write_cloud(self, *, balance: Any = 10792.8,
                    positions: dict[str, Any] | None = None) -> None:
        payload = {
            "balance": balance,
            "updated_at": "2026-11-08T11:11:21.617205Z",
            "positions": positions if positions is not None else {},
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
        self.write_cloud()
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
        assert snap.data["balance"] == 10792.8
        assert snap.data["current_positions"] == []
        totals = snap.data["ledger_scorecard"]["totals"]
        assert totals == {"trades": 10, "net_pnl": 195.06,
                          "win_rate": 0.4, "profit_factor": totals["profit_factor"]}
        assert totals["profit_factor"] == _expected_stats(FIXTURE_FILLS)["profit_factor"]
        # The heartbeat's own figures are a pulse, never a source.
        assert snap.data["balance"] != 20560.19

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
        world.write_cloud()
        world.write_fills()

        assert sw.read_status_snapshot() is None

    def test_missing_cloud_state_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_fills()

        assert sw.read_status_snapshot() is None

    def test_non_numeric_balance_is_not_served(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_cloud(balance="not-a-number")
        world.write_fills()

        assert sw.read_status_snapshot() is None

    def test_empty_ledger_is_a_valid_zero_trade_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_cloud()
        # no fill ledger file at all

        snap = sw.read_status_snapshot()

        assert snap is not None
        assert snap.data["ledger_scorecard"]["totals"]["trades"] == 0

    def test_positions_carry_their_symbol_and_unrealized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_heartbeat()
        world.write_cloud(
            positions={
                "TRXUSDT": {
                    "side": "SHORT",
                    "entry_price": 0.3052,
                    "unrealized_pnl": -0.27,
                }
            }
        )
        world.write_fills()

        snap = sw.read_status_snapshot()

        assert snap is not None
        (pos,) = snap.data["current_positions"]
        assert pos["symbol"] == "TRXUSDT"
        assert snap.data["unrealized_pnl"] == -0.27


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
        assert "Balance: 10,792.80" in result.content
        assert "Open positions: none" in result.content
        assert "10 closed trade(s)" in result.content
        assert "net P&L +195.06" in result.content
        assert "1.00" not in result.content  # the marker payload never rendered
        meta = (result.metadata or {}).get("stratex") or {}
        assert meta.get("source") == "stratex_watch_snapshot"
        assert meta.get("balance") == 10792.8
        assert meta.get("position_count") == 0
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
            "Balance: 10,792.80",
            "Open positions: none",
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
            "Balance: 10,792.80",
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
        assert "Balance: 10,792.80" in result.content
        meta = (result.metadata or {}).get("stratex") or {}
        assert meta.get("source") is None  # live serve carries no snapshot mark

    def test_missing_snapshot_falls_back_to_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_cloud()
        world.write_fills()
        # no heartbeat file at all
        client = _RecordingFleetClient(_real_live_payload())
        tool = StratexPortfolioTool(fleet_client=client)

        result = tool.execute(question="any open positions", kind="portfolio")

        assert len(client.envelopes) == 1
        assert not result.is_error
        assert "Balance: 10,792.80" in result.content

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
            "balance": 10792.8,
            "cash_balance": 10792.8,
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
