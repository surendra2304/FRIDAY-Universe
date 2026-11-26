"""Memora offline knowledge pack (TASK-MEM-032) — NOMAD's packaging pattern, adapted.

Project NOMAD (Crosstalk-Solutions/project-nomad) is an offline-first
knowledge server: curated content collections (offline Wikipedia via
Kiwix/ZIM, Khan Academy via Kolibri, offline maps via ProtoMaps, local AI
via Ollama) bundled on hardware you own, a manifest naming exactly what
is installed, and no network needed after install. This module adapts
that pattern — and only that pattern — into a Memora fallback store:

* A defined corpus subset, bundled in-repo as ``nomad_pack/manifest.json``
  + ``nomad_pack/corpus.jsonl`` (16 entries: FRIDAY-Universe standing
  orders and Memora fallback procedures, offline-first reference concepts,
  offline-learning pointers). The manifest names the pack version, the
  entry count, the collections, and the corpus SHA-256, so a tampered or
  truncated pack fails loudly at load instead of answering wrong.
* A local query path: stdlib-only Okapi BM25 ranking over the bundled
  corpus. No model, no vector store, no network, no database.
* A strict fallback switch (:func:`resolve_knowledge`): the Oracle ADB
  path is tried first and wins whenever it answers; the pack answers only
  when ADB is down, empty, or unconfigured — and every pack answer says
  so (``source: "offline_pack"``), so a reader never mistakes it for live
  store data. The pack complements the ADB store; it never replaces it.

Deliberate non-reuse: this module does NOT import ``core.memory.bm25``.
A fallback store must still load when the thing that is down is the
primary store's own import chain, so the pack depends on nothing in
Memora — stdlib only. The ranking below follows ``core.memory.bm25``'s
exact scoring (same tokenizer rules, same Okapi formula, same squash)
in ~60 lines, and the test suite pins the ranking behaviour directly.

Rejected NOMAD pieces (see the TASK-MEM-032 evidence doc for the full
judgement): the Docker-orchestrated Command Center, full ZIM dumps,
Ollama + Qdrant local-LLM RAG, and the no-auth open-server model — all
too heavy, too large, or wrong-shaped for a Memora library fallback.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PACK_DIR = Path(__file__).resolve().parent / "nomad_pack"
MANIFEST_NAME = "manifest.json"
CORPUS_NAME = "corpus.jsonl"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens (same rules as ``core.memory.bm25``).

    Single-character tokens are dropped — they are almost never content
    terms — except single digits, which can be meaningful (versions,
    counts).
    """
    return [tok for tok in _TOKEN_RE.findall((text or "").lower()) if len(tok) > 1 or tok.isdigit()]


def _squash(score: float) -> float:
    """Map a raw BM25 score into (0, 1) — monotonic, rank-preserving."""
    if score <= 0:
        return 0.0
    return score / (1.0 + score)


@dataclass(frozen=True)
class PackEntry:
    """One bundled corpus entry."""

    entry_id: str
    title: str
    collection: str
    body: str
    keywords: Tuple[str, ...] = ()

    def index_text(self) -> str:
        """Text the ranker sees: title counts twice (it names the topic),
        then keywords, then body."""
        return f"{self.title} {self.title} {' '.join(self.keywords)} {self.body}"

    def as_hit(self, score: float) -> Dict[str, Any]:
        return {
            "id": self.entry_id,
            "title": self.title,
            "collection": self.collection,
            "body": self.body,
            "score": round(score, 4),
        }


class PackError(ValueError):
    """The bundled pack is missing, malformed, or fails integrity."""


