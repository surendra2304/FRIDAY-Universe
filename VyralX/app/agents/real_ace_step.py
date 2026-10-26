"""
VyralX Deep Layer 12 — Real ACE-Step 1.5 Music Engine

Real repository integration:
    ace-step/ACE-Step-1.5
    Upstream: https://github.com/ace-step/ACE-Step-1.5

ACE-Step v1.5 is an open music foundation model: a language model conditions on
captions + lyrics, a latent audio codec compresses the waveform, and a
diffusion transformer (DiT, up to 4B in the XL series) generates the latent
track with flow matching (``base`` / ``sft`` / ``turbo`` variants).

This module ports the *planning and conditioning* maths that decides what the
model produces, so VyralX can drive real generation runs and validate them
offline:

* :class:`CaptionParser` / :class:`MusicTags` — caption tag parsing into a
  conditioning vector (genre, mood, instrument, tempo, era, vocal timbre).
* :class:`LyricStructurer` — ``[verse]`` / ``[chorus]`` sections, syllable
  counting and bar-accurate lyric timing.
* :class:`TempoMap` — bpm/time-signature grid (bars, beats, seconds).
* :class:`LatentAudioCodec` — latent frame maths and chunked-attention plan.
* :class:`DiTConfig` — parameter/FLOPs/VRAM estimates for base/sft/turbo/XL.
* :class:`FlowMatchingSampler` — rectified-flow step schedule with CFG.
* :class:`TrackAssembler` — fades, loudness normalisation, export plan.
* :class:`AceStepPipeline` — end-to-end generation plan and report.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


# ─────────────────────────────────────────────────────────────────────────────
# Caption conditioning
# ─────────────────────────────────────────────────────────────────────────────

GENRES = (
    "pop", "rock", "hip hop", "rap", "trap", "r&b", "soul", "funk", "jazz", "blues",
    "electronic", "edm", "house", "techno", "trance", "dubstep", "lo-fi", "ambient",
    "classical", "orchestral", "cinematic", "folk", "country", "reggae", "latin",
    "salsa", "bossa nova", "metal", "punk", "indie", "synthwave", "drum and bass",
    "gospel", "k-pop", "j-pop", "afrobeat", "disco", "chiptune",
)

MOODS = (
    "happy", "sad", "melancholic", "uplifting", "dark", "epic", "calm", "relaxing",
    "energetic", "aggressive", "romantic", "nostalgic", "dreamy", "tense", "hopeful",
    "mysterious", "playful", "triumphant", "lonely", "angry", "peaceful",
)

INSTRUMENTS = (
    "piano", "guitar", "acoustic guitar", "electric guitar", "bass", "synth",
    "strings", "violin", "cello", "drums", "drum machine", "808", "trumpet", "saxophone",
    "flute", "harp", "organ", "choir", "pad", "pluck", "brass", "percussion", "koto",
    "sitar", "tabla", "banjo", "accordion",
)

TEMPO_WORDS = {
    "very slow": 60, "slow": 76, "ballad": 72, "moderate": 96, "mid-tempo": 104,
    "uptempo": 120, "upbeat": 124, "fast": 140, "driving": 132, "frantic": 160,
}

ERAS = ("70s", "80s", "90s", "2000s", "2010s", "retro", "vintage", "modern", "futuristic")

VOCAL_TIMBRES = {
    "male": ("male vocal", "male vocals", "baritone", "tenor"),
    "female": ("female vocal", "female vocals", "soprano", "alto"),
    "raspy": ("raspy", "gritty", "husky"),
    "breathy": ("breathy", "airy", "soft vocal"),
    "choir": ("choir", "choral"),
}


@dataclass
class MusicTags:
    """Structured conditioning extracted from a caption."""

    genres: list[str] = field(default_factory=list)
    moods: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    eras: list[str] = field(default_factory=list)
    vocal_timbres: list[str] = field(default_factory=list)
    tempo_word: str = ""
    suggested_bpm: int = 0
    instrumental: bool = False
    language: str = "en"

    @property
    def primary_genre(self) -> str:
        return self.genres[0] if self.genres else "unspecified"

    @property
    def tag_count(self) -> int:
        return len(self.genres) + len(self.moods) + len(self.instruments) + len(self.eras) + len(self.vocal_timbres)

    def conditioning_vector(self) -> list[float]:
        """Deterministic sparse conditioning vector (genre/mood/instrument blocks)."""
        vector: list[float] = []
        for table, selected in (
            (GENRES, self.genres),
            (MOODS, self.moods),
            (INSTRUMENTS, self.instruments),
            (ERAS, self.eras),
        ):
            block = [1.0 if term in selected else 0.0 for term in table]
            total = sum(block)
            vector.extend([value / total if total else 0.0 for value in block])
        return [round(v, 4) for v in vector]

    @property
    def conditioning_dim(self) -> int:
        return len(GENRES) + len(MOODS) + len(INSTRUMENTS) + len(ERAS)

    def describe(self) -> str:
        parts = [", ".join(self.genres) or "unspecified genre"]
        if self.moods:
            parts.append(", ".join(self.moods) + " mood")
        if self.instruments:
            parts.append("with " + ", ".join(self.instruments))
        if self.eras:
            parts.append(", ".join(self.eras) + " production")
        if self.instrumental:
            parts.append("instrumental")
        elif self.vocal_timbres:
            parts.append(", ".join(self.vocal_timbres) + " lead")
        return "; ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genres": self.genres,
            "moods": self.moods,
            "instruments": self.instruments,
            "eras": self.eras,
            "vocal_timbres": self.vocal_timbres,
            "tempo_word": self.tempo_word,
            "suggested_bpm": self.suggested_bpm,
            "instrumental": self.instrumental,
            "language": self.language,
            "conditioning_dim": self.conditioning_dim,
            "description": self.describe(),
        }


class CaptionParser:
    """Free-text caption -> :class:`MusicTags` conditioning."""

    def __init__(self, default_bpm: int = 120):
        self.default_bpm = default_bpm

    def parse(self, caption: str, language: str = "en") -> MusicTags:
        text = (caption or "").lower()
        tags = MusicTags(language=language)

        def collect(table: tuple[str, ...]) -> list[str]:
            found = [term for term in table if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text)]
            return found

        tags.genres = collect(GENRES)
        tags.moods = collect(MOODS)
        tags.instruments = collect(INSTRUMENTS)
        tags.eras = collect(ERAS)
        tags.instrumental = bool(re.search(r"\b(instrumental|no vocal|no vocals)\b", text))
        for name, cues in VOCAL_TIMBRES.items():
            pattern = r"(?<![a-z])(" + "|".join(re.escape(cue) for cue in cues) + r")(?![a-z])"
            if re.search(pattern, text):
                tags.vocal_timbres.append(name)
        for word, bpm in TEMPO_WORDS.items():
            if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text):
                if not tags.tempo_word or bpm > tags.suggested_bpm:
                    tags.tempo_word, tags.suggested_bpm = word, bpm
        match = re.search(r"(\d{2,3})\s*(?:bpm|beats per minute)", text)
        if match:
            tags.suggested_bpm = int(match.group(1))
        if not tags.suggested_bpm:
            tags.suggested_bpm = self.default_bpm
        return tags


# ─────────────────────────────────────────────────────────────────────────────
# Lyrics
# ─────────────────────────────────────────────────────────────────────────────

SECTION_PATTERN = re.compile(r"^\s*\[\s*([a-zA-Z0-9_\- ]+)\s*\]\s*$")
STRUCTURE_TAGS = ("intro", "verse", "pre-chorus", "chorus", "post-chorus", "bridge", "hook", "drop", "outro", "solo", "interlude")


@dataclass
class LyricLine:
    """One lyric line placed on the musical grid."""

    text: str
    section: str = "verse"
    index: int = 0
    syllables: int = 0
    start_bar: float = 0.0
    bars: float = 1.0
    start_s: float = 0.0
    end_s: float = 0.0

    @property
    def duration(self) -> float:
        return round(self.end_s - self.start_s, 4)

    @property
    def syllables_per_second(self) -> float:
        return round(safe_div(self.syllables, self.duration), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "section": self.section,
            "text": self.text,
            "syllables": self.syllables,
            "start_bar": round(self.start_bar, 3),
            "bars": round(self.bars, 3),
            "start_s": round(self.start_s, 3),
            "end_s": round(self.end_s, 3),
            "sps": self.syllables_per_second,
        }


class LyricStructurer:
    """Parse ``[section]`` lyric scripts and lay them on the tempo grid."""

    VOWELS = "aeiouy"

    def __init__(self, bars_per_line: float = 1.0, max_syllables_per_second: float = 6.0):
        self.bars_per_line = bars_per_line
        self.max_syllables_per_second = max_syllables_per_second

    @classmethod
    def count_syllables(cls, text: str) -> int:
        """English syllable estimate: vowel groups minus silent trailing 'e'."""
        words = re.findall(r"[a-zA-Z']+", (text or "").lower())
        total = 0
        for word in words:
            groups = re.findall(r"[aeiouy]+", word)
            count = len(groups)
            if len(word) > 3 and word.endswith("e") and count > 1:
                count -= 1
            total += max(1, count)
        return total

    def parse(self, lyrics: str) -> list[tuple[str, str]]:
        """Returns ``(section, line)`` pairs."""
        section = "verse"
        out: list[tuple[str, str]] = []
        for raw in (lyrics or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            match = SECTION_PATTERN.match(line)
            if match:
                section = match.group(1).strip().lower()
                continue
            out.append((section, line))
        return out

    def structure(self, lyrics: str, tempo: "TempoMap", bars_per_line: float | None = None) -> list[LyricLine]:
        bars = bars_per_line if bars_per_line is not None else self.bars_per_line
        lines: list[LyricLine] = []
        cursor_bar = 0.0
        for index, (section, text) in enumerate(self.parse(lyrics)):
            syllables = self.count_syllables(text)
            alloc = bars
            if syllables:
                needed_s = safe_div(syllables, self.max_syllables_per_second)
                alloc = max(alloc, needed_s / max(0.001, tempo.seconds_per_bar))
            alloc = round(alloc * 2) / 2  # quantise to half bars
            lines.append(
                LyricLine(
                    text=text,
                    section=section,
                    index=index,
                    syllables=syllables,
                    start_bar=round(cursor_bar, 3),
                    bars=round(alloc, 3),
                    start_s=round(tempo.bar_to_time(cursor_bar), 4),
                    end_s=round(tempo.bar_to_time(cursor_bar + alloc), 4),
                )
            )
            cursor_bar += alloc
        return lines

    def report(self, lines: list[LyricLine]) -> dict[str, Any]:
        if not lines:
            return {"lines": 0}
        sections = Counter(line.section for line in lines)
        sps = [line.syllables_per_second for line in lines if line.duration > 0]
        return {
            "lines": len(lines),
            "sections": dict(sections),
            "total_syllables": sum(line.syllables for line in lines),
            "total_bars": round(sum(line.bars for line in lines), 3),
            "last_bar": round(max(line.start_bar + line.bars for line in lines), 3),
            "mean_syllables_per_second": round(safe_div(sum(sps), len(sps)), 3) if sps else 0.0,
            "over_density": [line.index for line in lines if line.syllables_per_second > self.max_syllables_per_second],
        }

    def to_lrc(self, lines: list[LyricLine]) -> str:
        rows = []
        for line in lines:
            minutes = int(line.start_s // 60)
            seconds = line.start_s % 60
            rows.append(f"[{minutes:02d}:{seconds:05.2f}]{line.text}")
        return "\n".join(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Tempo grid
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TempoMap:
    """bpm / time-signature grid with bar, beat and second conversions."""

    bpm: float = 120.0
    beats_per_bar: int = 4
    beat_unit: int = 4

    @property
    def seconds_per_beat(self) -> float:
        return round(60.0 / max(1e-6, self.bpm), 6)

    @property
    def seconds_per_bar(self) -> float:
        return round(self.seconds_per_beat * self.beats_per_bar, 6)

    @property
    def bars_per_minute(self) -> float:
        return round(self.bpm / self.beats_per_bar, 4)

    def bar_to_time(self, bar: float) -> float:
        return round(bar * self.seconds_per_bar, 6)

    def time_to_bar(self, seconds: float) -> float:
        return round(seconds / self.seconds_per_bar, 6)

    def bars_for_duration(self, duration_s: float) -> float:
        return round(duration_s / self.seconds_per_bar, 4)

    def duration_for_bars(self, bars: float) -> float:
        return round(bars * self.seconds_per_bar, 4)

    def beat_grid(self, bars: int) -> list[float]:
        return [round(i * self.seconds_per_beat, 6) for i in range(int(bars * self.beats_per_bar))]

    def downbeats(self, bars: int) -> list[float]:
        return [self.bar_to_time(i) for i in range(bars)]

    def grid_report(self, duration_s: float) -> dict[str, Any]:
        return {
            "bpm": self.bpm,
            "time_signature": f"{self.beats_per_bar}/{self.beat_unit}",
            "seconds_per_beat": self.seconds_per_beat,
            "seconds_per_bar": self.seconds_per_bar,
            "bars": self.bars_for_duration(duration_s),
            "beats": round(duration_s / self.seconds_per_beat, 3),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Latent codec + DiT
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class LatentAudioCodec:
    """Latent audio codec geometry (ACE-Step uses a compressed latent grid)."""

    latent_frame_rate: float = 25.0     # latent frames per second
    latent_dim: int = 64
    sample_rate: int = 44100
    downsample: int = 1024              # audio samples per latent frame (pre-latent)
    chunk_seconds: float = 10.0
    chunk_overlap_seconds: float = 1.0

    @property
    def compression_ratio(self) -> float:
        return round(self.sample_rate / self.latent_frame_rate, 2)

    def frames_for(self, duration_s: float) -> int:
        return int(round(duration_s * self.latent_frame_rate))

    def duration_for(self, frames: int) -> float:
        return round(frames / self.latent_frame_rate, 4)

    def token_count(self, duration_s: float) -> int:
        return self.frames_for(duration_s)

    def chunk_plan(self, duration_s: float) -> dict[str, Any]:
        """Chunked attention plan: windows with overlap and cross-fade."""
        frames = self.frames_for(duration_s)
        chunk = max(1, int(round(self.chunk_seconds * self.latent_frame_rate)))
        overlap = int(round(self.chunk_overlap_seconds * self.latent_frame_rate))
        if frames <= chunk:
            return {"chunks": 1, "chunk_frames": frames, "overlap_frames": 0, "total_frames": frames, "windows": [(0, frames)]}
        stride = max(1, chunk - overlap)
        windows: list[tuple[int, int]] = []
        start = 0
        while start < frames:
            end = min(frames, start + chunk)
            windows.append((start, end))
            if end == frames:
                break
            start += stride
        return {
            "chunks": len(windows),
            "chunk_frames": chunk,
            "overlap_frames": overlap,
            "total_frames": frames,
            "windows": windows,
            "effective_seconds": round(self.duration_for(sum(e - s for s, e in windows)), 3),
        }


DIT_VARIANTS: dict[str, dict[str, Any]] = {
    "base": {"layers": 32, "hidden": 2048, "heads": 16, "params_b": 2.6, "default_steps": 50, "guidance": 4.5, "is_distilled": False},
    "sft": {"layers": 32, "hidden": 2048, "heads": 16, "params_b": 2.6, "default_steps": 32, "guidance": 4.0, "is_distilled": False},
    "turbo": {"layers": 24, "hidden": 1536, "heads": 12, "params_b": 1.2, "default_steps": 8, "guidance": 3.0, "is_distilled": True},
    "xl-base": {"layers": 48, "hidden": 3072, "heads": 24, "params_b": 4.0, "default_steps": 60, "guidance": 5.0, "is_distilled": False},
    "xl-sft": {"layers": 48, "hidden": 3072, "heads": 24, "params_b": 4.0, "default_steps": 40, "guidance": 4.5, "is_distilled": False},
    "xl-turbo": {"layers": 48, "hidden": 3072, "heads": 24, "params_b": 4.0, "default_steps": 10, "guidance": 3.5, "is_distilled": True},
}


@dataclass
class DiTConfig:
    """Transformer geometry + cost model for one ACE-Step variant."""

    name: str = "turbo"
    layers: int = 24
    hidden: int = 1536
    heads: int = 12
    ff_mult: int = 4
    params_b: float = 1.2
    dtype_bytes: int = 2
    default_steps: int = 8
    guidance: float = 3.0
    is_distilled: bool = True

    @classmethod
    def for_variant(cls, name: str) -> "DiTConfig":
        if name not in DIT_VARIANTS:
            raise KeyError(f"unknown ACE-Step variant: {name}")
        return cls(name=name, **DIT_VARIANTS[name])

    @staticmethod
    def variants() -> list[str]:
        return sorted(DIT_VARIANTS)

    @property
    def head_dim(self) -> int:
        return self.hidden // self.heads

    def weight_bytes(self, quant_bytes: int | None = None) -> int:
        return int(self.params_b * 1e9 * (quant_bytes or self.dtype_bytes))

    def flops_per_step(self, tokens: int) -> float:
        """Rough transformer FLOPs: 2 * params * tokens * 3 (fwd ≈ 2N, bwd ≈ 4N)."""
        return 2.0 * self.params_b * 1e9 * tokens * 3.0

    def vram_bytes(self, tokens: int, batch: int = 1) -> int:
        kv = 2 * self.layers * self.hidden * tokens * batch * self.dtype_bytes
        activations = self.layers * tokens * batch * self.hidden * self.dtype_bytes * 8
        return int(self.weight_bytes() + kv + activations)

    def estimate_seconds(self, tokens: int, steps: int, throughput_flops: float = 3e13) -> float:
        return round(safe_div(self.flops_per_step(tokens) * steps, throughput_flops), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layers": self.layers,
            "hidden": self.hidden,
            "heads": self.heads,
            "head_dim": self.head_dim,
            "params_b": self.params_b,
            "default_steps": self.default_steps,
            "guidance": self.guidance,
            "is_distilled": self.is_distilled,
            "weight_gb": round(self.weight_bytes() / (1024 ** 3), 3),
        }


class FlowMatchingSampler:
    """Rectified-flow step schedule with classifier-free guidance."""

    def __init__(self, steps: int = 8, guidance: float = 3.0, shift: float = 3.0, cfg_interval: tuple[float, float] = (0.0, 1.0)):
        self.steps = max(1, steps)
        self.guidance = guidance
        self.shift = shift
        self.cfg_interval = cfg_interval

    def timesteps(self, tokens: int | None = None) -> list[float]:
        """Shifted 1 -> 0 schedule; larger contexts shift more (mu-style)."""
        raw = [1.0 - i / self.steps for i in range(self.steps + 1)]
        if self.shift <= 0:
            return [round(t, 6) for t in raw]
        scale = 1.0 + safe_div(math.log1p(max(0, tokens or 0)), math.log1p(4096.0)) * (self.shift - 1.0)
        shifted = [t ** (1.0 / scale) for t in raw]
        return [round(t, 6) for t in shifted]

    def cfg_active(self, t: float) -> bool:
        low, high = self.cfg_interval
        return low <= t <= high

    def step_size(self, tokens: int | None = None) -> dict[str, float]:
        schedule = self.timesteps(tokens)
        deltas = [schedule[i] - schedule[i + 1] for i in range(len(schedule) - 1)]
        return {
            "min": round(min(deltas), 6),
            "max": round(max(deltas), 6),
            "mean": round(safe_div(sum(deltas), len(deltas)), 6),
        }

    def report(self, tokens: int) -> dict[str, Any]:
        schedule = self.timesteps(tokens)
        return {
            "steps": self.steps,
            "guidance": self.guidance,
            "shift": self.shift,
            "schedule_first": schedule[0],
            "schedule_last": schedule[-1],
            "monotonic": all(a > b for a, b in zip(schedule, schedule[1:])),
            "step": self.step_size(tokens),
            "cfg_interval": list(self.cfg_interval),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Assembly + pipeline
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TrackSection:
    name: str
    start: float
    end: float
    fade_in: float = 0.0
    fade_out: float = 0.0
    gain_db: float = 0.0

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": self.duration,
            "fade_in": round(self.fade_in, 3),
            "fade_out": round(self.fade_out, 3),
            "gain_db": round(self.gain_db, 2),
        }


class TrackAssembler:
    """Fades, loudness normalisation and export plan for the rendered track."""

    def __init__(self, fade_in_s: float = 1.5, fade_out_s: float = 3.0, target_lufs: float = -14.0, ceiling_dbfs: float = -1.0):
        self.fade_in_s = fade_in_s
        self.fade_out_s = fade_out_s
        self.target_lufs = target_lufs
        self.ceiling_dbfs = ceiling_dbfs

    @staticmethod
    def rms_to_db(rms: float) -> float:
        return round(20 * math.log10(max(1e-10, rms)), 3)

    @staticmethod
    def db_to_gain(db: float) -> float:
        return round(10 ** (db / 20.0), 5)

    def estimate_lufs(self, rms: float) -> float:
        """RMS -> rough LUFS (integrated loudness runs ~3 dB above RMS for music)."""
        return round(self.rms_to_db(rms) + 3.0, 2)

    def normalisation_gain(self, measured_rms: float, true_peak: float = 1.0) -> float:
        """Gain needed to reach the target while staying under the peak ceiling."""
        needed = self.target_lufs - self.estimate_lufs(measured_rms)
        peak_headroom = 20 * math.log10(max(1e-6, self.db_to_gain(self.ceiling_dbfs) / max(1e-6, true_peak)))
        return round(min(needed, peak_headroom), 3)

    def sections_for(self, lines: list[LyricLine], duration_s: float) -> list[TrackSection]:
        if not lines:
            return [TrackSection("main", 0.0, duration_s, self.fade_in_s, self.fade_out_s)]
        sections: list[TrackSection] = []
        current_name = lines[0].section
        start = lines[0].start_s
        for line in lines[1:] + [LyricLine(text="", section="__end__", start_s=duration_s, end_s=duration_s)]:
            if line.section != current_name:
                end = line.start_s
                sections.append(
                    TrackSection(
                        name=current_name,
                        start=round(start, 3),
                        end=round(end, 3),
                        fade_in=self.fade_in_s if not sections else 0.15,
                        fade_out=0.15,
                    )
                )
                current_name, start = line.section, line.start_s
        if sections:
            sections[-1].fade_out = self.fade_out_s
        return sections

    def export_plan(self, duration_s: float, sections: list[TrackSection], bitrate_kbps: int = 320, sample_rate: int = 44100) -> dict[str, Any]:
        size_bytes = int(duration_s * bitrate_kbps * 1000 / 8)
        return {
            "duration_s": round(duration_s, 3),
            "sections": [s.to_dict() for s in sections],
            "formats": [
                {"container": "wav", "sample_rate": sample_rate, "bit_depth": 24,
                 "size_bytes": int(duration_s * sample_rate * 3 * 2)},
                {"container": "mp3", "bitrate_kbps": bitrate_kbps, "size_bytes": size_bytes},
                {"container": "flac", "bitrate_kbps": int(bitrate_kbps * 2.2), "size_bytes": int(size_bytes * 2.2)},
            ],
            "target_lufs": self.target_lufs,
            "ceiling_dbfs": self.ceiling_dbfs,
        }


@dataclass
class MusicGenerationPlan:
    caption: str
    lyrics: str
    duration_s: float
    tempo: TempoMap
    tags: MusicTags
    variant: str
    dit: dict[str, Any]
    sampler: dict[str, Any]
    codec: dict[str, Any]
    lyrics_report: dict[str, Any]
    cost: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "caption": self.caption[:80],
            "duration_s": round(self.duration_s, 3),
            "tempo": self.tempo.grid_report(self.duration_s),
            "tags": self.tags.to_dict(),
            "variant": self.variant,
            "dit": self.dit,
            "sampler": self.sampler,
            "codec": self.codec,
            "lyrics": self.lyrics_report,
            "cost": self.cost,
        }


class AceStepPipeline:
    """End-to-end ACE-Step generation planner."""

    def __init__(
        self,
        variant: str = "turbo",
        codec: LatentAudioCodec | None = None,
        structurer: LyricStructurer | None = None,
        parser: CaptionParser | None = None,
        assembler: TrackAssembler | None = None,
    ):
        self.variant = variant
        self.codec = codec or LatentAudioCodec()
        self.structurer = structurer or LyricStructurer()
        self.parser = parser or CaptionParser()
        self.assembler = assembler or TrackAssembler()

    def plan(
        self,
        caption: str,
        lyrics: str = "",
        duration_s: float = 60.0,
        bpm: int | None = None,
        beats_per_bar: int = 4,
        steps: int | None = None,
        guidance: float | None = None,
    ) -> MusicGenerationPlan:
        tags = self.parser.parse(caption)
        tempo = TempoMap(bpm=float(bpm or tags.suggested_bpm), beats_per_bar=beats_per_bar)
        config = DiTConfig.for_variant(self.variant)
        use_steps = steps or config.default_steps
        use_guidance = guidance if guidance is not None else config.guidance
        sampler = FlowMatchingSampler(steps=use_steps, guidance=use_guidance)

        lines = self.structurer.structure(lyrics, tempo) if lyrics else []
        tokens = self.codec.token_count(duration_s)
        chunk_plan = self.codec.chunk_plan(duration_s)
        flops = config.flops_per_step(tokens) * use_steps

        return MusicGenerationPlan(
            caption=caption,
            lyrics=lyrics,
            duration_s=duration_s,
            tempo=tempo,
            tags=tags,
            variant=self.variant,
            dit={**config.to_dict(), "tokens": tokens, "flops_total": flops},
            sampler=sampler.report(tokens),
            codec={**chunk_plan, "latent_frame_rate": self.codec.latent_frame_rate,
                   "latent_dim": self.codec.latent_dim, "compression_ratio": self.codec.compression_ratio},
            lyrics_report=self.structurer.report(lines),
            cost={
                "estimate_seconds": config.estimate_seconds(tokens, use_steps),
                "vram_gb": round(config.vram_bytes(tokens) / (1024 ** 3), 3),
                "weight_gb": round(config.weight_bytes() / (1024 ** 3), 3),
                "forward_passes": use_steps * (2 if use_guidance > 1.0 else 1),
                "tokens": tokens,
            },
        )

    def generate(
        self,
        caption: str,
        lyrics: str = "",
        duration_s: float = 60.0,
        bpm: int | None = None,
        steps: int | None = None,
        guidance: float | None = None,
    ) -> dict[str, Any]:
        """Plan the run, then lay out the track (sections, fades, exports)."""
        plan = self.plan(caption, lyrics, duration_s, bpm, 4, steps, guidance)
        tempo = plan.tempo
        lines = self.structurer.structure(lyrics, tempo) if lyrics else []
        sections = self.assembler.sections_for(lines, duration_s)
        measured_rms = 0.18
        return {
            "plan": plan.to_dict(),
            "sections": [s.to_dict() for s in sections],
            "lrc": self.structurer.to_lrc(lines) if lines else "",
            "loudness": {
                "measured_rms": measured_rms,
                "estimated_lufs": self.assembler.estimate_lufs(measured_rms),
                "normalisation_gain_db": self.assembler.normalisation_gain(measured_rms, true_peak=0.95),
                "target_lufs": self.assembler.target_lufs,
            },
            "export": self.assembler.export_plan(duration_s, sections),
        }

    def compare_variants(self, caption: str, duration_s: float = 60.0, lyrics: str = "") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in DiTConfig.variants():
            saved = self.variant
            self.variant = name
            plan = self.plan(caption, lyrics, duration_s)
            out[name] = {
                "steps": plan.sampler["steps"],
                "guidance": plan.sampler["guidance"],
                "estimate_seconds": plan.cost["estimate_seconds"],
                "vram_gb": plan.cost["vram_gb"],
                "params_b": plan.dit["params_b"],
            }
            self.variant = saved
        return out
