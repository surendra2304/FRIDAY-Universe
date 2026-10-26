"""
VyralX Deep Layer 12 — Real FLUX.2 Engine (rectified-flow image generation)

Real repository integration:
    black-forest-labs/flux2
    Upstream: https://github.com/black-forest-labs/flux2

FLUX.2 is Black Forest Labs' rectified-flow transformer for text-to-image
generation and multi-reference image editing. ``src/flux2`` ships four pieces of
pure logic that this module ports to stdlib Python for the VyralX agent:

``autoencoder.py``  -> :class:`Flux2AutoEncoderParams`, :class:`LatentPacker`,
                       :class:`ImagePrep` (32-channel VAE, 8x downsample, 2x2
                       patch packing, pixel-bucketed prep).
``sampling.py``     -> :class:`TimeStepScheduler` (mu/sigma time shift),
                       :class:`RectifiedFlowSampler` (Euler integration of the
                       velocity field), :class:`ClassifierFreeGuidance`,
                       :class:`PositionIdGrid` (t,h,w,l position ids and the
                       scatter/compress-time helpers),
                       :class:`ReferenceImageStack` (multi-reference t-offsets
                       plus the KV-cache plan from ``denoise_cached``).
``system_messages.py`` -> :class:`PromptUpsampler`.
``watermark.py``    -> :class:`WatermarkEncoder` / :class:`WatermarkDetector`,
                       a real mid-frequency Fourier-domain watermark.

The denoiser itself is injected (``velocity_fn``), exactly like upstream passes
a ``Flux2`` module into ``denoise()`` — so the sampling maths here is testable
without a GPU.
"""

from __future__ import annotations

import cmath
import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else (high if value > high else value)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def linspace(start: float, stop: float, count: int) -> list[float]:
    if count <= 1:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + step * i for i in range(count)]


