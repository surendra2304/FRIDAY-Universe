"""Forge local-business prospecting + auto-website pipeline (TASK-IG2-FRG-06).

Cluster #7 (IG wave-2 triage, BUILD/Forge): find local businesses with no
(or a weak) website, mine their public reviews for what customers actually
praise/complain about, and generate a starter site from that evidence.

Hard boundaries, enforced in code — not just in prose:

* **Prospecting data only.** The pipeline consumes prospect records the
  caller already has (a Maps/directory export, a hand-built list, a test
  fixture). It performs no scraping and no network calls itself, so it
  cannot violate a source's terms by accident.
* **Approval gate before anything leaves the building.** A pipeline run
  ends in ``PENDING_APPROVAL``. ``contact_sheet()`` and the starter site
  are *internal artefacts* until ``approve()`` is called; ``publish()``
  and ``contact_plan()`` raise ``PipelineGateError`` while the gate is
  closed, and there is deliberately **no send/outreach function at all**
  — the contact plan is a document for the owner, never a transmission.

Stdlib only, Python 3.10, no new dependencies.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_PRAISE = {
    "food": ("food", "tasty", "delicious", "biryani", "pizza", "coffee"),
    "service": ("service", "staff", "friendly", "helpful", "polite"),
    "price": ("price", "affordable", "value", "cheap", "reasonable"),
    "ambience": ("ambience", "clean", "cozy", "atmosphere", "hygiene"),
    "speed": ("quick", "fast", "prompt", "delivery"),
}
_COMPLAINT = {
    "parking": ("parking",),
    "waiting": ("wait", "slow", "delay", "late"),
    "hygiene": ("dirty", "hygiene", "unclean"),
    "price": ("expensive", "overpriced", "costly"),
}


class PipelineGateError(RuntimeError):
    """Raised when a gated action is attempted before owner approval."""


@dataclass(slots=True)
class Prospect:
    """One local business, as supplied by the caller's prospecting source."""

    name: str
    category: str = ""
    area: str = ""
    phone: str = ""
    website: str = ""
    rating: float = 0.0
    review_count: int = 0
    reviews: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("prospect needs a name")
        if not (0.0 <= self.rating <= 5.0):
            raise ValueError("rating must be 0..5")
        if self.review_count < 0:
            raise ValueError("review_count must be >= 0")


def prospect_score(p: Prospect) -> float:
    """Opportunity score 0..1: no website + proven demand scores highest."""
    p.validate()
    score = 0.0
    if not p.website.strip():
        score += 0.5
    elif "facebook.com" in p.website or "instagram.com" in p.website:
        score += 0.3  # social page only — still no real website
    if p.review_count >= 100:
        score += 0.3
    elif p.review_count >= 20:
        score += 0.2
    elif p.review_count >= 5:
        score += 0.1
    if p.rating >= 4.0:
        score += 0.2
    elif p.rating >= 3.5:
        score += 0.1
    return round(min(score, 1.0), 3)


def mine_review_themes(reviews: list[str]) -> dict[str, list[str]]:
    """Keyword-mine reviews into praise/complaint themes (deterministic)."""
    praise: dict[str, int] = {}
    complaints: dict[str, int] = {}
    for review in reviews or []:
        text = f" {review.lower()} "
        for theme, words in _PRAISE.items():
            if any(w in text for w in words):
                praise[theme] = praise.get(theme, 0) + 1
        for theme, words in _COMPLAINT.items():
            if any(w in text for w in words):
                complaints[theme] = complaints.get(theme, 0) + 1
    return {
        "praise": sorted(praise, key=lambda k: -praise[k]),
        "complaints": sorted(complaints, key=lambda k: -complaints[k]),
    }


