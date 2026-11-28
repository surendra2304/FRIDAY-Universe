"""FotoForensics ELA image check for the IntelX OSINT source kit (TASK-INT-052).

Source: intelx package X-09, item DaXwbFrDEuX — the FotoForensics
image-forensics reference inside the awareness-only OSINT set. The set's
one defensive, adoptable item is error-level analysis (ELA): checking
whether regions of a JPEG carry a different compression history from the
rest of the image, which is what a spliced-in or retouched region
typically shows. The rest of X-09 (dark-web OSINT carousels and
attack-technique items) is NOT adopted — offensive capability, recorded
in the re-audit report. This module is defensive only: it analyses an
image the caller already holds and wants to trust or question.

How ELA works: the image is re-saved as JPEG at a known quality and the
per-block mean absolute error between the original and the re-save is
measured. Blocks whose error is a strong outlier against the image's
own distribution are flagged as "hot" — their compression history
differs from the surrounding material.

What ELA can and cannot prove is recorded in READING_GUIDE and carried
in every result: ELA is a heuristic signal, never proof of editing, and
a consistent verdict is never proof of authenticity.

Pillow is the fleet's image library; it is imported lazily. Without it
the check returns verdict="unavailable" with checked=False — an
unavailable check is never reported as a clean image.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from pathlib import Path

CHECK_NAME = "fotoforensics_ela"

RECOMPRESS_QUALITY = 90
BLOCK_SIZE = 16  # analysis block size in pixels (2x2 JPEG blocks)
MIN_DIMENSION = 64  # below this, block statistics are meaningless
HOT_SIGMA = 3.0  # a block is hot if error > mean + HOT_SIGMA * std ...
HOT_RATIO = 2.0  # ... and at least HOT_RATIO x the mean error
MAX_HOT_FRACTION = 0.40  # hotter than this = whole-image effect, not a local edit
MIN_TEXTURE_STD = 2.0  # greyscale std below this = flat/synthetic image

LIMITS_NOTE = (
    "ELA is a heuristic signal, not proof of editing: platform re-saves "
    "can wash out or imitate ELA differences, and a consistent verdict "
    "means only that no region stood out, not that the image is authentic."
)

READING_GUIDE: dict = {
    "check": CHECK_NAME,
    "what_ela_measures": (
        "The image is re-saved as JPEG at a known quality (90) and the "
        "per-block mean absolute error between the original and the "
        "re-save is measured. Regions that were previously compressed "
        "at a different effective quality — a pasted-in patch, a "
        "retouched area, material that was never JPEG-compressed — "
        "respond differently from regions with the image's own "
        "compression history, and stand out as high-error ('hot') blocks."
    ),
    "can_show": [
        "That specific blocks re-compress very differently from the rest "
        "of the image — consistent with a spliced or retouched region; "
        "treat the flagged area as unverified.",
        "That no block stood out at the tested re-save quality — the "
        "image's compression history looks uniform at this sensitivity.",
        "That the whole image is heterogeneous (mixed sources or "
        "repeated re-saves) rather than carrying one localised edit.",
    ],
    "cannot_prove": [
        "That an image was edited. ELA is a signal, not proof: sharp "
        "edges, text, and high-frequency detail naturally carry higher "
        "error, and social-platform re-saves can imitate or erase "
        "ELA differences.",
        "That an image is authentic. A consistent verdict means only "
        "that no region stood out; a careful edit re-saved uniformly "
        "can leave no ELA trace.",
        "Anything about non-JPEG images. PNG/screenshot input carries "
        "no JPEG error level to compare and returns inconclusive, as "
        "do flat/synthetic images and images under 64px.",
    ],
    "how_to_read": [
        "Read hot_blocks as coordinates (x, y of the 16px block's "
        "top-left corner) plus the block's mean error; compare against "
        "mean_error for the whole image.",
        "A small cluster of adjacent hot blocks is the pattern a "
        "localised edit produces; isolated single hot blocks on edges "
        "or text are common in unedited images.",
        "Corroborate before acting: ELA alone never justifies calling "
        "an image fake — pair it with source, metadata, and "
        "reverse-image evidence.",
    ],
    "verdict_meanings": {
        "consistent": "no block's error level stood out from the image's own distribution",
        "suspicious_regions": "localised blocks re-compress very differently from the rest",
        "whole_image_heterogeneous": (
            "most blocks are outliers — a whole-image effect, not one localised edit"
        ),
        "inconclusive": "ELA is not defined for this input (non-JPEG, flat, or too small)",
        "unavailable": "the check could not run (Pillow missing); nothing was verified",
    },
}


@dataclass(frozen=True)
class ImageElaResult:
    verdict: str  # consistent | suspicious_regions | whole_image_heterogeneous
    #               | inconclusive | unavailable
    checked: bool  # False only when the check could not run at all
    reason: str
    image_format: str = ""
    width: int = 0
    height: int = 0
    mean_error: float = 0.0
    max_block_error: float = 0.0
    hot_blocks: tuple[dict, ...] = field(default_factory=tuple)
    hot_fraction: float = 0.0
    blocks_total: int = 0
    recompress_quality: int = RECOMPRESS_QUALITY

    def to_dict(self) -> dict:
        return {
            "check": CHECK_NAME,
            "verdict": self.verdict,
            "checked": self.checked,
            "reason": self.reason,
            "format": self.image_format,
            "width": self.width,
            "height": self.height,
            "mean_error": round(self.mean_error, 4),
            "max_block_error": round(self.max_block_error, 4),
            "hot_blocks": [dict(b) for b in self.hot_blocks],
            "hot_fraction": round(self.hot_fraction, 4),
            "blocks_total": self.blocks_total,
            "recompress_quality": self.recompress_quality,
            "limits": LIMITS_NOTE,
            "reading_guide": READING_GUIDE,
        }


def ela_reading_guide() -> dict:
    """The recorded reading guide: what ELA can and cannot prove."""
    return READING_GUIDE


def _load_pillow():
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return None, None
    return Image, ImageChops


def check_image_ela(data: bytes, *, quality: int = RECOMPRESS_QUALITY) -> ImageElaResult:
    """Run the FotoForensics ELA check over raw image bytes.

    Raises ValueError for empty or undecodable input. Returns
    verdict="unavailable" (checked=False) when Pillow is not installed,
    and verdict="inconclusive" when ELA is not defined for the input.
    """
    if not data:
        raise ValueError("image data must be non-empty")
    image_module, chops_module = _load_pillow()
    if image_module is None:
        return ImageElaResult(
            verdict="unavailable",
            checked=False,
            reason=(
                "Pillow is not installed on this host; the ELA check was "
                "NOT performed and the image must not be read as verified"
            ),
            recompress_quality=quality,
        )
    try:
        original = image_module.open(io.BytesIO(data))
        original.load()
    except Exception as exc:
        raise ValueError(f"undecodable image bytes: {exc}") from exc

    image_format = (original.format or "").upper()
    width, height = original.size
    if image_format != "JPEG":
        return ImageElaResult(
            verdict="inconclusive",
            checked=True,
            reason=(
                f"ELA is defined for JPEG input; got {image_format or 'unknown'} "
                "(screenshots/PNGs carry no JPEG error level to compare)"
            ),
            image_format=image_format,
            width=width,
            height=height,
            recompress_quality=quality,
        )
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        return ImageElaResult(
            verdict="inconclusive",
            checked=True,
            reason=(
                f"image is {width}x{height}; below the {MIN_DIMENSION}px "
                "minimum for meaningful block statistics"
            ),
            image_format=image_format,
            width=width,
            height=height,
            recompress_quality=quality,
        )

    rgb = original.convert("RGB")
    grey_pixels = list(rgb.convert("L").getdata())
    mean_px = sum(grey_pixels) / len(grey_pixels)
    var_px = sum((p - mean_px) ** 2 for p in grey_pixels) / len(grey_pixels)
    if math.sqrt(var_px) < MIN_TEXTURE_STD:
        return ImageElaResult(
            verdict="inconclusive",
            checked=True,
            reason=(
                "image is effectively flat (near-zero texture); "
                "ELA has no error-level variation to measure"
            ),
            image_format=image_format,
            width=width,
            height=height,
            recompress_quality=quality,
        )

    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = image_module.open(buffer)
    resaved.load()
    diff = chops_module.difference(rgb, resaved.convert("RGB")).convert("L")

    block_errors: list[tuple[int, int, float]] = []
    for by in range(height // BLOCK_SIZE):
        for bx in range(width // BLOCK_SIZE):
            tile = diff.crop(
                (
                    bx * BLOCK_SIZE,
                    by * BLOCK_SIZE,
                    (bx + 1) * BLOCK_SIZE,
                    (by + 1) * BLOCK_SIZE,
                )
            )
            tile_pixels = list(tile.getdata())
            block_errors.append(
                (bx * BLOCK_SIZE, by * BLOCK_SIZE, sum(tile_pixels) / len(tile_pixels))
            )
    if not block_errors:
        return ImageElaResult(
            verdict="inconclusive",
            checked=True,
            reason="no complete analysis blocks",
            image_format=image_format,
            width=width,
            height=height,
            recompress_quality=quality,
        )

    errors = [e for _, _, e in block_errors]
    mean_err = sum(errors) / len(errors)
    var_err = sum((e - mean_err) ** 2 for e in errors) / len(errors)
    std_err = math.sqrt(var_err)
    threshold = max(mean_err + HOT_SIGMA * std_err, mean_err * HOT_RATIO)
    hot = tuple(
        {"x": x, "y": y, "error": round(e, 3)}
        for x, y, e in block_errors
        if e > threshold and e > mean_err
    )
    hot_fraction = len(hot) / len(block_errors)
    measured = {
        "image_format": image_format,
        "width": width,
        "height": height,
        "mean_error": mean_err,
        "max_block_error": max(errors),
        "hot_blocks": hot,
        "hot_fraction": hot_fraction,
        "blocks_total": len(block_errors),
        "recompress_quality": quality,
    }
    if not hot:
        return ImageElaResult(
            verdict="consistent",
            checked=True,
            reason=(
                "no block's error level stood out from the image's own "
                f"distribution at re-save quality {quality}"
            ),
            **measured,
        )
    if hot_fraction > MAX_HOT_FRACTION:
        return ImageElaResult(
            verdict="whole_image_heterogeneous",
            checked=True,
            reason=(
                f"{hot_fraction:.0%} of blocks are error outliers — a "
                "whole-image effect (mixed sources or repeated re-saves), "
                "not a single localised edit"
            ),
            **measured,
        )
    return ImageElaResult(
        verdict="suspicious_regions",
        checked=True,
        reason=(
            f"{len(hot)} localised block(s) re-compress very differently "
            "from the rest of the image — consistent with a spliced or "
            "retouched region; treat the flagged area as unverified"
        ),
        **measured,
    )


def check_image_file_ela(path: str | Path, *, quality: int = RECOMPRESS_QUALITY) -> ImageElaResult:
    """Run the ELA check over an image file the caller already holds."""
    return check_image_ela(Path(path).read_bytes(), quality=quality)


__all__ = [
    "CHECK_NAME",
    "LIMITS_NOTE",
    "READING_GUIDE",
    "ImageElaResult",
    "check_image_ela",
    "check_image_file_ela",
    "ela_reading_guide",
]