class OfflinePack:
    """A loaded, integrity-checked offline knowledge pack.

    Load once (:meth:`load`) and reuse: the corpus is small (16 entries)
    and the BM25 statistics are built at load, so queries are pure
    in-memory ranking with no I/O after the first load.
    """

    def __init__(
        self,
        entries: List[PackEntry],
        manifest: Dict[str, Any],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self._entries = {e.entry_id: e for e in entries}
        self._manifest = dict(manifest)
        self._k1 = float(k1)
        self._b = float(b)
        self._doc_tokens: Dict[str, List[str]] = {}
        self._doc_freq: Counter = Counter()
        self._total_length = 0
        for entry in entries:
            tokens = _tokenize(entry.index_text())
            self._doc_tokens[entry.entry_id] = tokens
            self._total_length += len(tokens)
            for term in set(tokens):
                self._doc_freq[term] += 1

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls, pack_dir: Path = PACK_DIR) -> "OfflinePack":
        """Load + validate the bundled pack; raises :class:`PackError` on
        any defect (missing files, bad JSON, count/hash mismatch, duplicate
        ids, unknown collection). A fallback store that answers wrong is
        worse than one that refuses to load."""
        pack_dir = Path(pack_dir)
        manifest_path = pack_dir / MANIFEST_NAME
        corpus_path = pack_dir / CORPUS_NAME
        if not manifest_path.is_file():
            raise PackError(f"offline pack manifest missing: {manifest_path}")
        if not corpus_path.is_file():
            raise PackError(f"offline pack corpus missing: {corpus_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PackError(f"offline pack manifest is not valid JSON: {exc}") from exc
        if not isinstance(manifest, dict):
            raise PackError("offline pack manifest must be a JSON object")
        raw = corpus_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        expected_digest = manifest.get("entries_sha256")
        if expected_digest and digest != expected_digest:
            raise PackError(
                f"offline pack corpus hash mismatch: manifest says {expected_digest}, "
                f"file hashes to {digest} (tampered or truncated corpus?)"
            )
        entries: List[PackEntry] = []
        for lineno, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PackError(f"offline pack corpus line {lineno} is not valid JSON: {exc}") from exc
            entries.append(cls._entry_from_row(row, lineno))
        seen: set = set()
        for entry in entries:
            if entry.entry_id in seen:
                raise PackError(f"offline pack corpus has duplicate entry id: {entry.entry_id!r}")
            seen.add(entry.entry_id)
            if entry.collection not in manifest.get("collections", []):
                raise PackError(
                    f"offline pack entry {entry.entry_id!r} has undeclared collection "
                    f"{entry.collection!r} (manifest collections: {manifest.get('collections')})"
                )
        expected_count = manifest.get("entry_count")
        if expected_count is not None and len(entries) != expected_count:
            raise PackError(
                f"offline pack entry count mismatch: manifest says {expected_count}, "
                f"corpus has {len(entries)}"
            )
        return cls(entries, manifest)

    @staticmethod
    def _entry_from_row(row: Any, lineno: int) -> PackEntry:
        if not isinstance(row, dict):
            raise PackError(f"offline pack corpus line {lineno} is not a JSON object")
        entry_id = row.get("id")
        title = row.get("title")
        collection = row.get("collection")
        body = row.get("body")
        for field, value in (("id", entry_id), ("title", title), ("collection", collection), ("body", body)):
            if not isinstance(value, str) or not value.strip():
                raise PackError(f"offline pack corpus line {lineno} has no usable {field!r}")
        keywords = row.get("keywords", "")
        kw_tokens = tuple(_tokenize(keywords)) if isinstance(keywords, str) else ()
        return PackEntry(
            entry_id=entry_id.strip(),
            title=title.strip(),
            collection=collection.strip(),
            body=body.strip(),
            keywords=kw_tokens,
        )

    # -- reading ---------------------------------------------------------
    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def info(self) -> Dict[str, Any]:
        """Pack identity for logs and evidence: name, version, size, collections."""
        return {
            "pack": self._manifest.get("pack"),
            "version": self._manifest.get("version"),
            "task": self._manifest.get("task"),
            "entry_count": len(self._entries),
            "collections": list(self._manifest.get("collections", [])),
        }

    def entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """One entry by id (full body, no score), or None when unknown."""
        found = self._entries.get(entry_id)
        if found is None:
            return None
        return found.as_hit(1.0)

    def query(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Rank the corpus for ``query``; best first, at most ``top_k``.

        Pure in-memory BM25 — no I/O, no network, no database. An empty
        query or a query with no overlapping term returns ``[]``: the pack
        never invents an answer.
        """
        terms = [term for term in dict.fromkeys(_tokenize(query))]
        if not terms or not self._doc_tokens:
            return []
        n = len(self._doc_tokens)
        avg_len = self._total_length / max(1, n) or 1.0
        scored: List[Tuple[str, float]] = []
        for doc_id, tokens in self._doc_tokens.items():
            if not tokens:
                continue
            counts = Counter(tokens)
            doc_len = len(tokens)
            total = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                df = self._doc_freq.get(term, 0)
                idf = max(0.05, math.log(1.0 + (n - df + 0.5) / (df + 0.5)))
                denom = tf + self._k1 * (1.0 - self._b + self._b * doc_len / avg_len)
                total += idf * (tf * (self._k1 + 1.0)) / denom
            if total > 0:
                scored.append((doc_id, total))
        scored.sort(key=lambda kv: (-kv[1], kv[0]))
        return [self._entries[doc_id].as_hit(_squash(score)) for doc_id, score in scored[: max(0, top_k)]]


# ---------------------------------------------------------------------------
# Fallback switch: ADB first, offline pack second — never the reverse.
# ---------------------------------------------------------------------------

def resolve_knowledge(
    query: str,
    *,
    adb_query: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    adb_available: Optional[Callable[[], bool]] = None,
    pack: Optional[OfflinePack] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    """Answer ``query`` from the ADB store when it is up, else the offline pack.

    ``adb_query`` is the caller's ADB-backed search: it takes the query
    string and returns a list of hit dicts (the caller owns their shape),
    or raises on any ADB/network failure. ``adb_available`` is an optional
    cheap probe (``() -> bool``); when it reports False the ADB call is
    skipped outright instead of paying for a failing request.

    Returns ``{"source", "query", "hits", "fallback_reason", "adb_error"}``:

    * ``source == "adb"`` — ADB answered with at least one hit; the pack
      was not consulted even if it would have ranked higher. ADB wins.
    * ``source == "offline_pack"`` — the pack answered, with
      ``fallback_reason`` one of ``adb_unavailable`` (probe False or the
      ADB call raised), ``adb_empty`` (ADB answered but with zero hits),
      ``adb_not_configured`` (no ``adb_query`` was supplied), or
      ``empty_query``.
    * ``adb_error`` carries the ADB failure text when the ADB call raised,
      else None. An empty query short-circuits before any ADB call.
    """
    offline = pack if pack is not None else OfflinePack.load()
    if not (query or "").strip():
        return {
            "source": "offline_pack",
            "query": query,
            "hits": [],
            "fallback_reason": "empty_query",
            "adb_error": None,
        }
    if adb_query is None:
        return {
            "source": "offline_pack",
            "query": query,
            "hits": offline.query(query, top_k=top_k),
            "fallback_reason": "adb_not_configured",
            "adb_error": None,
        }
    if adb_available is not None:
        try:
            available = adb_available()
        except Exception as exc:  # probe failure == ADB unavailable
            return {
                "source": "offline_pack",
                "query": query,
                "hits": offline.query(query, top_k=top_k),
                "fallback_reason": "adb_unavailable",
                "adb_error": f"ADB probe raised {type(exc).__name__}: {exc}",
            }
        if not available:
            return {
                "source": "offline_pack",
                "query": query,
                "hits": offline.query(query, top_k=top_k),
                "fallback_reason": "adb_unavailable",
                "adb_error": "ADB probe reported unavailable",
            }
    try:
        adb_hits = adb_query(query)
    except Exception as exc:
        return {
            "source": "offline_pack",
            "query": query,
            "hits": offline.query(query, top_k=top_k),
            "fallback_reason": "adb_unavailable",
            "adb_error": f"ADB query raised {type(exc).__name__}: {exc}",
        }
    if adb_hits:
        return {
            "source": "adb",
            "query": query,
            "hits": list(adb_hits),
            "fallback_reason": None,
            "adb_error": None,
        }
    return {
        "source": "offline_pack",
        "query": query,
        "hits": offline.query(query, top_k=top_k),
        "fallback_reason": "adb_empty",
        "adb_error": None,
    }
