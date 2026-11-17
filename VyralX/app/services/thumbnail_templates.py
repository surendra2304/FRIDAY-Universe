"""VyralX layered thumbnail-template lane (IG General wave, cluster B1-07).

The generated-thumbnail path (``thumbnail_designer.generate_genre_thumbnail``)
hard-codes one layout in code: keyframe, gradient, badge pill, headline.
This module adds the template lane the B1-07 giveaway pattern points at —
a layered template whose named slots a producer swaps in minutes:

* A **template** is a directory holding ``template.json`` (the slot map)
  plus the layer PNGs it names. The slot map declares the canvas, the
  static art layers, and the slots: ``background`` / ``subject`` image
  slots, a ``badge_text`` pill slot, and the ``title_text`` slot that
  carries the packaging stage's thumbnail text.
* The **registry** (``TemplateRegistry``) discovers and validates those
  directories under ``app/data/thumbnail_templates/`` (override with the
  ``VYRALX_THUMBNAIL_TEMPLATE_DIR`` env var or an explicit root).
* The **compositor** (``render``) fills the slots with Pillow only and
  exports a platform-sized thumbnail.

Format decision — layered PNG + JSON slot map, not PSD: a PSD reader
(psd-tools) is not in the fleet's dependency set, decodes every layer at
once (a multi-layer 1080x1920 PSD is a real risk against the 320 MB
render-memory cap on the ~956 MB hosts), and buys nothing here because
the seed templates are authored in-house. PNG layers decode one at a
time with the Pillow the fleet already runs (one 1080x1920 RGBA layer
is ~8 MB). The creator's giveaway PSD is *not* copied or redistributed;
only the layered-template pattern is adopted.

Gate parity — no bypass: before compositing, the ``title_text`` fill is
checked with the packaging system's own ``lint_thumbnail_text`` (the
same function ``packaging.prepublish_checklist`` gates on). Text the
checklist would reject is refused here too, with the lint's own issues.
Nothing in this module uploads, schedules, or talks to YouTube.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.services.packaging import lint_thumbnail_text

log = logging.getLogger("vyralx.thumbnail_templates")

_RESAMPLE = Image.Resampling.LANCZOS  # Pillow >= 9.1; fleet declares >= 13

#: Named export sizes. A render is composed at the template's canvas
#: size, then scaled to the requested export size if one is given.
PLATFORM_SIZES: dict[str, tuple[int, int]] = {
    "shorts": (1080, 1920),
    "youtube": (1280, 720),
    "square": (1080, 1080),
}

_SLOT_TYPES = ("image", "title_text", "badge_text")
_FITS = ("cover", "contain")
_ALIGNS = ("left", "center", "right")


class ThumbnailTemplateError(Exception):
    """Base class for template-lane failures."""


class TemplateNotFoundError(ThumbnailTemplateError):
    """The requested template id is not in the registry."""


class TemplateValidationError(ThumbnailTemplateError):
    """A template's slot map (template.json) is invalid."""


class MissingSlotError(ThumbnailTemplateError):
    """A required slot was given no fill; the render is refused."""


class UnknownSlotError(ThumbnailTemplateError):
    """A fill names a slot the template does not declare."""


class SlotFillError(ThumbnailTemplateError):
    """A slot fill could not be used (unreadable image, bad value)."""


class ThumbnailTextGateError(ThumbnailTemplateError):
    """The packaging thumbnail-text lint rejected the title_text fill.

    Carries the lint's own ``issues`` list — the same verdict the
    pre-publish checklist's ``packaging_thumbnail_text`` gate returns.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = list(issues)
        super().__init__("thumbnail text gate: " + "; ".join(self.issues))


@dataclass(frozen=True)
class SlotSpec:
    """One named slot from a template's slot map."""

    name: str
    type: str  # one of _SLOT_TYPES
    rect: tuple[int, int, int, int]  # x, y, width, height in canvas px
    required: bool = False
    z: int = 0
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LayerSpec:
    """One static art layer (a PNG in the template directory)."""

    file: str
    z: int = 0


