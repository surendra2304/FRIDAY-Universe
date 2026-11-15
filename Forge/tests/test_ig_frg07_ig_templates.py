"""TASK-IG-FRG-07: build-template pack.

Corpus sources: DZm0KTppMuD (SaaS stack), DeJnEzVpp2o (solo-founder
stack), DfHw7hsIfvd (one-prompt agent), DfMhyC7Ma31 (website from a
brief). Pinned properties: the pack is internally consistent, goals
render completely (every file + env name + step), and the fleet
rules are structural — payments are test-mode, the agent template
declares no direct provider keys.
"""
from __future__ import annotations

import pytest

from app.templates.ig_templates import (
    TEMPLATES,
    get_template,
    list_templates,
    render_goal,
    validate_templates,
)


def test_pack_contents_and_validity():
    assert set(TEMPLATES) == {
        "saas-stack",
        "solo-founder-launch",
        "one-prompt-agent",
        "portfolio-website",
    }
    assert validate_templates() == []
    assert list_templates() == sorted(TEMPLATES.values(), key=lambda t: t.name)


def test_every_template_traces_to_corpus():
    expected = {
        "saas-stack": "DZm0KTppMuD",
        "solo-founder-launch": "DeJnEzVpp2o",
        "one-prompt-agent": "DfHw7hsIfvd",
        "portfolio-website": "DfMhyC7Ma31",
    }
    for name, shortcode in expected.items():
        assert shortcode in get_template(name).source_shortcodes


def test_render_goal_is_complete():
    template = get_template("saas-stack")
    goal = render_goal(template, "InvoiceFox")
    assert "InvoiceFox" in goal
    for path in template.manifest_paths():
        assert path in goal
    for var in template.env_vars:
        assert var in goal
    for step in template.steps:
        assert step in goal


def test_payments_template_is_test_mode_only():
    template = get_template("saas-stack")
    notes = " ".join(template.notes)
    assert "TEST mode" in notes
    goal = render_goal(template, "X")
    assert "TEST mode" in goal


def test_agent_template_uses_inference_not_provider_keys():
    template = get_template("one-prompt-agent")
    assert "INFERENCE_BASE_URL" in template.env_vars
    for forbidden in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        assert forbidden not in template.env_vars


def test_portfolio_template_invents_nothing():
    template = get_template("portfolio-website")
    assert any("must not invent" in n for n in template.notes)


def test_render_goal_requires_project_name():
    with pytest.raises(ValueError):
        render_goal(get_template("saas-stack"), "  ")


def test_unknown_template_raises_with_options():
    with pytest.raises(KeyError) as exc:
        get_template("nope")
    assert "saas-stack" in str(exc.value)
