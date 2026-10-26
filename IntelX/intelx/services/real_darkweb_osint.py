"""
IntelX/intelx/services/real_darkweb_osint.py — Real Dark Web OSINT Pipeline.

The plumbing an onion-space investigation actually needs, built as pure
functions and typed records so it can be tested without Tor, a vendor or a
language model: URL policy, engine result parsing, filtering, charset-correct
body decoding, boilerplate-free text extraction, link pivoting, untrusted-content
quarantine, a staged investigation pipeline, an on-disk investigation store and a
token stream that hides reasoning blocks.

Real working implementations:
- UrlRefused / OnionUrlPolicy: scheme, ambiguous-authority, userinfo and
  clearweb gates, redirect-hop accounting
- RedirectUnwrapper: the real target behind an engine's redirect wrapper (.onion
  extracted from query parameters, engine hosts excluded)
- HtmlDocument: an html.parser tree with anchors, text, meta charset
- CharsetSniffer + BodyReader: header/BOM/meta/UTF-8/latin-1 decoding and
  byte-capped reads
- TextExtractor: boilerplate stripping with a ratio fallback, whitespace
  collapse, onion link extraction from anchors and from visible text
- UntrustedText: zero-width and control-character scrubbing plus the delimiters
  that keep third-party page text out of instruction position
- AbuseMaterialFilter: unambiguous CSAM pattern refusal
- ResultFilter: title usefulness, trimming, dedup keys with tracking-parameter
  stripping, per-host caps and the full result stats block
- EngineRecord / SearchOutcome: per-engine ok/empty/failed vocabulary and the
  aggregates that separate "nothing exists" from "nothing answered"
- QueryRefiner: deterministic refinement (stopwords, quotes, operator hints)
- PivotSuggester: onion hosts, handles, emails, wallets and hashes lifted out of
  scraped text as follow-up pivots
- Investigation + PipelineError + InvestigationPipeline: staged runs with
  injectable search/scrape/summarize steps and honest terminal statuses
- InvestigationStore: collision-free filenames, newest-first ordering,
  tolerant loading
- StreamingBuffer: token buffering that strips <think> blocks and emits on
  newline or at a limit
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import (parse_qs, parse_qsl, quote_plus, unquote,
                          urlencode, urljoin, urlparse)


# ── URL policy ────────────────────────────────────────────────────────────

STATUS_OK = "ok"
STATUS_REFUSED = "refused"
STATUS_ERROR = "error"
STATUS_BLOCKED = "blocked"

# What ends the authority part of a URL. A backslash counts because HTTP
# clients read it as the start of the path while urlparse reads straight
# through it: a disagreement an attacker can use to smuggle a host.
_AUTHORITY_END = re.compile(r"[/?#\\]")
_ONION_HOST = re.compile(r"^[a-z2-7]{16}\.onion$|^[a-z2-7]{56}\.onion$", re.IGNORECASE)
_ONION_URL = re.compile(r"https?://[a-z0-9.-]+\.onion[^\s\"'<>]*", re.IGNORECASE)
_ONION_IN_TEXT = re.compile(
    r"(?:https?://)?([a-z2-7]{56}|[a-z2-7]{16})\.onion(/[^\s\"'<>)\]]*)?",
    re.IGNORECASE)


def outbound_host(url: str) -> str | None:
    """The host a request for ``url`` would connect to, or None if ambiguous.

    None covers whitespace, control characters, embedded userinfo and a
    backslash in the authority: each of those means two parsers disagree about
    the destination, so the only safe answer is to refuse.
    """
    raw = url if isinstance(url, str) else ""
    if not raw or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in raw):
        return None
    scheme, sep, rest = raw.partition("://")
    if not sep or scheme.lower() not in ("http", "https"):
        return None
    end = _AUTHORITY_END.search(rest)
    authority = rest[:end.start()] if end else rest
    if "@" in authority:
        return None
    if end and rest[end.start()] == "\\":
        return None
    host = authority.split(":")[0]
    return host.lower() or None


def is_onion(url: str) -> bool:
    """True when the host a request would reach is a hidden service."""
    host = outbound_host(url)
    return bool(host and host.endswith(".onion"))


def valid_onion_host(host: str) -> bool:
    return bool(_ONION_HOST.match((host or "").strip()))


class UrlRefused(Exception):
    """A URL the pipeline will not request, carrying the status to report."""

    def __init__(self, status: str, detail: str, http_status: int | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.http_status = http_status

    def as_record(self) -> dict[str, Any]:
        return {"status": self.status, "detail": self.detail,
                "http_status": self.http_status}


MAX_REDIRECTS = 5
REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


@dataclass
class UrlVerdict:
    """Whether a URL may be fetched, and why not when it may not."""

    url: str
    allowed: bool
    status: str
    detail: str
    host: str = ""
    onion: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"url": self.url, "allowed": self.allowed, "status": self.status,
                "detail": self.detail, "host": self.host, "onion": self.onion}


class OnionUrlPolicy:
    """The single gate every fetch and every redirect hop passes through."""

    def __init__(self, allow_clearweb: bool = False,
                 allowed_schemes: Sequence[str] = ("http", "https")) -> None:
        self.allow_clearweb = allow_clearweb
        self.allowed_schemes = tuple(s.lower() for s in allowed_schemes)

    def check(self, url: str) -> UrlVerdict:
        scheme = urlparse(url or "").scheme.lower()
        host = outbound_host(url or "")
        if scheme not in self.allowed_schemes:
            return UrlVerdict(url, False, STATUS_ERROR, "unsupported scheme")
        if host is None:
            return UrlVerdict(
                url, False, STATUS_ERROR,
                "rejected: userinfo, a backslash or whitespace in the host part")
        onion = host.endswith(".onion")
        if onion and not valid_onion_host(host):
            return UrlVerdict(url, False, STATUS_ERROR,
                              "malformed onion address", host, False)
        if not onion and not self.allow_clearweb:
            return UrlVerdict(url, False, STATUS_REFUSED, "not an onion host",
                              host, False)
        return UrlVerdict(url, True, STATUS_OK, "allowed", host, onion)

    def require(self, url: str) -> UrlVerdict:
        verdict = self.check(url)
        if not verdict.allowed:
            raise UrlRefused(verdict.status, verdict.detail)
        return verdict

    def follow(self, start: str, hops: Sequence[str]) -> list[str]:
        """Validate a redirect chain, refusing a hop or a chain that breaks policy."""
        chain = [start]
        current = start
        for hop in hops:
            if len(chain) > MAX_REDIRECTS:
                raise UrlRefused(STATUS_REFUSED, "too many redirects")
            target = urljoin(current, hop)
            verdict = self.check(target)
            if not verdict.allowed:
                raise UrlRefused(verdict.status, f"redirect blocked: {verdict.detail}")
            chain.append(target)
            current = target
        return chain


ENGINE_HOSTS = frozenset({
    "juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion",  # Ahmia
    "3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion",  # OnionLand
    "tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion",   # Tor66
})


class RedirectUnwrapper:
    """Recover the target of an engine's redirect wrapper or bare link."""

    def __init__(self, engine_hosts: Iterable[str] = ENGINE_HOSTS) -> None:
        self.engine_hosts = {h.lower() for h in engine_hosts}

    def unwrap(self, href: str, engine_host: str = "") -> str | None:
        """The external .onion URL an anchor points at, or None."""
        if not href:
            return None
        engine = (engine_host or "").lower()
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower()

        # Engine-local (or relative) redirect: the real target rides in a query
        # parameter, so parse_qs splits on & and percent-decodes it for us.
        if not host or host == engine:
            for values in parse_qs(parsed.query).values():
                for value in values:
                    found = self._first_external(value, engine)
                    if found:
                        return found

        candidates = _ONION_URL.findall(href) or _ONION_URL.findall(unquote(href))
        for candidate in candidates:
            candidate_host = (urlparse(candidate).hostname or "").lower()
            if candidate_host != engine:
                return candidate
        # Everything matched points back at the engine: try one unwrap inside.
        for candidate in candidates:
            for values in parse_qs(urlparse(candidate).query).values():
                for value in values:
                    found = self._first_external(unquote(value), engine)
                    if found:
                        return found
        return None

    def _first_external(self, value: str, engine: str) -> str | None:
        for nested in _ONION_URL.findall(value):
            host = (urlparse(nested).hostname or "").lower()
            if host != engine and is_onion(nested):
                return nested
        return None