@dataclass(frozen=True)
class ThumbnailTemplate:
    """A validated template: canvas, static layers, and slots."""

    id: str
    name: str
    description: str
    canvas: tuple[int, int]  # width, height
    layers: tuple[LayerSpec, ...]
    slots: dict[str, SlotSpec]
    root: Path


@dataclass
class RenderResult:
    """What a render produced. ``path`` mirrors the generated lane's
    contract (``create_viral_thumbnail`` returns the output path)."""

    path: str
    template_id: str
    size: tuple[int, int]
    lint: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    skipped_slots: list[str] = field(default_factory=list)
    filled_slots: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Slot-map parsing / validation
# ---------------------------------------------------------------------------


def _parse_color(value: Any, *, what: str) -> tuple[int, int, int, int]:
    """Accept '#RRGGBB', '#RRGGBBAA', [r, g, b] or [r, g, b, a]."""
    if isinstance(value, str) and value.startswith("#") and len(value) in (7, 9):
        try:
            parts = [int(value[i : i + 2], 16) for i in range(1, len(value), 2)]
        except ValueError:
            parts = []
        if len(parts) in (3, 4):
            if len(parts) == 3:
                parts.append(255)
            return tuple(parts)  # type: ignore[return-value]
    if isinstance(value, (list, tuple)) and len(value) in (3, 4):
        if all(isinstance(c, int) and 0 <= c <= 255 for c in value):
            parts = list(value) + [255] * (4 - len(value))
            return tuple(parts)  # type: ignore[return-value]
    raise TemplateValidationError(f"{what}: bad color {value!r}")


def _parse_rect(value: Any, *, what: str, canvas: tuple[int, int]) -> tuple[int, int, int, int]:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 4
        and all(isinstance(v, int) for v in value)
    ):
        x, y, w, h = (int(v) for v in value)
        if w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= canvas[0] and y + h <= canvas[1]:
            return (x, y, w, h)
    raise TemplateValidationError(f"{what}: rect {value!r} is not inside the canvas")


