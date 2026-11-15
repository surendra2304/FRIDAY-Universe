"""Approval dispatcher channel-credential resolution (TASK-SEN-006).

Production finding (alerting-path drill, 2026-11-15): the Sentinel systemd
unit does not export the fleet's Telegram pair into the process environment,
and the dispatcher only read ``os.environ`` — so guarded-action approvals
were queued to a journal line ("[SENTINEL APPROVAL QUEUED]") and no human
was ever notified. These tests pin the resolution contract: process
environment first, then .env files in the fleet layout.
"""

import json
import urllib.request

import pytest

import sentinel.gatekeeper.approval_dispatcher as dispatcher_module
from sentinel.gatekeeper.approval_dispatcher import approval_dispatcher

CRED_NAMES = (
    "TELEGRAM_BOT_TOKEN",
    "SENTINEL_TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SENTINEL_TELEGRAM_CHAT_ID",
    "DISCORD_WEBHOOK_URL",
    "SENTINEL_DISCORD_WEBHOOK_URL",
)


@pytest.fixture(autouse=True)
def _clean_credential_state(monkeypatch):
    for name in CRED_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("SENTINEL_ENV_FILE", raising=False)
    dispatcher_module._FILE_ENV_CACHE = None
    yield
    dispatcher_module._FILE_ENV_CACHE = None


def _write_env(tmp_path, text):
    env_file = tmp_path / ".env"
    env_file.write_text(text, encoding="utf-8")
    return env_file


def test_process_environment_wins(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "env-chat")
    assert approval_dispatcher.telegram_bot_token == "env-token"
    assert approval_dispatcher.telegram_chat_id == "env-chat"


def test_env_file_fallback(monkeypatch, tmp_path):
    env_file = _write_env(
        tmp_path,
        "# fleet shared env\n"
        'TELEGRAM_BOT_TOKEN="file-token"\n'
        "TELEGRAM_CHAT_ID='file-chat'\n",
    )
    monkeypatch.setattr(dispatcher_module, "_env_file_candidates", lambda: [env_file])
    assert approval_dispatcher.telegram_bot_token == "file-token"
    assert approval_dispatcher.telegram_chat_id == "file-chat"


def test_sentinel_prefixed_names_resolve_from_file(monkeypatch, tmp_path):
    env_file = _write_env(
        tmp_path,
        "SENTINEL_TELEGRAM_BOT_TOKEN=prefixed-token\n"
        "SENTINEL_TELEGRAM_CHAT_ID=prefixed-chat\n",
    )
    monkeypatch.setattr(dispatcher_module, "_env_file_candidates", lambda: [env_file])
    assert approval_dispatcher.telegram_bot_token == "prefixed-token"
    assert approval_dispatcher.telegram_chat_id == "prefixed-chat"


def test_unconfigured_returns_none(monkeypatch, tmp_path):
    missing = tmp_path / "does-not-exist.env"
    monkeypatch.setattr(dispatcher_module, "_env_file_candidates", lambda: [missing])
    assert approval_dispatcher.telegram_bot_token is None
    assert approval_dispatcher.telegram_chat_id is None
    assert approval_dispatcher.discord_webhook_url is None


def test_dispatch_sends_telegram_when_file_configured(monkeypatch, tmp_path):
    env_file = _write_env(
        tmp_path,
        "TELEGRAM_BOT_TOKEN=file-token\nTELEGRAM_CHAT_ID=file-chat\n",
    )
    monkeypatch.setattr(dispatcher_module, "_env_file_candidates", lambda: [env_file])
    sent = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        sent.append(req)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    pending = approval_dispatcher.submit_approval(
        agent_name="TEST",
        action="cred-resolution-drill",
        details={"test": True},
    )
    assert pending.status.value == "PENDING"
    assert len(sent) == 1
    assert sent[0].full_url == "https://api.telegram.org/botfile-token/sendMessage"
    payload = json.loads(sent[0].data.decode("utf-8"))
    assert payload["chat_id"] == "file-chat"


def test_dispatch_queues_without_sending_when_unconfigured(monkeypatch, tmp_path):
    missing = tmp_path / "does-not-exist.env"
    monkeypatch.setattr(dispatcher_module, "_env_file_candidates", lambda: [missing])

    def fail_urlopen(req, timeout=None):
        raise AssertionError("urlopen must not be called when unconfigured")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    pending = approval_dispatcher.submit_approval(
        agent_name="TEST",
        action="unconfigured-drill",
        details={"test": True},
    )
    assert pending.status.value == "PENDING"