# ── Untrusted text ────────────────────────────────────────────────────────

UNTRUSTED_OPEN = "<<<UNTRUSTED PAGE TEXT>>>"
UNTRUSTED_CLOSE = "<<<END UNTRUSTED PAGE TEXT>>>"

# Characters that carry no visual width but do carry meaning to a tokenizer:
# a prompt-injection payload can hide inside them, and a summarizer will read
# them as instructions if they are not removed.
_INVISIBLE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u206a-\u206f\ufeff\ufff9-\ufffb]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS = re.compile(r"\s+")


class UntrustedText:
    """Scrub third-party text and keep it in a clearly labelled block."""

    def __init__(self, max_chars: int = 50_000) -> None:
        self.max_chars = max_chars

    def scrub(self, text: str) -> str:
        cleaned = _INVISIBLE.sub("", text or "")
        cleaned = _CONTROL.sub(" ", cleaned)
        return _WS.sub(" ", cleaned).strip()

    def wrap(self, text: str, source: str = "") -> str:
        body = self.scrub(text)[:self.max_chars]
        head = f"{UNTRUSTED_OPEN}[source: {self.scrub(source) or 'unknown'}]\n"
        return head + body + "\n" + UNTRUSTED_CLOSE

    def strip_block(self, text: str) -> str:
        """Remove the delimiters, keeping the content (for storage)."""
        return (text or "").replace(UNTRUSTED_OPEN, "").replace(UNTRUSTED_CLOSE, "")

    def looks_injected(self, text: str) -> list[str]:
        """Signals that the page is addressing the summarizer, not the reader."""
        lowered = (text or "").lower()
        markers = (
            "ignore previous instructions", "ignore all previous",
            "disregard the above", "you are now", "system prompt",
            "as an ai language model", "new instructions:",
            "do not summarize", "output the following",
        )
        return [m for m in markers if m in lowered]


# ── HTML ──────────────────────────────────────────────────────────────────

