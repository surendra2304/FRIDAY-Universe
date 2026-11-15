"""TASK-IG-FRG-04: sketch-to-prompt front end (M3E Canvas pattern).

Corpus source: DejpO6SgeTK (M3E Canvas; card verdict: adopt).
Pinned properties: the prompt is deterministic and complete (every
screen, component and flow named); structural defects fail closed
with every problem named; unknown component types are kept but
surfaced as named warnings, never silently normalised.
"""
from __future__ import annotations

import pytest

from app.planning.sketch_prompt import parse_sketch, sketch_to_prompt

SKETCH = {
    "app_name": "Kirana List",
    "screens": [
        {
            "id": "home",
            "name": "Home",
            "components": [
                {"type": "app_bar", "label": "Kirana List"},
                {"type": "list", "label": "Shopping items"},
                {"type": "fab", "label": "Add item"},
            ],
            "links": [{"to": "add", "trigger": "tap the Add item button"}],
        },
        {
            "id": "add",
            "name": "Add Item",
            "components": [
                {"type": "text_field", "label": "Item name"},
                {"type": "button", "label": "Save"},
            ],
            "links": [{"to": "home", "trigger": "tap Save"}],
        },
    ],
}


def test_parse_valid_sketch():
    brief = parse_sketch(SKETCH)
    assert brief.app_name == "Kirana List"
    assert [s.id for s in brief.screens] == ["home", "add"]
    assert brief.warnings == []


def test_flows_resolve_to_screen_names():
    brief = parse_sketch(SKETCH)
    flows = brief.flows()
    assert "Home --tap the Add item button--> Add Item" in flows
    assert "Add Item --tap Save--> Home" in flows


def test_prompt_is_complete_and_deterministic():
    prompt_a = sketch_to_prompt(SKETCH)
    prompt_b = sketch_to_prompt(SKETCH)
    assert prompt_a == prompt_b
    for needle in [
        "Kirana List",
        "Home",
        "Add Item",
        "app_bar",
        "Shopping items",
        "tap Save",
        "one page per screen",
    ]:
        assert needle in prompt_a


def test_unknown_component_type_warns_but_is_kept():
    sketch = {
        "app_name": "X",
        "screens": [
            {
                "id": "s1",
                "name": "Main",
                "components": [{"type": "hologram", "label": "Holo"}],
            }
        ],
    }
    brief = parse_sketch(sketch)
    assert brief.screens[0].components[0].type == "hologram"
    assert any("hologram" in w for w in brief.warnings)
    assert "Sketch warnings" in brief.to_prompt()


def test_dangling_link_fails_closed():
    sketch = {
        "app_name": "X",
        "screens": [
            {"id": "s1", "name": "Main", "links": [{"to": "ghost"}]}
        ],
    }
    with pytest.raises(ValueError) as exc:
        parse_sketch(sketch)
    assert "ghost" in str(exc.value)


def test_duplicate_screen_id_fails_closed():
    sketch = {
        "app_name": "X",
        "screens": [
            {"id": "s1", "name": "One"},
            {"id": "s1", "name": "Two"},
        ],
    }
    with pytest.raises(ValueError) as exc:
        parse_sketch(sketch)
    assert "duplicate screen id: s1" in str(exc.value)


def test_empty_sketch_names_all_problems():
    with pytest.raises(ValueError) as exc:
        parse_sketch({})
    message = str(exc.value)
    assert "app_name" in message
    assert "screens" in message


def test_screen_without_components_prompts_honestly():
    sketch = {"app_name": "X", "screens": [{"id": "s1", "name": "Blank"}]}
    prompt = sketch_to_prompt(sketch)
    assert "no components sketched" in prompt
