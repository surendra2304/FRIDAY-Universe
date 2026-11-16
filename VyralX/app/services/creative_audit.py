"""VyralX creative audit for its OWN video packaging (TASK-IG2-VYR-10).

Pattern adapted from claude-ads (MIT,
https://github.com/AgriciDaniel/claude-ads): source-grounded audits
that report pass / fail / unknown findings *with evidence*, and
account changes that stay drafts unless a capability gate passes.
This is FRIDAY's own implementation of that audit pattern, applied
to the one creative surface VyralX actually owns today — a video's
title, thumbnail text, hook, description and tags. No
claude-ads code is vendored, and nothing here touches an ad
platform.

Deliberate scope limits (owner rules + upstream caveats):

* NO paid ad spend exists or is created: there are no ad accounts,
  no budgets and no platform calls in this module. It audits
  organic creative only, and any input claiming paid-spend data is
  reported as an unknown finding, never scored as performance.
* Findings are evidence-gated: a check that cannot be evaluated
  from the supplied creative (e.g. measured CTR, which needs
  platform analytics this module does not have) reports
  ``unknown`` with the missing evidence named — mirroring
  upstream's honesty that its scoring profiles ship disabled. This
  module likewise emits NO composite score.
* Changes are drafts: :func:`draft_revisions` returns proposed
  copy for owner review and mutates nothing; there is deliberately
  no apply/publish function here.

Checks that VyralX already owns are reused, not reinvented: title,
thumbnail-text and hook findings delegate to
``app.services.packaging`` lints, so the audit can never drift from
the packaging rules the pipeline actually enforces.
"""
from __future__ import annotations

from typing import Any

from app.services import packaging

AUDIT_VERSION = "ig2-vyr10-1"

STATUSES = ("pass", "fail", "unknown")

#: Description/tag hygiene limits for Shorts metadata.
DESCRIPTION_MIN_CHARS = 40
DESCRIPTION_MAX_HASHTAGS = 5
TAG_MIN_COUNT = 3
TAG_MAX_COUNT = 15


def _finding(check: str, status: str, evidence: str) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"status {status!r} not in {STATUSES}")
    return {"check": check, "status": status, "evidence": evidence}


def audit_creative(creative: dict[str, Any], *,
                   lane: str = "space_science") -> dict[str, Any]:
    """Audit one video's packaging with evidence for every finding.

    ``creative`` keys: title, thumbnail_text, hook_line,
    description, tags, and optionally ``paid_spend`` / ``ctr``
    claims — which are never scored (see module docstring).
    Returns findings plus pass/fail/unknown counts; NO composite
    score is emitted, by design.
    """
    creative = dict(creative or {})
    findings: list[dict[str, Any]] = []

    title = str(creative.get("title") or "")
    title_lint = packaging.lint_title(title, lane)
    findings.append(_finding(
        "title_packaging",
        "pass" if title_lint["ok"] else "fail",
        "; ".join(title_lint["issues"]) or f"title {title!r} passes lane lint"))

    thumb = str(creative.get("thumbnail_text") or "")
    thumb_lint = packaging.lint_thumbnail_text(thumb, title)
    findings.append(_finding(
        "thumbnail_text",
        "pass" if thumb_lint["ok"] else "fail",
        "; ".join(thumb_lint["issues"]) or f"thumbnail text {thumb!r} passes lint"))

    hook = str(creative.get("hook_line") or "")
    hook_score = packaging.score_hook(hook)
    findings.append(_finding(
        "hook_strength",
        "pass" if hook_score["ok"] else "fail",
        "; ".join(hook_score["issues"])
        or f"hook uses devices {hook_score['devices']}"))

    description = str(creative.get("description") or "")
    hashtags = description.count("#")
    if len(description) < DESCRIPTION_MIN_CHARS:
        findings.append(_finding(
            "description_substance", "fail",
            f"description is {len(description)} chars; "
            f"min {DESCRIPTION_MIN_CHARS}"))
    elif hashtags > DESCRIPTION_MAX_HASHTAGS:
        findings.append(_finding(
            "description_substance", "fail",
            f"{hashtags} hashtags; max {DESCRIPTION_MAX_HASHTAGS}"))
    else:
        findings.append(_finding(
            "description_substance", "pass",
            f"{len(description)} chars, {hashtags} hashtags"))

    tags = creative.get("tags") or []
    if TAG_MIN_COUNT <= len(tags) <= TAG_MAX_COUNT:
        findings.append(_finding(
            "tag_coverage", "pass", f"{len(tags)} tags"))
    else:
        findings.append(_finding(
            "tag_coverage", "fail",
            f"{len(tags)} tags; expected {TAG_MIN_COUNT}-{TAG_MAX_COUNT}"))

    # Evidence-gated unknowns: performance claims cannot be audited
    # from creative copy alone, and paid spend is out of scope.
    if "ctr" in creative or "retention" in creative:
        findings.append(_finding(
            "measured_performance", "unknown",
            "CTR/retention claims supplied without platform analytics "
            "evidence; not scored (audit input is creative copy only)"))
    else:
        findings.append(_finding(
            "measured_performance", "unknown",
            "no platform analytics evidence supplied; performance is "
            "not auditable from creative copy alone"))
    if creative.get("paid_spend"):
        findings.append(_finding(
            "paid_spend", "unknown",
            "paid spend claimed but VyralX runs no ad accounts; "
            "creative analysis only, no spend audited or created"))

    counts = {s: sum(1 for f in findings if f["status"] == s)
              for s in STATUSES}
    return {
        "version": AUDIT_VERSION,
        "kind": "vyralx.creative_audit",
        "lane": lane,
        "findings": findings,
        "counts": counts,
        "composite_score": None,
        "score_note": (
            "No composite score: like upstream claude-ads' disabled "
            "scoring profiles, scoring stays off until measured "
            "platform evidence exists to ground it."),
        "paid_spend_created": False,
        "changes_applied": False,
        "source": "claude-ads-pattern (MIT), FRIDAY-native port",
    }


