"""VyralX website-to-showreel prompt recipe (IG General cluster C2B-02).

The IG General-section read surfaced a complete prompt recipe
(@koffeewithkishan, reel Ddyj7HUJ8p5, shared 2026-09-30): paste a
website link into a high-effort LLM tool session with a spelled-out
prompt, and the session produces a dynamic 45-second motion-graphics
showreel for the site, with professional voiceover and production
music; best results when the session is connected to the project's
git/terminal.

This module stores that recipe as a parameterised production asset
(``app/data/showreel_recipe.json``) and emits *prompt packs* for a
target site: the filled prompt (the source prompt with its slots
substituted), the session checklist the recipe requires, and a
structured production spec (beat timings scaled from the asset's
structure shares) that a session or the pipeline can plan against.

Honest capability boundary: the render itself happens inside the
operator-run LLM tool session. This module adds the reusable recipe
and the emission helper only -- it does NOT add an on-fleet
video-rendering capability, makes no model call, no network call,
and has no render/upload/send surface. Any showreel produced with
the recipe enters VyralX's normal production pipeline and must
pass the five quality gates before any upload consideration.

Pure data + validation; Python 3.10.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REGISTRY_VERSION = "ig-general-c2b02-1"
_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "showreel_recipe.json"
DEFAULT_RECIPE_ID = "website_showreel"

_SLOT_NAMES = ("site_url", "brand_identity", "duration_seconds",
               "voiceover_style", "music_mood")
_MIN_SECONDS = 10
_MAX_SECONDS = 180
_MAX_TEXT_SLOT_CHARS = 200


def load_registry() -> dict[str, Any]:
    """Load the showreel recipe registry asset."""
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_recipe(recipe: dict[str, Any]) -> list[str]:
    """Structural problems with one recipe ([] = valid)."""
    problems: list[str] = []
    for field in ("id", "name", "ig_sources", "source", "prompt_template",
                  "brand_clause_template", "slots", "session_requirements",
                  "structure", "hard_rules", "honest_boundary",
                  "post_production"):
        if field not in recipe:
            problems.append(f"missing field: {field}")
    if problems:
        return problems

    source = recipe["source"]
    for field in ("cluster", "thread_fbid", "reel_url", "verbatim_prompt"):
        if not source.get(field):
            problems.append(f"missing source field: {field}")

    slot_names = [slot.get("name") for slot in recipe["slots"]]
    if sorted(slot_names) != sorted(_SLOT_NAMES):
        problems.append(f"slots must be exactly {_SLOT_NAMES}, got {slot_names}")
    for slot in recipe["slots"]:
        if slot["name"] == "site_url" and not slot.get("required"):
            problems.append("site_url must be a required slot")

    template = recipe["prompt_template"]
    for placeholder in ("site_url", "duration_seconds", "voiceover_style",
                        "music_mood"):
        if "{" + placeholder + "}" not in template:
            problems.append(f"prompt_template lacks slot: {placeholder}")
    if "{brand_identity}" not in recipe["brand_clause_template"]:
        problems.append("brand_clause_template lacks slot: brand_identity")

    total_share = sum(float(beat["share"]) for beat in recipe["structure"])
    if abs(total_share - 1.0) > 1e-6:
        problems.append(f"structure shares sum to {total_share}, not 1.0")
    return problems


def get_recipe(recipe_id: str = DEFAULT_RECIPE_ID) -> dict[str, Any]:
    """Return one validated recipe by id (ValueError if absent/invalid)."""
    registry = load_registry()
    if registry.get("registry_version") != REGISTRY_VERSION:
        raise ValueError(
            f"registry_version mismatch: {registry.get('registry_version')!r}")
    for recipe in registry.get("recipes", []):
        if recipe.get("id") == recipe_id:
            problems = validate_recipe(recipe)
            if problems:
                raise ValueError(f"recipe {recipe_id} invalid: {problems}")
            return recipe
    raise ValueError(f"unknown recipe id: {recipe_id}")


def _clean_text_slot(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{name} must not be empty")
    if len(cleaned) > _MAX_TEXT_SLOT_CHARS:
        raise ValueError(f"{name} exceeds {_MAX_TEXT_SLOT_CHARS} characters")
    return cleaned


def _clean_inputs(recipe: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    """Merge caller inputs over the recipe defaults; validate (fail closed)."""
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be a dict of slot values")
    unknown = sorted(set(inputs) - set(_SLOT_NAMES))
    if unknown:
        raise ValueError(f"unknown slots: {unknown}")

    defaults = {slot["name"]: slot.get("default") for slot in recipe["slots"]}
    merged = {**defaults, **inputs}

    site_url = merged.get("site_url")
    if site_url is None:
        raise ValueError("site_url is required")
    site_url = _clean_text_slot("site_url", site_url)
    parsed = urlparse(site_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"site_url must be an http(s) URL: {site_url!r}")
    merged["site_url"] = site_url

    duration = merged.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ValueError("duration_seconds must be a number")
    if not (_MIN_SECONDS <= duration <= _MAX_SECONDS):
        raise ValueError(
            f"duration_seconds must be within [{_MIN_SECONDS}, {_MAX_SECONDS}]")
    merged["duration_seconds"] = int(duration) if float(duration).is_integer() \
        else duration

    for name in ("voiceover_style", "music_mood"):
        merged[name] = _clean_text_slot(name, merged.get(name))
    brand = merged.get("brand_identity")
    merged["brand_identity"] = None if brand is None \
        else _clean_text_slot("brand_identity", brand)
    return merged


def fill_prompt(recipe: dict[str, Any], inputs: dict[str, Any]) -> str:
    """Fill the recipe's prompt template with validated slot values.

    Filling with the source recipe's own values (site_url =
    '<add the link>', 45 seconds, 'professional', 'high production',
    no brand identity) reproduces the source prompt verbatim.
    """
    cleaned = _clean_inputs(recipe, inputs)
    prompt = recipe["prompt_template"].format(**cleaned)
    if cleaned["brand_identity"] is not None:
        clause = recipe["brand_clause_template"].format(**cleaned)
        joiner = " " if prompt.endswith((".", "!", "?")) else ". "
        prompt = f"{prompt}{joiner}{clause}"
    return prompt


def _beat_plan(recipe: dict[str, Any], duration_seconds: float) -> list[dict[str, Any]]:
    """Scale the asset's structure shares into per-beat second timings."""
    beats: list[dict[str, Any]] = []
    for beat in recipe["structure"]:
        beats.append({"beat": beat["beat"], "share": beat["share"],
                      "seconds": round(beat["share"] * duration_seconds, 1),
                      "note": beat["note"]})
    residual = round(duration_seconds - sum(b["seconds"] for b in beats), 1)
    if beats and residual:
        beats[-1]["seconds"] = round(beats[-1]["seconds"] + residual, 1)
    return beats


