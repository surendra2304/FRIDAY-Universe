"""Append-only, hash-chained research journal for the Stratex desk.

TASK-IG-STR-05 (pattern: tradermonty/claude-trading-skills trade-memory
and post-mortem skills — see the repo card).

Every desk memo and post-mortem is appended as one JSON line carrying
the SHA-256 of the previous line, so the journal's history cannot be
quietly rewritten: verify_chain() detects any edit, deletion, or
reordering. Post-mortems use the fixed fields expected / happened /
lesson — a journal that only records wins is marketing, not research.

Local research tooling only: the journal is a file the caller owns; it
is not the production fill ledger and feeds nothing live.

Stdlib only, Python 3.10-compatible.
"""

import hashlib
import json
import os

GENESIS = "0" * 64


def _hash(prev_hash, payload):
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def append_entry(path, entry):
    """Append `entry` (a JSON-serialisable dict) to the journal at
    `path`, chained to the last entry's hash. Returns the stored
    record (entry + prev_hash + hash). The caller must include a
    "type" field ("memo" or "post_mortem"); post-mortems must carry
    expected / happened / lesson."""
    if "type" not in entry:
        raise ValueError("journal entries require a 'type' field")
    if entry["type"] == "post_mortem":
        missing = [k for k in ("expected", "happened", "lesson")
                   if not entry.get(k)]
        if missing:
            raise ValueError(
                "post_mortem entries require non-empty: %s" % missing)
    prev = GENESIS
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        if lines:
            prev = json.loads(lines[-1])["hash"]
    record = dict(entry)
    record["prev_hash"] = prev
    payload = json.dumps(record, sort_keys=True)
    record["hash"] = _hash(prev, payload)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_entries(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh.read().splitlines() if ln.strip()]


def verify_chain(path):
    """True iff every line's hash matches its contents and links to
    the previous line's hash, in order, from the genesis hash."""
    prev = GENESIS
    for rec in read_entries(path):
        stored = rec.get("hash")
        body = {k: v for k, v in rec.items() if k != "hash"}
        if body.get("prev_hash") != prev:
            return False
        if _hash(prev, json.dumps(body, sort_keys=True)) != stored:
            return False
        prev = stored
    return True
