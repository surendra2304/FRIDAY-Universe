"""
oanda_demo/credentials.py — OANDA credential resolution for Stratex.

Resolution order:
  1. Environment: OANDA_API_KEY / OANDA_ACCOUNT_ID / OANDA_PRACTICE
  2. credentials.md master copy (the file is gitignored; it lives on the
     Oracle Cloud VMs and is written by the Sync Credentials workflow).

Supported credentials.md formats (value inline or on the next line):

    ## OANDA Demo / Practice Account
    - API token: OANDA_API_KEY
      db0f6f0f...-1ddb...
    - Account ID: OANDA_ACCOUNT_ID
      101-001-40988523-001
    - OANDA_API_KEY: <value>          (inline, also accepted)

The loader NEVER logs token values.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_TOKEN_KEYS = ("api token", "oanda api", "oanda_api_key", "oanda token")
_ACCOUNT_KEYS = ("account id", "oanda account", "oanda_account_id")

_ENVVAR_LABEL = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
_ACCOUNT_ID_SHAPE = re.compile(r"^\d{3}-\d{3}-\d{6,}-\d{3}$")


def parse_credentials_text(text: str) -> Dict[str, str]:
    """Parse OANDA credentials out of a credentials.md body.

    Handles the house style used in the master credentials.md:
        - API token: OANDA_API_KEY
          <actual value on the next line>
    as well as plain inline forms.
    """
    out: Dict[str, str] = {}
    lines = [ln.strip() for ln in text.splitlines()]

    def next_value(idx: int) -> Optional[str]:
        """First plausible value at/after idx+1 (skips comments and labels)."""
        for j in range(idx + 1, len(lines)):
            ln = lines[j]
            if not ln or ln.startswith("#"):
                continue
            ln = ln.lstrip("-*").strip()
            if not ln:
                continue
            token = ln.split()[0].strip("`\"',")
            # A line like "token: ENVVAR_NAME" is a label, not a value.
            if _ENVVAR_LABEL.match(token) and ":" in ln:
                continue
            if _ENVVAR_LABEL.match(token) and len(ln.split()) == 1:
                continue
            return token
        return None

    for idx, ln in enumerate(lines):
        if not ln or ln.startswith("#"):
            continue
        body = ln.lstrip("-*").strip()          # house style uses "- key: value"
        if not body:
            continue
        low = body.lower()
        raw = body.split(":", 1)[1].strip() if ":" in body else ""
        inline = raw.strip("`\"',")
        inline_is_label = bool(inline) and bool(_ENVVAR_LABEL.match(inline))

        key = None
        if any(low.startswith(k) for k in _TOKEN_KEYS):
            key = "oanda_api_key"
        elif any(low.startswith(k) for k in _ACCOUNT_KEYS):
            key = "oanda_account_id"
        if not key or key in out:
            continue

        if inline and not inline_is_label:
            out[key] = inline
        else:
            val = next_value(idx)
            if val:
                out[key] = val
    return out


def _candidate_paths() -> List[Path]:
    paths: List[Path] = []
    env_path = os.getenv("FRIDAY_CREDENTIALS_FILE", "")
    if env_path:
        paths.append(Path(env_path))
    here = Path(__file__).resolve().parent
    for base in (here, here.parent, here.parent.parent, Path("/opt/friday_universe")):
        paths.append(base / "credentials.md")
    return paths


def load_oanda_credentials(allow_missing: bool = False) -> Tuple[str, str, bool]:
    """Return (api_key, account_id, practice). Raises RuntimeError if absent."""
    api_key = os.getenv("OANDA_API_KEY", "").strip()
    account_id = os.getenv("OANDA_ACCOUNT_ID", "").strip()
    practice = os.getenv("OANDA_PRACTICE", "true").strip().lower() in ("1", "true", "yes")

    if not api_key or not account_id:
        for path in _candidate_paths():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_credentials_text(text)
            api_key = api_key or parsed.get("oanda_api_key", "")
            account_id = account_id or parsed.get("oanda_account_id", "")
            if api_key and account_id:
                break

    if not api_key and not allow_missing:
        raise RuntimeError(
            "OANDA credentials not found: set OANDA_API_KEY/OANDA_ACCOUNT_ID "
            "env vars or add an OANDA section to credentials.md"
        )
    if account_id and not _ACCOUNT_ID_SHAPE.match(account_id):
        # Not the standard OANDA shape — refuse rather than fire orders at a
        # malformed account id.
        raise RuntimeError(f"OANDA account id has unexpected shape: {account_id!r}")
    return api_key, account_id, practice
