"""VyralX Monetization & Revenue Generation Engine.

Automates affiliate marketing, pinned comment conversion catalysts,
sponsorship templates, and revenue tracking across viral Shorts & Reels.
"""
from __future__ import annotations

import logging

log = logging.getLogger("vyralx.monetization")

# High-RPM Niche Affiliate Stack (Configurable in .env or settings)
AFFILIATE_OFFERS_BY_NICHE: dict[str, list[dict[str, str]]] = {
    "WILDLIFE": [
        {
            "product": "Wilderness Binoculars & Safari Optics",
            "url": "https://amzn.to/example-wildlife-optics",
            "cta": "🔭 Get the high-power safari optics featured in the video",
            "commission_type": "Amazon Associates (4-8%)",
        },
        {
            "product": "Ultra-Tough Adventure GoPro Mount Kit",
            "url": "https://amzn.to/example-gopro-mount",
            "cta": "🎥 Best action cam kit for extreme wildlife encounters",
            "commission_type": "Amazon Associates (4-8%)",
        },
    ],
    "LIFEHACKS": [
        {
            "product": "14-in-1 Titanium Bushcraft Multi-Tool",
            "url": "https://amzn.to/example-survival-multitool",
            "cta": "🛠️ The survival multi-tool used in this hack",
            "commission_type": "High-Converting E-commerce (10-15%)",
        },
        {
            "product": "Emergency Solar Water Purifier Kit",
            "url": "https://amzn.to/example-water-purifier",
            "cta": "💧 Portable emergency purifier - 50% OFF today",
            "commission_type": "Direct Brand Affiliate (15-20%)",
        },
    ],
    "COMEDY": [
        {
            "product": "Viral Soundboard & Studio Mic Set",
            "url": "https://amzn.to/example-soundboard",
            "cta": "🎙️ Upgrade your setup with the viral creator mic",
            "commission_type": "Amazon Associates (4-6%)",
        },
        {
            "product": "Trending Meme Merchandise & Apparel",
            "url": "https://creatorstore.example.com",
            "cta": "👕 Grab the exclusive trending drop",
            "commission_type": "Print-on-Demand (30-40% profit)",
        },
    ],
    "SPORTS": [
        {
            "product": "Elite Recovery Muscle Massage Gun",
            "url": "https://amzn.to/example-massage-gun",
            "cta": "⚡ Pro athlete recovery gear - Limited discount",
            "commission_type": "Amazon Associates (6-10%)",
        },
        {
            "product": "Performance Grip Strength & Training Set",
            "url": "https://amzn.to/example-grip-trainer",
            "cta": "💪 Essential grip strength kit used by champions",
            "commission_type": "E-commerce Affiliate (12%)",
        },
    ],
    "VIRAL": [
        {
            "product": "Trending Smart Home & Desk Gadgets",
            "url": "https://amzn.to/example-viral-gadgets",
            "cta": "🔥 Top trending viral gadgets this week",
            "commission_type": "Curated Amazon Storefront (5-10%)",
        },
    ],
}

DEFAULT_OFFERS = [
    {
        "product": "Trending Creator Desk Setup & LED Lights",
        "url": "https://amzn.to/example-creator-gear",
        "cta": "✨ Check out the creator gear shown in this video",
        "commission_type": "Amazon Associates (4-8%)",
    }
]


def generate_monetized_pinned_comment(category: str, engagement_question: str | None = None) -> str:
    """Generate high-CTR pinned comment with debate catalyst and affiliate link."""
    category_key = str(category).upper()
    offers = AFFILIATE_OFFERS_BY_NICHE.get(category_key, DEFAULT_OFFERS)
    selected = offers[0]

    question = engagement_question or "What would you do in this situation? Let us know below! 👇"

    lines = [
        f"📌 {selected['cta']}: {selected['url']}",
        "",
        f"💬 {question}",
        "",
        "🔔 Subscribe to VyralX for daily viral moments & insane stories!",
    ]
    return "\n".join(lines)


