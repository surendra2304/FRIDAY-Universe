"""TASK-STR-DAEMON-004: every daemon Telegram send is logged persistently.

Production evidence (DAEMON-001, 2026-11-21): the per-restart triple-send
was root-caused from the live journal, but the journal retains only ~2h of
the daemon's output — a future recurrence could not be investigated with
its full history intact. The fix logs every Telegram send the daemon makes
to Stratex/state/telegram_sends.jsonl (STRATEX_STATE_DIR override), one
JSON object per line: UTC timestamp, send type, dedupe key / message id.
These tests pin:

(a) one confirmed send appends exactly one log line with UTC timestamp,
    send type, dedupe key (sha1 of the text) and the Telegram message id;
(b) a dedupe-suppressed duplicate (same text within 120s) appends no
    second line — exactly-once logging: one confirmed send, one line;
(c) a failed send appends nothing;
(d) the log survives a restart: a fresh bot instance on the same state
    dir reads the old entries, and a new send appends to them;
(e) retention: entries older than 7 days are pruned on append, entries
    within 7 days are kept;
(f) send types classify the daemon's known messages (startup pair, daily
    summary, trade executed, position closed) and unknown text is "other";
(g) an unconfigured bot sends nothing and logs nothing; a corrupt log
    file never breaks a send and its unreadable lines are preserved;
(h) a photo send is logged too (type "photo", with its message id).
"""

import datetime
import hashlib
import json
import os
from unittest.mock import patch

import pytest

from notifications import telegram_send_log as send_log
from notifications.telegram_bot import TelegramBotClient

ONLINE = "🚀 <b>Stratex Online — Multi-Venue</b>\n\n• Venues: Binance Futures"
STARTED = "📡 <b>Stratex Started</b>\n💰 Balance: <code>$1,000.00</code>"
SUMMARY = "📊 <b>DAILY SUMMARY — 2026-11-22</b>\n\n• Symbols scanned: <code>5</code>"
EXECUTED = "🟢 <b>TRADE EXECUTED</b>\n\n• Symbol: <code>BTCUSDT</code>"
CLOSED = "💰 <b>POSITION CLOSED</b>\n\n• Symbol: <code>BTCUSDT</code>"


@pytest.fixture
def bot(monkeypatch, tmp_path):
    """A configured bot whose send log lives in the test's state dir."""
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
    return TelegramBotClient(
        bot_token="test-bot-token-12345",
        chat_id="123456789",
        request_timeout=2,
    )


def _ok_post(mock_post, message_id=999):
    mock_post.return_value.json.return_value = {
        "ok": True,
        "result": {"message_id": message_id},
    }


def _log_file(tmp_path):
    return tmp_path / "telegram_sends.jsonl"


def _seed_entry(days_old, send_type="other", first_line="seeded"):
    ts = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=days_old)
    ).isoformat()
    return {
        "ts": ts,
        "send_type": send_type,
        "dedupe_key": "seed",
        "message_id": 1,
        "chars": 6,
        "first_line": first_line,
    }


