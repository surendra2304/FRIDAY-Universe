"""Bytez free-tier guardrails for Inference (TASK-INF-039).

Adapts Bytez (scouted-repos card ``bytez.md``, verdict: adapt) one step
further than the TASK-IG2-INF-01 adapter: the adapter proved Bytez *can*
be called, but three properties of its documented $0 tier were still
unenforced at the call site, and each one is a way to silently burn the
free tier or misrecord what happened:

1. **One concurrent request.** The $0 tier allows a single concurrent
   request (Bytez billing docs, 2026-11-16). The gateway's per-provider
   rate limiter caps Bytez at 4 concurrent (``ModelGateway`` builds every
   provider's limiter with ``max_concurrency=4``), and the adapter itself
   had no guard at all — so concurrent gateway requests could put up to
   four simultaneous calls on a one-at-a-time tier and draw 429s. This
   module holds a process-wide, one-slot semaphore around every Bytez
   ``generate``/``stream`` call; a caller that cannot get the slot within
   ``BYTEZ_SLOT_WAIT_SECONDS`` (default 5 s) fails fast with
   :class:`BytezSlotBusyError` (a :class:`TimeoutError`), which the gateway
   takes through its timeout branch and escalates to the fallback ladder
   — the request is still served, by the next rung.
2. **Served-model identity.** Bytez is an aggregator: it routes to hosted
   open models, so the model that answers is not necessarily the model
   that was asked for — and ``OpenAICompatibleProvider.generate`` records
   the *requested* model in ``ProviderResponse.model`` without ever
   reading the ``model`` field Bytez returned. A substitution would
   therefore be recorded as the requested model. :func:`verify_served_model`
   compares the two ids and :func:`annotate_bytez_response` records the
   verdict in ``raw_response["bytez"]`` (requested / served / outcome)
   and logs a warning on mismatch or on a missing served id. The response
   is still returned — the content is usable — but ``resp.model`` keeps
   the requested id so gateway quota accounting stays keyed on what was
   asked for; the truth lives in the annotation, not in a silent
   substitution. This is the runtime half of the INF-005 serve-check the
   Bytez candidate spec (``benchmarks/candidates/bytez.json``) calls for.
3. **Free-tier model allowlist.** The adapter lists only <=7B open models
   (``BYTEZ_SUPPORTED_MODELS``), but nothing stopped a caller from asking
   Bytez for a larger, credit-metered model through the rung — paid spend
   through the FREE-only rule's back door. :func:`validate_bytez_model`
   resolves the effective model (``request.model`` or the default) and
   refuses anything outside the allowlist with
   :class:`BytezModelNotAllowedError` (a :class:`ValueError`, which the
   gateway normalises into a non-retryable error and escalates to the
   ladder) before any HTTP call is made and before the concurrency slot
   is taken.

Everything here is inert unless the rung is enabled: the gateway still
refuses Bytez entirely while ``INFERENCE_BYTEZ_RUNG_ENABLED`` is off
(the default), so these guards only ever run after an operator has read
probe reports and switched the rung on (TASK-IG2-INF-01). No live call,
no live key, and no probe traffic is involved in this module — the
empirical volume question stays with ``app.providers.bytez_probe``.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from app.providers.base import ProviderResponse
from app.utils.logger import logger

#: The $0 tier allows exactly one concurrent request (Bytez billing docs,
#: 2026-11-16). Anything above one is a 429 waiting to happen.
BYTEZ_MAX_CONCURRENT = 1

#: How long a caller waits for the single free-tier slot before failing
#: fast to the ladder. Override with BYTEZ_SLOT_WAIT_SECONDS (seconds,
#: float). A non-numeric or negative value falls back to the default.
DEFAULT_SLOT_WAIT_SECONDS = 5.0

_SLOT_WAIT_ENV = "BYTEZ_SLOT_WAIT_SECONDS"


class BytezSlotBusyError(TimeoutError):
    """No free-tier concurrency slot freed within the wait.

    A :class:`TimeoutError`, so the gateway takes its timeout branch and
    escalates to the fallback ladder instead of failing the request.
    """


class BytezModelNotAllowedError(ValueError):
    """The requested model is outside the <=7B free-tier allowlist.

    A :class:`ValueError`, so the gateway normalises it into a
    non-retryable error (no key quarantine, no same-provider retry) and
    escalates to the fallback ladder.
    """


def slot_wait_seconds() -> float:
    """Configured slot wait (env ``BYTEZ_SLOT_WAIT_SECONDS``, default 5 s)."""
    raw = os.environ.get(_SLOT_WAIT_ENV, "").strip()
    if not raw:
        return DEFAULT_SLOT_WAIT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_SLOT_WAIT_SECONDS
    return value if value >= 0 else DEFAULT_SLOT_WAIT_SECONDS


# The slot is process-wide (every BytezProvider instance shares it: the
# gateway builds a fresh provider per call) and is keyed by running event
# loop — asyncio primitives bind to the loop that first uses them, and
# tests (like the gateway) run each case on its own loop, so a semaphore
# bound to a dead loop must be replaced, not reused.
_slot_state: dict[str, Any] = {"loop": None, "semaphore": None}
_slot_state_lock = threading.Lock()


def _bytez_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    with _slot_state_lock:
        if _slot_state["loop"] is not loop or _slot_state["semaphore"] is None:
            _slot_state["loop"] = loop
            _slot_state["semaphore"] = asyncio.Semaphore(BYTEZ_MAX_CONCURRENT)
        return _slot_state["semaphore"]


@asynccontextmanager
async def acquire_bytez_slot(
    wait_seconds: float | None = None,
) -> AsyncIterator[None]:
    """Hold the single Bytez free-tier concurrency slot.

    Fails fast with :class:`BytezSlotBusyError` when the slot does not
    free within ``wait_seconds`` (default: :func:`slot_wait_seconds`).
    The slot is always released, including when the guarded call raises.
    """
    semaphore = _bytez_semaphore()
    timeout = DEFAULT_SLOT_WAIT_SECONDS if wait_seconds is None else wait_seconds
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise BytezSlotBusyError(
            f"Bytez free-tier concurrency slot timed out after {timeout}s "
            "(the $0 tier allows 1 concurrent request); escalating to the "
            "fallback ladder instead of queueing behind paid-tier traffic."
        ) from exc
    try:
        yield
    finally:
        semaphore.release()


def validate_bytez_model(
    model: str | None,
    supported_models: list[str],
    default_model: str,
) -> str:
    """Resolve the effective Bytez model and enforce the free-tier allowlist.

    Returns the model that will actually be requested (``model`` when set,
    else ``default_model``). Raises :class:`BytezModelNotAllowedError`
    when the effective model is outside ``supported_models`` — a larger,
    credit-metered model must never be reachable through the rung, and the
    refusal happens before any HTTP call and before the slot is taken.
    """
    effective = (model or "").strip() or default_model
    if effective not in supported_models:
        raise BytezModelNotAllowedError(
            f"Bytez model {effective!r} is not in the free-tier allowlist "
            f"(<=7B open models only: {', '.join(supported_models)}). "
            "Larger models are credit-metered (paid) and out of bounds under "
            "the FREE-only rule; refusing before any call is made."
        )
    return effective


@dataclass(frozen=True)
class ServedModelVerdict:
    """Outcome of comparing the requested model with the model Bytez served."""

    requested: str | None
    served: str | None
    # "match" | "mismatch" | "unknown" (served id missing from the response).
    outcome: str
    detail: str


def verify_served_model(
    requested: str | None, served: str | None
) -> ServedModelVerdict:
    """Compare the requested model id with the ``model`` Bytez returned.

    Model ids are compared exactly: Bytez serves canonical Hugging Face
    ids, so a case or spelling difference is a different model, not a
    formatting quirk. A missing served id is "unknown", never a match —
    an absent identity proves nothing.
    """
    if not requested or not served:
        return ServedModelVerdict(
            requested=requested,
            served=served,
            outcome="unknown",
            detail=(
                "served model id is missing from the Bytez response "
                f"(requested {requested!r}, served {served!r}); identity "
                "unverified — the response is usable but unattributed."
            ),
        )
    if served == requested:
        return ServedModelVerdict(
            requested=requested,
            served=served,
            outcome="match",
            detail=f"Bytez served the requested model {requested!r}.",
        )
    return ServedModelVerdict(
        requested=requested,
        served=served,
        outcome="mismatch",
        detail=(
            f"Bytez served {served!r} instead of the requested "
            f"{requested!r}; the response content is returned as-is, but "
            "quota and audit records must not attribute it to the "
            "requested model."
        ),
    )


def annotate_bytez_response(
    response: ProviderResponse, verdict: ServedModelVerdict
) -> ProviderResponse:
    """Record a served-model verdict on a Bytez response, in place.

    Writes ``raw_response["bytez"] = {"requested_model", "served_model",
    "served_model_match"}`` and logs a warning unless the served model
    matches. ``response.model`` is deliberately left as the requested id:
    gateway quota accounting is keyed on what was asked for, and the
    annotation — not a silent substitution — carries the truth. Returns
    the same response object for chaining.
    """
    raw = response.raw_response
    if not isinstance(raw, dict):
        raw = {}
        response.raw_response = raw
    raw["bytez"] = {
        "requested_model": verdict.requested,
        "served_model": verdict.served,
        "served_model_match": verdict.outcome == "match",
        "served_model_outcome": verdict.outcome,
    }
    if verdict.outcome != "match":
        logger.warning("BYTEZ: served-model identity %s", verdict.detail)
    return response
