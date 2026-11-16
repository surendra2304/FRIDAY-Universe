"""TASK-IG2-VYR-03: the short-video-factory batch pattern.

Behaviour pinned here:

* a job spec carries copy, a free EdgeTTS voice plan, an auto-mix
  plan over provenance-carrying storyboard materials, and timed
  subtitle cues — the upstream factory's chain, headless;
* Shorts are <60s: an over-long narration is rejected, not trimmed;
* materials without licence/provenance are refused;
* finance-advice copy is blocked (money = stories, never advice);
* fill_batch keeps producing until the preset queue target is met;
* jobs render/publish nothing and stay unlisted.

On clean main every test fails: app.services.shorts_factory does
not exist.
"""
from __future__ import annotations

import pytest

from app.services import shorts_factory as sf

MATERIALS = [{
    "catalog_id": "L1-001", "title": "Apollo footage",
    "license_name": "Public Domain",
    "page_url": "https://images.nasa.gov/details/1",
}]
FACTS = ["Apollo 11 launched in July 1969.",
         "Armstrong stepped out on July 20."]


def test_job_spec_has_full_factory_chain():
    job = sf.build_job("Apollo 11", FACTS, MATERIALS, lane="history")
    assert job["format"] == "shorts"
    assert (job["width"], job["height"]) == (1080, 1920)
    assert job["estimated_seconds"] < 60
    assert job["voice_plan"]["provider"] == "edge"
    assert job["voice_plan"]["paid"] is False
    assert job["mix_plan"]["segments"][0]["material"] == "L1-001"
    assert job["mix_plan"]["segments"][0]["license_name"] == "Public Domain"
    assert job["subtitle_cues"], "subtitle cues must be generated"
    assert job["publish"] is False
    assert job["privacy_if_published"] == "unlisted"


def test_overlong_narration_rejected_not_trimmed():
    long_facts = [" ".join(["word"] * 200) + "."]
    with pytest.raises(sf.ShortsFactoryError):
        sf.build_job("Too long", long_facts, MATERIALS)


def test_materials_require_provenance():
    with pytest.raises(sf.ShortsFactoryError):
        sf.build_job("Apollo 11", FACTS, [{"title": "mystery clip"}])
    with pytest.raises(sf.ShortsFactoryError):
        sf.build_job("Apollo 11", FACTS, [])


def test_unknown_lane_rejected():
    with pytest.raises(sf.ShortsFactoryError):
        sf.build_job("Tips", FACTS, MATERIALS, lane="money_tips")


def test_finance_advice_copy_blocked():
    with pytest.raises(sf.ShortsFactoryError):
        sf.build_job("Money", ["You should invest now for guaranteed "
                               "returns."], MATERIALS, lane="history")


def test_fill_batch_reaches_preset_target():
    batch = sf.fill_batch(
        [{"topic": "Apollo 11", "facts": FACTS, "materials": MATERIALS,
          "lane": "history"}],
        target_count=5)
    assert batch["job_count"] == 5
    assert batch["all_planned"] is True
    hooks = {j["copy"]["hook"] for j in batch["jobs"]}
    assert len(hooks) > 1, "cycled passes should vary the hook"


def test_fill_batch_validates_inputs():
    with pytest.raises(sf.ShortsFactoryError):
        sf.fill_batch([], target_count=3)
    with pytest.raises(sf.ShortsFactoryError):
        sf.fill_batch(
            [{"topic": "X", "facts": FACTS, "materials": MATERIALS}],
            target_count=0)
