"""
Real Deep Layer 16 Tests — black-forest-labs/flux2 → VyralX.

Functional tests for VyralX/app/agents/real_flux2.py:
autoencoder geometry and latent packing, image preparation/bucketing, the
resolution-shifted timestep schedule, rectified-flow Euler sampling,
classifier-free guidance, (t,h,w,l) position ids, reference-image KV-cache
planning, prompt upsampling, the QIM watermarking round-trip and the
end-to-end pipeline plan/generate.
"""

import importlib.util
import math
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "VyralX", "app", "agents", "real_flux2.py")

spec = importlib.util.spec_from_file_location("real_flux2", MODULE_PATH)
f2 = importlib.util.module_from_spec(spec)
sys.modules["real_flux2"] = f2
spec.loader.exec_module(f2)


def sample_latent(channels: int, height: int, width: int) -> list[float]:
    return [((c * 31 + (i % 17)) % 13) / 13.0
            for c in range(channels) for i in range(height * width)]


def make_image(width: int = 64, height: int = 64, kind: str = "ramp") -> list[list[float]]:
    if kind == "ramp":
        return [[float((x * 3 + y * 5) % 97) for x in range(width)] for y in range(height)]
    if kind == "gradient":
        return [[float(x) / max(1, width - 1) * 255.0 for x in range(width)] for y in range(height)]
    if kind == "blocks":
        return [[255.0 if (x // 8 + y // 8) % 2 == 0 else 0.0 for x in range(width)] for y in range(height)]
    return [[0.0 for _ in range(width)] for _ in range(height)]


# ── autoencoder + packing ────────────────────────────────────────────────────

def test_autoencoder_geometry():
    ae = f2.Flux2AutoEncoderParams()
    assert ae.latent_shape(1024, 1024) == (32, 128, 128)
    assert ae.token_count(1024, 1024) == 4096
    assert ae.latent_pixels(1024, 1024) == 16384
    assert ae.compression_ratio(1024, 1024) == pytest.approx(6.0)
    info = ae.to_dict()
    assert info["z_channels"] == 32
    assert info["downsample_factor"] == 8
    assert info["latent_channels_packed"] == 128  # z_channels * patch_size^2


def test_latent_packer_roundtrip_is_lossless():
    packer = f2.LatentPacker(patch_size=2, z_channels=32)
    latent = sample_latent(32, 8, 8)
    packed = packer.pack(latent, 8, 8)
    assert len(packed) == len(latent)
    assert packer.token_grid(8, 8) == (4, 4)
    assert packer.roundtrip_error(latent, 8, 8) == 0.0


def test_latent_packer_rejects_bad_shapes():
    packer = f2.LatentPacker(patch_size=2, z_channels=32)
    with pytest.raises(ValueError):
        packer.pack([0.0] * 10, 8, 8)
    with pytest.raises(ValueError):
        packer.pack(sample_latent(32, 8, 8), 7, 8)
    with pytest.raises(ValueError):
        packer.unpack([0.0] * 3, 8, 8)


# ── image prep ───────────────────────────────────────────────────────────────

def test_image_prep_scales_crops_and_reports():
    prep = f2.ImagePrep()
    prepared = prep.prepare(2000, 1300)
    assert prepared.scale == pytest.approx(0.6351, abs=1e-4)
    assert prepared.width % f2.ImagePrep.MULTIPLE_OF == 0
    assert prepared.height % f2.ImagePrep.MULTIPLE_OF == 0
    assert prepared.megapixels == pytest.approx(1.0314, abs=1e-4)
    assert (prepared.crop_x, prepared.crop_y) == (3, 5)


def test_image_prep_buckets_and_limits():
    prep = f2.ImagePrep()
    assert prep.bucket_for(1920, 1080) == (1280, 768)
    assert prep.scale_to_limit(1024, 1024, 1024 ** 2) == 1.0
    assert prep.scale_to_limit(4000, 3000, 1024 ** 2) == pytest.approx(0.295603, abs=1e-6)
    fitted = prep.fit_to_bucket(1920, 1080, megapixels=1.0)
    assert fitted.megapixels == pytest.approx(1.0)
    assert fitted.width % 16 == 0 and fitted.height % 16 == 0
    assert prep.center_crop_to_multiple(100, 100, 16) == (96, 96, 2, 2)


# ── schedule ─────────────────────────────────────────────────────────────────

def test_schedule_is_uniform_without_shift():
    scheduler = f2.TimeStepScheduler()
    assert scheduler.get_schedule(4, 1024, shift=False) == [1.0, 0.75, 0.5, 0.25, 0.0]
    assert scheduler.sigma_to_t(0.5) == pytest.approx(0.5)
    assert scheduler.snr(0.5) == pytest.approx(1.0)


def test_schedule_shifts_with_resolution():
    scheduler = f2.TimeStepScheduler()
    shifted = scheduler.get_schedule(4, 1024, shift=True)
    assert [round(t, 4) for t in shifted] == [1.0, 0.8492, 0.6525, 0.3849, 0.0]
    assert shifted == sorted(shifted, reverse=True)
    assert shifted[0] == pytest.approx(1.0, abs=1e-6)


def test_time_shift_is_bounded():
    scheduler = f2.TimeStepScheduler()
    assert scheduler.time_shift(1.15, 1.0, 0.5) == pytest.approx(0.759511, abs=1e-6)
    assert scheduler.time_shift(1e9, 1.0, 0.5) < 1.0, "mu must be clamped so exp(mu) stays finite"
    assert scheduler.time_shift(1.15, 1.0, 1.0) == pytest.approx(1.0, abs=1e-6)


def test_schedule_report_summarises_steps():
    scheduler = f2.TimeStepScheduler()
    report = scheduler.schedule_report(scheduler.get_schedule(4, 1024, shift=True))
    assert report["steps"] == 4
    assert report["monotonic"] is True
    assert report["mean_step"] == pytest.approx(0.249999, abs=1e-5)
    assert report["min_step"] <= report["max_step"]


# ── sampling + guidance ──────────────────────────────────────────────────────

def test_rectified_flow_euler_step():
    sampler = f2.RectifiedFlowSampler()
    assert sampler.step([1.0], [2.0], 1.0, 0.5) == pytest.approx([0.0])
    with pytest.raises(ValueError):
        sampler.step([1.0], [1.0, 2.0], 1.0, 0.5)


def test_rectified_flow_run_and_trace():
    sampler = f2.RectifiedFlowSampler()
    x, trace = sampler.run([1.0, 0.0], lambda xx, t, g: [2.0 for _ in xx],
                           [1.0, 0.5, 0.0], guidance=3.0, trace=True)
    assert x == pytest.approx([-1.0, -2.0])
    assert [row["step"] for row in trace] == [0, 1]
    assert all(row["dt"] < 0 for row in trace)
    plain = sampler.run([1.0], lambda xx, t, g: [1.0 for _ in xx], [1.0, 0.0])
    assert plain == pytest.approx([0.0])


def test_run_with_conditioning_truncates_reference_tokens():
    sampler = f2.RectifiedFlowSampler()
    result = sampler.run_with_conditioning(
        [0.0, 0.0], lambda xx, t, g: [1.0 for _ in xx] + [9.0, 9.0],
        [1.0, 0.0], cond_tokens=2)
    # dt = t_prev - t_curr = -1.0 with velocity 1.0
    assert result == pytest.approx([-1.0, -1.0])
    # without cond_tokens the extra reference predictions break the update
    with pytest.raises(ValueError):
        sampler.run_with_conditioning(
            [0.0, 0.0], lambda xx, t, g: [1.0 for _ in xx] + [9.0, 9.0], [1.0, 0.0])


def test_classifier_free_guidance_math():
    cfg = f2.ClassifierFreeGuidance()
    assert cfg.combine([0.0, 0.0], [1.0, 2.0], 3.0) == pytest.approx([3.0, 6.0])
    assert cfg.combine([1.0], [1.0], 7.0) == pytest.approx([1.0])
    with pytest.raises(ValueError):
        cfg.combine([1.0], [1.0, 2.0], 1.0)
    assert cfg.effective_guidance(3.0, 0.0) == 0.0
    assert cfg.effective_guidance(3.0, 0.5) == pytest.approx(1.8)
    cost = cfg.batch_cost(2, 100, use_cfg=True)
    assert cost == {"forward_passes": 4, "tokens_processed": 400}
    assert cfg.batch_cost(2, 100, use_cfg=False)["forward_passes"] == 2


def test_run_cfg_applies_guidance():
    cfg = f2.ClassifierFreeGuidance()
    out = cfg.run_cfg([0.0, 0.0], lambda xx, t, g: [1.0 if g else 0.0 for _ in xx],
                      [1.0, 0.5, 0.0], guidance=3.0)
    assert out == pytest.approx([-3.0, -3.0])


# ── position ids ─────────────────────────────────────────────────────────────

def test_position_id_grid():
    grid = f2.PositionIdGrid()
    assert grid.prc_img(2, 2)[:2] == [(0, 0, 0, 0), (0, 0, 1, 0)]
    assert len(grid.prc_img(4, 4)) == 16
    assert grid.prc_txt(3, t_coord=1) == [(1, 0, 0, 0), (1, 0, 0, 1), (1, 0, 0, 2)]
    assert grid.concat([(0, 0, 0, 0)], [(1, 1, 1, 1)]) == [(0, 0, 0, 0), (1, 1, 1, 1)]
    assert grid.compress_time([10, 20, 10, 30]) == [0, 1, 0, 2]


def test_scatter_ids_rebuilds_a_dense_grid():
    grid = f2.PositionIdGrid()
    scattered = grid.scatter_ids([[1.0, 2.0], [3.0, 4.0]], [(0, 0, 0, 0), (0, 0, 1, 0)])
    assert scattered[:4] == pytest.approx([1.0, 2.0, 3.0, 4.0])
    assert grid.scatter_ids([], []) == []


# ── reference images ─────────────────────────────────────────────────────────

def test_reference_stack_offsets_and_limits():
    refs = f2.ReferenceImageStack(scale=10)
    plan = refs.token_plan([1024, 1024, 1024])
    assert plan["references"] == 3
    assert plan["time_offsets"] == [10, 20, 30]
    assert plan["limit_pixels"] == 1024 ** 2
    assert plan["total_reference_tokens"] == 3072
    single = f2.ReferenceImageStack(scale=10)
    single.token_plan([1024])
    assert single.limit_pixels == 2024 ** 2
    assert f2.ReferenceImageStack().limit_pixels is None


def test_kv_cache_plan_saves_work():
    plan = f2.ReferenceImageStack.kv_cache_plan(num_steps=4, image_tokens=4096, reference_tokens=2048)
    assert plan["speedup"] == pytest.approx(1.7143, abs=1e-4)
    assert plan["saved_fraction"] == pytest.approx(0.4167, abs=1e-4)
    assert plan["attention_units_cached"] < plan["attention_units_naive"]


# ── prompt upsampling ────────────────────────────────────────────────────────

def test_prompt_upsampler_detects_short_prompts():
    upsampler = f2.PromptUpsampler()
    assert upsampler.needs_upsampling("a cat") is True
    assert upsampler.needs_upsampling("word " * 60) is False
    assert upsampler.estimate_tokens("a cat on a mat") == 6
    report = upsampler.report("a cat on a mat")
    assert report["mode"] == "short"
    assert report["needs_upsampling"] is True
    assert report["within_budget"] is True


def test_prompt_upsampler_enriches_and_builds_messages():
    upsampler = f2.PromptUpsampler()
    upsampled = upsampler.upsample("a cat on a mat")
    assert upsampled.startswith("a cat on a mat")
    assert len(upsampled) > len("a cat on a mat")
    messages = upsampler.build_messages("a cat")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "a cat" in messages[-1]["content"]
    assert "visual detail" in upsampler.system_message


# ── watermarking ─────────────────────────────────────────────────────────────

def test_watermark_bits_are_key_dependent():
    encoder = f2.WatermarkEncoder()
    assert len(encoder.bits("key-1")) == 64
    assert encoder.bits("key-1") != encoder.bits("key-2")
    assert all(bit in (0, 1) for bit in encoder.bits("key-1"))
    assert len(encoder.pattern("key-1")) == len(encoder.bits("key-1"))


@pytest.mark.parametrize("kind", ["ramp", "gradient", "blocks"])
def test_watermark_detects_the_right_key(kind):
    encoder = f2.WatermarkEncoder()
    detector = f2.WatermarkDetector()
    image = make_image(kind=kind)
    marked = encoder.embed(image, "secret-key")
    assert encoder.psnr(image, marked) > 45.0, "the mark must stay near-invisible"
    right = detector.score(marked, "secret-key")
    wrong = detector.score(marked, "wrong-key")
    assert right - wrong > 0.25, "the key must be separable on every image type"
    assert wrong < 0.35
    assert detector.score(image, "secret-key") < 0.35
    assert right > 0.35
    verdict = detector.detect(marked, "secret-key")
    assert verdict["detected"] is True
    assert verdict["score"] > verdict["threshold"]


def test_watermark_quantisation_helpers():
    encoder = f2.WatermarkEncoder()
    assert encoder.slots_per_block > 0
    assert encoder.step_for(1000.0) > 0
    zero = encoder.quantize(10.0, 4.0, 0)
    one = encoder.quantize(10.0, 4.0, 1)
    assert zero != one, "each bit must land on its own lattice"
    assert abs(zero - 10.0) <= 4.0 and abs(one - 10.0) <= 4.0
    assert abs(encoder.residual(10.0, 4.0)) <= 2.0 + 1e-9
    pairs = encoder.pairs()
    assert pairs and all(len(pair) == 2 for pair in pairs)


# ── pipeline ─────────────────────────────────────────────────────────────────

def test_pipeline_plan_reports_cost_and_geometry():
    pipeline = f2.Flux2Pipeline()
    plan = pipeline.plan("a lighthouse in a storm", 1024, 1024, steps=50, guidance=4.0)
    assert plan["tokens"] == 4096
    assert plan["latent_shape"] == (32, 128, 128)
    assert plan["compression_ratio"] == pytest.approx(6.0)
    assert plan["schedule"]["steps"] == 50
    assert plan["cost"]["forward_passes"] == 100
    assert plan["prompt"]["needs_upsampling"] is True
    assert "a lighthouse" in plan["upsampled_prompt"]


def test_pipeline_generate_is_deterministic():
    pipeline = f2.Flux2Pipeline(seed=7)
    first = pipeline.generate("a lighthouse in a storm", width=256, height=256, steps=4, guidance=3.0)
    second = pipeline.generate("a lighthouse in a storm", width=256, height=256, steps=4, guidance=3.0)
    assert first.digest == second.digest
    assert first.tokens == second.tokens
    assert len(first.latent) == 32 * 32 * 32
    assert first.to_dict()["prompt"] == "a lighthouse in a storm"
    assert len(first.timesteps) == 5
    assert first.timesteps[0] >= first.timesteps[-1]


def test_pipeline_generate_embeds_the_watermark():
    pipeline = f2.Flux2Pipeline(seed=3)
    image = make_image(width=64, height=64, kind="ramp")
    result = pipeline.generate("a lighthouse", width=256, height=256, steps=2,
                               guidance=1.0, image=image)
    assert result.watermark, "an input image must be watermarked on the way out"
    assert "psnr" in result.watermark


def test_pipeline_noise_accepts_string_and_int_seeds():
    pipeline = f2.Flux2Pipeline()
    noise = pipeline.noise(16, "s1")
    assert len(noise) == 16
    assert pipeline.noise(16, "s1") == noise
    assert pipeline.noise(16, "s2") != noise
    assert pipeline.noise(16, 5) == pipeline.noise(16, 5)
    assert all(math.isfinite(value) for value in noise)
    assert -4.0 < sum(noise) / len(noise) < 4.0


def test_pipeline_rejects_zero_steps():
    with pytest.raises(ValueError):
        f2.Flux2Pipeline().generate("x", steps=0)


# ── helpers ──────────────────────────────────────────────────────────────────

def test_numeric_helpers():
    assert f2.clamp(2.0) == 1.0 and f2.clamp(-2.0) == 0.0
    assert f2.clamp(0.25, 0.0, 0.5) == 0.25
    assert f2.safe_div(1.0, 0.0, default=5.0) == 5.0
    assert f2.linspace(0.0, 1.0, 3) == pytest.approx([0.0, 0.5, 1.0])
