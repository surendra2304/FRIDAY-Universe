"""TASK-SEN-022 — Sentinel Telegram channel startup self-check.

The 2026-11-15 silent-failure class: Sentinel booted with no Telegram
credentials in the process environment, logged nothing loud about it,
and the drill's approval prompts / operations alerts reached nobody.
The dispatcher degrades silently by design (it logs a quiet INFO line
per queued approval and carries on), so the failure was invisible until
someone noticed the silence.

This module is the boot-time tripwire. It resolves the Telegram
credentials through exactly the same path the live dispatcher uses
(``ApprovalDispatcher.telegram_bot_token`` / ``telegram_chat_id``:
process environment first, then the fleet .env files), so the check
cannot disagree with dispatch, and it logs a loud CRITICAL banner when
the channel is missing — or an INFO readiness line when it is present.
It never logs credential values, only variable names.

The check never blocks boot: a Sentinel that cannot page the owner
still has to watch the fleet. Visibility, not refusal, is the fix —
with production /ready degrading (see ``sentinel.apps.api.main``) so
the failure is visible to probers as well as to log readers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("sentinel.config.telegram_self_check")

# The credential variables, in the order the dispatcher resolves them
# (process env first, then .env files; see ApprovalDispatcher).
TOKEN_NAMES = ("TELEGRAM_BOT_TOKEN", "SENTINEL_TELEGRAM_BOT_TOKEN")
CHAT_ID_NAMES = ("TELEGRAM_CHAT_ID", "SENTINEL_TELEGRAM_CHAT_ID")


@dataclass(frozen=True, slots=True)
class TelegramChannelReport:
    """Outcome of the Telegram channel self-check at boot."""

    token_present: bool
    chat_id_present: bool
    discord_configured: bool
    missing: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        """True only when Telegram can actually dispatch (token + chat id)."""
        return self.token_present and self.chat_id_present


def check_telegram_channel(dispatcher=None) -> TelegramChannelReport:
    """Resolve the Telegram credentials the way the dispatcher does.

    ``dispatcher`` is injectable for tests; the default is the live
    ``ApprovalDispatcher`` singleton, so the check and dispatch can
    never disagree about what is configured.
    """
    if dispatcher is None:
        from sentinel.gatekeeper.approval_dispatcher import ApprovalDispatcher

        dispatcher = ApprovalDispatcher()
    token_present = bool(dispatcher.telegram_bot_token)
    chat_id_present = bool(dispatcher.telegram_chat_id)
    missing: list[str] = []
    if not token_present:
        missing.append(TOKEN_NAMES[0])
    if not chat_id_present:
        missing.append(CHAT_ID_NAMES[0])
    return TelegramChannelReport(
        token_present=token_present,
        chat_id_present=chat_id_present,
        discord_configured=bool(dispatcher.discord_webhook_url),
        missing=tuple(missing),
    )


def log_telegram_self_check(
    report: TelegramChannelReport, log: logging.Logger | None = None
) -> TelegramChannelReport:
    """Log the self-check verdict loudly. Returns the report unchanged."""
    log = log or logger
    if report.configured:
        log.info(
            "Telegram channel READY for owner alerts "
            "(bot token + chat id resolved; TASK-SEN-022 startup self-check)."
        )
        return report
    missing = ", ".join(report.missing)
    alternatives = ", ".join(
        alias
        for primary, alias in (TOKEN_NAMES, CHAT_ID_NAMES)
        if primary in report.missing
    )
    log.critical(
        "SENTINEL TELEGRAM CHANNEL NOT CONFIGURED — "
        "owner alerts CANNOT be delivered (TASK-SEN-022 startup self-check). "
        f"Missing: {missing}. "
        "Set them in the process environment or the fleet .env file "
        f"(alternatives: {alternatives}). "
        "Approval prompts and operations alerts will be queued and logged only — "
        "the 2026-11-15 silent-failure class. "
        f"Discord fallback configured: {report.discord_configured}."
    )
    return report


def verify_telegram_channel_at_startup(
    log: logging.Logger | None = None,
) -> TelegramChannelReport:
    """The one-call boot entry: check the channel, log the verdict loudly."""
    return log_telegram_self_check(check_telegram_channel(), log=log)
