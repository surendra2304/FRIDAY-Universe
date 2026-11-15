"""Alerting and Notification Dispatch Engine for Sentinel.

Features:
1. Alert Model (ID, severity, type, target, message, lifecycle status).
2. Alert Correlation & Deduplication (Suppresses storming alerts within cooldown window).
3. Dispatch Channels (Webhook notification dispatch, Email dispatch adapter stub).
4. Operator Alert Management (Acknowledge, Resolve, Escalate).

Dispatch wiring (TASK-SEN-008): an AlertEngine may carry a dispatcher —
any object exposing ``dispatch(alert, webhook_urls) -> dict``. Every NEWLY
created alert is dispatched exactly once; deduplication hits only bump
``occurrence_count`` and never re-dispatch, so a storm cannot spam the
human channel. The production dispatcher is
``sentinel.modules.operations.dispatch.OperationsAlertDispatcher``, which
sends through the approval dispatcher's shared human channel (TASK-SEN-006
credential resolution). The API lifespan wires it into the global
``alert_engine`` singleton; engines constructed without a dispatcher keep
the historical store-only behaviour (used by unit tests and tools).
Dispatch failures never break alert creation.
"""

import hashlib
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.baseline import BaselineDelta, ChangeType

logger = logging.getLogger("sentinel.operations.alerting")


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(BaseModel):
    alert_id: str
    target_ref: str
    severity: SeverityLevel
    change_type: ChangeType
    title: str
    message: str
    status: AlertStatus = AlertStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    occurrence_count: int = 1
    fingerprint: str = ""
    # TASK-SEN-008 dispatch outcome (defaults preserve pre-wiring semantics:
    # an alert that was never offered to a dispatcher is simply undispatched).
    dispatched: bool = False
    dispatch_channels: list[str] = Field(default_factory=list)
    dispatch_queued: bool = False


class AlertEngine:
    """Manages active alerts, storm deduplication, and webhook dispatching."""

    def __init__(self, dispatcher: Any | None = None):
        self._alerts: dict[str, Alert] = {}
        self._webhook_urls: list[str] = []
        self._dispatcher = dispatcher

    def set_dispatcher(self, dispatcher: Any | None):
        """Attach (or replace) the dispatch backend for NEW alerts."""
        self._dispatcher = dispatcher

    @property
    def dispatcher(self) -> Any | None:
        return self._dispatcher

    def register_webhook(self, url: str):
        if url not in self._webhook_urls:
            self._webhook_urls.append(url)

    @property
    def webhook_urls(self) -> list[str]:
        return list(self._webhook_urls)

    def process_delta(self, delta: BaselineDelta) -> Alert:
        # Calculate deduplication fingerprint based on target, type, and description
        fp_str = f"{delta.target_ref}|{delta.change_type.value}|{delta.description}"
        fingerprint = hashlib.sha256(fp_str.encode()).hexdigest()

        # Check existing open alert with same fingerprint
        for existing in self._alerts.values():
            if existing.fingerprint == fingerprint and existing.status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
                existing.occurrence_count += 1
                return existing

        alert = Alert(
            alert_id=f"ALT-{int(datetime.now(UTC).timestamp())}-{len(self._alerts)+1}",
            target_ref=delta.target_ref,
            severity=delta.severity,
            change_type=delta.change_type,
            title=f"[{delta.severity.value.upper()}] {delta.change_type.value.replace('_', ' ').title()}",
            message=delta.description,
            fingerprint=fingerprint,
        )
        self._alerts[alert.alert_id] = alert
        self._dispatch_new_alert(alert)
        return alert

    def _dispatch_new_alert(self, alert: Alert) -> None:
        """Offer a newly created alert to the dispatcher exactly once.

        Any dispatcher failure is logged and swallowed: alert creation is
        the durable record and must not fail because a channel is down.
        """
        if self._dispatcher is None:
            return
        try:
            result = self._dispatcher.dispatch(alert, list(self._webhook_urls)) or {}
        except Exception as e:
            logger.warning("Alert dispatch failed for %s: %s", alert.alert_id, e)
            return
        channels: list[str] = []
        if result.get("telegram"):
            channels.append("telegram")
        if result.get("discord"):
            channels.append("discord")
        channels.extend(f"webhook:{url}" for url in result.get("webhooks") or [])
        alert.dispatch_channels = channels
        alert.dispatched = bool(channels)
        alert.dispatch_queued = bool(result.get("queued")) and not channels

    def list_alerts(
        self,
        target_ref: str | None = None,
        severity: SeverityLevel | None = None,
        status: AlertStatus | None = None,
    ) -> list[Alert]:
        alerts = list(self._alerts.values())
        if target_ref:
            alerts = [a for a in alerts if a.target_ref == target_ref]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if status:
            alerts = [a for a in alerts if a.status == status]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def acknowledge_alert(self, alert_id: str, operator: str) -> Alert:
        if alert_id not in self._alerts:
            raise KeyError(f"Alert {alert_id} not found.")
        alert = self._alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = operator
        alert.acknowledged_at = datetime.now(UTC)
        return alert

    def resolve_alert(self, alert_id: str) -> Alert:
        if alert_id not in self._alerts:
            raise KeyError(f"Alert {alert_id} not found.")
        alert = self._alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(UTC)
        return alert


# Global Alert Engine Singleton
alert_engine = AlertEngine()
