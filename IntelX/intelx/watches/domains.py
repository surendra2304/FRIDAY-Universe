"""Topic domains for IntelX standing watches — TASK-INT-013.

Owner decision 2026-11-18: IntelX researches EVERYTHING the Universe works
in, not only trading. A *domain* is the unit of that widening: every watch
belongs to exactly one domain, domains are the subscription unit for the
Universe intel feed (TASK-INT-014), and a new research area joins by adding
one DomainSpec here plus its watches — never by editing the engine.

This module is data + pure helpers, standard-library only, like the engine
it describes. It deliberately does NOT import the engine at module level:
helpers take the watch registry as an argument so the engine can stay the
single owner of watch definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from intelx.watches.engine import WatchDefinition


@dataclass(frozen=True)
class DomainSpec:
    id: str
    title: str
    description: str
    # Why the Universe cares, in one line — the same discipline as
    # WatchDefinition.owner_value, one level up.
    universe_value: str


DOMAINS: dict[str, DomainSpec] = {
    spec.id: spec
    for spec in (
        DomainSpec(
            id="markets",
            title="Markets & trading structure",
            description=(
                "Exchange structure, ETF and listing decisions, leverage and "
                "margin rules, stablecoin and market regulation."
            ),
            universe_value=(
                "Stratex trades on this ground; Futuris forecasts market "
                "series from it."
            ),
        ),
        DomainSpec(
            id="ai_models",
            title="AI models & APIs",
            description=(
                "Frontier model releases, API changes, pricing and "
                "open-weights drops from the providers the fleet routes to."
            ),
            universe_value=(
                "FRIDAY and Inference run on these models; a release can "
                "change what the fleet should route to the day it ships."
            ),
        ),
        DomainSpec(
            id="india_regulatory",
            title="India tech & regulatory",
            description=(
                "DPDP rules, MeitY/RBI/SEBI/TRAI actions, UPI and payments "
                "structure, app bans and takedowns."
            ),
            universe_value=(
                "The owner is India-based; these rules land directly on his "
                "projects, accounts and compliance surface."
            ),
        ),
        DomainSpec(
            id="platforms_policy",
            title="Creator-platform policy & monetisation",
            description=(
                "YouTube / Meta / Instagram partner-programme, monetisation, "
                "recommendation, community-guideline and copyright-policy "
                "changes."
            ),
            universe_value=(
                "VyralX publishes on these platforms; a policy change decides "
                "what she may post and whether it earns."
            ),
        ),
        DomainSpec(
            id="tools_infra",
            title="Fleet tools & infrastructure",
            description=(
                "The stack the agents run on: CPython releases and security "
                "fixes, GitHub platform changes and deprecations, core "
                "dependency advisories."
            ),
            universe_value=(
                "Every agent is Python on GitHub; a security release or a "
                "platform deprecation is fleet maintenance news, not trivia."
            ),
        ),
        DomainSpec(
            id="world_events",
            title="World events with fleet impact",
            description=(
                "Internet and cloud outages, cable cuts, major cyber events, "
                "disasters and escalations with infrastructure blast radius."
            ),
            universe_value=(
                "The fleet is two small cloud VMs and one owner connection; "
                "events that can take infrastructure down are worth one "
                "alert, general world news is not."
            ),
        ),
        DomainSpec(
            id="general",
            title="General research",
            description=(
                "Anything a watch has not yet been classified into. A watch "
                "sitting in this domain is a classification debt, not a "
                "destination."
            ),
            universe_value=(
                "Fallback only; TASK-INT-013's tests require every shipped "
                "watch to declare a real domain."
            ),
        ),
    )
}


def watches_in_domain(
    domain: str, watches: dict[str, "WatchDefinition"]
) -> list["WatchDefinition"]:
    """All watches declared in ``domain``, in registry order."""
    return [w for w in watches.values() if w.domain == domain]


def domains_in_use(watches: dict[str, "WatchDefinition"]) -> list[str]:
    """Domain ids that at least one watch is declared in, registry order."""
    used = {w.domain for w in watches.values()}
    return [d for d in DOMAINS if d in used]


def validate_watch_domains(watches: dict[str, "WatchDefinition"]) -> list[str]:
    """Problems with the registry's domain declarations; empty means sound.

    A watch pointing at an unregistered domain is a configuration error the
    feed (TASK-INT-014) would silently misroute, so it is named here rather
    than discovered downstream.
    """
    problems: list[str] = []
    for watch in watches.values():
        if watch.domain not in DOMAINS:
            problems.append(
                f"watch {watch.id!r} declares unregistered domain {watch.domain!r}"
            )
    return problems
