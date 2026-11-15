"""VyralX invisible provenance watermarking (TASK-IG-VYR-08).

The IG reference corpus item Ddp2aMZtW8V covers Google's invisible
AI-content watermarking (the SynthID idea): content carries its
origin inside the media itself, invisibly, so it can be identified
wherever it turns up. VyralX's version of that idea is narrower
and fully its own: **every asset VyralX produces carries its
VYR-004 provenance record id invisibly**, so a thumbnail or frame
found anywhere can be traced back to the exact registry record
that licensed it — the registry says what the rights are, the
watermark proves which record an asset belongs to.

Implementation, honestly scoped:

* **Images** — the payload (record id + SHA-256 of the record's
  canonical registry JSON) is embedded in pixel LSBs (RGB,
  row-major) with a magic header, length and CRC-32. Pure Pillow;
  embed/extract/verify are deterministic and fully tested.
* **Video** — a guarded ffmpeg path extracts one frame, watermarks
  it as above, and writes an MP4 metadata marker carrying the
  record id. The metadata marker is *visible* metadata (named as
  such); the invisible layer is the frame watermark.
* **Limits, stated plainly:** LSB watermarking survives lossless
  copying and light edits; it does NOT survive re-encoding,
  cropping at scale, or screenshot-resampling. It is a provenance
  aid for honest tracing — not DRM, not proof against a determined
  adversary, and never a substitute for the registry itself.
  SynthID-class robustness (learned embeddings) is a research
  system, not something this module pretends to replicate.

Python 3.10; Pillow is the only dependency (already a VyralX
dependency — thumbnails/overlays use it).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zlib
from pathlib import Path
from typing import Any

from PIL import Image

from app.services.remix_flow import ProvenanceRecord, load_provenance

WATERMARK_VERSION = "ig-vyr08-1"
_MAGIC = b"VYW1"
_HEADER_BYTES = len(_MAGIC) + 4 + 4  # magic + length + crc32


def build_payload(record: ProvenanceRecord) -> bytes:
    """The watermark payload for a provenance record (JSON bytes)."""
    canonical = json.dumps(record.to_dict(), sort_keys=True,
                           ensure_ascii=False)
    return json.dumps({
        "v": 1,
        "wm": WATERMARK_VERSION,
        "record_id": record.record_id,
        "registry_sha256": hashlib.sha256(
            canonical.encode("utf-8")).hexdigest(),
    }, sort_keys=True).encode("utf-8")


def _frame(payload: bytes) -> bytes:
    return (_MAGIC + len(payload).to_bytes(4, "big") + payload
            + (zlib.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "big"))


def capacity_bytes(image: Image.Image) -> int:
    """Payload capacity of an image in bytes (1 bit per channel)."""
    w, h = image.size
    return (w * h * 3) // 8 - _HEADER_BYTES


def embed_payload(image: Image.Image, payload: bytes) -> Image.Image:
    """Return a copy of ``image`` with ``payload`` in its LSBs."""
    img = image.convert("RGB")
    if len(payload) > capacity_bytes(img):
        raise ValueError(
            f"image too small: payload {len(payload)}B exceeds "
            f"capacity {capacity_bytes(img)}B")
    frame = _frame(payload)
    bits = [(byte >> shift) & 1 for byte in frame
            for shift in range(7, -1, -1)]
    pixels = list(img.getdata())
    out = []
    for i, (r, g, b) in enumerate(pixels):
        channels = [r, g, b]
        for c in range(3):
            idx = i * 3 + c
            if idx < len(bits):
                channels[c] = (channels[c] & 0xFE) | bits[idx]
        out.append(tuple(channels))
    img.putdata(out)
    return img


def extract_payload(image: Image.Image) -> bytes | None:
    """Extract a watermark payload, or None if absent/corrupt.

    A flipped-bit payload fails its CRC and returns None — tamper
    and "no watermark" are both reported as absence, and the
    verifier distinguishes them by checking the header first
    (:func:`has_watermark_header`).
    """
    img = image.convert("RGB")
    bits: list[int] = []
    for (r, g, b) in img.getdata():
        bits.extend((r & 1, g & 1, b & 1))

    def take(nbytes: int, offset_bits: int) -> bytes:
        out = bytearray()
        for i in range(nbytes):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[offset_bits + i * 8 + j]
            out.append(byte)
        return bytes(out)

    header_bits = _HEADER_BYTES * 8
    if len(bits) < header_bits or take(4, 0) != _MAGIC:
        return None
    length = int.from_bytes(take(4, 32), "big")
    if length <= 0 or (len(_MAGIC) + 4 + length + 4) * 8 > len(bits):
        return None
    payload = take(length, 64)
    crc = int.from_bytes(take(4, 64 + length * 8), "big")
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        return None
    return payload


def has_watermark_header(image: Image.Image) -> bool:
    """True when the magic header is present (even if CRC fails)."""
    img = image.convert("RGB")
    bits: list[int] = []
    for (r, g, b) in list(img.getdata())[:11]:
        bits.extend((r & 1, g & 1, b & 1))
    magic_bits = [(byte >> shift) & 1 for byte in _MAGIC
                  for shift in range(7, -1, -1)]
    return bits[:32] == magic_bits


def watermark_image_file(source: str, record: ProvenanceRecord,
                         output: str) -> dict[str, Any]:
    """Embed a record's payload into an image file (PNG out)."""
    with Image.open(source) as img:
        marked = embed_payload(img, build_payload(record))
        marked.save(output, format="PNG")
    return {"watermarked": True, "output": output,
            "record_id": record.record_id,
            "watermark_version": WATERMARK_VERSION,
            "survives": "lossless copying; NOT re-encoding/cropping"}


