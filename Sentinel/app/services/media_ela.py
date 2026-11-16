"""
Sentinel/app/services/media_ela.py — Error Level Analysis (ELA) check for
edited-photo detection in Sentinel's media-verification toolkit.

TASK-IG2-SEN-04 (IG wave 2, cluster #74; source shortcode DaXwbFrDEuX —
a FotoForensics-style ELA demonstration). DEFENSIVE ONLY: this verifies
media the owner receives or is asked to trust (a "proof" screenshot, a
photo attached to a claim); it analyses a caller-supplied image and
nothing else — no scraping, no third-party targets.

How ELA works
-------------
A JPEG is divided into 8x8 blocks compressed at a known quality. If an
image is re-saved at a known quality, regions that were previously
compressed at a *different* effective quality respond differently:
a spliced-in region (pasted from another source, or never JPEG
compressed) shows a markedly different error level from the surrounding
material. This module re-saves the image at a fixed quality, measures
the per-block mean absolute error, and flags blocks whose error is a
strong outlier against the image's own distribution.

Honest limits (stated in every result)
--------------------------------------
- ELA is a *signal*, never proof of editing. Social platforms re-save
  images, which can wash out or imitate ELA differences.
- It is only defined for JPEG input. PNG/screenshot input returns
  INCONCLUSIVE, as do flat/synthetic images (near-zero texture gives
  ELA nothing to measure) and very small images.
- A CONSISTENT verdict means "no block stood out", not "authentic".

Dependencies: Pillow (already the fleet's image library) is imported
lazily; without it the module still imports and raises
``ElaUnavailableError`` when an analysis is attempted, so Sentinel
starts cleanly on a host where Pillow is absent.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any

RECOMPRESS_QUALITY = 90
BLOCK = 16                # analysis block size in pixels (2x2 JPEG blocks)
MIN_DIMENSION = 64        # below this, block statistics are meaningless
HOT_SIGMA = 3.0           # a block is hot if error > mean + HOT_SIGMA*std
HOT_RATIO = 2.0           # ...and at least HOT_RATIO x the mean error
MAX_HOT_FRACTION_SUSPICIOUS = 0.40  # hotter than this = whole-image effect
MIN_TEXTURE_STD = 2.0     # greyscale std below this = flat/synthetic image

LIMITS_NOTE = (
    "ELA is a heuristic signal, not proof of editing: platform re-saves "
    "can wash out or imitate ELA differences, and a CONSISTENT verdict "
    "means only that no region stood out, not that the image is authentic."
)


class ElaUnavailableError(RuntimeError):
    """Pillow is not installed on this host."""


class ElaInputError(ValueError):
    """The supplied bytes could not be decoded as an image."""


@dataclass
class ElaResult:
    verdict: str  # CONSISTENT | SUSPICIOUS_REGIONS | WHOLE_IMAGE_HETEROGENEOUS | INCONCLUSIVE
    reason: str
    format: str | None = None
    width: int = 0
    height: int = 0
    mean_error: float = 0.0
    max_block_error: float = 0.0
    hot_blocks: list[dict[str, int]] = field(default_factory=list)
    hot_fraction: float = 0.0
    blocks_total: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "mean_error": round(self.mean_error, 4),
            "max_block_error": round(self.max_block_error, 4),
            "hot_blocks": self.hot_blocks,
            "hot_fraction": round(self.hot_fraction, 4),
            "blocks_total": self.blocks_total,
            "limits": LIMITS_NOTE,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Sentinel ELA media check",
            f"Verdict: **{self.verdict}** — {self.reason}",
        ]
        if self.width:
            lines.append(
                f"Image: {self.format} {self.width}x{self.height}; "
                f"mean error {self.mean_error:.2f}, hottest block "
                f"{self.max_block_error:.2f}, hot blocks "
                f"{len(self.hot_blocks)}/{self.blocks_total} "
                f"({self.hot_fraction:.1%})."
            )
        for block in self.hot_blocks[:20]:
            lines.append(
                f"- hot block at x={block['x']}, y={block['y']} "
                f"(error {block['error']:.2f})"
            )
        lines.append(f"_{LIMITS_NOTE}_")
        return "\n".join(lines)


def _load_pillow():
    try:
        from PIL import Image, ImageChops  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on host
        raise ElaUnavailableError(
            "Pillow is not installed; ELA analysis is unavailable on this host"
        ) from exc
    return Image, ImageChops


def analyse_image_bytes(data: bytes, quality: int = RECOMPRESS_QUALITY) -> ElaResult:
    """Run ELA over raw image bytes and return the verdict."""
    Image, ImageChops = _load_pillow()
    try:
        original = Image.open(io.BytesIO(data))
        original.load()
    except Exception as exc:
        raise ElaInputError(f"undecodable image bytes: {exc}") from exc

    fmt = (original.format or "").upper()
    width, height = original.size
    if fmt != "JPEG":
        return ElaResult(
            verdict="INCONCLUSIVE",
            reason=f"ELA is defined for JPEG input; got {fmt or 'unknown'} "
                   "(screenshots/PNGs carry no JPEG error level to compare)",
            format=fmt or None, width=width, height=height,
        )
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        return ElaResult(
            verdict="INCONCLUSIVE",
            reason=f"image is {width}x{height}; below the {MIN_DIMENSION}px "
                   "minimum for meaningful block statistics",
            format=fmt, width=width, height=height,
        )

    rgb = original.convert("RGB")
    # Flat/synthetic images (solid fills, generated graphics) give ELA
    # nothing to measure — say so instead of emitting a false verdict.
    grey = rgb.convert("L")
    pixels = list(grey.getdata())
    mean_px = sum(pixels) / len(pixels)
    var_px = sum((p - mean_px) ** 2 for p in pixels) / len(pixels)
    if math.sqrt(var_px) < MIN_TEXTURE_STD:
        return ElaResult(
            verdict="INCONCLUSIVE",
            reason="image is effectively flat (near-zero texture); "
                   "ELA has no error-level variation to measure",
            format=fmt, width=width, height=height,
        )

    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)
    resaved.load()
    diff = ImageChops.difference(rgb, resaved.convert("RGB")).convert("L")

    cols = width // BLOCK
    rows = height // BLOCK
    block_errors: list[tuple[int, int, float]] = []
    for by in range(rows):
        for bx in range(cols):
            tile = diff.crop((bx * BLOCK, by * BLOCK,
                              (bx + 1) * BLOCK, (by + 1) * BLOCK))
            tile_pixels = list(tile.getdata())
            block_errors.append(
                (bx * BLOCK, by * BLOCK, sum(tile_pixels) / len(tile_pixels))
            )
    if not block_errors:
        return ElaResult(
            verdict="INCONCLUSIVE", reason="no complete analysis blocks",
            format=fmt, width=width, height=height,
        )

    errors = [e for _, _, e in block_errors]
    mean_err = sum(errors) / len(errors)
    var_err = sum((e - mean_err) ** 2 for e in errors) / len(errors)
    std_err = math.sqrt(var_err)
    threshold = max(mean_err + HOT_SIGMA * std_err, mean_err * HOT_RATIO)
    hot = [
        {"x": x, "y": y, "error": round(e, 3)}
        for x, y, e in block_errors if e > threshold and e > mean_err
    ]
    hot_fraction = len(hot) / len(block_errors)
    base = dict(
        format=fmt, width=width, height=height, mean_error=mean_err,
        max_block_error=max(errors), hot_blocks=hot,
        hot_fraction=hot_fraction, blocks_total=len(block_errors),
    )
    if not hot:
        return ElaResult(
            verdict="CONSISTENT",
            reason="no block's error level stood out from the image's own "
                   "distribution at re-save quality "
                   f"{quality}",
            **base,
        )
    if hot_fraction > MAX_HOT_FRACTION_SUSPICIOUS:
        return ElaResult(
            verdict="WHOLE_IMAGE_HETEROGENEOUS",
            reason=f"{hot_fraction:.0%} of blocks are error outliers — a "
                   "whole-image effect (mixed sources or repeated re-saves), "
                   "not a single localised edit",
            **base,
        )
    return ElaResult(
        verdict="SUSPICIOUS_REGIONS",
        reason=f"{len(hot)} localised block(s) re-compress very differently "
               "from the rest of the image — consistent with a spliced or "
               "retouched region; treat the flagged area as unverified",
        **base,
    )


def analyse_image(path: str, quality: int = RECOMPRESS_QUALITY) -> ElaResult:
    """Run ELA over an image file on the caller's own device/fleet host."""
    with open(path, "rb") as handle:
        return analyse_image_bytes(handle.read(), quality=quality)
