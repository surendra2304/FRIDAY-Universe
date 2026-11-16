"""TASK-IG2-FRG-06: Forge local-business prospecting + auto-website pipeline.

Pins: scoring favours no-website + proven demand, review mining, escaped
starter sites, and the approval gate (publish/contact-plan blocked until
approved; no outreach-sending surface exists at all).
"""
from __future__ import annotations

import pytest

from forge_upgrade.local_business_pipeline import (
    PipelineGateError, Prospect, build_site_prompt, mine_review_themes,
    prospect_score, render_starter_site, run_pipeline)


def _cafe() -> Prospect:
    return Prospect(name="Sunrise Cafe", category="Cafe", area="Kakinada",
                    phone="+91 90000 00000", rating=4.5, review_count=120,
                    reviews=["Great coffee and friendly staff",
                             "Tasty food, but parking is hard",
                             "Clean, cozy, affordable"])


def test_no_website_high_demand_scores_highest():
    assert prospect_score(_cafe()) == 1.0
    with_site = Prospect(name="Has Site", website="https://example.com",
                         rating=4.5, review_count=120)
    assert prospect_score(with_site) < prospect_score(_cafe())


def test_review_mining_finds_praise_and_complaints():
    themes = mine_review_themes(_cafe().reviews)
    assert "food" in themes["praise"] and "service" in themes["praise"]
    assert themes["complaints"] == ["parking"]


def test_site_prompt_is_review_mined_and_honest():
    prompt = build_site_prompt(_cafe(), mine_review_themes(_cafe().reviews))
    assert "Sunrise Cafe" in prompt and "parking" in prompt
    assert "No invented prices" in prompt


def test_starter_site_escapes_business_data():
    evil = Prospect(name="<script>alert(1)</script>", phone="123")
    site = render_starter_site(evil, {"praise": [], "complaints": []})
    assert "<script>alert(1)</script>" not in site
    assert "&lt;script&gt;" in site


def test_pipeline_ranks_filters_and_stays_pending():
    low = Prospect(name="Tiny", rating=2.0, review_count=0)
    run = run_pipeline([low, _cafe()])
    assert [p.name for p in run.prospects] == ["Sunrise Cafe"]
    assert run.status == "PENDING_APPROVAL"
    assert "sunrise-cafe" in run.sites and "sunrise-cafe" in run.prompts


def test_gate_blocks_publish_and_contact_plan_until_approved():
    run = run_pipeline([_cafe()])
    with pytest.raises(PipelineGateError):
        run.publish("sunrise-cafe")
    with pytest.raises(PipelineGateError):
        run.contact_plan()
    run.approve()
    assert "Sunrise Cafe" in run.publish("sunrise-cafe")
    assert "nothing auto-sent" in run.contact_plan()


def test_contact_sheet_is_data_only():
    run = run_pipeline([_cafe()])
    sheet = run.contact_sheet()
    assert sheet[0]["name"] == "Sunrise Cafe" and sheet[0]["phone"]


def test_module_has_no_outreach_sending_surface():
    import forge_upgrade.local_business_pipeline as mod
    names = [n.lower() for n in dir(mod)]
    assert not any("send" in n or "email" in n or "smtp" in n for n in names)
