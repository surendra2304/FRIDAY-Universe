"""Offline-first fallback mode (TASK-IG-FRD-007) — Project NOMAD pattern.

Pattern source: IG corpus item ``Ddy9EMkCb3Z`` (Project NOMAD, repo
card verdict **adapt**): an assistant that keeps working with no
internet. The full NOMAD stack (local LLM in Docker) is far too heavy
for the current ~956MB servers, so this is the miniature that fits:

* :class:`LocalKnowledgeStore` — a small file-backed store of cached
  Q&A pairs and ingested facts, warmed while online
  (:meth:`cache_answer`, :meth:`ingest_facts`).
* :class:`OfflineFallbackProvider` — a ``BaseLLMProvider`` that answers
  *only* from that store, by declared keyword-overlap matching. Every
  answer is prefixed ``[OFFLINE FALLBACK — cached, may be stale]`` and
  metadata-flagged. On no match it returns a clearly labelled
  unavailable message. **It never fabricates an answer** — a cache miss
  is stated, not filled in.

Wiring: ``friday.llm.factory`` wraps the production chat stack in the
existing ``FallbackChainLLMProvider`` with this provider as the last
rung when ``FRIDAY_OFFLINE_FALLBACK=on`` — it engages exactly when the
stack raises ``LLMProviderError`` (e.g. network down, pools dead).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

from friday.core.types import Message, Role
from friday.llm.base import BaseLLMProvider

OFFLINE_LABEL = "[OFFLINE FALLBACK — cached, may be stale]"
MATCH_THRESHOLD = 0.34

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "what", "when", "where",
    "who", "how", "why", "do", "does", "did", "i", "you", "my", "me",
    "of", "to", "in", "on", "for", "and", "or", "it", "this", "that",
}


def _tokens(text: str) -> set:
    return {
        t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(t) > 2 and t not in _STOP
    }


def _default_store_path() -> str:
    env = os.environ.get("FRIDAY_OFFLINE_KB_PATH", "").strip()
    if env:
        return env
    base = os.environ.get("FRIDAY_DATA_DIR", "").strip()
    root = base if base else os.path.join("FRIDAY", ".data")
    return os.path.join(root, "offline", "knowledge.json")


class LocalKnowledgeStore:
    """File-backed cached knowledge: Q&A pairs + ingested facts."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or _default_store_path()
        self._lock = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._entries = [e for e in data if isinstance(e, dict)]
        except (OSError, ValueError):
            self._entries = []

    def _save(self) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".kb-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def cache_answer(self, question: str, answer: str, source: str = "chat") -> None:
        with self._lock:
            self._entries.append(
                {
                    "kind": "qa",
                    "question": question,
                    "answer": answer,
                    "source": source,
                    "stored_at": time.time(),
                }
            )
            self._save()

    def ingest_facts(self, records: List[Dict[str, Any]], source: str = "memora") -> int:
        """Ingest Memora-shaped records ({fact_text|content|text}) as facts."""
        added = 0
        with self._lock:
            for record in records or []:
                text = ""
                for key in ("fact_text", "content", "text", "fact"):
                    value = record.get(key)
                    if isinstance(value, str) and value.strip():
                        text = value.strip()
                        break
                if not text:
                    continue
                self._entries.append(
                    {
                        "kind": "fact",
                        "question": text,
                        "answer": text,
                        "source": source,
                        "stored_at": time.time(),
                    }
                )
                added += 1
            if added:
                self._save()
        return added

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """Best keyword-overlap match, or None below the threshold."""
        q = _tokens(query)
        if not q:
            return None
        best: Optional[Dict[str, Any]] = None
        best_score = 0.0
        for entry in self._entries:
            haystack = _tokens(f"{entry.get('question', '')} {entry.get('answer', '')}")
            if not haystack:
                continue
            overlap = len(q & haystack)
            if len(q) > 2 and overlap < 2:
                continue
            score = overlap / len(q)
            if score > best_score:
                best_score = score
                best = entry
        if best is not None and best_score >= MATCH_THRESHOLD:
            result = dict(best)
            result["match_score"] = round(best_score, 3)
            return result
        return None

    def __len__(self) -> int:
        return len(self._entries)


class OfflineFallbackProvider(BaseLLMProvider):
    """Last-rung provider: cached answers only, honestly labelled."""

    def __init__(
        self,
        store: Optional[LocalKnowledgeStore] = None,
        model: str = "offline-fallback",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.store = store or LocalKnowledgeStore()

    @property
    def provider_name(self) -> str:
        return "offline_fallback"

    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Message:
        query = ""
        for message in reversed(messages or []):
            if getattr(message, "role", None) == Role.USER and message.content:
                query = message.content
                break
        hit = self.store.search(query) if query else None
        if hit is not None:
            content = (
                f"{OFFLINE_LABEL}\n\n{hit['answer']}\n\n"
                f"(Cached from: {hit.get('source', 'unknown')}; the live "
                "providers are unreachable, so this may be out of date.)"
            )
            return Message(
                role=Role.ASSISTANT,
                content=content,
                metadata={
                    "offline_fallback": True,
                    "cached": True,
                    "match_score": hit.get("match_score"),
                    "source": hit.get("source"),
                },
            )
        content = (
            f"{OFFLINE_LABEL}\n\n"
            "I'm currently offline — the live model providers are "
            "unreachable — and I have nothing cached that matches that. "
            "I won't guess. Try again when connectivity is back, or ask "
            "about something I may have cached earlier."
        )
        return Message(
            role=Role.ASSISTANT,
            content=content,
            metadata={"offline_fallback": True, "cached": False},
        )


def offline_fallback_enabled() -> bool:
    return os.environ.get("FRIDAY_OFFLINE_FALLBACK", "").strip().lower() in (
        "on",
        "true",
        "1",
        "yes",
    )


__all__ = [
    "OFFLINE_LABEL",
    "MATCH_THRESHOLD",
    "LocalKnowledgeStore",
    "OfflineFallbackProvider",
    "offline_fallback_enabled",
]