class HtmlDocument(HTMLParser):
    """A minimal HTML tree: tags, attributes, text and anchors."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.root: dict[str, Any] = {"tag": "#root", "attrs": {}, "children": [],
                                     "text": []}
        self.anchors: list[dict[str, str]] = []
        self.meta_charset: str = ""
        self.title: str = ""
        self._in_title = False
        self._current_anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k.lower(): (v or "") for k, v in attrs}
        node = {"tag": tag.lower(), "attrs": attributes, "children": [], "text": []}
        if self.stack:
            self.stack[-1]["children"].append(node)
        else:
            self.root["children"].append(node)
        self.stack.append(node)

        if tag.lower() == "meta":
            charset = attributes.get("charset", "")
            if not charset:
                content = attributes.get("content", "")
                match = re.search(r"charset\s*=\s*([\w.:-]+)", content, re.I)
                charset = match.group(1) if match else ""
            if charset and not self.meta_charset:
                self.meta_charset = charset
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a":
            self._current_anchor = {"href": attributes.get("href", ""), "text": ""}

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_anchor is not None:
            self._current_anchor["text"] = _WS.sub(" ", self._current_anchor["text"]).strip()
            self.anchors.append(self._current_anchor)
            self._current_anchor = None
        # Close back to the matching tag; unbalanced markup is common on the
        # surface this parser is pointed at, so a stray close must not corrupt
        # the stack.
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if self.stack:
            self.stack[-1]["text"].append(data)
        else:
            self.root["text"].append(data)
        if self._in_title:
            self.title += data
        if self._current_anchor is not None:
            self._current_anchor["text"] += data

    @classmethod
    def parse(cls, html: str) -> "HtmlDocument":
        document = cls()
        try:
            document.feed(html or "")
            document.close()
        except Exception:  # malformed markup must not abort an investigation
            pass
        return document


BOILERPLATE_TAGS = frozenset({"nav", "header", "footer", "aside", "script", "style"})
# If stripping furniture leaves less than this share of the page, the strip is
# assumed to have eaten the content and is discarded.
MIN_STRIPPED_RATIO = 0.25


def _collect_text(node: dict[str, Any], skip: frozenset[str],
                  out: list[str]) -> None:
    if node["tag"] in skip:
        return
    out.extend(node["text"])
    for child in node["children"]:
        _collect_text(child, skip, out)


class TextExtractor:
    """Readable text and onion links out of an HTML document."""

    def __init__(self, max_text_chars: int = 50_000,
                 max_links: int = 20, max_link_chars: int = 120) -> None:
        self.max_text_chars = max_text_chars
        self.max_links = max_links
        self.max_link_chars = max_link_chars

    def text(self, html: str) -> str:
        document = HtmlDocument.parse(html)
        full: list[str] = []
        _collect_text(document.root, frozenset(), full)
        full_text = _WS.sub(" ", " ".join(full)).strip()

        stripped: list[str] = []
        _collect_text(document.root, BOILERPLATE_TAGS, stripped)
        text = _WS.sub(" ", " ".join(stripped)).strip()
        if len(text) < MIN_STRIPPED_RATIO * len(full_text):
            text = full_text
        return text[:self.max_text_chars]

    def title(self, html: str) -> str:
        return _WS.sub(" ", HtmlDocument.parse(html).title).strip()

    def onion_links(self, html: str, base_url: str = "") -> list[str]:
        """Onion URLs this page points at, other hosts before its own."""
        document = HtmlDocument.parse(html)
        page_host = (urlparse(base_url or "").hostname or "").lower()
        seen: set[str] = set()
        off_host: list[str] = []
        same_host: list[str] = []

        def keep(url: str) -> None:
            url = url.split("#", 1)[0][:self.max_link_chars]
            if not is_onion(url):
                return
            key = url.rstrip("/").lower()
            if key in seen:
                return
            seen.add(key)
            host = (urlparse(url).hostname or "").lower()
            (same_host if host == page_host else off_host).append(url)

        unwrapper = RedirectUnwrapper()
        for anchor in document.anchors:
            href = (anchor.get("href") or "").strip()
            if href and not href.startswith("#"):
                # An engine or directory often wraps the real destination in a
                # same-host redirect; the wrapper is not the target.
                try:
                    target = unwrapper.unwrap(href, page_host)
                    keep(target or urljoin(base_url or "", href))
                except ValueError:
                    pass
            for match in _ONION_IN_TEXT.finditer(anchor.get("text") or ""):
                keep("http://{}.onion{}".format(match.group(1).lower(),
                                                match.group(2) or ""))
        for match in _ONION_IN_TEXT.finditer(self.text(html)):
            keep("http://{}.onion{}".format(match.group(1).lower(),
                                            match.group(2) or ""))
        return (off_host + same_host)[:self.max_links]


# ── Body handling ─────────────────────────────────────────────────────────

BOM_ENCODINGS = ((b"\xef\xbb\xbf", "utf-8-sig"),)


class BodyReader:
    """Byte-capped reads and charset-correct decoding for untrusted bodies."""

    def __init__(self, max_bytes: int = 1_000_000,
                 max_chars: int = 50_000,
                 allowed_types: Sequence[str] = ("text/html", "application/xhtml+xml",
                                                 "text/plain")) -> None:
        self.max_bytes = max_bytes
        self.max_chars = max_chars
        self.allowed_types = tuple(allowed_types)

    def cap(self, body: bytes, max_bytes: int | None = None) -> bytes:
        limit = self.max_bytes if max_bytes is None else max_bytes
        return (body or b"")[:max(0, limit)]

    def content_type_allowed(self, content_type: str) -> bool:
        lowered = (content_type or "").lower()
        if not lowered:
            return True
        return any(t in lowered for t in self.allowed_types)

    @staticmethod
    def _codec(name: str) -> str | None:
        cleaned = (name or "").strip().lower()
        return cleaned or None

    def charset(self, body: bytes, content_type: str = "") -> str:
        """Header, then BOM, then <meta>, then valid UTF-8, then latin-1."""
        match = re.search(r"charset\s*=\s*[\"']?\s*([^\"';\s]+)", content_type or "",
                          re.IGNORECASE)
        if match:
            codec = self._codec(match.group(1))
            if codec:
                return codec
        for bom, name in BOM_ENCODINGS:
            if body.startswith(bom):
                return name
        if body.startswith(b"\xff\xfe") or body.startswith(b"\xfe\xff"):
            return "utf-16"
        meta = re.search(rb"<meta[^>]*?charset\s*=\s*[\"']?\s*([A-Za-z0-9._:-]+)",
                         body[:64 * 1024], re.IGNORECASE)
        if meta:
            return meta.group(1).decode("ascii", "ignore").lower()
        try:
            body.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "latin-1"

    def decode(self, body: bytes, content_type: str = "") -> str:
        """Decode with the detected charset, never raising on bad bytes."""
        codec = self.charset(body, content_type)
        try:
            text = body.decode(codec, errors="replace")
        except (LookupError, TypeError):
            text = body.decode("utf-8", errors="replace")
        return text[:self.max_chars]

    def read(self, response: Any, max_bytes: int | None = None) -> str:
        """Read a response object with ``.content`` or ``.read()``, then decode."""
        body: bytes
        if hasattr(response, "content"):
            body = response.content or b""
        elif hasattr(response, "read"):
            body = response.read(self.max_bytes) or b""
        else:
            body = bytes(response or b"")
        headers = getattr(response, "headers", {}) or {}
        content_type = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
        return self.decode(self.cap(body, max_bytes), content_type)


# ── Results ───────────────────────────────────────────────────────────────

# Child sexual abuse material: never listed, filtered or scraped. Only
# unambiguous patterns, so adult and leak material is not caught in the net.
_ABUSE_MATERIAL = re.compile(
    r"child\W{0,3}(?:porn|sex|rape|nud)"
    r"|(?:rape|porn|sex)\W{0,3}child"
    r"|\bpedo(?:phil\w*|s)?\b"
    r"|\bpthc\b|\bjailbait\b|\bpreteens?\b|\blolitas?\b|\bhurtcore\b"
    r"|\bkidflix|\bonly\W{0,3}kids"
    r"|\bkid(?:s|dy|die)?\W{0,3}(?:porn|sex|nud)"
    r"|\bunderage\W{0,3}(?:porn|sex|nud|girls?|boys?)"
    r"|\bcp\W{0,3}(?:porn|videos?|links?|archive|collection)\b"
    r"|\bcsam\b", re.IGNORECASE)

MAX_TITLE_CHARS = 200
TRACKING_PARAMS = frozenset({
    "utm", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "fbclid", "gclid", "yclid", "msclkid", "src",
})

ENGINE_OK = "ok"
ENGINE_EMPTY = "empty"
ENGINE_FAILED = "failed"


@dataclass
class SearchResult:
    """One engine hit: a title and the target URL it points at."""

    title: str
    link: str
    engine: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"title": self.title, "link": self.link, "engine": self.engine}


def is_abuse_material(result: SearchResult | dict[str, Any]) -> bool:
    """True when a result's title or link names child sexual abuse material."""
    if isinstance(result, dict):
        title = result.get("title") or ""
        link = result.get("link") or ""
    else:
        title, link = result.title, result.link
    text = f"{title} {link} {unquote(link)}"
    return bool(_ABUSE_MATERIAL.search(text))


