"""Per-model servability tracking for Inference routing (TASK-REL-049).

Why this exists
---------------
TASK-INF-005 measured the production gateway for a full day and found
``gemini-3.8-flash`` serving **0 of 20 requests** — every request naming
it was substituted after a ~10–75s cascade — while the Gemini *provider*
stayed healthy (``gemini-3.6-flash`` served throughout). Every piece of
outcome recording in the gateway is provider-granular
(:class:`app.providers.health.ProviderHealthTracker`,
``app/governance/circuit_breaker.py``, ``app/optimization.py`` all key on
provider name), so a model-level failure of exactly this shape is
invisible to routing: TASK-REL-043's best-suitable selection filters by
``_provider_available`` (provider health), the never-serving model kept
its #1 chat ranking, and every request paid the cascade again.

This tracker is the model-level counterpart of the provider health
tracker. It records, per catalogue model, the outcomes the route layer
can actually observe from ``UnifiedExecutionResponse``:

- ``served`` — the model was attempted and produced the answer itself;
- ``substituted`` — the model was attempted but the gateway ladder
  served a different model;
- ``failed`` — the attempt came back degraded (no model answered).

The quarantine rule (declared, and justified by the INF-005 evidence)
--------------------------------------------------------------------
A model is quarantined after **10 consecutive non-serves** (substituted
or failed outcomes with no intervening serve). INF-005's model produced
15 in a row in the main window and 5 more in a second window hours
later; a streak of 10 full gateway executions — each one a real,
deadline-bound provider attempt, not a cheap health ping — with zero
serves is decisive model-level evidence, and it cannot be produced by
ordinary flakiness (a model that serves even intermittently resets the
streak). No time-span floor is imposed: the streak itself is the
evidence, and the probe-back below bounds the cost of a wrong call.

Quarantine is an *availability overlay* on selection, never a quality
judgement: it does not edit REL-043's ``MODEL_SUITABILITY`` rankings, so
a quarantined model keeps its rank and resumes it the moment it serves
again. While quarantined, a model becomes eligible for a **probe** every
``probe_interval_seconds`` (default 900s): selection may pick it once
(half-open, in the circuit-breaker sense the provider health tracker
already uses), and the probe's outcome decides — a serve clears the
quarantine immediately; a miss re-arms the probe clock.

State is in-process, like the provider health tracker: a restart clears
it, and 10 fresh consecutive non-serves re-latch it. Outcomes from the
streaming route are not recorded — the chunk protocol never reveals
which model actually served — so the tracker is fed by the non-streaming
route, which carries the chat/escalation traffic this failure mode was
measured on.
"""

from __future__ import annotations

import os
import time
from collections import deque
from typing import Any, Callable

SERVED = "served"
SUBSTITUTED = "substituted"
FAILED = "failed"
_OUTCOMES = (SERVED, SUBSTITUTED, FAILED)


def _env_int(name: str, default: int) -> int:
    """Read a positive-int tuning knob from the environment, fail safe."""
    try:
        value = int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


