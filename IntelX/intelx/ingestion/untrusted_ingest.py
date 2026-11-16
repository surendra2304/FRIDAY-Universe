"""Robin investigation pattern + untrusted-data hygiene (TASK-IG2-INT-04).

Source pattern: apurvsinghgautam/robin (MIT) — an AI dark-web OSINT tool
whose pipeline is: LLM query refinement -> search -> scrape -> LLM
filtering/summary, with the ingestion hygiene that scraped text is
returned inside **untrusted-data delimiters** after stripping control,
zero-width and bidi characters, so the model reads it as evidence rather
than instructions.

What is adopted here (pattern + hygiene only, per the spec card):
  * The pipeline shape, implemented FRIDAY-native with injectable
    search/fetch callables and a deterministic (no-LLM-key) refinement
    and relevance filter, so it runs fleet-feasible and hermetically
    testable.
  * The delimiter hygiene: :func:`strip_invisible` removes C0/C1 control
    characters (except newline/tab), zero-width characters, bidi
    overrides/embeddings and other Unicode format characters;
    :func:`wrap_untrusted` then wraps the cleaned text in explicit
    UNTRUSTED_DATA delimiters, neutralising any attempt by the payload
    itself to forge or close the delimiters.

What is explicitly NOT adopted:
  * Robin itself is not deployed (no Streamlit UI, no Tor daemon).
  * **No dark-web scraping from fleet IPs, ever.** This module performs
    no network I/O of its own; in production wiring the injected fetchers
    are IntelX's existing hardened clearnet connectors (SSRF guard,
    robots, byte caps). Use is defensive threat-intelligence research
    only — reading public reporting about threats, never interacting
    with dark-web services.

This complements (does not replace) ``connectors/sanitize.py`` (injection
*scanning*, non-mutating) and ``connectors/context_firewall.py`` (trust
tagging): those detect; this one cleans and delimits at ingestion time.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Awaitable, Callable

# ---------------------------------------------------------------------------
# Hygiene: strip invisible / control characters, then delimit
# ---------------------------------------------------------------------------

OPEN_DELIMITER = "<<<UNTRUSTED_DATA"
CLOSE_DELIMITER = "<<<END_UNTRUSTED_DATA>>>"
_DELIMITER_FORGERY_RE = re.compile(r"<{2,}\s*(?:END_)?UNTRUSTED_DATA\s*>{0,3}", re.IGNORECASE)
_KEEP_CONTROLS = {"\n", "\t"}


def strip_invisible(text: str) -> str:
    """Remove control, zero-width, bidi and other format characters.

    Newlines and tabs survive (they are document structure); every other
    Unicode category-C character (Cc, Cf, Cs, Co is kept — private use is
    content, Zl/Zp are normalised to spaces) is dropped or normalised.
    """
    out: list[str] = []
    for ch in text:
        if ch in _KEEP_CONTROLS:
            out.append(ch)
            continue
        category = unicodedata.category(ch)
        if category in ("Cc", "Cf", "Cs"):
            continue  # control, format (zero-width, bidi), surrogates
        if category in ("Zl", "Zp"):
            out.append(" ")
            continue
        out.append(ch)
    return "".join(out)


def wrap_untrusted(text: str, *, source: str) -> str:
    """Clean ``text`` and wrap it in untrusted-data delimiters.

    Any delimiter look-alike inside the payload is defused first, so the
    wrapped block has exactly one opening and one closing delimiter and
    the payload cannot break out of its evidence frame.
    """
    cleaned = strip_invisible(text)
    cleaned = _DELIMITER_FORGERY_RE.sub("[delimiter removed]", cleaned)
    safe_source = re.sub(r"[^A-Za-z0-9._\-/:]", "_", source)[:120]
    return f'{OPEN_DELIMITER} source="{safe_source}">>>\n{cleaned}\n{CLOSE_DELIMITER}'


def is_wrapped(text: str) -> bool:
    return text.startswith(OPEN_DELIMITER) and text.rstrip().endswith(CLOSE_DELIMITER)


# ---------------------------------------------------------------------------
# Pipeline: refine -> search -> scrape -> filter -> summarise (as evidence)
# ---------------------------------------------------------------------------

SearchFn = Callable[[str], Awaitable[list[dict]]]  # query -> [{title, url, snippet}]
FetchFn = Callable[[str], Awaitable[str]]  # url -> page text

_STOPWORDS = {
    "the", "a", "an", "of", "for", "and", "or", "in", "on", "to", "is",
    "what", "who", "how", "about", "with", "from", "that", "this",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]{1,}")
_QUOTED_RE = re.compile(r'"([^"]{2,80})"')


@dataclass(frozen=True)
class RefinedQuery:
    original: str
    refined: str
    pivots: tuple[str, ...]  # one-click follow-up queries (Robin pattern)
    key_terms: tuple[str, ...]


def refine_query(query: str) -> RefinedQuery:
    """Deterministic Robin-style query refinement (no LLM key required).

    Keeps quoted phrases verbatim, drops stopwords from the refined form,
    and derives pivot queries from the quoted phrases and the strongest
    key terms — the follow-ups an investigator would click next.
    """
    original = " ".join((query or "").split())
    quoted = _QUOTED_RE.findall(original)
    tokens = [t for t in _TOKEN_RE.findall(original) if t.lower() not in _STOPWORDS]
    key_terms = tuple(dict.fromkeys(t.lower() for t in tokens))
    refined_parts = [f'"{q}"' for q in quoted] + [t for t in tokens if t not in quoted]
    refined = " ".join(dict.fromkeys(refined_parts)) or original
    pivots: list[str] = []
    for phrase in quoted:
        pivots.append(f'"{phrase}" latest reporting')
    for term in key_terms[:3]:
        if term not in " ".join(pivots):
            pivots.append(f"{term} threat intelligence")
    return RefinedQuery(original=original, refined=refined, pivots=tuple(pivots[:5]), key_terms=key_terms)


def relevance_score(text: str, key_terms: tuple[str, ...]) -> float:
    """Fraction of key terms present in ``text`` (0.0-1.0), case-insensitive."""
    if not key_terms:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for term in key_terms if term in lowered)
    return hits / len(key_terms)


@dataclass
class EvidenceItem:
    title: str
    url: str
    relevance: float
    wrapped_text: str  # page text, cleaned + delimiter-wrapped

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "relevance": round(self.relevance, 4),
            "evidence": self.wrapped_text,
        }


@dataclass
class InvestigationResult:
    query: RefinedQuery
    evidence: list[EvidenceItem] = field(default_factory=list)
    dropped: int = 0  # search results filtered out as irrelevant/unfetchable

    def to_dict(self) -> dict:
        return {
            "original_query": self.query.original,
            "refined_query": self.query.refined,
            "pivot_queries": list(self.query.pivots),
            "evidence_count": len(self.evidence),
            "dropped": self.dropped,
            "evidence": [e.to_dict() for e in self.evidence],
        }


async def run_investigation(
    query: str,
    *,
    search: SearchFn,
    fetch: FetchFn,
    max_results: int = 5,
    min_relevance: float = 0.2,
    max_chars_per_page: int = 20_000,
) -> InvestigationResult:
    """Run one bounded investigation over injected clearnet search/fetch.

    Every scraped page enters the result only as delimiter-wrapped
    untrusted evidence; nothing scraped is ever returned as bare text
    that a downstream model could mistake for instructions.
    """
    refined = refine_query(query)
    results = await search(refined.refined)
    result = InvestigationResult(query=refined)
    for entry in results[: max(0, max_results)]:
        url = str(entry.get("url", ""))
        title = str(entry.get("title", ""))
        if not url:
            result.dropped += 1
            continue
        try:
            page = await fetch(url)
        except Exception:
            result.dropped += 1
            continue
        combined = f"{title}\n{entry.get('snippet', '')}\n{page}"
        score = relevance_score(combined, refined.key_terms)
        if score < min_relevance:
            result.dropped += 1
            continue
        result.evidence.append(EvidenceItem(
            title=title,
            url=url,
            relevance=score,
            wrapped_text=wrap_untrusted(page[:max_chars_per_page], source=url),
        ))
    result.evidence.sort(key=lambda e: e.relevance, reverse=True)
    return result
