"""Tests for the TASK-INT-040 S2 -> S1 envelope shipper.

Standard library only (unittest): the shipper itself is stdlib-only so
it can run as a standalone timer job on S2, and these tests prove it
without network, servers, or the IntelX app. pytest collects
unittest.TestCase classes, so ``python -m pytest tests/
test_int040_outbox_shipper.py`` also works.

The staged scenario mirrors the real defect: S2's outbox holds the
two envelopes IntelX actually fired (harness adapters, 2026-11-20;
RBI "Stop Switch", 2026-11-23 22:03 IST), S1's outbox holds 4 older,
disjoint lines from its independent pre-move polling. After shipping,
S1 must hold all 6 with its original 4 byte-identical — the shipper
appends, never overwrites.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from intelx.watches.outbox_shipper import (
    ENVELOPE_SCHEMA,
    LocalAppendTransport,
    OutboxShipper,
    ShipResult,
    ShipperError,
    SshAppendTransport,
    read_complete_lines,
    read_envelope_ids,
    validate_envelope,
)


def make_envelope(watch_id, title, url, fired_at, alert_class="digest", score=5):
    fp = hashlib.sha256(url.encode()).hexdigest()[:16]
    return {
        "schema": ENVELOPE_SCHEMA,
        "envelope_id": hashlib.sha256(f"{watch_id}:{fp}".encode()).hexdigest(),
        "dedupe_key": f"intelx.watch:{watch_id}:{fp[:16]}",
        "watch_id": watch_id,
        "domain": "general",
        "alert_class": alert_class,
        "severity": "high" if alert_class == "instant" else "info",
        "quiet_hours_exempt": alert_class == "instant",
        "title": title,
        "summary": title,
        "url": url,
        "publisher": "test",
        "published_at": fired_at,
        "fired_at": fired_at,
        "score": score,
        "score_reasons": ["test"],
        "provenance": {"source_feed": "test", "fetched_at": fired_at, "task": "TASK-INT-040"},
    }


def write_outbox(path, envelopes, partial_tail=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for env in envelopes:
            fh.write(json.dumps(env, ensure_ascii=False) + "\n")
        if partial_tail is not None:
            fh.write(partial_tail)


class ShipperTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "s2" / "data" / "watches"
        self.dst = self.root / "s1" / "data" / "watches"
        self.src.mkdir(parents=True)
        self.dst.mkdir(parents=True)
        self.state = self.root / "shipper_state.json"
        self.log = self.root / "shipper.log.jsonl"

    def shipper(self, transport=None):
        return OutboxShipper(
            source_dir=self.src,
            transport=transport or LocalAppendTransport(self.dst),
            state_path=self.state,
            log_path=self.log,
        )

    def log_events(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]


class TestValidateEnvelope(ShipperTestBase):
    def test_valid_digest_and_instant(self):
        for cls in ("digest", "instant"):
            env = make_envelope("w1", "t", "https://x/1", "2026-11-23T16:33:00+00:00", cls)
            ok, reason = validate_envelope(env)
            self.assertTrue(ok, reason)

    def test_missing_field_rejected(self):
        env = make_envelope("w1", "t", "https://x/1", "2026-11-23T16:33:00+00:00")
        del env["envelope_id"]
        ok, reason = validate_envelope(env)
        self.assertFalse(ok)
        self.assertIn("envelope_id", reason)

    def test_wrong_schema_and_class_rejected(self):
        env = make_envelope("w1", "t", "https://x/1", "2026-11-23T16:33:00+00:00")
        env["schema"] = "other/9"
        self.assertFalse(validate_envelope(env)[0])
        env["schema"] = ENVELOPE_SCHEMA
        env["alert_class"] = "urgent"
        self.assertFalse(validate_envelope(env)[0])


class TestReadCompleteLines(ShipperTestBase):
    def test_partial_tail_held_until_terminated(self):
        p = self.src / "outbox.jsonl"
        write_outbox(p, [make_envelope("w1", "a", "https://x/1", "2026-11-23T16:33:00+00:00")],
                     partial_tail='{"schema": "intelx.watch_alert/1", "partial')
        lines, off = read_complete_lines(p, 0)
        self.assertEqual(len(lines), 1)
        # Second read at the new offset: nothing complete yet.
        lines2, off2 = read_complete_lines(p, off)
        self.assertEqual(lines2, [])
        self.assertEqual(off2, off)
        # Terminate the partial line; it is now readable.
        with p.open("a", encoding="utf-8") as fh:
            fh.write('": true}\n')
        lines3, _ = read_complete_lines(p, off)
        self.assertEqual(len(lines3), 1)

    def test_missing_file_is_empty_not_error(self):
        lines, off = read_complete_lines(self.src / "nope.jsonl", 0)
        self.assertEqual((lines, off), ([], 0))

    def test_shrunk_file_restarts_at_zero(self):
        p = self.src / "outbox.jsonl"
        write_outbox(p, [make_envelope("w1", "a", "https://x/1", "2026-11-23T16:33:00+00:00")])
        _, off = read_complete_lines(p, 0)
        self.assertGreater(off, 0)
        p.write_text('{"schema": "x"}\n', encoding="utf-8")
        lines, off2 = read_complete_lines(p, off)
        self.assertEqual(len(lines), 1)
        self.assertGreater(off2, 0)


class TestShipLanes(ShipperTestBase):
    def test_digest_and_instant_lanes_shipped_byte_identical(self):
        digest = make_envelope("india_tech_regulatory", "RBI Stop Switch",
                               "https://rbi.example/stop-switch", "2026-11-23T16:33:00+00:00")
        instant = make_envelope("ai_model_releases", "Big model break",
                                "https://example.com/big-break", "2026-11-24T10:00:00+00:00",
                                alert_class="instant", score=8)
        write_outbox(self.src / "outbox.jsonl", [digest])
        write_outbox(self.src / "instant_outbox.jsonl", [instant])
        result = self.shipper().run()
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.shipped, 2)
        self.assertEqual((self.dst / "outbox.jsonl").read_text().strip(),
                         json.dumps(digest, ensure_ascii=False))
        self.assertEqual((self.dst / "instant_outbox.jsonl").read_text().strip(),
                         json.dumps(instant, ensure_ascii=False))
        events = self.log_events()
        self.assertEqual([e["envelope_id"] for e in events if e["event"] == "shipped"],
                         [digest["envelope_id"], instant["envelope_id"]])
        self.assertTrue(any(e["event"] == "run_summary" and e["ok"] for e in events))

    def test_second_run_ships_nothing_restart_is_idempotent(self):
        env = make_envelope("w1", "a", "https://x/1", "2026-11-23T16:33:00+00:00")
        write_outbox(self.src / "outbox.jsonl", [env])
        self.assertEqual(self.shipper().run().shipped, 1)
        # Fresh instance, same state file: nothing new to ship.
        result = self.shipper().run()
        self.assertEqual(result.shipped, 0)
        self.assertEqual(len((self.dst / "outbox.jsonl").read_text().splitlines()), 1)

    def test_malformed_line_counted_and_tail_not_wedged(self):
        good1 = make_envelope("w1", "a", "https://x/1", "2026-11-23T16:33:00+00:00")
        good2 = make_envelope("w1", "b", "https://x/2", "2026-11-23T17:00:00+00:00")
        bad = make_envelope("w1", "c", "https://x/3", "2026-11-23T17:30:00+00:00")
        del bad["dedupe_key"]
        p = self.src / "outbox.jsonl"
        write_outbox(p, [good1])
        with p.open("a", encoding="utf-8") as fh:
            fh.write("this is not json\n")
            fh.write(json.dumps(bad) + "\n")
            fh.write(json.dumps(good2) + "\n")
        result = self.shipper().run()
        self.assertTrue(result.ok)
        self.assertEqual(result.shipped, 2)
        lane = result.lanes[0]
        self.assertEqual(lane.malformed, 2)  # unparseable line + missing field
        dest_ids = read_envelope_ids(self.dst / "outbox.jsonl")
        self.assertEqual(dest_ids, {good1["envelope_id"], good2["envelope_id"]})

    def test_source_replaced_reship_is_deduped_not_duplicated(self):
        env = make_envelope("w1", "a", "https://x/1", "2026-11-23T16:33:00+00:00")
        p = self.src / "outbox.jsonl"
        write_outbox(p, [env])
        self.assertEqual(self.shipper().run().shipped, 1)
        # Source file replaced with the same envelope serialised more
        # compactly (fewer bytes, so the offset restarts at 0); the
        # shipped-ids set must prevent a duplicate line landing on S1.
        p.write_text(json.dumps(env, separators=(",", ":")) + "\n", encoding="utf-8")
        result = self.shipper().run()
        self.assertEqual(result.shipped, 0)
        self.assertEqual(result.lanes[0].skipped_duplicate, 1)
        self.assertEqual(len((self.dst / "outbox.jsonl").read_text().splitlines()), 1)


class TestFailureVisibility(ShipperTestBase):
    def test_failed_ship_is_recorded_offset_not_advanced_and_retries(self):
        class FailingTransport:
            def append_lines(self, dest_name, lines):
                raise ShipperError("boom: ssh: connect to host 10.0.0.121 port 22: refused")

        env = make_envelope("w1", "a", "https://x/1", "2026-11-23T16:33:00+00:00")
        write_outbox(self.src / "outbox.jsonl", [env])
        result = self.shipper(transport=FailingTransport()).run()
        self.assertFalse(result.ok)
        self.assertEqual(result.shipped, 0)
        self.assertTrue(result.errors)
        self.assertFalse((self.dst / "outbox.jsonl").exists())
        events = self.log_events()
        self.assertTrue(any(e["event"] == "ship_failed" for e in events))
        self.assertTrue(any(e["event"] == "run_summary" and not e["ok"] for e in events))
        # Retry with a working transport ships the same envelope.
        result2 = self.shipper().run()
        self.assertTrue(result2.ok)
        self.assertEqual(result2.shipped, 1)

    def test_audit_finds_missing_rbi_envelope_then_goes_clean(self):
        harness = make_envelope("ai_model_releases", "harness adapters",
                                "https://example.com/harness", "2026-11-20T18:26:00+00:00", score=4)
        rbi = make_envelope("india_tech_regulatory", "RBI Stop Switch payments-fraud proposal",
                            "https://rbi.example/stop-switch", "2026-11-23T16:33:00+00:00", score=5)
        write_outbox(self.src / "outbox.jsonl", [harness, rbi])
        # S1 holds 4 older, disjoint lines from pre-move polling.
        s1_old = [make_envelope("ai_model_releases", f"old {i}",
                                f"https://example.com/old-{i}",
                                "2026-11-20T10:00:00+00:00", score=3)
                  for i in range(4)]
        write_outbox(self.dst / "outbox.jsonl", s1_old)
        s1_before = (self.dst / "outbox.jsonl").read_bytes()

        report = self.shipper().audit(self.dst)
        self.assertEqual(len(report["missing"]), 2)
        self.assertEqual({m["envelope_id"] for m in report["missing"]},
                         {harness["envelope_id"], rbi["envelope_id"]})

        result = self.shipper().run()
        self.assertEqual(result.shipped, 2)
        # S1's original 4 lines are preserved byte-identical at the head.
        dest_bytes = (self.dst / "outbox.jsonl").read_bytes()
        self.assertTrue(dest_bytes.startswith(s1_before))
        self.assertEqual(len(dest_bytes.decode().splitlines()), 6)
        report2 = self.shipper().audit(self.dst)
        self.assertEqual(report2["missing"], [])
        self.assertEqual(report2["per_lane"]["outbox.jsonl"],
                         {"source": 2, "destination": 6, "missing": 0})


class TestSshTransportCommand(ShipperTestBase):
    def test_ssh_command_appends_only_no_other_remote_command(self):
        t = SshAppendTransport(host="10.0.0.121",
                             dest_dir="/opt/friday_universe/IntelX/data/watches")
        cmd = t._ssh_cmd("outbox.jsonl")
        self.assertEqual(cmd[0], "ssh")
        self.assertIn("10.0.0.121", cmd)
        remote = cmd[-1]
        self.assertTrue(remote.startswith("cat >> "))
        self.assertIn("outbox.jsonl", remote)
        # No shell metacharacters beyond the single append redirect.
        self.assertNotIn(";", remote)
        self.assertNotIn("&&", remote)

    def test_ssh_transport_rejects_missing_host_or_dir(self):
        from intelx.watches.outbox_shipper import build_live_transport
        import os
        os.environ.pop("INTELX_OUTBOX_SHIPPER_DEST_HOST", None)
        os.environ.pop("INTELX_OUTBOX_SHIPPER_DEST_DIR", None)
        with self.assertRaises(ShipperError):
            build_live_transport()



class TestReadOutboxEnvelopes(unittest.TestCase):
    """TASK-INT-060: producer-side snapshot behind GET /v1/watches/outbox."""

    def test_missing_outbox_is_empty_not_an_error(self):
        from intelx.watches.engine import read_outbox_envelopes

        with tempfile.TemporaryDirectory() as tmp:
            snap = read_outbox_envelopes(Path(tmp) / "outbox.jsonl")
        self.assertEqual(snap, {"size": 0, "envelopes": [], "malformed": 0})

    def test_valid_and_malformed_lines(self):
        from intelx.watches.engine import read_outbox_envelopes

        env = make_envelope("w1", "t", "https://x/1", "2026-11-23T16:33:00+00:00")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outbox.jsonl"
            write_outbox(path, [env], partial_tail="{not json\n")
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"schema": "other/9"}) + "\n")
            snap = read_outbox_envelopes(path)
        self.assertEqual([e["envelope_id"] for e in snap["envelopes"]], [env["envelope_id"]])
        self.assertEqual(snap["malformed"], 2)
        self.assertGreater(snap["size"], 0)


if __name__ == "__main__":
    unittest.main()
