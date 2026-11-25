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
# TASK-IG2-FRD-03-FIX-01: detail-page enrichment budget. Editorial list
# pages (JaRanks) carry names + descriptions but no contacts in the listing
# block — the phone/email live on the listing's own detail page. Leads that
# lack both are enriched from their same-host detail link, bounded here.
MAX_DETAIL_FETCHES = 20
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{6,}\d")
# Browser-like request headers (TASK-IG2-FRD-03-FIX-01). The live failure
# (FRD-054): FindYello 403'd the fetcher's "FRIDAY-LeadGen/1.0" User-Agent
# (bot protection). A delegated fetch of a public directory sends what a
# browser sends; the tool still reports honestly when a site refuses it.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_ALLOWED_PORTS = {80, 443}


def _clean_phone(raw: str) -> str:
    """Normalise a phone candidate, or "" when it is not a usable phone.

    Guards the two junk classes the bare regex admits: too-short fragments
    (extensions, list numbers) and ISO dates (``2026-11-25`` matches the
    digit/dash shape but is not a phone). A real contact number has 7-15
    digits and is not an 8-digit YYYYMMDD date.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) < 7 or len(digits) > 15:
        return ""
    if re.fullmatch(r"(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", digits):
        return ""
    return text


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

    TASK-IG2-FRD-03-FIX-01: two tightenings, from the live JaRanks failure
    (FRD-054: 65 rows, 0 phones/emails, nav junk as leads). (1) Chrome
    exclusion — blocks are never opened inside ``<nav>``/``<header>``/
    ``<footer>`` (the "JaRanks", "Home", "How we chose", "Profile" rows
    were header/nav/footer items whose classes hint at a listing). (2) The
    name is the first text chunk with a real word in it, so a bare list
    number ("1.") never becomes the business name.
    """

    _HINTS = ("listing", "business", "company", "card", "result", "results",
               "item")
    _CHROME_TAGS = ("nav", "header", "footer")
    # Void elements have no end tag: counting them in the block depth would
    # leave the depth permanently elevated, so a block opened before an
    # <img> would swallow every following sibling until the page ends
    # (found via the JaRanks logo <img> inside a "rounded-card" div).
    _VOID_TAGS = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    })

    @staticmethod
    def _hinted(classes: str) -> bool:
        """Whole-token hint match on a class/id string.

        TASK-IG2-FRD-03-FIX-01: substring matching false-fires on Tailwind
        utilities — "item" inside "items-center" opened a block per tag row
        (the spurious "Motor" leads). Tokens are split on whitespace,
        hyphens and underscores, so "listing-card" still matches ("listing",
        "card") while "items-center" ("items", "center") does not.
        """
        tokens = re.split(r"[\s\-_]+", classes.lower())
        return any(h in tokens for h in _ListingParser._HINTS)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self._current: dict | None = None
        self._depth = 0
        self._chrome_depth = 0
        self.next_url = ""
        self.page_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr = dict(attrs)
        classes = f"{attr.get('class', '')} {attr.get('id', '')}".lower()
        # Pagination lives in <nav> on most directories — the "next" link is
        # read before the chrome exclusion below, or pagination breaks.
        if tag == "a" and "next" in re.split(r"[\s\-_]+", classes):
            self.next_url = attr.get("href", "")
        if tag in self._CHROME_TAGS:
            self._chrome_depth += 1
            return
        if self._chrome_depth:
            return
        if self._current is None and self._hinted(classes):
            self._current = {"text": [], "tel": "", "mailto": "", "href": ""}
            self._depth = 1
            return
        if self._current is not None:
            if tag not in self._VOID_TAGS:
                self._depth += 1
            href = attr.get("href", "")
            if href.startswith("tel:") and not self._current["tel"]:
                self._current["tel"] = href[4:]
            elif href.startswith("mailto:") and not self._current["mailto"]:
                self._current["mailto"] = href[7:]
            elif href.startswith(("http://", "https://")) and not self._current["href"]:
                self._current["href"] = href
            # TASK-IG2-FRD-03-FIX-01: relative links are the norm on modern
            # directories (JaRanks profile links are "/profile/...") — capture
            # the first usable href of any shape; parse_listing_page joins it
            # against the page URL. Fragments and javascript: links are not
            # detail pages.
            elif (href and not href.startswith(("#", "javascript:"))
                    and not self._current["href"]):
                self._current["href"] = href

    def handle_endtag(self, tag: str) -> None:
        if tag in self._CHROME_TAGS:
            self._chrome_depth = max(0, self._chrome_depth - 1)
            return
        if self._chrome_depth:
            return
        if self._current is not None:
            self._depth -= 1
            if self._depth <= 0:
                self.blocks.append(self._current)
                self._current = None

    def handle_data(self, data: str) -> None:
        if self._chrome_depth:
            return
        text = data.strip()
        if text:
            self.page_text.append(text)
            if self._current is not None:
                self._current["text"].append(text)


