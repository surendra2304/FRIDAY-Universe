"""TASK-VYR-057: offline pins for the cycle-4 pool refresh run 2 file.

Covers ``docs/collaboration/TASK-VYR-057-POOL.json`` (filed by the
discovery pass on S2, 2026-11-24 ~18:19-18:24 IST): the pool schema, the
15-60s Shorts-length gate, the most-popular ranking by view_count, and
disjointness from the VYR-055 pool, the VYR-053 pool, and from the VYR-037
candidate 2 id.
Stdlib-only and fully offline: the pool files are read from the repo, so
no network and no YouTube account are needed.

These pins fail if a pool edit breaks the ranking, lets a non-Shorts
candidate in, drops a gate verdict, or re-files a candidate another pool
already holds.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_POOL = _ROOT / "docs" / "collaboration" / "TASK-VYR-057-POOL.json"
_VYR055_POOL = _ROOT / "docs" / "collaboration" / "TASK-VYR-055-POOL.json"
_VYR053_POOL = _ROOT / "docs" / "collaboration" / "TASK-VYR-053-POOL.json"

GATE_KEYS = {
    "bgm_presence",
    "caption_track_count",
    "duration_15_60s",
    "licence",
    "loudness",
    "watermark",
}


@pytest.fixture(scope="module")
def pool():
    return json.loads(_POOL.read_text())


@pytest.fixture(scope="module")
def vyr055_ids():
    return {c["id"] for c in json.loads(_VYR055_POOL.read_text())["candidates"]}


@pytest.fixture(scope="module")
def vyr053_ids():
    return {c["id"] for c in json.loads(_VYR053_POOL.read_text())["candidates"]}


def test_pool_branch_and_count(pool):
    assert pool["branch"] == "muse4/task-vyr-057-supervised-cycle-4-pool-refresh-2"
    assert len(pool["candidates"]) == 4


def test_ranks_are_1_to_4_in_order(pool):
    assert [c["rank"] for c in pool["candidates"]] == [1, 2, 3, 4]


def test_ranked_by_views_descending(pool):
    views = [c["views"] for c in pool["candidates"]]
    assert views == sorted(views, reverse=True)
    assert all(isinstance(v, int) and v >= 0 for v in views)


def test_shorts_length_gate_passes_for_all(pool):
    for c in pool["candidates"]:
        assert 15 <= c["duration_seconds"] <= 60
        assert c["gates"]["duration_15_60s"] == "PASS"


def test_candidate_shape_and_urls(pool):
    for c in pool["candidates"]:
        assert isinstance(c["id"], str) and c["id"]
        assert isinstance(c["title"], str) and c["title"]
        assert isinstance(c["uploader"], str) and c["uploader"]
        assert c["url"] == f"https://youtube.com/shorts/{c['id']}"
        assert set(c["gates"]) == GATE_KEYS
        assert c["gates"]["licence"] == "PENDING"
        for gate in ("caption_track_count", "bgm_presence", "watermark", "loudness"):
            assert c["gates"][gate] == "BLOCKED"


def test_disjoint_from_vyr055_pool(pool, vyr055_ids):
    assert len(vyr055_ids) == 7
    assert not ({c["id"] for c in pool["candidates"]} & vyr055_ids)


def test_disjoint_from_vyr053_pool(pool, vyr053_ids):
    assert len(vyr053_ids) == 6
    assert not ({c["id"] for c in pool["candidates"]} & vyr053_ids)


def test_disjoint_from_vyr037_candidate_2(pool):
    assert "CpQGaTtppnU" not in {c["id"] for c in pool["candidates"]}


def test_no_duplicate_ids(pool):
    ids = [c["id"] for c in pool["candidates"]]
    assert len(ids) == len(set(ids))
