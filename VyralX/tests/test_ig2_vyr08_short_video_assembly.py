"""TASK-IG2-VYR-08: the MoneyPrinterTurbo-pattern assembly plan.

Behaviour pinned here:

* a script becomes scenes with per-scene footage queries, provider
  fallback chains and cumulative timing;
* the three upstream formats (9:16 / 16:9 / 1:1) map to real shapes;
* a ``short`` estimating >=60s is rejected (Shorts are <60s);
* voiceover is free Edge TTS only — paid providers rejected by name;
* a finance-advice script is blocked by the compliance screen;
* plans are batch/offline, publish nothing, and stay unlisted;
* batch generation de-duplicates topics.

On clean main every test fails: app.services.short_video_assembly
does not exist.
"""
from __future__ import annotations

import pytest

from app.services import short_video_assembly as asm

SCRIPT = (
    "The Saturn V stood taller than a football field. "
    "Its five engines burned for just 150 seconds. "
    "Then the quietest part of the flight began."
)


def test_script_segments_into_timed_scenes_with_queries():
    plan = asm.build_assembly_plan("Saturn V", SCRIPT)
    scenes = plan["scenes"]
    assert len(scenes) == 3
    assert scenes[0]["start_s"] == 0.0
    assert scenes[1]["start_s"] == scenes[0]["duration_s"]
    assert all(s["footage_query"] for s in scenes)
    assert scenes[0]["stock_providers"] == list(asm.STOCK_PROVIDERS)
    assert plan["estimated_seconds"] == round(
        sum(s["duration_s"] for s in scenes), 2)


def test_formats_map_to_upstream_shapes():
    for fmt, aspect in (("vertical", "9:16"), ("landscape", "16:9"),
                        ("square", "1:1")):
        plan = asm.build_assembly_plan("T", SCRIPT, fmt=fmt)
        composite = plan["stages"][-1]
        assert composite["aspect"] == aspect
        assert composite["width"] * (int(aspect.split(":")[1])) == \
            composite["height"] * (int(aspect.split(":")[0]))


def test_stage_chain_is_free_and_ordered():
    plan = asm.build_assembly_plan("Saturn V", SCRIPT)
    stages = [s["stage"] for s in plan["stages"]]
    assert stages == ["script", "footage_match", "voiceover",
                      "subtitles", "music", "composite"]
    assert all(s["paid"] is False for s in plan["stages"] if "paid" in s)
    assert plan["stages"][0]["providers"] == list(asm.SCRIPT_PROVIDERS)


def test_short_over_60s_is_rejected():
    long_script = " ".join(["This sentence carries ten plain words "
                            "for timing purposes only today."] * 20)
    assert asm.estimate_seconds(long_script) >= 60
    with pytest.raises(asm.AssemblyError):
        asm.build_assembly_plan("Long", long_script, kind="short")
    plan = asm.build_assembly_plan("Long", long_script, kind="standard")
    assert plan["is_short"] is False


def test_paid_tts_and_unknown_options_rejected():
    for provider in asm.PAID_TTS_PROVIDERS:
        with pytest.raises(asm.AssemblyError):
            asm.build_assembly_plan("T", SCRIPT, tts_provider=provider)
    with pytest.raises(asm.AssemblyError):
        asm.build_assembly_plan("T", SCRIPT, fmt="portrait")
    with pytest.raises(asm.AssemblyError):
        asm.build_assembly_plan("T", SCRIPT, subtitle_source="paid_api")


def test_empty_inputs_rejected():
    with pytest.raises(asm.AssemblyError):
        asm.build_assembly_plan("", SCRIPT)
    with pytest.raises(asm.AssemblyError):
        asm.build_assembly_plan("T", "   ")


def test_finance_advice_script_is_blocked():
    bad = "You should invest your savings now for guaranteed returns."
    with pytest.raises(asm.AssemblyError):
        asm.build_assembly_plan("Money", bad)


def test_plan_is_batch_offline_unlisted_and_unpublished():
    plan = asm.build_assembly_plan("Saturn V", SCRIPT)
    assert plan["execution"] == "batch_offline"
    assert plan["resident_service"] is False
    assert plan["publish"] is False
    assert plan["privacy_if_published"] == "unlisted"
    assert plan["paid_services_used"] is False
    assert plan["under_60s"] is True


def test_batch_dedupes_topics_and_keeps_order():
    items = [
        {"topic": "Saturn V", "script": SCRIPT},
        {"topic": "saturn v", "script": SCRIPT},
        {"topic": "Apollo", "script": SCRIPT},
    ]
    plans = asm.build_batch(items)
    assert [p["topic"] for p in plans] == ["Saturn V", "Apollo"]
