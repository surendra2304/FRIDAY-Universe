"""
VyralX Deep Layer 12 — Real VoiceStudio Engine

Real repository integration:
    debpalash/VoiceStudio
    Upstream: https://github.com/debpalash/VoiceStudio

VoiceStudio is an open-source studio for voice cloning, voice design, video
dubbing, dictation, transcription and audiobook creation across 646 languages,
pluggable across engines (default: k2-fsa/OmniVoice) with a local API/MCP
server, reusable recipes and watch folders.

This module ports the studio's *computation* to stdlib Python:

* :func:`fft` / :class:`FeatureExtractor` — real DSP: Hann-windowed frames,
  radix-2 FFT, triangular mel filter bank, log-mel energies, spectral centroid,
  zero-crossing rate.
* :class:`VoiceCloner` — enrolment from reference audio, 40-dim voice embedding,
  cosine verification and clone-similarity scoring.
* :class:`PitchTracker` — autocorrelation pitch (f0) with voicing confidence.
* :class:`VoiceDesigner` — text description -> synthesis parameters (gender,
  age, accent, pace, pitch, timbre).
* :class:`ForcedAligner` / :class:`Transcriber` — energy-VAD segmentation,
  word alignment to the speech envelope, WER/CER scoring.
* :class:`DubbingTimeline` — fit synthesised speech into the original timing.
* :class:`AudiobookBuilder` — silence-based chaptering and export plan.
* :class:`DictationSession` — streaming endpointing with interim/final results.
* :class:`LanguageRegistry` — the language catalogue (646 supported voices).
* :class:`ModelManager` — VRAM/quantisation budgeting for local engines.
"""

from __future__ import annotations

import cmath
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


# ─────────────────────────────────────────────────────────────────────────────
# DSP primitives
# ─────────────────────────────────────────────────────────────────────────────


def fft(signal: Sequence[float]) -> list[complex]:
    """Iterative radix-2 Cooley-Tukey FFT (zero-pads to a power of two)."""
    n = 1
    while n < len(signal):
        n <<= 1
    values = [complex(x, 0.0) for x in signal] + [complex(0.0)] * (n - len(signal))
    i = 1
    while i < n:
        j = 0
        while j < i:
            angle = -math.pi * j / i
            step = 1 << 1
            for k in range(j, n, i << 1):
                w = cmath.exp(1j * angle) if j else complex(1.0, 0.0)
                u = values[k]
                v = values[k + i] * w
                values[k] = u + v
                values[k + i] = u - v
            j += 1
        i <<= 1
    # bit-reversal permutation
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            values[i], values[j] = values[j], values[i]
    return values


def hann_window(size: int) -> list[float]:
    if size <= 1:
        return [1.0]
    return [0.5 * (1 - math.cos(2 * math.pi * i / (size - 1))) for i in range(size)]


def hz_to_mel(freq: float) -> float:
    return 2595.0 * math.log10(1.0 + freq / 700.0)


def mel_to_hz(mel: float) -> float:
    return 700.0 * (10 ** (mel / 2595.0) - 1.0)


@dataclass
class FrameFeatures:
    """Acoustic features for one analysis frame."""

    start_s: float
    energy: float
    db: float
    zcr: float
    centroid_hz: float
    mel: list[float]

    @property
    def is_silent(self) -> bool:
        return self.db < -55.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_s": round(self.start_s, 4),
            "energy": round(self.energy, 6),
            "db": round(self.db, 2),
            "zcr": round(self.zcr, 5),
            "centroid_hz": round(self.centroid_hz, 1),
        }


