"""
TASK (stale portfolio-state fix) — the daemon-book composition.

Stratex's supervision surfaces used to compose "the portfolio" from
state/cloud_portfolio_state.json — written only by the retired MT5
cTrader engine, frozen 2026-11-08 (balance 10792.8, zero positions) —
while the multi-venue daemon held the live book. These tests pin the
re-based composition (daemon_book):

* aggregates (balance / count / headline unrealized) come from
  state/daemon_heartbeat.json, gated on freshness + RUNNING + live pid;
* position rows come from state/forward_scorecard.json, flattened
  across ALL entrant cards (including UNREGISTERED), with per-row
  unrealized ABSENT — the scorecard has no marks, so none is invented;
* a stale heartbeat yields an explicit daemon-unavailable payload,
  never the cloud file; a stale scorecard withholds the row list but
  still serves aggregates;
* /api/positions serves the scorecard projection in the legacy row
  shape for OPEN, and the telemetry store only for CLOSED;
* /api/status's positions leg serves the same projection.
"""

import datetime
import json
import os

import pytest

import daemon_book  # noqa: F401  (import proves the shared module resolves)
import dashboard
from api import friday_supervision as sup

HEARTBEAT = {
    "status": "RUNNING",
    "timestamp": "2026-11-17T10:00:00Z",
    "total_balance": 20552.55,
    "total_equity": 20524.44,
    "unrealized_pnl": -28.11,
    "open_positions": 3,
    "last_strategy_evaluation": "2026-11-17T10:00:00Z",
    "scan_count": 42,
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _scorecard(generated_at: str) -> dict:
    return {
        "generated_at": generated_at,
        "entrants": [
            {
                "entrant_id": "dow_effect",
                "open_positions": [
                    {
                        "venue": "binance_futures",
                        "symbol": "BTCUSDT",
                        "side": "LONG",
                        "qty": 0.01,
                        "entry_price": 90000.0,
                        "opened_ts": 1763000000.0,
                        "opened_at": "2026-11-13T00:00:00Z",
                        "strategy": "dow_effect",
                        "source": "tag",
                    },
                    {
                        "venue": "oanda_practice",
                        "symbol": "EURUSD",
                        "side": "SHORT",
                        "qty": 1000.0,
                        "entry_price": 1.08,
                        "opened_ts": 1763000100.0,
                        "opened_at": "2026-11-13T00:01:40Z",
                        "strategy": "ichimoku",
                        "source": "tag",
                    },
                ],
            },
            {
                "entrant_id": "UNREGISTERED",
                "open_positions": [
                    {
                        "venue": "binance_futures",
                        "symbol": "SOLUSDT",
                        "side": "LONG",
                        "qty": 2.0,
                        "entry_price": 200.0,
                        "opened_ts": 1763000200.0,
                        "opened_at": "2026-11-13T00:03:20Z",
                        "strategy": "mystery",
                        "source": "tag",
                    }
                ],
            },
        ],
    }


@pytest.fixture()
def live_book_files(tmp_path, monkeypatch):
    """A fresh heartbeat + fresh scorecard, wired via the env overrides."""
    hb = dict(HEARTBEAT, pid=os.getpid())
    hb_path = tmp_path / "daemon_heartbeat.json"
    hb_path.write_text(json.dumps(hb))
    monkeypatch.setenv("STRATEX_DAEMON_HEARTBEAT_FILE", str(hb_path))
    card_path = tmp_path / "forward_scorecard.json"
    card_path.write_text(json.dumps(_scorecard(_now_iso())))
    monkeypatch.setenv("STRATEX_FORWARD_SCORECARD_FILE", str(card_path))
    return {"heartbeat": hb_path, "scorecard": card_path, "dir": tmp_path}


@pytest.fixture()
def telemetry_history(tmp_path, monkeypatch):
    """A telemetry position-history store with one CLOSED record and one
    phantom OPEN record from the retired testnet engine (bb_reversion —
    the deleted strategy whose OPEN rows the old /api/positions served).
    """
    rows = [
        {
            "position_id": "HIST-CLOSED-1",
            "trade_id": "HIST-CLOSED-1",
            "symbol": "ETHUSDT",
            "strategy": "testnet_scalper",
            "side": "BUY",
            "status": "CLOSED",
            "entry_timestamp": "2026-11-01T00:00:00Z",
            "entry_price": 2000.0,
            "quantity": 0.5,
        },
        {
            "position_id": "HIST-OPEN-PHANTOM",
            "trade_id": "HIST-OPEN-PHANTOM",
            "symbol": "XRPUSDT",
            "strategy": "bb_reversion",
            "side": "BUY",
            "status": "OPEN",
            "entry_timestamp": "2026-11-02T00:00:00Z",
            "entry_price": 2.0,
            "quantity": 100.0,
        },
    ]
    hist = tmp_path / "testnet_position_history.jsonl"
    hist.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    monkeypatch.setenv("TESTNET_POSITION_HISTORY_FILE", str(hist))
    from testnet_engine.telemetry_manager import TelemetryManager

    TelemetryManager._instance = None
    yield hist
    TelemetryManager._instance = None


# ---------------------------------------------------------------------------
# Supervision composition (_real_trading_data)
# ---------------------------------------------------------------------------


class TestSupervisionComposition:
    def test_aggregates_and_rows_come_from_the_daemon(self, live_book_files):
        data = sup._real_trading_data()
        assert data["engine_source"] == "multi_venue_daemon"
        assert data["engine_data_status"] == "ok"
        # Balance basis is the heartbeat's combined multi-venue total —
        # NOT the retired MT5 file's 10792.8, NOT the scorecard's
        # account_equity_usd (a different basis).
        assert data["balance"] == 20552.55
        assert data["cash"] == 20552.55
        assert data["unrealized_pnl"] == -28.11
        assert data["position_count"] == 3
        assert data["positions_source"] == "forward_scorecard"
        assert data["positions_as_of"] is not None
        rows = data["positions"]
        # Flattened across ALL entrant cards, incl. UNREGISTERED.
        assert len(rows) == 3
        assert {r["symbol"] for r in rows} == {"BTCUSDT", "EURUSD", "SOLUSDT"}
        btc = next(r for r in rows if r["symbol"] == "BTCUSDT")
        assert btc["position_id"] == "binance_futures:BTCUSDT"
        assert btc["quantity"] == 0.01
        assert btc["entry_price"] == 90000.0
        assert btc["side"] == "LONG"
        assert btc["strategy"] == "dow_effect"
        # The scorecard has no marks: per-row unrealized is ABSENT,
        # never synthesised as 0.0; SL/TP are never fabricated.
        for row in rows:
            assert "unrealized_pnl" not in row
            assert "stop_loss" not in row
            assert "take_profit" not in row

    def test_cloud_file_is_never_served(self, live_book_files, monkeypatch):
        # Poison: a fresh cloud_portfolio_state.json with the retired
        # engine's figures sitting in the working directory's state dir.
        state_dir = live_book_files["dir"] / "state"
        state_dir.mkdir()
        (state_dir / "cloud_portfolio_state.json").write_text(
            json.dumps({"balance": 10792.8, "positions": {}})
        )
        monkeypatch.chdir(live_book_files["dir"])
        data = sup._real_trading_data()
        assert data["balance"] == 20552.55
        assert data["position_count"] == 3
        assert len(data["positions"]) == 3

    def test_stale_heartbeat_is_daemon_unavailable(self, live_book_files):
        hb_path = live_book_files["heartbeat"]
        old = datetime.datetime.now().timestamp() - 3600
        os.utime(hb_path, (old, old))
        data = sup._real_trading_data()
        assert data["engine_data_status"] == "daemon_unavailable"
        assert data["balance"] == 0.0
        assert data["positions"] == []
        assert data["position_count"] == 0
        assert data["positions_source"] == "unavailable"

    def test_stale_scorecard_withholds_rows_but_serves_aggregates(
        self, live_book_files
    ):
        stale = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=2)
        ).isoformat()
        live_book_files["scorecard"].write_text(json.dumps(_scorecard(stale)))
        data = sup._real_trading_data()
        assert data["balance"] == 20552.55
        assert data["position_count"] == 3
        assert data["positions"] == []
        assert data["positions_source"] == "unavailable"
        assert data["positions_as_of"] == stale

    def test_divergence_headline_count_wins(self, live_book_files):
        hb = dict(HEARTBEAT, pid=os.getpid(), open_positions=5)
        live_book_files["heartbeat"].write_text(json.dumps(hb))
        data = sup._real_trading_data()
        # The venue-derived headline count serves as-is; the row list is
        # neither padded nor trimmed to force a match.
        assert data["position_count"] == 5
        assert len(data["positions"]) == 3
        assert data["positions_as_of"] is not None


