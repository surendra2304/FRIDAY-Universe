"""Delegated lead-generation errand engine (TASK-IG2-FRD-03).

Cluster #17 (IG wave-2 triage, BUILD/FRIDAY): the owner delegates
"scrape <directory category> and give me the contacts" — the reel's
example is a Yello-style business directory (e.g. insurance companies in
a city). FRIDAY fetches the directory listing pages, extracts structured
contacts, dedupes them, and delivers ONE artefact: a structured contact
table (Markdown + CSV) for the owner.

Hard boundaries, enforced in code:

* **The table is the deliverable.** There is no outreach function — no
  email/SMS/call code exists in this module. Contacts are never messaged.
* **SSRF-guarded fetching** in the same shape as
  ``friday.tools.builtin.web_fetch_summarize``: http/https only, ports
  80/443, private/loopback/link-local/reserved resolutions refused
  before connecting. The fetcher is injectable for tests.
* **Bounded**: page count and lead count are capped; pagination follows
  only same-host ``next`` links discovered in the fetched HTML.

Stdlib parsing (``html.parser``) — no new dependencies, Python 3.10.
"""
from __future__ import annotations

import csv
import io
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

MAX_PAGES = 5
MAX_LEADS = 200
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{6,}\d")
_ALLOWED_PORTS = {80, 443}


class LeadGenError(ValueError):
    """Raised when a lead-generation errand is refused or cannot run."""


