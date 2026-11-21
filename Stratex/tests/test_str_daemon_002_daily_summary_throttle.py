"""TASK-STR-DAEMON-002: the daily-summary throttle must survive restarts.

Production evidence (DAEMON-001, 2026-11-21): after a daemon restart
the first scan cycle re-sent that day's Telegram daily summary,
because _last_summary_date lived only in memory (run_daemon.py:353)
and reset to "" on restart — the third leg of the per-restart
triple-send.

The fix persists the last-sent UTC day in Stratex/state/
(daily_summary_state.json, STRATEX_STATE_DIR override). These tests
pin:

(a) a fresh engine on the same UTC day does NOT re-send after a
    restart (the bug: the in-memory throttle reset);
(b) the first engine on a new UTC day sends exactly once, and a
    restart later that day does not re-send;
(c) a missing or corrupt state file degrades to sending once, then
    persists (the pre-DAEMON-002 behaviour, not a crash);
(d) the persisted file holds exactly the last-sent UTC day.
"""

import datetime
import json

import autonomy.run_daemon as run_daemon
from autonomy.run_daemon import StratexTradingEngine


RESULTS = {"symbols": 5, "signals": 1}


class _FakeBot:
    """Telegram bot stub: configured, records every sent message."""

    def __init__(self):
        self.is_configured = True
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


class _StubEngine:
    """Inner engine stub: bot + the risk/position reads the summary uses."""

    def __init__(self):
        self.telegram_bot = _FakeBot()
        self.realized_pnl = 0.0
        self.positions = {}

    def get_risk_summary(self):
        return {
            "total_equity": 1000.0,
            "realized_pnl": 0.0,
            "daily_loss_limit_hit": False,
        }


def _engine(tmp_path, monkeypatch):
    """An engine built like the production one, minus __init__."""
    eng = StratexTradingEngine.__new__(StratexTradingEngine)
    eng.engine = _StubEngine()
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
    return eng


def _today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def _state_file(tmp_path):
    return tmp_path / "daily_summary_state.json"


class TestDailySummaryThrottlePersists:
    def test_restart_same_day_does_not_resend(self, tmp_path, monkeypatch):
        """(a) The DAEMON-001 bug: a restart inside the same UTC day
        re-sent the summary. With the throttle persisted, the second
        process sends nothing."""
        first = _engine(tmp_path, monkeypatch)
        first._maybe_send_daily_summary(dict(RESULTS))
        assert len(first.engine.telegram_bot.sent) == 1
        assert "DAILY SUMMARY" in first.engine.telegram_bot.sent[0]

        # A fresh engine = a restart: same state dir, no memory carried.
        second = _engine(tmp_path, monkeypatch)
        second._maybe_send_daily_summary(dict(RESULTS))
        assert second.engine.telegram_bot.sent == []

    def test_new_utc_day_sends_once_then_restart_does_not(self, tmp_path, monkeypatch):
        """(b) First start of a new UTC day still sends once; a restart
        later that day does not re-send."""
        yesterday = (_today() - datetime.timedelta(days=1)).isoformat()
        _state_file(tmp_path).write_text(
            json.dumps({"last_summary_date": yesterday})
        )

        first = _engine(tmp_path, monkeypatch)
        first._maybe_send_daily_summary(dict(RESULTS))
        assert len(first.engine.telegram_bot.sent) == 1

        # Same engine, second scan: in-memory throttle still holds.
        first._maybe_send_daily_summary(dict(RESULTS))
        assert len(first.engine.telegram_bot.sent) == 1

        # Fresh engine later the same day: persisted throttle holds.
        second = _engine(tmp_path, monkeypatch)
        second._maybe_send_daily_summary(dict(RESULTS))
        assert second.engine.telegram_bot.sent == []

    def test_missing_state_sends_once(self, tmp_path, monkeypatch):
        """(c) No state file (first run ever): send once, then persist."""
        assert not _state_file(tmp_path).exists()
        eng = _engine(tmp_path, monkeypatch)
        eng._maybe_send_daily_summary(dict(RESULTS))
        assert len(eng.engine.telegram_bot.sent) == 1
        assert _state_file(tmp_path).exists()

    def test_corrupt_state_sends_once_then_persists(self, tmp_path, monkeypatch):
        """(c) A corrupt state file degrades to sending once, then
        overwrites the file with a valid state — never a crash."""
        _state_file(tmp_path).write_text("{not json")
        eng = _engine(tmp_path, monkeypatch)
        eng._maybe_send_daily_summary(dict(RESULTS))
        assert len(eng.engine.telegram_bot.sent) == 1
        assert json.loads(_state_file(tmp_path).read_text()) == {
            "last_summary_date": _today().isoformat()
        }

    def test_state_file_holds_last_sent_day(self, tmp_path, monkeypatch):
        """(d) The persisted file holds exactly the last-sent UTC day."""
        eng = _engine(tmp_path, monkeypatch)
        eng._maybe_send_daily_summary(dict(RESULTS))
        assert json.loads(_state_file(tmp_path).read_text()) == {
            "last_summary_date": _today().isoformat()
        }
        # The in-memory throttle agrees with the persisted file.
        assert eng._last_summary_date == _today().isoformat()
