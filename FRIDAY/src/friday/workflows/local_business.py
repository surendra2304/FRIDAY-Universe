"""Local-business website + appointment-agent patterns (IG F-30 / F-35).

IG implementation wave, FRIDAY lane (Cluster C) — two buildable patterns
from the full-watch lane package, implemented as FRIDAY features:

* **F-30 — local-business website generation.** Prospect local businesses
  (the video used Google Maps) that have *good reviews but a poor or no
  website* — the worked example on screen was a restaurant at 4.7 stars
  with 206 reviews — then generate a premium website for the business
  with an AI coding agent driven by a structured generation prompt.
* **F-35 — appointment-agent prompt generation.** Pick a niche, open a
  business's website, copy its *services* section, and generate a system
  prompt for an appointment-booking agent from that services text (the
  video pasted it into an LLM and imported the result into a voice-agent
  platform).

Provenance, stated honestly:

* The F-30 prompt was recovered **only in part**: the on-screen prompt's
  TAIL (its performance/design requirements) was read verbatim; its head
  was never recovered in any frame. ``RECOVERED_PROMPT_TAIL`` below is
  that recovered tail. Everything else in the generated site prompt —
  the structure, the business brief, the section list — is **FRIDAY's
  own construction**, written for this module, and is never presented
  as the video's text.
* The F-35 ("Riley") prompt's own text was **never recovered** — only
  the method was. ``build_appointment_agent_prompt`` implements the
  method with FRIDAY's own prompt text.
* Both videos were framed as earnings hustles ("earn 3-5k in 1 hour",
  "$273/day"). Those claims are **not adopted**. What is implemented is
  the working pattern: qualification criteria + prompt generation.

Hard boundaries, enforced in code:

* **Generation only.** This module qualifies prospects and builds
  prompts. It does not scrape Maps, fetch websites, contact businesses,
  or deploy anything — there is no network or outreach surface here.
  The deliverable is the prompt text (and the qualification verdict),
  for the owner to use or discard.
* **No invented facts.** The appointment prompt embeds only the
  services text it is given and instructs the agent to never invent
  services or prices beyond it; with no services text it refuses
  (``LocalBusinessError``) rather than emitting a hollow prompt.

Stdlib only — no new dependencies, Python 3.10.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# FRIDAY's operationalisation of F-30's "good reviews": the video gives
# one worked example (4.7 stars / 206 reviews), not thresholds. These
# defaults are ours, chosen so the worked example qualifies comfortably
# while a thin or mediocre profile does not.
MIN_RATING = 4.3
MIN_REVIEWS = 100

WEBSITE_STATES = ("none", "poor", "good", "unknown")
_FOOD_CATEGORIES = {"restaurant", "cafe", "coffee", "bakery", "food", "dhaba", "hotel-restaurant"}


class LocalBusinessError(ValueError):
    """Raised when a local-business pattern cannot run honestly."""


@dataclass
class Prospect:
    """One local business being considered for the F-30 pattern."""

    name: str
    category: str = ""
    rating: float | None = None
    reviews: int | None = None
    website_state: str = "unknown"  # one of WEBSITE_STATES


@dataclass
class Qualification:
    name: str
    verdict: str  # qualified | reviews_only | website_gap_only | not_qualified | insufficient_data
    score: int
    reasons: list[str] = field(default_factory=list)


def qualify_prospect(prospect: Prospect) -> Qualification:
    """Score one prospect against the F-30 criteria.

    Qualified = good reviews (rating/reviews at or above the module
    thresholds) AND a website gap (no website, or a poor one). Missing
    review data is reported as ``insufficient_data`` — never guessed.
    """
    reasons: list[str] = []
    if prospect.website_state not in WEBSITE_STATES:
        raise LocalBusinessError(
            f"website_state must be one of {WEBSITE_STATES}, got {prospect.website_state!r}"
        )
    if prospect.rating is None or prospect.reviews is None:
        return Qualification(
            name=prospect.name,
            verdict="insufficient_data",
            score=0,
            reasons=["rating/review count not provided — the F-30 criteria cannot be judged"],
        )

    score = 0
    good_reviews = prospect.rating >= MIN_RATING and prospect.reviews >= MIN_REVIEWS
    if prospect.rating >= MIN_RATING:
        score += 25
        reasons.append(f"rating {prospect.rating} ≥ {MIN_RATING}")
    else:
        reasons.append(f"rating {prospect.rating} < {MIN_RATING} — reviews are not 'good' by the F-30 bar")
    if prospect.reviews >= MIN_REVIEWS:
        score += 25
        reasons.append(f"{prospect.reviews} reviews ≥ {MIN_REVIEWS}")
    else:
        reasons.append(f"only {prospect.reviews} reviews (< {MIN_REVIEWS}) — too thin to prove demand")

    website_gap = prospect.website_state in ("none", "poor")
    if prospect.website_state == "none":
        score += 50
        reasons.append("no website at all — the full F-30 gap")
    elif prospect.website_state == "poor":
        score += 40
        reasons.append("website exists but is poor — the F-30 gap")
    elif prospect.website_state == "good":
        reasons.append("website is already good — no gap to fill")
    else:
        reasons.append("website state unknown — the gap is unproven")

    if good_reviews and website_gap:
        verdict = "qualified"
    elif good_reviews:
        verdict = "reviews_only"
    elif website_gap:
        verdict = "website_gap_only"
    else:
        verdict = "not_qualified"
    return Qualification(name=prospect.name, verdict=verdict, score=score, reasons=reasons)


# The F-30 prompt TAIL, as recovered from the on-screen prompt (lane
# package F-30). These requirement lines — and only these — are the
# video's; the prompt's head was never recovered.
RECOVERED_PROMPT_TAIL: tuple[str, ...] = (
    "Lazy-load images.",
    "Use modern image formats.",
    "Minimize animations on mobile.",
    "Ensure fast loading on slow networks.",
    "Design: modern, clean, premium, minimal — strong food visuals, no clutter.",
)
# The tail's end goal, as recovered — specific to the video's restaurant
# demo, so it is applied to food businesses and adapted (and marked as
# adapted) for other categories.
RECOVERED_END_GOAL_FOOD = (
    "End goal: a high-converting site positioning the restaurant as the "
    "most trusted 24h dining destination."
)


def build_site_generation_prompt(
    business_name: str,
    category: str = "",
    services_text: str = "",
    location: str = "",
) -> str:
    """Build FRIDAY's website-generation prompt for one business (F-30).

    The brief and section structure are FRIDAY's own construction; the
    requirements block at the end is the recovered prompt tail, included
    verbatim under its own header so the two are never confused.
    """
    name = (business_name or "").strip()
    if not name:
        raise LocalBusinessError("build_site_generation_prompt needs a business name.")
    cat = (category or "").strip().lower()
    is_food = cat in _FOOD_CATEGORIES
    lines = [
        f"Build a premium website for {name}" + (f", a {category.strip()} business" if category.strip() else "")
        + (f" in {location.strip()}" if location.strip() else "") + ".",
        "",
        "This prompt's structure is FRIDAY's own; the requirements block at",
        "the end is quoted verbatim from a reference prompt (see provenance).",
        "",
        "Sections to build:",
        "- Hero: the business name, what it does, one clear call to action.",
        "- About: a short, honest introduction — no invented history or awards.",
        "- Services / menu: exactly the offerings listed in the brief below; invent nothing.",
        "- Gallery: real photos where provided; clearly-marked placeholders otherwise.",
        "- Reviews: a section ready for the business's genuine customer reviews.",
        "- Visit us: address, hours and contact details as given in the brief.",
        "",
        "Business brief:",
        f"- Name: {name}",
    ]
    if category.strip():
        lines.append(f"- Category: {category.strip()}")
    if location.strip():
        lines.append(f"- Location: {location.strip()}")
    if services_text.strip():
        lines += ["- Services / offerings (verbatim from the business):", services_text.strip()]
    else:
        lines.append("- Services / offerings: not provided — use clearly-marked placeholders.")
    lines += ["", "Requirements (verbatim from the reference prompt's recovered tail):"]
    for item in RECOVERED_PROMPT_TAIL:
        if not is_food and "food visuals" in item:
            lines.append(
                "- Design: modern, clean, premium, minimal — strong visuals of the "
                "business's own work, no clutter. [adapted from the recovered tail, "
                "which was written for a restaurant]"
            )
        else:
            lines.append(f"- {item}")
    if is_food:
        lines.append(f"- {RECOVERED_END_GOAL_FOOD}")
    else:
        lines.append(
            "- End goal: a high-converting site positioning the business as the "
            "most trusted choice in its area. [FRIDAY's adaptation of the "
            "recovered tail's end goal]"
        )
    return "\n".join(lines)


def build_appointment_agent_prompt(
    business_name: str,
    services_text: str,
    niche: str = "",
) -> str:
    """Generate an appointment-booking agent's system prompt (F-35 method).

    The method: take the services text from the business's own site and
    generate the agent's system prompt from it. The generated text is
    FRIDAY's own — the video's "Riley" prompt was never recovered.
    Refuses without services text: the services are the substance of
    the prompt, and inventing them would make the agent lie to callers.
    """
    name = (business_name or "").strip()
    services = (services_text or "").strip()
    if not name:
        raise LocalBusinessError("build_appointment_agent_prompt needs a business name.")
    if not services:
        raise LocalBusinessError(
            "build_appointment_agent_prompt needs the business's services text "
            "(copied from its own website, per the F-35 method) — without it "
            "the agent would have to invent services."
        )
    lines = [
        f"You are the appointment-booking assistant for {name}"
        + (f", a {niche.strip()} business" if niche.strip() else "") + ".",
        "",
        "Your one job: help callers book appointments for the services below.",
        "",
        "Services (from the business's own website — offer exactly these):",
        services,
        "",
        "How you work:",
        "- Greet the caller, ask which service they want, and offer the services above by name.",
        "- Collect the caller's name, a contact number, and a preferred date and time.",
        "- Repeat the booking details back and confirm them before ending the conversation.",
        "- Never invent services, prices, timings or policies that are not in the services text above.",
        "- If a caller asks for something outside the services above, say honestly that you "
        "cannot help with that and offer to pass a message to the business.",
        "- Keep answers short and warm; you are a booking assistant, not a salesperson.",
    ]
    return "\n".join(lines)