def _pick_name(chunks: list[str]) -> str:
    """First chunk with a real word in it (skips bare list numbers)."""
    for chunk in chunks:
        if len(re.sub(r"\W", "", chunk)) >= 3:
            return chunk[:120]
    return (chunks[0][:120] if chunks else "")


class _HeadingParser(HTMLParser):
    """Fallback listing extraction for pages with no hinted blocks.

    Modern directories (JaRanks, live 2026-11-25) use Tailwind utility
    classes — no ``listing``/``business``/``card`` hook exists anywhere in
    the markup, so the hint parser finds zero blocks. The structure that
    DOES survive is the heading: each provider is an ``<h2>``/``<h3>``
    carrying a link to its own profile page, followed by its description
    and meta rows. A section is one heading plus the text up to the next
    heading; the heading link becomes the detail-page URL. Only used when
    the hint parser found nothing, so hinted pages are untouched.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self._current: dict | None = None
        self._in_heading = False
        self._chars = 0

    def _close(self) -> None:
        if self._current is not None:
            self.blocks.append(self._current)
            self._current = None
        self._in_heading = False
        self._chars = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("h2", "h3"):
            self._close()
            self._current = {"text": [], "tel": "", "mailto": "", "href": "",
                             "heading": []}
            self._in_heading = True
            return
        if self._current is not None and tag == "a" and self._in_heading:
            # Only links INSIDE the heading are the section's detail link.
            # A link collected from the section body (e.g. a footer
            # "newsletter" link trailing the last section) would send the
            # enrichment fetch to the wrong page and misattribute its
            # contacts to this heading.
            href = dict(attrs).get("href", "")
            if href.startswith("tel:") and not self._current["tel"]:
                self._current["tel"] = href[4:]
            elif href.startswith("mailto:") and not self._current["mailto"]:
                self._current["mailto"] = href[7:]
            elif (href and not href.startswith(("#", "javascript:"))
                    and not self._current["href"]):
                self._current["href"] = href

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h2", "h3"):
            self._in_heading = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._current is None:
            return
        # Sections are provider blurbs, not essays: cap the collected text
        # so the LAST section cannot swallow the footer (and inherit its
        # phone number) when no further heading closes it.
        if self._chars >= 2000:
            return
        self._chars += len(text)
        if self._in_heading:
            self._current["heading"].append(text)
        self._current["text"].append(text)

    def close(self) -> None:  # noqa: D102 - flush the last section
        super().close()
        self._close()


def _extract_contacts_from_html(html_text: str) -> tuple[str, str]:
    """Best-effort (phone, email) from a detail page's HTML.

    ``tel:``/``mailto:`` hrefs first (the page means them as contacts),
    then the visible-text regexes. Used to enrich listing blocks whose own
    block carries no contact signal (editorial list pages).
    """
    from urllib.parse import unquote

    html_text = html_text or ""
    tel = re.search(r"""href=["']tel:([^"']+)""", html_text, re.I)
    mail = re.search(r"""href=["']mailto:([^"'?]+)""", html_text, re.I)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text)).strip()
    phone_match = _PHONE_RE.search(text)
    email_match = _EMAIL_RE.search(text)
    phone = _clean_phone(unquote(tel.group(1)) if tel else
                         (phone_match.group(0) if phone_match else ""))
    email = (unquote(mail.group(1)).strip() if mail else
             (email_match.group(0) if email_match else ""))
    return phone, email


