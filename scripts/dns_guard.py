#!/usr/bin/env python3
"""dns_guard — never let a silent DNS drift kill the FRIDAY Universe front door again.

Root cause this guards (found 2026-11-13): the DuckDNS record for
friday-universe.duckdns.org silently stopped pointing at the Oracle servers
(public DNS answered with the DuckDNS catch-all on Linode IPs; openresty,
bot-challenge pages, a bare "OK"). Every domain-facing surface — dashboard,
chat, voice wss, agent endpoints, bridge — died for the OWNER while every
server-local health check stayed green, because nothing ever resolved the
public domain from outside and compared it with reality.

What this does every run:
  1. Resolve friday-universe.duckdns.org via TWO public DoH resolvers
     (Google + Cloudflare) — never the local resolver, which can be honest
     and still wrong about what the world sees.
  2. Compare with the expected public IP list (argument or state file).
  3. On drift: optionally AUTO-CORRECT through the DuckDNS update API when a
     token is available, and always alert via Telegram (owner channel),
     rate-limited by a cooldown latch so one incident is one alert.
  4. Persist state so a restart mid-incident does not re-spam.

Exit codes: 0 healthy or alerted-drift, 1 hard failure (recorded honestly).
Secrets are read from env or credentials.md and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE_PATH = REPO / "scripts" / ".dns_guard_state.json"

DOH_URLS = (
    "https://dns.google/resolve?name={name}&type=A",
    "https://cloudflare-dns.com/dns-query?name={name}&type=A",
)

# 2026-11-14 lesson: the --name default was misspelled 'duckns.org' (missing
# 'd'). duckns.org serves a wildcard catch-all with the same Linode trio as
# the real duckdns.org catch-all, so every default run monitored the TYPO
# domain, reported false drift, and fired owner alerts while the real record
# was healthy on all 8 authoritative nameservers. Defaults live here as
# constants so tests can pin them exactly.
DEFAULT_NAME = "friday-universe.duckdns.org"
DEFAULT_EXPECTED = "140.245.208.100"  # Oracle Server 1 public ingress


# --------------------------------------------------------------- resolution
def resolve_public(name: str, timeout: float = 10.0) -> list[str]:
    """A-record IPs as the public world sees them, via DoH. Empty on total failure."""
    seen: list[str] = []
    for url in DOH_URLS:
        try:
            req = urllib.request.Request(
                url.format(name=urllib.parse.quote(name)),
                headers={"accept": "application/dns-json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
            if ips:
                seen = ips
                break  # first resolver that answers authoritatively wins
        except Exception:
            continue
    return seen


# --------------------------------------------------------------- credentials
def _credential(kind: str) -> str:
    """Read a credential without ever printing it.

    Order: dedicated env var, then credentials.md sections. Values are only
    used in-place; the return is consumed by callers that must not log it.
    """
    env_map = {
        "duckdns_token": "DUCKDNS_TOKEN",
        "telegram_token": "ZAI_NOTIFICATIONS_TOKEN",
        "telegram_chat": "ZAI_NOTIFICATIONS_CHAT_ID",
    }
    env = (os.getenv(env_map[kind]) or "").strip()
    if env:
        return env
    path = REPO / "credentials.md"
    if not path.exists():
        return ""
    text = path.read_text(errors="ignore")
    if kind == "duckdns_token":
        # 2026-11-14 fix: the original (?im)^#{1,3}\s*duckdns.*$(.*?)... could
        # NEVER match — without re.S the lazy capture cannot cross the header
        # newline, so the section was always empty. Latent bug (unexercised
        # while no token existed) caught by the vault self-test the moment the
        # owner supplied the first real token. Header line is now consumed
        # explicitly, the capture is DOTALL, bounded by the next header or EOF.
        m = re.search(r"(?ims)^#{1,3}[ \t]*duckdns[^\n]*\n(.*?)(?=^#{1,3}[ \t]|\Z)", text)
        section = m.group(1) if m else ""
        m2 = re.search(r"(?im)(?:token|key)\s*[:=]\s*`?([a-f0-9\-]{16,})`?", section)
        return m2.group(1) if m2 else ""
    if kind == "telegram_token":
        # credentials.md shape: "- token: 123456789:AA..." under a Telegram section
        m = re.search(r"(?m)^[^\n]*?(\d{8,12}:[A-Za-z0-9_-]{30,})\s*$", text)
        return m.group(1) if m else ""
    if kind == "telegram_chat":
        # credentials.md shape: "- Owner chat id (surendra2304): 123456789"
        m = re.search(r"(?im)chat\s*id[^:\n]*[:=]\s*(\d{7,})", text)
        return m.group(1) if m else ""
    return ""


# --------------------------------------------------------------- state latch
@dataclass
class GuardState:
    last_alert_key: str = ""
    last_alert_ts: float = 0.0
    fields: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "GuardState":
        try:
            raw = json.loads(STATE_PATH.read_text())
            return cls(
                last_alert_key=str(raw.get("last_alert_key", "")),
                last_alert_ts=float(raw.get("last_alert_ts", 0.0)),
                fields=dict(raw.get("fields", {})),
            )
        except Exception:
            return cls()

    def save(self) -> None:
        try:
            STATE_PATH.write_text(
                json.dumps(
                    {
                        "last_alert_key": self.last_alert_key,
                        "last_alert_ts": self.last_alert_ts,
                        "fields": self.fields,
                    },
                    indent=2,
                )
            )
        except Exception:
            pass


# --------------------------------------------------------------- actions
def duckdns_update(domain: str, token: str, ip: str, timeout: float = 15.0) -> tuple[bool, str]:
    """Point <domain> (no .duckdns.org suffix) at <ip>. Never logs the token."""
    url = (
        f"https://www.duckdns.org/update?domains={urllib.parse.quote(domain)}"
        f"&token={urllib.parse.quote(token)}&ip={urllib.parse.quote(ip)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
        return body.upper().startswith("OK"), body[:40]
    except Exception as exc:
        return False, f"request failed: {exc.__class__.__name__}"


def telegram_alert(token: str, chat: str, text: str, timeout: float = 15.0) -> bool:
    if not token or not chat:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat, "text": text[:4000]}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


# --------------------------------------------------------------- main
def run(name: str, expected: list[str], auto_fix_domain: str | None,
        cooldown_s: int, dry_run: bool) -> int:
    actual = resolve_public(name)
    if not actual:
        # Both resolvers failing is itself an incident worth one alert.
        drift = "dns-unresolvable"
        detail = f"{name}: both public DoH resolvers failed to answer"
    else:
        bad = [ip for ip in actual if ip not in expected]
        missing = [ip for ip in expected if ip not in actual]
        if not bad and not missing:
            print(f"[dns_guard] OK {name} -> {', '.join(actual)} (expected match)")
            return 0
        drift = "dns-drift"
        detail = (
            f"{name} resolves to {', '.join(actual)} but expected {', '.join(expected)}"
        )

    state = GuardState.load()
    key = f"{drift}:{'|'.join(sorted(actual))}"
    fresh = (key != state.last_alert_key) or (time.time() - state.last_alert_ts > cooldown_s)

    fixed_note = ""
    if drift == "dns-drift" and auto_fix_domain and expected and not dry_run:
        token = _credential("duckdns_token")
        if token:
            ok, resp = duckdns_update(auto_fix_domain, token, expected[0])
            fixed_note = f" | auto-correct attempted via DuckDNS API: {'OK' if ok else 'FAILED (' + resp + ')'}"
        else:
            fixed_note = " | NO DuckDNS token configured — manual fix required"

    print(f"[dns_guard] DRIFT {detail}{fixed_note}")
    if fresh:
        alerted = telegram_alert(
            _credential("telegram_token"),
            _credential("telegram_chat"),
            f"FRIDAY DNS GUARD\n{detail}{fixed_note}\n"
            f"Fix: log in to duckdns.org and point the record at {', '.join(expected)}, "
            f"or store a DUCKDNS_TOKEN so dns_guard auto-corrects.",
        )
        state.last_alert_key = key
        state.last_alert_ts = time.time()
        state.save()
        print(f"[dns_guard] alert sent: {alerted}")
    else:
        print("[dns_guard] drift already alerted recently — cooldown held")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="FRIDAY Universe public-DNS watchdog")
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--expected", default=DEFAULT_EXPECTED,
                    help="comma-separated expected public A-record IPs")
    ap.add_argument("--auto-fix-domain", default=None,
                    help="duckdns domain label (e.g. 'friday-universe') to auto-correct on drift")
    ap.add_argument("--cooldown", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return run(
        args.name,
        [ip.strip() for ip in args.expected.split(",") if ip.strip()],
        args.auto_fix_domain,
        args.cooldown,
        args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
