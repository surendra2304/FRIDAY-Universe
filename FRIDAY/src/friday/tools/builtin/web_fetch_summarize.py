"""Checklist F13 (MASTER_COMPLETION_CHECKLIST) — Batch 6, ZAI Agent 2.

Fetch a web page and summarize it on request, with the guard the existing
fetch tools lack: an SSRF gate that refuses loopback, link-local, private
and cloud-metadata targets BEFORE any connection is opened.

The owner asks "summarize <url>" or "fetch and summarize this page" — the
answer must come from the REAL page content (fetched, cleaned, and read by
the synthesize tool), never the LLM's imagination about what the page might
say. Failures are honest: an unreachable page is reported as unreachable.

Routing (server chain): FETCH_SUMMARIZE_KEYWORDS → TOOL_EXECUTION
web_fetch_summarize — never DIRECT_REASONING guessing, never SCREEN.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

try:  # optional at import time (tests run without network)
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

_FETCH_TIMEOUT = 15.0
_MAX_PAGE_CHARS = 12000
#: Ports the guard allows; everything else is refused.
_ALLOWED_PORTS = {80, 443}


def _is_forbidden_target(url: str) -> str | None:
    """Return a human reason when the URL targets a forbidden destination.

    SSRF guard (checklist F13): loopback, link-local, private ranges, cloud
    metadata endpoints and non-http schemes are refused before connect.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return "the URL could not be parsed"
    if parsed.scheme not in ("http", "https"):
        return f"scheme '{parsed.scheme}' is not allowed (http/https only)"
    host = (parsed.hostname or "").strip()
    if not host:
        return "no host in the URL"
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local") or host.endswith(".internal"):
        return f"'{host}' is a local hostname"
    if parsed.port is not None and parsed.port not in _ALLOWED_PORTS:
        return f"port {parsed.port} is not allowed (80/443 only)"

    # Resolve DNS once and check every address it returns (DNS rebinding
    # mitigation: a name that resolves to a private IP is refused).
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return f"'{host}' does not resolve"
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip.split("%")[0])
        except ValueError:
            continue
        if (
            addr.is_loopback
            or addr.is_private
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            return f"'{host}' resolves to a forbidden address ({addr})"
    return None


def _clean_page(html: str) -> str:
    """Strip non-content elements and blank lines (same recipe as the
    existing FetchWebpageContentTool — one truth, two surfaces)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "svg", "form"]):
        tag.decompose()
    raw = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in raw.splitlines()]
    return "\n".join(ln for ln in lines if ln)


class WebFetchSummarizeTool(BaseTool):
    """Fetch a URL, clean it, and summarize it against the owner's question."""

    name = "web_fetch_summarize"
    description = (
        "Fetch a web page and summarize its real content. Use when the owner "
        "shares a link and asks what it says — 'summarize this page', 'what "
        "does this article say', 'fetch and summarize <url>'. The answer comes "
        "from the fetched page itself; unreachable pages are reported honestly."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 45.0
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The full URL (http:// or https://)."},
            "question": {
                "type": "string",
                "description": "Optional focus for the summary (default: the page's key points).",
            },
        },
        "required": ["url"],
    }

    def execute(self, url: str = "", question: str = "", **kwargs: Any) -> ToolResult:
        target = (url or "").strip()
        question = (question or "").strip()
        if not target:
            return ToolResult(
                name=self.name,
                content="I need a URL to fetch — which page should I read, Boss?",
                is_error=True,
                safety_level=self.safety_level,
            )

        # SSRF gate — before ANY connection (F13).
        reason = _is_forbidden_target(target)
        if reason:
            return ToolResult(
                name=self.name,
                content=(
                    f"I won't fetch that address — {reason}. Fetching internal or "
                    "local addresses from inside the fleet is blocked to protect the servers."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"ssrf_blocked": True, "reason": reason},
            )

        if httpx is None:  # pragma: no cover
            return ToolResult(
                name=self.name,
                content="I can't fetch pages in this environment — the HTTP client is not installed.",
                is_error=True,
                safety_level=self.safety_level,
            )

        try:
            with httpx.Client(
                timeout=_FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "FRIDAY_Assistant/1.0"},
            ) as client:
                # Re-check after redirects: a public URL may redirect inward.
                response = client.get(target)
                final_reason = _is_forbidden_target(str(response.url))
                if final_reason:
                    return ToolResult(
                        name=self.name,
                        content=f"I stopped — that page redirected to a blocked address ({final_reason}).",
                        is_error=True,
                        safety_level=self.safety_level,
                        metadata={"ssrf_blocked": True, "reason": final_reason},
                    )
                response.raise_for_status()
                page_text = _clean_page(response.text)[:_MAX_PAGE_CHARS]
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=f"I couldn't fetch {target} — {type(exc).__name__}: {exc}. The page is not summarized because I never read it.",
                is_error=True,
                safety_level=self.safety_level,
            )

        if not page_text.strip():
            return ToolResult(
                name=self.name,
                content=f"{target} returned a page with no readable text (scripts and navigation stripped).",
                is_error=True,
                safety_level=self.safety_level,
            )

        # Summarize through the SAME synthesize tool the research path uses.
        try:
            from friday.tools.builtin.web_research import SynthesizeInformationTool

            focus = question or "the page's key points"
            synth = SynthesizeInformationTool().execute(text=page_text, query=focus)
            summary = synth.content if not synth.is_error else ""
        except Exception:
            summary = ""

        if summary.strip():
            head = f"📄 {target}\n\n{summary.strip()}"
        else:
            # Honest fallback: the first informative lines, not a fake summary.
            lines = [ln for ln in page_text.splitlines() if len(ln.strip()) > 40][:6]
            head = f"📄 {target}\n\nI read the page; here are its opening points:\n" + "\n".join(f"- {ln[:160]}" for ln in lines)
        return ToolResult(
            name=self.name,
            content=head,
            safety_level=self.safety_level,
            metadata={"url": target, "question": question, "chars_read": len(page_text)},
        )
