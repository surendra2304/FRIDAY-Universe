"""TASK-VYR-019: the series registry is the loop's single source of truth
for all-category organisation — every trending category must resolve to
a series, and every editorial label the pipeline can emit must file
under exactly one series."""
from __future__ import annotations

from app.services.viral_series import (
    LABEL_BY_YOUTUBE_ID,
    SERIES_BY_LABEL,
    YOUTUBE_TRENDING_CATEGORIES,
    label_for_youtube_category_id,
    normalise_label,
    series_for_category,
)


def test_every_trending_category_has_a_series():
    assert len(YOUTUBE_TRENDING_CATEGORIES) >= 12
    for category_id, label, _name in YOUTUBE_TRENDING_CATEGORIES:
        assert LABEL_BY_YOUTUBE_ID[category_id] == label
        assert label in SERIES_BY_LABEL
        info = SERIES_BY_LABEL[label]
        assert info["youtube_category_id"] == category_id
        assert info["series"].startswith("VyralX ")
        assert info["playlist_title"].endswith("| VyralX")
        assert info["slug"]


def test_all_pipeline_labels_are_registered():
    # The labels viral_remix's maps key on (original lanes + the
    # all-category extension) must all resolve to a series.
    for label in (
        "VIRAL", "COMEDY", "SPORTS", "FILM", "AUTOS", "MUSIC", "PETS",
        "TRAVEL", "GAMING", "PEOPLE", "ENTERTAINMENT", "NEWS", "HOWTO",
        "EDUCATION", "TECH",
    ):
        assert normalise_label(label) == label
        assert series_for_category(label)["label"] == label


def test_normalise_label_aliases_and_fallback():
    assert normalise_label("comedy") == "COMEDY"
    assert normalise_label(" Sports ") == "SPORTS"
    assert normalise_label("") == "VIRAL"
    assert normalise_label(None) == "VIRAL"
    assert normalise_label("not-a-category") == "VIRAL"


def test_label_for_youtube_category_id():
    assert label_for_youtube_category_id("17") == "SPORTS"
    assert label_for_youtube_category_id("23") == "COMEDY"
    assert label_for_youtube_category_id("999") == "VIRAL"
