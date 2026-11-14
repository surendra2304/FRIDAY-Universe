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


async def collect_live_brief(query: str, search, fetch, max_sources: int = 5, synthesize=None) -> dict:
    """Fetch real documents and quote relevant passages without mock extraction.

    Without a synthesis callback this is explicitly extractive. A configured
    callback may produce a source-attributed model draft, never independent fact
    verification. A search snippet alone is never promoted to a
    retrieved-document finding. Existing SSRF/robots/byte guards belong to fetch.

    TASK-REL-016: if the synthesis callback fails or returns a non-success
    draft, the extractive findings already retrieved are returned labelled
    unsynthesised (answer_kind "unsynthesised_raw_findings", status DEGRADED,
    synthesis error recorded) — retrieved evidence is never silently discarded,
    and it is never certified as a synthesised brief either.
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
    source_documents = []
    topical_query = re.sub(r"https?://[^\s]+", " ", query.lower())
    def normalized_words(text):
        # Treat serialize/serialization as the same topic, not URL tokens.
        return {"serializ" if word.startswith("serializ") else
                "quot" if word.startswith("quot") else word
                for word in re.findall(r"\w{3,}", text.lower())}
    terms = normalized_words(topical_query) - {"the", "and", "for", "what", "with", "from", "research", "summarize",
        "explain", "how", "does", "works", "handles", "give", "highlights",
        "cite", "actual", "source", "sources", "urls", "not", "build", "code",
        "publish", "anything", "please", "tell", "about", "this", "that", "only", "directly", "relevant", "passages",
        "excerpts", "answer", "question", "using", "based"}
    for candidate in results[:15]:
        if len(sources) >= max_sources:
            break
        url = str(getattr(candidate, "url", ""))
        if url in seen or not public_source({"url": url}):
            continue
        seen.add(url)
        try:
            # TASK-REL-007: 250KB was below the real size of modern article
            # pages — live evidence (2026-11-14) showed CNET/NBC/YouTube
            # candidates dying on ContentSizeExceededError before any prose
            # was captured, leaving too few source documents to synthesize
            # from. The connector still hard-caps at MAX_PAGE_BYTES (2MB)
            # and streams with abort, so the guard remains; this only stops
            # the brief pipeline from imposing a second, smaller cap.
            document = await fetch.fetch(url, max_bytes=1_000_000)
            if document.status_code != 200:
                failures.append({"url": url, "reason": f"http_{document.status_code}",
                                 "status_code": document.status_code})
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
            document_terms = set().union(*(normalized_words(p) for p in paragraphs))
            if len(terms) >= 3 and len(terms & document_terms) < 2:
                failures.append({"url": url, "reason": "insufficient_topic_overlap"})
                continue
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
            source_documents.append({"source_id": sid, "title": title, "url": final_url,
                                     "text": "\n".join(paragraphs)[:18_000]})
            for passage in passages:
                excerpt = passage[:1200]
                findings.append({"statement": excerpt, "status": "source_excerpt", "quote": excerpt,
                                 "truncated": len(passage) > len(excerpt),
                                 "citations": [{"source_id": sid, "source_title": title, "source_url": final_url}]})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # TASK-REL-038: record the precise skip reason, not just the
            # exception class. The hardened fetcher raises on HTTP errors;
            # surface the status code, and name the known Google News case:
            # news.google.com RSS article links are redirector URLs that
            # refuse automated fetches (typically 403) — an honest skip
            # with that reason, never a silent drop or a weakened guard.
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if isinstance(status_code, int):
                host = urlsplit(url).hostname or ""
                reason = (
                    f"google_news_redirect_http_{status_code}"
                    if host == "news.google.com" or host.endswith(".news.google.com")
                    else f"http_{status_code}"
                )
                failures.append({"url": url, "reason": reason, "status_code": status_code})
            else:
                failures.append({"url": url, "reason": type(exc).__name__})
    answer_kind = "source_excerpts"
    synthesis_metadata = {}
    synthesis_failure = None
    if synthesize is not None and source_documents:
        try:
            draft = await synthesize(query, source_documents)
            if draft.get("status") != "SUCCESS":
                # TASK-REL-016: a refused/unverified draft is a synthesis
                # failure, not a reason to destroy evidence already retrieved.
                # Keep the extractive findings; they are labelled
                # unsynthesised below and the result stays DEGRADED.
                synthesis_failure = {"reason": str(draft.get("error") or "synthesis_unverified")}
                failures.append(dict(synthesis_failure))
            else:
                findings = draft["findings"]
                answer_kind = draft["answer_kind"]
                synthesis_metadata = {k: draft[k] for k in ["quotes_verified", "semantic_entailment_verified", "synthesis_provider"]}
                used_ids = {c["source_id"] for f in findings for c in f["citations"]}
                sources = [s for s in sources if s["id"] in used_ids]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Same rule on the exception path: record the failure, keep the
            # extractive findings, never certify them as a synthesised brief.
            failure = {"reason": "synthesis_" + type(exc).__name__}
            # Explicit diagnostic codes only, never arbitrary exception strings,
            # model deliberation, prompts, credentials or response bodies.
            details = getattr(exc, "public_details", {})
            if isinstance(details, dict):
                failure.update({k: details[k] for k in ["reason_code", "finish_reason", "output_characters"] if k in details})
            synthesis_failure = failure
            failures.append(failure)
    if synthesis_failure is not None:
        answer_kind = "unsynthesised_raw_findings"
    spoken_body = " ".join(f"According to {f['citations'][0]['source_title']}, {f['statement']}" for f in findings[:3])
    if synthesis_failure is not None:
        spoken = (f"Unsynthesised raw findings — synthesis failed ({synthesis_failure['reason']}). {spoken_body}"
                  if spoken_body else
                  "Synthesis failed and no source excerpts could be extracted. No completed brief is being claimed.")
    elif spoken_body:
        spoken = spoken_body
    else:
        spoken = ("I retrieved sources but could not produce a source-grounded answer. No completed brief is being claimed."
                  if sources else "I could not retrieve topical readable sources for that query. I will not invent a research brief.")
    if synthesis_failure is not None:
        header = (f"Unsynthesised — raw findings: synthesis failed ({synthesis_failure['reason']}); "
                  "the excerpts below are verbatim retrieved source passages, NOT a synthesised answer.")
    elif answer_kind != "source_excerpts":
        header = "Source-attributed model draft — quotations checked, claims not independently verified."
    else:
        header = "Retrieved-source excerpts — not independently verified facts or a verified answer to every part of the question."
    lines = [header]
    for finding in findings:
        citation = finding["citations"][0]
        lines.extend([f"\n{citation['source_title']}: {finding['statement']}", citation["source_url"]])
        if synthesis_failure is None and answer_kind != "source_excerpts":
            lines.append(f"Supporting source quotation: {finding['quote']}")
    if findings and synthesis_failure is not None:
        summary = (f"Retrieved {len(sources)} source document(s); synthesis failed ({synthesis_failure['reason']}) — "
                   f"returning {len(findings)} unsynthesised raw finding(s) (verbatim source excerpts), not a synthesised brief.")
    elif findings:
        summary = f"Retrieved {len(sources)} source document(s); findings are source-attributed, not independent verification."
    else:
        summary = f"Retrieved {len(sources)} source document(s), but no grounded answer was verified."
    return {"status": "SUCCESS" if findings and synthesis_failure is None else "DEGRADED", "query": query,
            "answer_kind": answer_kind, "question_answered": False, **synthesis_metadata,
            "synthesis_status": ("failed" if synthesis_failure is not None else
                                 "succeeded" if synthesize is not None and source_documents else "not_attempted"),
            **({"synthesis_error": synthesis_failure} if synthesis_failure is not None else {}),
            "findings": findings, "sources": sources, "spoken_summary": spoken,
            "text_response": "\n".join(lines), "source_failures": failures,
            "summary": summary}