def build_prompt_pack(inputs: dict[str, Any],
                      recipe_id: str = DEFAULT_RECIPE_ID) -> dict[str, Any]:
    """Emit the complete prompt pack for a target site.

    The pack is the recipe's deliverable: a ready-to-run filled
    prompt, the session checklist, a structured production spec,
    and the hard rules / honest boundary that travel with it.
    """
    recipe = get_recipe(recipe_id)
    cleaned = _clean_inputs(recipe, inputs)
    duration = cleaned["duration_seconds"]
    return {
        "recipe_id": recipe["id"],
        "registry_version": REGISTRY_VERSION,
        "source_cluster": recipe["source"]["cluster"],
        "inputs": cleaned,
        "prompt": fill_prompt(recipe, cleaned),
        "session_checklist": list(recipe["session_requirements"]),
        "production_spec": {
            "format": "motion-graphics showreel video",
            "target_site": cleaned["site_url"],
            "duration_seconds": duration,
            "beats": _beat_plan(recipe, duration),
            "voiceover_style": cleaned["voiceover_style"],
            "music_mood": cleaned["music_mood"],
            "brand_identity": cleaned["brand_identity"],
        },
        "hard_rules": list(recipe["hard_rules"]),
        "honest_boundary": recipe["honest_boundary"],
        "post_production": recipe["post_production"],
    }


def prompt_pack_markdown(pack: dict[str, Any]) -> str:
    """Render an emitted prompt pack as a human-readable document."""
    spec = pack["production_spec"]
    lines = [
        f"# Showreel prompt pack — {pack['recipe_id']}",
        "",
        f"- Recipe registry: {pack['registry_version']} "
        f"(source cluster {pack['source_cluster']})",
        f"- Target site: {spec['target_site']}",
        f"- Duration: {spec['duration_seconds']} seconds",
        f"- Voiceover: {spec['voiceover_style']}",
        f"- Music: {spec['music_mood']}",
        f"- Brand identity: {spec['brand_identity'] or '(from the site itself)'}",
        "",
        "## Prompt (paste into the LLM tool session)",
        "",
        pack["prompt"],
        "",
        "## Session checklist",
        "",
    ]
    lines += [f"- {item}" for item in pack["session_checklist"]]
    lines += ["", "## Production spec", "",
              "| Beat | Seconds | Share | Note |",
              "|---|---|---|---|"]
    for beat in spec["beats"]:
        lines.append(f"| {beat['beat']} | {beat['seconds']} | "
                     f"{beat['share']} | {beat['note']} |")
    lines += ["", "## Hard rules", ""]
    lines += [f"- {rule}" for rule in pack["hard_rules"]]
    lines += ["", "## Honest boundary", "", pack["honest_boundary"],
              "", "## After production", "", pack["post_production"], ""]
    return "\n".join(lines)
