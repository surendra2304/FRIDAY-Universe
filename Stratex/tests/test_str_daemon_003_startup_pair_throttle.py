"""TASK-STR-DAEMON-003: the startup Telegram pair must send once per UTC day.

Production evidence (DAEMON-001, 2026-11-21): the daemon sent its startup
Telegram pair — the "Online" message plus the "Started" heartbeat — on
every restart, two of the three legs of the per-restart triple-send (the
third leg, the daily summary, was gated in DAEMON-002).

The fix gates the pair on the UTC day, persisted in Stratex/state/
(startup_pair_state.json, STRATEX_STATE_DIR override). These tests pin:

(a) a fresh start sends the pair exactly once (both legs), and a
    restart inside the same UTC day sends nothing;
(b) the first start of a new UTC day sends the pair exactly once, and a
    restart later that day sends nothing;
(c) a missing or corrupt state file degrades to sending once, then
    persists (the pre-DAEMON-003 behaviour, not a crash);
(d) the persisted file holds exactly the last-sent UTC day;
(e) an unconfigured bot sends nothing and persists nothing — a later
    configured start still sends;
(f) a failed risk read still sends the Online leg and persists.
"""

import datetime
import json

import autonomy.run_daemon as run_daemon


RISK = {"total_balance": 1000.0, "max_positions": 10, "daily_loss_limit_hit": False}


class _FakeBot:
    """Telegram bot stub: records every sent message."""

    def __init__(self, configured=True):
        self.is_configured = configured
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


def _today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def _state_file(tmp_path):
    return tmp_path / "startup_pair_state.json"


_MISSING = object()


def _send(tmp_path, monkeypatch, bot=None, risk=_MISSING):
    """A daemon start: fresh state-dir read, no memory carried.

    risk=None means the risk read failed (test f); otherwise the
    default RISK dict is used.
    """
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
    bot = bot if bot is not None else _FakeBot()
    sent = run_daemon._maybe_send_startup_pair(
        bot, RISK if risk is _MISSING else risk
    )
    return sent, bot


class TestStartupPairThrottlePersists:
    def test_restart_same_day_does_not_resend(self, tmp_path, monkeypatch):
        """(a) The DAEMON-001 bug: a restart inside the same UTC day
        re-sent the startup pair. With the throttle persisted, the
        second process sends nothing."""
        sent, bot = _send(tmp_path, monkeypatch)
        assert sent is True
        assert len(bot.sent) == 2
        assert "Stratex Online" in bot.sent[0]
        assert "Stratex Started" in bot.sent[1]

        # A fresh process = a restart: same state dir, no memory carried.
        sent2, bot2 = _send(tmp_path, monkeypatch)
        assert sent2 is False
        assert bot2.sent == []

    def test_new_utc_day_sends_once_then_restart_does_not(self, tmp_path, monkeypatch):
        """(b) First start of a new UTC day still sends the pair once;
        a restart later that day does not re-send."""
        yesterday = (_today() - datetime.timedelta(days=1)).isoformat()
        _state_file(tmp_path).write_text(
            json.dumps({"last_startup_pair_date": yesterday})
        )

        sent, bot = _send(tmp_path, monkeypatch)
        assert sent is True
        assert len(bot.sent) == 2

        # Same process, second call: persisted throttle still holds.
        sent2, bot2 = _send(tmp_path, monkeypatch)
        assert sent2 is False
        assert bot2.sent == []

    def test_missing_state_sends_once(self, tmp_path, monkeypatch):
        """(c) No state file (first run ever): send once, then persist."""
        assert not _state_file(tmp_path).exists()
        sent, bot = _send(tmp_path, monkeypatch)
        assert sent is True
        assert len(bot.sent) == 2
        assert _state_file(tmp_path).exists()

    def test_corrupt_state_sends_once_then_persists(self, tmp_path, monkeypatch):
        """(c) A corrupt state file degrades to sending once, then
        overwrites the file with a valid state — never a crash."""
        _state_file(tmp_path).write_text("{not json")
        sent, bot = _send(tmp_path, monkeypatch)
        assert sent is True
        assert len(bot.sent) == 2
        assert json.loads(_state_file(tmp_path).read_text()) == {
            "last_startup_pair_date": _today().isoformat()
        }

    def test_state_file_holds_last_sent_day(self, tmp_path, monkeypatch):
        """(d) The persisted file holds exactly the last-sent UTC day."""
        _send(tmp_path, monkeypatch)
        assert json.loads(_state_file(tmp_path).read_text()) == {
            "last_startup_pair_date": _today().isoformat()
        }

    def test_unconfigured_bot_sends_nothing_and_persists_nothing(
        self, tmp_path, monkeypatch
    ):
        """(e) Bot not configured: nothing sent, nothing persisted — a
        later configured start still sends the pair."""
        sent, bot = _send(tmp_path, monkeypatch, bot=_FakeBot(configured=False))
        assert sent is False
        assert bot.sent == []
        assert not _state_file(tmp_path).exists()

        sent2, bot2 = _send(tmp_path, monkeypatch)
        assert sent2 is True
        assert len(bot2.sent) == 2

    def test_failed_risk_read_still_sends_online_leg(self, tmp_path, monkeypatch):
        """(f) The risk read failed (risk None): the Online leg still
        goes out, the Started leg is skipped, and the day persists."""
        sent, bot = _send(tmp_path, monkeypatch, risk=None)
        assert sent is True
        assert len(bot.sent) == 1
        assert "Stratex Online" in bot.sent[0]
        assert json.loads(_state_file(tmp_path).read_text()) == {
            "last_startup_pair_date": _today().isoformat()
        }
