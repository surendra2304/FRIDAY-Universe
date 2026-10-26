"""
Real Deep Layer 18 Tests — ace-step/ACE-Step-1.5 → VyralX.

Functional tests for VyralX/app/agents/real_ace_step.py:
caption parsing into conditioning tags, lyric structuring on the tempo grid
(LRC export included), tempo maps, the latent audio codec chunk plan, DiT
variant sizing/FLOPs, flow-matching schedules, track assembly with loudness
normalisation, and the end-to-end pipeline (plan, generate, compare_variants).
"""

import importlib.util
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "VyralX", "app", "agents", "real_ace_step.py")

spec = importlib.util.spec_from_file_location("real_ace_step", MODULE_PATH)
ace = importlib.util.module_from_spec(spec)
sys.modules["real_ace_step"] = ace
spec.loader.exec_module(ace)


LYRICS = ("[Verse]\n"
          "The midnight city never sleeps alone\n"
          "We chase the neon glow\n"
          "[Chorus]\n"
          "Hold the line tonight\n"
          "We burn the sky")


# ── caption parsing ──────────────────────────────────────────────────────────

def test_caption_parser_extracts_tags():
    tags = ace.CaptionParser().parse(
        "upbeat 80s synthwave with analog synth, driving drums, female vocal, 128 bpm, instrumental")
    assert tags.genres == ["synthwave"]
    assert set(tags.instruments) == {"synth", "drums"}
    assert tags.eras == ["80s"]
    assert tags.vocal_timbres == ["female"]
    assert tags.tempo_word == "driving"
    assert tags.suggested_bpm == 128
    assert tags.instrumental is True
    assert tags.to_dict()["conditioning_dim"] == 95


def test_caption_parser_does_not_confuse_female_with_male():
    tags = ace.CaptionParser().parse("a female vocal over warm pads")
    assert tags.vocal_timbres == ["female"]
    assert "male" not in tags.vocal_timbres
    male = ace.CaptionParser().parse("a male baritone over warm pads")
    assert male.vocal_timbres == ["male"]


def test_conditioning_vector_is_sparse_and_stable():
    parser = ace.CaptionParser()
    tags = parser.parse("synthwave with analog synth, 128 bpm")
    vector = tags.conditioning_vector()
    assert len(vector) == 95
    assert sum(1 for value in vector if value) >= 2
    assert parser.parse("synthwave with analog synth, 128 bpm").conditioning_vector() == vector
    assert len(parser.parse("lofi hip hop with dusty piano").conditioning_vector()) == 95


def test_caption_description_is_human_readable():
    tags = ace.CaptionParser().parse("80s synthwave with analog synth and drums, instrumental")
    description = tags.describe()
    assert "synthwave" in description
    assert "instrumental" in description


# ── lyrics ───────────────────────────────────────────────────────────────────

def test_syllable_counting():
    structurer = ace.LyricStructurer()
    assert structurer.count_syllables("The midnight city never sleeps alone") == 10
    assert structurer.count_syllables("sky") == 1
    assert structurer.count_syllables("") == 0
    assert structurer.count_syllables("make") == 1  # silent trailing 'e'


def test_lyric_parse_splits_sections():
    structurer = ace.LyricStructurer()
    pairs = structurer.parse(LYRICS)
    assert [section for section, _ in pairs] == ["verse", "verse", "chorus", "chorus"]
    assert pairs[0][1] == "The midnight city never sleeps alone"
    assert structurer.parse("") == []


def test_lyric_structure_lands_on_the_grid():
    structurer = ace.LyricStructurer()
    lines = structurer.structure(LYRICS, ace.TempoMap(128))
    assert len(lines) == 4
    assert [line.start_bar for line in lines] == [0.0, 1.0, 2.0, 3.0]
    assert lines[0].start_s == 0.0
    assert lines[0].end_s == pytest.approx(1.875)
    assert lines[-1].end_s == pytest.approx(7.5)
    assert all(line.duration > 0 for line in lines)
    assert all(line.bars > 0 for line in lines)


def test_lyric_report_flags_over_density():
    structurer = ace.LyricStructurer(bars_per_line=0.5, max_syllables_per_second=2.0)
    lines = structurer.structure(LYRICS, ace.TempoMap(128))
    report = structurer.report(lines)
    assert report["lines"] == 4
    assert report["sections"] == {"verse": 2, "chorus": 2}
    assert report["total_syllables"] == 24
    assert report["over_density"], "a 0.5-bar line at 2 syllables/s must be over-dense"
    assert structurer.report([]) == {"lines": 0}


def test_lrc_export_timestamps():
    structurer = ace.LyricStructurer()
    lines = structurer.structure(LYRICS, ace.TempoMap(128))
    lrc = structurer.to_lrc(lines)
    rows = lrc.strip().splitlines()
    assert len(rows) == 4
    assert rows[0] == "[00:00.00]The midnight city never sleeps alone"
    assert rows[-1].startswith("[00:05.62]")
    assert structurer.to_lrc([]) == ""


