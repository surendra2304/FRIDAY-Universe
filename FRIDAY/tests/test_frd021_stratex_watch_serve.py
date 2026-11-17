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
  balance 10,792.80 / 0 open / 10 closed / net +195.06);
- a stale heartbeat (>60 s), a missing heartbeat, a missing cloud
  state, a non-RUNNING daemon, or a non-numeric balance all fall
  back to the live dispatch;
- "analyze" always dispatches live; the tool's sendable surface
  stays ("status", "analyze") — the snapshot path sends nothing,
  so no mutation-shaped intent can ever take it;
- the heartbeat is a freshness pulse ONLY: its own figures (the
  daemon's multi-venue view) never leak into the answer.
"""

from __future__ import annotations

import json
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

#: Keeper-baseline shape (production, 2026-11-17): 10 fills netting
#: +195.0598 -> served as 10 closed trades, net +195.06.
FIXTURE_FILLS: list[dict[str, Any]] = [
    {"record_type": "FILL", "strategy": "legacy", "symbol": "BTCUSDT",
     "net_pnl": 100.0, "exit_time": 1763000001.0},
    {"record_type": "FILL", "strategy": "legacy", "symbol": "ETHUSDT",
     "net_pnl": 60.0, "exit_time": 1763000002.0},
    {"record_type": "FILL", "strategy": "legacy", "symbol": "SOLUSDT",
     "net_pnl": 35.7066, "exit_time": 1763000003.0},
    *[
        {"record_type": "FILL", "strategy": "bb_reversion", "symbol": "XRPUSDT",
         "net_pnl": -0.1078, "exit_time": 1763000010.0 + i}
        for i in range(6)
    ],
    {"record_type": "FILL", "strategy": "stage_c_sleeve", "symbol": "USDJPY",
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


def _live_payload() -> dict[str, Any]:
    """Stratex's execute status summary as built from the fixture state
    (friday_supervision._compute_engine_status_summary shape)."""
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in FIXTURE_FILLS:
        by_strategy.setdefault(str(row.get("strategy") or "UNATTRIBUTED"), []).append(row)
    return {
        "engine": "Stratex",
        "trading_mode": "PAPER",
        "balance": 10792.8,
        "cash_balance": 10792.8,
        "current_positions": [],
        "unrealized_pnl": 0.0,
        "active_strategies": [],
        "ledger_scorecard": {
            "totals": _expected_stats(FIXTURE_FILLS),
            "strategies": {
                name: _expected_stats(rows)
                for name, rows in sorted(by_strategy.items())
            },
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
                          "win_rate": 0.3, "profit_factor": totals["profit_factor"]}
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
        of the composed answers are byte-identical. The ONLY tolerated
        difference is the header's mode word: the live summary carries
        Stratex's config TRADING_MODE ("PAPER"), for which FRIDAY has
        no truthful local source, so the snapshot answer takes the
        formatter's own default ("demo"). No figure differs."""
        world = _World(tmp_path, monkeypatch)
        world.write_all()

        snap_client = _RecordingFleetClient(_MARKER_PAYLOAD)
        snap_result = StratexPortfolioTool(fleet_client=snap_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert snap_client.envelopes == []

        # Same figure files; only the freshness pulse is stale, so the
        # tool takes the live path and renders the execute payload
        # Stratex builds from this identical state.
        world.write_heartbeat(age_s=3600.0)
        live_client = _RecordingFleetClient(_live_payload())
        live_result = StratexPortfolioTool(fleet_client=live_client).execute(
            question="how is my portfolio", kind="portfolio"
        )
        assert len(live_client.envelopes) == 1

        for literal in (
            "Balance: 10,792.80",
            "Open positions: none",
            "10 closed trade(s)",
            "net P&L +195.06",
            "win rate 30%",
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

    def test_stale_snapshot_falls_back_to_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _World(tmp_path, monkeypatch)
        world.write_all(age_s=3600.0)
        client = _RecordingFleetClient(_live_payload())
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
        client = _RecordingFleetClient(_live_payload())
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
