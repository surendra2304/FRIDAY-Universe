"""Checklist D17 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.

Owner preferences: the small set of owner-tunable knobs the UI and the
scheduled passes read to behave the way the owner asked for. File-backed
(atomic writes), one record per owner, never invented — defaults are
explicit and the API always returns them when unset.

Fields:
- name          : how FRIDAY addresses the owner in chat/voice (default "Boss")
- timezone      : IANA tz (default "Asia/Kolkata" — the owner_time module)
- briefing_time : HH:MM IST for the daily self-report (default "21:00")
- notify_telegram : whether scheduled pushes go to Telegram (default true)
- notify_voice    : whether scheduled pushes go to voice (default false;
                    voice minutes are limited — see E8/G9)
- voice_personality : the Gemini Live voice persona (default "assistant")
- accent_locale     : STT accent hint (default "en-IN" — owner's Telugu-English mix)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "name": "Boss",
    "timezone": "Asia/Kolkata",
    "briefing_time": "21:00",
    "notify_telegram": True,
    "notify_voice": False,
    "voice_personality": "assistant",
    "accent_locale": "en-IN",
}

#: The owner is the only user — a single record keyed on this constant.
OWNER_ID = "owner"


def _store_path() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "owner", "preferences.json"))
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "..", "..", ".data", "owner", "preferences.json"))


_ALLOWED_KEYS = frozenset(DEFAULTS.keys())


class OwnerPreferences:
    """File-backed owner preferences (D17). Defaults are explicit; never invents."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _store_path()
        self._lock = threading.RLock()
        self._cache: dict[str, Any] | None = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            self._cache = {}
        except Exception as exc:
            logger.warning("[OWNER PREFS] store unreadable (%s) — using defaults", exc)
            self._cache = {}
        return self._cache

    def _save(self) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, sort_keys=True)
        os.replace(tmp, self._path)

    def get(self) -> dict[str, Any]:
        """Return the full preferences dict, with defaults for any unset field."""
        with self._lock:
            stored = self._load()
        merged = dict(DEFAULTS)
        for k in _ALLOWED_KEYS:
            v = stored.get(k)
            if v is not None and v != "":
                merged[k] = v
        merged["owner_id"] = OWNER_ID
        return merged

    def update(self, partial: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial update. Unknown keys are ignored (never stored)."""
        if not isinstance(partial, dict):
            raise ValueError("preferences update must be a dict")
        with self._lock:
            data = self._load()
            changed: dict[str, Any] = {}
            for k, v in partial.items():
                if k not in _ALLOWED_KEYS:
                    continue
                # Type-validate against the default's type.
                default = DEFAULTS[k]
                if isinstance(default, bool):
                    v = bool(v)
                elif isinstance(default, str):
                    v = str(v).strip()
                    if k == "briefing_time" and not _valid_hhmm(v):
                        continue  # ignore invalid time; keep the default
                data[k] = v
                changed[k] = v
            self._cache = data
            self._save()
        return self.get()

    def reset_for_tests(self, path: str | None = None) -> None:
        self._path = path or self._path
        self._cache = None


def _valid_hhmm(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return False
    try:
        h, m = int(value[:2]), int(value[3:])
    except ValueError:
        return False
    return 0 <= h < 24 and 0 <= m < 60


#: Process-wide singleton (server endpoints + scheduled loops share one).
owner_preferences = OwnerPreferences()