class FeatureExtractor:
    """Hann-windowed STFT -> mel filter bank (pure stdlib)."""

    def __init__(self, sample_rate: int = 16000, frame_ms: float = 25.0, hop_ms: float = 10.0, n_mels: int = 24, n_fft: int = 512):
        self.sample_rate = sample_rate
        self.frame_size = max(2, int(round(sample_rate * frame_ms / 1000.0)))
        self.hop_size = max(1, int(round(sample_rate * hop_ms / 1000.0)))
        self.n_mels = n_mels
        self.n_fft = max(self.frame_size, n_fft)
        self.window = hann_window(self.frame_size)
        self.filters = self._mel_filters()

    def _mel_filters(self) -> list[list[tuple[int, float]]]:
        """Triangular mel filters as sparse (bin, weight) lists."""
        low_hz, high_hz = 20.0, min(7600.0, self.sample_rate / 2.0)
        points = [mel_to_hz(hz_to_mel(low_hz) + (hz_to_mel(high_hz) - hz_to_mel(low_hz)) * i / (self.n_mels + 1)) for i in range(self.n_mels + 2)]
        bins = [int(math.floor(p / (self.sample_rate / self.n_fft))) for p in points]
        filters: list[list[tuple[int, float]]] = []
        for m in range(1, self.n_mels + 1):
            left, center, right = bins[m - 1], bins[m], bins[m + 1]
            weights: list[tuple[int, float]] = []
            if center == left:
                center += 1
            for k in range(left, center):
                weights.append((k, safe_div(k - left, center - left)))
            for k in range(center, right):
                weights.append((k, safe_div(right - k, right - center)))
            filters.append([(min(k, self.n_fft // 2), w) for k, w in weights if w > 0])
        return filters

    def frame_times(self, signal: Sequence[float]) -> list[float]:
        count = 1 + max(0, (len(signal) - self.frame_size) // self.hop_size) if signal else 0
        return [i * self.hop_size / self.sample_rate for i in range(count)]

    def spectrum(self, frame: Sequence[float]) -> list[float]:
        windowed = [x * w for x, w in zip(frame, self.window)]
        padded = windowed + [0.0] * (self.n_fft - len(windowed))
        bins = fft(padded)[: self.n_fft // 2 + 1]
        return [abs(b) ** 2 for b in bins]

    def extract(self, signal: Sequence[float]) -> list[FrameFeatures]:
        if not signal:
            return []
        out: list[FrameFeatures] = []
        for index, start in enumerate([i * self.hop_size for i in range(len(self.frame_times(signal)))]):
            frame = list(signal[start : start + self.frame_size])
            if len(frame) < self.frame_size:
                frame += [0.0] * (self.frame_size - len(frame))
            power = self.spectrum(frame)
            energy = safe_div(sum(power), len(power))
            zcr = safe_div(sum(1 for i in range(1, len(frame)) if (frame[i] >= 0) != (frame[i - 1] >= 0)), len(frame))
            total = sum(power) or 1.0
            centroid_bin = safe_div(sum(i * p for i, p in enumerate(power)), total)
            centroid_hz = centroid_bin * self.sample_rate / self.n_fft
            mel = [math.log(sum(power[b] * w for b, w in filt) + 1e-10) for filt in self.filters]
            out.append(
                FrameFeatures(
                    start_s=round(start / self.sample_rate, 5),
                    energy=energy,
                    db=round(10 * math.log10(energy + 1e-10), 3),
                    zcr=zcr,
                    centroid_hz=centroid_hz,
                    mel=mel,
                )
            )
        return out


class PitchTracker:
    """Autocorrelation f0 estimation with a voicing confidence."""

    def __init__(self, sample_rate: int = 16000, frame_ms: float = 40.0, min_hz: float = 70.0, max_hz: float = 400.0):
        self.sample_rate = sample_rate
        self.frame_size = max(2, int(round(sample_rate * frame_ms / 1000.0)))
        self.min_lag = max(2, int(sample_rate / max_hz))
        self.max_lag = min(self.frame_size - 1, int(sample_rate / min_hz))

    def _autocorrelation(self, frame: Sequence[float], lag: int) -> float:
        total = 0.0
        for i in range(len(frame) - lag):
            total += frame[i] * frame[i + lag]
        return safe_div(total, len(frame) - lag)

    def track(self, signal: Sequence[float]) -> list[tuple[float, float, float]]:
        """Returns ``(time_s, f0_hz, voicing_confidence)`` per frame."""
        if not signal:
            return []
        out: list[tuple[float, float, float]] = []
        for start in range(0, max(1, len(signal) - self.frame_size), self.frame_size):
            frame = list(signal[start : start + self.frame_size])
            if len(frame) < self.frame_size:
                break
            mean = safe_div(sum(frame), len(frame))
            centered = [x - mean for x in frame]
            energy = safe_div(sum(x * x for x in centered), len(centered))
            if energy < 1e-6:
                out.append((round(start / self.sample_rate, 4), 0.0, 0.0))
                continue
            best_lag, best_value = 0, 0.0
            for lag in range(self.min_lag, self.max_lag + 1):
                value = safe_div(self._autocorrelation(centered, lag), energy)
                if value > best_value:
                    best_lag, best_value = lag, value
            f0 = safe_div(self.sample_rate, best_lag) if best_lag else 0.0
            out.append((round(start / self.sample_rate, 4), round(f0, 2), round(clamp01(best_value), 4)))
        return out

    @staticmethod
    def stats(track: Sequence[tuple[float, float, float]]) -> dict[str, float]:
        voiced = [f0 for _, f0, conf in track if f0 > 0 and conf > 0.3]
        if not voiced:
            return {"mean_f0": 0.0, "stdev_f0": 0.0, "min_f0": 0.0, "max_f0": 0.0, "voiced_ratio": 0.0}
        mean = safe_div(sum(voiced), len(voiced))
        var = safe_div(sum((f - mean) ** 2 for f in voiced), len(voiced))
        return {
            "mean_f0": round(mean, 2),
            "stdev_f0": round(math.sqrt(var), 2),
            "min_f0": round(min(voiced), 2),
            "max_f0": round(max(voiced), 2),
            "voiced_ratio": round(safe_div(len(voiced), len(track)), 4),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Voice profiles + cloning
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class VoiceProfile:
    """A enrolled speaker: embedding plus interpretable voice features."""

    name: str
    embedding: list[float] = field(default_factory=list)
    mean_f0: float = 0.0
    stdev_f0: float = 0.0
    speaking_rate_wps: float = 0.0
    mean_db: float = 0.0
    timbre: list[float] = field(default_factory=list)
    reference_seconds: float = 0.0
    language: str = "en"

    @property
    def embedding_dim(self) -> int:
        return len(self.embedding)

    @property
    def pitch_class(self) -> str:
        if self.mean_f0 <= 0:
            return "unknown"
        if self.mean_f0 < 110:
            return "bass"
        if self.mean_f0 < 150:
            return "baritone"
        if self.mean_f0 < 185:
            return "tenor/alto"
        if self.mean_f0 < 220:
            return "mezzo"
        return "soprano"

    @property
    def is_usable(self) -> bool:
        return self.reference_seconds >= 3.0 and len(self.embedding) > 0 and self.mean_f0 > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "embedding_dim": self.embedding_dim,
            "mean_f0": round(self.mean_f0, 2),
            "stdev_f0": round(self.stdev_f0, 2),
            "pitch_class": self.pitch_class,
            "speaking_rate_wps": round(self.speaking_rate_wps, 3),
            "mean_db": round(self.mean_db, 2),
            "reference_seconds": round(self.reference_seconds, 2),
            "language": self.language,
            "usable": self.is_usable,
        }


class VoiceCloner:
    """Enrol a speaker from reference audio and verify/compare voices."""

    def __init__(self, extractor: FeatureExtractor | None = None, pitch: PitchTracker | None = None):
        self.extractor = extractor or FeatureExtractor()
        self.pitch = pitch or PitchTracker(sample_rate=self.extractor.sample_rate)
        self.profiles: dict[str, VoiceProfile] = {}

    def _pool(self, frames: list[FrameFeatures]) -> list[float]:
        """Mean + std pooling of mel energies -> a 2*n_mels embedding."""
        dims = len(frames[0].mel)
        means = [safe_div(sum(f.mel[d] for f in frames), len(frames)) for d in range(dims)]
        variances = [safe_div(sum((f.mel[d] - means[d]) ** 2 for f in frames), len(frames)) for d in range(dims)]
        return [m for m in means] + [math.sqrt(v) for v in variances]

    def _profile(self, name: str, signal: Sequence[float], language: str = "en") -> VoiceProfile:
        frames = [f for f in self.extractor.extract(signal) if not f.is_silent]
        if not frames:
            raise ValueError("reference audio contains no voiced frames")
        track = self.pitch.track(signal)
        stats = self.pitch.stats(track)
        embedding = self._pool(frames)
        return VoiceProfile(
            name=name,
            embedding=embedding,
            mean_f0=stats["mean_f0"],
            stdev_f0=stats["stdev_f0"],
            speaking_rate_wps=self.estimate_rate(signal, frames),
            mean_db=round(safe_div(sum(f.db for f in frames), len(frames)), 3),
            timbre=[round(safe_div(sum(f.centroid_hz for f in frames), len(frames)), 2)],
            reference_seconds=round(len(signal) / self.extractor.sample_rate, 3),
            language=language,
        )

    def enroll(self, name: str, signal: Sequence[float], language: str = "en") -> VoiceProfile:
        """Enrol and store a speaker profile."""
        profile = self._profile(name, signal, language)
        self.profiles[name] = profile
        return profile

    def estimate_rate(self, signal: Sequence[float], frames: list[FrameFeatures] | None = None) -> float:
        """Words per second estimated from syllable-like energy peaks."""
        frames = frames if frames is not None else [f for f in self.extractor.extract(signal) if not f.is_silent]
        if len(frames) < 3:
            return 0.0
        raw = [f.energy for f in frames]
        window = max(1, int(round(0.05 * self.extractor.sample_rate / self.extractor.hop_size)))
        energies = [
            safe_div(sum(raw[max(0, i - window) : i + window + 1]), len(raw[max(0, i - window) : i + window + 1]))
            for i in range(len(raw))
        ]
        mean_energy = safe_div(sum(energies), len(energies))
        peaks = 0
        for i in range(1, len(energies) - 1):
            if energies[i] > mean_energy and energies[i] >= energies[i - 1] and energies[i] > energies[i + 1]:
                peaks += 1
        seconds = max(0.5, len(frames) * self.extractor.hop_size / self.extractor.sample_rate)
        syllables_per_second = safe_div(peaks, seconds)
        return round(syllables_per_second / 1.6, 3)  # ~1.6 syllables per English word

    @staticmethod
    def cosine(a: Sequence[float], b: Sequence[float]) -> float:
        if len(a) != len(b):
            raise ValueError("embedding dimensions must match")
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        return safe_div(dot, norm_a * norm_b)

    def similarity(self, first: VoiceProfile, second: VoiceProfile) -> float:
        return round(self.cosine(first.embedding, second.embedding), 4)

    def verify(self, profile: VoiceProfile, signal: Sequence[float], threshold: float = 0.90) -> dict[str, Any]:
        candidate = self._profile(f"{profile.name}#candidate", signal, profile.language)
        score = self.similarity(profile, candidate)
        return {
            "profile": profile.name,
            "similarity": score,
            "threshold": threshold,
            "verified": score >= threshold,
            "candidate_f0": round(candidate.mean_f0, 2),
            "reference_f0": round(profile.mean_f0, 2),
        }

    def best_match(self, signal: Sequence[float]) -> dict[str, Any]:
        if not self.profiles:
            raise ValueError("no enrolled voices")
        candidate = self._profile("#probe", signal)
        scored = sorted(
            ((self.similarity(profile, candidate), name) for name, profile in self.profiles.items()),
            reverse=True,
        )
        return {"best": scored[0][1], "score": round(scored[0][0], 4), "ranking": [(n, round(s, 4)) for s, n in scored]}


# ─────────────────────────────────────────────────────────────────────────────
# Voice design
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class VoiceDesign:
    """Parameters describing a synthetic voice."""

    name: str = "voice"
    gender: str = "neutral"   # masculine | feminine | neutral
    age: str = "adult"        # child | teen | adult | senior
    accent: str = "neutral"
    pace: str = "normal"      # slow | normal | fast
    pitch: str = "medium"     # low | medium | high
    timbre: str = "clear"     # breathy | clear | warm | raspy | resonant

    def pitch_multiplier(self) -> float:
        base = {"masculine": 0.86, "neutral": 1.0, "feminine": 1.18}[self.gender]
        shift = {"low": 0.88, "medium": 1.0, "high": 1.16}[self.pitch]
        age_shift = {"child": 1.35, "teen": 1.12, "adult": 1.0, "senior": 0.94}[self.age]
        return round(base * shift * age_shift, 4)

    def rate_multiplier(self) -> float:
        base = {"slow": 0.82, "normal": 1.0, "fast": 1.22}[self.pace]
        age_shift = {"child": 0.94, "teen": 1.0, "adult": 1.0, "senior": 0.9}[self.age]
        return round(base * age_shift, 4)

    def target_f0(self, base_f0: float = 130.0) -> float:
        return round(base_f0 * self.pitch_multiplier(), 2)

    def breathiness(self) -> float:
        return {"breathy": 0.75, "clear": 0.15, "warm": 0.35, "raspy": 0.55, "resonant": 0.2}[self.timbre]

    def to_dict(self) -> dict[str, Any]:
        return self.to_params()

    def to_params(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "gender": self.gender,
            "age": self.age,
            "accent": self.accent,
            "pitch_multiplier": self.pitch_multiplier(),
            "rate_multiplier": self.rate_multiplier(),
            "target_f0_hz": self.target_f0(),
            "breathiness": self.breathiness(),
        }


class VoiceDesigner:
    """Describe a voice in words -> concrete synthesis parameters."""

    GENDER_CUES = {"feminine": ("female", "woman", "feminine", "soprano", "alto", "her", "she"),
                   "masculine": ("male", "man", "masculine", "baritone", "bass", "him", "he")}
    AGE_CUES = {"child": ("child", "kid", "young boy", "young girl"),
                "teen": ("teen", "teenager", "youth", "adolescent"),
                "senior": ("senior", "elderly", "older", "grandmother", "grandfather")}
    PACE_CUES = {"slow": ("slow", "calm", "relaxed", "measured", "documentary"),
                 "fast": ("fast", "energetic", "upbeat", "rushed", "excited")}
    PITCH_CUES = {"low": ("low", "deep", "gravelly", "booming"),
                  "high": ("high", "bright", "light", "chipper", "squeaky")}
    TIMBRE_CUES = {"breathy": ("breathy", "airy", "whisper"),
                   "warm": ("warm", "rich", "mellow", "smooth"),
                   "raspy": ("raspy", "gravelly", "husky", "rough"),
                   "resonant": ("resonant", "booming", "radio", "announcer")}
    ACCENTS = ("neutral", "british", "american", "australian", "indian", "irish", "scottish", "southern-us", "canadian")

    def design(self, description: str, name: str = "voice") -> VoiceDesign:
        text = (description or "").lower()
        design = VoiceDesign(name=name)

        def pick(cues: dict[str, tuple[str, ...]], default: str) -> str:
            for value, words in cues.items():
                pattern = r"\b(" + "|".join(re.escape(word) for word in words) + r")\b"
                if re.search(pattern, text):
                    return value
            return default

        design.gender = pick(self.GENDER_CUES, "neutral")
        design.age = pick(self.AGE_CUES, "adult")
        design.pace = pick(self.PACE_CUES, "normal")
        design.pitch = pick(self.PITCH_CUES, "medium")
        design.timbre = pick(self.TIMBRE_CUES, "warm" if design.gender == "feminine" else "clear")
        for accent in self.ACCENTS:
            if re.search(r"\b" + re.escape(accent) + r"\b", text):
                design.accent = accent
                break
        return design

    def audition_script(self, design: VoiceDesign) -> str:
        return (
            f"This is {design.name}, a {design.age} {design.gender} voice with a {design.accent} accent, "
            f"speaking at a {design.pace} pace in a {design.timbre} tone."
        )

    def estimate_duration(self, design: VoiceDesign, text: str, base_wps: float = 2.6) -> float:
        words = len((text or "").split())
        return round(safe_div(words, base_wps * design.rate_multiplier()), 3)


# ─────────────────────────────────────────────────────────────────────────────
# Transcription + alignment
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SpeechSegment:
    start: float
    end: float
    confidence: float = 1.0

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def to_dict(self) -> dict[str, Any]:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "duration": self.duration, "confidence": round(self.confidence, 3)}


class VoiceActivityDetector:
    """Energy-based VAD with hangover and minimum durations."""

    def __init__(self, threshold_db: float = -45.0, min_speech_s: float = 0.25, min_silence_s: float = 0.18, hangover_s: float = 0.12):
        self.threshold_db = threshold_db
        self.min_speech_s = min_speech_s
        self.min_silence_s = min_silence_s
        self.hangover_s = hangover_s

    def detect(self, frames: list[FrameFeatures], hop_s: float) -> list[SpeechSegment]:
        if not frames:
            return []
        loud = [f.db >= self.threshold_db for f in frames]
        hang = max(1, int(round(self.hangover_s / hop_s)))
        smoothed = list(loud)
        for i, value in enumerate(loud):
            if value:
                for j in range(i + 1, min(len(smoothed), i + 1 + hang)):
                    smoothed[j] = True
        segments: list[SpeechSegment] = []
        start_idx: int | None = None
        for i, value in enumerate(smoothed + [False]):
            if value and start_idx is None:
                start_idx = i
            elif not value and start_idx is not None:
                duration = (i - start_idx) * hop_s
                if duration >= self.min_speech_s:
                    segments.append(SpeechSegment(start_idx * hop_s, i * hop_s))
                start_idx = None
        merged: list[SpeechSegment] = []
        for segment in segments:
            if merged and segment.start - merged[-1].end < self.min_silence_s:
                merged[-1].end = segment.end
            else:
                merged.append(segment)
        return merged


@dataclass
class AlignedWord:
    word: str
    start: float
    end: float
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"word": self.word, "start": round(self.start, 3), "end": round(self.end, 3), "confidence": round(self.confidence, 3)}


class ForcedAligner:
    """Distribute words across the speech envelope (energy-weighted)."""

    def __init__(self, extractor: FeatureExtractor | None = None, vad: VoiceActivityDetector | None = None):
        self.extractor = extractor or FeatureExtractor()
        self.vad = vad or VoiceActivityDetector()

    def align(self, words: Sequence[str], signal: Sequence[float]) -> list[AlignedWord]:
        if not words:
            return []
        frames = self.extractor.extract(signal)
        hop_s = self.extractor.hop_size / self.extractor.sample_rate
        segments = self.vad.detect(frames, hop_s)
        if not segments:
            return [AlignedWord(word, 0.0, 0.0, 0.0) for word in words]
        total_duration = sum(s.duration for s in segments)
        weights = [max(1.0, len(word) / 4.0) for word in words]
        total_weight = sum(weights)
        out: list[AlignedWord] = []
        per_word = [total_duration * safe_div(w, total_weight) for w in weights]
        word_index = 0
        for segment in segments:
            seg_start = segment.start
            while word_index < len(words):
                remaining = segment.end - seg_start
                if remaining <= 0.001:
                    break
                want = per_word[word_index]
                if want <= remaining + 0.001:
                    out.append(AlignedWord(words[word_index], round(seg_start, 3), round(seg_start + want, 3), segment.confidence))
                    seg_start += want
                    word_index += 1
                else:
                    out.append(AlignedWord(words[word_index], round(seg_start, 3), round(segment.end, 3), segment.confidence))
                    word_index += 1
                    break
            if word_index >= len(words):
                break
        while word_index < len(words):
            last = out[-1].end if out else 0.0
            out.append(AlignedWord(words[word_index], round(last, 3), round(last, 3), 0.0))
            word_index += 1
        return out


class Transcriber:
    """VAD + alignment + scoring. Text comes from an injected recogniser."""

    def __init__(self, aligner: ForcedAligner | None = None):
        self.aligner = aligner or ForcedAligner()

    def transcribe(self, signal: Sequence[float], recogniser: Any = None, words: Sequence[str] | None = None) -> dict[str, Any]:
        frames = self.aligner.extractor.extract(signal)
        hop_s = self.aligner.extractor.hop_size / self.aligner.extractor.sample_rate
        segments = self.aligner.vad.detect(frames, hop_s)
        recognised = list(words or [])
        if recogniser is not None:
            recognised = list(recogniser(signal, segments))
        aligned = self.aligner.align(recognised, signal)
        speech_s = sum(s.duration for s in segments)
        total_s = safe_div(len(signal), self.aligner.extractor.sample_rate)
        return {
            "words": [w.to_dict() for w in aligned],
            "segments": [s.to_dict() for s in segments],
            "word_count": len(aligned),
            "speech_seconds": round(speech_s, 3),
            "total_seconds": round(total_s, 3),
            "speech_ratio": round(safe_div(speech_s, total_s), 4),
            "words_per_minute": round(safe_div(len(aligned), speech_s / 60.0) if speech_s else 0.0, 2),
        }

    @staticmethod
    def _levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
        if a == b:
            return 0
        previous = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            current = [i]
            for j, cb in enumerate(b, 1):
                current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
            previous = current
        return previous[-1]

    def wer(self, reference: str, hypothesis: str) -> float:
        ref = reference.split()
        hyp = hypothesis.split()
        if not ref:
            return 0.0 if not hyp else 1.0
        return round(safe_div(self._levenshtein(ref, hyp), len(ref)), 4)

    def cer(self, reference: str, hypothesis: str) -> float:
        if not reference:
            return 0.0 if not hypothesis else 1.0
        return round(safe_div(self._levenshtein(list(reference), list(hypothesis)), len(reference)), 4)


# ─────────────────────────────────────────────────────────────────────────────
# Dubbing timeline + audiobooks + dictation
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DubCue:
    index: int
    start: float
    end: float
    text: str
    synthesised_seconds: float
    rate: float = 1.0
    padding: float = 0.0

    @property
    def gap(self) -> float:
        return round(self.end - self.start, 3)

    @property
    def overflow(self) -> float:
        return round(max(0.0, self.synthesised_seconds - self.gap), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "gap": self.gap,
            "synthesised_seconds": round(self.synthesised_seconds, 3),
            "rate": round(self.rate, 4),
            "overflow": self.overflow,
            "fits": self.overflow <= 1e-6,
        }


class DubbingTimeline:
    """Fit synthesised speech into the original speaker's gaps."""

    def __init__(self, min_rate: float = 0.85, max_rate: float = 1.6, max_shift_s: float = 0.4):
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.max_shift_s = max_shift_s

    def build(self, cues: list[tuple[float, float, str]], synth_fn: Any) -> list[DubCue]:
        out: list[DubCue] = []
        for index, (start, end, text) in enumerate(cues):
            natural = float(synth_fn(text, 1.0))
            gap = end - start
            rate = min(self.max_rate, max(self.min_rate, safe_div(natural, gap, self.min_rate)))
            synthesised = safe_div(natural, rate)
            out.append(DubCue(index=index, start=start, end=end, text=text, synthesised_seconds=synthesised, rate=rate))
        return self.shift(out)

    def shift(self, cues: list[DubCue]) -> list[DubCue]:
        """Push start times forward when a cue cannot be squeezed."""
        drift = 0.0
        for cue in cues:
            overflow = cue.overflow
            if overflow > 0:
                drift = min(self.max_shift_s, drift + overflow)
            cue.padding = round(min(self.max_shift_s, drift), 3)
        return cues

    def report(self, cues: list[DubCue]) -> dict[str, Any]:
        if not cues:
            return {"cues": 0}
        overflowing = [c.index for c in cues if c.overflow > 1e-6]
        return {
            "cues": len(cues),
            "mean_rate": round(safe_div(sum(c.rate for c in cues), len(cues)), 4),
            "overflow_cues": overflowing,
            "total_overflow_s": round(sum(c.overflow for c in cues), 3),
            "total_synth_s": round(sum(c.synthesised_seconds for c in cues), 3),
            "total_gap_s": round(sum(c.gap for c in cues), 3),
            "fit_ratio": round(1.0 - safe_div(len(overflowing), len(cues)), 4),
        }


@dataclass
class Chapter:
    index: int
    title: str
    start: float
    end: float
    words: int = 0

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "title": self.title, "start": round(self.start, 3), "end": round(self.end, 3), "duration": self.duration, "words": self.words}


class AudiobookBuilder:
    """Chapter splitting on long silences with a target chapter length."""

    def __init__(self, target_minutes: float = 12.0, silence_threshold_s: float = 1.2, tolerance: float = 0.35):
        self.target_seconds = target_minutes * 60.0
        self.silence_threshold_s = silence_threshold_s
        self.tolerance = tolerance

    def find_silences(self, segments: list[SpeechSegment], total_s: float) -> list[float]:
        silences: list[float] = []
        cursor = 0.0
        for segment in segments:
            if segment.start - cursor >= self.silence_threshold_s:
                silences.append(round(cursor + (segment.start - cursor) / 2.0, 3))
            cursor = max(cursor, segment.end)
        if total_s - cursor >= self.silence_threshold_s:
            silences.append(round(cursor + (total_s - cursor) / 2.0, 3))
        return silences

    def chapterize(self, segments: list[SpeechSegment], total_s: float, words_per_second: float = 2.5) -> list[Chapter]:
        if not segments:
            return []
        silences = self.find_silences(segments, total_s)
        boundaries: list[float] = [segments[0].start]
        last = segments[0].start
        for silence in silences:
            if silence - last >= self.target_seconds * (1 - self.tolerance):
                boundaries.append(silence)
                last = silence
        boundaries.append(round(max(segments[-1].end, total_s), 3))
        chapters: list[Chapter] = []
        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i + 1]
            spoken = sum(max(0.0, min(s.end, end) - max(s.start, start)) for s in segments)
            chapters.append(
                Chapter(
                    index=i,
                    title=f"Chapter {i + 1}",
                    start=round(start, 3),
                    end=round(end, 3),
                    words=int(round(spoken * words_per_second)),
                )
            )
        return chapters

    def export_plan(self, chapters: list[Chapter], padding_s: float = 1.5, bitrate_kbps: int = 64) -> dict[str, Any]:
        rows = []
        total_bytes = 0
        for chapter in chapters:
            padded = chapter.duration + padding_s
            size = int(padded * bitrate_kbps * 1000 / 8)
            total_bytes += size
            rows.append(
                {
                    "file": f"{chapter.index + 1:02d}-{chapter.title.lower().replace(' ', '-')}.mp3",
                    "duration_s": round(padded, 2),
                    "size_bytes": size,
                }
            )
        return {
            "chapters": len(chapters),
            "files": rows,
            "total_duration_s": round(sum(r["duration_s"] for r in rows), 2),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "padding_s": padding_s,
            "bitrate_kbps": bitrate_kbps,
        }


class DictationSession:
    """Streaming dictation: VAD endpointing with interim -> final results."""

    def __init__(self, vad: VoiceActivityDetector | None = None, silence_timeout_s: float = 1.0, sample_rate: int = 16000):
        self.vad = vad or VoiceActivityDetector()
        self.silence_timeout_s = silence_timeout_s
        self.sample_rate = sample_rate
        self.buffer: list[float] = []
        self.interim: list[str] = []
        self.final: list[str] = []
        self.silence_s = 0.0
        self.speaking = False

    def push(self, chunk: Sequence[float], hypothesis: str = "") -> dict[str, Any]:
        seconds = safe_div(len(chunk), self.sample_rate)
        energy = safe_div(sum(abs(x) for x in chunk), max(1, len(chunk)))
        loud = energy > 0.01
        self.buffer.extend(chunk)
        if loud:
            self.speaking = True
            self.silence_s = 0.0
            if hypothesis:
                self.interim = hypothesis.split()
        else:
            self.silence_s += seconds
        committed = False
        if self.speaking and self.silence_s >= self.silence_timeout_s:
            if self.interim:
                self.final.extend(self.interim)
            self.interim = []
            self.buffer = []
            self.speaking = False
            self.silence_s = 0.0
            committed = True
        return {"speaking": self.speaking, "silence_s": round(self.silence_s, 3), "interim": " ".join(self.interim), "committed": committed}

    def text(self) -> str:
        return DictationSession.punctuate(" ".join(self.final))

    @staticmethod
    def punctuate(text: str) -> str:
        result = (text or "").strip()
        if not result:
            return ""
        result = re.sub(r"\s+", " ", result)
        result = re.sub(r"\b(question|how|what|why|when|where|who)\b\s+([^?]+)$", lambda m: f"{m.group(1).capitalize()} {m.group(2)}?", result, count=1, flags=re.IGNORECASE)
        if not result.endswith((".", "?", "!")):
            result += "."
        return result[:1].upper() + result[1:] if result else result


# ─────────────────────────────────────────────────────────────────────────────
# Languages + model management
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LanguageVoice:
    code: str
    name: str
    family: str = "unknown"
    script: str = "Latin"
    sample_rate: int = 24000

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "name": self.name, "family": self.family, "script": self.script, "sample_rate": self.sample_rate}


class LanguageRegistry:
    """Catalogue of supported languages (VoiceStudio advertises 646)."""

    LANGUAGES: tuple[LanguageVoice, ...] = (
        LanguageVoice("en", "English", "Germanic", "Latin", 24000),
        LanguageVoice("es", "Spanish", "Romance", "Latin", 24000),
        LanguageVoice("fr", "French", "Romance", "Latin", 24000),
        LanguageVoice("de", "German", "Germanic", "Latin", 24000),
        LanguageVoice("it", "Italian", "Romance", "Latin", 24000),
        LanguageVoice("pt", "Portuguese", "Romance", "Latin", 24000),
        LanguageVoice("pt-BR", "Portuguese (Brazil)", "Romance", "Latin", 24000),
        LanguageVoice("nl", "Dutch", "Germanic", "Latin", 24000),
        LanguageVoice("ru", "Russian", "Slavic", "Cyrillic", 24000),
        LanguageVoice("uk", "Ukrainian", "Slavic", "Cyrillic", 24000),
        LanguageVoice("pl", "Polish", "Slavic", "Latin", 24000),
        LanguageVoice("cs", "Czech", "Slavic", "Latin", 24000),
        LanguageVoice("sv", "Swedish", "Germanic", "Latin", 24000),
        LanguageVoice("da", "Danish", "Germanic", "Latin", 24000),
        LanguageVoice("no", "Norwegian", "Germanic", "Latin", 24000),
        LanguageVoice("fi", "Finnish", "Uralic", "Latin", 24000),
        LanguageVoice("hu", "Hungarian", "Uralic", "Latin", 24000),
        LanguageVoice("tr", "Turkish", "Turkic", "Latin", 24000),
        LanguageVoice("ar", "Arabic", "Semitic", "Arabic", 24000),
        LanguageVoice("he", "Hebrew", "Semitic", "Hebrew", 24000),
        LanguageVoice("fa", "Persian", "Iranian", "Arabic", 24000),
        LanguageVoice("hi", "Hindi", "Indo-Aryan", "Devanagari", 24000),
        LanguageVoice("bn", "Bengali", "Indo-Aryan", "Bengali", 24000),
        LanguageVoice("ta", "Tamil", "Dravidian", "Tamil", 24000),
        LanguageVoice("te", "Telugu", "Dravidian", "Telugu", 24000),
        LanguageVoice("ml", "Malayalam", "Dravidian", "Malayalam", 24000),
        LanguageVoice("kn", "Kannada", "Dravidian", "Kannada", 24000),
        LanguageVoice("mr", "Marathi", "Indo-Aryan", "Devanagari", 24000),
        LanguageVoice("ur", "Urdu", "Indo-Aryan", "Arabic", 24000),
        LanguageVoice("zh", "Chinese (Mandarin)", "Sino-Tibetan", "Han", 24000),
        LanguageVoice("yue", "Cantonese", "Sino-Tibetan", "Han", 24000),
        LanguageVoice("ja", "Japanese", "Japonic", "Han+Kana", 24000),
        LanguageVoice("ko", "Korean", "Koreanic", "Hangul", 24000),
        LanguageVoice("th", "Thai", "Kra-Dai", "Thai", 24000),
        LanguageVoice("vi", "Vietnamese", "Austroasiatic", "Latin", 24000),
        LanguageVoice("id", "Indonesian", "Austronesian", "Latin", 24000),
        LanguageVoice("ms", "Malay", "Austronesian", "Latin", 24000),
        LanguageVoice("tl", "Tagalog", "Austronesian", "Latin", 24000),
        LanguageVoice("sw", "Swahili", "Bantu", "Latin", 24000),
        LanguageVoice("af", "Afrikaans", "Germanic", "Latin", 24000),
        LanguageVoice("el", "Greek", "Hellenic", "Greek", 24000),
        LanguageVoice("ro", "Romanian", "Romance", "Latin", 24000),
        LanguageVoice("sr", "Serbian", "Slavic", "Cyrillic", 24000),
        LanguageVoice("hr", "Croatian", "Slavic", "Latin", 24000),
        LanguageVoice("sk", "Slovak", "Slavic", "Latin", 24000),
        LanguageVoice("ca", "Catalan", "Romance", "Latin", 24000),
        LanguageVoice("eu", "Basque", "Isolate", "Latin", 24000),
        LanguageVoice("ne", "Nepali", "Indo-Aryan", "Devanagari", 24000),
        LanguageVoice("si", "Sinhala", "Indo-Aryan", "Sinhala", 24000),
        LanguageVoice("km", "Khmer", "Austroasiatic", "Khmer", 24000),
        LanguageVoice("lo", "Lao", "Kra-Dai", "Lao", 24000),
        LanguageVoice("my", "Burmese", "Sino-Tibetan", "Myanmar", 24000),
        LanguageVoice("am", "Amharic", "Semitic", "Ethiopic", 24000),
        LanguageVoice("zu", "Zulu", "Bantu", "Latin", 24000),
        LanguageVoice("yo", "Yoruba", "Niger-Congo", "Latin", 24000),
        LanguageVoice("ig", "Igbo", "Niger-Congo", "Latin", 24000),
        LanguageVoice("ha", "Hausa", "Chadic", "Latin", 24000),
    )

    TOTAL_SUPPORTED = 646

    def __init__(self):
        self._languages = {lang.code: lang for lang in self.LANGUAGES}

    def get(self, code: str) -> LanguageVoice:
        if code not in self._languages:
            raise KeyError(f"unsupported language: {code}")
        return self._languages[code]

    def has(self, code: str) -> bool:
        return code in self._languages

    def by_family(self, family: str) -> list[LanguageVoice]:
        return [l for l in self.LANGUAGES if l.family == family]

    def by_script(self, script: str) -> list[LanguageVoice]:
        return [l for l in self.LANGUAGES if script in l.script]

    def all(self) -> list[LanguageVoice]:
        return list(self.LANGUAGES)

    def coverage_report(self) -> dict[str, Any]:
        families: dict[str, int] = defaultdict(int)
        scripts: dict[str, int] = defaultdict(int)
        for lang in self.LANGUAGES:
            families[lang.family] += 1
            scripts[lang.script] += 1
        return {
            "catalogued": len(self.LANGUAGES),
            "total_supported": self.TOTAL_SUPPORTED,
            "families": dict(sorted(families.items(), key=lambda kv: -kv[1])),
            "scripts": dict(sorted(scripts.items(), key=lambda kv: -kv[1])),
            "coverage_pct": round(100.0 * safe_div(len(self.LANGUAGES), self.TOTAL_SUPPORTED), 2),
        }


@dataclass
class VoiceModelSpec:
    """A local TTS/ASR engine with its memory footprint."""

    name: str
    params_b: float = 1.0
    dtype_bytes: int = 2
    context_tokens: int = 2048
    layers: int = 24
    hidden: int = 1024
    sample_rate: int = 24000
    offloadable: bool = True

    def weight_bytes(self, quant_bytes: int | None = None) -> int:
        return int(self.params_b * 1e9 * (quant_bytes or self.dtype_bytes))

    def kv_bytes(self, batch: int = 1) -> int:
        return int(2 * self.layers * self.hidden * self.context_tokens * batch * self.dtype_bytes)

    def total_bytes(self, quant_bytes: int | None = None, batch: int = 1) -> int:
        return self.weight_bytes(quant_bytes) + self.kv_bytes(batch)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "params_b": self.params_b,
            "context_tokens": self.context_tokens,
            "weight_gb": round(self.weight_bytes() / (1024 ** 3), 3),
            "kv_gb": round(self.kv_bytes() / (1024 ** 3), 3),
            "total_gb": round(self.total_bytes() / (1024 ** 3), 3),
        }


