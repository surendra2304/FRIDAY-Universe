"""IG General implementer wave, VyralX BUILD 2 of 4 (cluster B1-07):
the layered thumbnail-template lane.

Behaviour pinned here:

* the seed registry loads and validates (3 templates, canvas sizes,
  slot maps), and a template whose slot map is broken is rejected with
  the reason, never silently half-loaded;
* slot filling composites image + badge + title slots in z order and
  the output file really has the requested export size (canvas-native,
  platform presets, explicit tuples);
* text overflow is handled by shrinking, then wrapping, then an
  ellipsised truncation that is *reported* in the result warnings —
  never a silent mid-glyph clip;
* a missing required slot refuses the render (no partial thumbnail);
  an unfilled optional slot is skipped and recorded; an unknown fill
  key is refused (typo protection);
* gate parity: title text the packaging checklist would reject is
  refused by the lane with the lint's own issues — the same verdict
  from ``packaging.lint_thumbnail_text`` and from the
  ``packaging_thumbnail_text`` gate inside ``prepublish_checklist``.
  There is no template-lane bypass around the packaging gates.

On clean main every test fails: app.services.thumbnail_templates does
not exist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.services import packaging
from app.services import thumbnail_templates as tt

SEED_ROOT = (
    Path(__file__).resolve().parent.parent
    / "app" / "data" / "thumbnail_templates"
)


@pytest.fixture()
def registry() -> tt.TemplateRegistry:
    return tt.TemplateRegistry(SEED_ROOT)


@pytest.fixture()
def subject(tmp_path: Path) -> Path:
    """A synthetic subject image (producers fill this slot with a frame)."""
    path = tmp_path / "subject.png"
    Image.new("RGB", (480, 640), (200, 60, 40)).save(path)
    return path


def _mini_template(root: Path, slots: dict, canvas=(400, 300)) -> Path:
    """Write a one-off template directory for validation tests."""
    tdir = root / "mini"
    tdir.mkdir(parents=True)
    Image.new("RGBA", canvas, (10, 10, 10, 255)).save(tdir / "bg.png")
    payload = {
        "id": "mini",
        "name": "Mini",
        "canvas": {"width": canvas[0], "height": canvas[1]},
        "layers": [{"file": "bg.png", "z": 0}],
        "slots": slots,
    }
    (tdir / "template.json").write_text(json.dumps(payload), encoding="utf-8")
    return tdir


# ---------------------------------------------------------------------------
# Registry / validation
# ---------------------------------------------------------------------------


def test_seed_registry_loads_three_templates(registry: tt.TemplateRegistry):
    ids = registry.template_ids()
    assert ids == ["clean-explainer-9x16", "impact-arena-9x16", "impact-landscape-16x9"]
    arena = registry.get("impact-arena-9x16")
    assert arena.canvas == (1080, 1920)
    assert arena.slots["subject"].required is True
    assert arena.slots["title"].type == "title_text"
    assert registry.get("impact-landscape-16x9").canvas == (1280, 720)


def test_describe_reports_slots(registry: tt.TemplateRegistry):
    desc = registry.describe("impact-arena-9x16")
    assert desc["canvas"] == {"width": 1080, "height": 1920}
    assert desc["slots"]["badge"]["type"] == "badge_text"
    assert set(desc["layers"]) == {"background.png", "overlay.png"}


def test_unknown_template_raises(registry: tt.TemplateRegistry):
    with pytest.raises(tt.TemplateNotFoundError):
        registry.get("no-such-template")


def test_invalid_slot_map_rejected(tmp_path: Path):
    _mini_template(tmp_path, {"x": {"type": "hologram", "rect": [0, 0, 50, 50]}})
    with pytest.raises(tt.TemplateValidationError, match="unknown type"):
        tt.TemplateRegistry(tmp_path).get("mini")


def test_rect_outside_canvas_rejected(tmp_path: Path):
    _mini_template(tmp_path, {"x": {"type": "image", "rect": [300, 0, 200, 50]}})
    with pytest.raises(tt.TemplateValidationError, match="not inside the canvas"):
        tt.TemplateRegistry(tmp_path).get("mini")


def test_layer_size_mismatch_rejected(tmp_path: Path):
    tdir = _mini_template(tmp_path, {"x": {"type": "image", "rect": [0, 0, 50, 50]}})
    Image.new("RGBA", (99, 99), (0, 0, 0, 255)).save(tdir / "bg.png")
    with pytest.raises(tt.TemplateValidationError, match="canvas"):
        tt.TemplateRegistry(tmp_path).get("mini")


# ---------------------------------------------------------------------------
# Rendering: slot filling and export sizes
# ---------------------------------------------------------------------------


def test_render_fills_slots_and_exports_canvas_size(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    out = tmp_path / "arena.png"
    result = tt.render(
        "impact-arena-9x16",
        {"subject": subject, "title": "HE DID WHAT?", "badge": "GAMING"},
        out,
        title="The Untold Story of One Impossible Comeback",
        registry=registry,
    )
    assert Path(result.path).is_file()
    assert result.size == (1080, 1920)
    with Image.open(out) as img:
        assert img.size == (1080, 1920)
    assert set(result.filled_slots) == {"subject", "title", "badge"}
    assert result.lint == {"ok": True, "issues": []}
    # The subject slot region carries the subject's colour, not backdrop.
    with Image.open(out) as img:
        assert img.convert("RGB").getpixel((700, 700)) == (200, 60, 40)


def test_render_platform_export_sizes(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    fills = {"subject": subject, "title": "HE DID WHAT?"}
    for preset, expected in (
        ("shorts", (1080, 1920)),
        ("youtube", (1280, 720)),
        ("square", (1080, 1080)),
    ):
        out = tmp_path / f"out_{preset}.png"
        result = tt.render("impact-arena-9x16", fills, out, size=preset, registry=registry)
        assert result.size == expected
        with Image.open(out) as img:
            assert img.size == expected
    out = tmp_path / "out_tuple.png"
    result = tt.render(
        "impact-arena-9x16", fills, out, size=(640, 360), registry=registry
    )
    assert result.size == (640, 360)


def test_render_jpeg_destination(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    out = tmp_path / "thumb.jpg"
    tt.render(
        "impact-landscape-16x9",
        {"subject": subject, "title": "NOBODY SAW IT COMING"},
        out,
        registry=registry,
    )
    with Image.open(out) as img:
        assert img.format == "JPEG"
        assert img.size == (1280, 720)


def test_background_image_slot_overrides_backdrop(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    backdrop = tmp_path / "backdrop.png"
    Image.new("RGB", (800, 800), (20, 120, 200)).save(backdrop)
    out = tmp_path / "custom_bg.png"
    tt.render(
        "impact-arena-9x16",
        {"subject": subject, "title": "HE DID WHAT?", "background_image": backdrop},
        out,
        registry=registry,
    )
    with Image.open(out) as img:
        # A corner away from subject/title shows the supplied backdrop.
        assert img.convert("RGB").getpixel((60, 1100)) == (20, 120, 200)


def test_optional_slot_skipped_and_recorded(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    out = tmp_path / "no_badge.png"
    result = tt.render(
        "impact-arena-9x16",
        {"subject": subject, "title": "HE DID WHAT?"},
        out,
        registry=registry,
    )
    assert "badge" in result.skipped_slots
    assert "badge" not in result.filled_slots


# ---------------------------------------------------------------------------
# Missing / unknown slots
# ---------------------------------------------------------------------------


def test_missing_required_slot_refused(
    registry: tt.TemplateRegistry, tmp_path: Path
):
    out = tmp_path / "never.png"
    with pytest.raises(tt.MissingSlotError, match="subject"):
        tt.render("impact-arena-9x16", {"title": "HE DID WHAT?"}, out, registry=registry)
    assert not out.exists()  # fail-closed: no partial thumbnail


def test_unknown_fill_key_refused(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    with pytest.raises(tt.UnknownSlotError, match="titel"):
        tt.render(
            "impact-arena-9x16",
            {"subject": subject, "titel": "HE DID WHAT?"},
            tmp_path / "x.png",
            registry=registry,
        )


def test_missing_subject_file_refused(
    registry: tt.TemplateRegistry, tmp_path: Path
):
    with pytest.raises(tt.SlotFillError, match="does not exist"):
        tt.render(
            "impact-arena-9x16",
            {"subject": tmp_path / "ghost.png", "title": "HE DID WHAT?"},
            tmp_path / "x.png",
            registry=registry,
        )


# ---------------------------------------------------------------------------
# Text overflow
# ---------------------------------------------------------------------------


def test_long_title_text_truncates_with_warning(tmp_path: Path):
    _mini_template(
        tmp_path,
        {
            "title": {
                "type": "title_text",
                "rect": [10, 10, 200, 90],
                "required": True,
                "options": {"size_start": 60, "size_min": 40, "max_lines": 2},
            }
        },
    )
    registry = tt.TemplateRegistry(tmp_path)
    out = tmp_path / "fitted.png"
    # Lint-clean (2 words, 19 chars) but far too wide for the 200px rect
    # even at the minimum font size: shrink + wrap cannot save it, so the
    # fit must truncate with an ellipsis and report it.
    result = tt.render(
        "mini",
        {"title": "WONDERFUL WONDERFUL"},
        out,
        registry=registry,
    )
    assert Path(result.path).is_file()
    assert any("truncated" in w for w in result.warnings)


def test_fitting_title_text_does_not_truncate(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    result = tt.render(
        "impact-arena-9x16",
        {"subject": subject, "title": "HE DID WHAT?"},
        tmp_path / "ok.png",
        registry=registry,
    )
    assert not any("truncated" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Gate parity with the packaging system
# ---------------------------------------------------------------------------


def _full_candidate(thumbnail_text: str, title: str) -> dict:
    """A prepublish candidate that passes every non-thumbnail gate."""
    return {
        "lane": "tech_ai",
        "title": title,
        "thumbnail_text": thumbnail_text,
        "hook_line": "This AI just changed everything. Watch.",
        "duration_s": 30,
        "claimed_material_possible": False,
        "sync": {
            "beat_max_error_s": 0.1,
            "caption_mean_abs_offset_s": 0.05,
            "caption_max_abs_offset_s": 0.2,
            "narration_coverage": 0.99,
        },
        "provenance": {
            "source_url": "https://example.com/source",
            "author": "NASA",
            "license": "public domain",
            "retrieved_on": "2026-11-17",
        },
        "commentary": {"script": " ".join(["word"] * 45), "voiceover_present": True},
    }


@pytest.mark.parametrize(
    "bad_text",
    [
        "THIS TITLE HAS FAR TOO MANY WORDS",  # > 4 words and > 24 chars
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # 26 chars > 24
        "",  # empty (treated as a missing required fill by the lane)
    ],
)
def test_gate_parity_lint_failing_text_refused(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path, bad_text: str
):
    title = "This AI Just Did 5 Impossible Things"
    lint = packaging.lint_thumbnail_text(bad_text, title)
    assert lint["ok"] is False  # the packaging lint itself rejects it
    checklist = packaging.prepublish_checklist(_full_candidate(bad_text, title))
    thumb_gate = next(
        g for g in checklist["gates"] if g["gate"] == "packaging_thumbnail_text"
    )
    assert thumb_gate["ok"] is False  # ...and so does the checklist gate
    with pytest.raises((tt.ThumbnailTextGateError, tt.MissingSlotError)):
        tt.render(
            "impact-arena-9x16",
            {"subject": subject, "title": bad_text},
            tmp_path / "refused.png",
            title=title,
            registry=registry,
        )
    assert not (tmp_path / "refused.png").exists()


def test_gate_error_carries_the_lints_own_issues(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    bad_text = "THIS TITLE HAS FAR TOO MANY WORDS"
    title = "This AI Just Did 5 Impossible Things"
    with pytest.raises(tt.ThumbnailTextGateError) as excinfo:
        tt.render(
            "impact-arena-9x16",
            {"subject": subject, "title": bad_text},
            tmp_path / "refused.png",
            title=title,
            registry=registry,
        )
    assert excinfo.value.issues == packaging.lint_thumbnail_text(bad_text, title)["issues"]


def test_gate_parity_title_repeat_refused(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    # Thumbnail text that merely repeats the title's opening words is a
    # packaging-gate failure; the lane must refuse it identically.
    title = "The Untold Story of One Impossible Comeback"
    with pytest.raises(tt.ThumbnailTextGateError, match="repeats the title"):
        tt.render(
            "impact-arena-9x16",
            {"subject": subject, "title": "The Untold Story"},
            tmp_path / "refused.png",
            title=title,
            registry=registry,
        )


def test_render_template_thumbnail_returns_path(
    registry: tt.TemplateRegistry, subject: Path, tmp_path: Path
):
    out = tmp_path / "parity.png"
    path = tt.render_template_thumbnail(
        "impact-arena-9x16",
        {"subject": subject, "title": "HE DID WHAT?"},
        out,
        registry=registry,
    )
    assert path == str(out)
    assert Path(path).is_file()
