"""TASK-IG-VYR-08: invisible provenance watermarking (SynthID-style idea).

Behaviour pinned here:

* a provenance payload (record id + registry hash) round-trips
  through an image's LSBs byte-exactly, and the marked image is
  visually the same image (LSB changes only);
* verification against the provenance registry succeeds for a
  genuine mark, fails for an unmarked image, and detects a
  tampered payload via CRC (header present, payload invalid);
* an image too small for the payload is refused, naming capacity;
* the guarded video path watermarks a real frame and marks the
  MP4's metadata on a synthetic clip (skipped without ffmpeg).

On clean main every test fails: app.services.provenance_watermark
does not exist.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest
from PIL import Image

from app.services import provenance_watermark as wm
from app.services import remix_flow as rf

RECORD = rf.ProvenanceRecord(
    platform="wikimedia_commons", title="Gradient Sun",
    author="NASA/SDO", source_page_url="https://example.com/sun",
    media_url="https://example.com/sun.mp4",
    license_name="Public Domain", retrieved_at="2026-11-15",
    license_class="public_domain", allowed=True,
    decision_reason="PD test record")


def _image(size=(64, 64), colour=(120, 30, 200)):
    return Image.new("RGB", size, colour)


def test_payload_roundtrip_and_visual_identity():
    img = _image()
    payload = wm.build_payload(RECORD)
    marked = wm.embed_payload(img, payload)
    assert wm.extract_payload(marked) == payload
    # LSB-only change: every channel differs by at most 1.
    before = list(img.getdata())
    after = list(marked.getdata())
    assert all(abs(a - b) <= 1
               for px_a, px_b in zip(after, before)
               for a, b in zip(px_a, px_b))


def test_unmarked_image_has_no_payload():
    img = _image()
    assert wm.extract_payload(img) is None
    assert wm.has_watermark_header(img) is False
    verdict = wm.verify_image(img)
    assert verdict["verified"] is False
    assert "no VyralX watermark" in verdict["reason"]


def test_verify_against_registry(tmp_path):
    registry = tmp_path / "prov.jsonl"
    rf.record_provenance([RECORD], registry)
    marked = wm.embed_payload(_image(), wm.build_payload(RECORD))
    verdict = wm.verify_image(marked, registry)
    assert verdict["verified"] is True
    assert verdict["record_id"] == RECORD.record_id
    assert verdict["license_class"] == "public_domain"


def test_tamper_detected_via_crc():
    marked = wm.embed_payload(_image(), wm.build_payload(RECORD))
    pixels = list(marked.getdata())
    # Flip LSBs across a stretch of pixels (payload region).
    for i in range(40, 90):
        r, g, b = pixels[i]
        pixels[i] = (r ^ 1, g ^ 1, b ^ 1)
    marked.putdata(pixels)
    assert wm.extract_payload(marked) is None
    verdict = wm.verify_image(marked)
    assert verdict["verified"] is False
    assert verdict["header_present"] is True
    assert "altered" in verdict["reason"]


def test_capacity_refusal():
    tiny = _image(size=(4, 4))
    with pytest.raises(ValueError, match="too small"):
        wm.embed_payload(tiny, wm.build_payload(RECORD))


@pytest.mark.skipif(shutil.which("ffmpeg") is None,
                    reason="ffmpeg not available")
def test_video_frame_and_metadata_marking(tmp_path):
    src = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-shortest", str(src)], check=True, capture_output=True,
        timeout=60)
    result = wm.watermark_video_frame(str(src), RECORD,
                                      str(tmp_path / "out"))
    assert result["watermarked"] is True, result
    with Image.open(result["frame"]) as frame:
        assert wm.extract_payload(frame) == wm.build_payload(RECORD)
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_format", "-of", "json",
         result["marked_video"]], capture_output=True, text=True,
        timeout=30)
    assert RECORD.record_id in probe.stdout
