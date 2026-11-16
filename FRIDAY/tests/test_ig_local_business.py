"""IG implementation wave (FRIDAY lane, Cluster C) — F-30 / F-35 tests.

Covers the local-business pattern module, its tool wrapper, and — per
the AUDIT-2 wiring lesson — a production-path registry test that fails
if the ``local_business`` registration is removed from
``agent/mixins/tools.py``.
"""
import pytest

from friday.tools.builtin.local_business_tools import LocalBusinessTool
from friday.workflows.local_business import (
    RECOVERED_PROMPT_TAIL,
    LocalBusinessError,
    Prospect,
    build_appointment_agent_prompt,
    build_site_generation_prompt,
    qualify_prospect,
)


# — F-30 qualification ————————————————————————————————————————————————

def test_worked_example_qualifies():
    # The video's worked example (lane package F-30): 4.7 stars, 206
    # reviews, poor website.
    q = qualify_prospect(Prospect(name="Sri Bhavani restaurant", category="restaurant",
                                  rating=4.7, reviews=206, website_state="poor"))
    assert q.verdict == "qualified"
    assert q.score == 90


def test_no_website_is_the_full_gap():
    q = qualify_prospect(Prospect(name="Cafe", rating=4.9, reviews=500, website_state="none"))
    assert q.verdict == "qualified"
    assert q.score == 100


def test_good_website_blocks_qualification():
    q = qualify_prospect(Prospect(name="Cafe", rating=4.9, reviews=500, website_state="good"))
    assert q.verdict == "reviews_only"


def test_thin_reviews_do_not_qualify():
    q = qualify_prospect(Prospect(name="Cafe", rating=4.9, reviews=12, website_state="none"))
    assert q.verdict == "website_gap_only"


def test_missing_review_data_is_insufficient_not_guessed():
    q = qualify_prospect(Prospect(name="Cafe", website_state="none"))
    assert q.verdict == "insufficient_data"
    assert q.score == 0


def test_bad_website_state_is_refused():
    with pytest.raises(LocalBusinessError):
        qualify_prospect(Prospect(name="Cafe", rating=5.0, reviews=10, website_state="shiny"))


# — F-30 site prompt ——————————————————————————————————————————————————

def test_site_prompt_carries_the_recovered_tail_verbatim():
    prompt = build_site_generation_prompt("Sri Bhavani restaurant", category="restaurant")
    for line in RECOVERED_PROMPT_TAIL:
        assert line in prompt
    # The tail's restaurant end goal is present for a food business.
    assert "most trusted 24h dining destination" in prompt
    assert "Sri Bhavani restaurant" in prompt


def test_site_prompt_marks_provenance():
    prompt = build_site_generation_prompt("Sri Bhavani restaurant", category="restaurant")
    assert "verbatim from the reference prompt's recovered tail" in prompt
    assert "FRIDAY's own" in prompt


def test_site_prompt_adapts_the_food_line_for_non_food():
    prompt = build_site_generation_prompt("Smile Dental", category="dentist")
    assert "strong food visuals" not in prompt
    assert "adapted from the recovered tail" in prompt
    # The performance requirements are category-independent and stay verbatim.
    assert "Lazy-load images." in prompt
    assert "Ensure fast loading on slow networks." in prompt


def test_site_prompt_needs_a_name():
    with pytest.raises(LocalBusinessError):
        build_site_generation_prompt("  ")


# — F-35 appointment prompt ———————————————————————————————————————————

def test_appointment_prompt_is_built_from_the_services_text():
    services = "Root canal treatment\nDental implants\nTeeth cleaning"
    prompt = build_appointment_agent_prompt("Smile Dental", services, niche="dentist")
    assert "Smile Dental" in prompt
    assert "Root canal treatment" in prompt
    assert "Never invent services" in prompt
    assert "confirm them" in prompt


def test_appointment_prompt_refuses_without_services():
    # The F-35 method's input is the business's own services text; without
    # it the generator must refuse rather than emit a hollow prompt.
    with pytest.raises(LocalBusinessError):
        build_appointment_agent_prompt("Smile Dental", "   ")


# — Tool wrapper ——————————————————————————————————————————————————————

def test_tool_qualify_action():
    res = LocalBusinessTool().execute(
        action="qualify", business_name="Sri Bhavani restaurant",
        rating=4.7, reviews=206, website_state="poor",
    )
    assert not res.is_error
    assert res.metadata["verdict"] == "qualified"


def test_tool_appointment_prompt_refusal_is_honest():
    res = LocalBusinessTool().execute(
        action="appointment_prompt", business_name="Smile Dental", services_text="",
    )
    assert res.is_error and res.refused


def test_tool_unknown_action_is_refused():
    res = LocalBusinessTool().execute(action="teleport", business_name="X")
    assert res.is_error and res.refused


# — Production-path wiring (AUDIT-2 lesson) ———————————————————————————

def test_local_business_is_in_the_live_registry():
    from friday.agent.mixins.tools import ToolExecutionMixin

    class _StubMemory:
        def search(self, *a, **k):
            return []

    agent = ToolExecutionMixin.__new__(ToolExecutionMixin)
    agent.memory = _StubMemory()
    agent.skill_registry = None
    agent.authorizer = None
    agent.llm_provider = None
    agent.provider = None
    registry = agent._create_default_registry()
    tool = registry.get("local_business")
    assert tool is not None, "local_business missing from the production registry"
    assert isinstance(tool, LocalBusinessTool)