# ── tempo ────────────────────────────────────────────────────────────────────

def test_tempo_map_grid():
    tempo = ace.TempoMap(128)
    assert tempo.seconds_per_beat == pytest.approx(0.46875)
    assert tempo.seconds_per_bar == pytest.approx(1.875)
    assert tempo.bars_per_minute == pytest.approx(32.0)
    assert tempo.duration_for_bars(32) == pytest.approx(60.0)
    assert tempo.bars_for_duration(60.0) == pytest.approx(32.0)
    assert len(tempo.beat_grid(32)) == 128
    assert tempo.downbeats(32)[:4] == [0.0, 1.875, 3.75, 5.625]
    assert tempo.bar_to_time(2) == pytest.approx(3.75)
    assert tempo.time_to_bar(3.75) == pytest.approx(2.0)


def test_grid_report():
    report = ace.TempoMap(128).grid_report(60.0)
    assert report["bpm"] == 128
    assert report["time_signature"] == "4/4"
    assert report["bars"] == pytest.approx(32.0)
    assert report["beats"] == pytest.approx(128.0)


# ── codec ────────────────────────────────────────────────────────────────────

def test_latent_codec_chunk_plan():
    codec = ace.LatentAudioCodec()
    plan = codec.chunk_plan(60.0)
    assert plan["chunks"] == 7
    assert plan["chunk_frames"] == 250
    assert plan["overlap_frames"] == 25
    assert plan["total_frames"] == 1500
    assert plan["windows"][0] == (0, 250)
    assert plan["windows"][1] == (225, 475)
    assert plan["effective_seconds"] == pytest.approx(66.0)
    assert codec.frames_for(60.0) == 1500
    assert codec.duration_for(1500) == pytest.approx(60.0)
    assert codec.token_count(60.0) == 1500


def test_latent_codec_compression_and_short_audio():
    codec = ace.LatentAudioCodec()
    assert codec.chunk_plan(5.0)["chunks"] == 1
    assert codec.chunk_plan(0.0)["total_frames"] == 0
    assert codec.frames_for(0.0) == 0


# ── DiT variants ─────────────────────────────────────────────────────────────

def test_dit_variants_are_registered():
    variants = ace.DiTConfig.variants()
    assert set(variants) == {"base", "sft", "turbo", "xl-base", "xl-sft", "xl-turbo"}


def test_dit_variant_sizing():
    turbo = ace.DiTConfig.for_variant("turbo")
    assert turbo.layers == 24 and turbo.hidden == 1536
    assert turbo.params_b == pytest.approx(1.2)
    assert turbo.default_steps == 8
    assert turbo.is_distilled is True
    xl = ace.DiTConfig.for_variant("xl-turbo")
    assert xl.layers == 48 and xl.hidden == 3072
    assert xl.params_b == pytest.approx(4.0)
    assert xl.weight_bytes() > turbo.weight_bytes()
    assert turbo.vram_bytes(1500) > turbo.weight_bytes()
    assert turbo.head_dim == 128
    assert turbo.to_dict()["name"] == "turbo"
    with pytest.raises(KeyError):
        ace.DiTConfig.for_variant("mega")


def test_dit_costs_scale_with_tokens():
    turbo = ace.DiTConfig.for_variant("turbo")
    small = turbo.flops_per_step(1000)
    large = turbo.flops_per_step(2000)
    assert large > small
    assert turbo.estimate_seconds(8, 2000) > turbo.estimate_seconds(8, 1000)
    assert turbo.estimate_seconds(16, 1000) > turbo.estimate_seconds(8, 1000)


# ── flow matching ────────────────────────────────────────────────────────────

def test_flow_matching_schedule():
    sampler = ace.FlowMatchingSampler(steps=8, guidance=3.0)
    timesteps = sampler.timesteps(1500)
    assert len(timesteps) == 9
    assert timesteps[0] == pytest.approx(1.0)
    assert timesteps[-1] == pytest.approx(0.0)
    assert timesteps == sorted(timesteps, reverse=True)
    assert [round(t, 6) for t in timesteps[:4]] == [1.0, 0.952747, 0.900967, 0.843345]
    report = sampler.report(1500)
    assert report["steps"] == 8 and report["monotonic"] is True
    assert report["step"]["mean"] == pytest.approx(0.125)
    assert sampler.step_size()["mean"] == pytest.approx(0.125)


def test_cfg_active_window():
    sampler = ace.FlowMatchingSampler(steps=8, guidance=3.0)
    assert sampler.cfg_active(0.5) is True
    assert sampler.cfg_active(1.5) is False
    assert sampler.report(1500)["cfg_interval"] == [0.0, 1.0]


# ── track assembly ───────────────────────────────────────────────────────────

