"""Tests for TASK-IG-STR-05 desk_journal (stdlib-only, offline)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.desk_journal import append_entry, read_entries, verify_chain


def test_append_and_verify(tmp_path):
    p = str(tmp_path / "journal.jsonl")
    r1 = append_entry(p, {"type": "memo", "desk": "x", "n": 1})
    r2 = append_entry(p, {"type": "post_mortem", "expected": "up",
                          "happened": "down", "lesson": "size smaller"})
    assert r2["prev_hash"] == r1["hash"]
    assert verify_chain(p) is True
    entries = read_entries(p)
    assert [e["type"] for e in entries] == ["memo", "post_mortem"]


def test_tamper_detected(tmp_path):
    p = str(tmp_path / "journal.jsonl")
    append_entry(p, {"type": "memo", "n": 1})
    append_entry(p, {"type": "memo", "n": 2})
    lines = Path(p).read_text().splitlines()
    rec = json.loads(lines[0])
    rec["n"] = 999  # rewrite history
    lines[0] = json.dumps(rec, sort_keys=True)
    Path(p).write_text("\n".join(lines) + "\n")
    assert verify_chain(p) is False


def test_post_mortem_requires_fields(tmp_path):
    p = str(tmp_path / "journal.jsonl")
    try:
        append_entry(p, {"type": "post_mortem", "expected": "x"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for incomplete post_mortem")
    try:
        append_entry(p, {"no_type": True})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for missing type")
