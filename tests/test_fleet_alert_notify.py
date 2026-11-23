"""TASK-OBS-014 — fleet alert forwarder unit tests.

Covers the pure forwarding logic of scripts/fleet_alert_notify.py:
raw text passthrough, stable event keys, exit codes per gate result,
and the FRIDAY/src path insertion. The real Telegram send is never
exercised here — notify_owner is monkeypatched; the live send is
proven by the controlled drill in TASK-OBS-014-FLEET-ALERT-COMMAND.md.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fleet_alert_notify.py"


def _load_script(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(module_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def notify_mod():
    return _load_script("fleet_alert_notify_under_test", _SCRIPT_PATH)


def _set_alert(monkeypatch, text, alert_json=None):
    monkeypatch.setenv("FLEET_ALERT_TEXT", text)
    if alert_json is None:
        monkeypatch.delenv("FLEET_ALERT_JSON", raising=False)
    else:
        monkeypatch.setenv("FLEET_ALERT_JSON", alert_json)


class TestForwarding:
    def test_raw_text_passed_through_unescaped(self, notify_mod, monkeypatch, capsys):
        calls = []

        def fake_notify(text, *, severity, event_key):
            calls.append((text, severity, event_key))
            return "sent"

        monkeypatch.setattr(notify_mod, "notify_owner", fake_notify)
        raw = "[CRITICAL] SERVICE_DOWN DrillProbe: error=URLError: <urlopen error [Errno 111] Connection refused>"
        _set_alert(
            monkeypatch,
            raw,
            '{"alert": "SERVICE_DOWN", "service": "DrillProbe", "detail": "x", "severity": "critical"}',
        )
        assert notify_mod.main() == 0
        assert len(calls) == 1
        text, severity, event_key = calls[0]
        assert text == raw  # no escaping, no truncation, no reformatting
        assert "<urlopen error" in text
        assert severity == 1  # Severity.ALERT
        assert event_key == "fleet_alert:DrillProbe:SERVICE_DOWN"
        assert "sent" in capsys.readouterr().out

    def test_missing_text_returns_2_and_never_calls(self, notify_mod, monkeypatch):
        calls = []
        monkeypatch.setattr(notify_mod, "notify_owner", lambda *a, **k: calls.append(1) or "sent")
        monkeypatch.delenv("FLEET_ALERT_TEXT", raising=False)
        assert notify_mod.main() == 2
        assert calls == []

    def test_blank_text_returns_2(self, notify_mod, monkeypatch):
        monkeypatch.setattr(notify_mod, "notify_owner", lambda *a, **k: "sent")
        monkeypatch.setenv("FLEET_ALERT_TEXT", "   ")
        assert notify_mod.main() == 2

    def test_invalid_json_falls_back_to_text_hash_key(self, notify_mod, monkeypatch):
        calls = []
        monkeypatch.setattr(
            notify_mod, "notify_owner",
            lambda text, *, severity, event_key: calls.append(event_key) or "sent",
        )
        text = "[WARNING] HEALTH_FAIL Memora: /health returned HTTP 503"
        _set_alert(monkeypatch, text, "{not json")
        assert notify_mod.main() == 0
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        assert calls == [f"fleet_alert:text:{digest}"]

    def test_missing_json_falls_back_to_text_hash_key(self, notify_mod, monkeypatch):
        calls = []
        monkeypatch.setattr(
            notify_mod, "notify_owner",
            lambda text, *, severity, event_key: calls.append(event_key) or "sent",
        )
        text = "[CRITICAL] CRASH_LOOP Forge: NRestarts 3 -> 6 (+3) in one window"
        _set_alert(monkeypatch, text, None)
        assert notify_mod.main() == 0
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        assert calls == [f"fleet_alert:text:{digest}"]

    def test_json_without_service_or_alert_falls_back(self, notify_mod, monkeypatch):
        calls = []
        monkeypatch.setattr(
            notify_mod, "notify_owner",
            lambda text, *, severity, event_key: calls.append(event_key) or "sent",
        )
        text = "[CRITICAL] SOMETHING odd"
        _set_alert(monkeypatch, text, '{"severity": "critical"}')
        assert notify_mod.main() == 0
        assert calls[0].startswith("fleet_alert:text:")

    def test_event_key_stable_for_same_condition(self, notify_mod, monkeypatch):
        keys = []
        monkeypatch.setattr(
            notify_mod, "notify_owner",
            lambda text, *, severity, event_key: keys.append(event_key) or "sent",
        )
        alert_json = '{"alert": "SERVICE_DOWN", "service": "Memora", "detail": "a", "severity": "critical"}'
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN Memora: detail a", alert_json)
        assert notify_mod.main() == 0
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN Memora: detail b", alert_json)
        assert notify_mod.main() == 0
        assert keys == ["fleet_alert:Memora:SERVICE_DOWN"] * 2


class TestExitCodes:
    @pytest.mark.parametrize("result", ["sent"])
    def test_sent_returns_0(self, notify_mod, monkeypatch, result):
        monkeypatch.setattr(notify_mod, "notify_owner", lambda *a, **k: result)
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN X: down", '{"alert": "SERVICE_DOWN", "service": "X"}')
        assert notify_mod.main() == 0

    @pytest.mark.parametrize(
        "result", ["below_bar", "duplicate", "cooldown", "daily_cap", "disabled"]
    )
    def test_held_results_return_0(self, notify_mod, monkeypatch, result):
        monkeypatch.setattr(notify_mod, "notify_owner", lambda *a, **k: result)
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN X: down", '{"alert": "SERVICE_DOWN", "service": "X"}')
        assert notify_mod.main() == 0

    @pytest.mark.parametrize("result", ["failed", "not_configured"])
    def test_unsent_results_return_2(self, notify_mod, monkeypatch, result):
        monkeypatch.setattr(notify_mod, "notify_owner", lambda *a, **k: result)
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN X: down", '{"alert": "SERVICE_DOWN", "service": "X"}')
        assert notify_mod.main() == 2

    def test_notify_raising_returns_2(self, notify_mod, monkeypatch, capsys):
        def boom(*a, **k):
            raise RuntimeError("gateway exploded")

        monkeypatch.setattr(notify_mod, "notify_owner", boom)
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN X: down", '{"alert": "SERVICE_DOWN", "service": "X"}')
        assert notify_mod.main() == 2
        assert "RuntimeError" in capsys.readouterr().out

    def test_no_notify_owner_available_returns_2(self, notify_mod, monkeypatch, capsys):
        # The unit env has no FRIDAY tree, so the real import fails and
        # notify_owner is None — the script must say so and exit 2.
        assert notify_mod.notify_owner is None
        _set_alert(monkeypatch, "[CRITICAL] SERVICE_DOWN X: down", '{"alert": "SERVICE_DOWN", "service": "X"}')
        assert notify_mod.main() == 2
        assert "NOT_CONFIGURED" in capsys.readouterr().out


class TestFridaySrcInsertion:
    def test_friday_src_inserted_when_present(self, tmp_path):
        root = tmp_path / "repo"
        (root / "scripts").mkdir(parents=True)
        (root / "FRIDAY" / "src").mkdir(parents=True)
        copied = root / "scripts" / "fleet_alert_notify.py"
        shutil.copy(_SCRIPT_PATH, copied)
        before = list(sys.path)
        mod = _load_script("fleet_alert_notify_insertion_probe", copied)
        assert str(root / "FRIDAY" / "src") in sys.path
        assert mod.notify_owner is None  # no real FRIDAY package under the fake src
        # Leave sys.path as the import left it; the probe module is isolated.
        assert before is not None