def generate_monetized_description(
    title: str,
    category: str,
    original_attribution: str = "",
    business_email: str = "partnerships@vyralx.media",
) -> str:
    """Build high-revenue YouTube description with affiliate links, disclosures, and brand deal contacts."""
    category_key = str(category).upper()
    offers = AFFILIATE_OFFERS_BY_NICHE.get(category_key, DEFAULT_OFFERS)

    sections = [
        f"{title.strip()}",
        "",
        "🔥 FEATURED GEAR & PRODUCTS:",
    ]

    for offer in offers:
        sections.append(f"• {offer['cta']}: {offer['url']}")

    sections.extend([
        "",
        "💼 BRAND DEALS & SPONSORSHIPS:",
        f"Contact our team: {business_email}",
        "",
        "---",
        "⚖️ Fair Use & Attribution Disclaimer:",
        original_attribution or "Curated & remixed for educational, commentary, and transformative entertainment purposes.",
        "Disclosure: Some links above may be affiliate links. At no extra cost to you, we may receive a commission on qualifying purchases.",
        "",
        f"#Shorts #Viral #Trending #{category_key} #fyp",
    ])

    return "\n".join(sections)


# --------------------------------------------------------------------------- #
# TASK-VYR-014: the LIVE description path.
#
# The generate_* functions above predate the viral pipeline and are not
# called by it; their offer links are placeholders and must never ship.
# The live path (viral_remix.produce_viral_short) uses ONLY the
# config-driven footer below: links come from the operator's settings,
# never from constants in code, and the footer is empty until the operator
# configures real links (affiliate accounts are the owner's to open).
# --------------------------------------------------------------------------- #
import json as _json

_AMAZON_HINTS = ("amazon.", "amzn.to", "amzn.in")


def configured_affiliate_links(settings=None) -> list[dict[str, str]]:
    """Parse the operator-configured affiliate/product links.

    Source: settings.affiliate_links_json — a JSON list of
    {"label": ..., "url": ...}. Anything malformed is dropped, never
    raised: a bad config value must not break an upload.
    """
    if settings is None:
        try:
            from app.config import get_settings

            settings = get_settings()
        except Exception:
            return []
    raw = str(getattr(settings, "affiliate_links_json", "") or "").strip()
    if not raw:
        return []
    try:
        parsed = _json.loads(raw)
    except ValueError:
        log.warning("affiliate_links_json is not valid JSON; ignoring")
        return []
    links: list[dict[str, str]] = []
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            if label and url.startswith(("https://", "http://")):
                links.append({"label": label, "url": url})
    return links


def monetization_footer(settings=None) -> str:
    """Description footer carrying the monetization slots.

    Returns "" when nothing is configured, so uploads stay byte-identical
    to the pre-monetization format until the operator fills the slots.

    When links exist, the disclosure block is mandatory and always
    attached: FTC + India ASCI rules require it, and Amazon's Operating
    Agreement requires its exact sentence near affiliate links.
    """
    if settings is None:
        try:
            from app.config import get_settings

            settings = get_settings()
        except Exception:
            return ""
    links = configured_affiliate_links(settings)
    business_email = str(getattr(settings, "business_email", "") or "").strip()

    if not links and not business_email:
        return ""

    lines: list[str] = []
    if links:
        lines.append("🛒 PRODUCTS & GEAR:")
        for link in links:
            lines.append(f"• {link['label']}: {link['url']}")
        lines.append("")
        lines.append(
            "Disclosure: Some links above are affiliate links. If you buy "
            "through them, this channel may earn a commission at no extra "
            "cost to you. #ad"
        )
        if any(any(hint in link["url"] for hint in _AMAZON_HINTS) for link in links):
            lines.append("As an Amazon Associate I earn from qualifying purchases.")
    if business_email:
        if lines:
            lines.append("")
        lines.append(f"💼 Business & sponsorships: {business_email}")
    return "\n".join(lines)