def _load_template(root: Path) -> ThumbnailTemplate:
    map_path = root / "template.json"
    if not map_path.is_file():
        raise TemplateValidationError(f"{root.name}: template.json is missing")
    try:
        raw = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateValidationError(f"{root.name}: template.json unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise TemplateValidationError(f"{root.name}: template.json must be a JSON object")
    template_id = raw.get("id")
    if template_id != root.name:
        raise TemplateValidationError(
            f"{root.name}: slot map id {template_id!r} does not match its directory name"
        )
    canvas_raw = raw.get("canvas") or {}
    width, height = canvas_raw.get("width"), canvas_raw.get("height")
    if not (isinstance(width, int) and isinstance(height, int) and 16 <= width <= 4096
            and 16 <= height <= 4096):
        raise TemplateValidationError(f"{root.name}: canvas must be 16..4096 px per side")
    canvas = (width, height)

    layers: list[LayerSpec] = []
    for i, entry in enumerate(raw.get("layers") or []):
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise TemplateValidationError(f"{root.name}: layers[{i}] needs a 'file' name")
        layer_file = root / entry["file"]
        if not layer_file.is_file():
            raise TemplateValidationError(f"{root.name}: layer file {entry['file']!r} is missing")
        try:
            with Image.open(layer_file) as probe:
                layer_size = probe.size
        except Exception as exc:
            raise TemplateValidationError(
                f"{root.name}: layer file {entry['file']!r} is not a readable image: {exc}"
            ) from exc
        if layer_size != canvas:
            raise TemplateValidationError(
                f"{root.name}: layer {entry['file']!r} is {layer_size}, canvas is {canvas}"
            )
        layers.append(LayerSpec(file=entry["file"], z=int(entry.get("z", 0))))

    slots: dict[str, SlotSpec] = {}
    raw_slots = raw.get("slots")
    if not isinstance(raw_slots, dict) or not raw_slots:
        raise TemplateValidationError(f"{root.name}: slot map declares no slots")
    for name, spec in raw_slots.items():
        if not isinstance(spec, dict):
            raise TemplateValidationError(f"{root.name}: slot {name!r} must be an object")
        slot_type = spec.get("type")
        if slot_type not in _SLOT_TYPES:
            raise TemplateValidationError(
                f"{root.name}: slot {name!r} has unknown type {slot_type!r}"
            )
        options = dict(spec.get("options") or {})
        if slot_type == "image" and options.get("fit", "cover") not in _FITS:
            raise TemplateValidationError(f"{root.name}: slot {name!r} has bad fit")
        if slot_type in ("title_text", "badge_text"):
            if options.get("align", "left") not in _ALIGNS:
                raise TemplateValidationError(f"{root.name}: slot {name!r} has bad align")
            for key in ("color", "stroke_color", "fill", "text_color", "outline"):
                if key in options:
                    _parse_color(options[key], what=f"{root.name} slot {name!r} {key}")
        slots[name] = SlotSpec(
            name=name,
            type=slot_type,
            rect=_parse_rect(spec.get("rect"), what=f"{root.name} slot {name!r}", canvas=canvas),
            required=bool(spec.get("required", False)),
            z=int(spec.get("z", 0)),
            options=options,
        )
    return ThumbnailTemplate(
        id=root.name,
        name=str(raw.get("name") or root.name),
        description=str(raw.get("description") or ""),
        canvas=canvas,
        layers=tuple(layers),
        slots=slots,
        root=root,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def default_template_root() -> Path:
    """Where seed templates live: ``app/data/thumbnail_templates``.

    The ``VYRALX_THUMBNAIL_TEMPLATE_DIR`` env var overrides it (tests,
    staging, a future operator-managed template library).
    """
    override = os.environ.get("VYRALX_THUMBNAIL_TEMPLATE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "thumbnail_templates"


class TemplateRegistry:
    """Discovers and validates the templates under one root directory."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_template_root()
        self._cache: dict[str, ThumbnailTemplate] = {}

    def template_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            child.name
            for child in self.root.iterdir()
            if child.is_dir() and (child / "template.json").is_file()
        )

    def get(self, template_id: str) -> ThumbnailTemplate:
        if template_id not in self._cache:
            if template_id not in self.template_ids():
                raise TemplateNotFoundError(
                    f"no thumbnail template {template_id!r} under {self.root}"
                )
            self._cache[template_id] = _load_template(self.root / template_id)
        return self._cache[template_id]

    def describe(self, template_id: str) -> dict[str, Any]:
        template = self.get(template_id)
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "canvas": {"width": template.canvas[0], "height": template.canvas[1]},
            "layers": [layer.file for layer in template.layers],
            "slots": {
                name: {
                    "type": slot.type,
                    "rect": list(slot.rect),
                    "required": slot.required,
                }
                for name, slot in sorted(template.slots.items())
            },
        }


# ---------------------------------------------------------------------------
# Fonts and text fitting
# ---------------------------------------------------------------------------

_FONT_DIRS = (
    Path("data/fonts"),
    Path("/opt/friday_universe/VyralX/data/fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/local/share/fonts"),
)
_FONT_PREFERENCE = (
    "Montserrat-Black.ttf",
    "Anton-Regular.ttf",
    "DejaVuSans-Bold.ttf",
)


def _load_font(size: int, font_name: str | None = None) -> ImageFont.ImageFont:
    """Load a heavy display font, mirroring thumbnail_designer's search.

    Falls back to Pillow's bundled default rather than failing the
    render; the caller records a warning when that happens.
    """
    candidates: list[Path] = []
    if font_name:
        candidates += [base / font_name for base in _FONT_DIRS]
    for preferred in _FONT_PREFERENCE:
        candidates += [base / preferred for base in _FONT_DIRS]
    for cand in candidates:
        if cand.is_file():
            try:
                return ImageFont.truetype(str(cand), size)
            except Exception:
                continue
    if font_name:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _font_is_fallback(font: ImageFont.ImageFont) -> bool:
    return not isinstance(font, ImageFont.FreeTypeFont)


def _wrap_by_width(
    draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.ImageFont, max_width: int
) -> list[str]:
    """Greedy word wrap measured in pixels (never by character count)."""
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_width: int,
    max_lines: int,
    size_start: int,
    size_min: int,
    font_name: str | None,
) -> tuple[ImageFont.ImageFont, list[str], bool]:
    """Fit ``text`` into a box: shrink the font, then wrap, then truncate.

    Returns (font, lines, truncated). Truncation happens only at the
    minimum size with more lines than the box allows; the final line is
    ellipsised to width and the caller records the truncation as a
    warning — output is never silently clipped mid-glyph.
    """
    words = text.split()
    size = size_start
    while size >= size_min:
        font = _load_font(size, font_name)
        lines = _wrap_by_width(draw, words, font, max_width)
        widest_word = max((draw.textlength(w, font=font) for w in words), default=0.0)
        if len(lines) <= max_lines and widest_word <= max_width:
            return font, lines, False
        size -= 4
    font = _load_font(size_min, font_name)
    lines = _wrap_by_width(draw, words, font, max_width)
    if len(lines) <= max_lines and all(
        draw.textlength(line, font=font) <= max_width for line in lines
    ):
        return font, lines, False
    kept = lines[:max_lines] or [""]
    last = kept[-1]
    while last and draw.textlength(last + "…", font=font) > max_width:
        last = last[:-1]
    kept[-1] = (last + "…") if last else "…"
    return font, kept, True


# ---------------------------------------------------------------------------
# Slot drawing
# ---------------------------------------------------------------------------


def _fit_image_into_rect(
    image: Image.Image, rect: tuple[int, int, int, int], fit: str
) -> Image.Image:
    """Return ``image`` resized/cropped to exactly the rect's size."""
    _, _, w, h = rect
    src = image.convert("RGBA")
    if fit == "contain":
        scale = min(w / src.width, h / src.height)
        resized = src.resize(
            (max(1, round(src.width * scale)), max(1, round(src.height * scale))),
            _RESAMPLE,
        )
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.alpha_composite(resized, ((w - resized.width) // 2, (h - resized.height) // 2))
        return out
    # cover: scale to fill, centre-crop the overflow
    scale = max(w / src.width, h / src.height)
    resized = src.resize(
        (max(w, round(src.width * scale)), max(h, round(src.height * scale))),
        _RESAMPLE,
    )
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _draw_image_slot(
    canvas_img: Image.Image, slot: SlotSpec, fill: Any
) -> None:
    if isinstance(fill, Image.Image):
        image = fill
    elif isinstance(fill, (str, Path)):
        path = Path(fill)
        if not path.is_file():
            raise SlotFillError(f"slot {slot.name!r}: image fill {path} does not exist")
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
        except Exception as exc:
            raise SlotFillError(f"slot {slot.name!r}: cannot read image {path}: {exc}") from exc
    else:
        raise SlotFillError(
            f"slot {slot.name!r}: image fill must be a path or PIL Image, got {type(fill)}"
        )
    fitted = _fit_image_into_rect(image, slot.rect, str(slot.options.get("fit", "cover")))
    canvas_img.alpha_composite(fitted, (slot.rect[0], slot.rect[1]))


def _draw_title_text(
    canvas_img: Image.Image,
    draw: ImageDraw.ImageDraw,
    slot: SlotSpec,
    text: str,
    result: RenderResult,
) -> None:
    opts = slot.options
    x, y, w, h = slot.rect
    display = text.upper() if opts.get("uppercase", True) else text
    font, lines, truncated = _fit_text(
        draw,
        display,
        max_width=w,
        max_lines=int(opts.get("max_lines", 3)),
        size_start=int(opts.get("size_start", 96)),
        size_min=int(opts.get("size_min", 40)),
        font_name=opts.get("font"),
    )
    if truncated:
        result.warnings.append(
            f"title_text truncated to fit slot {slot.name!r}: {text!r}"
        )
    if _font_is_fallback(font):
        result.warnings.append("no display font found; used Pillow's default font")
    fill = _parse_color(opts.get("color", "#FFFFFF"), what=f"slot {slot.name!r} color")
    stroke = _parse_color(
        opts.get("stroke_color", "#000000"), what=f"slot {slot.name!r} stroke_color"
    )
    size = getattr(font, "size", int(opts.get("size_min", 40)))
    stroke_width = max(2, round(size * float(opts.get("stroke_ratio", 0.11))))
    line_height = round(size * float(opts.get("line_spacing", 1.18)))
    align = str(opts.get("align", "left"))
    shadow = opts.get("shadow", True)
    ty = y
    for line in lines:
        line_w = draw.textlength(line, font=font)
        if align == "center":
            tx = x + (w - line_w) / 2
        elif align == "right":
            tx = x + (w - line_w)
        else:
            tx = float(x)
        if shadow:
            draw.text(
                (tx + 4, ty + 5), line, font=font, fill=(0, 0, 0, 160),
            )
        draw.text(
            (tx, ty),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke,
        )
        ty += line_height
        if ty > y + h:  # fitted lines are bounded; this is a belt-and-braces stop
            break


def _draw_badge_text(
    draw: ImageDraw.ImageDraw, slot: SlotSpec, text: str, result: RenderResult
) -> None:
    opts = slot.options
    x, y, w, h = slot.rect
    display = text.upper() if opts.get("uppercase", True) else text
    font = _load_font(int(opts.get("size", 40)), opts.get("font"))
    if _font_is_fallback(font):
        result.warnings.append("no display font found; used Pillow's default font")
    text_w = draw.textlength(display, font=font)
    bbox = draw.textbbox((0, 0), display, font=font)
    text_h = bbox[3] - bbox[1]
    pad_x = int(opts.get("pad_x", 22))
    pad_y = int(opts.get("pad_y", 10))
    pill_w = min(w, round(text_w) + 2 * pad_x)
    pill_h = min(h, round(text_h) + 2 * pad_y)
    align = str(opts.get("align", "left"))
    if align == "center":
        px = x + (w - pill_w) // 2
    elif align == "right":
        px = x + (w - pill_w)
    else:
        px = x
    fill = _parse_color(opts.get("fill", "#0A0A0A"), what=f"slot {slot.name!r} fill")
    outline = _parse_color(
        opts.get("outline", "#FFD700"), what=f"slot {slot.name!r} outline"
    )
    text_color = _parse_color(
        opts.get("text_color", "#FFD700"), what=f"slot {slot.name!r} text_color"
    )
    draw.rounded_rectangle(
        [px, y, px + pill_w, y + pill_h],
        radius=int(opts.get("radius", 14)),
        fill=fill,
        outline=outline,
        width=int(opts.get("outline_width", 3)),
    )
    draw.text(
        (px + (pill_w - text_w) / 2, y + (pill_h - text_h) / 2 - bbox[1]),
        display,
        font=font,
        fill=text_color,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _resolve_export_size(
    size: str | tuple[int, int] | None, canvas: tuple[int, int]
) -> tuple[int, int]:
    if size is None:
        return canvas
    if isinstance(size, str):
        if size not in PLATFORM_SIZES:
            raise ThumbnailTemplateError(
                f"unknown export size {size!r}; use one of {sorted(PLATFORM_SIZES)} "
                "or a (width, height) tuple"
            )
        return PLATFORM_SIZES[size]
    w, h = size
    if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
        raise ThumbnailTemplateError(f"bad export size {size!r}")
    return (w, h)


def render(
    template_id: str,
    fills: dict[str, Any],
    destination: str | Path,
    *,
    title: str = "",
    size: str | tuple[int, int] | None = None,
    registry: TemplateRegistry | None = None,
) -> RenderResult:
    """Composite one template into a finished thumbnail file.

    ``fills`` maps slot names to fills: image slots take a path or a PIL
    Image; text slots take strings. ``title`` is the packaging stage's
    chosen video title — it is not drawn; it is given to the thumbnail
    text lint, which rejects thumbnail text that merely repeats the
    title's opening words (the same rule the pre-publish checklist
    enforces). Returns a RenderResult; the file is written only on
    success — every failure is raised before any output exists.
    """
    registry = registry or TemplateRegistry()
    template = registry.get(template_id)
    fills = dict(fills or {})

    unknown = sorted(set(fills) - set(template.slots))
    if unknown:
        raise UnknownSlotError(
            f"template {template_id!r} has no slot(s): {', '.join(unknown)}"
        )
    missing = sorted(
        name
        for name, slot in template.slots.items()
        if slot.required and fills.get(name) in (None, "")
    )
    if missing:
        raise MissingSlotError(
            f"template {template_id!r} requires fill(s) for: {', '.join(missing)}"
        )

    result = RenderResult(
        path=str(destination), template_id=template_id, size=template.canvas
    )

    # --- Packaging gate parity: the title_text fill must pass the same
    # lint the pre-publish checklist's packaging_thumbnail_text gate
    # applies. A lint failure refuses the render; there is no bypass.
    title_slot = next(
        (s for s in template.slots.values() if s.type == "title_text"), None
    )
    if title_slot is not None and fills.get(title_slot.name) not in (None, ""):
        lint = lint_thumbnail_text(str(fills[title_slot.name]), title)
        result.lint = lint
        if not lint["ok"]:
            raise ThumbnailTextGateError(lint["issues"])

    canvas_img = Image.new("RGBA", template.canvas, (0, 0, 0, 255))
    draw = ImageDraw.Draw(canvas_img)

    drawables: list[tuple[int, str, Any]] = []
    for layer in template.layers:
        drawables.append((layer.z, "layer", layer))
    for name, slot in template.slots.items():
        if fills.get(name) in (None, ""):
            if not slot.required:
                result.skipped_slots.append(name)
            continue
        drawables.append((slot.z, "slot", slot))
    drawables.sort(key=lambda item: item[0])

    for _, kind, item in drawables:
        if kind == "layer":
            layer_path = template.root / item.file
            with Image.open(layer_path) as layer_img:
                canvas_img.alpha_composite(layer_img.convert("RGBA"), (0, 0))
            continue
        slot = item
        fill = fills[slot.name]
        if slot.type == "image":
            _draw_image_slot(canvas_img, slot, fill)
            draw = ImageDraw.Draw(canvas_img)
        elif slot.type == "title_text":
            _draw_title_text(canvas_img, draw, slot, str(fill), result)
        elif slot.type == "badge_text":
            _draw_badge_text(draw, slot, str(fill), result)
        result.filled_slots.append(slot.name)

    export_size = _resolve_export_size(size, template.canvas)
    out = canvas_img
    if export_size != template.canvas:
        canvas_aspect = template.canvas[0] / template.canvas[1]
        export_aspect = export_size[0] / export_size[1]
        if abs(canvas_aspect - export_aspect) > 0.01:
            result.warnings.append(
                f"export size {export_size} changes the aspect ratio of canvas "
                f"{template.canvas}; the composite is scaled, not re-laid-out — "
                "prefer a template whose canvas matches the target platform"
            )
        out = canvas_img.resize(export_size, _RESAMPLE)
    result.size = export_size

    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.suffix.lower() in (".jpg", ".jpeg"):
        out.convert("RGB").save(dest, quality=92)
    else:
        out.save(dest)
    result.path = str(dest)
    log.info(
        "Rendered template thumbnail %s (%s) -> %s",
        template_id, "x".join(map(str, export_size)), dest.name,
    )
    return result


def render_template_thumbnail(
    template_id: str,
    fills: dict[str, Any],
    destination: str | Path,
    *,
    title: str = "",
    size: str | tuple[int, int] | None = None,
    registry: TemplateRegistry | None = None,
) -> str:
    """Path-returning wrapper with the generated lane's contract
    (``create_viral_thumbnail`` returns the output path as a string)."""
    return render(
        template_id, fills, destination, title=title, size=size, registry=registry
    ).path


def list_templates(registry: TemplateRegistry | None = None) -> list[dict[str, Any]]:
    """Describe every registered template (id, canvas, slot summary)."""
    registry = registry or TemplateRegistry()
    return [registry.describe(tid) for tid in registry.template_ids()]
