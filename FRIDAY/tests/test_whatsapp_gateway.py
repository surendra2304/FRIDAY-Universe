"""TASK-IG2-FRD-02 — WhatsApp channel gateway (OpenClaw pattern).

Contracts locked here:
- the gateway is inert until WHATSAPP_ACCESS_TOKEN / _PHONE_NUMBER_ID /
  _OWNER_NUMBER are configured (start() False, stays silent);
- Meta's subscription handshake echoes the challenge only for the right
  verify token;
- X-Hub-Signature-256 is verified over the raw body and FAILS CLOSED
  when no app secret is configured;
- the owner gate matches Telegram's: only the owner's number reaches
  the brain; any other sender gets one refusal line and no processing;
- /status and /missions are deterministic; other text goes to the same
  brain callable; duplicate webhook deliveries are dropped by id.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.proactive import whatsapp_gateway as wa  # noqa: E402

OWNER = "919999999999"
APP_SECRET = "test-app-secret"


def _configured(monkeypatch: pytest.MonkeyPatch, brain=None) -> wa.WhatsAppGateway:
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1234567890")
    monkeypatch.setenv("WHATSAPP_OWNER_NUMBER", OWNER)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    gateway = wa.WhatsAppGateway(send_interval=0)
    if brain is not None:
        gateway.set_brain(brain)
    return gateway


def _capture_sends(gateway: wa.WhatsAppGateway) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []
    gateway._api_send = lambda to, text: (sent.append((to, text)), True)[1]  # type: ignore[method-assign]
    return sent


def _payload(text: str, sender: str = OWNER, mid: str = "wamid.1") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": sender, "profile": {"name": "Owner"}}],
                            "messages": [
                                {"id": mid, "from": sender, "type": "text", "text": {"body": text}}
                            ],
                        }
                    }
                ]
            }
        ],
    }


# ----------------------------------------------------------------------
# configuration gates
# ----------------------------------------------------------------------

def test_unconfigured_gateway_stays_off(monkeypatch):
    for key in (
        "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_OWNER_NUMBER",
        "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    gateway = wa.WhatsAppGateway()
    assert gateway.is_configured() is False
    assert gateway.start() is False
    assert gateway.running is False


def test_configured_gateway_starts(monkeypatch):
    gateway = _configured(monkeypatch)
    assert gateway.is_configured() is True
    assert gateway.start() is True
    assert gateway.running is True
    gateway.stop()
    assert gateway.running is False


# ----------------------------------------------------------------------
# Meta handshakes
# ----------------------------------------------------------------------

def test_verify_subscription_echoes_only_for_right_token(monkeypatch):
    gateway = _configured(monkeypatch)
    assert gateway.verify_subscription("subscribe", "verify-me", "challenge-42") == "challenge-42"
    assert gateway.verify_subscription("subscribe", "wrong", "challenge-42") is None
    assert gateway.verify_subscription("unsubscribe", "verify-me", "challenge-42") is None


def test_signature_matches_hmac_and_fails_closed(monkeypatch):
    gateway = _configured(monkeypatch)
    body = json.dumps(_payload("hello")).encode()
    good = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert gateway.signature_matches(body, good) is True
    assert gateway.signature_matches(body, "sha256=deadbeef") is False
    assert gateway.signature_matches(body, None) is False
    # No app secret configured → fail closed, even for a well-formed header.
    monkeypatch.delenv("WHATSAPP_APP_SECRET")
    monkeypatch.setattr(wa, "_env_config", lambda: {k: "" for k in (
        "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_OWNER_NUMBER",
        "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN")})
    assert gateway.signature_matches(body, good) is False


# ----------------------------------------------------------------------
# payload extraction + owner gate + brain
# ----------------------------------------------------------------------

def test_extract_messages_text_only():
    payload = _payload("check the fleet")
    payload["entry"][0]["changes"][0]["value"]["statuses"] = [{"id": "wamid.0", "status": "delivered"}]
    payload["entry"][0]["changes"][0]["value"]["messages"].append(
        {"id": "wamid.2", "from": OWNER, "type": "image", "image": {"id": "x"}}
    )
    messages = wa.WhatsAppGateway.extract_messages(payload)
    assert len(messages) == 1
    assert messages[0]["text"] == "check the fleet"
    assert messages[0]["from"] == OWNER


def test_non_owner_is_refused_and_never_reaches_brain(monkeypatch):
    calls: list[str] = []
    gateway = _configured(monkeypatch, brain=lambda text: calls.append(text) or {"reply": "x"})
    sent = _capture_sends(gateway)
    gateway.process_message_for_tests({"id": "m1", "from": "14155550123", "text": "do something", "name": "Stranger"})
    assert calls == []
    assert len(sent) == 1
    assert "answers only to him" in sent[0][1]
    assert sent[0][0] == "14155550123"


def test_owner_text_reaches_brain_and_reply_is_sent(monkeypatch):
    gateway = _configured(monkeypatch, brain=lambda text: {"reply": f"echo:{text}"})
    sent = _capture_sends(gateway)
    gateway.process_message_for_tests({"id": "m2", "from": OWNER, "text": "check Stratex", "name": "Owner"})
    assert sent == [(OWNER, "echo:check Stratex")]


def test_owner_number_with_plus_and_spaces_still_matches(monkeypatch):
    gateway = _configured(monkeypatch, brain=lambda text: {"reply": "ok"})
    sent = _capture_sends(gateway)
    gateway.process_message_for_tests({"id": "m3", "from": "+91 99999 99999", "text": "ping", "name": "Owner"})
    assert sent and sent[0][1] == "ok"


def test_brain_failure_is_reported_not_faked(monkeypatch):
    def boom(text):
        raise RuntimeError("engine down")

    gateway = _configured(monkeypatch, brain=boom)
    sent = _capture_sends(gateway)
    gateway.process_message_for_tests({"id": "m4", "from": OWNER, "text": "ping", "name": "Owner"})
    assert sent and "Nothing was faked" in sent[0][1]


def test_duplicate_webhook_delivery_dropped(monkeypatch):
    calls: list[str] = []
    gateway = _configured(monkeypatch, brain=lambda text: calls.append(text) or {"reply": "ok"})
    _capture_sends(gateway)
    payload = _payload("hello", mid="wamid.dup")
    assert gateway.process_webhook_payload(payload) == 1
    assert gateway.process_webhook_payload(payload) == 0


def test_send_message_splits_long_text(monkeypatch):
    gateway = _configured(monkeypatch)
    sent = _capture_sends(gateway)
    assert gateway.send_message("x" * 9000) is True
    assert len(sent) == 3
    assert all(len(chunk) <= wa.MAX_MESSAGE_CHARS for _, chunk in sent)
