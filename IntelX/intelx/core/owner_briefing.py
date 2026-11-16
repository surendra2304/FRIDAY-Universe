"""Owner-briefing format for IntelX delivered research (TASK-INT-006).

Every briefing IntelX delivers to the owner — the live brief assembled by
``collect_live_brief`` and the stored-research export from
``export_text_citations`` — is framed the same way:

1. **Headline answer first.** The lead finding's own statement, never new
   prose invented by the formatter and never a process disclaimer. (The
   live brief carries one line before the headline block: the REL-016
   status label — "Unsynthesised — raw findings", "Source-attributed
   model draft", "Retrieved-source excerpts" — whose exact opening is
   pinned by tests/test_live_research_task_contract.py, because it is
   how any reader of the delivered text knows whether it is holding an
   answer at all. The stored export has no such label and leads with
   the headline itself.)
2. **Confidence on one line, in plain words**, with its measured basis
   (source/domain counts, quote verification, synthesis status, disputed
   or inference shares).
3. **Evidence with citations** — the existing citation machinery,
   unchanged, machine-validated as before.
4. **What would change this conclusion** — derived mechanically from the
   evidence state (single-domain dependence, disputed findings,
   excerpts-only delivery, synthesis failure). Never invented: if the
   evidence state does not produce a condition, none is printed.

Honesty constraints inherited from the pipeline, NOT weakened here:

- This pipeline verifies *attribution* (a quote matches its source), never
  truth, and semantic entailment is unchecked. Confidence therefore caps
  at "Moderate" for a quote-verified synthesised draft and at "Low" for
  raw excerpts, single-domain drafts, disputed or inference-only stored
  findings, and failed synthesis. No path in this module can emit "High".
- The label lines themselves stay (they are the REL-016 contract above),
  but their original disclaimer tails (attributed, not independently
  verified; excerpts are not an answer) are not repeated after them:
  that honesty content is preserved in the confidence basis and the
  change conditions — relocated, not dropped.

Coordination: TASK-INT-003's depth rubric scores source diversity (D1),
primary-source ratio (D2), contradiction handling (D3) and citation
verifiability (D4) on this same delivered text. The basis line reports the
D1/D2 inputs (source and distinct-domain counts), attributed positions
stay separate evidence lines (D3), and citations stay machine-verifiable
(D4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

_TWO_PART_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "com.au", "net.au", "co.in", "gov.in",
    "com.br", "co.jp", "com.cn", "co.za", "com.mx", "co.nz",
}


def registrable_domain(url: str) -> str:
    """Best-effort registrable domain for counting distinct outlets.

    Deliberately simple (last two labels, with a small two-part public
    suffix set): it only feeds counts in the confidence basis, never a
    trust decision.
    """
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    labels = [p for p in host.split(".") if p]
    if len(labels) <= 2:
        return host
    tail2 = ".".join(labels[-2:])
    if tail2 in _TWO_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return tail2


def distinct_domains(urls) -> list[str]:
    """Sorted distinct registrable domains for a set of source URLs."""
    return sorted({d for d in (registrable_domain(u) for u in urls) if d})


def _val(obj: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        val = obj.get(field_name, default)
    else:
        val = getattr(obj, field_name, default)
    return val if val is not None else default


@dataclass(frozen=True)
class BriefingAssessment:
    level: str  # "Moderate" or "Low" — see module docstring for the cap.
    basis: str
    change_conditions: tuple[str, ...]


def _single_domain_condition(domain: str) -> str:
    return (f"This rests on a single domain ({domain}). A second independent "
            f"source contradicting it would overturn the headline.")


def assess_live_briefing(*, answer_kind: str, synthesis_status: str,
                         synthesis_error_reason: str | None,
                         quotes_verified: bool, source_urls: list[str],
                         findings_count: int) -> BriefingAssessment:
    """Confidence + change conditions for a live brief envelope."""
    domains = distinct_domains(source_urls)
    n_sources = len(source_urls)
    if findings_count == 0:
        return BriefingAssessment(
            level="Low",
            basis="No findings were produced, so there is no conclusion to rely on.",
            change_conditions=(
                "A run that retrieves topical, readable sources would replace "
                "this empty result.",),
        )
    if synthesis_status == "failed":
        reason = synthesis_error_reason or "unknown"
        conditions = [
            "A successful synthesis run over the retrieved sources would "
            "replace these raw excerpts with an attributed answer — until "
            "then there is no conclusion to defend.",
        ]
        if len(domains) == 1:
            conditions.append(_single_domain_condition(domains[0]))
        return BriefingAssessment(
            level="Low",
            basis=(f"Synthesis failed ({reason}); what follows is verbatim "
                   f"source excerpts from {n_sources} source(s), not an answer."),
            change_conditions=tuple(conditions[:3]),
        )
    if answer_kind == "source_excerpts":
        conditions = [
            "A synthesised, quote-checked pass over these excerpts could "
            "reorder or replace this picture; treat the excerpts as raw "
            "material, not a conclusion.",
        ]
        if len(domains) == 1:
            conditions.append(_single_domain_condition(domains[0]))
        return BriefingAssessment(
            level="Low",
            basis=(f"Verbatim excerpts from {n_sources} source(s) across "
                   f"{len(domains)} domain(s); no synthesis was run, so no "
                   f"conclusion has been drawn from them."),
            change_conditions=tuple(conditions[:3]),
        )
    # Source-attributed model draft.
    if quotes_verified and len(domains) >= 2:
        return BriefingAssessment(
            level="Moderate",
            basis=(f"Source-attributed draft: every quotation was verified "
                   f"verbatim against its source ({n_sources} source(s), "
                   f"{len(domains)} domains). Claims are attributed, not "
                   f"independently fact-checked — that is why this caps at "
                   f"Moderate."),
            change_conditions=(
                "The cited sources agree as retrieved. A contradicting "
                "report from an independent outlet — or a correction from "
                "any cited source — would reopen the headline.",),
        )
    if quotes_verified and len(domains) == 1:
        return BriefingAssessment(
            level="Low",
            basis=(f"Source-attributed draft resting on a single domain "
                   f"({domains[0]}); quotations verified verbatim, claims "
                   f"not independently fact-checked."),
            change_conditions=(
                _single_domain_condition(domains[0]),
                f"A correction or retraction from {domains[0]} removes the "
                f"only support for the headline."),
        )
    return BriefingAssessment(
        level="Low",
        basis=("Source-attributed draft whose quotations could not be "
               "confirmed verified; treat as unconfirmed."),
        change_conditions=(
            "A draft whose quotations verify verbatim against the retrieved "
            "sources would replace this unconfirmed one.",),
    )


def assess_stored_briefing(findings: list[Any], sources: list[Any]) -> BriefingAssessment:
    """Confidence + change conditions for a stored-research export."""
    if not findings:
        return BriefingAssessment(
            level="Low",
            basis="No findings were produced, so there is no conclusion to rely on.",
            change_conditions=(
                "A run that produces cited findings would replace this "
                "empty result.",),
        )
    urls: list[str] = []
    for s in sources or []:
        u = _val(s, "url") or _val(s, "location")
        if u:
            urls.append(str(u))
    statuses: list[str] = []
    numeric_conf: list[float] = []
    for f in findings:
        statuses.append(str(_val(f, "status", "verified")).lower())
        for cit in _val(f, "citations", []) or []:
            cu = _val(cit, "source_url") or _val(cit, "url")
            if cu:
                urls.append(str(cu))
        conf = _val(f, "confidence")
        if conf is None:
            conf = _val(f, "confidence_score")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
            numeric_conf.append(float(conf))
    domains = distinct_domains(urls)
    n = len(findings)
    disputed = sum(1 for s in statuses if s == "disputed")
    inference = sum(1 for s in statuses if s in ("inference", "unverified"))
    verified = n - disputed - inference
    mean_note = ""
    if len(numeric_conf) == n and n:
        mean_note = f" Mean claim confidence {sum(numeric_conf) / n:.2f}."
    if disputed:
        conditions = [
            f"{disputed} of the findings below are marked disputed and are "
            f"unresolved; evidence settling that dispute would change this "
            f"briefing's balance.",
        ]
        if len(domains) == 1:
            conditions.append(_single_domain_condition(domains[0]))
        return BriefingAssessment(
            level="Low",
            basis=(f"{disputed} of {n} finding(s) are disputed and "
                   f"{inference} rest on inference; only {verified} are "
                   f"backed by verified claims.{mean_note}"),
            change_conditions=tuple(conditions[:3]),
        )
    if verified == 0:
        return BriefingAssessment(
            level="Low",
            basis=(f"All {n} finding(s) are inference or unverified; none is "
                   f"backed by a verified claim.{mean_note}"),
            change_conditions=(
                "A verified, cited claim supporting or contradicting these "
                "inferences would replace this basis entirely.",),
        )
    if len(domains) == 1:
        return BriefingAssessment(
            level="Low",
            basis=(f"{verified} of {n} finding(s) are backed by verified "
                   f"claims, but every citation traces to a single domain "
                   f"({domains[0]}).{mean_note}"),
            change_conditions=(_single_domain_condition(domains[0]),),
        )
    if inference and verified <= inference:
        return BriefingAssessment(
            level="Low",
            basis=(f"Only {verified} of {n} finding(s) are backed by "
                   f"verified claims across {len(domains)} domains; the "
                   f"rest are labelled inference.{mean_note}"),
            change_conditions=(
                "Verified evidence confirming or replacing the inference "
                "findings would change the balance of this briefing.",),
        )
    return BriefingAssessment(
        level="Moderate",
        basis=(f"{verified} of {n} finding(s) are backed by verified "
               f"claims across {len(domains)} domains"
               + (f"; {inference} further finding(s) are labelled inference"
                  if inference else "")
               + f". Citations are machine-checked for integrity; the "
               f"underlying facts are not independently verified — that is "
               f"why this caps at Moderate.{mean_note}"),
        change_conditions=(
            "The cited sources agree as retrieved. A contradicting report "
            "from an independent outlet — or a correction from any cited "
            "source — would reopen the headline.",),
    )


_MARKDOWN_TOKENS = re.compile(r"\[[CS]:[a-zA-Z0-9_\-]+\]")


def stored_headline(findings: list[Any]) -> str:
    """Headline for a stored export: the lead finding's own statement.

    Status prefixes follow the export's existing convention so a headline
    never presents inference or a disputed claim as settled.
    """
    if not findings:
        return "No findings were produced for this research."
    first = findings[0]
    statement = str(_val(first, "statement") or _val(first, "conclusion", "") or "").strip()
    statement = _MARKDOWN_TOKENS.sub("", statement).strip()
    status = str(_val(first, "status", "verified")).lower()
    if status in ("inference", "unverified"):
        return f"[Inference] {statement}"
    if status == "disputed":
        return f"[Disputed] {statement}"
    return statement


def render_headline_block(headline: str, assessment: BriefingAssessment) -> str:
    """The first thing the owner reads: answer, then plain confidence."""
    return (f"{headline}\n\n"
            f"Confidence: {assessment.level} — {assessment.basis}")


def render_change_conditions(assessment: BriefingAssessment, *, markdown: bool) -> str:
    """The 'what would change this conclusion' block ('' when none)."""
    if not assessment.change_conditions:
        return ""
    heading = ("### What Would Change This Conclusion" if markdown
               else "What would change this conclusion:")
    lines = [heading]
    lines.extend(f"- {c}" for c in assessment.change_conditions)
    return "\n".join(lines)