def dedup_key(link: str) -> str:
    """Identity of a page: host, path and query minus tracking parameters."""
    parsed = urlparse(link or "")
    kept = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(kept), doseq=True)
    return "{}://{}{}{}".format(
        parsed.scheme,
        unquote(parsed.hostname or "").lower(),
        unquote(parsed.path).rstrip("/"),
        "?" + query if query else "",
    )


@dataclass
class ResultStats:
    """What the filters did, so a thin search is not mistaken for an empty web."""

    results_raw: int
    dropped_abuse: int
    after_dedup: int
    kept: int
    distinct_hosts: int
    per_host_limit: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "results_raw": self.results_raw,
            "results_dropped_abuse": self.dropped_abuse,
            "results_after_dedup": self.after_dedup,
            "results_kept": self.kept,
            "distinct_hosts": self.distinct_hosts,
            "per_host_limit": self.per_host_limit,
        }


class ResultFilter:
    """Refuse, normalise, deduplicate and cap engine results."""

    def __init__(self, per_host_limit: int = 3,
                 max_title_chars: int = MAX_TITLE_CHARS,
                 max_results: int | None = None) -> None:
        self.per_host_limit = per_host_limit
        self.max_title_chars = max_title_chars
        self.max_results = max_results

    @staticmethod
    def useful_title(title: str) -> bool:
        return bool(title) and len(title) >= 4 and any(ch.isalnum() for ch in title)

    def trim_title(self, title: str) -> str:
        clean = _WS.sub(" ", (title or "")).strip()
        if len(clean) <= self.max_title_chars:
            return clean
        return clean[:self.max_title_chars].rstrip() + "..."

    @staticmethod
    def host(link: str) -> str:
        try:
            return unquote(urlparse(link or "").hostname or "").lower()
        except ValueError:
            return ""

    def apply(self, results: Sequence[SearchResult],
              engine_hosts: Iterable[str] = ()) -> tuple[list[SearchResult], ResultStats]:
        blocked_hosts = {h.lower() for h in engine_hosts}
        cleaned: list[SearchResult] = []
        raw = len(results)
        dropped = 0
        for result in results:
            if is_abuse_material(result):
                dropped += 1
                continue
            if not self.useful_title(result.title):
                dropped += 1
                continue
            host = self.host(result.link)
            if host in blocked_hosts:
                dropped += 1
                continue
            cleaned.append(SearchResult(self.trim_title(result.title),
                                        result.link, result.engine))

        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for result in cleaned:
            try:
                key = dedup_key(result.link)
            except (ValueError, TypeError):
                key = result.link.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(result)

        counts: Counter[str] = Counter()
        kept: list[SearchResult] = []
        for result in deduped:
            host = self.host(result.link)
            if self.per_host_limit > 0 and counts[host] >= self.per_host_limit:
                continue
            counts[host] += 1
            kept.append(result)
        if self.max_results is not None:
            kept = kept[:max(0, self.max_results)]

        stats = ResultStats(
            results_raw=raw, dropped_abuse=dropped, after_dedup=len(deduped),
            kept=len(kept),
            distinct_hosts=len({self.host(r.link) for r in kept}),
            per_host_limit=self.per_host_limit,
        )
        return kept, stats


