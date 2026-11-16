"""Recent-failover event log for Inference (TASK-IG2-INF-03).

The quota ledger (:mod:`app.providers.quota_ledger`) counts attempts; the
health tracker (:mod:`app.providers.health`) scores providers; neither
answers the operator's simplest question — *"what just failed over, from
where, and why?"* — which is exactly the question asked every time quota
exhaustion has surfaced as a mysterious agent failure.

This module is the missing piece: a bounded, thread-safe, in-memory ring
buffer that :meth:`app.providers.gateway.ModelGateway._execute_dynamic_fallback`
records one event into per ladder escalation. It is served, read-only, on
the admin dashboard (:mod:`app.routers.admin_dashboard`).

Honesty bounds: events cover **this process only**, since it started, up to
the ring capacity (oldest events are dropped silently — the snapshot says
how many were dropped). Reasons are truncated and credential-scrubbed by
the gateway before they arrive here; this module never sees a key.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

MAX_EVENTS = 200
_REASON_CAP = 300


class FailoverLog:
    """Bounded ring buffer of gateway fallback escalations."""

    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._dropped = 0
        self._lock = threading.Lock()

    def record(
        self,
        *,
        from_provider: str,
        reason: str | None,
        model: str | None = None,
        capability: str | None = None,
        stage_name: str | None = None,
        ts: float | None = None,
    ) -> None:
        """Record one escalation into the fallback ladder. Never raises."""
        try:
            when = time.time() if ts is None else float(ts)
            event = {
                "ts": when,
                "at_utc": datetime.fromtimestamp(when, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "from_provider": (from_provider or "unknown").lower().strip(),
                "model": model,
                "capability": capability,
                "stage_name": stage_name,
                "reason": (reason or "")[:_REASON_CAP] or None,
            }
            with self._lock:
                if len(self._events) == self._events.maxlen:
                    self._dropped += 1
                self._events.append(event)
        except Exception:  # noqa: BLE001 - observability must never break serving
            pass

    def snapshot(self, limit: int = 20) -> dict[str, Any]:
        """Newest-first recent events plus coverage metadata."""
        with self._lock:
            events = list(reversed(self._events))[: max(0, limit)]
            return {
                "events": events,
                "events_retained": len(self._events),
                "events_dropped_oldest": self._dropped,
                "capacity": self._events.maxlen,
                "basis": (
                    "Fallback escalations recorded by this Inference process since it "
                    "started. In-memory only: a restart clears the log, and events past "
                    "capacity drop oldest-first."
                ),
            }


#: Process-wide singleton; the gateway records into this instance.
failover_log = FailoverLog()
