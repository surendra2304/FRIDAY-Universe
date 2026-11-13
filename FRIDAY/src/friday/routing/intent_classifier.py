"""
routing/intent_classifier.py — LLM intent-classification mid-tier (TASK-INTENT-001).

The routing ladder is deterministic keyword tables (capability_router.py +
fast_paths.py). They are fast and test-pinned, but their coverage is
pattern-shaped: phrasings no table matches fall through to the generic LLM
tool loop (multi-second, unsteered), and phrasings matching >=2 tables are
resolved by score arithmetic rather than understanding (the documented
misroute class: research->VISION_MODEL, trading-intent->launcher, "write a
script"->video-script engine).

This module adds ONE bounded mid-tier between the deterministic tiers and the
generic loop. Contract (pinned by tests):

- **Fail-open**: any timeout/error/low-confidence returns ``None`` and the
  pipeline proceeds byte-identical to the pre-tier behaviour. The classifier
  can only add information, never block a turn.
- **Weak-signal gate**: fires only when the deterministic tables are weak
  (no table matched, or >=2 tables matched). A single unambiguous table hit
  never pays an LLM call.
- **Deterministic tiers stay authoritative**: CapabilityRouter.route_request
  stays a pure function; fast paths keep their ``fast_path: True`` exclusivity;
  compound requests are never claimed here.
- **Bounded**: the provider call runs under a wall-clock timeout
  (``Settings.intent_classify_timeout``, default 2.5s) in a single-worker
  pool, results are LRU-cached per normalized message, and ``temperature=0``
  with ``max_tokens=200`` keeps the call cheap.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

from friday.core.types import Message, Role

logger = logging.getLogger("friday.routing.intent")

#: Confidence above which the classifier may steer the tool loop.
STEER_CONFIDENCE = 0.85
#: Confidence above which the classifier may upgrade understanding confidence.
CLARITY_CONFIDENCE = 0.65
#: Cache bound (same shape as CapabilityRouter._WORD_BOUNDARY_CACHE usage).
_CACHE_MAX = 256

_PLAUSIBLE_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

# Compact label list for the classification prompt: the canonical tool names
# the deterministic tables route to (capability_router.py required_tools) plus
# the generic execution capabilities. Kept static and small so the prompt is
# deterministic in tests and cheap in production.
_TOOL_LABELS: tuple[str, ...] = (
    "intelx_research (evidence-based research brief with citations)",
    "stratex_portfolio (portfolio/market account snapshot, read-only)",
    "forge_code_task (build, fix or review software)",
    "futuris_forecast (statistical forecast/prediction)",
    "sentinel_security (security posture/scan lookup, read-only)",
    "get_fleet_status (live health probe of the specialist agents)",
    "vyralx_script (video script drafting)",
    "vyralx_render (render a video clip)",
    "vyralx_publish (upload/publish video — owner-gated)",
    "cortex_web_ops (web operations/health lookup)",
    "memora_memory (remember/recall/forget personal facts)",
    "web_fetch_summarize (fetch and summarize a URL)",
    "price_alert (create/manage a price watch alert)",
    "send_gmail (draft/send an email)",
    "open_whatsapp (open/send a WhatsApp message)",
    "dictionary (word definition lookup)",
    "price_or_market_data (current price/market quote lookup)",
    "local_computation (pure arithmetic/conversion — no tools needed)",
    "plain_conversation (small talk/greeting/question needing no tools)",
)


@dataclass
class IntentClassification:
    """One classifier verdict (maps onto the CompiledIntent field shapes)."""

    intent: str
    capability: str = ""
    required_tools: list[str] = field(default_factory=list)
    confidence: float = 0.0
    operand: str = ""
    source: str = "llm"

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "capability": self.capability,
            "required_tools": list(self.required_tools),
            "confidence": self.confidence,
            "operand": self.operand,
            "source": self.source,
        }


def build_classify_messages(
    message: str,
    recent_messages: Iterable[Message] = (),
) -> list[Message]:
    """Build the bounded classification prompt (system + compact history + turn)."""
    labels = "\n".join(f"- {label}" for label in _TOOL_LABELS)
    system = (
        "You classify ONE user request for a personal assistant (FRIDAY). "
        "Reply with ONLY a JSON object, no prose, no markdown fences, shaped exactly:\n"
        '{"intent": "<short intent id>", "capability": "<tool label or plain_conversation>", '
        '"required_tools": ["<tool name>"], "confidence": <0.0-1.0>, "operand": "<the thing acted on, or empty>"}\n'
        "Rules: pick required_tools ONLY from the label list (empty for plain conversation "
        "and local_computation); confidence reflects how sure you are; never invent tools; "
        "never execute anything.\n"
        "Known tool labels:\n" + labels
    )
    history: list[Message] = []
    for msg in list(recent_messages)[-3:]:
        content = (getattr(msg, "content", "") or "").strip()
        if content:
            history.append(
                Message(
                    role=Role.ASSISTANT if getattr(msg, "role", None) == Role.ASSISTANT else Role.USER,
                    content=content[:400],
                )
            )
    history.append(Message(role=Role.USER, content=message[:2000]))
    return [Message(role=Role.SYSTEM, content=system), *history]


class LLMIntentClassifier:
    """Bounded LLM intent classification with fail-open semantics."""

    def __init__(self, settings: Any = None, provider: Any = None) -> None:
        self._settings = settings
        self._provider = provider
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._executor_lock = threading.Lock()
        self._cache: dict[str, IntentClassification | None] = {}
        self._cache_lock = threading.Lock()
        self.timeout = 2.5
        if settings is not None:
            self.timeout = float(getattr(settings, "intent_classify_timeout", self.timeout) or self.timeout)
        elif os.getenv("FRIDAY_INTENT_CLASSIFY_TIMEOUT"):
            try:
                self.timeout = float(os.getenv("FRIDAY_INTENT_CLASSIFY_TIMEOUT"))
            except ValueError:
                pass

    # -- provider plumbing --------------------------------------------------
    def _get_provider(self) -> Any | None:
        if self._provider is not None:
            return self._provider
        try:
            from friday.core.config import get_settings
            from friday.llm.factory import create_llm_provider

            settings = self._settings or get_settings()
            if not bool(getattr(settings, "intent_classify_enabled", True)):
                return None
            self._settings = settings
            # Idiom of cognition/capability.py: lazy provider from settings so
            # mock/test providers work unchanged.
            self._provider = create_llm_provider(settings)
        except Exception as e:  # pragma: no cover - config failures only
            logger.debug(f"Intent classifier provider unavailable: {e}")
            return None
        return self._provider

    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._executor_lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="intent-classify"
                )
            return self._executor

    def _call_provider(self, messages: list[Message]) -> str | None:
        provider = self._get_provider()
        if provider is None:
            return None
        future = self._get_executor().submit(provider.generate, messages)
        try:
            response = future.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError:
            logger.info("Intent classification timed out; proceeding deterministically")
            return None
        except Exception as e:
            logger.debug(f"Intent classification call failed: {type(e).__name__}: {e}")
            return None
        return getattr(response, "content", None)

    # -- parsing ------------------------------------------------------------
    @staticmethod
    def parse_response(text: str | None) -> IntentClassification | None:
        """Parse a classifier reply; None on anything malformed (fail-open)."""
        if not text:
            return None
        match = _JSON_BLOCK.search(text)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except (ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        intent = str(payload.get("intent") or "").strip()
        if not intent:
            return None
        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if not 0.0 <= confidence <= 1.0:
            return None
        raw_tools = payload.get("required_tools") or []
        tools: list[str] = []
        if isinstance(raw_tools, list):
            for item in raw_tools:
                name = str(item).strip()
                if _PLAUSIBLE_TOOL_NAME.match(name) and name not in tools:
                    tools.append(name)
        return IntentClassification(
            intent=intent[:64],
            capability=str(payload.get("capability") or "").strip()[:64],
            required_tools=tools[:4],
            confidence=round(confidence, 3),
            operand=str(payload.get("operand") or "").strip()[:200],
        )

    # -- public API ----------------------------------------------------------
    def classify(
        self,
        message: str,
        recent_messages: Iterable[Message] = (),
    ) -> IntentClassification | None:
        """Classify one turn; returns None on any failure (fail-open)."""
        key = (message or "").lower().strip()
        if not key:
            return None
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
        classification = self.parse_response(
            self._call_provider(build_classify_messages(message, recent_messages))
        )
        if classification is not None:
            classification.source = "llm_intent_tier"
        with self._cache_lock:
            if len(self._cache) >= _CACHE_MAX:
                # Bounded cache: drop the oldest third (dict preserves order).
                for stale in list(self._cache)[: _CACHE_MAX // 3]:
                    self._cache.pop(stale, None)
            self._cache[key] = classification
        return classification

    @staticmethod
    def signal_is_weak(message: str, router: Any) -> bool:
        """True when the deterministic tables give no single clear answer.

        Weak = no table matched (generic-loop fallback territory) or >=2
        tables matched (score-arithmetic ambiguity). A single table hit is a
        deterministic win and never reaches the classifier.
        """
        try:
            matched = int(router.deterministic_match_count(message))
        except Exception:
            return False
        return matched == 0 or matched >= 2

    def reset_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()


_singleton: LLMIntentClassifier | None = None
_singleton_lock = threading.Lock()


def get_intent_classifier() -> LLMIntentClassifier | None:
    """Process-wide lazy classifier; None when explicitly disabled by env.

    ``FRIDAY_INTENT_CLASSIFIER=off`` keeps the pipeline byte-identical to the
    pre-tier behaviour (kill switch for live incidents). The switch prevents
    lazy CREATION only: an already-injected singleton (test double, ops
    override) is still returned, so hermetic suites that inject a fake before
    the env is read never construct a real provider through the hook.
    """
    global _singleton
    if _singleton is not None:
        return _singleton
    if os.getenv("FRIDAY_INTENT_CLASSIFIER", "").strip().lower() in ("off", "false", "0", "no"):
        return None
    with _singleton_lock:
        if _singleton is None:
            try:
                _singleton = LLMIntentClassifier()
            except Exception:  # pragma: no cover - construction is trivial
                return None
        return _singleton


def reset_intent_classifier() -> None:
    """Test/ops hook: drop the singleton and its cache."""
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            _singleton.reset_cache()
        _singleton = None
