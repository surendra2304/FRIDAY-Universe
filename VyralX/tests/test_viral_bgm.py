"""TASK-VYR-019: BGM policy switch + phonk as a first-class style.

Growth mode draws popular/chart tracks (phonk included as a named
source category); monetisation mode draws the YouTube-library folder;
no library ever means "no bed" — the labelled synth fallback stands in.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.services import viral_bgm


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "data_dir": tmp_path / "data",
        "media_dir": tmp_path / "media",
        "render_dir": tmp_path / "renders",
    }
    values.update(overrides)
    return Settings(**values)


def _stock(folder: Path, catalog: list[dict], files: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in files:
        (folder / name).write_bytes(b"fake-audio")
    (folder / "catalog.json").write_text(
        json.dumps({"tracks": catalog}), encoding="utf-8"
    )


def test_policy_folders_and_default(tmp_path):
    growth = _settings(tmp_path)
    assert viral_bgm.policy(growth) == "growth"
    assert viral_bgm.library_dir(growth) == tmp_path / "data" / "bgm"
    monetised = _settings(tmp_path, viral_bgm_policy="monetisation")
    assert viral_bgm.policy(monetised) == "monetisation"
    assert viral_bgm.library_dir(monetised) == tmp_path / "data" / "bgm_library"
    # The Settings validator rejects anything outside the two policies,
    # and policy() still normalises defensively for loose namespaces.
    from types import SimpleNamespace

    assert viral_bgm.policy(SimpleNamespace(viral_bgm_policy="loud")) == "growth"


def test_catalog_styles_and_phonk_filename_inference(tmp_path):
    settings = _settings(tmp_path)
    _stock(
        tmp_path / "data" / "bgm",
        catalog=[
            {"file": "chart-hit.mp3", "title": "Chart Hit", "categories": ["SPORTS"], "styles": ["pop"]},
            {"file": "drift-edit.mp3", "title": "Drift Edit", "categories": ["SPORTS"], "styles": ["phonk"]},
        ],
        files=["chart-hit.mp3", "drift-edit.mp3", "raw-phonk-banger.mp3"],
    )
    tracks = {track["file"]: track for track in viral_bgm.load_catalog(settings)}
    assert tracks["chart-hit.mp3"]["styles"] == ["pop"]
    assert tracks["drift-edit.mp3"]["styles"] == ["phonk"]
    # No catalog entry at all: the filename alone stocks the phonk shelf.
    assert viral_bgm.PHONK_STYLE in tracks["raw-phonk-banger.mp3"]["styles"]
    status = viral_bgm.library_status(settings)
    assert status["tracks_available"] == 3
    assert status["phonk_tracks"] == 2


def test_phonk_preferred_for_high_energy_categories(tmp_path):
    settings = _settings(tmp_path)
    _stock(
        tmp_path / "data" / "bgm",
        catalog=[
            {"file": "chart-hit.mp3", "title": "Chart Hit", "categories": ["SPORTS"], "styles": ["pop"]},
            {"file": "drift-edit.mp3", "title": "Drift Edit", "categories": ["SPORTS"], "styles": ["phonk"]},
        ],
        files=["chart-hit.mp3", "drift-edit.mp3"],
    )
    assert viral_bgm.preferred_style("SPORTS") == "phonk"
    assert viral_bgm.preferred_style("GAMING") == "phonk"
    assert viral_bgm.preferred_style("EDUCATION") == ""
    picked = viral_bgm.select_track(
        settings, category="SPORTS", rotation_key="any",
        style=viral_bgm.preferred_style("SPORTS"),
    )
    assert picked["file"] == "drift-edit.mp3"
    # Without the style preference both tracks stay in the pool.
    either = viral_bgm.select_track(settings, category="SPORTS", rotation_key="any")
    assert either["file"] in {"chart-hit.mp3", "drift-edit.mp3"}
    # Category relevance still outranks style: a phonk track tagged for
    # another category does not evict a category match.
    picked_edu = viral_bgm.select_track(
        settings, category="EDUCATION", rotation_key="any", style="phonk",
    )
    assert picked_edu is not None  # falls back to the whole library


def test_prepare_music_bed_labels_phonk_and_falls_back(tmp_path, monkeypatch):
    from app.services import viral_remix

    settings = _settings(tmp_path)
    _stock(
        tmp_path / "data" / "bgm",
        catalog=[
            {"file": "drift-edit.mp3", "title": "Drift Edit", "categories": ["SPORTS"], "styles": ["phonk"]},
        ],
        files=["drift-edit.mp3"],
    )

    def fake_run(cmd, timeout=None):
        Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[-1]).write_bytes(b"bed")

    monkeypatch.setattr(viral_remix, "_run", fake_run)
    destination = tmp_path / "media" / "voiceovers" / "proj-bed.wav"
    path, label = viral_bgm.prepare_music_bed(
        destination, 30.0, category="SPORTS", settings=settings
    )
    assert path == destination and destination.is_file()
    assert label == "growth:Drift Edit:phonk"
    assert viral_bgm.is_real_track_label(label) is True

    empty = _settings(tmp_path / "other")
    monkeypatch.setattr(
        viral_remix, "build_music_bed",
        lambda dest, seconds: (dest.write_bytes(b"synth"), dest)[1],
    )
    path2, label2 = viral_bgm.prepare_music_bed(
        tmp_path / "media" / "voiceovers" / "proj2-bed.wav", 20.0,
        category="SPORTS", settings=empty,
    )
    assert label2 == "synth_fallback"
    assert viral_bgm.is_real_track_label(label2) is False
    assert path2.is_file()


def test_is_real_track_label_gates_on_library_tracks_only():
    # TASK-VYR-038: the per-job gate field must be True only for a real
    # library track — never for the synth fallback, and never for the
    # empty label (no bed prepared).
    assert viral_bgm.is_real_track_label("growth:Drift Edit:phonk") is True
    assert viral_bgm.is_real_track_label("growth:Chart Hit") is True
    assert viral_bgm.is_real_track_label("monetisation:Library Track") is True
    assert viral_bgm.is_real_track_label("synth_fallback") is False
    assert viral_bgm.is_real_track_label("") is False