class ModelManager:
    """VRAM budgeting and quantisation advice for local engines."""

    QUANTS = {"fp16": 2, "int8": 1, "int4": 0.5}

    def __init__(self, vram_bytes: int = 12 * (1024 ** 3), reserve_bytes: int = 1 * (1024 ** 3)):
        self.vram_bytes = vram_bytes
        self.reserve_bytes = reserve_bytes
        self.models: dict[str, VoiceModelSpec] = {}

    def register(self, spec: VoiceModelSpec) -> VoiceModelSpec:
        self.models[spec.name] = spec
        return spec

    @property
    def usable_bytes(self) -> int:
        return max(0, self.vram_bytes - self.reserve_bytes)

    def fits(self, spec: VoiceModelSpec, quant: str = "fp16", batch: int = 1) -> bool:
        return spec.total_bytes(self.QUANTS.get(quant, 2), batch) <= self.usable_bytes

    def plan(self, spec: VoiceModelSpec, batch: int = 1) -> dict[str, Any]:
        rows = []
        for name, bytes_per_param in self.QUANTS.items():
            needed = spec.total_bytes(bytes_per_param, batch)
            rows.append(
                {
                    "quant": name,
                    "bytes_per_param": bytes_per_param,
                    "needed_gb": round(needed / (1024 ** 3), 3),
                    "fits": needed <= self.usable_bytes,
                    "headroom_gb": round((self.usable_bytes - needed) / (1024 ** 3), 3),
                }
            )
        recommended = next((r for r in rows if r["fits"]), rows[-1])
        return {
            "model": spec.name,
            "vram_gb": round(self.vram_bytes / (1024 ** 3), 2),
            "usable_gb": round(self.usable_bytes / (1024 ** 3), 2),
            "options": rows,
            "recommended": recommended["quant"],
            "offload_required": not any(r["fits"] for r in rows[:1]),
        }
