"""Tests for TASK-IG2-SEN-04 media_ela (ELA edited-photo detection).

Synthetic images only, built in-memory with Pillow: a textured base
saved once as JPEG (uniform compression history) vs the same base with
a never-JPEG-compressed patch spliced in (a different compression
history in one localised region — exactly what ELA exists to surface).
"""
import io
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from app.services.media_ela import (  # noqa: E402
    ElaInputError, analyse_image_bytes,
)


def textured_image(size=256, seed=7):
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


def jpeg_bytes(img, quality=92):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def test_uniform_history_jpeg_is_consistent():
    result = analyse_image_bytes(jpeg_bytes(textured_image()))
    assert result.verdict == "CONSISTENT", result.as_dict()
    assert result.hot_blocks == []


def test_spliced_patch_is_flagged_in_its_region():
    base = textured_image()
    # A patch with NO JPEG history: sharp checkerboard, pasted in raw,
    # then the composite is saved once. Its blocks re-compress very
    # differently from the once-compressed surroundings.
    patch = Image.new("RGB", (64, 64))
    pp = patch.load()
    for y in range(64):
        for x in range(64):
            v = 255 if (x // 4 + y // 4) % 2 else 0
            pp[x, y] = (v, 255 - v, v)
    base.paste(patch, (96, 96))
    result = analyse_image_bytes(jpeg_bytes(base))
    assert result.verdict == "SUSPICIOUS_REGIONS", result.as_dict()
    assert result.hot_blocks, result.as_dict()
    # At least one hot block overlaps the pasted 96..160 square.
    assert any(
        80 <= b["x"] < 176 and 80 <= b["y"] < 176 for b in result.hot_blocks
    ), result.as_dict()


def test_png_input_is_inconclusive_not_a_verdict():
    buf = io.BytesIO()
    textured_image().save(buf, "PNG")
    result = analyse_image_bytes(buf.getvalue())
    assert result.verdict == "INCONCLUSIVE"
    assert "JPEG" in result.reason


def test_flat_image_is_inconclusive():
    flat = Image.new("RGB", (256, 256), (120, 120, 120))
    result = analyse_image_bytes(jpeg_bytes(flat))
    assert result.verdict == "INCONCLUSIVE"


def test_undecodable_bytes_raise_input_error():
    with pytest.raises(ElaInputError):
        analyse_image_bytes(b"this is not an image at all")


def test_result_dict_carries_limits_note():
    result = analyse_image_bytes(jpeg_bytes(textured_image()))
    payload = result.as_dict()
    assert payload["verdict"] == "CONSISTENT"
    assert "not proof" in payload["limits"]
    assert payload["blocks_total"] > 0