@dataclass
class EngineRecord:
    """What one search engine did with a query, and what it returned."""

    engine: str
    status: str
    http_status: int | None = None
    error: str = ""
    links: list[SearchResult] = field(default_factory=list)

    @property
    def results(self) -> int:
        return len(self.links)

    def as_dict(self) -> dict[str, Any]:
        return {"engine": self.engine, "status": self.status,
                "results": self.results, "http_status": self.http_status,
                "error": self.error}


@dataclass
class SearchOutcome:
    """Engine records plus the filtered results, with honest aggregates."""

    records: list[EngineRecord] = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def count(self, status: str) -> int:
        return sum(1 for r in self.records if r.status == status)

    @property
    def engines_unreachable(self) -> bool:
        """No engine replied, and at least one tried: the search did not run."""
        answered = self.count(ENGINE_OK) + self.count(ENGINE_EMPTY)
        return answered == 0 and self.count(ENGINE_FAILED) > 0

    def summary(self) -> dict[str, Any]:
        return {
            "engines_queried": len(self.records),
            "engines_answered": self.count(ENGINE_OK),
            "engines_empty": self.count(ENGINE_EMPTY),
            "engines_failed": self.count(ENGINE_FAILED),
            "unreachable": self.engines_unreachable,
            **dict(self.stats),
        }


class SearchAggregator:
    """Fold per-engine records into one filtered, de-duplicated outcome."""

    def __init__(self, result_filter: ResultFilter | None = None,
                 engine_hosts: Iterable[str] = ENGINE_HOSTS) -> None:
        self.result_filter = result_filter or ResultFilter()
        self.engine_hosts = tuple(engine_hosts)

    def aggregate(self, records: Sequence[EngineRecord]) -> SearchOutcome:
        raw: list[SearchResult] = [link for record in records for link in record.links]
        kept, stats = self.result_filter.apply(raw, self.engine_hosts)
        return SearchOutcome(records=list(records), results=kept,
                             stats=stats.as_dict())


def engine_status(result_count: int, http_status: int | None = None,
                  error: str = "") -> str:
    """Map a fetch outcome to the engine vocabulary."""
    if error:
        return ENGINE_FAILED
    if http_status is not None and http_status != 200:
        return ENGINE_FAILED
    return ENGINE_OK if result_count else ENGINE_EMPTY


def tor_bootstrapped(log_text: str) -> bool:
    """True when Tor's log says it can build circuits.

    The SOCKS port opens before circuits are ready; a search started in that
    window silently loses engines.
    """
    if not log_text:
        return True
    return "Bootstrapped 100%" in log_text


# ── Query refinement and pivots ───────────────────────────────────────────

STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "at", "by",
    "with", "from", "is", "are", "was", "were", "be", "been", "this", "that",
    "these", "those", "it", "its", "as", "about", "into", "over", "please",
    "find", "search", "look", "get", "me", "any", "all", "some",
})

# Keyword -> the alternative terms an onion index should also try. Appended as a
# parenthesised OR group so the engine reads it as one clause.
OPERATOR_HINTS = {
    "leak": "(dump OR database OR breach)",
    "market": "(shop OR vendor OR storefront)",
    "forum": "(board OR thread OR discussion)",
    "ransomware": "(lockbit OR extortion OR encryptor)",
    "credentials": "(combolist OR logs OR passwords)",
    "card": "(carding OR cvv OR bins)",
}


class QueryRefiner:
    """Turn a raw question into an onion search string.

    Deterministic on purpose: the refine step must never be the reason an
    investigation produces nothing, and the result has to be reproducible for
    the same input.
    """

    def __init__(self, max_terms: int = 8, add_hints: bool = True) -> None:
        self.max_terms = max_terms
        self.add_hints = add_hints

    def terms(self, query: str) -> list[str]:
        words = re.findall(r"[a-z0-9][a-z0-9._-]*", (query or "").lower())
        kept = [w for w in words if w not in STOPWORDS and len(w) > 1]
        seen: set[str] = set()
        unique: list[str] = []
        for word in kept:
            if word in seen:
                continue
            seen.add(word)
            unique.append(word)
        return unique[:self.max_terms]

    def refine(self, query: str) -> str:
        """Quoted multi-word phrases stay quoted; the rest is tightened.

        An onion index matches all terms, so a phrase that must stay together
        is quoted and everything else is dropped to its keywords.
        """
        raw = (query or "").strip()
        if not raw:
            return ""
        parts: list[str] = []
        for phrase in re.findall(r'"([^"]+)"', raw):
            cleaned = _WS.sub(" ", phrase).strip().lower()
            if cleaned:
                parts.append(f'"{cleaned}"')
        for match in re.findall(r"\b[0-9a-f]{16,64}\b", raw.lower()):
            if match not in parts:
                parts.append(match)
        for term in self.terms(re.sub(r'"[^"]+"', " ", raw)):
            if term not in " ".join(parts):
                parts.append(term)
        refined = " ".join(parts)
        if self.add_hints:
            for hint_key, hint in OPERATOR_HINTS.items():
                # Word-boundary match, so "leaked" does not trigger the "leak"
                # hint and quietly change the query's meaning.
                if re.search(r"\b" + re.escape(hint_key) + r"\b", refined):
                    refined += " " + hint
                    break
        return refined.strip()

    @staticmethod
    def encode(query: str) -> str:
        """Percent-encode for an engine URL template (``+`` between terms)."""
        return quote_plus(query or "")


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{3,32}\b")
WALLET_RE = re.compile(r"\b(?:bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}"
                       r"|4[0-9AB][1-9A-HJ-NP-Za-km-z]{93})\b")
