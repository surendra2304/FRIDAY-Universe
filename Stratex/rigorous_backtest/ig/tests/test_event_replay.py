"""Tests for TASK-IG2-STR-06 event_replay (stdlib-only, offline)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.event_replay import (  # noqa: E402
    EventLogError, EventRecorder, read_events, replay, stream_digest,
    verify_deterministic,
)

BAR = {"time": 0, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}


def write_session(path, session_id="s1"):
    with EventRecorder(path, session_id) as rec:
        rec.market(BAR, ts=0)
        rec.signal({"bar": 0, "side": "LONG", "sl": 97.5, "tp": 103.0}, ts=0)
        rec.order({"bar": 1, "side": "LONG", "qty": 1.0, "kind": "BRACKET"}, ts=1)
        rec.fill({"bar": 1, "side": "LONG", "price": 100.5, "qty": 1.0}, ts=1)
    return path


def test_record_and_replay_roundtrip(tmp_path):
    path = write_session(tmp_path / "log.jsonl")
    events = read_events(path)
    assert [e["type"] for e in events] == [
        "session_start", "market", "signal", "order", "fill", "session_end"]
    assert [e["seq"] for e in events] == list(range(len(events)))
    assert list(replay(path)) == events
    report = verify_deterministic(path)
    assert report["deterministic"] is True
    assert report["replays_identical"] is True
    assert report["sealed_digest_matches"] is True


def test_identical_sessions_produce_identical_logs(tmp_path):
    a = write_session(tmp_path / "a.jsonl")
    b = write_session(tmp_path / "b.jsonl")
    assert a.read_bytes() == b.read_bytes()
    assert stream_digest(read_events(a)) == stream_digest(read_events(b))


def test_tampered_payload_is_detected(tmp_path):
    path = write_session(tmp_path / "log.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[3] = lines[3].replace('"qty":1.0', '"qty":9.0')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(EventLogError):
        read_events(path)


def test_deleted_event_is_detected(tmp_path):
    path = write_session(tmp_path / "log.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[2]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(EventLogError):
        read_events(path)


def test_reordered_events_are_detected(tmp_path):
    path = write_session(tmp_path / "log.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[2], lines[3] = lines[3], lines[2]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(EventLogError):
        read_events(path)


def test_second_session_appends_and_chain_still_verifies(tmp_path):
    path = write_session(tmp_path / "log.jsonl", session_id="s1")
    first_len = len(read_events(path))
    with EventRecorder(path, "s2") as rec:
        rec.market(BAR, ts=10)
    events = read_events(path)
    assert len(events) > first_len
    assert events[first_len]["type"] == "session_start"
    assert events[first_len]["payload"]["session_id"] == "s2"
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_unknown_event_type_rejected(tmp_path):
    with EventRecorder(tmp_path / "log.jsonl", "s1") as rec:
        with pytest.raises(ValueError):
            rec.record("teleport", {}, ts=0)
