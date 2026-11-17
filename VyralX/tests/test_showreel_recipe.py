"""IG General C2B-02: website-to-showreel prompt recipe asset + helper.

Pins: the registry asset preserves the source recipe's verbatim
prompt; filling the template with the source's own values reproduces
that prompt exactly; a fixture site in yields a complete prompt pack
(filled prompt + session checklist + production spec with beat
timings summing to the duration); invalid inputs fail closed; the
module has no render/upload/send surface (the render happens in an
operator-run LLM tool session, never on the fleet).
On clean main this fails: app.services.showreel_recipe does not exist.
"""
from __future__ import annotations

import pytest

from app.services import showreel_recipe as srr

FIXTURE = {"site_url": "https://example.com/landing"}

VERBATIM_PROMPT = (
    "We are making the video for this website <add the link> make a dynamic "
    "45 second motion graphics video that shows what an incredible motion "
    "designer you are, like it's your showreel for a resume. go all out. "
    "Add professional voiceover and high production music"
)


def test_asset_loads_and_validates():
    registry = srr.load_registry()
    assert registry["registry_version"] == srr.REGISTRY_VERSION
    recipe = srr.get_recipe()
    assert recipe["id"] == "website_showreel"
    assert srr.validate_recipe(recipe) == []
    assert recipe["source"]["cluster"] == "C2B-02"
    assert recipe["source"]["thread_fbid"] == "1122818056813568"
    assert recipe["ig_sources"] == ["Ddyj7HUJ8p5"]


def test_verbatim_source_prompt_preserved():
    recipe = srr.get_recipe()
    assert recipe["source"]["verbatim_prompt"] == VERBATIM_PROMPT


def test_template_reproduces_source_prompt_with_source_values():
    # Template-level substitution with the source recipe's own values
    # (the placeholder text '<add the link>' is not a valid input URL,
    # so this pins template<->verbatim fidelity below the validator).
    recipe = srr.get_recipe()
    filled = recipe["prompt_template"].format(
        site_url="<add the link>", duration_seconds=45,
        voiceover_style="professional", music_mood="high production",
        brand_identity=None)
    assert filled == VERBATIM_PROMPT


def test_defaults_emission_for_fixture_site():
    pack = srr.build_prompt_pack(FIXTURE)
    assert pack["recipe_id"] == "website_showreel"
    assert "https://example.com/landing" in pack["prompt"]
    assert "45 second" in pack["prompt"]
    assert "professional voiceover" in pack["prompt"]
    assert "high production music" in pack["prompt"]
    spec = pack["production_spec"]
    assert spec["duration_seconds"] == 45
    assert spec["target_site"] == "https://example.com/landing"
    assert sum(b["seconds"] for b in spec["beats"]) == 45
    assert pack["session_checklist"] and pack["hard_rules"]
    assert "does NOT add an on-fleet video-rendering capability" \
        in pack["honest_boundary"]


def test_overrides_and_brand_clause():
    pack = srr.build_prompt_pack({
        "site_url": "https://friday-universe.duckdns.org/",
        "duration_seconds": 30,
        "voiceover_style": "confident and warm",
        "music_mood": "cinematic electronic",
        "brand_identity": "dark dashboard, glowing orb core, red/orange glow",
    })
    assert "30 second" in pack["prompt"]
    assert "confident and warm voiceover" in pack["prompt"]
    assert "cinematic electronic music" in pack["prompt"]
    assert pack["prompt"].endswith(
        "Match the site's brand identity throughout: "
        "dark dashboard, glowing orb core, red/orange glow.")
    assert sum(b["seconds"] for b in pack["production_spec"]["beats"]) == 30


def test_invalid_inputs_fail_closed():
    with pytest.raises(ValueError):
        srr.build_prompt_pack({})  # site_url missing
    with pytest.raises(ValueError):
        srr.build_prompt_pack({"site_url": "not a url"})
    with pytest.raises(ValueError):
        srr.build_prompt_pack({"site_url": "ftp://example.com/"})
    with pytest.raises(ValueError):
        srr.build_prompt_pack({**FIXTURE, "duration_seconds": 5})
    with pytest.raises(ValueError):
        srr.build_prompt_pack({**FIXTURE, "duration_seconds": 999})
    with pytest.raises(ValueError):
        srr.build_prompt_pack({**FIXTURE, "unknown_slot": "x"})
    with pytest.raises(ValueError):
        srr.build_prompt_pack({**FIXTURE, "voiceover_style": "  "})


def test_no_render_or_send_surface():
    public = {name for name in dir(srr) if not name.startswith("_")}
    forbidden_verbs = {"render", "upload", "publish", "send", "post"}
    assert not any(name.casefold().split("_")[0] in forbidden_verbs
                   for name in public)
    assert public == {"load_registry", "validate_recipe", "get_recipe",
                      "fill_prompt", "build_prompt_pack",
                      "prompt_pack_markdown", "REGISTRY_VERSION",
                      "DEFAULT_RECIPE_ID", "annotations", "json", "Path",
                      "Any", "urlparse"}


def test_markdown_render_is_complete():
    md = srr.prompt_pack_markdown(srr.build_prompt_pack(FIXTURE))
    assert "https://example.com/landing" in md
    assert "## Prompt" in md and "## Session checklist" in md
    assert "## Production spec" in md and "## Honest boundary" in md
