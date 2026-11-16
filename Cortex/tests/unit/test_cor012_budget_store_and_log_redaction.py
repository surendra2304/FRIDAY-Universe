"""TASK-COR-012 — the two defects the 2026-11-17 breach drill found live.

F1: ``DatabaseBudgetStore`` saves were not durable in production. The
store runs its I/O on its own thread's event loop, but on the default
path it borrowed the app's pooled ``AsyncSessionLocal`` — whose
connections carry futures bound to the app loop — so every save from the
request path died with ``RuntimeError: got Future attached to a
different loop`` (drill: save_errors=1, ``agent_budget_state`` had 0
rows, the breach pause lived only in the process mirror). The fix gives
the store its own ``NullPool`` engine built from the app DSN. The
aiosqlite driver tolerates cross-loop pool reuse, so the production
failure is modelled here by a loop-bound stand-in factory: usable on
its owning thread, raising the production error anywhere else — which
is exactly how the borrowed app factory behaved for the store.

F2: httpx's INFO logger prints full request URLs; the escalation
webhook URL (Telegram ``sendMessage``) embeds the bot token, so the
token reached Cortex's journal even though PR #820 kept it out of
persisted records. The fix is a redaction filter on the httpx/httpcore
loggers, installed at API startup.
"""

from __future__ import annotations

import asyncio
import logging
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import cortex_api.config as config
from cortex_api.agent_budgets import DatabaseBudgetStore
from cortex_api.db_models import AgentBudgetStateModel
from cortex_core.resilience import (
    SecretUrlRedactionFilter,
    install_secret_url_log_redaction,
    redact_secret_urls,
)

# Assembled at runtime so no literal token shape sits in the source
# (the secrets scanner cannot tell a fixture token from a real one).
TOKEN = "123456789:" + "AAE" + "x" * 31
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

STATE = {"usage": {"Cortex": {"tokens": 750001, "tasks": 0}}, "marker": "cor012"}


# ── F1: the default store path owns its engine ─────────────────────────


class _LoopBoundFactory:
    """Stand-in for the production app session factory.

    Works only on the thread that created it (the "app loop"); any use
    from another thread raises the exact production error. Wraps a real
    factory so that, if the store ever did use it on the owning thread,
    the I/O itself would succeed — the failure is purely the binding.
    """

    def __init__(self, real_factory):
        self._real = real_factory
        self._owner = threading.get_ident()

    def __call__(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("got Future attached to a different loop")
        return self._real()


def _create_budget_table(dsn: str) -> None:
    async def _create() -> None:
        engine = create_async_engine(dsn, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda c: AgentBudgetStateModel.__table__.create(c, checkfirst=True)
            )
        await engine.dispose()

    asyncio.run(_create())


def test_default_store_does_not_borrow_the_app_factory():
    store = DatabaseBudgetStore()
    assert store._factory() is not config.AsyncSessionLocal


def test_default_store_saves_despite_loop_bound_app_factory(tmp_path, monkeypatch):
    dsn = f"sqlite+aiosqlite:///{tmp_path}/budgets.db"
    _create_budget_table(dsn)

    real_factory = async_sessionmaker(
        create_async_engine(dsn, poolclass=NullPool), expire_on_commit=False
    )
    monkeypatch.setattr(config, "AsyncSessionLocal", _LoopBoundFactory(real_factory))
    monkeypatch.setattr(config.settings, "postgres_dsn", dsn)

    store = DatabaseBudgetStore()  # default path — no injected factory

    # The request path is never the store's loop: save from a worker thread.
    failures: list[BaseException] = []

    def _save() -> None:
        try:
            store.save(STATE)
        except BaseException as exc:  # noqa: BLE001 - asserted below
            failures.append(exc)

    worker = threading.Thread(target=_save)
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive()
    assert failures == []

    status = store.status()
    assert status["save_errors"] == 0
    assert status["durable"] is True

    # A fresh store (a "restart") reads the state back from the database,
    # not from any in-process mirror.
    store2 = DatabaseBudgetStore()
    assert store2.load() == STATE
    assert store2.status()["load_errors"] == 0


def test_default_store_actually_writes_a_row(tmp_path, monkeypatch):
    dsn = f"sqlite+aiosqlite:///{tmp_path}/budgets.db"
    _create_budget_table(dsn)
    monkeypatch.setattr(config.settings, "postgres_dsn", dsn)

    store = DatabaseBudgetStore()
    store.save(STATE)
    assert store.status()["durable"] is True

    async def _count() -> int:
        engine = create_async_engine(dsn, poolclass=NullPool)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM agent_budget_state")
            )
            count = int(result.scalar_one())
        await engine.dispose()
        return count

    assert asyncio.run(_count()) == 1


# ── F2: bot tokens never reach a log sink ──────────────────────────────


def test_redact_secret_urls_covers_telegram_url_and_bare_token():
    line = f'HTTP Request: POST {TELEGRAM_URL} "HTTP/1.1 200 OK"'
    redacted = redact_secret_urls(line)
    assert TOKEN not in redacted
    assert "api.telegram.org/bot***" in redacted
    assert "sendMessage" in redacted  # the useful part of the line survives

    assert redact_secret_urls(f"delivery failed for bot{TOKEN} retrying") == (
        "delivery failed for bot*** retrying"
    )
    # Non-secret text passes through untouched.
    assert redact_secret_urls("HTTP Request: GET https://example.net/x") == (
        "HTTP Request: GET https://example.net/x"
    )


def test_filter_rewrites_httpx_style_record_with_args():
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='HTTP Request: %s %s "%s %d %s"',
        args=("POST", TELEGRAM_URL, "HTTP/1.1", 200, "OK"),
        exc_info=None,
    )
    assert SecretUrlRedactionFilter().filter(record) is True
    message = record.getMessage()
    assert TOKEN not in message
    assert "api.telegram.org/bot***/sendMessage" in message


def test_installed_filter_redacts_real_httpx_logger_output(caplog):
    install_secret_url_log_redaction()
    try:
        with caplog.at_level(logging.INFO, logger="httpx"):
            logging.getLogger("httpx").info(
                'HTTP Request: POST %s "HTTP/1.1 200 OK"', TELEGRAM_URL
            )
    finally:
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.filters = [
            f for f in httpx_logger.filters
            if not isinstance(f, SecretUrlRedactionFilter)
        ]
    assert TOKEN not in caplog.text
    assert "bot***" in caplog.text


def test_install_is_idempotent():
    first = install_secret_url_log_redaction()
    try:
        second = install_secret_url_log_redaction()
        assert first is second
        attached = [
            f for f in logging.getLogger("httpx").filters
            if isinstance(f, SecretUrlRedactionFilter)
        ]
        assert attached == [first]
    finally:
        for name in ("httpx", "httpcore"):
            target = logging.getLogger(name)
            target.filters = [
                f for f in target.filters
                if not isinstance(f, SecretUrlRedactionFilter)
            ]