def check_url_allowed(url: str) -> str | None:
    """Return a refusal reason, or None when the URL may be fetched."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return "the URL could not be parsed"
    if parsed.scheme not in ("http", "https"):
        return f"scheme '{parsed.scheme}' is not allowed (http/https only)"
    host = (parsed.hostname or "").strip()
    if not host:
        return "no host in the URL"
    if host in ("localhost", "localhost.localdomain") or host.endswith(
            (".local", ".internal")):
        return f"'{host}' is a local hostname"
    if parsed.port is not None and parsed.port not in _ALLOWED_PORTS:
        return f"port {parsed.port} is not allowed (80/443 only)"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return f"'{host}' does not resolve"
    for info in infos:
        try:
            addr = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        except ValueError:
            continue
        if (addr.is_loopback or addr.is_private or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return f"'{host}' resolves to a forbidden address ({addr})"
    return None


@dataclass(slots=True)
class Lead:
    name: str
    phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""
    category: str = ""
    source_url: str = ""

    def key(self) -> str:
        return (self.email or self.phone or self.name).strip().lower()


class _ListingParser(HTMLParser):
    """Extract candidate business blocks from directory listing HTML.

    Generic by design (directories differ): a block is any element whose
    class/id hints at a listing (``listing``, ``business``, ``company``,
    ``card``, ``result``) — its text, ``tel:``/``mailto:`` links and first
    outbound link become one Lead. Pages with no hinted blocks fall back
    to contact-detail extraction from the whole page text.
    """

    _HINTS = ("listing", "business", "company", "card", "result", "item")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self._current: dict | None = None
        self._depth = 0
        self.next_url = ""
        self.page_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr = dict(attrs)
        classes = f"{attr.get('class', '')} {attr.get('id', '')}".lower()
        if self._current is None and any(h in classes for h in self._HINTS):
            self._current = {"text": [], "tel": "", "mailto": "", "href": ""}
            self._depth = 1
            return
        if self._current is not None:
            self._depth += 1
            href = attr.get("href", "")
            if href.startswith("tel:") and not self._current["tel"]:
                self._current["tel"] = href[4:]
            elif href.startswith("mailto:") and not self._current["mailto"]:
                self._current["mailto"] = href[7:]
            elif href.startswith(("http://", "https://")) and not self._current["href"]:
                self._current["href"] = href
        if tag == "a" and "next" in classes:
            self.next_url = attr.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if self._current is not None:
            self._depth -= 1
            if self._depth <= 0:
                self.blocks.append(self._current)
                self._current = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.page_text.append(text)
            if self._current is not None:
                self._current["text"].append(text)


def parse_listing_page(html_text: str, page_url: str, category: str = "") -> tuple[list[Lead], str]:
    """Parse one listing page -> (leads, next_page_url_or_empty)."""
    parser = _ListingParser()
    parser.feed(html_text or "")
    leads: list[Lead] = []
    for block in parser.blocks:
        text = " ".join(block["text"])
        if not text:
            continue
        name = block["text"][0][:120]
        phone_match = _PHONE_RE.search(text)
        email_match = _EMAIL_RE.search(text)
        leads.append(Lead(
            name=name,
            phone=block["tel"] or (phone_match.group(0).strip() if phone_match else ""),
            email=block["mailto"] or (email_match.group(0) if email_match else ""),
            website=block["href"],
            category=category,
            source_url=page_url,
        ))
    next_url = urljoin(page_url, parser.next_url) if parser.next_url else ""
    return leads, next_url


def dedupe_leads(leads: list[Lead]) -> list[Lead]:
    seen: dict[str, Lead] = {}
    for lead in leads:
        key = lead.key()
        if key and key not in seen:
            seen[key] = lead
        elif key in seen:  # fill blanks from the duplicate, never overwrite
            existing = seen[key]
            for attr in ("phone", "email", "website", "address"):
                if not getattr(existing, attr) and getattr(lead, attr):
                    setattr(existing, attr, getattr(lead, attr))
    return list(seen.values())


def render_table(leads: list[Lead], fmt: str = "markdown") -> str:
    """Render the deliverable table (markdown or csv)."""
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["name", "phone", "email", "website", "category", "source_url"])
        for lead in leads:
            writer.writerow([lead.name, lead.phone, lead.email, lead.website,
                             lead.category, lead.source_url])
        return out.getvalue()
    lines = ["| Name | Phone | Email | Website | Category |",
             "|---|---|---|---|---|"]
    for lead in leads:
        def cell(v: str) -> str:
            return v.replace("|", "/").strip()
        lines.append(f"| {cell(lead.name)} | {cell(lead.phone)} | {cell(lead.email)} "
                     f"| {cell(lead.website)} | {cell(lead.category)} |")
    return "\n".join(lines)


@dataclass(slots=True)
class LeadGenResult:
    leads: list[Lead] = field(default_factory=list)
    pages_fetched: int = 0
    start_url: str = ""
    category: str = ""

    def table(self, fmt: str = "markdown") -> str:
        return render_table(self.leads, fmt)


def _default_fetcher(url: str) -> str:
    import httpx  # fleet dependency, imported lazily

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "FRIDAY-LeadGen/1.0"})
    resp.raise_for_status()
    return resp.text


def run_lead_generation(start_url: str, category: str = "", *,
                        fetcher=None, max_pages: int = MAX_PAGES) -> LeadGenResult:
    """Run the errand: fetch -> parse -> dedupe -> table-ready result."""
    reason = check_url_allowed(start_url)
    if reason:
        raise LeadGenError(f"refused: {reason}")
    fetch = fetcher or _default_fetcher
    result = LeadGenResult(start_url=start_url, category=category)
    url = start_url
    start_host = urlparse(start_url).hostname
    for _ in range(min(max_pages, MAX_PAGES)):
        if not url:
            break
        if urlparse(url).hostname != start_host:
            break  # pagination never leaves the directory's own host
        html_text = fetch(url)
        result.pages_fetched += 1
        leads, next_url = parse_listing_page(html_text, url, category)
        result.leads.extend(leads)
        if len(result.leads) >= MAX_LEADS:
            result.leads = result.leads[:MAX_LEADS]
            break
        url = next_url
    result.leads = dedupe_leads(result.leads)
    return result


__all__ = ["Lead", "LeadGenError", "LeadGenResult", "check_url_allowed",
           "dedupe_leads", "parse_listing_page", "render_table",
           "run_lead_generation"]
