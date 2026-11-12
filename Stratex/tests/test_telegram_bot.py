"""
tests/test_telegram_bot.py — Comprehensive Unit Tests for TelegramBotClient.

Verifies:
1. Configuration detection and secret masking.
2. Outbound notifications (trade intent, fill, risk rejection, emergency halt).
3. Inbound interactive command dispatcher (/start, /status, /halt, /resume, /positions, /balance).
4. Security barrier dropping unauthorized chat IDs.
5. Polling updates, offset tracking, and background daemon lifecycle.
"""
from unittest.mock import MagicMock, patch

import pytest

from notifications.telegram_bot import TelegramBotClient, get_telegram_bot
from stratex_agents.order_intent import TradeIntent


class TestTelegramBotClient:
    @pytest.fixture
    def bot(self):
        return TelegramBotClient(
            bot_token="test-bot-token-12345",
            chat_id="123456789",
            request_timeout=2,
        )

    def test_configuration_detection(self):
        configured = TelegramBotClient("token", "123")
        assert configured.is_configured is True

        empty_token = TelegramBotClient("", "123")
        assert empty_token.is_configured is False

        empty_chat = TelegramBotClient("token", "")
        assert empty_chat.is_configured is False

    @patch("requests.post")
    def test_send_message_success(self, mock_post, bot):
        mock_post.return_value.json.return_value = {"ok": True, "result": {"message_id": 999}}
        success = bot.send_message("<b>Hello</b>")
        assert success is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["chat_id"] == "123456789"
        assert kwargs["json"]["text"] == "<b>Hello</b>"
        assert kwargs["json"]["parse_mode"] == "HTML"

    @patch("requests.post")
    def test_send_message_failure(self, mock_post, bot):
        mock_post.return_value.json.return_value = {"ok": False, "description": "Forbidden"}
        success = bot.send_message("test")
        assert success is False

        # Exception handling
        mock_post.side_effect = Exception("network down")
        assert bot.send_message("test") is False

    @patch("requests.post")
    def test_notify_trade_intent(self, mock_post, bot):
        mock_post.return_value.json.return_value = {"ok": True}
        intent = TradeIntent(
            venue="binance",
            symbol="ETHUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.5,
            environment="binance_testnet",
            stop_loss=2500.0,
            take_profit=2700.0,
            strategy="kalman_mean_reversion",
            client_order_id="stx-test-123",
        )
        res = bot.notify_trade_intent(intent, status="FILLED", fill_price=2550.0, pnl=25.0)
        assert res is True
        args, kwargs = mock_post.call_args
        text = kwargs["json"]["text"]
        assert "ETHUSDT" in text
        assert "BUY" in text
        assert "2,550.0000" in text
        assert "25.00" in text

    @patch("requests.post")
    def test_notify_risk_rejection(self, mock_post, bot):
        mock_post.return_value.json.return_value = {"ok": True}
        intent = TradeIntent(
            venue="binance",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.1,
            environment="binance_testnet",
            stop_loss=90.0,
            take_profit=110.0,
            strategy="test_strategy",
        )
        res = bot.notify_risk_rejection(intent, reason="MAX_MARGIN_EXCEEDED")
        assert res is True
        text = mock_post.call_args[1]["json"]["text"]
        assert "RISK GATE BLOCKED ORDER" in text
        assert "MAX_MARGIN_EXCEEDED" in text

    @patch("requests.post")
    def test_notify_emergency_halt(self, mock_post, bot):
        mock_post.return_value.json.return_value = {"ok": True}
        res = bot.notify_emergency_halt("api_panic", "Manual panic switch")
        assert res is True
        text = mock_post.call_args[1]["json"]["text"]
        assert "EMERGENCY PANIC HALT" in text
        assert "api_panic" in text

    def test_handle_command_start_and_help(self, bot):
        res = bot.handle_command("/start")
        assert "/status" in res
        assert "/positions" in res
        assert "/halt" in res

        res_help = bot.handle_command("/help")
        assert "/status" in res_help

    def test_handle_command_status(self, bot):
        res = bot.handle_command("/status")
        assert "Stratex Engine Status" in res
        assert "Oracle Cloud" in res

    def test_handle_command_positions_and_balance(self, bot):
        pos = bot.handle_command("/positions")
        assert "Active Positions" in pos

        bal = bot.handle_command("/balance")
        # The balance command's honest contract: a real venue report when a
        # venue responds, or the explicit "Balance unavailable" refusal when
        # none does (sandbox has no live venue). Either is truthful; a fake
        # number is not acceptable.
        assert "Account Balance" in bal or "Balance unavailable" in bal

    def test_handle_command_halt_and_resume(self, bot):
        halt_resp = bot.handle_command("/halt")
        assert "EMERGENCY HALT TRIGGERED" in halt_resp

        resume_resp = bot.handle_command("/resume")
        assert "Trading Resumed" in resume_resp

    def test_handle_command_natural_language(self, bot):
        resp = bot.handle_command("Why did you enter long on BTC?")
        assert "Quantitative Intelligence" in resp
        assert "Regime" in resp

    @patch("requests.post")
    def test_process_update_authorized_vs_unauthorized(self, mock_post, bot):
        mock_post.return_value.json.return_value = {"ok": True}

        # 1. Unauthorized message
        bot.process_update({
            "message": {
                "chat": {"id": "999999999"},
                "text": "/status",
            }
        })
        mock_post.assert_not_called()

        # 2. Authorized message
        bot.process_update({
            "message": {
                "chat": {"id": "123456789"},
                "text": "/status",
            }
        })
        mock_post.assert_called_once()

    @patch("requests.get")
    @patch("requests.post")
    def test_poll_once(self, mock_post, mock_get, bot):
        mock_get.return_value.json.return_value = {
            "ok": True,
            "result": [
                {
                    "update_id": 1001,
                    "message": {
                        "chat": {"id": "123456789"},
                        "text": "/status",
                    },
                }
            ],
        }
        mock_post.return_value.json.return_value = {"ok": True}

        count = bot.poll_once()
        assert count == 1
        assert bot._last_update_id == 1001
        # The update dispatches through the executor thread pool; drain it
        # before asserting on the outbound reply so the test is race-free.
        executor = bot._executor
        if executor is not None:
            executor.shutdown(wait=True)
        mock_post.assert_called_once()

    # ------------------------------------------------------------------
    # TASK-STRATEX-TG409 — 409-conflict episode handling (ZAI Agent 2)
    # ------------------------------------------------------------------

    @staticmethod
    def _conflict_response(status: int = 409):
        """Build a requests-like mock response carrying a 409 status."""
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = {"ok": False, "description": "Conflict: terminated by other getUpdates request"}
        return resp

    @staticmethod
    def _ok_empty_response():
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"ok": True, "result": []}
        return resp

    @patch("notifications.telegram_bot.requests.get")
    def test_conflict_first_hit_sets_backoff_and_episode(self, mock_get, bot):
        """First 409 opens episode #1 with a 1s backoff, not zero."""
        mock_get.return_value = self._conflict_response()
        bot.poll_once()
        assert bot._conflict_episode_count == 1
        assert bot._conflict_backoff == 1.0
        assert bot.conflict_episode == 1

    @patch("notifications.telegram_bot.requests.get")
    def test_conflict_backoff_doubles_and_caps_at_120s(self, mock_get, bot):
        """Backoff grows 1 -> 2 -> 4 ... and caps at 120s."""
        mock_get.return_value = self._conflict_response()
        expected = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 120.0, 120.0]
        for step, want in enumerate(expected, start=1):
            bot.poll_once()
            assert bot._conflict_backoff == want, f"step {step}: expected {want}, got {bot._conflict_backoff}"
        assert bot._conflict_episode_count == 1, "repeated conflicts are ONE episode until recovery"

    @patch("notifications.telegram_bot.requests.get")
    @patch("notifications.telegram_bot.requests.post")
    def test_conflict_alert_sent_once_per_episode(self, mock_post, mock_get, bot):
        """The owner-visible alert fires exactly once per episode, not per conflict."""
        mock_get.return_value = self._conflict_response()
        mock_post.return_value.json.return_value = {"ok": True}
        for _ in range(5):
            bot.poll_once()
        outbound = [c for c in mock_post.call_args_list if "getUpdates" not in str(c)]
        conflict_alerts = [c for c in outbound if "CONFLICT" in str(c)]
        assert len(conflict_alerts) == 1, f"expected exactly one owner alert, saw {len(conflict_alerts)}"

    @patch("notifications.telegram_bot.requests.get")
    @patch("notifications.telegram_bot.requests.post")
    def test_conflict_alert_not_resent_after_realert_in_next_episode(self, mock_post, mock_get, bot):
        """Recovery then a NEW conflict re-alerts (new episode) — once again."""
        mock_get.side_effect = [
            self._conflict_response(),
            self._ok_empty_response(),   # recovery
            self._conflict_response(),  # new episode
            self._conflict_response(),  # same new episode
        ]
        mock_post.return_value.json.return_value = {"ok": True}
        bot.poll_once()  # conflict 1 -> alert #1
        bot.poll_once()  # recovery -> backoff reset
        assert bot.conflict_episode is None
        assert bot._conflict_backoff == 0.0
        bot.poll_once()  # conflict episode 2 -> alert #2
        bot.poll_once()  # still episode 2 -> NO third alert
        conflict_alerts = [c for c in mock_post.call_args_list if "CONFLICT" in str(c)]
        assert len(conflict_alerts) == 2
        assert bot._conflict_episode_count == 2

    @patch("notifications.telegram_bot.requests.get")
    def test_recovery_clears_backoff_and_reports_episode_count(self, mock_get, bot):
        """A successful poll after a conflict closes the episode: backoff -> 0."""
        mock_get.side_effect = [
            self._conflict_response(),
            self._ok_empty_response(),
        ]
        bot.poll_once()
        assert bot._conflict_backoff == 1.0
        bot.poll_once()
        assert bot._conflict_backoff == 0.0
        assert bot.conflict_episode is None
        # episode count is cumulative history, not current state
        assert bot._conflict_episode_count == 1

    @patch("notifications.telegram_bot.requests.get")
    @patch("notifications.telegram_bot.requests.post")
    def test_alert_failure_never_breaks_polling(self, mock_post, mock_get, bot):
        """When the outbound alert fails, polling still returns normally and
        episode state is tracked (honest accounting, no exception raised)."""
        mock_get.return_value = self._conflict_response()
        mock_post.side_effect = Exception("network down")
        result = bot.poll_once()  # must not raise
        assert result == 0
        assert bot._conflict_episode_count == 1
        assert bot._conflict_alert_sent is False, "failed alert may be retried next episode"

    @patch("notifications.telegram_bot.requests.get")
    def test_healthy_polling_keeps_conflict_state_clean(self, mock_get, bot):
        """No 409 ever seen: no episode, no backoff, property stays None."""
        mock_get.return_value = self._ok_empty_response()
        for _ in range(3):
            assert bot.poll_once() == 0
        assert bot.conflict_episode is None
        assert bot._conflict_backoff == 0.0
        assert bot._conflict_episode_count == 0

    def test_polling_daemon_lifecycle(self, bot):
        with patch.object(bot, "poll_once") as mock_poll:
            bot.start_polling_in_background()
            assert bot._polling_active is True
            bot.stop_polling()
            assert bot._polling_active is False

    def test_singleton_accessor(self):
        instance = get_telegram_bot()
        assert isinstance(instance, TelegramBotClient)
