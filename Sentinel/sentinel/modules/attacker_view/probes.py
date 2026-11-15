"""Read-only network probes for the attacker-view audit.

Deliberately minimal capabilities — this is all the audit is allowed to do:

* ``tcp_connect`` — a single TCP connect attempt (is the port answering?).
* ``http_get`` — one unauthenticated HTTP GET, body truncated.

There is intentionally no authentication attempt, no payload, no write,
and no redirect following beyond the HTTP library default. Probers are
injectable so tests never touch a real network.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

MAX_BODY_CHARS = 2048


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""

    @property
    def content_type(self) -> str:
        for key, value in self.headers.items():
            if key.lower() == "content-type":
                return value.lower()
        return ""


def tcp_connect(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to (host, port) succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_get(url: str, timeout: float = 5.0) -> HttpResponse | None:
    """One unauthenticated GET. Returns None on any network error so the
    caller can record the target as unreachable instead of guessing."""
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "FRIDAY-Sentinel-AttackerViewAudit/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BODY_CHARS).decode("utf-8", "replace")
            return HttpResponse(
                status=resp.status,
                headers=dict(resp.headers.items()),
                body=body,
            )
    except urllib.error.HTTPError as exc:
        # An HTTP error status is still an answer — the audit needs it
        # (401/403 is exactly what a healthy auth posture looks like).
        try:
            body = exc.read(MAX_BODY_CHARS).decode("utf-8", "replace")
        except Exception:
            body = ""
        headers = dict(exc.headers.items()) if exc.headers else {}
        return HttpResponse(status=exc.code, headers=headers, body=body)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