# ---------------------------------------------------------------------------
# /api/positions
# ---------------------------------------------------------------------------


class TestApiPositions:
    def test_open_is_the_scorecard_projection(
        self, live_book_files, telemetry_history
    ):
        client = dashboard.app.test_client()
        resp = client.get("/api/positions?status=OPEN")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["positions_source"] == "forward_scorecard"
        assert payload["data_age"] < 60
        assert payload["count"] == 3
        rows = payload["positions"]
        # Legacy row shape + side mapping LONG->BUY / SHORT->SELL.
        by_symbol = {r["symbol"]: r for r in rows}
        assert by_symbol["BTCUSDT"]["side"] == "BUY"
        assert by_symbol["EURUSD"]["side"] == "SELL"
        assert by_symbol["SOLUSDT"]["side"] == "BUY"
        assert by_symbol["BTCUSDT"]["position_id"] == "binance_futures:BTCUSDT"
        assert (
            by_symbol["BTCUSDT"]["trade_id"] == "daemon_binance_futures_BTCUSDT"
        )
        assert by_symbol["BTCUSDT"]["status"] == "OPEN"
        assert by_symbol["BTCUSDT"]["entry_timestamp"] == "2026-11-13T00:00:00Z"
        for row in rows:
            assert "unrealized_pnl" not in row
            assert "current_price" not in row
            assert "stop_loss" not in row
            assert "take_profit" not in row
        # The retired engine's phantom OPEN record is never served.
        assert "HIST-OPEN-PHANTOM" not in {r["position_id"] for r in rows}

    def test_open_stale_scorecard_is_honest_empty(
        self, live_book_files, telemetry_history
    ):
        stale = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=2)
        ).isoformat()
        live_book_files["scorecard"].write_text(json.dumps(_scorecard(stale)))
        client = dashboard.app.test_client()
        payload = client.get("/api/positions?status=OPEN").get_json()
        assert payload["positions"] == []
        assert payload["count"] == 0
        assert payload["positions_source"] == "unavailable"
        # data_age is honest now — the scorecard's real age, not 0.0.
        assert payload["data_age"] > 1800

    def test_closed_still_comes_from_telemetry(
        self, live_book_files, telemetry_history
    ):
        client = dashboard.app.test_client()
        payload = client.get("/api/positions?status=CLOSED").get_json()
        assert payload["count"] == 1
        assert payload["positions"][0]["position_id"] == "HIST-CLOSED-1"
        assert payload["positions"][0]["status"] == "CLOSED"


# ---------------------------------------------------------------------------
# /api/status positions leg
# ---------------------------------------------------------------------------


class TestApiStatusPositionsLeg:
    def test_status_positions_come_from_the_daemon(
        self, live_book_files, monkeypatch
    ):
        monkeypatch.setattr(
            dashboard,
            "get_live_account_and_holdings",
            lambda: {
                "usdt_total_cash": 5000.0,
                "active_trade_holdings_value": 0.0,
                "total_crypto_value": 0.0,
                "holdings": [],
            },
        )
        monkeypatch.setattr(dashboard, "_get_trades_data", lambda: {})
        client = dashboard.app.test_client()
        resp = client.get("/api/status")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["open_positions"] == 3
        rows = payload["open_positions_data"]
        assert len(rows) == 3
        assert {r["symbol"] for r in rows} == {"BTCUSDT", "EURUSD", "SOLUSDT"}
        for row in rows:
            assert "unrealized_pnl" not in row
            assert "stop_loss" not in row
            assert "take_profit" not in row
