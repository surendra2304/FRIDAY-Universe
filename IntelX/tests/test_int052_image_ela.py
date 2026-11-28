"""Tests for TASK-INT-052 — FotoForensics ELA check in the OSINT source kit.

Hermetic: images are built in-memory with Pillow. A textured base saved
once as JPEG (uniform compression history) vs the same base with a
never-JPEG-compressed patch spliced in (a different compression history
in one localised region — exactly what ELA exists to surface). The
file-based test checks one real JPEG file through the kit and records
its verdict, which is the task's done criterion.
"""

from __future__ import annotations

import io
import random

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from intelx.osint.image_ela import (  # noqa: E402
    CHECK_NAME,
    check_image_ela,
    check_image_file_ela,
    ela_reading_guide,
)


def textured_image(size: int = 256, seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            base = (x * 255) // size
            noise = rng.randint(-30, 30)
            px[x, y] = (
                max(0, min(255, base + noise)),
                max(0, min(255, 200 - base + noise)),
                max(0, min(255, 128 + noise)),
            )
    return img


def jpeg_bytes(img: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def spliced_image() -> Image.Image:
    base = textured_image()
    patch = Image.new("RGB", (64, 64))
    pp = patch.load()
    for y in range(64):
        for x in range(64):
            v = 255 if (x // 4 + y // 4) % 2 else 0
            pp[x, y] = (v, 255 - v, v)
    base.paste(patch, (96, 96))
    return base


def test_uniform_history_jpeg_is_consistent() -> None:
    result = check_image_ela(jpeg_bytes(textured_image()))
    assert result.verdict == "consistent", result.to_dict()
    assert result.checked
    assert result.hot_blocks == ()
    assert result.blocks_total > 0


def test_spliced_patch_is_flagged_in_its_region() -> None:
    result = check_image_ela(jpeg_bytes(spliced_image()))
    assert result.verdict == "suspicious_regions", result.to_dict()
    assert result.hot_blocks, result.to_dict()
    assert any(
        80 <= b["x"] < 176 and 80 <= b["y"] < 176 for b in result.hot_blocks
    ), result.to_dict()


def test_real_jpeg_file_checked_through_kit_with_verdict_recorded(tmp_path) -> None:
    path = tmp_path / "checked_image.jpg"
    path.write_bytes(jpeg_bytes(spliced_image()))
    result = check_image_file_ela(path)
    payload = result.to_dict()
    assert payload["check"] == CHECK_NAME == "fotoforensics_ela"
    assert payload["verdict"] == "suspicious_regions"
    assert payload["checked"] is True
    assert payload["format"] == "JPEG"
    assert payload["width"] == 256 and payload["height"] == 256
    assert payload["hot_blocks"]


def test_png_input_is_inconclusive_not_a_verdict() -> None:
    buf = io.BytesIO()
    textured_image().save(buf, "PNG")
    result = check_image_ela(buf.getvalue())
    assert result.verdict == "inconclusive"
    assert "JPEG" in result.reason


def test_flat_image_is_inconclusive() -> None:
    flat = Image.new("RGB", (256, 256), (120, 120, 120))
    result = check_image_ela(jpeg_bytes(flat))
    assert result.verdict == "inconclusive"


def test_small_image_is_inconclusive() -> None:
    result = check_image_ela(jpeg_bytes(textured_image(size=32)))
    assert result.verdict == "inconclusive"
    assert "64px" in result.reason


def test_undecodable_and_empty_input_raise() -> None:
    with pytest.raises(ValueError):
        check_image_ela(b"this is not an image at all")
    with pytest.raises(ValueError):
        check_image_ela(b"")


def test_result_carries_reading_guide_and_limits() -> None:
    payload = check_image_ela(jpeg_bytes(textured_image())).to_dict()
    assert "not proof" in payload["limits"]
    guide = payload["reading_guide"]
    assert guide["check"] == "fotoforensics_ela"
    assert guide["can_show"] and guide["cannot_prove"]
    assert any("authentic" in line for line in guide["cannot_prove"])
    assert ela_reading_guide() == guide
