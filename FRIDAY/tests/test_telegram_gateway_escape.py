"""TASK-OBS-010 — the Telegram gateway HTML-escapes outbound text.

Contracts locked here (the OBS-008 gap (b) fix):
- ``send_message`` escapes ``&``, ``<``, ``>`` before sending: the API
  call uses ``parse_mode=HTML``, and a raw ``<...>`` in the text (a probe
  error such as ``<urlopen error ...>`` in a watcher alert) makes
  Telegram reject the whole message — OBS-008's first drill attempt
  returned ``NotifyResult.FAILED`` for exactly this reason;
- escaping happens in the gateway (the single send choke point), so
  every sender is covered — watcher alerts via ``notify_owner``, the
  daily/weekly self-report, brain replies, status lines — and no caller
  must escape as well (that would double-escape to ``&amp;lt;``);
- plain text passes through unchanged, and quotes stay literal
  (``quote=False``: only the three characters Telegram's HTML mode
  requires are escaped);
- chunking happens after escaping, so no chunk can ever carry a raw
  ``<`` or ``>``.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.proactive import telegram_gateway as tg  # noqa: E402

#: The exact alert text that failed to send in OBS-008 (first attempt).
OBS008_ALERT_TEXT = (
    "[CRITICAL] SERVICE_DOWN DrillProbe: ActiveState=inactive SubState=dead; "
    "error=URLError: <urlopen error [Errno 111] Connection refused>"
)


def _gateway(monkeypatch: pytest.MonkeyPatch) -> tg.TelegramGateway:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
    return tg.TelegramGateway()


class _CapturingApi:
    """Stand in for ``_api``: record sendMessage payloads, never hit the network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        return {"ok": True, "result": {"message_id": 1}}


class TestSendMessageEscapes:
    def test_obs008_alert_text_sends_escaped(self, monkeypatch):
        g = _gateway(monkeypatch)
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        assert g.send_message(OBS008_ALERT_TEXT) is True
        assert len(api.calls) == 1
        method, params = api.calls[0]
        assert method == "sendMessage"
        assert params["parse_mode"] == "HTML"
        assert params["text"] == html.escape(OBS008_ALERT_TEXT, quote=False)
        assert "<urlopen error" not in params["text"]
        assert "&lt;urlopen error [Errno 111] Connection refused&gt;" in params["text"]
        assert "<" not in params["text"] and ">" not in params["text"]

    def test_ampersand_is_escaped_so_no_entity_can_be_injected(self, monkeypatch):
        g = _gateway(monkeypatch)
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        assert g.send_message("A & B &lt;not a tag&gt;") is True
        assert api.calls[0][1]["text"] == "A &amp; B &amp;lt;not a tag&amp;gt;"

    def test_plain_text_passes_through_unchanged(self, monkeypatch):
        g = _gateway(monkeypatch)
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        text = "Fleet: 5/5 reachable at 04:10 AM IST\n✅ FRIDAY\n❌ IntelX"
        assert g.send_message(text) is True
        assert api.calls[0][1]["text"] == text

    def test_quotes_stay_literal(self, monkeypatch):
        g = _gateway(monkeypatch)
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        assert g.send_message('He said "hi" — it\'s fine') is True
        assert api.calls[0][1]["text"] == 'He said "hi" — it\'s fine'

    def test_well_formed_tag_renders_literally_not_bold(self, monkeypatch):
        # Documented trade-off: no caller relies on HTML formatting
        # through this gateway (code search: parse_mode appears only
        # here), so a ``<b>`` in a brain reply now shows literally
        # instead of bold — delivery is guaranteed instead of the
        # message failing outright on a malformed tag.
        g = _gateway(monkeypatch)
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        assert g.send_message("Use <b>bold</b> tags") is True
        assert api.calls[0][1]["text"] == "Use &lt;b&gt;bold&lt;/b&gt; tags"

    def test_long_text_chunks_after_escaping_with_no_raw_brackets(self, monkeypatch):
        g = _gateway(monkeypatch)
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        unit = "alert <urlopen error [Errno 111] Connection refused> "
        text = unit * 200  # ~10k chars raw, more escaped
        assert g.send_message(text) is True
        assert len(api.calls) > 1, "long text must still be chunked"
        for _, params in api.calls:
            assert "<" not in params["text"] and ">" not in params["text"]
            assert len(params["text"]) <= tg.MAX_MESSAGE_CHARS
        assert "".join(p["text"] for _, p in api.calls) == html.escape(text, quote=False)

    def test_no_chat_id_still_returns_false(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        g = tg.TelegramGateway()
        api = _CapturingApi()
        monkeypatch.setattr(g, "_api", api)
        assert g.send_message("hello <world>") is False
        assert api.calls == []


class TestSendOwnerMessageRouting:
    def test_send_owner_message_delegates_to_the_escaping_send_message(self, monkeypatch):
        # The module-level helper must hand the RAW text to the gateway's
        # send_message (which escapes); it must not escape itself, or
        # the text would double-escape.
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
        seen: list[str] = []
        monkeypatch.setattr(
            tg.telegram_gateway, "send_message", lambda text, chat_id=None: seen.append(text) or True
        )
        assert tg.send_owner_message(OBS008_ALERT_TEXT) is True
        assert seen == [OBS008_ALERT_TEXT], "gateway must receive the raw text and escape it"