class ModelServabilityTracker:
    """Rolling per-model serve/substitute/fail tracking with quarantine.

    Parameters are injectable for tests; production uses the module
    singleton below, tuned by the ``INFERENCE_MODEL_QUARANTINE_*`` /
    ``INFERENCE_MODEL_PROBE_INTERVAL_S`` environment variables.
    """

    def __init__(
        self,
        *,
        min_consecutive_misses: int = 10,
        window_seconds: float = 6 * 3600.0,
        probe_interval_seconds: float = 900.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.min_consecutive_misses = max(1, int(min_consecutive_misses))
        self.window_seconds = float(window_seconds)
        self.probe_interval_seconds = float(probe_interval_seconds)
        self._clock = clock or time.time
        self._events: dict[str, deque[tuple[float, str]]] = {}
        self._quarantined_since: dict[str, float] = {}
        self._last_probe_at: dict[str, float] = {}

    # -- internals ------------------------------------------------------

    @staticmethod
    def _norm(model_id: str | None) -> str:
        return (model_id or "").strip().lower()

    def _now(self, now: float | None) -> float:
        return self._clock() if now is None else float(now)

    def _prune(self, model: str, now: float) -> None:
        events = self._events.get(model)
        if not events:
            return
        cutoff = now - self.window_seconds
        while events and events[0][0] < cutoff:
            events.popleft()

    def _consecutive_misses(self, model: str) -> int:
        streak = 0
        for _ts, outcome in reversed(self._events.get(model, ())):
            if outcome == SERVED:
                break
            streak += 1
        return streak

    # -- recording ------------------------------------------------------

    def record_outcome(self, model_id: str | None, outcome: str, *, now: float | None = None) -> None:
        """Record one observed outcome for a model.

        ``served`` clears any quarantine (a serve is direct evidence the
        model answers again, whatever its history). A miss while
        quarantined counts as that period's probe attempt and re-arms
        the probe clock. A miss while healthy extends the consecutive
        streak; reaching ``min_consecutive_misses`` latches quarantine.
        """
        model = self._norm(model_id)
        if not model or outcome not in _OUTCOMES:
            return
        ts = self._now(now)
        events = self._events.setdefault(model, deque())
        events.append((ts, outcome))
        self._prune(model, ts)
        if outcome == SERVED:
            self._quarantined_since.pop(model, None)
            self._last_probe_at.pop(model, None)
            return
        if model in self._quarantined_since:
            self._last_probe_at[model] = ts
            return
        if self._consecutive_misses(model) >= self.min_consecutive_misses:
            self._quarantined_since[model] = ts
            self._last_probe_at[model] = ts

    def record_serve(self, model_id: str | None, *, now: float | None = None) -> None:
        """Record that a model produced an answer (e.g. as a ladder substitute)."""
        self.record_outcome(model_id, SERVED, now=now)

    # -- queries ----------------------------------------------------------

    def is_quarantined(self, model_id: str | None) -> bool:
        return self._norm(model_id) in self._quarantined_since

    def probe_due(self, model_id: str | None, *, now: float | None = None) -> bool:
        """Whether a quarantined model is due its next half-open probe."""
        model = self._norm(model_id)
        since = self._quarantined_since.get(model)
        if since is None:
            return False
        last_probe = max(since, self._last_probe_at.get(model, since))
        return self._now(now) - last_probe >= self.probe_interval_seconds

    def selection_view(self, model_id: str | None, *, now: float | None = None) -> dict[str, Any]:
        """The model's servability state, in the shape routing metadata carries."""
        model = self._norm(model_id)
        ts = self._now(now)
        self._prune(model, ts)
        events = self._events.get(model, ())
        serves = sum(1 for _t, outcome in events if outcome == SERVED)
        quarantined = model in self._quarantined_since
        next_probe_at = None
        if quarantined:
            since = self._quarantined_since[model]
            last_probe = max(since, self._last_probe_at.get(model, since))
            next_probe_at = last_probe + self.probe_interval_seconds
        return {
            "model": model,
            "attempts": len(events),
            "serves": serves,
            "misses": len(events) - serves,
            "consecutive_misses": self._consecutive_misses(model),
            "quarantined": quarantined,
            "probe_due": self.probe_due(model, now=ts),
            "quarantined_since": self._quarantined_since.get(model),
            "next_probe_at": next_probe_at,
        }

    def snapshot(self, *, now: float | None = None) -> dict[str, dict[str, Any]]:
        """Servability state for every model with recorded outcomes."""
        models = set(self._events) | set(self._quarantined_since)
        return {model: self.selection_view(model, now=now) for model in sorted(models)}

    def reset(self) -> None:
        """Clear all tracked state (test isolation)."""
        self._events.clear()
        self._quarantined_since.clear()
        self._last_probe_at.clear()


def _default_tracker() -> ModelServabilityTracker:
    return ModelServabilityTracker(
        min_consecutive_misses=_env_int("INFERENCE_MODEL_QUARANTINE_MIN_MISSES", 10),
        window_seconds=float(_env_int("INFERENCE_MODEL_QUARANTINE_WINDOW_S", 6 * 3600)),
        probe_interval_seconds=float(_env_int("INFERENCE_MODEL_PROBE_INTERVAL_S", 900)),
    )


# Global singleton instance — the model-level counterpart of
# app.providers.health.provider_health_tracker.
model_servability_tracker = _default_tracker()