HASH_RE = re.compile(r"\b[0-9a-fA-F]{32,64}\b")
PGP_RE = re.compile(r"-----BEGIN PGP PUBLIC KEY BLOCK-----")


@dataclass
class Pivot:
    """A follow-up lead lifted out of scraped text."""

    kind: str          # onion | email | handle | wallet | hash | pgp
    value: str
    source: str = ""
    score: float = 0.5

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value,
                "source": self.source, "score": round(self.score, 4)}


class PivotSuggester:
    """Extract follow-up pivots from scraped pages, ranked by how well they carry.

    A wallet address or a PGP key identifies an actor across markets; a generic
    32-character hash often does not. The score encodes that, so the caller can
    cut the list instead of chasing noise.
    """

    KIND_WEIGHTS = {
        "onion": 0.9, "wallet": 0.85, "pgp": 0.8, "email": 0.6,
        "handle": 0.45, "hash": 0.3,
    }

    def __init__(self, limit: int = 8, min_occurrences: int = 1) -> None:
        self.limit = limit
        self.min_occurrences = min_occurrences

    def extract(self, pages: dict[str, str]) -> list[Pivot]:
        counter: Counter[tuple[str, str]] = Counter()
        source_of: dict[tuple[str, str], str] = {}
        for url, text in (pages or {}).items():
            cleaned = UntrustedText().scrub(text)
            for match in re.finditer(r"(?:https?://)?([a-z2-7]{16}|[a-z2-7]{56})"
                                     r"\.onion", cleaned, re.IGNORECASE):
                value = f"http://{match.group(1).lower()}.onion"
                key = ("onion", value)
                counter[key] += 1
                source_of.setdefault(key, url)
            for kind, pattern in (("email", EMAIL_RE), ("handle", HANDLE_RE),
                                  ("wallet", WALLET_RE), ("hash", HASH_RE)):
                for match in pattern.finditer(cleaned):
                    value = match.group(0)
                    if kind == "hash" and value.lower().startswith(("http",)):
                        continue
                    key = (kind, value)
                    counter[key] += 1
                    source_of.setdefault(key, url)
            if PGP_RE.search(cleaned):
                key = ("pgp", "pgp_public_key_block")
                counter[key] += 1
                source_of.setdefault(key, url)

        pivots: list[Pivot] = []
        for (kind, value), occurrences in counter.items():
            if occurrences < self.min_occurrences:
                continue
            base = self.KIND_WEIGHTS.get(kind, 0.3)
            # Repetition across pages matters, but only logarithmically.
            score = min(1.0, base + 0.1 * math.log2(occurrences + 1))
            pivots.append(Pivot(kind, value, source_of[(kind, value)], score))
        pivots.sort(key=lambda p: (-p.score, p.kind, p.value))
        return pivots[:self.limit]

    def queries(self, pivots: Sequence[Pivot]) -> list[str]:
        """Pivot -> the search string that follows it up."""
        out: list[str] = []
        for pivot in pivots:
            if pivot.kind == "onion":
                out.append(pivot.value)
            elif pivot.kind in ("email", "handle"):
                out.append(f'"{pivot.value}"')
            elif pivot.kind == "wallet":
                out.append(pivot.value)
            elif pivot.kind == "hash":
                out.append(pivot.value)
        return out


# ── Investigation ─────────────────────────────────────────────────────────

STATUS_NO_RESULTS = "no_results"
STATUS_ENGINES_UNREACHABLE = "engines_unreachable"
STATUS_NOTHING_RELEVANT = "nothing_relevant"
STATUS_NOTHING_READABLE = "nothing_readable"
STATUS_COMPLETE = "ok"

STAGE_ACTIONS = {
    "refine": "refine the query",
    "search": "search the dark web",
    "filter": "filter the search results",
    "scrape": "scrape the selected pages",
    "summarize": "generate the investigation summary",
    "save": "save the investigation",
}

DEFAULT_MAX_RESULTS = 25
DEFAULT_MAX_SCRAPE = 5
DEFAULT_CONTENT_CHARS = 8_000


class PipelineError(RuntimeError):
    """A stage failed: which one, and the error underneath."""

    def __init__(self, stage: str, original: Exception) -> None:
        self.stage = stage
        self.action = STAGE_ACTIONS.get(stage, stage)
        self.original = original
        super().__init__(f"Failed to {self.action}: {original}")


