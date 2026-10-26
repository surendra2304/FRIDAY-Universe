"""
VyralX Deep Layer 12 — Real HyperFrames Engine (HTML -> deterministic MP4)

Real repository integration:
    heygen-com/hyperframes
    Upstream: https://github.com/heygen-com/hyperframes

HyperFrames renders HTML, CSS, media and *seekable* animations into
deterministic MP4 videos: an authoring format (HTML + keyframes) plus a
renderer contract that guarantees the same input always produces the same
frames. This module ports the parts that are pure logic — the scene/timeline
model, keyframe interpolation, transitions, caption alignment, HTML scene-graph
parsing and the deterministic render manifest — into the VyralX agent using
only the standard library.

Classes
-------
StyleDeclaration      — CSS declaration block -> typed values (px, %, colors).
SceneNode             — one node of a parsed HTML scene graph.
HtmlSceneGraph        — real HTMLParser-based scene graph with time sampling.
Keyframe / AnimationTrack — easing-based, seekable property animation.
TransitionScheduler   — scene overlaps, transition kinds, validation.
FrameClock            — frame <-> time conversion at a fixed fps.
CaptionAligner        — word-level caption cue timing with drift correction.
DeterministicRng      — hash-seeded PRNG so renders are reproducible.
RenderManifest        — content-addressed manifest of every frame decision.
FfmpegCommandBuilder  — deterministic ffmpeg argv for the frame pipeline.
HyperframesComposer   — end-to-end: scenes -> timeline -> cues -> manifest.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Callable

_COLOR_NAMES = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "transparent": (0, 0, 0),
    "gray": (128, 128, 128), "grey": (128, 128, 128), "yellow": (255, 255, 0),
    "orange": (255, 165, 0), "purple": (128, 0, 128), "pink": (255, 192, 203),
}

_HEX_RE = re.compile(r"^#([0-9a-f]{3}|[0-9a-f]{6})$", re.IGNORECASE)
_RGB_RE = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$", re.IGNORECASE)
_NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(px|%|em|rem|vh|vw|s|ms|deg)?$")


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


# ─────────────────────────────────────────────────────────────────────────────
# CSS values
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Length:
    """A CSS length with its unit resolved against a reference size."""

    value: float
    unit: str = "px"

    def resolve(self, reference: float = 1080.0) -> float:
        if self.unit == "px":
            return self.value
        if self.unit == "%":
            return self.value / 100.0 * reference
        if self.unit in ("em", "rem"):
            return self.value * 16.0
        if self.unit in ("vh", "vw"):
            return self.value / 100.0 * reference
        return self.value

    @staticmethod
    def parse(raw: str) -> "Length | None":
        match = _NUM_RE.match((raw or "").strip())
        if not match:
            return None
        return Length(float(match.group(1)), match.group(2) or "px")


@dataclass(frozen=True)
class Color:
    """An RGBA color parsed from any CSS color syntax we support."""

    r: int = 0
    g: int = 0
    b: int = 0
    a: float = 1.0

    @property
    def hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @property
    def luminance(self) -> float:
        """Rec. 709 relative luminance, 0-1."""
        return round((0.2126 * self.r + 0.7152 * self.g + 0.0722 * self.b) / 255.0, 4)

    @property
    def is_dark(self) -> bool:
        return self.luminance < 0.35

    def contrast_ratio(self, other: "Color") -> float:
        def lin(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

        def lum(col: "Color") -> float:
            return 0.2126 * lin(col.r) + 0.7152 * lin(col.g) + 0.0722 * lin(col.b)

        l1, l2 = sorted((lum(self), lum(other)), reverse=True)
        return round(safe_div(l1 + 0.05, l2 + 0.05), 3)

    @staticmethod
    def parse(raw: str) -> "Color | None":
        text = (raw or "").strip().lower()
        if not text:
            return None
        if text in _COLOR_NAMES:
            r, g, b = _COLOR_NAMES[text]
            return Color(r, g, b, 0.0 if text == "transparent" else 1.0)
        hex_match = _HEX_RE.match(text)
        if hex_match:
            digits = hex_match.group(1)
            if len(digits) == 3:
                r, g, b = (int(c * 2, 16) for c in digits)
            else:
                r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
            return Color(r, g, b)
        rgb_match = _RGB_RE.match(text)
        if rgb_match:
            r, g, b = (int(rgb_match.group(i)) for i in (1, 2, 3))
            alpha = float(rgb_match.group(4)) if rgb_match.group(4) else 1.0
            return Color(r, g, b, alpha)
        return None


class StyleDeclaration:
    """A parsed inline ``style="..."`` declaration block."""

    ANIMATABLE = ("opacity", "translateX", "translateY", "scale", "rotate", "width", "height", "blur")

    def __init__(self, raw: str = ""):
        self.raw = raw or ""
        self.props: dict[str, str] = {}
        self.parse(self.raw)

    def parse(self, raw: str) -> dict[str, str]:
        self.props = {}
        for chunk in (raw or "").split(";"):
            if ":" not in chunk:
                continue
            key, _, value = chunk.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key:
                self.props[key] = value
        return self.props

    def get(self, name: str, default: str = "") -> str:
        return self.props.get(name, default)

    def color(self, name: str, fallback: Color | None = None) -> Color | None:
        parsed = Color.parse(self.get(name))
        return parsed if parsed is not None else fallback

    def length(self, name: str, reference: float = 1080.0, default: float = 0.0) -> float:
        parsed = Length.parse(self.get(name))
        return parsed.resolve(reference) if parsed else default

    def number(self, name: str, default: float = 1.0) -> float:
        parsed = Length.parse(self.get(name))
        return parsed.value if parsed else default

    def opacity(self) -> float:
        return clamp01(self.number("opacity", 1.0))

    def to_dict(self) -> dict[str, str]:
        return dict(self.props)


# ─────────────────────────────────────────────────────────────────────────────
# HTML scene graph
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SceneNode:
    """One element of the parsed HTML scene."""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    style: StyleDeclaration = field(default_factory=StyleDeclaration)
    text: str = ""
    children: list["SceneNode"] = field(default_factory=list)
    depth: int = 0

    @property
    def element_id(self) -> str:
        return self.attrs.get("id", "")

    @property
    def classes(self) -> list[str]:
        return [c for c in self.attrs.get("class", "").split() if c]

    @property
    def is_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def is_media(self) -> bool:
        return self.tag in ("img", "video", "audio", "source")

    @property
    def src(self) -> str:
        return self.attrs.get("src", "")

    def walk(self) -> list["SceneNode"]:
        out: list[SceneNode] = [self]
        for child in self.children:
            out.extend(child.walk())
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "id": self.element_id,
            "classes": self.classes,
            "style": self.style.to_dict(),
            "text": self.text.strip()[:80],
            "children": [c.to_dict() for c in self.children],
        }


class _SceneGraphBuilder(HTMLParser):
    """Real HTML -> :class:`SceneNode` tree (stdlib html.parser)."""

    VOID = {"br", "img", "hr", "meta", "link", "input", "source"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = SceneNode(tag="root")
        self._stack: list[SceneNode] = [self.root]
        self.node_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = SceneNode(
            tag=tag,
            attrs={k: (v or "") for k, v in attrs},
            style=StyleDeclaration(dict(attrs).get("style", "")),
            depth=len(self._stack) - 1,
        )
        self._stack[-1].children.append(node)
        self.node_count += 1
        if tag not in self.VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = SceneNode(
            tag=tag,
            attrs={k: (v or "") for k, v in attrs},
            style=StyleDeclaration(dict(attrs).get("style", "")),
            depth=len(self._stack) - 1,
        )
        self._stack[-1].children.append(node)
        self.node_count += 1

    def handle_endtag(self, tag: str) -> None:
        for idx in range(len(self._stack) - 1, 0, -1):
            if self._stack[idx].tag == tag:
                del self._stack[idx:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._stack[-1].text += data


class HtmlSceneGraph:
    """Parses an HTML scene and answers structural + sampling questions."""

    def __init__(self, html: str):
        self.html = html or ""
        builder = _SceneGraphBuilder()
        builder.feed(self.html)
        builder.close()
        self.root = builder.root
        self.node_count = builder.node_count

    @property
    def nodes(self) -> list[SceneNode]:
        return self.root.walk()

    def find(self, selector: str) -> list[SceneNode]:
        """Supports ``#id``, ``.class`` and plain tag selectors."""
        if selector.startswith("#"):
            wanted = selector[1:]
            return [n for n in self.nodes if n.element_id == wanted]
        if selector.startswith("."):
            wanted = selector[1:]
            return [n for n in self.nodes if wanted in n.classes]
        return [n for n in self.nodes if n.tag == selector]

    def text_content(self) -> str:
        return " ".join(n.text.strip() for n in self.nodes if n.is_text).strip()

    def media_sources(self) -> list[str]:
        return [n.src for n in self.nodes if n.is_media and n.src]

    def z_order(self) -> list[SceneNode]:
        """Paint order: document order, then explicit z-index (stable)."""
        items = [n for n in self.nodes if n.tag != "root"]
        items.sort(key=lambda n: (n.style.number("z-index", 0.0),))
        return items

    def visible_at(self, time_s: float, scene_start: float = 0.0) -> list[SceneNode]:
        """Elements whose animation window (if any) covers ``time_s``.

        Elements declare their window with ``--enter``/``--exit`` style values in
        seconds; elements without them are visible for the whole scene.
        """
        local = time_s - scene_start
        out: list[SceneNode] = []
        for node in self.nodes:
            if node.tag == "root":
                continue
            enter_raw = node.style.get("--enter")
            exit_raw = node.style.get("--exit")
            enter = Length.parse(enter_raw).value if enter_raw else 0.0
            exit_at = Length.parse(exit_raw).value if exit_raw else math.inf
            if enter <= local < exit_at:
                out.append(node)
        return out

    def summary(self) -> dict[str, Any]:
        tags: dict[str, int] = defaultdict(int)
        for node in self.nodes:
            tags[node.tag] += 1
        return {
            "nodes": self.node_count,
            "tag_mix": dict(sorted(tags.items(), key=lambda kv: -kv[1])),
            "media": self.media_sources(),
            "text_chars": len(self.text_content()),
            "words": len(self.text_content().split()),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Frame clock + deterministic randomness
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FrameClock:
    """Converts between frame indices and timestamps at a fixed fps."""

    fps: float = 30.0
    duration_s: float = 0.0

    @property
    def total_frames(self) -> int:
        return int(round(self.duration_s * self.fps))

    @property
    def frame_duration(self) -> float:
        return safe_div(1.0, self.fps)

    def time_at(self, frame: int) -> float:
        return round(frame * self.frame_duration, 6)

    def frame_at(self, time_s: float) -> int:
        return max(0, min(self.total_frames - 1, int(math.floor(time_s * self.fps))))

    def frame_times(self) -> list[float]:
        return [self.time_at(i) for i in range(self.total_frames)]

    def seek(self, time_s: float) -> dict[str, Any]:
        frame = self.frame_at(time_s)
        return {"frame": frame, "time": self.time_at(frame), "snapped_time": time_s, "fps": self.fps}


class DeterministicRng:
    """Hash-seeded PRNG (splitmix-style) so every render is byte-identical."""

    MASK64 = (1 << 64) - 1

    def __init__(self, seed: str | int = "hyperframes"):
        if isinstance(seed, str):
            digest = hashlib.sha256(seed.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big")
        self.state = seed & self.MASK64 or 0x9E3779B97F4A7C15

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & self.MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self.MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self.MASK64
        return (z ^ (z >> 31)) & self.MASK64

    def random(self) -> float:
        return (self.next_u64() >> 11) / float(1 << 53)

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.random()

    def int_between(self, low: int, high: int) -> int:
        if high <= low:
            return low
        return low + int(self.next_u64() % (high - low + 1))

    def choice(self, items: list[Any]) -> Any:
        if not items:
            raise ValueError("cannot choose from an empty sequence")
        return items[int(self.next_u64() % len(items))]


# ─────────────────────────────────────────────────────────────────────────────
# Keyframes + tracks
# ─────────────────────────────────────────────────────────────────────────────

EASINGS: dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1.0 - (1.0 - t) ** 2,
    "ease_in_out": lambda t: 3 * t * t - 2 * t * t * t,
    "ease_in_cubic": lambda t: t ** 3,
    "ease_out_cubic": lambda t: 1.0 - (1.0 - t) ** 3,
    "ease_in_out_cubic": lambda t: 4 * t ** 3 if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2,
    "ease_out_expo": lambda t: 1.0 if t >= 1.0 else 1.0 - 2 ** (-10 * t),
    "ease_out_back": lambda t: 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
    "ease_out_elastic": lambda t: 1.0 if t in (0.0, 1.0) else 2 ** (-9 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1,
    "step": lambda t: 0.0 if t < 1.0 else 1.0,
}


def cubic_bezier(p1x: float, p1y: float, p2x: float, p2y: float) -> Callable[[float], float]:
    """CSS ``cubic-bezier(x1,y1,x2,y2)`` timing function (Newton-refined)."""

    def bezier(a: float, b: float, t: float) -> float:
        return 3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3

    def slope(a: float, b: float, t: float) -> float:
        return 3 * a * (1 - 4 * t + 3 * t ** 2) + 3 * b * (2 * t - 3 * t ** 2) + 3 * t ** 2

    def easing(x: float) -> float:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        t = x
        for _ in range(8):
            current = bezier(p1x, p2x, t) - x
            if abs(current) < 1e-6:
                break
            derivative = slope(p1x, p2x, t)
            if abs(derivative) < 1e-9:
                break
            t -= current / derivative
        return bezier(p1y, p2y, t)

    return easing


def spring(stiffness: float = 180.0, damping: float = 22.0, mass: float = 1.0) -> Callable[[float], float]:
    """Critically-ish damped spring curve sampled over unit progress."""

    def easing(t: float) -> float:
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        omega = math.sqrt(stiffness / mass)
        zeta = damping / (2 * math.sqrt(stiffness * mass))
        if zeta < 1:
            wd = omega * math.sqrt(1 - zeta * zeta)
            return 1 - math.exp(-zeta * omega * t) * (math.cos(wd * t) + (zeta * omega / wd) * math.sin(wd * t))
        return 1 - (1 + omega * t) * math.exp(-omega * t)

    return easing


@dataclass
class Keyframe:
    """A value at a specific local time with an easing curve into the next one."""

    time_s: float
    value: float
    easing: str = "ease_in_out"

    def to_dict(self) -> dict[str, Any]:
        return {"time_s": round(self.time_s, 4), "value": round(self.value, 5), "easing": self.easing}


@dataclass
class AnimationTrack:
    """A seekable animation of one property, sampled at any time."""

    name: str
    keyframes: list[Keyframe] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.keyframes[0].time_s if self.keyframes else 0.0

    @property
    def end(self) -> float:
        return self.keyframes[-1].time_s if self.keyframes else 0.0

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 6)

    def add(self, time_s: float, value: float, easing: str = "ease_in_out") -> "AnimationTrack":
        self.keyframes.append(Keyframe(time_s, value, easing))
        self.keyframes.sort(key=lambda k: k.time_s)
        return self

    def _easing(self, name: str) -> Callable[[float], float]:
        if name in EASINGS:
            return EASINGS[name]
        match = re.match(r"cubic-bezier\(\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*\)", name or "")
        if match:
            return cubic_bezier(*(float(g) for g in match.groups()))
        match = re.match(r"spring\(\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", name or "")
        if match:
            return spring(*(float(g) for g in match.groups() if g is not None))
        return EASINGS["linear"]

    def sample(self, time_s: float) -> float:
        """Value of the property at ``time_s`` (clamped outside the track)."""
        frames = self.keyframes
        if not frames:
            return 0.0
        if len(frames) == 1 or time_s <= frames[0].time_s:
            return frames[0].value
        if time_s >= frames[-1].time_s:
            return frames[-1].value
        for i in range(len(frames) - 1):
            a, b = frames[i], frames[i + 1]
            if a.time_s <= time_s <= b.time_s:
                span = b.time_s - a.time_s
                progress = safe_div(time_s - a.time_s, span)
                eased = clamp01(self._easing(a.easing)(progress))
                return a.value + (b.value - a.value) * eased
        return frames[-1].value

    def samples(self, fps: float = 30.0) -> list[tuple[float, float]]:
        clock = FrameClock(fps=fps, duration_s=self.duration)
        return [(clock.time_at(i), round(self.sample(self.start + clock.time_at(i)), 6)) for i in range(clock.total_frames)]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "start": self.start, "end": self.end, "keyframes": [k.to_dict() for k in self.keyframes]}


