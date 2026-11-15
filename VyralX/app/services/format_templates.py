"""VyralX content-format template registry (TASK-IG-VYR-09).

The IG reference corpus is full of *formats*: AI short films
(DRZmz6PjG5a, DfCJAl2JnGE), a recurring-character series built on
game characters (DcQ5ZUOhelW), animated explainers (DePlCX-Az0V,
De1VfkaOM_2), Google-Earth flyovers (Db8qrQ2p4dO), ambient
long-form (DenFQo1OXqK). A format is only useful to VyralX once it
is written down as a template the pipeline can plan against — and
only once its hard rules are explicit, because two of the corpus
formats carry traps:

* the character series is built on **game IP** — gameplay and
  third-party characters are compliance-gate exclusions
  (TASK-VYR-009), so the template keeps the recurring-character
  mechanics and mandates ORIGINAL characters;
* Google Earth Studio output is **terms-restricted**, so the
  flyover template sources public-domain aerial/satellite stock
  from the stocked catalogues instead.

This module loads ``app/data/format_templates.json``, validates
every template (required fields, structure shares summing to 1.0,
lanes within the owner's three, and a screen of template text
against the compliance gate's excluded tokens — a template that
invokes an excluded category fails to load), and instantiates a
template into a per-episode format plan with beat timings.

Pure data + validation; no rendering, no network. Python 3.10.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services import compliance_gate

REGISTRY_VERSION = "ig-vyr09-1"
_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "format_templates.json"
_OWNER_LANES = {"space_science", "history", "tech_ai"}


def _screen_text(template: dict[str, Any]) -> str | None:
    """Gate-token screen over a template's descriptive text.

    Same method as the compliance gate itself: casefolded
    substring match against ``EXCLUDED_TOKENS``. The hard_rules
    field is where exclusions are *named as prohibitions*, so the
    screen covers name + source_strategy (what the template says
    to DO), not the rules that forbid.
    """
    text = " ".join([str(template.get("name") or ""),
                     str(template.get("source_strategy") or "")]).casefold()
    for token in compliance_gate.EXCLUDED_TOKENS:
        if token in text:
            return token
    return None


def validate_template(template: dict[str, Any]) -> list[str]:
    """Structural + gate problems with one template ([] = valid)."""
    problems: list[str] = []
    for field in ("id", "name", "lanes", "structure",
                  "source_strategy", "hard_rules", "target_seconds"):
        if field not in template:
            problems.append(f"missing field: {field}")
    if problems:
        return problems
    bad_lanes = set(template["lanes"]) - _OWNER_LANES
    if bad_lanes:
        problems.append(f"lanes outside the owner's three: "
                        f"{sorted(bad_lanes)}")
    shares = [float(b.get("share") or 0) for b in template["structure"]]
    if not shares or abs(sum(shares) - 1.0) > 0.011:
        problems.append(f"structure shares must sum to 1.0 "
                        f"(got {round(sum(shares), 3)})")
    lo, hi = template["target_seconds"]
    if not (0 < lo <= hi):
        problems.append(f"target_seconds range invalid: {template['target_seconds']}")
    token = _screen_text(template)
    if token:
        problems.append(f"template invokes gate-excluded token: {token!r}")
    return problems


def load_templates(path: Path | None = None) -> list[dict[str, Any]]:
    """Load + validate the registry; raises on any invalid entry."""
    data = json.loads(Path(path or _DATA_PATH).read_text(encoding="utf-8"))
    templates = data.get("templates") or []
    problems: list[str] = []
    seen: set[str] = set()
    for template in templates:
        tid = template.get("id", "?")
        if tid in seen:
            problems.append(f"duplicate template id: {tid}")
        seen.add(tid)
        problems.extend(f"{tid}: {p}" for p in validate_template(template))
    if problems:
        raise ValueError("format template registry invalid: "
                         + "; ".join(problems))
    return templates


def get_template(template_id: str,
                 path: Path | None = None) -> dict[str, Any]:
    for template in load_templates(path):
        if template["id"] == template_id:
            return template
    raise ValueError(f"unknown format template: {template_id!r}")


def instantiate(template_id: str, target_seconds: float,
                path: Path | None = None) -> dict[str, Any]:
    """A per-episode format plan: beats with absolute timings."""
    template = get_template(template_id, path)
    lo, hi = template["target_seconds"]
    beats = []
    cursor = 0.0
    structure = template["structure"]
    for i, beat in enumerate(structure):
        if i == len(structure) - 1:
            end = float(target_seconds)
        else:
            end = cursor + float(beat["share"]) * target_seconds
        beats.append({"beat": beat["beat"], "note": beat.get("note", ""),
                      "start": round(cursor, 1), "end": round(end, 1)})
        cursor = end
    return {
        "kind": "format_plan",
        "registry_version": REGISTRY_VERSION,
        "template_id": template_id,
        "template_name": template["name"],
        "target_seconds": target_seconds,
        "within_template_range": lo <= target_seconds <= hi,
        "beats": beats,
        "source_strategy": template["source_strategy"],
        "hard_rules": template["hard_rules"],
        "status": "pending_review",
    }
