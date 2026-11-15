"""Safe response cache for inference completions (TASK-INF-006).

Why this exists
---------------
Inference already had two caches, and neither enforced the rule this module
is built around — *a personalised or contextual answer must never be served
to the wrong context*:

* ``TenantCache`` (``cache.py``) keys by tenant only, with one flat TTL and
  no notion of the context an answer was produced under.
* ``MultiLevelCache`` (``app/performance_cache.py``) additionally stores
  every answer under *shared* keys (any mode, any caller) and a
  punctuation-stripped "normalized" key. Within a namespace, an answer
  produced under one caller's context can be served to another caller whose
  recorded ``extra`` happens to match, and two different questions can
  collide after punctuation stripping.

``SafeResponseCache`` is the response cache with the safety semantics made
structural rather than conventional:

Context classes
    Every request is classified (declared class wins as a floor; automatic
    signals can only *raise* the class, never lower it):

    * ``PUBLIC`` — no personal or contextual inputs. Shareable across
      callers. The context fingerprint is *excluded* from the key.
    * ``CONTEXTUAL`` — the answer depends on supplied context. The key
      embeds a SHA-256 fingerprint of the exact context, so an entry is
      only ever served to a byte-identical context.
    * ``PERSONALISED`` — bound to a principal (user/session/conversation
      identifier present). **Never stored by default**
      (``allow_personalised_storage=False``); if storage is explicitly
      enabled, the key embeds the principal fingerprint and the TTL is the
      shortest class TTL. A personalised entry can therefore never be
      served to a different principal: the lookup key itself differs.

Matching
    *Exact match* — canonical fingerprint of the full request payload
    (model, messages/prompt, sampling parameters, response schema,
    capabilities, extra) plus, per class, the context fingerprint.

    *Task-template match* — only for templates registered in advance with
    declared *invariant slots* (slot values that do not affect the answer,
    e.g. a request id). The template key covers the template id + version
    and every non-invariant slot value. Unregistered prompts never
    template-match, and templates never serve ``PERSONALISED`` requests.
    This replaces the old punctuation-stripping approximation with declared
    semantics.

Stochastic requests
    Requests sampled with temperature > 0 (or top_p < 1) may be replayed
    only by exact match, only within the identical context fingerprint,
    with their TTL capped at ``stochastic_ttl_cap_seconds``. They are
    never template-matched: a template hit asserts the answer does not
    depend on the varying slots, which sampling makes untestable.

TTLs and invalidation
    One TTL per class (see ``CachePolicy``), checked on every read.
    Invalidation is generation-based: each namespace and template carries
    a generation counter embedded in every key, so
    ``invalidate_namespace`` / ``invalidate_template`` orphan all affected
    entries in O(1). ``invalidate_context`` / ``invalidate_principal``
    delete by fingerprint scan (the store is bounded). ``policy_version``
    is embedded in every key: bumping it (model catalogue or routing
    policy change) orphans the entire cache.

Bounds and metrics
    LRU-bounded by ``max_entries``. ``stats()`` reports hits by match
    kind, misses, bypasses by reason, stores, evictions, expirations,
    invalidations and the modelled latency saved (sum of the original
    provider latency recorded with each entry, over hits).

The store is process-local and thread-safe. It deliberately does not
persist: a restart is a full invalidation, which is the safe direction.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ContextClass(str, Enum):
    PUBLIC = "public"
    CONTEXTUAL = "contextual"
    PERSONALISED = "personalised"


_CLASS_RANK = {ContextClass.PUBLIC: 0, ContextClass.CONTEXTUAL: 1, ContextClass.PERSONALISED: 2}


def _raise_class(current: ContextClass, floor: ContextClass) -> ContextClass:
    return floor if _CLASS_RANK[floor] > _CLASS_RANK[current] else current


# Context keys whose presence means the answer is bound to one principal.
_PRINCIPAL_CONTEXT_KEYS = frozenset(
    {"user_id", "principal_id", "session_id", "conversation_id", "account_id", "customer_id"}
)

# First-person markers: their presence means the answer plausibly depends on
# who is asking, so the request is at least CONTEXTUAL (never PUBLIC/shared).
_PERSONAL_MARKER_RE = re.compile(
    r"\b(my|mine|myself|i|me|we|our|ours)\b", re.IGNORECASE
)


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sha(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


@dataclass(frozen=True)
class CachePolicy:
    public_ttl_seconds: float = 3600.0
    contextual_ttl_seconds: float = 300.0
    personalised_ttl_seconds: float = 60.0
    template_ttl_seconds: float = 900.0
    stochastic_ttl_cap_seconds: float = 300.0
    max_entries: int = 1024
    policy_version: str = "1"
    # Hard default: personalised answers are not stored at all. Enabling
    # storage still scopes every entry to its principal fingerprint.
    allow_personalised_storage: bool = False

    def ttl_for(self, context_class: ContextClass, *, template: bool = False) -> float:
        if template:
            return self.template_ttl_seconds
        return {
            ContextClass.PUBLIC: self.public_ttl_seconds,
            ContextClass.CONTEXTUAL: self.contextual_ttl_seconds,
            ContextClass.PERSONALISED: self.personalised_ttl_seconds,
        }[context_class]


@dataclass(frozen=True)
class TemplateSpec:
    """A registered task template.

    ``invariant_slots`` names the slots whose values do not affect the
    answer (request ids, timestamps, trace ids). Every other slot value is
    part of the template key. ``max_class`` caps the context class a
    template may serve; templates never serve PERSONALISED requests
    regardless of this setting.
    """

    template_id: str
    version: str = "1"
    invariant_slots: frozenset[str] = frozenset()
    max_class: ContextClass = ContextClass.CONTEXTUAL


@dataclass
class _Entry:
    value: Any
    expires_at: float
    context_fingerprint: str
    principal_fingerprint: str | None
    namespace: str
    template_id: str | None
    original_latency_seconds: float


@dataclass
class CacheLookup:
    hit: bool
    value: Any = None
    key: str | None = None
    match_kind: str | None = None  # "exact" | "template"
    reason: str = ""  # machine-readable miss/bypass reason


@dataclass
class CacheStats:
    hits_exact: int = 0
    hits_template: int = 0
    misses: int = 0
    stores: int = 0
    evictions: int = 0
    expirations: int = 0
    invalidations: int = 0
    latency_saved_seconds: float = 0.0
    bypasses: dict[str, int] = field(default_factory=dict)

    @property
    def hits(self) -> int:
        return self.hits_exact + self.hits_template

    @property
    def lookups(self) -> int:
        return self.hits + self.misses

    def hit_rate(self) -> float:
        return (self.hits / self.lookups) if self.lookups else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "hits_exact": self.hits_exact,
            "hits_template": self.hits_template,
            "misses": self.misses,
            "lookups": self.lookups,
            "hit_rate": round(self.hit_rate(), 4),
            "stores": self.stores,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "invalidations": self.invalidations,
            "latency_saved_seconds": round(self.latency_saved_seconds, 3),
            "bypasses": dict(self.bypasses),
        }


class SafeResponseCache:
    """Context-safe response cache. See the module docstring for the rules."""

    def __init__(self, policy: CachePolicy | None = None) -> None:
        self.policy = policy or CachePolicy()
        if self.policy.max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._data: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.RLock()
        self._templates: dict[str, TemplateSpec] = {}
        self._namespace_generations: dict[str, int] = {}
        self._template_generations: dict[str, int] = {}
        self._stats = CacheStats()

    # ------------------------------------------------------------------
    # Classification and fingerprints
    # ------------------------------------------------------------------
    def classify(
        self,
        *,
        declared: ContextClass | str | None = None,
        principal_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        prompt_text: str = "",
    ) -> ContextClass:
        """Classify a request. Automatic signals only ever raise the class."""
        cls = ContextClass.PUBLIC
        if declared is not None:
            cls = ContextClass(declared)
        context = context or {}
        if principal_id or any(
            context.get(k) not in (None, "") for k in _PRINCIPAL_CONTEXT_KEYS
        ):
            cls = _raise_class(cls, ContextClass.PERSONALISED)
        elif context:
            cls = _raise_class(cls, ContextClass.CONTEXTUAL)
        if prompt_text and _PERSONAL_MARKER_RE.search(prompt_text):
            cls = _raise_class(cls, ContextClass.CONTEXTUAL)
        return cls

    @staticmethod
    def context_fingerprint(
        context: Mapping[str, Any] | None, principal_id: str | None = None
    ) -> str:
        """Fingerprint of the exact context (and principal, when present)."""
        material: dict[str, Any] = {"context": dict(context or {})}
        if principal_id:
            material["principal"] = principal_id
        return _sha(material)

    @staticmethod
    def principal_fingerprint(principal_id: str | None) -> str | None:
        if not principal_id:
            return None
        return _sha({"principal": principal_id})

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def register_template(self, spec: TemplateSpec) -> None:
        with self._lock:
            self._templates[spec.template_id] = spec
            self._template_generations.setdefault(spec.template_id, 0)

    def template_for(self, template_id: str | None) -> TemplateSpec | None:
        if not template_id:
            return None
        return self._templates.get(template_id)

    # ------------------------------------------------------------------
    # Key construction
    # ------------------------------------------------------------------
    def _namespace_generation(self, namespace: str) -> int:
        return self._namespace_generations.get(namespace, 0)

    def _exact_key(
        self,
        *,
        namespace: str,
        payload: Mapping[str, Any],
        context_class: ContextClass,
        context_fingerprint: str,
    ) -> str:
        ctx_part = "-" if context_class is ContextClass.PUBLIC else context_fingerprint
        return "|".join(
            (
                f"v{self.policy.policy_version}",
                f"ns={namespace}",
                f"gen={self._namespace_generation(namespace)}",
                f"cls={context_class.value}",
                f"ctx={ctx_part}",
                f"req={_sha(dict(payload))}",
            )
        )

    def _template_key(
        self,
        *,
        namespace: str,
        spec: TemplateSpec,
        slots: Mapping[str, Any],
        context_class: ContextClass,
        context_fingerprint: str,
    ) -> str | None:
        if context_class is ContextClass.PERSONALISED:
            return None
        if _CLASS_RANK[context_class] > _CLASS_RANK[spec.max_class]:
            return None
        semantic_slots = {
            k: v for k, v in dict(slots).items() if k not in spec.invariant_slots
        }
        ctx_part = "-" if context_class is ContextClass.PUBLIC else context_fingerprint
        return "|".join(
            (
                f"v{self.policy.policy_version}",
                f"ns={namespace}",
                f"gen={self._namespace_generation(namespace)}",
                f"cls={context_class.value}",
                f"ctx={ctx_part}",
                f"tpl={spec.template_id}@{spec.version}",
                f"tgen={self._template_generations.get(spec.template_id, 0)}",
                f"slots={_sha(semantic_slots)}",
            )
        )

    # ------------------------------------------------------------------
    # Lookup / store
    # ------------------------------------------------------------------
    def lookup(
        self,
        *,
        namespace: str,
        payload: Mapping[str, Any],
        context_class: ContextClass,
        context_fingerprint: str,
        template_id: str | None = None,
        template_slots: Mapping[str, Any] | None = None,
        stochastic: bool = False,
    ) -> CacheLookup:
        """Exact match first, then (for non-stochastic, non-personalised
        requests) the registered-template match."""
        if context_class is ContextClass.PERSONALISED and not self.policy.allow_personalised_storage:
            return self._bypass("personalised_storage_disabled")
        exact_key = self._exact_key(
            namespace=namespace,
            payload=payload,
            context_class=context_class,
            context_fingerprint=context_fingerprint,
        )
        with self._lock:
            entry = self._read_locked(exact_key)
            if entry is not None:
                self._stats.hits_exact += 1
                self._stats.latency_saved_seconds += entry.original_latency_seconds
                return CacheLookup(True, entry.value, exact_key, "exact", "hit_exact")

            if template_id and not stochastic:
                spec = self._templates.get(template_id)
                if spec is not None:
                    tpl_key = self._template_key(
                        namespace=namespace,
                        spec=spec,
                        slots=template_slots or {},
                        context_class=context_class,
                        context_fingerprint=context_fingerprint,
                    )
                    if tpl_key is not None:
                        entry = self._read_locked(tpl_key)
                        if entry is not None:
                            self._stats.hits_template += 1
                            self._stats.latency_saved_seconds += entry.original_latency_seconds
                            return CacheLookup(True, entry.value, tpl_key, "template", "hit_template")
            self._stats.misses += 1
            return CacheLookup(False, None, exact_key, None, "miss")

    def store(
        self,
        *,
        namespace: str,
        payload: Mapping[str, Any],
        value: Any,
        context_class: ContextClass,
        context_fingerprint: str,
        principal_id: str | None = None,
        original_latency_seconds: float = 0.0,
        template_id: str | None = None,
        template_slots: Mapping[str, Any] | None = None,
        stochastic: bool = False,
    ) -> str:
        """Store a completed response. Returns the exact key, or a bypass
        reason string starting with ``"bypass:"`` when nothing was stored."""
        if context_class is ContextClass.PERSONALISED and not self.policy.allow_personalised_storage:
            self._count_bypass("personalised_storage_disabled")
            return "bypass:personalised_storage_disabled"
        if context_class is ContextClass.PERSONALISED and not principal_id:
            # Defence in depth: never store a personalised answer that is
            # not bound to a principal fingerprint.
            self._count_bypass("personalised_without_principal")
            return "bypass:personalised_without_principal"
        if isinstance(original_latency_seconds, bool) or not isinstance(
            original_latency_seconds, (int, float)
        ) or not math.isfinite(original_latency_seconds) or original_latency_seconds < 0:
            raise ValueError("original_latency_seconds must be a finite number >= 0")

        ttl = self.policy.ttl_for(context_class)
        if stochastic:
            ttl = min(ttl, self.policy.stochastic_ttl_cap_seconds)
        exact_key = self._exact_key(
            namespace=namespace,
            payload=payload,
            context_class=context_class,
            context_fingerprint=context_fingerprint,
        )
        principal_fp = self.principal_fingerprint(principal_id)
        with self._lock:
            self._write_locked(
                exact_key,
                value,
                ttl,
                context_fingerprint=context_fingerprint,
                principal_fingerprint=principal_fp,
                namespace=namespace,
                template_id=None,
                original_latency_seconds=float(original_latency_seconds),
            )
            if template_id and not stochastic:
                spec = self._templates.get(template_id)
                if spec is not None:
                    tpl_key = self._template_key(
                        namespace=namespace,
                        spec=spec,
                        slots=template_slots or {},
                        context_class=context_class,
                        context_fingerprint=context_fingerprint,
                    )
                    if tpl_key is not None:
                        self._write_locked(
                            tpl_key,
                            value,
                            self.policy.ttl_for(context_class, template=True),
                            context_fingerprint=context_fingerprint,
                            principal_fingerprint=principal_fp,
                            namespace=namespace,
                            template_id=spec.template_id,
                            original_latency_seconds=float(original_latency_seconds),
                        )
            self._stats.stores += 1
        return exact_key

    def delete(self, key: str) -> None:
        """Evict one entry by key (e.g. a malformed value found on read)."""
        with self._lock:
            self._data.pop(key, None)

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------
    def invalidate_namespace(self, namespace: str) -> None:
        """Orphan every entry in a namespace (generation bump, O(1))."""
        with self._lock:
            self._namespace_generations[namespace] = self._namespace_generation(namespace) + 1
            self._stats.invalidations += 1

    def invalidate_template(self, template_id: str) -> None:
        """Orphan every entry produced under a template (generation bump)."""
        with self._lock:
            self._template_generations[template_id] = (
                self._template_generations.get(template_id, 0) + 1
            )
            self._stats.invalidations += 1

    def invalidate_context(self, context_fingerprint: str) -> int:
        """Delete every entry stored under one context fingerprint."""
        return self._delete_matching(lambda e: e.context_fingerprint == context_fingerprint)

    def invalidate_principal(self, principal_id: str) -> int:
        """Delete every entry bound to one principal (e.g. on logout/erasure)."""
        fp = self.principal_fingerprint(principal_id)
        if fp is None:
            return 0
        return self._delete_matching(lambda e: e.principal_fingerprint == fp)

    def flush(self) -> None:
        with self._lock:
            removed = len(self._data)
            self._data.clear()
            self._stats.invalidations += removed

    def _delete_matching(self, predicate) -> int:
        with self._lock:
            keys = [k for k, e in self._data.items() if predicate(e)]
            for k in keys:
                self._data.pop(k, None)
            self._stats.invalidations += len(keys)
            return len(keys)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _read_locked(self, key: str) -> _Entry | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._data.pop(key, None)
            self._stats.expirations += 1
            return None
        self._data.move_to_end(key)
        return entry

    def _write_locked(
        self,
        key: str,
        value: Any,
        ttl: float,
        *,
        context_fingerprint: str,
        principal_fingerprint: str | None,
        namespace: str,
        template_id: str | None,
        original_latency_seconds: float,
    ) -> None:
        if ttl <= 0:
            self._data.pop(key, None)
            return
        if key not in self._data and len(self._data) >= self.policy.max_entries:
            self._data.popitem(last=False)
            self._stats.evictions += 1
        self._data[key] = _Entry(
            value=value,
            expires_at=time.monotonic() + ttl,
            context_fingerprint=context_fingerprint,
            principal_fingerprint=principal_fingerprint,
            namespace=namespace,
            template_id=template_id,
            original_latency_seconds=original_latency_seconds,
        )

    def _bypass(self, reason: str) -> CacheLookup:
        self._count_bypass(reason)
        return CacheLookup(False, None, None, None, f"bypass:{reason}")

    def _count_bypass(self, reason: str) -> None:
        with self._lock:
            self._stats.bypasses[reason] = self._stats.bypasses.get(reason, 0) + 1

    def stats(self) -> dict[str, Any]:
        with self._lock:
            out = self._stats.as_dict()
            out["entries"] = len(self._data)
            out["policy_version"] = self.policy.policy_version
            return out

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
