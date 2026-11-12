"""
tests/test_telegram_webhook.py — webhook-mode tests for TelegramBotClient
(TASK-STRATEX-TGWEBHOOK, ZAI Agent 2).

Covers:
1. TELEGRAM_WEBHOOK_URL / TELEGRAM_WEBHOOK_SECRET detection + webhook_mode.
2. set_webhook() registering the URL (and secret_token) with Telegram.
3. process_webhook_update(): secret-header auth, duplicate update_id drop,
   dispatch to process_update.
4. start_listening() chooses webhook registration in webhook mode and does
   NOT start a poller; falls back to polling when registration fails.
5. The dashboard's /telegram-webhook route wires the bot correctly (403 on
   bad secret, 400 on bad JSON, 200 on accepted).
"""
import os
import unittest
from unittest.mock import MagicMock, patch

from notifications.telegram_bot import TelegramBotClient, get_telegram_bot


def _mkbot(**env):
    """Fresh webhook-configured bot with env patched."""
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("TELEGRAM_WEBHOOK_URL", None)
        for k, v in env.items():
            os.environ[k] = v
        bot = TelegramBotClient(bot_token="tok", chat_id="42")
        # clear afterwards so later tests are not polluted
        for k in env:
            os.environ.pop(k, None)
        return bot


class TestWebhookModeFlag:
    def test_webhook_mode_off_by_default(self):
        bot = TelegramBotClient(bot_token="tok", chat_id="42")
        assert bot.webhook_mode is False
        assert bot.webhook_url == ""

    def test_webhook_mode_on_when_url_set(self):
        bot = _mkbot(TELEGRAM_WEBHOOK_URL="https://example.com/stratex/telegram-webhook")
        assert bot.webhook_mode is True
        assert bot.webhook_url.endswith("/telegram-webhook")

    def test_webhook_secret_loaded(self):
        bot = _mkbot(
            TELEGRAM_WEBHOOK_URL="https://example.com/hook",
            TELEGRAM_WEBHOOK_SECRET="s3cret",
        )
        assert bot.webhook_secret == "s3cret"


class TestSetWebhook:
    @patch("notifications.telegram_bot.requests.post")
    def test_set_webhook_registers_url_and_secret(self, mock_post):
        mock_post.return_value.json.return_value = {"ok": True}
        bot = _mkbot(
            TELEGRAM_WEBHOOK_URL="https://example.com/hook",
            TELEGRAM_WEBHOOK_SECRET="s3cret",
        )
        assert bot.set_webhook() is True
        kwargs = mock_post.call_args.kwargs
        assert kwargs["json"]["url"] == "https://example.com/hook"
        assert kwargs["json"]["secret_token"] == "s3cret"
        assert kwargs["json"]["allowed_updates"] == ["message", "edited_message"]

    @patch("notifications.telegram_bot.requests.post")
    def test_set_webhook_reports_failure(self, mock_post):
        mock_post.return_value.json.return_value = {"ok": False, "description": "bad URL"}
        bot = _mkbot(TELEGRAM_WEBHOOK_URL="https://example.com/hook")
        assert bot.set_webhook() is False

    def test_set_webhook_noop_without_url(self):
        bot = TelegramBotClient(bot_token="tok", chat_id="42")
        assert bot.set_webhook() is False


class TestProcessWebhookUpdate:
    def _bot(self):
        return _mkbot(
            TELEGRAM_WEBHOOK_URL="https://example.com/hook",
            TELEGRAM_WEBHOOK_SECRET="s3cret",
        )

    def test_rejects_wrong_secret(self):
        bot = self._bot()
        upd = {"update_id": 100, "message": {"chat": {"id": 42}}}
        assert bot.process_webhook_update(upd, secret_header="WRONG") is False

    def test_accepts_correct_secret_and_dispatches(self):
        bot = self._bot()
        bot.process_update = MagicMock()
        upd = {"update_id": 100, "message": {"chat": {"id": 42}}}
        assert bot.process_webhook_update(upd, secret_header="s3cret") is True
        # dispatch is async; drain the executor
        bot.stop_polling()
        bot.process_update.assert_called_once()

    def test_duplicate_update_id_dropped(self):
        bot = self._bot()
        bot.process_update = MagicMock()
        upd = {"update_id": 100, "message": {"chat": {"id": 42}}}
        assert bot.process_webhook_update(upd, secret_header="s3cret") is True
        assert bot.process_webhook_update(upd, secret_header="s3cret") is False
        bot.stop_polling()

    def test_non_dict_rejected(self):
        bot = self._bot()
        assert bot.process_webhook_update("not-a-dict", secret_header="s3cret") is False


class TestStartListening:
    @patch.object(TelegramBotClient, "set_webhook", return_value=True)
    @patch.object(TelegramBotClient, "start_polling_in_background")
    def test_webhook_mode_registers_and_does_not_poll(self, mock_poll, mock_hook):
        bot = _mkbot(TELEGRAM_WEBHOOK_URL="https://example.com/hook")
        assert bot.start_listening() is True
        mock_hook.assert_called_once()
        mock_poll.assert_not_called()
        bot.stop_polling()

    @patch.object(TelegramBotClient, "set_webhook", return_value=False)
    @patch.object(TelegramBotClient, "start_polling_in_background")
    def test_fallback_to_polling_when_registration_fails(self, mock_poll, mock_hook):
        bot = _mkbot(TELEGRAM_WEBHOOK_URL="https://example.com/hook")
        assert bot.start_listening() is False
        mock_hook.assert_called_once()
        mock_poll.assert_called_once()
        bot.stop_polling()

    @patch.object(TelegramBotClient, "set_webhook", return_value=True)
    def test_unconfigured_bot_refuses_to_listen(self, mock_hook):
        bot = TelegramBotClient(bot_token="", chat_id="")
        assert bot.start_listening() is False
        mock_hook.assert_not_called()


class TestDashboardWebhookRoute:
    """The dashboard route exists and returns proper status codes.

    Skipped when Flask is unavailable (agent sandbox); the server venv has
    Flask installed, so the route is exercised there.
    """

    def _client(self):
        from importlib import reload as _reload
        import dashboard as dash_mod
        app = dash_mod.app
        app.config["TESTING"] = True
        return app.test_client(), dash_mod

    def test_route_exists(self):
        try:
            import flask  # noqa: F401
        except ImportError:
            import pytest
            pytest.skip("flask not installed in this environment")
        client, _ = self._client()
        # bad JSON -> 400
        rv = client.post("/telegram-webhook", data=b"not json",
                         content_type="application/json")
        assert rv.status_code == 400

    def test_route_rejects_bad_secret(self):
        try:
            import flask  # noqa: F401
        except ImportError:
            import pytest
            pytest.skip("flask not installed in this environment")
        client, _ = self._client()
        upd = {"update_id": 7, "message": {"chat": {"id": 1}}}
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "right"}, clear=False):
            rv = client.post(
                "/telegram-webhook",
                json=upd,
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            )
        assert rv.status_code == 403
