"""Pre-synthesis source-diversity check for the live research pipeline.

TASK-INT-004 (2026-11-15): a code audit of the live research pipeline found
that diversity was never measured anywhere in it — a finding citing two
outlets that both republished the same wire copy counted as if it had two
independent sources behind it. (The companion empirical audit of persisted
production outputs is still outstanding; see
``IntelX/docs/SOURCE_DIVERSITY_AUDIT_INT004.md``.) This module is the check
that now runs in ``collect_live_brief`` BEFORE synthesis:

- Retrieved documents are clustered by near-duplicate text (token-set
  Jaccard). Documents in one cluster are the same underlying copy — wire
  syndication, mirrors, reprints — and collapse to ONE independent source.
- The synthesizer is handed only the cluster representatives, so syndicated
  copies cannot masquerade as independent corroboration in the draft either.
- Every finding is annotated with the number of INDEPENDENT sources behind
  its citations (after collapse) and flagged ``single_source`` when that
  count is below two. The flag is surfaced on the result, never hidden:
  in the current pipeline shape most findings are single-source by
  construction (one citation per finding), and the report says so plainly.

Pure stdlib, deterministic, no network. Similarity is a lexical proxy for
"same copy", not a semantic judgement: two genuinely different articles that
happen to share vocabulary stay separate at the 0.80 threshold, and the
report records exactly which documents collapsed together so the decision
is auditable.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

#: Token-set Jaccard at or above this means "same underlying copy".
NEAR_DUPLICATE_THRESHOLD = 0.80

#: A finding needs at least this many independent sources to not be flagged.
MIN_INDEPENDENT_SOURCES = 2

_WORD = re.compile(r"\w{3,}")


def source_domain(url: str) -> str:
    """Registrable-style host key: lowercased hostname minus a leading www."""
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _tokens(text: str) -> frozenset:
    return frozenset(_WORD.findall(str(text or "").lower()))


def text_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity in [0, 1]; 0.0 when either side is empty."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cluster_documents(documents: list[dict], threshold: float = NEAR_DUPLICATE_THRESHOLD):
    """Group near-duplicate documents; return (cluster_of, groups).

    ``cluster_of`` maps every document's source_id to its cluster
    representative's source_id (the first document of the cluster in
    retrieval order). ``groups`` lists only the multi-member clusters —
    the wire-echo evidence — with member ids and their domains.
    """
    ids = [str(d.get("source_id") or "") for d in documents]
    parent = {sid: sid for sid in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            # Keep the earlier-retrieved document as representative.
            parent[max(rx, ry, key=ids.index)] = min(rx, ry, key=ids.index)

    for i in range(len(documents)):
        for j in range(i + 1, len(documents)):
            if text_similarity(documents[i].get("text"), documents[j].get("text")) >= threshold:
                union(ids[i], ids[j])
    cluster_of = {sid: find(sid) for sid in ids}
    members: dict[str, list[dict]] = {}
    for d in documents:
        members.setdefault(cluster_of[str(d.get("source_id") or "")], []).append(d)
    groups = [
        {"representative": rep,
         "members": [str(d.get("source_id") or "") for d in docs],
         "domains": sorted({source_domain(d.get("url")) for d in docs} - {""})}
        for rep, docs in members.items() if len(docs) > 1
    ]
    return cluster_of, groups


def collapse_documents(documents: list[dict], cluster_of: dict) -> list[dict]:
    """One representative document per cluster, retrieval order preserved."""
    seen, out = set(), []
    for d in documents:
        rep = cluster_of.get(str(d.get("source_id") or ""))
        if rep not in seen:
            seen.add(rep)
            out.append(d)
    return out


def _cited_source_ids(finding: dict, url_to_id: dict) -> list[str]:
    ids = []
    for c in finding.get("citations") or []:
        if not isinstance(c, dict):
            continue
        sid = c.get("source_id") or url_to_id.get(str(c.get("source_url") or ""))
        if sid:
            ids.append(str(sid))
    return ids


def annotate_findings(findings: list[dict], documents: list[dict], cluster_of: dict) -> list[dict]:
    """Copy each finding with its independent-source count and diversity flag.

    The count is the number of distinct clusters behind the finding's
    citations — two citations into one wire-copy cluster count as one.
    Citations that resolve to no retrieved document count as zero.
    """
    url_to_id = {str(d.get("url") or ""): str(d.get("source_id") or "") for d in documents}
    out = []
    for f in findings:
        if not isinstance(f, dict):
            out.append(f)
            continue
        clusters = {cluster_of.get(sid, sid) for sid in _cited_source_ids(f, url_to_id)}
        count = len(clusters)
        out.append({**f, "independent_source_count": count,
                    "diversity_flag": "single_source" if count < MIN_INDEPENDENT_SOURCES else "multi_source"})
    return out


def build_diversity_report(findings: list[dict], documents: list[dict],
                           cluster_of: dict, groups: list[dict]) -> dict:
    """Run-level diversity summary attached to every brief result."""
    annotated = annotate_findings(findings, documents, cluster_of)
    single = sum(1 for f in annotated
                 if isinstance(f, dict) and f.get("diversity_flag") == "single_source")
    total = len(annotated)
    return {
        "documents_retrieved": len(documents),
        "distinct_domains": len({source_domain(d.get("url")) for d in documents} - {""}),
        "independent_sources": len(set(cluster_of.values())),
        "collapsed_groups": groups,
        "findings": total,
        "single_source_findings": single,
        "single_source_share": round(single / total, 4) if total else None,
        "min_independent_sources_required": MIN_INDEPENDENT_SOURCES,
    }


def assess_source_diversity(findings: list[dict], documents: list[dict]):
    """One-call pipeline entry: (annotated_findings, report, collapsed_documents)."""
    cluster_of, groups = cluster_documents(documents)
    annotated = annotate_findings(findings, documents, cluster_of)
    report = build_diversity_report(findings, documents, cluster_of, groups)
    return annotated, report, collapse_documents(documents, cluster_of)