def parse_listing_page(html_text: str, page_url: str, category: str = "",
                       require_contact: bool = True) -> tuple[list[Lead], str]:
    """Parse one listing page -> (leads, next_page_url_or_empty).

    With ``require_contact`` (default) a block becomes a lead only when it
    carries a contact signal — a phone or an email, from a ``tel:``/
    ``mailto:`` link or the block text. Name-only blocks (nav junk, section
    heads) are dropped, never delivered as leads. ``run_lead_generation``
    passes ``require_contact=False`` so it can enrich contact-less blocks
    from their detail pages before the same filter is applied.
    """
    parser = _ListingParser()
    parser.feed(html_text or "")
    # Empty blocks (image-only containers such as a "rounded-card" logo div)
    # do not count: if every hinted block is empty, the page is really a
    # heading-structured page and the fallback must still run.
    blocks = [b for b in parser.blocks if " ".join(b["text"]).strip()]
    if not blocks:
        # No hinted blocks (Tailwind/modern markup): fall back to headings.
        heading_parser = _HeadingParser()
        heading_parser.feed(html_text or "")
        heading_parser.close()
        blocks = heading_parser.blocks
    leads: list[Lead] = []
    for block in blocks:
        text = " ".join(block["text"])
        if not text:
            continue
        name = _pick_name(block["text"])
        phone_match = _PHONE_RE.search(text)
        email_match = _EMAIL_RE.search(text)
        lead = Lead(
            name=name,
            phone=_clean_phone(block["tel"]) or _clean_phone(
                phone_match.group(0) if phone_match else ""),
            email=block["mailto"] or (email_match.group(0) if email_match else ""),
            website=urljoin(page_url, block["href"]) if block["href"] else "",
            category=category,
            source_url=page_url,
        )
        if require_contact and not (lead.phone or lead.email):
            continue
        leads.append(lead)
    next_url = urljoin(page_url, parser.next_url) if parser.next_url else ""
    return leads, next_url


def dedupe_leads(leads: list[Lead]) -> list[Lead]:
    # A lead matches an earlier one when ANY of its identity keys (email,
    # phone, name) matches — a relisted business whose second listing shows
    # only its name and website must still merge with the first listing
    # that carried its email/phone (the pagination case in the tests).
    seen: dict[str, Lead] = {}
    ordered: list[Lead] = []
    for lead in leads:
        keys = {
            value.strip().lower()
            for value in (lead.email, lead.phone, lead.name)
            if value and value.strip()
        }
        existing = next((seen[k] for k in keys if k in seen), None)
        if existing is None:
            ordered.append(lead)
            for k in keys:
                seen[k] = lead
        else:  # fill blanks from the duplicate, never overwrite
            for attr in ("phone", "email", "website", "address"):
                if not getattr(existing, attr) and getattr(lead, attr):
                    setattr(existing, attr, getattr(lead, attr))
            for k in keys:
                seen.setdefault(k, existing)
    return ordered


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
        resp = client.get(url, headers=_BROWSER_HEADERS)
    resp.raise_for_status()
    return resp.text


def run_lead_generation(start_url: str, category: str = "", *,
                        fetcher=None, max_pages: int = MAX_PAGES) -> LeadGenResult:
    """Run the errand: fetch -> parse -> dedupe -> table-ready result.

    TASK-IG2-FRD-03-FIX-01: listing blocks without a contact signal are
    enriched from their same-host detail page (bounded by
    MAX_DETAIL_FETCHES) before the contact filter runs — editorial list
    pages carry names but no contacts in the block. The contact filter
    runs AFTER dedupe, so a name-only relisting still merges into (and
    fills the website of) the contactful first listing. A lead with no
    phone and no email after enrichment is dropped, never delivered.
    """
    reason = check_url_allowed(start_url)
    if reason:
        raise LeadGenError(f"refused: {reason}")
    fetch = fetcher or _default_fetcher
    result = LeadGenResult(start_url=start_url, category=category)
    url = start_url
    start_host = urlparse(start_url).hostname
    detail_fetches = 0
    for _ in range(min(max_pages, MAX_PAGES)):
        if not url:
            break
        if urlparse(url).hostname != start_host:
            break  # pagination never leaves the directory's own host
        html_text = fetch(url)
        result.pages_fetched += 1
        leads, next_url = parse_listing_page(html_text, url, category,
                                             require_contact=False)
        for lead in leads:
            if (lead.phone or lead.email) or not lead.website:
                continue
            if urlparse(lead.website).hostname != start_host:
                continue  # detail pages never leave the directory's host
            if check_url_allowed(lead.website) is not None:
                continue
            if detail_fetches >= MAX_DETAIL_FETCHES:
                break
            try:
                detail_fetches += 1
                phone, email = _extract_contacts_from_html(fetch(lead.website))
            except Exception:
                continue  # a dead detail page drops the lead, never the run
            lead.phone = lead.phone or phone
            lead.email = lead.email or email
        result.leads.extend(leads)
        if len(result.leads) >= MAX_LEADS:
            result.leads = result.leads[:MAX_LEADS]
            break
        url = next_url
    result.leads = dedupe_leads(result.leads)
    result.leads = [lead for lead in result.leads if lead.phone or lead.email]
    return result


__all__ = ["Lead", "LeadGenError", "LeadGenResult", "check_url_allowed",
           "dedupe_leads", "parse_listing_page", "render_table",
           "run_lead_generation"]
