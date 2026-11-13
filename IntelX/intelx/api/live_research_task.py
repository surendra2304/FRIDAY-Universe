"""Fresh research adapter for the universal task protocol, separate from history.

Receipt evidence describes pipeline output, NOT durable task persistence. A
transport/request id alone is never evidence of findings. Budget applies to the
whole pipeline, not individually to each document or LLM call.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable
from urllib.parse import urlsplit


def public_source(source: object) -> bool:
    if not isinstance(source, dict):
        return False
    try:
        url = urlsplit(str(source.get("url") or source.get("source_url") or ""))
        return url.scheme in {"http", "https"} and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


async def run_live_research(task_id: str, query: str, run: Callable[[], Awaitable[dict]]) -> dict:
    try:
        result = await asyncio.wait_for(run(), timeout=100.0)
    except TimeoutError:
        return {"task_id": task_id, "target_agent": "intelx", "status": "DEGRADED",
                "result": {}, "error": "research_deadline_exceeded",
                "summary": "Research exceeded its deadline; no completed brief is being claimed."}
    if not isinstance(result, dict):
        return {"task_id": task_id, "target_agent": "intelx", "status": "DEGRADED",
                "result": {}, "error": "invalid_pipeline_response", "summary": "Research returned an invalid response."}
    sources = result.get("sources")
    findings = result.get("findings")
    source_urls = {str(s.get("url") or s.get("source_url") or "")
                   for s in sources if public_source(s)} if isinstance(sources, list) else set()
    findings_cited = isinstance(findings, list) and bool(findings) and all(
        isinstance(f, dict) and isinstance(f.get("statement"), str) and bool(f["statement"].strip())
        and isinstance(f.get("citations"), list) and bool(f["citations"])
        and all(isinstance(c, dict) and c.get("source_url") in source_urls for c in f["citations"])
        for f in findings)
    evidence_ok = (str(result.get("status", "")).upper() == "SUCCESS"
                   and isinstance(sources, list) and bool(sources) and all(public_source(s) for s in sources)
                   and findings_cited)
    payload = dict(result)
    payload["query"] = query
    payload["citations_count"] = len(sources) if isinstance(sources, list) else 0
    payload["fresh_research"] = True
    payload["durable_run"] = False  # the current synchronous pipeline is ephemeral
    if not evidence_ok:
        return {"task_id": task_id, "target_agent": "intelx", "status": "DEGRADED", "result": payload,
                "error": "sourced_findings_unverified",
                "summary": "Fresh research ran but did not return verifiable sourced findings. No completed sourced brief is being claimed."}
    return {"task_id": task_id, "target_agent": "intelx", "status": "SUCCESS", "result": payload,
            "summary": str(result.get("summary") or "Fresh sourced research completed."),
            "receipt": {"requested_action": "research_live", "target": "intelx",
                        "authorization_decision": "AUTHORIZED", "failure_reason": None,
                        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
                        "result": {"run_id": result.get("run_id"), "fresh_research": True},
                        "verification_evidence": {"pipeline": "friday.research", "source_count": len(sources),
                                                  "findings_count": len(findings), "durable_run": False}}}


async def collect_live_brief(query: str, search, fetch, max_sources: int = 5) -> dict:
    """Fetch real documents and quote relevant passages without mock extraction.

    This is an explicitly extractive brief, not independent fact verification or
    an LLM-written synthesis. A search snippet alone is never promoted to a
    retrieved-document finding. Existing SSRF/robots/byte guards belong to fetch.
    """
    import hashlib
    import re
    from html.parser import HTMLParser

    class DocumentText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hidden = 0
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in {"script", "style", "noscript", "pre", "nav", "header", "footer"}:
                self.hidden += 1
            if tag in {"p", "div", "li", "h1", "h2", "h3", "br"} and not self.hidden:
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in {"script", "style", "noscript", "pre", "nav", "header", "footer"}:
                self.hidden = max(0, self.hidden - 1)
            if tag in {"p", "div", "li"} and not self.hidden:
                self.parts.append("\n")

        def handle_data(self, data):
            if not self.hidden:
                # Source formatting newlines are not paragraph boundaries.
                # Splitting on them returned isolated sentence tails in live docs.
                self.parts.append(data.replace("\r", " ").replace("\n", " "))

    # Explicit source URLs are fetched directly; they are still subject to the
    # hardened connector's SSRF, redirect, robots, MIME and byte limits.
    from types import SimpleNamespace
    direct_urls = re.findall(r"https?://[^\s<>\"']+", query)
    if direct_urls:
        results = [SimpleNamespace(url=u.rstrip(".,;"), title=u.rstrip(".,;")) for u in direct_urls[:max_sources]]
    else:
        results = await search.fetch(query, max_results=min(15, max_sources * 3))
    findings, sources, failures, seen = [], [], [], set()
    topical_query = re.sub(r"https?://[^\s]+", " ", query.lower())
    def normalized_words(text):
        # Treat serialize/serialization as the same topic, not URL tokens.
        return {"serializ" if word.startswith("serializ") else
                "quot" if word.startswith("quot") else word
                for word in re.findall(r"\w{3,}", text.lower())}
    terms = normalized_words(topical_query) - {"the", "and", "for", "what", "with", "from", "research", "summarize",
        "explain", "how", "does", "works", "handles", "give", "highlights",
        "cite", "actual", "source", "sources", "urls", "not", "build", "code",
        "publish", "anything", "please", "tell", "about", "this", "that"}
    for candidate in results[:15]:
        if len(sources) >= max_sources:
            break
        url = str(getattr(candidate, "url", ""))
        if url in seen or not public_source({"url": url}):
            continue
        seen.add(url)
        try:
            document = await fetch.fetch(url, max_bytes=250_000)
            if document.status_code != 200:
                failures.append({"url": url, "reason": "http_non_200"})
                continue
            content_type = str(document.content_type).lower()
            if not any(t in content_type for t in ("text/html", "text/plain", "text/markdown")):
                failures.append({"url": url, "reason": "unsupported_document_type"})
                continue
            final_url = str(document.final_url or url)
            if not public_source({"url": final_url}):
                continue
            text = document.content.decode("utf-8", "replace")
            if "text/html" in content_type:
                parser = DocumentText()
                parser.feed(text)
                text = "".join(parser.parts)
            paragraphs = [" ".join(p.split()) for p in text.splitlines()]
            # Titles, function signatures and navigation are not useful sourced
            # answers. Require a prose sentence; version-number dots don't count.
            paragraphs = [p for p in paragraphs if 40 <= len(p) <= 4000
                          and re.search(r"[.!?](?:\s|$)", p)]
            ranked = sorted(enumerate(paragraphs), key=lambda p: (-len(terms & normalized_words(p[1])), p[0]))
            if terms:
                ranked = [p for p in ranked if terms & normalized_words(p[1])]
            if not ranked:
                failures.append({"url": url, "reason": "no_topical_passage" if paragraphs else "no_readable_passage"})
                continue
            # Keep separate contiguous passages; never label disjoint text as
            # a single verbatim quote or let one long paragraph erase the rest.
            passages = list(dict.fromkeys(passage for _, passage in ranked))[:3]
            sid = hashlib.sha256(final_url.encode()).hexdigest()[:16]
            title = str(getattr(candidate, "title", "") or final_url)[:160]
            source = {"id": sid, "title": title, "url": final_url,
                      "retrieved_at": datetime.now(timezone.utc).isoformat(),
                      "evidence_kind": "retrieved_document", "independently_verified": False}
            sources.append(source)
            for passage in passages:
                excerpt = passage[:1200]
                findings.append({"statement": excerpt, "status": "source_excerpt", "quote": excerpt,
                                 "truncated": len(passage) > len(excerpt),
                                 "citations": [{"source_id": sid, "source_title": title, "source_url": final_url}]})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures.append({"url": url, "reason": type(exc).__name__})
    spoken = " ".join(f"According to {f['citations'][0]['source_title']}, {f['statement']}" for f in findings[:3])
    if not spoken:
        spoken = "I could not retrieve readable sources for that query. I will not invent a research brief."
    lines = ["Retrieved-source excerpts — not independently verified facts or a verified answer to every part of the question."]
    for finding in findings:
        citation = finding["citations"][0]
        lines.extend([f"\n{citation['source_title']}: {finding['statement']}", citation["source_url"]])
    return {"status": "SUCCESS" if findings else "DEGRADED", "query": query,
            "answer_kind": "source_excerpts", "question_answered": False,
            "findings": findings, "sources": sources, "spoken_summary": spoken,
            "text_response": "\n".join(lines), "source_failures": failures,
            "summary": f"Retrieved {len(sources)} source document(s); findings are attributed excerpts, not independent verification."}