class TestSendLogPersists:
    @patch("notifications.telegram_bot.requests.post")
    def test_confirmed_send_logs_exactly_one_line(self, mock_post, bot, tmp_path):
        """(a) One confirmed send: exactly one line, with timestamp, type,
        dedupe key (sha1 of the text) and the Telegram message id."""
        _ok_post(mock_post, message_id=999)
        assert bot.send_message(ONLINE) is True

        entries = send_log.read_send_log()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["send_type"] == "startup_online"
        assert entry["dedupe_key"] == hashlib.sha1(ONLINE.encode("utf-8")).hexdigest()
        assert entry["message_id"] == 999
        assert entry["chars"] == len(ONLINE)
        assert entry["first_line"] == "🚀 Stratex Online — Multi-Venue"
        # UTC timestamp, parseable and recent.
        ts = datetime.datetime.fromisoformat(entry["ts"])
        assert ts.tzinfo is not None
        age = datetime.datetime.now(datetime.timezone.utc) - ts
        assert age < datetime.timedelta(minutes=5)

    @patch("notifications.telegram_bot.requests.post")
    def test_duplicate_within_120s_logs_no_second_line(self, mock_post, bot, tmp_path):
        """(b) The DAEMON-004 exactly-once rule: send_message's 120s dedupe
        suppresses the re-send, and the suppressed send appends no line —
        one confirmed send, one log line."""
        _ok_post(mock_post, message_id=999)
        assert bot.send_message(EXECUTED) is True
        assert bot.send_message(EXECUTED) is True  # suppressed duplicate
        assert mock_post.call_count == 1

        entries = send_log.read_send_log()
        assert len(entries) == 1
        assert entries[0]["send_type"] == "trade_executed"

    @patch("notifications.telegram_bot.requests.post")
    def test_failed_send_logs_nothing(self, mock_post, bot, tmp_path):
        """(c) A rejected send appends nothing; a network error appends
        nothing either. The log records sends that happened, not attempts."""
        mock_post.return_value.json.return_value = {
            "ok": False,
            "description": "Forbidden",
        }
        assert bot.send_message(ONLINE) is False
        assert send_log.read_send_log() == []
        assert not _log_file(tmp_path).exists()

        mock_post.side_effect = Exception("network down")
        assert bot.send_message(ONLINE) is False
        assert send_log.read_send_log() == []

    @patch("notifications.telegram_bot.requests.post")
    def test_log_survives_restart(self, mock_post, bot, tmp_path, monkeypatch):
        """(d) The DAEMON-001 gap, closed: a fresh bot instance (a restart)
        on the same state dir reads the old entries, and its send appends
        to them instead of starting a new log."""
        _ok_post(mock_post, message_id=111)
        assert bot.send_message(ONLINE) is True

        # A restart: new bot, no memory carried, same state dir.
        restarted = TelegramBotClient(
            bot_token="test-bot-token-12345",
            chat_id="123456789",
            request_timeout=2,
        )
        entries = send_log.read_send_log()
        assert len(entries) == 1
        assert entries[0]["message_id"] == 111

        _ok_post(mock_post, message_id=222)
        assert restarted.send_message(STARTED) is True
        entries = send_log.read_send_log()
        assert [e["message_id"] for e in entries] == [111, 222]
        assert [e["send_type"] for e in entries] == [
            "startup_online",
            "startup_started",
        ]

    @patch("notifications.telegram_bot.requests.post")
    def test_retention_prunes_older_than_7_days(self, mock_post, bot, tmp_path):
        """(e) The log retains at least 7 days: an 8-day-old entry is
        pruned on the next append, a ~7-day-old entry is kept."""
        _log_file(tmp_path).write_text(
            "\n".join(
                json.dumps(_seed_entry(days, first_line=f"{days}d old"))
                for days in (8, 6.96, 0.04)
            )
            + "\n",
            encoding="utf-8",
        )
        _ok_post(mock_post, message_id=333)
        assert bot.send_message(SUMMARY) is True

        entries = send_log.read_send_log()
        assert [e["first_line"] for e in entries] == [
            "6.96d old",
            "0.04d old",
            "📊 DAILY SUMMARY — 2026-11-22",
        ]

    @patch("notifications.telegram_bot.requests.post")
    def test_send_types_classify_known_messages(self, mock_post, bot, tmp_path):
        """(f) The daemon's known messages classify to stable types; an
        unknown message is still logged, as "other" with its first line."""
        _ok_post(mock_post)
        for text in (ONLINE, STARTED, SUMMARY, EXECUTED, CLOSED, "hello world"):
            assert bot.send_message(text) is True

        entries = send_log.read_send_log()
        assert [e["send_type"] for e in entries] == [
            "startup_online",
            "startup_started",
            "daily_summary",
            "trade_executed",
            "position_closed",
            "other",
        ]
        assert entries[-1]["first_line"] == "hello world"

    @patch("notifications.telegram_bot.requests.post")
    def test_unconfigured_bot_logs_nothing(self, mock_post, tmp_path, monkeypatch):
        """(g) Bot not configured: nothing sent, nothing logged — and no
        state file is created, so a later configured start still logs."""
        monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
        quiet = TelegramBotClient(bot_token="", chat_id="123")
        assert quiet.send_message(ONLINE) is False
        mock_post.assert_not_called()
        assert not _log_file(tmp_path).exists()

    @patch("notifications.telegram_bot.requests.post")
    def test_corrupt_log_never_breaks_a_send(self, mock_post, bot, tmp_path):
        """(g) A corrupt pre-existing log degrades gracefully: the send
        still goes out and is logged, and the unreadable line is preserved
        verbatim rather than deleted by the pruner."""
        _log_file(tmp_path).write_text("{not json\n", encoding="utf-8")
        _ok_post(mock_post, message_id=444)
        assert bot.send_message(EXECUTED) is True

        raw = _log_file(tmp_path).read_text(encoding="utf-8").splitlines()
        assert raw[0] == "{not json"
        assert json.loads(raw[1])["message_id"] == 444
        assert len(send_log.read_send_log()) == 1

    @patch("notifications.telegram_bot.requests.post")
    def test_photo_send_is_logged(self, mock_post, bot, tmp_path):
        """(h) A chart photo is a Telegram send too: logged as type
        "photo" with its message id and caption line."""
        photo = tmp_path / "equity.png"
        photo.write_bytes(b"\x89PNG\r\n\x1a\n")
        _ok_post(mock_post, message_id=4242)
        assert bot.send_photo(str(photo), caption="📈 Stratex equity curve") is True

        entries = send_log.read_send_log()
        assert len(entries) == 1
        assert entries[0]["send_type"] == "photo"
        assert entries[0]["message_id"] == 4242
        assert entries[0]["dedupe_key"] is None
        assert entries[0]["first_line"] == "📈 Stratex equity curve"


