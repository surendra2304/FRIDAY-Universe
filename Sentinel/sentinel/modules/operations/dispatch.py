"""Operations alert dispatch for Sentinel (TASK-SEN-008).

Before this module existed, operations alerts were a dead end: the
operations ``AlertEngine`` stored alerts in an in-memory dict, its
``register_webhook`` was never called anywhere, and ``process_delta`` never
dispatched anything — no human ever saw a detection-side alert.

This dispatcher wires operations alerts into the SAME human-notification
channel as guarded-action approvals: it sends through
``ApprovalDispatcher.dispatch_notification``, which carries the credential
resolution fixed by TASK-SEN-006 (process environment first, then the fleet
.env files) and the Telegram/Discord transports. One channel configuration
now serves both Sentinel alerting paths.

Behaviour when no channel is configured mirrors the approval path: the
alert is logged as QUEUED (a journal line) and dispatch reports
``queued: True`` — visible, honest, and non-fatal. Registered AlertEngine
webhooks are also delivered here (JSON POST of the alert model).
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from sentinel.gatekeeper.approval_dispatcher import approval_dispatcher
from sentinel.modules.operations.alerting import Alert

logger = logging.getLogger("sentinel.operations.dispatch")

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}

_SEVERITY_COLOR = {
    "critical": 15158332,
    "high": 16753920,
    "medium": 16776960,
    "low": 3447003,
    "info": 9807270,
}


def format_alert_telegram(alert: Alert) -> str:
    """Render an operations alert as a Telegram HTML message."""
    emoji = _SEVERITY_EMOJI.get(alert.severity.value.lower(), "⚪")
    return (
        f"{emoji} <b>SENTINEL OPERATIONS ALERT</b>\n\n"
        f"<b>Severity:</b> {alert.severity.value.upper()}\n"
        f"<b>Target:</b> <code>{alert.target_ref}</code>\n"
        f"<b>Change:</b> {alert.change_type.value}\n"
        f"<b>Alert:</b> <code>{alert.alert_id}</code>\n"
        f"<b>Detail:</b> {alert.message}\n"
    )


def format_alert_discord(alert: Alert) -> dict[str, Any]:
    """Render an operations alert as a Discord webhook payload."""
    emoji = _SEVERITY_EMOJI.get(alert.severity.value.lower(), "⚪")
    return {
        "content": f"{emoji} **SENTINEL OPERATIONS ALERT**",
        "embeds": [
            {
                "title": alert.title,
                "description": alert.message[:1000],
                "fields": [
                    {"name": "Target", "value": f"`{alert.target_ref}`", "inline": True},
                    {"name": "Change", "value": alert.change_type.value, "inline": True},
                    {"name": "Alert ID", "value": f"`{alert.alert_id}`", "inline": True},
                ],
                "color": _SEVERITY_COLOR.get(alert.severity.value.lower(), 9807270),
            }
        ],
    }


class OperationsAlertDispatcher:
    """Dispatches operations alerts to the shared human channel + webhooks."""

    def __init__(self, channel=None):
        # `channel` is the ApprovalDispatcher singleton by default; injectable
        # for tests. All credential resolution lives in the channel (SEN-006).
        self._channel = channel if channel is not None else approval_dispatcher

    @property
    def channel_configured(self) -> bool:
        return bool(getattr(self._channel, "channel_configured", False))

    def dispatch(self, alert: Alert, webhook_urls: list[str] | None = None) -> dict[str, Any]:
        """Dispatch one newly-created alert. Never raises.

        Returns a result map: per-channel booleans for telegram/discord,
        a list of webhook URLs that accepted the POST, and ``queued`` —
        True when no human channel is configured (the alert then exists
        only in the engine + journal, exactly like an unconfigured
        approval, and the journal line says so).
        """
        result: dict[str, Any] = {
            "telegram": False,
            "discord": False,
            "webhooks": [],
            "queued": False,
        }

        if self.channel_configured:
            try:
                sent = self._channel.dispatch_notification(
                    format_alert_telegram(alert),
                    discord_payload=format_alert_discord(alert),
                )
                result["telegram"] = bool(sent.get("telegram"))
                result["discord"] = bool(sent.get("discord"))
            except Exception as e:  # transport layer already swallows; belt & braces
                logger.warning("Operations alert channel dispatch error: %s", e)
            if result["telegram"] or result["discord"]:
                logger.info(
                    "[SENTINEL OPERATIONS ALERT DISPATCHED] %s (%s on %s) via %s",
                    alert.alert_id,
                    alert.change_type.value,
                    alert.target_ref,
                    "+".join(k for k in ("telegram", "discord") if result[k]),
                )
            else:
                logger.warning(
                    "[SENTINEL OPERATIONS ALERT FAILED] %s (%s on %s): channel configured "
                    "but every transport failed",
                    alert.alert_id,
                    alert.change_type.value,
                    alert.target_ref,
                )
        else:
            result["queued"] = True
            logger.info(
                "[SENTINEL OPERATIONS ALERT QUEUED] %s (%s on %s). "
                "(Alerts ready: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or "
                "DISCORD_WEBHOOK_URL, in the process environment or a fleet .env file "
                "when desired.)",
                alert.alert_id,
                alert.change_type.value,
                alert.target_ref,
            )

        for url in webhook_urls or []:
            if self._send_webhook(url, alert):
                result["webhooks"].append(url)

        return result

    def _send_webhook(self, url: str, alert: Alert) -> bool:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(alert.model_dump(mode="json")).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5.0)
            return True
        except Exception as e:
            logger.warning("Operations alert webhook dispatch error (%s): %s", url, e)
            return False


# Shared dispatcher instance wired into the global AlertEngine by the API
# lifespan (see sentinel.apps.api.main) and usable directly in tests/tools.
operations_dispatcher = OperationsAlertDispatcher()
