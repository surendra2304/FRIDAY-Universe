from pathlib import Path
import time
import unittest

from mesh.envelope import AgentEnvelope, build_envelope, validate_envelope, verify_envelope


class EnvelopeVerificationTests(unittest.TestCase):
    def test_missing_required_fields_are_rejected(self):
        ok, reason = validate_envelope({"message_id": "x"})
        self.assertFalse(ok)
        self.assertIn("Missing required field", reason)

    def test_invalid_payload_type_is_rejected(self):
        ok, reason = validate_envelope({
            "message_id": "x",
            "correlation_id": "c",
            "from_agent": "FRIDAY",
            "to_agent": "MEMORA",
            "intent": "record",
            "priority": "normal",
            "ttl": 30,
            "payload": [],
        })
        self.assertFalse(ok)
        self.assertEqual(reason, "Payload must be a JSON object")

    def test_empty_agents_are_rejected(self):
        ok, reason = validate_envelope({
            "message_id": "x",
            "correlation_id": "c",
            "from_agent": "",
            "to_agent": "MEMORA",
            "intent": "record",
            "priority": "normal",
            "ttl": 30,
            "payload": {},
        })
        self.assertFalse(ok)
        self.assertIn("non-empty", reason)

    def test_signature_round_trip(self):
        envelope = build_envelope("FRIDAY", "MEMORA", "record", {"x": 1}, secret_key="s3cret")
        self.assertTrue(envelope.verify_signature("s3cret"))
        self.assertFalse(envelope.verify_signature("wrong"))

    def test_verify_envelope_accepts_valid_signed_envelope(self):
        envelope = build_envelope("FRIDAY", "MEMORA", "record", {"x": 1}, secret_key="s3cret")
        ok, reason = verify_envelope(envelope.to_dict(), "s3cret")
        self.assertTrue(ok, reason)

    def test_verify_envelope_rejects_tampered_payload(self):
        envelope = build_envelope("FRIDAY", "MEMORA", "record", {"x": 1}, secret_key="s3cret")
        data = envelope.to_dict()
        data["payload"]["x"] = 2
        ok, reason = verify_envelope(data, "s3cret")
        self.assertFalse(ok)
        self.assertIn("signature", reason)

    def test_expired_envelope_is_rejected(self):
        envelope = AgentEnvelope(from_agent="FRIDAY", to_agent="MEMORA", intent="record", ttl=1)
        envelope.created_at = time.time() - 5
        ok, reason = verify_envelope(envelope.to_dict())
        self.assertFalse(ok)
        self.assertIn("TTL expired", reason)

    def test_from_dict_round_trip(self):
        envelope = build_envelope("FRIDAY", "MEMORA", "record", {"x": 1}, secret_key="s3cret")
        restored = AgentEnvelope.from_dict(envelope.to_dict())
        self.assertEqual(restored.message_id, envelope.message_id)
        self.assertEqual(restored.payload, envelope.payload)
        self.assertEqual(restored.signature, envelope.signature)


if __name__ == "__main__":
    unittest.main()