class TestSendLogModule:
    def test_classify_known_and_unknown(self):
        assert send_log.classify_send_type(ONLINE) == "startup_online"
        assert send_log.classify_send_type(STARTED) == "startup_started"
        assert send_log.classify_send_type(SUMMARY) == "daily_summary"
        assert send_log.classify_send_type(EXECUTED) == "trade_executed"
        assert send_log.classify_send_type(CLOSED) == "position_closed"
        assert (
            send_log.classify_send_type("⚠️ <b>STRATEX BOT CONFLICT #2</b>")
            == "poll_conflict"
        )
        assert send_log.classify_send_type("unrelated text") == "other"
        assert send_log.classify_send_type("") == "other"

    def test_read_missing_log_is_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
        assert send_log.read_send_log() == []

    def test_default_path_is_stratex_state(self, monkeypatch):
        monkeypatch.delenv("STRATEX_STATE_DIR", raising=False)
        assert send_log.send_log_path().endswith(
            os.path.join("state", "telegram_sends.jsonl")
        )

    def test_prune_removes_only_old_entries(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
        _log_file(tmp_path).write_text(
            "\n".join(
                json.dumps(_seed_entry(days, first_line=f"{days}d old"))
                for days in (9, 3, 0)
            )
            + "\n",
            encoding="utf-8",
        )
        assert send_log.prune_send_log() == 1
        assert [e["first_line"] for e in send_log.read_send_log()] == [
            "3d old",
            "0d old",
        ]

    def test_append_never_raises_when_state_path_is_a_file(self, tmp_path, monkeypatch):
        """Logging must never break a send: if the state dir cannot be
        created (here the state-dir path is an existing file), append
        degrades to None instead of raising."""
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir", encoding="utf-8")
        monkeypatch.setenv("STRATEX_STATE_DIR", str(blocker))
        assert send_log.append_send_log(text=ONLINE) is None
