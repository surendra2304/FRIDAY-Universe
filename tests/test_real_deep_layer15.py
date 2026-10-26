"""
Real Deep Layer 15 Tests — krillinai/OpenCreator → VyralX.

Functional tests for VyralX/app/agents/real_open_creator.py:
platform presets and size estimation, the media-provider catalogue with
explainable scoring, the pipeline DAG (topological order, batches, critical
path, validation), the retrying executor, the dubbing/timing pipeline with
language-expansion and rate clamping, deterministic shot prompts and the batch
job planner.
"""

import importlib.util
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "VyralX", "app", "agents", "real_open_creator.py")

spec = importlib.util.spec_from_file_location("real_open_creator", MODULE_PATH)
oc = importlib.util.module_from_spec(spec)
sys.modules["real_open_creator"] = oc
spec.loader.exec_module(oc)


@pytest.fixture()
def dag():
    graph = oc.PipelineDAG()
    graph.add(oc.PipelineStage("download", "io"))
    graph.add(oc.PipelineStage("transcribe", "asr", depends_on=("download",)))
    graph.add(oc.PipelineStage("translate", "text", depends_on=("transcribe",)))
    graph.add(oc.PipelineStage("images", "image", depends_on=("translate",)))
    graph.add(oc.PipelineStage("tts", "tts", depends_on=("translate",)))
    graph.add(oc.PipelineStage("render", "render", depends_on=("images", "tts")))
    return graph


HANDLERS = {
    "io": lambda stage, ctx: {"bytes": 1024},
    "asr": lambda stage, ctx: {"segments": 3},
    "text": lambda stage, ctx: {"language": "es"},
    "image": lambda stage, ctx: {"shots": 2},
    "tts": lambda stage, ctx: {"audio_s": 12.0},
    "render": lambda stage, ctx: {"file": "out.mp4"},
}


# ── presets ──────────────────────────────────────────────────────────────────

def test_preset_registry_lists_platforms():
    registry = oc.PresetRegistry()
    names = registry.names()
    assert "tiktok" in names and "youtube_4k" in names
    assert registry.for_platform("tiktok").name == "tiktok"


def test_tiktok_preset_metrics():
    preset = oc.PresetRegistry().get("tiktok")
    assert (preset.width, preset.height) == (1080, 1920)
    assert preset.orientation == "vertical"
    assert preset.megapixels == pytest.approx(2.074, abs=1e-3)
    assert preset.aspect_ratio == pytest.approx(0.5625)
    assert preset.estimate_size_mb(30.0) == pytest.approx(22.03, abs=1e-2)
    assert preset.bitrate_for_duration(30.0) == (6000 + 160) * 1000 * 30 // 8
    assert preset.scale_args() == "scale=1080:1920"


def test_preset_size_grows_with_duration():
    preset = oc.PresetRegistry().get("tiktok")
    assert preset.estimate_size_mb(60.0) == pytest.approx(2 * preset.estimate_size_mb(30.0), abs=1e-2)


# ── provider catalogue ───────────────────────────────────────────────────────

def test_profile_catalogue_covers_media_kinds():
    registry = oc.MediaProfileRegistry()
    kinds = {profile.kind for profile in registry.all()}
    assert kinds == {"image", "video", "voice", "avatar"}
    assert registry.get("img_flux2_dev").provider == "bfl"
    assert [p.profile_id for p in registry.by_kind("voice")]


def test_profile_cost_and_duration_fits():
    registry = oc.MediaProfileRegistry()
    image = registry.get("img_flux2_dev")
    assert image.cost_for(4) == pytest.approx(0.16)
    assert image.fits_duration(600.0) is True
    voice = registry.get("voice_openai")
    assert voice.unit == "char"
    assert voice.cost_for(2000) == pytest.approx(0.03)
    video = registry.get("video_kling")
    assert video.max_duration_s == 10.0
    assert video.fits_duration(9.0) is True
    assert video.fits_duration(11.0) is False


def test_provider_scorer_weights_and_ranking():
    scorer = oc.ProviderScorer()
    registry = oc.MediaProfileRegistry()
    score = scorer.score(registry.get("img_flux2_dev"), "image")
    assert score.task_fit == 1.0
    assert score.weighted_score == pytest.approx(0.9518, abs=1e-3)
    assert set(score.parts()) == set(oc.ProviderScore.WEIGHTS)
    ranked = scorer.rank(registry.by_kind("image"), "image")
    assert [row.profile.profile_id for row in ranked][0] == "img_flux2_dev"
    assert ranked[0].weighted_score >= ranked[-1].weighted_score
    assert "img_flux2_dev" in ranked[0].explain()


