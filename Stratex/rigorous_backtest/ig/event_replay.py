"""Deterministic event-replay log for Stratex (demo) sessions — research tooling.

TASK-IG2-STR-06 (IG wave 2; pattern from the NautilusTrader repo card —
a deterministic event-driven architecture where every session can be
replayed exactly).

WHY: when a live DEMO trade surprises, the fleet's verification standard
demands evidence, not log archaeology. This module is an append-only
recording of the events that define a session — market bars, strategy
signals, orders and fills — in a form that can be replayed
deterministically: the same log always yields the same event stream,
byte for byte, so a replay either reproduces the session exactly or the
log itself is provably damaged.

FORMAT: one JSON object per line (JSONL), each record:
    {"seq": int, "ts": <event time, caller-supplied>, "type": str,
     "payload": {...}, "prev_hash": hex, "hash": hex}
hash = SHA-256 over the canonical JSON of {seq, ts, type, payload,
prev_hash}. The chain makes silent edits, deletions and reordering
detectable; seq continuity makes gaps detectable. session_start /
session_end records bracket a session; session_end carries the event
count and the stream digest (SHA-256 over the canonical sequence of
(type, payload) pairs), which replay verifies.

Append-only discipline: EventRecorder opens the file in append mode
only, continues seq/hash from the existing tail (verifying it first),
and never rewrites a line. Storage is a plain JSONL file — NOT SQLite
(repo rule: no new local database files) — a few MB per session at
bar/order granularity.

DEMO-ONLY: the recorder is a passive observer. It imports nothing from
production, connects to no venue, and can record a live-trading session
only if a caller wires it to one — which nothing in Stratex may do
under the owner's demo-only rule.

Stdlib only, Python 3.10-compatible.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVENT_TYPES = ("session_start", "market", "signal", "order", "fill", "session_end")
GENESIS_HASH = "0" * 64


class EventLogError(Exception):
    """Raised when a log fails integrity verification (tamper/gap/corruption)."""


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _record_hash(seq: int, ts, type_: str, payload: dict, prev_hash: str) -> str:
    body = {"seq": seq, "ts": ts, "type": type_, "payload": payload,
            "prev_hash": prev_hash}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def stream_digest(events) -> str:
    """Digest of the (type, payload) sequence — the identity of a session's
    behaviour, independent of wall-clock metadata."""
    h = hashlib.sha256()
    for e in events:
        h.update(_canonical({"type": e["type"], "payload": e["payload"]}).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


class EventRecorder:
    """Append-only writer. One recorder per session; construct with the
    log path, record events, close() to seal the session."""

    def __init__(self, path, session_id: str):
        self.path = Path(path)
        self.session_id = session_id
        self._seq = 0
        self._prev_hash = GENESIS_HASH
        self._events: list[dict] = []
        if self.path.exists() and self.path.stat().st_size > 0:
            existing = read_events(self.path)  # verifies the existing chain
            if existing:
                self._seq = existing[-1]["seq"] + 1
                self._prev_hash = existing[-1]["hash"]
                self._events = list(existing)
        self._fh = self.path.open("a", encoding="utf-8")
        self.record("session_start", {"session_id": session_id}, ts=None)

    def record(self, type_: str, payload: dict, ts=None) -> dict:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type_!r}; expected one of {EVENT_TYPES}")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        digest = _record_hash(self._seq, ts, type_, payload, self._prev_hash)
        rec = {"seq": self._seq, "ts": ts, "type": type_, "payload": payload,
               "prev_hash": self._prev_hash, "hash": digest}
        self._fh.write(_canonical(rec) + "\n")
        self._fh.flush()
        self._events.append(rec)
        self._prev_hash = digest
        self._seq += 1
        return rec

    # Convenience wrappers matching the session vocabulary.
    def market(self, bar: dict, ts=None) -> dict:
        return self.record("market", {"bar": bar}, ts=ts)

    def signal(self, signal: dict, ts=None) -> dict:
        return self.record("signal", signal, ts=ts)

    def order(self, order: dict, ts=None) -> dict:
        return self.record("order", order, ts=ts)

    def fill(self, fill: dict, ts=None) -> dict:
        return self.record("fill", fill, ts=ts)

    def close(self) -> dict:
        """Seal the session with a session_end record carrying the event
        count and stream digest (the recorded half of the determinism
        check that verify_deterministic performs on replay)."""
        body = {"session_id": self.session_id,
                "events_before_end": len(self._events),
                "stream_digest": stream_digest(self._events)}
        rec = self.record("session_end", body, ts=None)
        self._fh.close()
        return rec

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if not self._fh.closed:
            self.close()
        return False


def read_events(path) -> list[dict]:
    """Read a log and verify seq continuity + the full hash chain.
    Raises EventLogError on any gap, reorder, edit or truncation of a
    sealed record."""
    path = Path(path)
    events = []
    prev_hash = GENESIS_HASH
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise EventLogError(f"line {lineno}: invalid JSON: {e}") from e
        expected_seq = events[-1]["seq"] + 1 if events else 0
        if rec.get("seq") != expected_seq:
            raise EventLogError(
                f"line {lineno}: seq gap/reorder — expected {expected_seq}, got {rec.get('seq')}")
        if rec.get("prev_hash") != prev_hash:
            raise EventLogError(f"line {lineno}: prev_hash mismatch — chain broken")
        digest = _record_hash(rec["seq"], rec.get("ts"), rec["type"],
                              rec["payload"], rec["prev_hash"])
        if digest != rec.get("hash"):
            raise EventLogError(f"line {lineno}: hash mismatch — record altered")
        events.append(rec)
        prev_hash = rec["hash"]
    return events


def replay(path):
    """Yield the verified events of a log in recorded order. Replaying
    the same log always yields the identical sequence — that is the
    determinism contract the parity harness (ig/parity_harness.py)
    relies on."""
    yield from read_events(path)


def verify_deterministic(path) -> dict:
    """Replay twice and compare, and check the sealed session_end digest
    against the replayed stream. Returns a report dict; `deterministic`
    is True only if both replays are identical AND (when a session_end
    is present) its recorded digest matches the replayed stream."""
    first = read_events(path)
    second = read_events(path)
    identical = _canonical(first) == _canonical(second)
    sealed_ok = None
    ends = [e for e in first if e["type"] == "session_end"]
    if ends:
        end = ends[-1]
        before = first[:end["seq"]]
        sealed_ok = (
            end["payload"].get("events_before_end") == len(before)
            and end["payload"].get("stream_digest") == stream_digest(before))
    return {"events": len(first),
            "replays_identical": identical,
            "sealed_digest_matches": sealed_ok,
            "stream_digest": stream_digest(first),
            "deterministic": bool(identical and (sealed_ok is not False))}
