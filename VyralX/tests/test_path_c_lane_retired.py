"""TASK-VYR-033: the Path C lane is retired — regression pins.

The lane catalogues (``VyralX/app/data/source_catalog_lane*.json``),
their loaders (``app.services.source_catalog{,_lane2,_lane3}``), the
consumers (``app.services.content_factory``, ``app.services.previs``),
the catalogue builders (``VyralX/scripts/build_lane*_catalog.py``)
and the lane tests were removed as one scoped task after verifying
no live path referenced them (GitHub issue #35, TASK-VYR-033
evidence: repo-wide code search + local-tree cross-check).

These pins fail if any part of the lane is resurrected without a
deliberate decision recorded on the board. They are stdlib-only and
do not import any VyralX module.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_DATA = _ROOT / "app" / "data"
_SERVICES = _ROOT / "app" / "services"
_SCRIPTS = _ROOT / "scripts"
_TESTS = _ROOT / "tests"

_RETIRED_JSONS = (
    _DATA / "source_catalog_lane1.json",
    _DATA / "source_catalog_lane2.json",
    _DATA / "source_catalog_lane3.json",
)

_RETIRED_MODULES = (
    "app.services.source_catalog",
    "app.services.source_catalog_lane2",
    "app.services.source_catalog_lane3",
    "app.services.content_factory",
    "app.services.previs",
)

_RETIRED_BUILDERS = (
    _SCRIPTS / "build_lane1_catalog.py",
    _SCRIPTS / "build_lane2_catalog.py",
    _SCRIPTS / "build_lane3_catalog.py",
)

_RETIRED_TESTS = (
    _TESTS / "test_source_catalog.py",
    _TESTS / "test_source_catalog_lane2.py",
    _TESTS / "test_source_catalog_lane3.py",
    _TESTS / "test_ig_vyr02_content_factory.py",
    _TESTS / "test_ig_vyr06_previs.py",
)


def test_lane_catalogue_jsons_absent():
    for path in _RETIRED_JSONS:
        assert not path.exists(), f"Path C lane file resurrected: {path}"


def test_lane_modules_not_importable():
    for name in _RETIRED_MODULES:
        assert importlib.util.find_spec(name) is None, (
            f"Path C lane module resurrected: {name}")
    for filename in ("source_catalog.py", "source_catalog_lane2.py",
                     "source_catalog_lane3.py", "content_factory.py",
                     "previs.py"):
        assert not (_SERVICES / filename).exists(), (
            f"Path C lane file resurrected: {_SERVICES / filename}")


def test_lane_builders_absent():
    for path in _RETIRED_BUILDERS:
        assert not path.exists(), f"Path C lane file resurrected: {path}"


def test_lane_tests_absent():
    for path in _RETIRED_TESTS:
        assert not path.exists(), f"Path C lane file resurrected: {path}"