def test_provider_scorer_penalises_mismatches():
    scorer = oc.ProviderScorer()
    registry = oc.MediaProfileRegistry()
    wrong_kind = scorer.score(registry.get("voice_openai"), "image")
    assert wrong_kind.task_fit == 0.0
    too_long = scorer.score(registry.get("video_kling"), "video", duration_s=30.0)
    assert too_long.task_fit == 0.0


def test_provider_choose_returns_an_explanation():
    scorer = oc.ProviderScorer()
    registry = oc.MediaProfileRegistry()
    choice = scorer.choose(registry, "voice", amount=2000)
    assert choice["selected"]["profile_id"] == "voice_openai"
    assert choice["estimated_cost_usd"] == pytest.approx(0.03)
    assert choice["runners_up"]
    assert "voice_openai" in choice["explanation"]
    with pytest.raises(KeyError):
        scorer.choose(registry, "hologram")


# ── DAG ──────────────────────────────────────────────────────────────────────

def test_dag_topological_order_and_batches(dag):
    assert dag.order() == ["download", "transcribe", "translate", "images", "tts", "render"]
    batches = dag.batches()
    assert batches == [["download"], ["transcribe"], ["translate"], ["images", "tts"], ["render"]]
    assert dag.critical_path_length() == pytest.approx(5.0)
    assert dag.validate() == []


def test_dag_detects_missing_dependency_and_cycles():
    broken = oc.PipelineDAG()
    broken.add(oc.PipelineStage("a", "io", depends_on=("ghost",)))
    assert broken.validate()
    cyclic = oc.PipelineDAG()
    cyclic.add(oc.PipelineStage("x", "io", depends_on=("y",)))
    cyclic.add(oc.PipelineStage("y", "io", depends_on=("x",)))
    assert cyclic.validate()


# ── executor ─────────────────────────────────────────────────────────────────

def test_executor_runs_every_stage_in_order(dag):
    executor = oc.PipelineExecutor(handlers=HANDLERS)
    result = executor.run(dag)
    assert result["ok"] is True
    assert result["completed"] == 6
    assert result["failed"] == [] and result["skipped"] == []
    assert [row["stage_id"] for row in result["log"]] == dag.order()
    assert dag.stages["render"].output == {"file": "out.mp4"}


def test_executor_skips_stages_without_handlers(dag):
    executor = oc.PipelineExecutor(handlers={"io": HANDLERS["io"]})
    result = executor.run(dag)
    assert result["completed"] == 1
    assert set(result["skipped"]) == {"transcribe", "translate", "images", "tts", "render"}


def test_executor_retries_then_fails():
    calls = {"n": 0}

    def flaky(stage, ctx):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    graph = oc.PipelineDAG()
    graph.add(oc.PipelineStage("only", "io"))
    executor = oc.PipelineExecutor(handlers={"io": flaky}, max_attempts=3)
    result = executor.run(graph)
    assert result["ok"] is True
    assert graph.stages["only"].attempts == 3
    assert executor.log[-1]["backoff_ms"] > 0

    calls["n"] = 0
    graph2 = oc.PipelineDAG()
    graph2.add(oc.PipelineStage("only", "io"))
    failing = oc.PipelineExecutor(handlers={"io": lambda s, c: (_ for _ in ()).throw(RuntimeError("nope"))}, max_attempts=2)
    result2 = failing.run(graph2)
    assert result2["ok"] is False
    assert result2["failed"] == ["only"]


def test_retry_policy_backoff_is_capped():
    policy = oc.RetryPolicy(max_attempts=3, base_backoff_ms=200, factor=2.0, max_backoff_ms=8000)
    assert [policy.backoff_ms(i) for i in range(1, 6)] == [200, 400, 800, 1600, 3200]
    assert policy.total_backoff_ms() == 1400
    capped = oc.RetryPolicy(max_attempts=9, max_backoff_ms=800)
    assert capped.backoff_ms(9) == 800


# ── dubbing ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def segments():
    pipeline = oc.DubbingPipeline(source_language="en", target_language="es")
    return pipeline.build_segments([
        (0.0, 2.0, "Welcome to the show."),
        (2.0, 5.5, "Today we look at how compilers actually work."),
        (5.5, 7.0, "Short line."),
    ])