def test_loudness_helpers():
    assembler = ace.TrackAssembler()
    assert assembler.estimate_lufs(0.18) == pytest.approx(-11.89, abs=1e-2)
    assert assembler.rms_to_db(0.5) == pytest.approx(-6.021, abs=1e-3)
    assert assembler.db_to_gain(-6) == pytest.approx(0.50119, abs=1e-4)
    assert assembler.normalisation_gain(0.18, 0.95) == pytest.approx(-2.11, abs=1e-2)
    assert assembler.estimate_lufs(0.18) > assembler.estimate_lufs(0.05)


def test_sections_follow_lyric_structure():
    assembler = ace.TrackAssembler()
    lines = ace.LyricStructurer().structure(LYRICS, ace.TempoMap(128))
    sections = assembler.sections_for(lines, 30.0)
    assert [section.name for section in sections] == ["verse", "chorus"]
    assert sections[0].start == 0.0
    assert sections[0].end == pytest.approx(3.75)
    assert sections[-1].end == pytest.approx(30.0)
    assert sections[-1].fade_out > sections[0].fade_out
    empty = assembler.sections_for([], 30.0)
    assert len(empty) == 1 and empty[0].name == "main"
    assert empty[0].to_dict()["duration"] == pytest.approx(30.0)


def test_export_plan_sizes():
    assembler = ace.TrackAssembler()
    sections = assembler.sections_for([], 90.0)
    plan = assembler.export_plan(90.0, sections)
    formats = {row["container"]: row["size_bytes"] for row in plan["formats"]}
    assert formats["wav"] == 23_814_000
    assert formats["mp3"] == 3_600_000
    assert formats["flac"] == 7_920_000
    assert plan["target_lufs"] == pytest.approx(-14.0)
    assert plan["ceiling_dbfs"] == pytest.approx(-1.0)


# ── pipeline ─────────────────────────────────────────────────────────────────

def test_pipeline_plan_is_fully_specified():
    plan = ace.AceStepPipeline("turbo").plan(
        "upbeat synthwave with analog synth", LYRICS, 60.0)
    assert plan.caption == "upbeat synthwave with analog synth"
    assert plan.duration_s == 60.0
    assert plan.variant == "turbo"
    assert plan.tempo.bpm == 124.0
    assert plan.tags.genres == ["synthwave"]
    assert plan.dit["tokens"] == 1500
    assert plan.sampler["steps"] == 8
    assert plan.codec["chunks"] == 7
    assert plan.lyrics_report["lines"] == 4
    assert plan.cost["estimate_seconds"] > 0
    assert plan.to_dict()["variant"] == "turbo"


def test_pipeline_generate_produces_deliverables():
    result = ace.AceStepPipeline("turbo").generate(
        "upbeat synthwave with analog synth", LYRICS, 90.0)
    assert set(result) == {"plan", "sections", "lrc", "loudness", "export"}
    plan = result["plan"]
    assert plan["tempo"]["bpm"] == 124.0
    assert plan["codec"]["chunks"] == 10
    assert plan["codec"]["total_frames"] == 2250
    assert plan["cost"]["forward_passes"] == 16
    assert plan["cost"]["estimate_seconds"] == pytest.approx(4.32, abs=1e-2)
    assert plan["cost"]["vram_gb"] == pytest.approx(3.78, abs=1e-2)
    assert result["lrc"].startswith("[00:00.00]The midnight city")
    assert result["loudness"]["normalisation_gain_db"] == pytest.approx(-2.11, abs=1e-2)
    containers = {row["container"] for row in result["export"]["formats"]}
    assert containers == {"wav", "mp3", "flac"}
    assert [section["name"] for section in result["sections"]] == ["verse", "chorus"]


def test_pipeline_compare_variants():
    comparison = ace.AceStepPipeline("turbo").compare_variants("upbeat synthwave", 120.0)
    assert set(comparison) == set(ace.DiTConfig.variants())
    assert comparison["turbo"]["steps"] == 8
    assert comparison["base"]["steps"] == 50
    assert comparison["turbo"]["estimate_seconds"] < comparison["xl-base"]["estimate_seconds"]
    assert comparison["turbo"]["vram_gb"] < comparison["xl-turbo"]["vram_gb"]
    for metrics in comparison.values():
        assert metrics["estimate_seconds"] > 0
        assert metrics["vram_gb"] > 0


def test_pipeline_rejects_unknown_variant():
    pipeline = ace.AceStepPipeline("ultra")
    with pytest.raises(KeyError):
        pipeline.plan("upbeat synthwave", LYRICS, 60.0)


# ── helpers ──────────────────────────────────────────────────────────────────

def test_numeric_helpers():
    assert ace.clamp01(5.0) == 1.0 and ace.clamp01(-5.0) == 0.0
    assert ace.safe_div(1.0, 0.0, default=2.0) == 2.0
