"""TASK-IG2-VYR-01: the Podcastfy-pattern audio-content lane.

Behaviour pinned here:

* source text becomes an alternating two-host dialogue (explainer /
  questioner) with intro and outro, capped by mode;
* only VyralX lanes and the short/longform modes are accepted;
* TTS planning is FREE paths only — Edge and Gemini pass, paid
  OpenAI/ElevenLabs are rejected by name;
* a dialogue containing finance advice is blocked by the compliance
  screen (money is stories, never advice);
* the job manifest is batch/offline, never a resident service,
  publishes nothing and would stay unlisted.

On clean main every test fails: app.services.audio_content does
not exist.
"""
from __future__ import annotations

import pytest

from app.services import audio_content as ac

SOURCE = (
    "Apollo 11 launched on July 16 1969. The Saturn V was the tallest "
    "rocket ever flown successfully. Armstrong stepped onto the surface "
    "on July 20. The crew splashed down safely four days later."
)


def test_dialogue_alternates_two_hosts_with_intro_and_outro():
    script = ac.build_dialogue_script(SOURCE, "Apollo 11", lane="history")
    speakers = [t["speaker"] for t in script["turns"]]
    assert speakers[0] == "host_b"  # host B opens, host A explains
    assert "Apollo 11" in script["turns"][0]["text"]
    assert set(speakers) == {"host_a", "host_b"}
    for prev, cur in zip(speakers, speakers[1:]):
        assert prev != cur
    assert script["finance_advice_hits"] == []


def test_dialogue_respects_short_mode_turn_cap():
    long_source = " ".join(f"Fact number {i} happened." for i in range(50))
    script = ac.build_dialogue_script(long_source, "Facts", mode="short")
    assert len(script["turns"]) <= ac.MODES["short"]["max_turns"]


def test_unknown_lane_and_mode_rejected():
    with pytest.raises(ac.AudioContentError):
        ac.build_dialogue_script(SOURCE, "X", lane="money_tips")
    with pytest.raises(ac.AudioContentError):
        ac.build_dialogue_script(SOURCE, "X", mode="medium")


def test_empty_source_rejected():
    with pytest.raises(ac.AudioContentError):
        ac.build_dialogue_script("   ", "Nothing")


def test_tts_plan_free_providers_get_distinct_host_voices():
    script = ac.build_dialogue_script(SOURCE, "Apollo 11")
    for provider in ac.FREE_TTS_PROVIDERS:
        segments = ac.plan_tts_segments(script, provider=provider)
        assert len(segments) == len(script["turns"])
        assert all(s["paid"] is False for s in segments)
        voices = {s["speaker"]: s["voice"] for s in segments}
        assert voices["host_a"] != voices["host_b"]


def test_tts_plan_rejects_paid_providers():
    script = ac.build_dialogue_script(SOURCE, "Apollo 11")
    for provider in ac.PAID_TTS_PROVIDERS:
        with pytest.raises(ac.AudioContentError):
            ac.plan_tts_segments(script, provider=provider)


def test_finance_advice_dialogue_is_blocked():
    bad = ("Stocks always go up. You should invest your savings now "
           "for guaranteed returns.")
    with pytest.raises(ac.AudioContentError):
        ac.build_dialogue_script(bad, "Money story", lane="history")


def test_job_manifest_is_batch_offline_and_unlisted():
    job = ac.build_audio_job(SOURCE, "Apollo 11", lane="history")
    assert job["execution"] == "batch_offline"
    assert job["resident_service"] is False
    assert job["publish"] is False
    assert job["privacy_if_published"] == "unlisted"
    assert job["paid_services_used"] is False
    assert job["tts_segments"]