def test_dubbing_language_expansion_and_translation(segments):
    pipeline = oc.DubbingPipeline(source_language="en", target_language="es")
    assert pipeline.expansion_factor() == pytest.approx(1.22)
    assert len(segments[0].translated) >= len(segments[0].text)
    assert oc.DubbingPipeline(target_language="ja").expansion_factor() == pytest.approx(0.82)
    assert oc.DubbingPipeline(target_language="zz").expansion_factor() == pytest.approx(1.15)
    assert oc.DubbingPipeline(target_language="en").expansion_factor() == pytest.approx(1.0)


def test_dubbing_plan_clamps_speaking_rate(segments):
    pipeline = oc.DubbingPipeline()
    plans = pipeline.plan(segments)
    assert len(plans) == 3
    for row in plans:
        assert pipeline.min_rate <= row.rate <= pipeline.max_rate
        assert row.required_seconds <= row.available_seconds + 1e-6
        assert row.lead_in >= 0.0


def test_dubbing_report_summarises_fit(segments):
    pipeline = oc.DubbingPipeline()
    report = pipeline.report(pipeline.plan(segments))
    assert report["segments"] == 3
    assert report["target_language"] == "es"
    assert report["fit_ratio"] == pytest.approx(1.0)
    assert report["overflow_segments"] == []
    assert report["mean_cps"] > 0
    assert report["over_cps_limit"] == []


def test_dubbing_exports_srt_and_vtt(segments):
    pipeline = oc.DubbingPipeline()
    srt = pipeline.to_srt(segments)
    assert srt.splitlines()[1] == "00:00:00,000 --> 00:00:02,000"
    assert "Bienvenido" in srt or "Welcome" in srt
    vtt = pipeline.to_vtt(segments)
    assert vtt.splitlines()[0] == "WEBVTT"
    assert "-->" in vtt


# ── shot prompts ─────────────────────────────────────────────────────────────

def test_shot_prompt_is_deterministic_and_styled():
    builder = oc.ShotPromptBuilder()
    prompt = builder.build("shot-1", "a lighthouse", "keeper lights the lamp", "stormy coast",
                           aspect_ratio="9:16")
    again = builder.build("shot-1", "a lighthouse", "keeper lights the lamp", "stormy coast",
                          aspect_ratio="9:16")
    assert prompt.seed == again.seed
    assert prompt.camera in oc.ShotPromptBuilder.CAMERAS
    assert prompt.lens in oc.ShotPromptBuilder.LENSES
    assert prompt.lighting in oc.ShotPromptBuilder.LIGHTING
    assert prompt.mood in oc.ShotPromptBuilder.MOODS
    text = prompt.build()
    assert "a lighthouse" in text and "9:16" in text
    assert prompt.negative in text or prompt.style in text


def test_shot_prompt_variations_differ_only_by_seed():
    builder = oc.ShotPromptBuilder()
    variants = builder.variations("shot-1", "a lighthouse", 3)
    assert len({v.seed for v in variants}) == 3
    assert variants[0].subject == variants[2].subject
    assert builder.seed_for("shot-1", 2) == variants[2].seed


# ── batch planner ────────────────────────────────────────────────────────────

def test_batch_planner_waves_and_eta():
    planner = oc.BatchJobPlanner(concurrency=2)
    preset = oc.PresetRegistry().get("tiktok")
    for i in range(3):
        planner.queue(preset, duration_s=30.0, job_id=f"job{i}")
    plan = planner.plan()
    assert plan["jobs"] == 3
    assert plan["waves"] == [["job0", "job1"], ["job2"]]
    assert plan["total_duration_s"] == pytest.approx(90.0)
    assert plan["total_size_mb"] == pytest.approx(66.09, abs=1e-2)
    assert plan["retry_policy"]["total_backoff_ms"] == 1400
    assert plan["eta_seconds"] > 0
    assert planner.eta_seconds(render_speed=2.0) < plan["eta_seconds"]


def test_batch_job_size_uses_its_preset():
    job = oc.BatchJob(job_id="j", preset=oc.PresetRegistry().get("tiktok"), duration_s=30.0)
    assert job.estimated_size_mb == pytest.approx(22.03, abs=1e-2)


# ── helpers ──────────────────────────────────────────────────────────────────

def test_timestamp_formatters():
    assert oc.timestamp_srt(3661.5) == "01:01:01,500"
    assert oc.timestamp_vtt(3661.5) == "01:01:01.500"
    assert oc.clamp01(4.0) == 1.0 and oc.clamp01(-1.0) == 0.0
    assert oc.safe_div(1.0, 0.0, default=3.0) == 3.0