def build_site_prompt(p: Prospect, themes: dict[str, list[str]]) -> str:
    """The review-mined site prompt — the brief Forge builds the site from."""
    praise = ", ".join(themes.get("praise", [])) or "quality"
    complaints = ", ".join(themes.get("complaints", [])) or "none noted"
    return (
        f"Build a one-page starter website for {p.name} "
        f"({p.category or 'local business'} in {p.area or 'its area'}). "
        f"Customers praise: {praise}. Address honestly, do not hide: {complaints}. "
        f"Rating {p.rating} from {p.review_count} reviews. "
        "Sections: hero with name + category, about, services/menu highlights "
        "drawn from the praised themes, reviews strip, contact block with the "
        "business phone. No invented prices, awards, or testimonials."
    )


def render_starter_site(p: Prospect, themes: dict[str, list[str]]) -> str:
    """Render a single self-contained starter HTML page (all data escaped)."""
    name = html.escape(p.name)
    category = html.escape(p.category or "Local business")
    area = html.escape(p.area)
    phone = html.escape(p.phone)
    praise_items = "".join(
        f"<li>{html.escape(t.title())} — loved by customers</li>"
        for t in themes.get("praise", [])) or "<li>Quality local service</li>"
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{name} — {category}</title></head><body>"
        f"<header><h1>{name}</h1><p>{category} · {area}</p></header>"
        f"<section><h2>Why customers choose us</h2><ul>{praise_items}</ul></section>"
        f"<section><h2>Visit us</h2><p>Rated {p.rating} from {p.review_count} reviews.</p>"
        f"<p>Call: {phone}</p></section>"
        "<footer><p>Starter site generated by Forge — owner review required before publishing.</p></footer>"
        "</body></html>"
    )


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-") or "business"


@dataclass(slots=True)
class PipelineRun:
    """One pipeline run: ranked prospects + artefacts, behind the gate."""

    prospects: list[Prospect]
    themes: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    prompts: dict[str, str] = field(default_factory=dict)
    sites: dict[str, str] = field(default_factory=dict)
    status: str = "PENDING_APPROVAL"

    def approve(self) -> None:
        self.status = "APPROVED"

    def reject(self) -> None:
        self.status = "REJECTED"

    def _require_approved(self, action: str) -> None:
        if self.status != "APPROVED":
            raise PipelineGateError(
                f"{action} is blocked: pipeline is {self.status}; "
                "the owner must approve() this run first")

    def contact_sheet(self) -> list[dict[str, str]]:
        """Internal contact sheet (data only — this never sends anything)."""
        return [{"name": p.name, "phone": p.phone, "area": p.area,
                 "category": p.category, "score": str(prospect_score(p))}
                for p in self.prospects]

    def contact_plan(self) -> str:
        """A *document* describing proposed outreach — gated, never sent."""
        self._require_approved("contact_plan")
        lines = ["Proposed outreach (owner executes manually; nothing auto-sent):"]
        lines += [f"- {p.name} ({p.area}): starter site ready, pitch = praised themes "
                  f"{', '.join(self.themes.get(_slug(p.name), {}).get('praise', [])) or 'quality'}"
                  for p in self.prospects]
        return "\n".join(lines)

    def publish(self, slug: str) -> str:
        """Return a site for publishing — gated; the caller does any upload."""
        self._require_approved("publish")
        if slug not in self.sites:
            raise KeyError(f"no starter site for {slug!r}")
        return self.sites[slug]


def run_pipeline(prospects: list[Prospect], *, min_score: float = 0.3) -> PipelineRun:
    """Rank prospects, mine reviews, generate prompts + starter sites.

    Ends PENDING_APPROVAL by construction — see the module docstring.
    """
    ranked = sorted((p for p in prospects if prospect_score(p) >= min_score),
                    key=prospect_score, reverse=True)
    run = PipelineRun(prospects=ranked)
    for p in ranked:
        slug = _slug(p.name)
        themes = mine_review_themes(p.reviews)
        run.themes[slug] = themes
        run.prompts[slug] = build_site_prompt(p, themes)
        run.sites[slug] = render_starter_site(p, themes)
    return run


__all__ = ["PipelineGateError", "PipelineRun", "Prospect", "build_site_prompt",
           "mine_review_themes", "prospect_score", "render_starter_site",
           "run_pipeline"]