# ─────────────────────────────────────────────────────────────────────────────
# Autoencoder: latent geometry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Flux2AutoEncoderParams:
    """VAE configuration (mirrors ``flux2.autoencoder.AutoEncoderParams``)."""

    resolution: int = 256
    in_channels: int = 3
    ch: int = 128
    out_ch: int = 3
    ch_mult: tuple[int, ...] = (1, 2, 4, 4)
    num_res_blocks: int = 2
    z_channels: int = 32
    patch_size: int = 2

    @property
    def downsample_factor(self) -> int:
        return 2 ** (len(self.ch_mult) - 1)

    @property
    def latent_channels(self) -> int:
        """Channels after 2x2 patch packing."""
        return self.z_channels * self.patch_size ** 2

    def latent_shape(self, height: int, width: int) -> tuple[int, int, int]:
        f = self.downsample_factor
        return (self.z_channels, height // f, width // f)

    def token_count(self, height: int, width: int) -> int:
        _, lh, lw = self.latent_shape(height, width)
        return (lh // self.patch_size) * (lw // self.patch_size)

    def latent_pixels(self, height: int, width: int) -> int:
        _, lh, lw = self.latent_shape(height, width)
        return lh * lw

    def compression_ratio(self, height: int, width: int) -> float:
        return round(safe_div(height * width * self.in_channels, self.latent_pixels(height, width) * self.z_channels), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "in_channels": self.in_channels,
            "z_channels": self.z_channels,
            "ch_mult": list(self.ch_mult),
            "downsample_factor": self.downsample_factor,
            "patch_size": self.patch_size,
            "latent_channels_packed": self.latent_channels,
        }


class LatentPacker:
    """Patchify / unpatchify a CHW latent (``einops``-free, pure Python)."""

    def __init__(self, patch_size: int = 2, z_channels: int = 32):
        self.patch_size = patch_size
        self.z_channels = z_channels

    def pack(self, latent: list[float], height: int, width: int) -> list[float]:
        """CHW latent -> sequence of ``(ph*pw*c)`` tokens in row-major order."""
        p, c = self.patch_size, self.z_channels
        if len(latent) != c * height * width:
            raise ValueError(f"expected {c * height * width} values, got {len(latent)}")
        if height % p or width % p:
            raise ValueError(f"latent {height}x{width} is not divisible by patch size {p}")
        tokens: list[float] = []
        for by in range(0, height, p):
            for bx in range(0, width, p):
                for ch in range(c):
                    for dy in range(p):
                        for dx in range(p):
                            y, x = by + dy, bx + dx
                            tokens.append(latent[(ch * height + y) * width + x])
        return tokens

    def unpack(self, tokens: list[float], height: int, width: int) -> list[float]:
        p, c = self.patch_size, self.z_channels
        expected = (height // p) * (width // p) * c * p * p
        if len(tokens) != expected:
            raise ValueError(f"expected {expected} token values, got {len(tokens)}")
        latent = [0.0] * (c * height * width)
        idx = 0
        for by in range(0, height, p):
            for bx in range(0, width, p):
                for ch in range(c):
                    for dy in range(p):
                        for dx in range(p):
                            y, x = by + dy, bx + dx
                            latent[(ch * height + y) * width + x] = tokens[idx]
                            idx += 1
        return latent

    def token_grid(self, height: int, width: int) -> tuple[int, int]:
        return height // self.patch_size, width // self.patch_size

    def roundtrip_error(self, latent: list[float], height: int, width: int) -> float:
        back = self.unpack(self.pack(latent, height, width), height, width)
        return max(abs(a - b) for a, b in zip(latent, back))


# ─────────────────────────────────────────────────────────────────────────────
# Image prep
# ─────────────────────────────────────────────────────────────────────────────

RESOLUTION_BUCKETS: tuple[tuple[int, int, float], ...] = (
    (1024, 1024, 1.0),
    (1280, 768, 0.98),
    (768, 1280, 0.98),
    (1440, 720, 1.04),
    (720, 1440, 1.04),
    (1536, 640, 0.98),
    (640, 1536, 0.98),
)


@dataclass
class PreparedImage:
    width: int
    height: int
    crop_x: int = 0
    crop_y: int = 0
    scale: float = 1.0
    megapixels: float = 0.0

    @property
    def aspect_ratio(self) -> float:
        return round(safe_div(self.width, self.height), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "crop": [self.crop_x, self.crop_y],
            "scale": round(self.scale, 4),
            "megapixels": round(self.megapixels, 4),
            "aspect_ratio": self.aspect_ratio,
        }


class ImagePrep:
    """Resolution bucketing, centre-cropping and pixel-limit scaling."""

    MULTIPLE_OF = 16

    def center_crop_to_multiple(self, width: int, height: int, multiple: int = MULTIPLE_OF) -> tuple[int, int, int, int]:
        new_w = (width // multiple) * multiple
        new_h = (height // multiple) * multiple
        crop_x = (width - new_w) // 2
        crop_y = (height - new_h) // 2
        return new_w, new_h, crop_x, crop_y

    def scale_to_limit(self, width: int, height: int, limit_pixels: int) -> float:
        pixels = width * height
        if pixels <= limit_pixels or limit_pixels <= 0:
            return 1.0
        return round(math.sqrt(limit_pixels / pixels), 6)

    def bucket_for(self, width: int, height: int) -> tuple[int, int]:
        target = safe_div(width, height, 1.0)
        best = min(RESOLUTION_BUCKETS, key=lambda b: abs(safe_div(b[0], b[1]) - target))
        return best[0], best[1]

    def prepare(
        self,
        width: int,
        height: int,
        target_megapixels: float = 1.0,
        limit_pixels: int = 1024 ** 2,
    ) -> PreparedImage:
        scale = self.scale_to_limit(width, height, limit_pixels)
        w, h = int(round(width * scale)), int(round(height * scale))
        cropped_w, cropped_h, crop_x, crop_y = self.center_crop_to_multiple(w, h)
        return PreparedImage(
            width=max(self.MULTIPLE_OF, cropped_w),
            height=max(self.MULTIPLE_OF, cropped_h),
            crop_x=crop_x,
            crop_y=crop_y,
            scale=scale,
            megapixels=round(safe_div(cropped_w * cropped_h, 1_000_000.0), 4),
        )

    def fit_to_bucket(self, width: int, height: int, megapixels: float = 1.0) -> PreparedImage:
        bw, bh = self.bucket_for(width, height)
        scale = math.sqrt(megapixels * 1_000_000.0 / (bw * bh))
        return PreparedImage(
            width=int(round(bw * scale / self.MULTIPLE_OF)) * self.MULTIPLE_OF,
            height=int(round(bh * scale / self.MULTIPLE_OF)) * self.MULTIPLE_OF,
            scale=round(scale, 4),
            megapixels=round(megapixels, 4),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Schedules
# ─────────────────────────────────────────────────────────────────────────────


class TimeStepScheduler:
    """FLUX timestep schedule with resolution-dependent shifting."""

    @staticmethod
    def time_shift(mu: float, sigma: float, t: float) -> float:
        """``exp(mu) / (exp(mu) + (1/t - 1) ** sigma)``."""
        t = min(max(t, 1e-6), 1.0)
        mu = min(max(mu, 0.0), 12.0)  # keep exp(mu) finite for direct callers
        return math.exp(mu) / (math.exp(mu) + (1.0 / t - 1.0) ** sigma)

    @staticmethod
    def get_lin_function(
        x1: float = 256.0,
        y1: float = 0.5,
        x2: float = 4096.0,
        y2: float = 1.15,
    ) -> Callable[[float], float]:
        """Linear map from image sequence length to the shift exponent ``mu``."""
        slope = safe_div(y2 - y1, x2 - x1)
        intercept = y1 - slope * x1
        return lambda x: slope * x + intercept

    def get_schedule(
        self,
        num_steps: int,
        image_seq_len: int,
        base_shift: float = 0.5,
        max_shift: float = 1.15,
        shift: bool = True,
    ) -> list[float]:
        """Linearly spaced 1 -> 0 timesteps, optionally mu-shifted by resolution."""
        timesteps = linspace(1.0, 0.0, num_steps + 1)
        if not shift:
            return [round(t, 6) for t in timesteps]
        lin = self.get_lin_function(x1=256.0, y1=base_shift, x2=4096.0, y2=max_shift)
        mu = min(max(lin(image_seq_len), 0.0), 12.0)
        return [round(self.time_shift(mu, 1.0, t), 6) for t in timesteps]

    @staticmethod
    def sigma_to_t(sigma: float) -> float:
        return 1.0 - sigma

    def snr(self, t: float) -> float:
        """Signal-to-noise proxy for a rectified-flow timestep."""
        return round(safe_div(1.0 - t, max(t, 1e-6)), 4)

    def step_sizes(self, timesteps: list[float]) -> list[float]:
        return [round(timesteps[i] - timesteps[i + 1], 6) for i in range(len(timesteps) - 1)]

    def schedule_report(self, timesteps: list[float]) -> dict[str, Any]:
        sizes = self.step_sizes(timesteps)
        return {
            "steps": len(sizes),
            "first": timesteps[0],
            "last": timesteps[-1],
            "monotonic": all(a > b for a, b in zip(timesteps, timesteps[1:])),
            "min_step": min(sizes) if sizes else 0.0,
            "max_step": max(sizes) if sizes else 0.0,
            "mean_step": round(safe_div(sum(sizes), len(sizes)), 6) if sizes else 0.0,
        }


class RectifiedFlowSampler:
    """Euler integrator for a rectified-flow velocity field.

    Upstream::

        img = img + (t_prev - t_curr) * pred

    i.e. the flow matching update where the network predicts the velocity
    ``dx/dt`` and the schedule runs from t=1 (noise) to t=0 (data).
    """

    def step(self, x: list[float], velocity: list[float], t_curr: float, t_prev: float) -> list[float]:
        if len(x) != len(velocity):
            raise ValueError("velocity must match latent length")
        dt = t_prev - t_curr
        return [xi + dt * vi for xi, vi in zip(x, velocity)]

    def run(
        self,
        x: list[float],
        velocity_fn: Callable[[list[float], float, float | None], list[float]],
        timesteps: list[float],
        guidance: float | None = None,
        trace: bool = False,
    ) -> list[float] | tuple[list[float], list[dict[str, Any]]]:
        history: list[dict[str, Any]] = []
        for index, (t_curr, t_prev) in enumerate(zip(timesteps[:-1], timesteps[1:])):
            velocity = velocity_fn(x, t_curr, guidance)
            norm = math.sqrt(sum(v * v for v in velocity)) / max(1, len(velocity))
            x = self.step(x, velocity, t_curr, t_prev)
            if trace:
                history.append(
                    {
                        "step": index,
                        "t_curr": round(t_curr, 5),
                        "t_prev": round(t_prev, 5),
                        "dt": round(t_prev - t_curr, 5),
                        "velocity_norm": round(norm, 6),
                        "x_norm": round(math.sqrt(sum(v * v for v in x)) / max(1, len(x)), 6),
                    }
                )
        return (x, history) if trace else x

    def run_with_conditioning(
        self,
        x: list[float],
        velocity_fn: Callable[[list[float], float, float | None], list[float]],
        timesteps: list[float],
        guidance: float | None = None,
        cond_tokens: int = 0,
    ) -> list[float]:
        """Upstream ``denoise``: reference tokens are appended for the forward
        pass and the prediction is truncated back to the image tokens."""
        for t_curr, t_prev in zip(timesteps[:-1], timesteps[1:]):
            velocity = velocity_fn(x, t_curr, guidance)
            if cond_tokens:
                velocity = velocity[: len(x)]
            x = self.step(x, velocity, t_curr, t_prev)
        return x


class ClassifierFreeGuidance:
    """``x = x_uncond + guidance * (x_cond - x_uncond)`` (upstream
    ``vanilla_guidance`` / the CFG branch of ``denoise_cfg``)."""

    @staticmethod
    def combine(x_uncond: list[float], x_cond: list[float], guidance: float) -> list[float]:
        if len(x_uncond) != len(x_cond):
            raise ValueError("uncond and cond predictions must match")
        return [u + guidance * (c - u) for u, c in zip(x_uncond, x_cond)]

    def run_cfg(
        self,
        x: list[float],
        velocity_fn: Callable[[list[float], float, float | None], list[float]],
        timesteps: list[float],
        guidance: float = 4.0,
    ) -> list[float]:
        sampler = RectifiedFlowSampler()
        for t_curr, t_prev in zip(timesteps[:-1], timesteps[1:]):
            v_uncond = velocity_fn(x, t_curr, None)
            v_cond = velocity_fn(x, t_curr, guidance)
            velocity = self.combine(v_uncond, v_cond, guidance)
            x = sampler.step(x, velocity, t_curr, t_prev)
        return x

    @staticmethod
    def effective_guidance(guidance: float, t: float) -> float:
        """Guidance is usually most useful early; rescale by timestep."""
        return round(guidance * clamp(t * 1.2), 4)

    @staticmethod
    def batch_cost(num_steps: int, tokens: int, use_cfg: bool) -> dict[str, int]:
        passes = num_steps * (2 if use_cfg else 1)
        return {"forward_passes": passes, "tokens_processed": passes * tokens}


# ─────────────────────────────────────────────────────────────────────────────
# Position ids
# ─────────────────────────────────────────────────────────────────────────────


class PositionIdGrid:
    """``(t, h, w, l)`` position ids used by FLUX.2's packed sequence."""

    @staticmethod
    def prc_img(height: int, width: int, t_coord: int = 0) -> list[tuple[int, int, int, int]]:
        return [(t_coord, y, x, 0) for y in range(height) for x in range(width)]

    @staticmethod
    def prc_txt(length: int, t_coord: int = 0) -> list[tuple[int, int, int, int]]:
        return [(t_coord, 0, 0, i) for i in range(length)]

    @staticmethod
    def compress_time(t_ids: list[int]) -> list[int]:
        """Map scattered time ids onto a dense 0..n-1 range (upstream helper)."""
        unique = sorted(set(t_ids))
        remap = {value: index for index, value in enumerate(unique)}
        return [remap[t] for t in t_ids]

    @staticmethod
    def scatter_ids(values: list[tuple[float, ...]], ids: list[tuple[int, int, int, int]]) -> list[float]:
        """Place packed tokens back into a dense ``(t*h*w)`` grid."""
        if not ids:
            return []
        t_ids = PositionIdGrid.compress_time([i[0] for i in ids])
        h_ids = [i[1] for i in ids]
        w_ids = [i[2] for i in ids]
        t = max(t_ids) + 1
        h = max(h_ids) + 1
        w = max(w_ids) + 1
        channels = len(values[0]) if values else 1
        out = [0.0] * (t * h * w * channels)
        for value, tid, hid, wid in zip(values, t_ids, h_ids, w_ids):
            base = (tid * h * w + hid * w + wid) * channels
            for c in range(channels):
                out[base + c] = value[c] if c < len(value) else 0.0
        return out

    @staticmethod
    def concat(primary: list[tuple[int, int, int, int]], extra: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        return list(primary) + list(extra)


# ─────────────────────────────────────────────────────────────────────────────
# Reference images (editing) + KV cache
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ReferenceImageStack:
    """Multi-reference conditioning with per-image time offsets.

    Upstream ``encode_image_refs`` uses ``t_off = scale + scale * i`` with
    ``scale = 10`` so each reference image occupies its own time coordinate,
    and limits each reference to ``1024**2`` pixels (``2024**2`` for a single
    reference).
    """

    scale: int = 10
    count: int = 0

    @property
    def time_offsets(self) -> list[int]:
        return [self.scale + self.scale * i for i in range(self.count)]

    @property
    def limit_pixels(self) -> int | None:
        if self.count > 1:
            return 1024 ** 2
        if self.count == 1:
            return 2024 ** 2
        return None

    def token_plan(self, ref_token_counts: list[int]) -> dict[str, Any]:
        self.count = len(ref_token_counts)
        return {
            "references": self.count,
            "time_offsets": self.time_offsets,
            "limit_pixels": self.limit_pixels,
            "tokens_per_reference": ref_token_counts,
            "total_reference_tokens": sum(ref_token_counts),
        }

    @staticmethod
    def kv_cache_plan(num_steps: int, image_tokens: int, reference_tokens: int) -> dict[str, Any]:
        """``denoise_cached`` computes reference KV once and reuses it."""
        naive = num_steps * (image_tokens + reference_tokens) ** 2
        cached = (image_tokens + reference_tokens) ** 2 + (num_steps - 1) * image_tokens ** 2
        return {
            "steps": num_steps,
            "image_tokens": image_tokens,
            "reference_tokens": reference_tokens,
            "attention_units_naive": naive,
            "attention_units_cached": cached,
            "speedup": round(safe_div(naive, cached), 4),
            "saved_fraction": round(1.0 - safe_div(cached, naive), 4),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Prompt upsampling
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_MESSAGES: dict[str, str] = {
    "simple": (
        "You are a prompt engineer. Rewrite the user's prompt to be more descriptive and "
        "specific, preserving intent. Keep it under 80 words."
    ),
    "short": (
        "Expand the user's prompt with concrete visual detail: subject, setting, lighting, "
        "lens and mood. Under 120 words."
    ),
    "detailed": (
        "You are an expert image-prompt writer. Rewrite the prompt with rich detail: subject, "
        "composition, camera, optics, lighting, palette, texture, mood and style. Under 200 words."
    ),
    "edit": (
        "You are an image-editing prompt writer. Describe the final image and name every change "
        "to apply to the reference image. Preserve what must not change."
    ),
}


class PromptUpsampler:
    """Prompt upsampling front-end (upstream ``system_messages.py``)."""

    def __init__(self, mode: str = "short", max_prompt_tokens: int = 512):
        self.mode = mode if mode in SYSTEM_MESSAGES else "short"
        self.max_prompt_tokens = max_prompt_tokens

    @property
    def system_message(self) -> str:
        return SYSTEM_MESSAGES[self.mode]

    @staticmethod
    def estimate_tokens(prompt: str) -> int:
        words = re.findall(r"\w+|[^\w\s]", prompt or "")
        return max(1, int(round(len(words) * 1.3)))

    def needs_upsampling(self, prompt: str) -> bool:
        tokens = self.estimate_tokens(prompt)
        return tokens < 24 or len((prompt or "").split()) < 8

    def build_messages(self, prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": f"Prompt: {prompt}\nRewritten prompt:"},
        ]

    def upsample(self, prompt: str, descriptors: dict[str, str] | None = None) -> str:
        """Deterministic offline upsampler: appends missing visual descriptors.

        With a real LLM the messages above are sent to the model; offline we
        expand the prompt with the descriptor set so behaviour stays testable.
        """
        descriptors = descriptors or {
            "lighting": "soft directional light",
            "camera": "shot on 35mm",
            "mood": "cinematic, high detail",
        }
        tokens = self.estimate_tokens(prompt)
        if not self.needs_upsampling(prompt):
            return prompt
        lowered = (prompt or "").lower()
        parts: list[str] = []
        for key, value in descriptors.items():
            if key not in lowered and value.split()[-1] not in lowered:
                parts.append(value)
        suffix = ", ".join(parts)
        upsampled = f"{prompt.strip()}, {suffix}" if suffix else prompt.strip()
        return upsampled

    def report(self, prompt: str) -> dict[str, Any]:
        tokens = self.estimate_tokens(prompt)
        return {
            "mode": self.mode,
            "tokens": tokens,
            "words": len((prompt or "").split()),
            "needs_upsampling": self.needs_upsampling(prompt),
            "within_budget": tokens <= self.max_prompt_tokens,
            "messages": len(self.build_messages(prompt)),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Watermark
# ─────────────────────────────────────────────────────────────────────────────


def _dft2(block: list[list[float]]) -> list[list[complex]]:
    height, width = len(block), len(block[0])
    out: list[list[complex]] = []
    for ky in range(height):
        row: list[complex] = []
        for kx in range(width):
            acc = 0j
            for y in range(height):
                for x in range(width):
                    angle = -2 * math.pi * ((ky * y / height) + (kx * x / width))
                    acc += block[y][x] * cmath.exp(1j * angle)
            row.append(acc)
        out.append(row)
    return out


def _idft2(spectrum: list[list[complex]]) -> list[list[float]]:
    height, width = len(spectrum), len(spectrum[0])
    out: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            acc = 0j
            for ky in range(height):
                for kx in range(width):
                    angle = 2 * math.pi * ((ky * y / height) + (kx * x / width))
                    acc += spectrum[ky][kx] * cmath.exp(1j * angle)
            row.append((acc / (height * width)).real)
        out.append(row)
    return out


class WatermarkEncoder:
    """Invisible mid-frequency Fourier watermark (upstream ``watermark.py``).

    Implemented as dither-modulation QIM (quantization index modulation) in the
    mid-band magnitudes of ``block_size x block_size`` DCT-like blocks:

    * a keyed pseudo-random bit sequence selects one of two dithered lattices
      per frequency slot;
    * the magnitude pair ``|F(u,v)|`` / ``|F(-u,-v)|`` is quantised together so
      conjugate symmetry (and therefore a real-valued image) is preserved;
    * detection needs no original: the per-slot quantisation residual is
      compared against the keyed lattice offset.

    Mid-band only: low frequencies carry the visible structure, high
    frequencies are where compression noise lives.
    """

    def __init__(
        self,
        block_size: int = 8,
        strength: float = 6.0,
        relative: float = 0.002,
        low_band: int = 1,
        high_band: int = 5,
    ):
        self.block_size = block_size
        self.strength = strength
        self.relative = relative
        self.low_band = low_band
        self.high_band = high_band

    # -- key material ------------------------------------------------------
    def pattern(self, key: str, size: int | None = None) -> list[float]:
        """Deterministic, zero-mean, unit-norm pattern derived from ``key``."""
        size = size or self.block_size
        seed = hashlib.sha256((key or "flux2").encode("utf-8")).digest()
        raw: list[float] = []
        while len(raw) < size * size:
            seed = hashlib.sha256(seed).digest()
            raw.extend(b / 255.0 - 0.5 for b in seed)
        values = raw[: size * size]
        mean = safe_div(sum(values), len(values))
        centered = [v - mean for v in values]
        norm = math.sqrt(sum(v * v for v in centered)) or 1.0
        return [v / norm for v in centered]

    def bits(self, key: str, size: int | None = None) -> list[int]:
        return [1 if value > 0 else 0 for value in self.pattern(key, size)]

    # -- band geometry -----------------------------------------------------
    def _radius(self, ky: int, kx: int, size: int) -> float:
        return math.hypot(min(ky, size - ky), min(kx, size - kx))

    def _is_mid_band(self, ky: int, kx: int, size: int | None = None) -> bool:
        size = size or self.block_size
        return self.low_band <= self._radius(ky, kx, size) <= self.high_band

    def pairs(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Canonical conjugate-symmetric mid-band pairs, in stable order."""
        size = self.block_size
        out: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for ky in range(size):
            for kx in range(size):
                mirror = ((-ky) % size, (-kx) % size)
                if (ky, kx) >= mirror:
                    continue
                if self._is_mid_band(ky, kx, size):
                    out.append(((ky, kx), mirror))
        return out

    @property
    def slots_per_block(self) -> int:
        return len(self.pairs())

    # -- quantisation ------------------------------------------------------
    def step_for(self, block_dc: float) -> float:
        """Lattice step for a block.

        Derived from the block's DC magnitude, which the watermark never
        touches, so the encoder and the blind detector agree on the step
        without sharing the original image.
        """
        return max(self.strength, self.relative * block_dc)

    @staticmethod
    def _offset(bit: int) -> float:
        """Lattice offset for a bit: -0.25 or +0.25 of a step."""
        return (bit - 0.5) * 0.5

    @staticmethod
    def quantize(magnitude: float, step: float, bit: int) -> float:
        offset = WatermarkEncoder._offset(bit) * step
        quantised = math.floor((magnitude - offset) / step + 0.5) * step + offset
        return max(0.0, quantised)

    @staticmethod
    def residual(magnitude: float, step: float) -> float:
        """Signed distance of ``magnitude`` from the un-dithered lattice, in steps."""
        return magnitude / step - math.floor(magnitude / step + 0.5)

    # -- embed / extract ---------------------------------------------------
    def embed(self, image: list[list[float]], key: str = "flux2") -> list[list[float]]:
        size = self.block_size
        bits = self.bits(key, size)
        pairs = self.pairs()
        height, width = len(image), len(image[0])
        out = [row[:] for row in image]
        for by in range(0, height - size + 1, size):
            for bx in range(0, width - size + 1, size):
                block = [row[bx : bx + size] for row in image[by : by + size]]
                spectrum = _dft2(block)
                step = self.step_for(abs(spectrum[0][0]))
                for index, ((ky, kx), (my, mx)) in enumerate(pairs):
                    bit = bits[index % len(bits)]
                    magnitude = (abs(spectrum[ky][kx]) + abs(spectrum[my][mx])) / 2.0
                    quantised = self.quantize(magnitude, step, bit)
                    phase = cmath.phase(spectrum[ky][kx])
                    spectrum[ky][kx] = cmath.rect(quantised, phase)
                    spectrum[my][mx] = cmath.rect(quantised, -phase)
                patched = _idft2(spectrum)
                for y in range(size):
                    for x in range(size):
                        out[by + y][bx + x] = clamp(patched[y][x], 0.0, 255.0)
        return out

    def extract(self, image: list[list[float]]) -> list[float]:
        """Per-slot quantisation residual, expressed in lattice steps."""
        return [value for value, _ in self.extract_weighted(image)]

    def extract_weighted(self, image: list[list[float]]) -> list[tuple[float, float]]:
        """Residual plus a reliability weight for every slot.

        Coefficients far below one lattice step survive quantisation badly (the
        residual is pure reconstruction noise there), so each slot is weighted
        by ``min(1, magnitude / step)`` before the detector averages.
        """
        size = self.block_size
        pairs = self.pairs()
        height, width = len(image), len(image[0])
        out: list[tuple[float, float]] = []
        for by in range(0, height - size + 1, size):
            for bx in range(0, width - size + 1, size):
                block = [row[bx : bx + size] for row in image[by : by + size]]
                spectrum = _dft2(block)
                step = self.step_for(abs(spectrum[0][0]))
                for (ky, kx), (my, mx) in pairs:
                    magnitude = (abs(spectrum[ky][kx]) + abs(spectrum[my][mx])) / 2.0
                    out.append((self.residual(magnitude, step), clamp(magnitude / step)))
        return out

    @staticmethod
    def psnr(original: list[list[float]], modified: list[list[float]]) -> float:
        flat_a = [v for row in original for v in row]
        flat_b = [v for row in modified for v in row]
        mse = safe_div(sum((a - b) ** 2 for a, b in zip(flat_a, flat_b)), len(flat_a), 0.0)
        if mse <= 0:
            return 99.0
        return round(10 * math.log10(255.0 ** 2 / mse), 3)


class WatermarkDetector:
    """Blind detector for :class:`WatermarkEncoder`.

    Averages ``cos(2*pi*(residual - expected_offset))`` over every slot: a
    watermarked image with the right key scores near 1.0, everything else
    (unwatermarked or wrong key) hovers around 0.
    """

    def __init__(self, encoder: WatermarkEncoder | None = None, threshold: float = 0.35):
        self.encoder = encoder or WatermarkEncoder()
        self.threshold = threshold

    def score(self, image: list[list[float]], key: str = "flux2") -> float:
        """Reliability-weighted mean agreement with the keyed lattice."""
        slots = self.encoder.extract_weighted(image)
        if not slots:
            return 0.0
        bits = self.encoder.bits(key, self.encoder.block_size)
        per_block = self.encoder.slots_per_block or len(bits)
        total = 0.0
        weight_sum = 0.0
        for index, (value, weight) in enumerate(slots):
            # The bit sequence restarts every block (embed indexes within a block).
            expected = self.encoder._offset(bits[index % per_block % len(bits)])
            total += weight * math.cos(2 * math.pi * (value - expected))
            weight_sum += weight
        if weight_sum <= 0:
            return 0.0
        return round(total / weight_sum, 4)

    def detect(self, image: list[list[float]], key: str = "flux2") -> dict[str, Any]:
        score = self.score(image, key)
        return {
            "score": score,
            "threshold": self.threshold,
            "detected": score >= self.threshold,
            "slots": len(self.encoder.extract(image)),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class GenerationResult:
    prompt: str
    width: int
    height: int
    steps: int
    guidance: float
    latent: list[float]
    timesteps: list[float]
    tokens: int
    digest: str
    trace: list[dict[str, Any]] = field(default_factory=list)
    watermark: dict[str, Any] = field(default_factory=dict)

    @property
    def latent_stats(self) -> dict[str, float]:
        if not self.latent:
            return {}
        mean = safe_div(sum(self.latent), len(self.latent))
        var = safe_div(sum((v - mean) ** 2 for v in self.latent), len(self.latent))
        return {"mean": round(mean, 6), "std": round(math.sqrt(var), 6), "min": round(min(self.latent), 6), "max": round(max(self.latent), 6)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt[:80],
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "guidance": self.guidance,
            "tokens": self.tokens,
            "latent_dims": len(self.latent),
            "latent_stats": self.latent_stats,
            "digest": self.digest,
            "watermark": self.watermark,
        }


class Flux2Pipeline:
    """End-to-end FLUX.2-style generation with an injected velocity model."""

    def __init__(
        self,
        ae: Flux2AutoEncoderParams | None = None,
        packer: LatentPacker | None = None,
        prep: ImagePrep | None = None,
        scheduler: TimeStepScheduler | None = None,
        upsampler: PromptUpsampler | None = None,
        watermark: WatermarkEncoder | None = None,
        seed: int = 0,
    ):
        self.ae = ae or Flux2AutoEncoderParams()
        self.packer = packer or LatentPacker(patch_size=self.ae.patch_size, z_channels=self.ae.z_channels)
        self.prep = prep or ImagePrep()
        self.scheduler = scheduler or TimeStepScheduler()
        self.upsampler = upsampler or PromptUpsampler()
        self.watermark = watermark or WatermarkEncoder(strength=18.0)
        self.seed = seed

    @staticmethod
    def _seed_state(seed: int | str | None) -> int:
        """Accept an int seed or hash a string seed into a 31-bit state."""
        if seed is None:
            return 1
        if isinstance(seed, str):
            digest = hashlib.sha256(seed.encode()).digest()
            return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
        return int(seed) or 1

    def noise(self, size: int, seed: int | str | None = None) -> list[float]:
        """Deterministic Gaussian-ish noise (Box-Muller from a hashed seed)."""
        seed = self.seed if seed is None else seed
        state = self._seed_state(seed)

        def next_random() -> float:
            nonlocal state
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            return state / 0x7FFFFFFF

        out: list[float] = []
        while len(out) < size:
            u1 = max(1e-9, next_random())
            u2 = next_random()
            radius = math.sqrt(-2.0 * math.log(u1))
            out.append(radius * math.cos(2 * math.pi * u2))
            if len(out) < size:
                out.append(radius * math.sin(2 * math.pi * u2))
        return out[:size]

    def prepare_latent(self, height: int, width: int, seed: int | None = None) -> dict[str, Any]:
        prepared = self.prep.prepare(width, height)
        c, lh, lw = self.ae.latent_shape(prepared.width, prepared.height)
        size = c * lh * lw
        latent = self.noise(size, seed)
        tokens = self.packer.pack(latent, lh, lw)
        return {
            "prepared": prepared.to_dict(),
            "latent_shape": (c, lh, lw),
            "latent_values": size,
            "token_count": self.ae.token_count(prepared.width, prepared.height),
            "latent": latent,
            "tokens": tokens,
            "compression_ratio": self.ae.compression_ratio(prepared.width, prepared.height),
        }

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        steps: int = 8,
        guidance: float = 4.0,
        seed: int | None = None,
        velocity_fn: Callable[[list[float], float, float | None], list[float]] | None = None,
        use_cfg: bool = False,
        image: list[list[float]] | None = None,
    ) -> GenerationResult:
        if steps < 1:
            raise ValueError("steps must be >= 1")
        prepared_latent = self.prepare_latent(height, width, seed)
        tokens = prepared_latent["token_count"]
        timesteps = self.scheduler.get_schedule(steps, tokens)
        latent = prepared_latent["latent"]

        def default_velocity(x: list[float], t: float, g: float | None) -> list[float]:
            # Analytic rectified-flow velocity towards a prompt-conditioned target
            # so the pipeline is exercisable without a transformer.
            target_seed = hashlib.sha256(f"{prompt}|{len(x)}".encode()).digest()
            scale = 1.0 if g is None else 1.0 + 0.05 * g
            return [
                (target_seed[i % len(target_seed)] / 255.0 - 0.5) * 2.0 * scale - xi * 0.05
                for i, xi in enumerate(x)
            ]

        model = velocity_fn or default_velocity
        if use_cfg:
            final = ClassifierFreeGuidance().run_cfg(latent, model, timesteps, guidance)
            trace: list[dict[str, Any]] = []
        else:
            final, trace = RectifiedFlowSampler().run(latent, model, timesteps, guidance=None, trace=True)

        watermark_info: dict[str, Any] = {}
        if image is not None:
            marked = self.watermark.embed(image, key=prompt[:32] or "flux2")
            watermark_info = {
                **WatermarkDetector(self.watermark).detect(marked, key=prompt[:32] or "flux2"),
                "psnr": self.watermark.psnr(image, marked),
            }

        digest = hashlib.sha256(
            f"{prompt}|{width}x{height}|{steps}|{guidance}|{len(final)}|{prepared_latent['token_count']}".encode()
        ).hexdigest()
        return GenerationResult(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps,
            guidance=guidance,
            latent=[round(v, 6) for v in final],
            timesteps=timesteps,
            tokens=tokens,
            digest=digest[:16],
            trace=trace,
            watermark=watermark_info,
        )

    def plan(self, prompt: str, width: int = 1024, height: int = 1024, steps: int = 8, guidance: float = 4.0) -> dict[str, Any]:
        """Cost/geometry plan for a generation request."""
        prepared_latent = self.prepare_latent(height, width)
        tokens = prepared_latent["token_count"]
        return {
            "prompt": self.upsampler.report(prompt),
            "upsampled_prompt": self.upsampler.upsample(prompt),
            "resolution": prepared_latent["prepared"],
            "latent_shape": prepared_latent["latent_shape"],
            "tokens": tokens,
            "compression_ratio": prepared_latent["compression_ratio"],
            "schedule": self.scheduler.schedule_report(self.scheduler.get_schedule(steps, tokens)),
            "cost": ClassifierFreeGuidance.batch_cost(steps, tokens, use_cfg=guidance > 1.0),
        }
