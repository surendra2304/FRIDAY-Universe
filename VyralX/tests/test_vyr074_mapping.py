"""TASK-VYR-074: repo-side mapping for PRODUCTION-VERIFY of IG3-VYR-07..10.

This test pins the mapping, not live behaviour. Each of the four corpus
items is a MERGED IG3 implementation (Nov 2026-11-17, merge batch 2); the
live extreme-condition verification is a separate leg, gated on the
VyralX-Server route + the VYR-056 yt-dlp repair, and is NOT claimed here.

What is pinned, per item (verified first-hand against main ce3c817f,
2026-11-25 ~01:15 IST):

* IG3-VYR-07 (B114 motion templates, PR #828 via #847):
  ``VyralX/app/services/motion_templates.py`` holds exactly the twelve
  source-named templates in ``_TEMPLATE_NAMES`` and builds
  ``TEMPLATE_LIBRARY`` from them; the editor rules (5 MB logo cap,
  5s-30s loops) and the export matrix are constants in the same module.
* IG3-VYR-08 (B125 idea generator, PR #825 via #848):
  ``VyralX/app/services/idea_generator.py`` defines
  ``analyse_performers`` / ``generate_ideas`` over operator-supplied
  records only — the module makes no platform calls.
* IG3-VYR-09 (B131 production rules, PR #830 via #849):
  ``VyralX/app/services/production_rules.py`` + the single data folder
  ``VyralX/app/data/production_rules.json`` holding exactly the five
  source rules (hook_first_second, visuals_timed_to_voice,
  pictures_land_on_words, motion_until_last_frame,
  frame_review_60fps); ``load_rules`` / ``check_plan`` are defined.
* IG3-VYR-10 (B120 scene-assembly evaluation, PR #832):
  ``VyralX/docs/SCENE_ASSEMBLY_EVALUATION.md`` records the split —
  the composition layer exists, per-scene clip generation stays
  off-fleet by design, the admission gate stays CLOSED.

Stdlib only: the test reads files as text and never imports the app, so
it runs in CI without the service stack.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MOTION_TEMPLATES = ROOT / "VyralX" / "app" / "services" / "motion_templates.py"
IDEA_GENERATOR = ROOT / "VyralX" / "app" / "services" / "idea_generator.py"
PRODUCTION_RULES = ROOT / "VyralX" / "app" / "services" / "production_rules.py"
PRODUCTION_RULES_DATA = ROOT / "VyralX" / "app" / "data" / "production_rules.json"
SCENE_EVAL = ROOT / "VyralX" / "docs" / "SCENE_ASSEMBLY_EVALUATION.md"

EXPECTED_TEMPLATES = (
    "Card Globe",
    "Orbit Globe",
    "Triple Scene",
    "Spiral Stream",
    "Cover Ring",
    "Collage Reel",
    "Fan Shuffle",
    "Sweep Ring",
    "Scatter Zoom",
    "Sphere Wall",
    "Totem Wall",
    "Card Tunnel",
)

EXPECTED_RULE_IDS = (
    "hook_first_second",
    "visuals_timed_to_voice",
    "pictures_land_on_words",
    "motion_until_last_frame",
    "frame_review_60fps",
)

PINNED_TESTS = {
    "IG3-VYR-07": "test_ig3_vyr07_motion_templates.py",
    "IG3-VYR-08": "test_ig3_vyr08_idea_generator.py",
    "IG3-VYR-09": "test_ig3_vyr09_production_rules.py",
    "IG3-VYR-10": "test_ig3_vyr10_scene_assembly_eval.py",
}


def _read(path: Path) -> str:
    assert path.is_file(), f"mapping target missing from checkout: {path}"
    return path.read_text(encoding="utf-8")


def test_vyr07_motion_templates_twelve_source_names():
    src = _read(MOTION_TEMPLATES)
    block = re.search(r"_TEMPLATE_NAMES\s*=\s*\((.*?)\)\n", src, re.S)
    assert block is not None, "_TEMPLATE_NAMES tuple not found"
    names = re.findall(r'\(\s*"([^"]+)",\s*"[^"]+"\)', block.group(1))
    assert tuple(names) == EXPECTED_TEMPLATES, names
    assert "TEMPLATE_LIBRARY" in src
    assert "LOGO_MAX_BYTES = 5_000_000" in src
    assert "LOOP_MIN_SECONDS = 5.0" in src and "LOOP_MAX_SECONDS = 30.0" in src
    for fn in ("list_templates", "get_template", "fill_template", "export_spec"):
        assert re.search(rf"^def {fn}\b", src, re.M), f"missing {fn}"


def test_vyr08_idea_generator_operator_supplied_only():
    src = _read(IDEA_GENERATOR)
    assert "def analyse_performers" in src
    assert "def generate_ideas" in src
    assert "operator-supplied" in src
    assert "no platform calls" in src


def test_vyr09_production_rules_single_folder_five_rules():
    src = _read(PRODUCTION_RULES)
    assert "def load_rules" in src
    assert "def check_plan" in src
    data = json.loads(_read(PRODUCTION_RULES_DATA))
    rules = data.get("rules") or []
    assert len(rules) == 5, [r.get("id") for r in rules]
    assert tuple(r["id"] for r in rules) == EXPECTED_RULE_IDS
    for rule in rules:
        assert rule.get("statement") and rule.get("enforcement"), rule["id"]


def test_vyr10_scene_assembly_eval_records_the_split():
    src = _read(SCENE_EVAL)
    assert "composition layer" in src
    assert "off-fleet" in src.lower() or "OFF-FLEET" in src
    assert "gate stays CLOSED" in src


def test_vyr074_pinned_behaviour_tests_exist():
    tests_dir = ROOT / "VyralX" / "tests"
    for item, name in PINNED_TESTS.items():
        path = tests_dir / name
        assert path.is_file(), f"{item}: pinned behaviour test missing: {name}"