def verify_image(image: Image.Image,
                 registry_path: Path | None = None) -> dict[str, Any]:
    """Verify an image's watermark against the provenance registry."""
    payload = extract_payload(image)
    if payload is None:
        return {
            "verified": False,
            "header_present": has_watermark_header(image),
            "reason": ("watermark header present but payload failed "
                       "its CRC — media was altered after marking"
                       if has_watermark_header(image) else
                       "no VyralX watermark found"),
        }
    try:
        data = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"verified": False, "header_present": True,
                "reason": "payload is not valid watermark JSON"}
    record_id = data.get("record_id")
    for record in load_provenance(registry_path):
        if record.record_id == record_id:
            expected = hashlib.sha256(json.dumps(
                record.to_dict(), sort_keys=True,
                ensure_ascii=False).encode("utf-8")).hexdigest()
            if expected == data.get("registry_sha256"):
                return {"verified": True, "record_id": record_id,
                        "title": record.title,
                        "license_class": record.license_class,
                        "reason": "watermark matches the registry "
                                  "record exactly"}
            return {"verified": False, "record_id": record_id,
                    "reason": "record id found but registry hash "
                              "differs — registry record changed "
                              "after marking"}
    return {"verified": False, "record_id": record_id,
            "reason": "watermark is genuine but its record is not "
                      "in this registry"}


def watermark_video_frame(video_path: str, record: ProvenanceRecord,
                          output_dir: str, at_seconds: float = 1.0,
                          timeout: int = 120) -> dict[str, Any]:
    """Guarded: extract one frame, watermark it, mark the MP4.

    Produces ``<output_dir>/frame_watermarked.png`` and
    ``<output_dir>/marked.mp4`` (metadata marker
    ``comment=vyralx-provenance:<record_id>`` — visible metadata,
    named as such). Reports honestly when ffmpeg or the source is
    unavailable; executes nothing else.
    """
    if shutil.which("ffmpeg") is None:
        return {"watermarked": False, "reason": "ffmpeg not found"}
    if not Path(video_path).exists():
        return {"watermarked": False,
                "reason": f"source not found: {video_path}"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    frame_png = out / "frame_raw.png"
    grab = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(at_seconds), "-i", video_path,
         "-frames:v", "1", str(frame_png)],
        capture_output=True, text=True, timeout=timeout)
    if grab.returncode != 0 or not frame_png.exists():
        return {"watermarked": False,
                "reason": f"frame grab failed: "
                          f"{grab.stderr.strip()[:200]}"}
    marked = watermark_image_file(str(frame_png), record,
                                  str(out / "frame_watermarked.png"))
    marked_mp4 = out / "marked.mp4"
    mux = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", video_path, "-map", "0", "-c", "copy",
         "-metadata", f"comment=vyralx-provenance:{record.record_id}",
         str(marked_mp4)],
        capture_output=True, text=True, timeout=timeout)
    if mux.returncode != 0 or not marked_mp4.exists():
        return {"watermarked": False,
                "reason": f"metadata mux failed: "
                          f"{mux.stderr.strip()[:200]}"}
    return {"watermarked": True,
            "frame": marked["output"],
            "marked_video": str(marked_mp4),
            "record_id": record.record_id,
            "metadata_marker": "visible MP4 comment metadata",
            "invisible_layer": "the watermarked frame PNG",
            "survives": "lossless copying; NOT re-encoding/cropping"}
