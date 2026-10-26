"""
VyralX Deep Layer 12 — Real OpenCreator Workspace Engine

Real repository integration:
    krillinai/OpenCreator (formerly KrillinAI)
    Upstream: https://github.com/krillinai/OpenCreator

OpenCreator is an AI workspace for creators: reusable Skills (scripts, video,
images, voice, translation, editing), visual *presets*, and provider-agnostic
media profiles, all driven by an agent. The parts that are logic rather than
plumbing are ported here:

* :class:`CreatorPreset` / :class:`PresetRegistry` — the visual settings that
  define a delivery target (aspect, resolution, fps, bitrates).
* :class:`MediaProfile` / :class:`MediaProfileRegistry` — the provider/model
  catalogue (image, voice, video, avatar) with cost, latency and capability
  metadata, mirroring ``apps/daemon/scripts/*-profiles.ts``.
* :class:`ProviderScorer` — weighted, explainable provider selection instead of
  "first available".
* :class:`PipelineStage` / :class:`PipelineDAG` — dependency-ordered execution
  with parallel batches and cycle detection.
* :class:`DubbingPipeline` — subtitle timing, translation, isochronous speech
  rate fitting (the core of OpenCreator's dubbing feature).
* :class:`ShotPromptBuilder` — deterministic shot prompts with seeds and
  negative prompts.
* :class:`BatchJobPlanner` / :class:`RetryPolicy` — batch rendering with
  exponential backoff.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def timestamp_srt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def timestamp_vtt(seconds: float) -> str:
    return timestamp_srt(seconds).replace(",", ".")


# ─────────────────────────────────────────────────────────────────────────────
# Presets
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CreatorPreset:
    """A delivery target: aspect ratio, resolution, frame rate, bitrates."""

    name: str
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    video_bitrate_kbps: int = 8000
    audio_bitrate_kbps: int = 192
    audio_sample_rate: int = 44100
    language: str = "en"
    platform: str = "youtube"

    @property
    def aspect_ratio(self) -> float:
        return round(safe_div(self.width, self.height), 4)

    @property
    def orientation(self) -> str:
        if self.aspect_ratio > 1.05:
            return "landscape"
        if self.aspect_ratio < 0.95:
            return "vertical"
        return "square"

    @property
    def megapixels(self) -> float:
        return round(safe_div(self.width * self.height, 1_000_000.0), 3)

    @property
    def is_short_form(self) -> bool:
        return self.orientation == "vertical"

    def bitrate_for_duration(self, duration_s: float) -> int:
        """Total bytes implied by the bitrates for a clip of ``duration_s``."""
        total_bits = (self.video_bitrate_kbps + self.audio_bitrate_kbps) * 1000 * duration_s
        return int(round(total_bits / 8))

    def estimate_size_mb(self, duration_s: float) -> float:
        return round(self.bitrate_for_duration(duration_s) / (1024 * 1024), 2)

    def scale_args(self) -> str:
        return f"scale={self.width}:{self.height}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "resolution": f"{self.width}x{self.height}",
            "aspect_ratio": self.aspect_ratio,
            "orientation": self.orientation,
            "fps": self.fps,
            "video_bitrate_kbps": self.video_bitrate_kbps,
            "audio_bitrate_kbps": self.audio_bitrate_kbps,
            "megapixels": self.megapixels,
            "language": self.language,
            "platform": self.platform,
        }


class PresetRegistry:
    """The presets OpenCreator ships for the main social platforms."""

    PRESETS: tuple[CreatorPreset, ...] = (
        CreatorPreset("youtube_1080p", 1920, 1080, 30.0, 8000, 192, 44100, "en", "youtube"),
        CreatorPreset("youtube_4k", 3840, 2160, 30.0, 45000, 256, 48000, "en", "youtube"),
        CreatorPreset("youtube_shorts", 1080, 1920, 30.0, 6000, 192, 44100, "en", "youtube"),
        CreatorPreset("tiktok", 1080, 1920, 30.0, 6000, 160, 44100, "en", "tiktok"),
        CreatorPreset("instagram_reel", 1080, 1920, 30.0, 6000, 160, 44100, "en", "instagram"),
        CreatorPreset("instagram_square", 1080, 1080, 30.0, 5000, 160, 44100, "en", "instagram"),
        CreatorPreset("x_landscape", 1280, 720, 30.0, 5000, 128, 44100, "en", "x"),
        CreatorPreset("linkedin", 1920, 1080, 30.0, 6000, 160, 44100, "en", "linkedin"),
    )

    def __init__(self):
        self._presets = {p.name: p for p in self.PRESETS}

    def get(self, name: str) -> CreatorPreset:
        if name not in self._presets:
            raise KeyError(f"unknown preset: {name}")
        return self._presets[name]

    def names(self) -> list[str]:
        return sorted(self._presets)

    def for_platform(self, platform: str, short_form: bool = False) -> CreatorPreset:
        candidates = [p for p in self.PRESETS if p.platform == platform]
        if short_form:
            candidates = [p for p in candidates if p.is_short_form] or candidates
        return candidates[0] if candidates else self.get("youtube_1080p")

    def add(self, preset: CreatorPreset) -> CreatorPreset:
        self._presets[preset.name] = preset
        return preset


# ─────────────────────────────────────────────────────────────────────────────
# Media profiles + provider scoring
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MediaProfile:
    """One provider/model combination for a media kind."""

    profile_id: str
    kind: str  # image | voice | video | avatar | llm
    provider: str
    model: str
    quality: float = 0.7          # 0-1 expected fidelity
    control: float = 0.5          # reference/style directability
    reliability: float = 0.9
    latency_ms: int = 3000
    cost_per_unit: float = 0.01   # per image / per second / per 1k chars
    unit: str = "image"           # image | second | char
    max_duration_s: float = 0.0   # 0 = unlimited
    supports_reference: bool = False
    supports_style: bool = False
    notes: str = ""

    def cost_for(self, amount: float = 1.0) -> float:
        return round(self.cost_per_unit * amount, 4)

    def fits_duration(self, duration_s: float) -> bool:
        return self.max_duration_s <= 0 or duration_s <= self.max_duration_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "kind": self.kind,
            "provider": self.provider,
            "model": self.model,
            "quality": self.quality,
            "control": self.control,
            "reliability": self.reliability,
            "latency_ms": self.latency_ms,
            "cost_per_unit": self.cost_per_unit,
            "unit": self.unit,
            "max_duration_s": self.max_duration_s,
            "supports_reference": self.supports_reference,
        }


class MediaProfileRegistry:
    """Catalogue of media profiles (mirrors the OpenCreator profile scripts)."""

    PROFILES: tuple[MediaProfile, ...] = (
        MediaProfile("img_flux2_dev", "image", "bfl", "flux2-dev", quality=0.94, control=0.9,
                     reliability=0.93, latency_ms=9000, cost_per_unit=0.04, supports_reference=True, supports_style=True),
        MediaProfile("img_flux2_klein", "image", "bfl", "flux2-klein-4b", quality=0.86, control=0.85,
                     reliability=0.95, latency_ms=1500, cost_per_unit=0.008, supports_reference=True, supports_style=True),
        MediaProfile("img_sdxl", "image", "fal", "sdxl-lightning", quality=0.74, control=0.7,
                     reliability=0.9, latency_ms=1200, cost_per_unit=0.003, supports_reference=True),
        MediaProfile("voice_omnivoice", "voice", "local", "k2-fsa/omnivoice", quality=0.85, control=0.8,
                     reliability=0.86, latency_ms=600, cost_per_unit=0.0, unit="char", supports_reference=True),
        MediaProfile("voice_chirp3", "voice", "google", "chirp3-hd", quality=0.93, control=0.6,
                     reliability=0.95, latency_ms=900, cost_per_unit=0.000016, unit="char"),
        MediaProfile("voice_openai", "voice", "openai", "gpt-4o-mini-tts", quality=0.9, control=0.75,
                     reliability=0.96, latency_ms=1100, cost_per_unit=0.000015, unit="char"),
        MediaProfile("video_kling", "video", "fal", "kling-v3", quality=0.92, control=0.8,
                     reliability=0.88, latency_ms=180000, cost_per_unit=0.28, unit="second", max_duration_s=10.0),
        MediaProfile("video_veo", "video", "google", "veo-3", quality=0.95, control=0.85,
                     reliability=0.9, latency_ms=240000, cost_per_unit=0.5, unit="second", max_duration_s=8.0),
        MediaProfile("video_animatediff", "video", "local", "animatediff-lightning", quality=0.7, control=0.6,
                     reliability=0.85, latency_ms=45000, cost_per_unit=0.0, unit="second", max_duration_s=4.0),
        MediaProfile("avatar_heygen", "avatar", "heygen", "avatar-iv", quality=0.93, control=0.7,
                     reliability=0.9, latency_ms=120000, cost_per_unit=0.35, unit="second", supports_reference=True),
    )

    def __init__(self):
        self._profiles = {p.profile_id: p for p in self.PROFILES}

    def get(self, profile_id: str) -> MediaProfile:
        if profile_id not in self._profiles:
            raise KeyError(f"unknown media profile: {profile_id}")
        return self._profiles[profile_id]

    def by_kind(self, kind: str) -> list[MediaProfile]:
        return [p for p in self._profiles.values() if p.kind == kind]

    def all(self) -> list[MediaProfile]:
        return [self._profiles[k] for k in sorted(self._profiles)]

    def add(self, profile: MediaProfile) -> MediaProfile:
        self._profiles[profile.profile_id] = profile
        return profile


@dataclass
class ProviderScore:
    """Weighted score of one provider against one task context."""

    profile: MediaProfile
    task_fit: float = 0.0
    output_quality: float = 0.0
    control: float = 0.0
    reliability: float = 0.0
    cost_efficiency: float = 0.0
    latency: float = 0.0
    continuity: float = 0.0

    WEIGHTS = {
        "task_fit": 0.30,
        "output_quality": 0.20,
        "control": 0.15,
        "reliability": 0.15,
        "cost_efficiency": 0.10,
        "latency": 0.05,
        "continuity": 0.05,
    }

    @property
    def weighted_score(self) -> float:
        return sum(getattr(self, key) * weight for key, weight in self.WEIGHTS.items())

    def parts(self) -> dict[str, float]:
        return {key: round(getattr(self, key), 4) for key in self.WEIGHTS}

    def explain(self) -> str:
        ranked = sorted(
            ((name, getattr(self, name), weight) for name, weight in self.WEIGHTS.items()),
            key=lambda row: row[1] * row[2],
            reverse=True,
        )
        top = ", ".join(f"{name}={value:.2f} (w={weight})" for name, value, weight in ranked[:3])
        return f"{self.profile.profile_id}: {self.weighted_score:.3f} — {top}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile.profile_id,
            "provider": self.profile.provider,
            "kind": self.profile.kind,
            "parts": self.parts(),
            "weighted_score": round(self.weighted_score, 4),
        }


class ProviderScorer:
    """Explainable provider selection: never just 'first available'."""

    def __init__(self, budget_usd: float = 5.0, max_latency_ms: int = 120_000):
        self.budget_usd = budget_usd
        self.max_latency_ms = max_latency_ms
        self.locked_provider: str | None = None

    def _cost_efficiency(self, profile: MediaProfile, amount: float) -> float:
        cost = profile.cost_for(amount)
        if cost <= 0:
            return 1.0
        return clamp01(1.0 - math.log1p(cost / max(self.budget_usd, 0.01)) / math.log1p(2.0))

    def _latency(self, profile: MediaProfile) -> float:
        if profile.latency_ms <= self.max_latency_ms / 10:
            return 1.0
        return clamp01(1.0 - math.log1p(profile.latency_ms / max(self.max_latency_ms, 1)) / math.log1p(10.0))

    def _continuity(self, profile: MediaProfile) -> float:
        if self.locked_provider is None:
            return 0.5
        return 1.0 if profile.provider == self.locked_provider else 0.15

    def score(
        self,
        profile: MediaProfile,
        requirement: str = "image",
        needs_reference: bool = False,
        duration_s: float = 0.0,
        amount: float = 1.0,
    ) -> ProviderScore:
        kind_fit = 1.0 if profile.kind == requirement else 0.0
        capability = 1.0
        if needs_reference and not profile.supports_reference:
            capability *= 0.35
        if duration_s and not profile.fits_duration(duration_s):
            capability = 0.0
        return ProviderScore(
            profile=profile,
            task_fit=round(kind_fit * capability, 4),
            output_quality=clamp01(profile.quality),
            control=clamp01(profile.control if needs_reference else (profile.control + 0.2)),
            reliability=clamp01(profile.reliability),
            cost_efficiency=round(self._cost_efficiency(profile, amount), 4),
            latency=round(self._latency(profile), 4),
            continuity=round(self._continuity(profile), 4),
        )

    def rank(
        self,
        profiles: list[MediaProfile],
        requirement: str = "image",
        needs_reference: bool = False,
        duration_s: float = 0.0,
        amount: float = 1.0,
    ) -> list[ProviderScore]:
        scored = [self.score(p, requirement, needs_reference, duration_s, amount) for p in profiles]
        scored.sort(key=lambda s: s.weighted_score, reverse=True)
        return scored

    def choose(
        self,
        registry: MediaProfileRegistry,
        requirement: str,
        needs_reference: bool = False,
        duration_s: float = 0.0,
        amount: float = 1.0,
    ) -> dict[str, Any]:
        ranked = self.rank(registry.by_kind(requirement), requirement, needs_reference, duration_s, amount)
        if not ranked:
            raise KeyError(f"no profiles for requirement: {requirement}")
        best = ranked[0]
        return {
            "requirement": requirement,
            "selected": best.to_dict(),
            "explanation": best.explain(),
            "runners_up": [s.to_dict() for s in ranked[1:3]],
            "estimated_cost_usd": round(best.profile.cost_for(amount), 4),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline DAG
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PipelineStage:
    """One unit of work in a creator pipeline."""

    stage_id: str
    kind: str  # download | transcribe | translate | tts | image | video | edit | render
    depends_on: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | completed | failed | skipped
    attempts: int = 0
    duration_ms: int = 0
    output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "kind": self.kind,
            "depends_on": list(self.depends_on),
            "status": self.status,
            "attempts": self.attempts,
            "duration_ms": self.duration_ms,
            "params": self.params,
        }


class PipelineDAG:
    """Dependency graph with topological batching and cycle detection."""

    def __init__(self):
        self.stages: dict[str, PipelineStage] = {}

    def add(self, stage: PipelineStage) -> PipelineStage:
        self.stages[stage.stage_id] = stage
        return stage

    def validate(self) -> list[str]:
        problems: list[str] = []
        for stage in self.stages.values():
            for dep in stage.depends_on:
                if dep not in self.stages:
                    problems.append(f"{stage.stage_id}: missing dependency {dep}")
        known = {s.stage_id for s in self.stages.values()}
        for name in self._cycle_nodes():
            problems.append(f"cycle detected at stage {name}")
        if not known:
            problems.append("empty pipeline")
        return problems

    def _cycle_nodes(self) -> list[str]:
        color: dict[str, int] = {name: 0 for name in self.stages}
        found: list[str] = []

        def visit(name: str) -> None:
            color[name] = 1
            for dep in self.stages[name].depends_on:
                if dep not in self.stages:
                    continue
                if color[dep] == 0:
                    visit(dep)
                elif color[dep] == 1:
                    found.append(dep)
            color[name] = 2

        for name in list(self.stages):
            if color[name] == 0:
                visit(name)
        return sorted(set(found))

    def batches(self) -> list[list[str]]:
        """Stages grouped into parallelizable waves (Kahn's algorithm)."""
        remaining = {name: set(s.depends_on) & set(self.stages) for name, s in self.stages.items()}
        done: set[str] = set()
        waves: list[list[str]] = []
        while len(done) < len(self.stages):
            wave = sorted(name for name, deps in remaining.items() if name not in done and deps <= done)
            if not wave:
                break
            waves.append(wave)
            done.update(wave)
        return waves

    def order(self) -> list[str]:
        return [name for wave in self.batches() for name in wave]

    def critical_path_length(self, durations: dict[str, float] | None = None) -> float:
        durations = durations or {}
        longest: dict[str, float] = {}
        for name in self.order():
            own = durations.get(name, 1.0)
            longest[name] = own + max([longest.get(d, 0.0) for d in self.stages[name].depends_on] or [0.0])
        return round(max(longest.values()) if longest else 0.0, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": [s.to_dict() for s in self.stages.values()],
            "batches": self.batches(),
            "order": self.order(),
            "problems": self.validate(),
        }


class PipelineExecutor:
    """Runs a DAG with injected handlers and a retry policy."""

    def __init__(self, handlers: dict[str, Callable[[PipelineStage, dict[str, Any]], dict[str, Any]]] | None = None, max_attempts: int = 3):
        self.handlers = handlers or {}
        self.max_attempts = max_attempts
        self.log: list[dict[str, Any]] = []

    def backoff_ms(self, attempt: int, base_ms: int = 200, factor: float = 2.0) -> int:
        return int(round(base_ms * (factor ** max(0, attempt - 1))))

    def run(self, dag: PipelineDAG, context: dict[str, Any] | None = None) -> dict[str, Any]:
        problems = dag.validate()
        if problems:
            return {"ok": False, "problems": problems}
        context = dict(context or {})
        for wave in dag.batches():
            for name in wave:
                stage = dag.stages[name]
                handler = self.handlers.get(stage.kind)
                if handler is None:
                    stage.status = "skipped"
                    self.log.append({"stage_id": name, "status": "skipped", "reason": "no handler"})
                    continue
                last_error = ""
                for attempt in range(1, self.max_attempts + 1):
                    stage.attempts = attempt
                    try:
                        result = handler(stage, context)
                        stage.status = "completed"
                        stage.output = result or {}
                        context[name] = stage.output
                        self.log.append(
                            {"stage_id": name, "status": "completed", "attempt": attempt,
                             "backoff_ms": 0 if attempt == 1 else self.backoff_ms(attempt)}
                        )
                        break
                    except Exception as exc:  # noqa: BLE001 - pipelines report, not crash
                        last_error = str(exc)
                        self.log.append(
                            {"stage_id": name, "status": "retry", "attempt": attempt,
                             "backoff_ms": self.backoff_ms(attempt), "error": last_error[:120]}
                        )
                else:
                    stage.status = "failed"
                    self.log.append({"stage_id": name, "status": "failed", "error": last_error[:160]})
        completed = sum(1 for s in dag.stages.values() if s.status == "completed")
        return {
            "ok": completed == len(dag.stages),
            "stages": len(dag.stages),
            "completed": completed,
            "failed": [s.stage_id for s in dag.stages.values() if s.status == "failed"],
            "skipped": [s.stage_id for s in dag.stages.values() if s.status == "skipped"],
            "log": self.log,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Dubbing
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SubtitleSegment:
    """One subtitle line with source and translated text."""

    index: int
    start: float
    end: float
    text: str
    translated: str = ""

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    @property
    def text_cps(self) -> float:
        return round(safe_div(len(self.text), self.duration), 2)

    @property
    def translated_cps(self) -> float:
        return round(safe_div(len(self.translated or self.text), self.duration), 2)

    @property
    def expansion(self) -> float:
        """How much longer the translation is than the source (1.0 = same)."""
        return round(safe_div(len(self.translated or self.text), max(1, len(self.text))), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": self.duration,
            "text": self.text,
            "translated": self.translated,
            "expansion": self.expansion,
            "cps": self.translated_cps,
        }


@dataclass
class DubSegmentPlan:
    """Per-segment speech-synthesis plan for one subtitle line."""

    segment: SubtitleSegment
    required_seconds: float
    available_seconds: float
    rate: float
    lead_in: float = 0.0

    @property
    def fits(self) -> bool:
        return self.required_seconds <= self.available_seconds + 1e-6

    @property
    def compression(self) -> float:
        return round(safe_div(self.required_seconds, self.available_seconds, 1.0), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.segment.index,
            "available_seconds": round(self.available_seconds, 3),
            "required_seconds": round(self.required_seconds, 3),
            "rate": round(self.rate, 4),
            "fits": self.fits,
            "compression": self.compression,
            "lead_in": round(self.lead_in, 3),
        }


class DubbingPipeline:
    """Transcribe -> translate -> fit speech to the original timing.

    The heart of OpenCreator's dubbing: each translated line must be spoken
    inside the gap left by the original speaker, so the synthesis rate and the
    lead-in are solved per segment (isochronous alignment).
    """

    def __init__(
        self,
        source_language: str = "en",
        target_language: str = "es",
        base_cps: float = 15.0,
        min_rate: float = 0.85,
        max_rate: float = 1.65,
        max_cps: float = 21.0,
    ):
        self.source_language = source_language
        self.target_language = target_language
        self.base_cps = base_cps
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.max_cps = max_cps

    # -- expansion model ---------------------------------------------------
    EXPANSION_BY_PAIR: dict[tuple[str, str], float] = {
        ("en", "es"): 1.22, ("en", "de"): 1.30, ("en", "fr"): 1.28,
        ("en", "pt"): 1.21, ("en", "it"): 1.24, ("en", "ja"): 0.82,
        ("en", "ko"): 0.88, ("en", "hi"): 1.18, ("en", "ru"): 1.25,
        ("en", "en"): 1.0,
    }

    def expansion_factor(self) -> float:
        pair = (self.source_language, self.target_language)
        if pair in self.EXPANSION_BY_PAIR:
            return self.EXPANSION_BY_PAIR[pair]
        if self.source_language == self.target_language:
            return 1.0
        return 1.15

    def translate(self, text: str) -> str:
        """Offline placeholder translation: a length-calibrated stand-in.

        A real deployment calls the LLM/translation provider; offline we expand
        the source by the language-pair expansion factor so the timing maths is
        exercised with realistic text lengths.
        """
        target_chars = max(1, int(round(len(text) * self.expansion_factor())))
        base = (text + " " + text)[: target_chars].strip()
        if len(base) < target_chars:
            base = (base + " " + text * 3)[:target_chars].strip()
        return base[:target_chars]

    def build_segments(self, cues: list[tuple[float, float, str]]) -> list[SubtitleSegment]:
        segments: list[SubtitleSegment] = []
        for i, (start, end, text) in enumerate(cues):
            segments.append(SubtitleSegment(index=i, start=start, end=end, text=text, translated=self.translate(text)))
        return segments

    def plan(self, segments: list[SubtitleSegment]) -> list[DubSegmentPlan]:
        plans: list[DubSegmentPlan] = []
        for index, segment in enumerate(segments):
            gap = segment.start - (segments[index - 1].end if index else 0.0)
            available = segment.duration + max(0.0, gap) * 0.5
            chars = len(segment.translated or segment.text)
            natural = safe_div(chars, self.base_cps)
            rate = min(self.max_rate, max(self.min_rate, safe_div(natural, available, self.min_rate)))
            required = safe_div(natural, rate)
            lead_in = max(0.0, round((available - required) / 2.0, 3))
            plans.append(
                DubSegmentPlan(
                    segment=segment,
                    required_seconds=round(required, 3),
                    available_seconds=round(available, 3),
                    rate=round(rate, 4),
                    lead_in=lead_in,
                )
            )
        return plans

    def report(self, plans: list[DubSegmentPlan]) -> dict[str, Any]:
        if not plans:
            return {"segments": 0}
        overflow = [p.segment.index for p in plans if not p.fits]
        cps_values = [safe_div(len(p.segment.translated or p.segment.text), p.required_seconds) for p in plans]
        return {
            "segments": len(plans),
            "target_language": self.target_language,
            "expansion_factor": self.expansion_factor(),
            "mean_rate": round(safe_div(sum(p.rate for p in plans), len(plans)), 4),
            "max_rate_used": round(max(p.rate for p in plans), 4),
            "overflow_segments": overflow,
            "fit_ratio": round(1.0 - safe_div(len(overflow), len(plans)), 4),
            "mean_cps": round(safe_div(sum(cps_values), len(cps_values)), 2),
            "over_cps_limit": [i for i, c in enumerate(cps_values) if c > self.max_cps],
        }

    def to_srt(self, segments: list[SubtitleSegment], translated: bool = True) -> str:
        lines: list[str] = []
        for segment in segments:
            text = segment.translated if translated and segment.translated else segment.text
            lines.append(f"{segment.index + 1}\n{timestamp_srt(segment.start)} --> {timestamp_srt(segment.end)}\n{text}\n")
        return "\n".join(lines)

    def to_vtt(self, segments: list[SubtitleSegment], translated: bool = True) -> str:
        body = self.to_srt(segments, translated).replace(",", ".")
        return "WEBVTT\n\n" + body


# ─────────────────────────────────────────────────────────────────────────────
# Shot prompts + batch jobs
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ShotPrompt:
    subject: str = ""
    action: str = ""
    setting: str = ""
    camera: str = "medium shot"
    lens: str = "35mm"
    lighting: str = "soft directional light"
    mood: str = "cinematic"
    style: str = "photorealistic"
    negative: str = "text, watermark, deformed hands, extra fingers"
    aspect_ratio: str = "16:9"
    seed: int = 0

    def build(self) -> str:
        parts = [
            f"{self.subject} {self.action}".strip(),
            f"in {self.setting}" if self.setting else "",
            f"{self.camera}, {self.lens} lens",
            f"{self.lighting}, {self.mood} mood",
            f"{self.style} style",
            f"aspect ratio {self.aspect_ratio}",
        ]
        return ", ".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        return {"prompt": self.build(), "negative_prompt": self.negative, "seed": self.seed}


class ShotPromptBuilder:
    """Deterministic shot prompts (subject + style tokens + stable seed)."""

    CAMERAS = ("extreme wide shot", "wide shot", "medium shot", "close-up", "extreme close-up", "over the shoulder", "top-down")
    LENSES = ("18mm", "24mm", "35mm", "50mm", "85mm", "135mm")
    LIGHTING = ("soft directional light", "golden hour", "high-key studio", "low-key noir", "neon practicals", "overcast")
    MOODS = ("cinematic", "documentary", "playful", "tense", "inspirational", "minimal")

    def __init__(self, style: str = "photorealistic", negative: str = "text, watermark, deformed hands, extra fingers"):
        self.style = style
        self.negative = negative

    def seed_for(self, shot_id: str, take: int = 0) -> int:
        digest = hashlib.sha256(f"{shot_id}|{take}".encode()).digest()
        return int.from_bytes(digest[:4], "big") % (2 ** 31)

    def build(self, shot_id: str, subject: str, action: str = "", setting: str = "", take: int = 0, aspect_ratio: str = "16:9") -> ShotPrompt:
        digest = hashlib.sha256(f"{shot_id}|{subject}".encode()).digest()
        return ShotPrompt(
            subject=subject,
            action=action,
            setting=setting,
            camera=self.CAMERAS[digest[0] % len(self.CAMERAS)],
            lens=self.LENSES[digest[1] % len(self.LENSES)],
            lighting=self.LIGHTING[digest[2] % len(self.LIGHTING)],
            mood=self.MOODS[digest[3] % len(self.MOODS)],
            style=self.style,
            negative=self.negative,
            aspect_ratio=aspect_ratio,
            seed=self.seed_for(shot_id, take),
        )

    def variations(self, shot_id: str, subject: str, count: int = 3, **kwargs: Any) -> list[ShotPrompt]:
        return [self.build(shot_id, subject, take=i, **kwargs) for i in range(count)]


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_backoff_ms: int = 200
    factor: float = 2.0
    max_backoff_ms: int = 8000

    def backoff_ms(self, attempt: int) -> int:
        raw = self.base_backoff_ms * (self.factor ** max(0, attempt - 1))
        return int(min(self.max_backoff_ms, round(raw)))

    def total_backoff_ms(self) -> int:
        return sum(self.backoff_ms(a) for a in range(1, self.max_attempts + 1))


@dataclass
class BatchJob:
    job_id: str
    preset: CreatorPreset
    duration_s: float = 0.0
    attempts: int = 0
    status: str = "queued"

    @property
    def estimated_size_mb(self) -> float:
        return self.preset.estimate_size_mb(self.duration_s)


class BatchJobPlanner:
    """Queues batch renders, tracks concurrency and estimates completion."""

    def __init__(self, concurrency: int = 2, retry: RetryPolicy | None = None):
        self.concurrency = max(1, concurrency)
        self.retry = retry or RetryPolicy()
        self.jobs: list[BatchJob] = []

    def submit(self, job: BatchJob) -> BatchJob:
        self.jobs.append(job)
        return job

    def queue(self, preset: CreatorPreset, duration_s: float, job_id: str = "") -> BatchJob:
        job = BatchJob(job_id=job_id or f"job-{len(self.jobs) + 1:04d}", preset=preset, duration_s=duration_s)
        return self.submit(job)

    @property
    def total_duration_s(self) -> float:
        return round(sum(j.duration_s for j in self.jobs), 3)

    @property
    def total_size_mb(self) -> float:
        return round(sum(j.estimated_size_mb for j in self.jobs), 2)

    def eta_seconds(self, render_speed: float = 1.0) -> float:
        """Wall-clock estimate: renders are 1/render_speed of realtime."""
        waves = math.ceil(safe_div(len(self.jobs), self.concurrency, 0.0))
        render = safe_div(self.total_duration_s, render_speed) * safe_div(1, self.concurrency)
        retries = safe_div(self.retry.total_backoff_ms(), 1000.0) * waves * 0.25
        return round(render + retries, 2)

    def plan(self) -> dict[str, Any]:
        waves: list[list[str]] = []
        for i in range(0, len(self.jobs), self.concurrency):
            waves.append([j.job_id for j in self.jobs[i : i + self.concurrency]])
        return {
            "jobs": len(self.jobs),
            "concurrency": self.concurrency,
            "waves": waves,
            "total_duration_s": self.total_duration_s,
            "total_size_mb": self.total_size_mb,
            "eta_seconds": self.eta_seconds(),
            "retry_policy": {
                "max_attempts": self.retry.max_attempts,
                "total_backoff_ms": self.retry.total_backoff_ms(),
            },
        }
