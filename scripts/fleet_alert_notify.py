#!/usr/bin/env python3
"""TASK-OBS-014 — fleet alert forwarder (the FLEET_ALERT_COMMAND).

The fleet health watcher (`scripts/fleet_health_watcher.py`) invokes this
script once per NEW alert, with two environment variables:

  FLEET_ALERT_TEXT  the raw alert line, e.g.
                    ``[CRITICAL] SERVICE_DOWN Memora: ActiveState=inactive ...``
  FLEET_ALERT_JSON  the alert dict as JSON
                    (``{"alert": ..., "service": ..., "detail": ..., "severity": ...}``)

This script forwards that text to the owner on Telegram through the
fleet's single gated path, ``friday.proactive.owner_notify.notify_owner``
(the @fridayuniverse_bot credentials, the OBS-010 HTML-escape fix, the
kill switch, daily cap, per-key cooldown and text dedupe all live
there). It adds no second sender and no new credentials: the gateway
resolves the bot token / chat id from the process environment, then the
repo-root ``.env``, exactly as the deployed FRIDAY service does.

Wired as the watcher's alert command on both Oracle servers via a
systemd drop-in (see docs/collaboration/TASK-OBS-014-FLEET-ALERT-COMMAND.md):

  Environment=FLEET_ALERT_COMMAND=/opt/friday_universe/venv/bin/python /opt/friday_universe/scripts/fleet_alert_notify.py

Design rules (locked by tests/test_fleet_alert_notify.py):

- The alert text is passed through RAW. The watcher hands raw text to
  the command and the gateway escapes it once (OBS-010 single-escape
  point); this script must never escape, truncate or reformat it.
- Severity is always ALERT. RECOVERED alerts never reach the command
  (the watcher prints and closes them before dispatch), so every
  alert this script sees is a real incident the owner wants now.
- The event key is stable per condition — ``fleet_alert:<service>:<alert>``
  from FLEET_ALERT_JSON — so the gate's per-key cooldown dedupes a
  flapping service. When the JSON is missing or unparsable, the key
  falls back to a hash of the text (stable per distinct text).
- Exit codes: 0 = sent, or deliberately held by the gate (below bar /
  duplicate / cooldown / daily cap / kill switch off — the gate held
  it, the watcher must not treat that as failure); 2 = the alert did
  NOT reach the owner (send failed, gateway not configured, FRIDAY
  tree unavailable, or no alert text in the environment). The watcher
  invokes the command with ``check=False`` and journals the printed
  ``FLEET-ALERT-NOTIFY`` line either way.
- Never raises into the watcher: every failure path prints a line and
  returns 2. No secret is ever printed (the text itself is the alert,
  which the owner is meant to see; tokens/chat ids are never read here).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The FRIDAY package lives under FRIDAY/src, not on the default path.
# Insert it (repo-root derived from this file) so the script works both
# from a checkout and from the deployed /opt/friday_universe tree.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_FRIDAY_SRC = _REPO_ROOT / "FRIDAY" / "src"
if _FRIDAY_SRC.is_dir() and str(_FRIDAY_SRC) not in sys.path:
    sys.path.insert(0, str(_FRIDAY_SRC))

try:  # pragma: no cover - exercised by the real tree, not the unit env
    from friday.proactive.owner_notify import Severity, notify_owner
except Exception:  # noqa: BLE001 - FRIDAY tree absent in the unit-test env
    notify_owner = None  # type: ignore[assignment]
    Severity = None  # type: ignore[assignment]

#: Severity.ALERT is IntEnum 1; the literal keeps the unit env working
#: when the real import is unavailable (notify_owner is None there too).
_ALERT_SEVERITY = Severity.ALERT if Severity is not None else 1

#: Gate results that mean the message was deliberately held, not lost.
_HELD_RESULTS = {"below_bar", "duplicate", "cooldown", "daily_cap", "disabled"}


def _event_key(text: str) -> str:
    """Stable per-condition key for the owner-notify gate."""
    raw_json = os.environ.get("FLEET_ALERT_JSON") or ""
    try:
        data = json.loads(raw_json) if raw_json.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    if isinstance(data, dict):
        service = str(data.get("service") or "").strip()
        alert = str(data.get("alert") or "").strip()
        if service and alert:
            return f"fleet_alert:{service}:{alert}"
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"fleet_alert:text:{digest}"


def _result_value(result) -> str:
    """NotifyResult (a str Enum) or a plain string, normalised to text."""
    return str(getattr(result, "value", result))


def main(argv: list[str] | None = None) -> int:
    """Forward $FLEET_ALERT_TEXT to the owner. Returns an exit code."""
    del argv  # no CLI arguments; everything arrives via the environment
    text = (os.environ.get("FLEET_ALERT_TEXT") or "").strip()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not text:
        print(
            "FLEET-ALERT-NOTIFY: no FLEET_ALERT_TEXT in environment; "
            "nothing forwarded",
            file=sys.stderr,
            flush=True,
        )
        return 2
    if notify_owner is None:
        print(
            f"FLEET-ALERT-NOTIFY [{stamp}]: NOT_CONFIGURED "
            "(friday.proactive.owner_notify unavailable); alert not sent",
            flush=True,
        )
        return 2
    key = _event_key(text)
    try:
        result = notify_owner(text, severity=_ALERT_SEVERITY, event_key=key)
    except Exception as exc:  # noqa: BLE001 - alerting must never kill the watcher
        print(
            f"FLEET-ALERT-NOTIFY [{stamp}]: FAILED "
            f"({type(exc).__name__}); alert not sent; event_key={key}",
            flush=True,
        )
        return 2
    value = _result_value(result)
    print(
        f"FLEET-ALERT-NOTIFY [{stamp}]: {value}; event_key={key}",
        flush=True,
    )
    if value == "sent" or value in _HELD_RESULTS:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