@dataclass
class ScrapeRecord:
    """The outcome of fetching one page, with the status that explains it."""

    url: str
    status: str
    title: str = ""
    text: str = ""
    http_status: int | None = None
    detail: str = ""
    links: list[str] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        return self.status == STATUS_OK and bool(self.text)

    def as_dict(self) -> dict[str, Any]:
        return {"url": self.url, "status": self.status, "title": self.title,
                "http_status": self.http_status, "detail": self.detail,
                "chars": len(self.text), "links": list(self.links)}


@dataclass
class Investigation:
    """Everything one investigation produced, and what it ran with."""

    query: str
    status: str = STATUS_COMPLETE
    refined: str = ""
    results: list[SearchResult] = field(default_factory=list)
    filtered: list[SearchResult] = field(default_factory=list)
    scraped: dict[str, ScrapeRecord] = field(default_factory=dict)
    summary: str = ""
    pivots: list[Pivot] = field(default_factory=list)
    engine_summary: dict[str, Any] = field(default_factory=dict)
    stages: list[str] = field(default_factory=list)
    max_results: int = DEFAULT_MAX_RESULTS
    max_scrape: int = DEFAULT_MAX_SCRAPE
    content_chars: int = DEFAULT_CONTENT_CHARS
    started_at: str = ""
    finished_at: str = ""
    saved_as: str | None = None

    @property
    def readable_pages(self) -> dict[str, str]:
        return {url: rec.text for url, rec in self.scraped.items() if rec.readable}

    def to_record(self) -> dict[str, Any]:
        """The JSON body written to disk: no raw page text, no credentials."""
        return {
            "query": self.query,
            "refined_query": self.refined,
            "status": self.status,
            "summary": self.summary,
            "sources": [r.as_dict() for r in self.filtered],
            "pivots": [p.as_dict() for p in self.pivots],
            "pages": [rec.as_dict() for rec in self.scraped.values()],
            "results_count": len(self.results),
            "scraped_count": len(self.scraped),
            "engine_summary": self.engine_summary,
            "stages": self.stages,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class InvestigationRunner:
    """Run refine -> search -> filter -> scrape -> summarize, honestly.

    Each stage is injectable, so the same code path runs against Tor in
    production and against fixtures in a test. Terminal statuses are distinct on
    purpose: "no engine answered" is not "the dark web is empty", and "the
    filtered pages were all unreachable" is not "nothing relevant exists".
    """

    def __init__(self, refiner: QueryRefiner | None = None,
                 result_filter: ResultFilter | None = None,
                 extractor: TextExtractor | None = None,
                 pivoter: PivotSuggester | None = None,
                 max_results: int = DEFAULT_MAX_RESULTS,
                 max_scrape: int = DEFAULT_MAX_SCRAPE,
                 content_chars: int = DEFAULT_CONTENT_CHARS,
                 on_stage: Callable[[str, Investigation], None] | None = None,
                 clock: Callable[[], str] = _now) -> None:
        self.refiner = refiner or QueryRefiner()
        self.result_filter = result_filter or ResultFilter()
        self.extractor = extractor or TextExtractor()
        self.pivoter = pivoter or PivotSuggester()
        self.max_results = max_results
        self.max_scrape = max_scrape
        self.content_chars = content_chars
        self.on_stage = on_stage
        self.clock = clock

    def _stage(self, name: str, investigation: Investigation) -> None:
        investigation.stages.append(name)
        if self.on_stage:
            self.on_stage(name, investigation)

    def run(self,
            query: str,
            search_fn: Callable[[str], SearchOutcome],
            scrape_fn: Callable[[Sequence[SearchResult], int], dict[str, ScrapeRecord]] | None = None,
            summarize_fn: Callable[[str, dict[str, str]], str] | None = None,
            save: bool = False,
            store: "InvestigationStore | None" = None) -> Investigation:
        investigation = Investigation(
            query=query, max_results=self.max_results,
            max_scrape=self.max_scrape, content_chars=self.content_chars,
            started_at=self.clock(),
        )

        # 1. refine
        self._stage("refine", investigation)
        try:
            investigation.refined = self.refiner.refine(query) or query
        except Exception as exc:  # a refinement bug must not lose the query
            raise PipelineError("refine", exc) from exc

        # 2. search
        self._stage("search", investigation)
        try:
            outcome = search_fn(investigation.refined)
        except Exception as exc:
            raise PipelineError("search", exc) from exc
        investigation.results = list(outcome.results)
        investigation.engine_summary = outcome.summary()

        if not investigation.results:
            return self._finish(
                investigation,
                STATUS_ENGINES_UNREACHABLE if outcome.engines_unreachable
                else STATUS_NO_RESULTS,
                save, store,
            )

        # 3. filter: the user's cap applies before anything is ranked further
        self._stage("filter", investigation)
        try:
            kept, stats = self.result_filter.apply(
                investigation.results[:self.max_results])
        except Exception as exc:
            raise PipelineError("filter", exc) from exc
        investigation.filtered = kept
        investigation.engine_summary.update(stats.as_dict())
        if not kept:
            return self._finish(investigation, STATUS_NOTHING_RELEVANT, save, store)

        if scrape_fn is None:
            return self._finish(investigation, STATUS_COMPLETE, save, store)

        # 4. scrape
        self._stage("scrape", investigation)
        try:
            investigation.scraped = dict(
                scrape_fn(kept[:self.max_scrape], self.content_chars) or {})
        except Exception as exc:
            raise PipelineError("scrape", exc) from exc
        if not investigation.readable_pages:
            return self._finish(investigation, STATUS_NOTHING_READABLE, save, store)

        # 5. summarize
        self._stage("summarize", investigation)
        try:
            if summarize_fn is None:
                investigation.summary = self._fallback_summary(investigation)
            else:
                investigation.summary = summarize_fn(
                    investigation.refined, investigation.readable_pages) or ""
        except Exception as exc:
            raise PipelineError("summarize", exc) from exc
        if not investigation.summary.strip():
            investigation.summary = self._fallback_summary(investigation)

        # 6. pivots: a convenience, never a reason to fail a finished run
        self._stage("pivots", investigation)
        try:
            investigation.pivots = self.pivoter.extract(investigation.readable_pages)
        except Exception:
            investigation.pivots = []

        return self._finish(investigation, STATUS_COMPLETE, save, store)

    def _fallback_summary(self, investigation: Investigation) -> str:
        lines = [f"Investigation: {investigation.refined or investigation.query}"]
        lines.append(f"Sources read: {len(investigation.readable_pages)}")
        for url, record in investigation.scraped.items():
            if not record.readable:
                continue
            snippet = record.text[:240].rstrip()
            lines.append(f"- {record.title or 'untitled'} ({url}): {snippet}")
        return "\n".join(lines)

    def _finish(self, investigation: Investigation, status: str,
                save: bool = False,
                store: "InvestigationStore | None" = None) -> Investigation:
        investigation.status = status
        investigation.finished_at = self.clock()
        if save and store is not None:
            self._stage("save", investigation)
            store.save(investigation)
        return investigation


# ── Store ─────────────────────────────────────────────────────────────────

FILENAME_PREFIX = "investigation_"
FILENAME_GLOB = FILENAME_PREFIX + "*.json"
_FILENAME_RE = re.compile(
    r"^" + re.escape(FILENAME_PREFIX) + r"(\d{8}_\d{6})(?:_(\d+))?\.json$")


class InvestigationStore:
    """Saved investigations on disk: unique names, newest first, tolerant reads."""

    def __init__(self, directory: str | Path = "investigations") -> None:
        self.directory = Path(directory)

    def _candidates(self, stamp: str) -> Iterable[str]:
        yield f"{FILENAME_PREFIX}{stamp}.json"
        suffix = 1
        while True:
            yield f"{FILENAME_PREFIX}{stamp}_{suffix}.json"
            suffix += 1

    def save(self, investigation: Investigation,
             stamp: str | None = None) -> str | None:
        """Write the record, claiming the first free name for this second.

        A write failure does not raise: the investigation stays intact in
        memory and comes back with ``saved_as`` unset.
        """
        stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        body = json.dumps(investigation.to_record(), indent=2, default=str)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            for name in self._candidates(stamp):
                path = self.directory / name
                try:
                    # Exclusive create: two saves in one second never collide.
                    with path.open("x", encoding="utf-8") as handle:
                        handle.write(body)
                except FileExistsError:
                    continue
                investigation.saved_as = name
                return name
        except OSError:
            return None
        return None

    @staticmethod
    def _order_key(path: Path) -> tuple[str, int]:
        match = _FILENAME_RE.match(path.name)
        if match:
            return (match.group(1), int(match.group(2) or 0))
        return (path.stem[len(FILENAME_PREFIX):], -1)

    def load(self) -> list[dict[str, Any]]:
        """Every saved record, newest first; unreadable files are skipped."""
        try:
            paths = sorted(self.directory.glob(FILENAME_GLOB),
                           key=self._order_key, reverse=True)
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            data["_filename"] = path.name
            records.append(data)
        return records


# ── Streaming ─────────────────────────────────────────────────────────────

_THINK_OPEN = re.compile(r"<\s*(think|thinking)\s*>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"<\s*/\s*(think|thinking)\s*>", re.IGNORECASE)
_THINK_BLOCK = re.compile(r"<\s*(think|thinking)\s*>.*?<\s*/\s*\1\s*>",
                          re.IGNORECASE | re.DOTALL)


class StreamingBuffer:
    """Collect streamed tokens, drop reasoning blocks, emit readable chunks.

    Reasoning models stream their scratchpad first. Forwarding it to a report —
    or to a caller's stdout, where a stdio JSON-RPC session would be destroyed —
    is a real failure, so the buffer holds tokens back until it knows whether
    they are the answer.
    """

    def __init__(self, emit: Callable[[str], None] | None = None,
                 buffer_limit: int = 60) -> None:
        self.emit = emit
        self.buffer_limit = max(1, buffer_limit)
        self.buffer = ""
        self.text = ""

    def feed(self, token: str) -> str:
        if not token:
            return ""
        self.buffer += token
        self.text += token
        # A partially received open tag must not be flushed as content.
        if _THINK_OPEN.search(self.buffer) and not _THINK_CLOSE.search(self.buffer):
            return ""
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            return self.flush()
        return ""

    def flush(self) -> str:
        chunk = _THINK_BLOCK.sub("", self.buffer)
        self.buffer = ""
        if not chunk:
            return ""
        if self.emit:
            self.emit(chunk)
        return chunk

    def close(self) -> str:
        return self.flush()

    @property
    def answer(self) -> str:
        """Everything streamed, with reasoning blocks removed."""
        return _THINK_BLOCK.sub("", self.text).strip()

    def escape_json_rpc(self) -> dict[str, Any]:
        """Whether the captured text is safe to put on a stdio transport."""
        raw = self.text
        return {"has_newlines": "\n" in raw, "length": len(raw),
                "safe_on_stdio": "\n" not in raw and len(raw) < 4096}
