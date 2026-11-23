"""TASK-SEN-022 — Sentinel Telegram channel startup self-check tests.

Covers sentinel/config/telegram_self_check.py: missing credentials fail
loudly (CRITICAL, names the missing variables, never the values);
present credentials log readiness; the check resolves through the same
path the live dispatcher uses (process env, then .env files). No live
Telegram call is made — presence, not delivery, is what the 2026-11-15
class got wrong. The /ready wiring lives in
Sentinel/tests/unit/test_sen022_telegram_self_check.py.
"""
from __future__ import annotations

import logging

import pytest
from sentinel.config.telegram_self_check import (
    check_telegram_channel,
    log_telegram_self_check,
    verify_telegram_channel_at_startup,
)
from sentinel.gatekeeper import approval_dispatcher as dispatch_mod

TOKEN = "TELEGRAM_BOT_TOKEN"
CHAT = "TELEGRAM_CHAT_ID"
DISCORD = "DISCORD_WEBHOOK_URL"
ENV_FILE = "SENTINEL_ENV_FILE"

FAKE_TOKEN = "tok-TEST-VALUE-12345"
FAKE_CHAT = "chat-TEST-VALUE-67890"


@pytest.fixture()
def isolated(monkeypatch, tmp_path):
    """Fully controlled credential resolution for one test.

    Clears every Telegram variable from the process env, points the
    .env-file search at a single tmp file, and resets the dispatcher's
    file-env cache before and after.
    """
    env_file = tmp_path / "sentinel-test.env"
    env_file.write_text("", encoding="utf-8")
    for name in (TOKEN, CHAT, "SENTINEL_TELEGRAM_BOT_TOKEN",
                 "SENTINEL_TELEGRAM_CHAT_ID", DISCORD, ENV_FILE):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(ENV_FILE, str(env_file))
    monkeypatch.setattr(dispatch_mod, "_env_file_candidates", lambda: [env_file])
    dispatch_mod._FILE_ENV_CACHE = None
    yield env_file
    dispatch_mod._FILE_ENV_CACHE = None


def _set_env(monkeypatch, **values):
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_missing_both_fails_loudly(isolated, monkeypatch, caplog):
    with caplog.at_level(logging.CRITICAL, logger="sentinel.config.telegram_self_check"):
        report = verify_telegram_channel_at_startup()
    assert report.configured is False
    assert report.token_present is False
    assert report.chat_id_present is False
    assert report.missing == (TOKEN, CHAT)
    assert "CRITICAL" in caplog.text
    assert "TELEGRAM CHANNEL NOT CONFIGURED" in caplog.text
    assert TOKEN in caplog.text and CHAT in caplog.text
    assert "2026-11-15" in caplog.text


def test_token_only_still_fails(isolated, monkeypatch, caplog):
    _set_env(monkeypatch, **{TOKEN: FAKE_TOKEN})
    with caplog.at_level(logging.CRITICAL, logger="sentinel.config.telegram_self_check"):
        report = check_telegram_channel()
        log_telegram_self_check(report)
    assert report.configured is False
    assert report.token_present is True
    assert report.chat_id_present is False
    assert report.missing == (CHAT,)
    assert FAKE_TOKEN not in caplog.text  # values are never logged
    assert "TELEGRAM CHANNEL NOT CONFIGURED" in caplog.text


def test_chat_only_still_fails(isolated, monkeypatch):
    _set_env(monkeypatch, **{CHAT: FAKE_CHAT})
    report = check_telegram_channel()
    assert report.configured is False
    assert report.token_present is False
    assert report.chat_id_present is True
    assert report.missing == (TOKEN,)


def test_both_present_via_env_logs_readiness(isolated, monkeypatch, caplog):
    _set_env(monkeypatch, **{TOKEN: FAKE_TOKEN, CHAT: FAKE_CHAT})
    with caplog.at_level(logging.INFO, logger="sentinel.config.telegram_self_check"):
        report = verify_telegram_channel_at_startup()
    assert report.configured is True
    assert report.missing == ()
    assert "Telegram channel READY" in caplog.text
    assert FAKE_TOKEN not in caplog.text
    assert FAKE_CHAT not in caplog.text


def test_both_present_via_env_file(monkeypatch, tmp_path, caplog):
    # The real .env-file path (no candidate monkeypatching): the
    # SENTINEL_ENV_FILE override is read when the env holds nothing.
    env_file = tmp_path / "sentinel.env"
    env_file.write_text(
        f"{TOKEN}={FAKE_TOKEN}\n{CHAT}={FAKE_CHAT}\n", encoding="utf-8")
    for name in (TOKEN, CHAT, "SENTINEL_TELEGRAM_BOT_TOKEN",
                 "SENTINEL_TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(ENV_FILE, str(env_file))
    dispatch_mod._FILE_ENV_CACHE = None
    # TEMP-DIAG (TASK-SEN-022 re-check): this test fails in the full
    # tests/ suite but passes standalone. Dump the resolution state
    # (keys only, never values) so the next CI run shows which link
    # breaks. Remove once the cause is known.
    import os as _os
    import sys as _sys
    _live = _sys.modules.get("sentinel.gatekeeper.approval_dispatcher")
    print("SEN022-DIAG dispatch_mod file:", dispatch_mod.__file__)
    print("SEN022-DIAG live module is dispatch_mod:", _live is dispatch_mod)
    print("SEN022-DIAG live module file:", getattr(_live, "__file__", None))
    print("SEN022-DIAG SENTINEL_ENV_FILE:", _os.environ.get(ENV_FILE))
    print("SEN022-DIAG candidates fn:",
          getattr(dispatch_mod._env_file_candidates, "__name__", "?"))
    print("SEN022-DIAG candidates:",
          [str(p) for p in dispatch_mod._env_file_candidates()])
    print("SEN022-DIAG dispatch cache after reset:",
          dispatch_mod._FILE_ENV_CACHE)
    print("SEN022-DIAG live cache:",
          None if _live is None or _live._FILE_ENV_CACHE is None
          else sorted(_live._FILE_ENV_CACHE.keys()))
    print("SEN022-DIAG live candidates fn:",
          getattr(_live._env_file_candidates, "__name__", "?")
          if _live is not None else None)
    try:
        with caplog.at_level(logging.INFO, logger="sentinel.config.telegram_self_check"):
            report = verify_telegram_channel_at_startup()
        assert report.configured is True
        assert "Telegram channel READY" in caplog.text
        assert FAKE_TOKEN not in caplog.text
    finally:
        dispatch_mod._FILE_ENV_CACHE = None


def test_discord_does_not_rescue_telegram(isolated, monkeypatch, caplog):
    _set_env(monkeypatch, **{DISCORD: "https://discord.example/hooks/test"})
    with caplog.at_level(logging.CRITICAL, logger="sentinel.config.telegram_self_check"):
        report = verify_telegram_channel_at_startup()
    assert report.configured is False
    assert report.discord_configured is True
    assert "Discord fallback configured: True" in caplog.text
    assert "TELEGRAM CHANNEL NOT CONFIGURED" in caplog.text


def test_injected_dispatcher_is_used():
    class Stub:
        telegram_bot_token = "stub-token"
        telegram_chat_id = None
        discord_webhook_url = None

    report = check_telegram_channel(dispatcher=Stub())
    assert report.configured is False
    assert report.missing == (CHAT,)

    class ReadyStub:
        telegram_bot_token = "stub-token"
        telegram_chat_id = "stub-chat"
        discord_webhook_url = None

    assert check_telegram_channel(dispatcher=ReadyStub()).configured is True