# ─────────────────────────────────────────────────────────────────────────────
# Scenes, transitions, timeline
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SceneSpec:
    """One HTML scene in the composition."""

    scene_id: str
    html: str
    duration_s: float = 3.0
    transition_in: str = "cut"
    transition_out: str = "cut"
    transition_duration: float = 0.4
    background: str = "#000000"
    tracks: list[AnimationTrack] = field(default_factory=list)

    @property
    def scene_graph(self) -> HtmlSceneGraph:
        return HtmlSceneGraph(self.html)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "duration_s": round(self.duration_s, 3),
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
            "transition_duration": round(self.transition_duration, 3),
            "background": self.background,
            "tracks": [t.to_dict() for t in self.tracks],
            "html_chars": len(self.html),
        }


@dataclass
class PlacedScene:
    """A scene positioned on the timeline."""

    scene: SceneSpec
    start: float
    end: float
    transition_in_duration: float = 0.0
    transition_out_duration: float = 0.0

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 6)

    @property
    def midpoint(self) -> float:
        return round((self.start + self.end) / 2.0, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene.scene_id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": self.duration,
            "transition_in_duration": round(self.transition_in_duration, 3),
            "transition_out_duration": round(self.transition_out_duration, 3),
        }


class TransitionScheduler:
    """Lays scenes out on a timeline and resolves transition overlaps."""

    SUPPORTED = ("cut", "crossfade", "dip_to_black", "wipe_left", "wipe_right", "slide_up", "push_left")

    def __init__(self, default_transition: float = 0.4, allow_overlap: bool = True):
        self.default_transition = default_transition
        self.allow_overlap = allow_overlap

    def validate(self, scenes: list[SceneSpec]) -> list[str]:
        problems: list[str] = []
        for scene in scenes:
            for kind in (scene.transition_in, scene.transition_out):
                if kind not in self.SUPPORTED:
                    problems.append(f"{scene.scene_id}: unsupported transition '{kind}'")
            if scene.transition_duration < 0:
                problems.append(f"{scene.scene_id}: negative transition duration")
            if scene.transition_duration * 2 > scene.duration_s:
                problems.append(
                    f"{scene.scene_id}: transition {scene.transition_duration:.2f}s exceeds half the scene duration"
                )
            if scene.duration_s <= 0:
                problems.append(f"{scene.scene_id}: non-positive duration")
        if not scenes:
            problems.append("empty composition: no scenes")
        return problems

    def layout(self, scenes: list[SceneSpec]) -> list[PlacedScene]:
        cursor = 0.0
        placed: list[PlacedScene] = []
        for index, scene in enumerate(scenes):
            overlap = min(scene.transition_duration, self.default_transition) if scene.transition_in in ("crossfade", "push_left", "wipe_left", "wipe_right", "slide_up") else 0.0
            if not self.allow_overlap:
                overlap = 0.0
            start = max(0.0, cursor - overlap) if index > 0 else 0.0
            end = start + scene.duration_s
            placed.append(
                PlacedScene(
                    scene=scene,
                    start=round(start, 6),
                    end=round(end, 6),
                    transition_in_duration=overlap,
                    transition_out_duration=scene.transition_duration,
                )
            )
            cursor = end
        return placed

    def total_duration(self, placed: list[PlacedScene]) -> float:
        return round(max((p.end for p in placed), default=0.0), 6)

    def transition_curve(self, kind: str, progress: float) -> float:
        """Cross-fade weight for scene A at ``progress`` (0 -> 1)."""
        p = clamp01(progress)
        if kind == "cut":
            return 1.0 if p < 1.0 else 0.0
        if kind == "crossfade":
            return 1.0 - p
        if kind == "dip_to_black":
            return 1.0 - abs(2 * p - 1)
        if kind in ("wipe_left", "wipe_right", "slide_up", "push_left"):
            # Wipes reveal rather than blend: A holds until the wipe passes.
            return 1.0 - EASINGS["ease_in_out_cubic"](p)
        return 1.0 - p

    def overlap_report(self, placed: list[PlacedScene]) -> dict[str, Any]:
        overlaps = [p for p in placed if p.transition_in_duration > 0]
        return {
            "scenes": len(placed),
            "with_overlap": len(overlaps),
            "total_overlap_s": round(sum(p.transition_in_duration for p in overlaps), 3),
            "total_duration_s": self.total_duration(placed),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Captions
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CaptionCue:
    """One rendered caption line."""

    index: int
    start: float
    end: float
    text: str
    words: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 6)

    @property
    def characters_per_second(self) -> float:
        return round(safe_div(len(self.text), self.duration), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "cps": self.characters_per_second,
        }

    def to_srt(self) -> str:
        def stamp(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int(round((seconds - math.floor(seconds)) * 1000))
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        return f"{self.index + 1}\n{stamp(self.start)} --> {stamp(self.end)}\n{self.text}\n"


class CaptionAligner:
    """Word-level caption timing with drift correction and readability limits.

    HyperFrames' ``align-captions`` script snaps generated captions to detected
    speech; this is the deterministic core: distribute word durations over an
    available window, wrap to a character budget, and correct drift so the last
    cue ends exactly on the target.
    """

    def __init__(self, max_chars: int = 32, max_cps: float = 20.0, min_duration: float = 0.6, max_lines: int = 2):
        self.max_chars = max_chars
        self.max_cps = max_cps
        self.min_duration = min_duration
        self.max_lines = max_lines

    def wrap(self, words: list[str]) -> list[list[str]]:
        lines: list[list[str]] = []
        current: list[str] = []
        current_len = 0
        for word in words:
            addition = len(word) + (1 if current else 0)
            if current and current_len + addition > self.max_chars:
                lines.append(current)
                current, current_len = [word], len(word)
            else:
                current.append(word)
                current_len += addition
        if current:
            lines.append(current)
        return lines

    def group_words(self, words: list[str]) -> list[list[str]]:
        """Greedy grouping: fill a cue until chars or the line cap is hit."""
        groups: list[list[str]] = []
        current: list[str] = []
        for word in words:
            candidate = current + [word]
            if current and (len(" ".join(candidate)) > self.max_chars * self.max_lines):
                groups.append(current)
                current = [word]
            else:
                current = candidate
        if current:
            groups.append(current)
        return groups

    def align(
        self,
        words: list[str],
        start: float = 0.0,
        end: float | None = None,
        word_weights: list[float] | None = None,
    ) -> list[CaptionCue]:
        if not words:
            return []
        weights = word_weights or [max(1.0, len(w) / 4.0) for w in words]
        if len(weights) != len(words):
            weights = [max(1.0, len(w) / 4.0) for w in words]
        total_weight = sum(weights) or float(len(words))
        duration = end - start if end is not None and end > start else max(
            len(words) / 2.6, self.min_duration * math.ceil(len(words) / 4)
        )
        end = start + duration

        groups = self.group_words(words)
        cues: list[CaptionCue] = []
        cursor_weight = 0.0
        cursor = 0
        for index, group in enumerate(groups):
            group_weight = sum(weights[cursor : cursor + len(group)])
            cursor += len(group)
            group_start = start + duration * safe_div(cursor_weight, total_weight)
            group_end = start + duration * safe_div(cursor_weight + group_weight, total_weight)
            cursor_weight += group_weight
            if group_end - group_start < self.min_duration:
                group_end = group_start + self.min_duration
            cues.append(
                CaptionCue(
                    index=index,
                    start=round(group_start, 4),
                    end=round(min(group_end, end), 4),
                    text=" ".join(group),
                    words=group,
                )
            )
        return self.correct_drift(cues, end)

    def correct_drift(self, cues: list[CaptionCue], target_end: float) -> list[CaptionCue]:
        """Stretch/compress cue boundaries so the last cue ends at ``target_end``."""
        if not cues:
            return cues
        current_end = cues[-1].end
        if abs(current_end - target_end) < 1e-6:
            return cues
        span_start = cues[0].start
        span = current_end - span_start
        if span <= 0:
            cues[-1].end = round(target_end, 4)
            return cues
        scale = safe_div(target_end - span_start, span, 1.0)
        for cue in cues:
            cue.start = round(span_start + (cue.start - span_start) * scale, 4)
            cue.end = round(span_start + (cue.end - span_start) * scale, 4)
        cues[-1].end = round(target_end, 4)
        return cues

    def readability_report(self, cues: list[CaptionCue]) -> dict[str, Any]:
        if not cues:
            return {"cues": 0}
        cps_values = [c.characters_per_second for c in cues]
        too_fast = [c.index for c in cues if c.characters_per_second > self.max_cps]
        return {
            "cues": len(cues),
            "mean_cps": round(statistics_mean(cps_values), 2),
            "max_cps": round(max(cps_values), 2),
            "too_fast": too_fast,
            "min_duration": round(min(c.duration for c in cues), 3),
            "total_covered_s": round(sum(c.duration for c in cues), 3),
        }

    def to_srt(self, cues: list[CaptionCue]) -> str:
        return "\n".join(cue.to_srt() for cue in cues)


def statistics_mean(values: list[float]) -> float:
    return safe_div(sum(values), len(values))


# ─────────────────────────────────────────────────────────────────────────────
# Render manifest + ffmpeg
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RenderManifest:
    """Content-addressed description of a render (determinism contract)."""

    composition_id: str
    fps: float
    width: int
    height: int
    duration_s: float
    scenes: list[dict[str, Any]]
    cues: list[dict[str, Any]]
    assets: list[str]
    seed: str = "hyperframes"

    @property
    def total_frames(self) -> int:
        return int(round(self.duration_s * self.fps))

    @property
    def digest(self) -> str:
        payload = {
            "composition_id": self.composition_id,
            "fps": self.fps,
            "size": [self.width, self.height],
            "duration": round(self.duration_s, 6),
            "scenes": self.scenes,
            "cues": self.cues,
            "assets": sorted(self.assets),
            "seed": self.seed,
        }
        return hashlib.sha256(repr(sorted(payload.items(), key=lambda kv: kv[0])).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition_id": self.composition_id,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "duration_s": round(self.duration_s, 3),
            "total_frames": self.total_frames,
            "scenes": self.scenes,
            "cue_count": len(self.cues),
            "assets": sorted(self.assets),
            "seed": self.seed,
            "digest": self.digest[:16],
        }


class FfmpegCommandBuilder:
    """Builds a deterministic ffmpeg argv for a HyperFrames composition."""

    def __init__(self, codec: str = "libx264", pix_fmt: str = "yuv420p", crf: int = 18, preset: str = "medium"):
        self.codec = codec
        self.pix_fmt = pix_fmt
        self.crf = crf
        self.preset = preset

    def frames_input(self, frame_pattern: str, fps: float) -> list[str]:
        return ["-framerate", f"{fps:g}", "-i", frame_pattern]

    def encode_args(self, width: int, height: int) -> list[str]:
        return [
            "-c:v", self.codec,
            "-preset", self.preset,
            "-crf", str(self.crf),
            "-pix_fmt", self.pix_fmt,
            "-s", f"{width}x{height}",
        ]

    def build(self, manifest: RenderManifest, frames_dir: str = "frames", output: str = "out.mp4") -> list[str]:
        argv = ["ffmpeg", "-y"]
        argv += self.frames_input(f"{frames_dir}/frame_%06d.png", manifest.fps)
        if manifest.cues:
            argv += ["-i", "captions.srt"]
            argv += ["-c:s", "mov_text"]
        argv += self.encode_args(manifest.width, manifest.height)
        argv += ["-frames:v", str(manifest.total_frames), output]
        return argv

    def concat_demuxer(self, clips: list[str], output: str = "concat.mp4") -> tuple[str, list[str]]:
        listing = "\n".join(f"file '{clip}'" for clip in clips)
        return listing, ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", output]


class HyperframesComposer:
    """End-to-end: HTML scenes -> timeline -> captions -> deterministic manifest."""

    def __init__(
        self,
        fps: float = 30.0,
        width: int = 1080,
        height: int = 1920,
        seed: str = "hyperframes",
        scheduler: TransitionScheduler | None = None,
        captioner: CaptionAligner | None = None,
    ):
        self.fps = fps
        self.width = width
        self.height = height
        self.seed = seed
        self.scheduler = scheduler or TransitionScheduler()
        self.captioner = captioner or CaptionAligner()
        self.scenes: list[SceneSpec] = []

    def add_scene(self, scene: SceneSpec) -> SceneSpec:
        self.scenes.append(scene)
        return scene

    def timeline(self) -> list[PlacedScene]:
        return self.scheduler.layout(self.scenes)

    def validate(self) -> list[str]:
        return self.scheduler.validate(self.scenes)

    def captions(self, scene: SceneSpec, placed: PlacedScene) -> list[CaptionCue]:
        graph = HtmlSceneGraph(scene.html)
        words = graph.text_content().split()
        if not words:
            return []
        # Captions start after the incoming transition clears.
        start = placed.start + placed.transition_in_duration
        return self.captioner.align(words, start=start, end=placed.end)

    def build(self, composition_id: str = "composition") -> RenderManifest:
        problems = self.validate()
        if problems:
            raise ValueError("; ".join(problems))
        placed = self.timeline()
        duration = self.scheduler.total_duration(placed)
        assets: list[str] = []
        cues: list[dict[str, Any]] = []
        scene_rows: list[dict[str, Any]] = []
        for item in placed:
            graph = item.scene.scene_graph
            assets.extend(graph.media_sources())
            scene_cues = self.captions(item.scene, item)
            cues.extend(cue.to_dict() for cue in scene_cues)
            scene_rows.append({**item.to_dict(), "graph": graph.summary(), "cues": len(scene_cues)})
        return RenderManifest(
            composition_id=composition_id,
            fps=self.fps,
            width=self.width,
            height=self.height,
            duration_s=duration,
            scenes=scene_rows,
            cues=cues,
            assets=sorted(set(assets)),
            seed=self.seed,
        )

    def frame_plan(self, manifest: RenderManifest | None = None) -> list[dict[str, Any]]:
        """Per-frame decisions: which scene is on screen and its transition weight."""
        manifest = manifest or self.build()
        placed = self.timeline()
        clock = FrameClock(fps=self.fps, duration_s=manifest.duration_s)
        plan: list[dict[str, Any]] = []
        for index in range(clock.total_frames):
            time_s = clock.time_at(index)
            current, position = None, 0
            for item in placed:
                if item.start <= time_s < item.end:
                    current, position = item, placed.index(item)
                    break
            if current is None and placed:
                current, position = placed[-1], len(placed) - 1
            weight = 1.0
            if current is not None and current.transition_in_duration > 0:
                progress = safe_div(time_s - current.start, current.transition_in_duration)
                if 0.0 <= progress <= 1.0:
                    weight = self.scheduler.transition_curve(current.scene.transition_in, progress)
            plan.append(
                {
                    "frame": index,
                    "time": round(time_s, 4),
                    "scene_id": current.scene.scene_id if current else "",
                    "scene_index": position,
                    "opacity": round(weight, 4),
                }
            )
        return plan
