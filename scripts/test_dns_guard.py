"""dns_guard tests — pinned offline, no network access needed.

Covers the 2026-11-13 incident exactly: public DoH answers with foreign IPs,
the guard must detect drift, attempt auto-correction only when a token
exists, alert once (cooldown latch), and stay healthy on match.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import dns_guard  # noqa: E402


class _Resp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        if isinstance(self._payload, (bytes, bytearray)):
            return bytes(self._payload)
        if isinstance(self._payload, str):
            return self._payload.encode()
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _doh(ip_list):
    return {"Answer": [{"type": 1, "data": ip} for ip in ip_list]}


def test_resolve_public_uses_first_answering_resolver():
    with mock.patch.object(
        urllib.request, "urlopen", side_effect=lambda req, timeout=None: _Resp(_doh(["1.2.3.4"]))
    ):
        assert dns_guard.resolve_public("x.example") == ["1.2.3.4"]


def test_resolve_public_swallows_total_failure():
    def boom(req, timeout=None):
        raise OSError("no network")

    with mock.patch.object(urllib.request, "urlopen", side_effect=boom):
        assert dns_guard.resolve_public("x.example") == []


def test_run_healthy_match_exits_zero(capsys):
    with mock.patch.object(dns_guard, "resolve_public", return_value=["140.245.208.100"]):
        rc = dns_guard.run("n", ["140.245.208.100"], None, 1800, False)
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_run_detects_drift_and_alerts(tmp_path, capsys):
    state = tmp_path / "state.json"
    with mock.patch.object(dns_guard, "STATE_PATH", state), mock.patch.object(
        dns_guard, "resolve_public", return_value=["192.155.84.236"]
    ), mock.patch.object(
        dns_guard, "telegram_alert", return_value=True
    ) as alert, mock.patch.object(
        dns_guard, "_credential", side_effect=lambda kind: {"telegram_token": "t", "telegram_chat": "c"}.get(kind, "")
    ):
        rc = dns_guard.run("friday-universe.duckns.org", ["140.245.208.100"], None, 1800, False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRIFT" in out and "192.155.84.236" in out and "140.245.208.100" in out
    assert alert.call_count == 1
    saved = json.loads(state.read_text())
    assert saved["last_alert_key"].startswith("dns-drift")


def test_run_cooldown_latch_prevents_spam(tmp_path, capsys):
    state = tmp_path / "state.json"
    with mock.patch.object(dns_guard, "STATE_PATH", state), mock.patch.object(
        dns_guard, "resolve_public", return_value=["192.155.84.236"]
    ), mock.patch.object(
        dns_guard, "telegram_alert", return_value=True
    ) as alert, mock.patch.object(
        dns_guard, "_credential", side_effect=lambda kind: {"telegram_token": "t", "telegram_chat": "c"}.get(kind, "")
    ):
        dns_guard.run("n", ["140.245.208.100"], None, 1800, False)
        dns_guard.run("n", ["140.245.208.100"], None, 1800, False)
    assert alert.call_count == 1  # second identical drift held by cooldown
    assert "cooldown held" in capsys.readouterr().out


def test_run_auto_fix_attempts_duckdns_only_with_token(tmp_path, capsys):
    state = tmp_path / "state.json"
    # without token: honest manual-fix note, no update call
    with mock.patch.object(dns_guard, "STATE_PATH", state), mock.patch.object(
        dns_guard, "resolve_public", return_value=["192.155.84.236"]
    ), mock.patch.object(
        dns_guard, "duckdns_update", return_value=(True, "OK")
    ) as upd, mock.patch.object(
        dns_guard, "telegram_alert", return_value=True
    ), mock.patch.object(
        dns_guard, "_credential", side_effect=lambda kind: {"telegram_token": "t", "telegram_chat": "c"}.get(kind, "")
    ):
        dns_guard.run("n", ["140.245.208.100"], "friday-universe", 1800, False)
        assert upd.call_count == 0
        assert "NO DuckDNS token" in capsys.readouterr().out
    # with token: one update call targeting the expected IP
    with mock.patch.object(dns_guard, "STATE_PATH", tmp_path / "s2.json"), mock.patch.object(
        dns_guard, "resolve_public", return_value=["192.155.84.236"]
    ), mock.patch.object(
        dns_guard, "duckdns_update", return_value=(True, "OK")
    ) as upd, mock.patch.object(
        dns_guard, "telegram_alert", return_value=True
    ), mock.patch.object(
        dns_guard, "_credential", side_effect=lambda kind: {"telegram_token": "t", "telegram_chat": "c", "duckdns_token": "tok"}.get(kind, "")
    ):
        dns_guard.run("n", ["140.245.208.100"], "friday-universe", 1800, False)
    upd.assert_called_once_with("friday-universe", "tok", "140.245.208.100")
    assert "auto-correct attempted" in capsys.readouterr().out


def test_credential_never_in_stdout():
    # resolver failures return empty string, never a value echo
    with mock.patch.object(dns_guard, "REPO", Path("/nonexistent")):
        assert dns_guard._credential("duckdns_token") == ""


def test_duckdns_update_url_shape():
    captured = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        return _Resp("OK")

    with mock.patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
        ok, resp = dns_guard.duckdns_update("friday-universe", "SECRET-TOKEN", "1.2.3.4")
    assert ok and resp == "OK"
    assert "domains=friday-universe" in captured["url"] and "ip=1.2.3.4" in captured["url"]
    assert "SECRET-TOKEN" in captured["url"]  # token goes to duckdns.org only, never to logs


def test_duckdns_token_reads_from_credentials_section(tmp_path):
    # 2026-11-14 regression pin: house vault format (DuckDNS section at EOF).
    # The pre-fix section regex could never cross the header newline, so the
    # token was unreachable — found the moment the owner supplied a real token.
    creds = tmp_path / "credentials.md"
    creds.write_text(
        "# FRIDAY Universe — Credentials\n\n"
        "## Telegram bots\n\n- token: 123456789:AAExampleTelegramShapeNotDuckDns\n\n"
        "## DuckDNS (owner-supplied 2026-11-14)\n\n"
        "- Service: DuckDNS dynamic DNS — friday-universe.duckns.org -> 140.245.208.100\n"
        "- token: aaaa0000-bbbb-11cc-22dd-eeeeeeeeeeee\n"
        "- Verified live: 2026-11-14 ~11:45 IST\n"
    )
    with mock.patch.object(dns_guard, "REPO", tmp_path):
        assert dns_guard._credential("duckdns_token") == "aaaa0000-bbbb-11cc-22dd-eeeeeeeeeeee"


def test_duckdns_token_section_boundary_stops_at_next_header(tmp_path):
    # DuckDNS section mid-file: a LATER section's hex token must not leak in.
    creds = tmp_path / "credentials.md"
    creds.write_text(
        "## DuckDNS (owner-supplied)\n\n- token: 11110000-2222-33cc-44dd-555555555555\n\n"
        "## OANDA Demo\n\n- API token: 9999aaaa8888bbbb\n"
    )
    with mock.patch.object(dns_guard, "REPO", tmp_path):
        assert dns_guard._credential("duckdns_token") == "11110000-2222-33cc-44dd-555555555555"


def test_duckdns_token_empty_when_no_section(tmp_path):
    creds = tmp_path / "credentials.md"
    creds.write_text("## OANDA Demo\n\n- API token: abcdefabcdefabcdef\n")
    with mock.patch.object(dns_guard, "REPO", tmp_path):
        assert dns_guard._credential("duckdns_token") == ""