def draft_revisions(creative: dict[str, Any], *,
                    lane: str = "space_science") -> dict[str, Any]:
    """Propose fixes for the failing checks — as a DRAFT only.

    Mirrors claude-ads' capability gate: the draft is returned for
    owner review, the input creative is not mutated, and nothing is
    applied or published from here.
    """
    audit = audit_creative(creative, lane=lane)
    failed = [f["check"] for f in audit["findings"] if f["status"] == "fail"]
    suggestions: dict[str, str] = {}
    if "title_packaging" in failed:
        suggestions["title"] = (
            "Rewrite to <=60 chars with a concrete anchor (number, "
            "question or named subject) and no banned lane terms.")
    if "thumbnail_text" in failed:
        suggestions["thumbnail_text"] = (
            "Cut to <=4 words / <=24 chars that do not repeat the "
            "title's opening words.")
    if "hook_strength" in failed:
        suggestions["hook_line"] = (
            "Rewrite to <=12 words carrying a number, question, "
            "negation/secret, or second-person address.")
    if "description_substance" in failed:
        suggestions["description"] = (
            f"Write >={DESCRIPTION_MIN_CHARS} chars of real context "
            f"with <={DESCRIPTION_MAX_HASHTAGS} hashtags.")
    if "tag_coverage" in failed:
        suggestions["tags"] = (
            f"Supply {TAG_MIN_COUNT}-{TAG_MAX_COUNT} specific tags.")
    return {
        "version": AUDIT_VERSION,
        "status": "draft",
        "applied": False,
        "failed_checks": failed,
        "suggestions": suggestions,
        "note": "Draft only — owner review required; nothing applied.",
    }


def creative_brief(topic: str, *, lane: str = "space_science") -> dict[str, Any]:
    """A claude-ads-style creative brief for one planned video:
    the constraints a creator works to, stated before production."""
    if lane not in packaging.LANES:
        raise ValueError(f"lane {lane!r} not in VyralX lanes")
    if not str(topic or "").strip():
        raise ValueError("topic is empty")
    return {
        "version": AUDIT_VERSION,
        "kind": "vyralx.creative_brief",
        "topic": str(topic),
        "lane": lane,
        "lane_label": packaging.LANES[lane]["label"],
        "constraints": {
            "title_max_chars": packaging.TITLE_MAX_CHARS,
            "thumbnail_max_words": packaging.THUMB_MAX_WORDS,
            "thumbnail_max_chars": packaging.THUMB_MAX_CHARS,
            "hook_max_words": packaging.HOOK_MAX_WORDS,
            "tags": f"{TAG_MIN_COUNT}-{TAG_MAX_COUNT}",
            "privacy_if_published": "unlisted",
            "paid_spend": False,
        },
        "audit_after_production": "app.services.creative_audit.audit_creative",
    }
