"""
TASK-IG2-SEN-01 — Defensive-only skill pack tests.

The pack adapts DEFENSIVE skills from the community
Anthropic-Cybersecurity-Skills library (Apache-2.0, Mahipal Jangra /
mukul975 — an independent community project, NOT affiliated with
Anthropic PBC). Offensive and dual-use skills are excluded by policy and
the loader must refuse them fail-closed.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Sentinel.app.services.defensive_skills import (  # noqa: E402
    EXCLUDED_CATEGORIES,
    EXCLUDED_SKILL_NAMES,
    EXCLUDED_TIERS,
    DefensiveSkillPolicyError,
    check_skill_policy,
    load_defensive_skill_pack,
    load_skill_file,
)

PACK_ROOT = (
    Path(__file__).resolve().parents[1] / "Sentinel" / "skills" / "defensive"
)


@pytest.fixture(scope="module")
def pack():
    return load_defensive_skill_pack()


def test_pack_loads_and_is_all_defensive(pack):
    assert len(pack) >= 10
    audit = pack.audit()
    assert audit["all_defensive"] is True
    assert audit["tiers_present"] == ["defensive"]


def test_pack_covers_core_defensive_domains(pack):
    domains = {s.domain for s in pack.skills.values()}
    assert {
        "soc-operations", "incident-response", "cloud-security",
        "threat-hunting", "vulnerability-management", "iam", "ai-security",
    } <= domains


def test_every_skill_has_workflow_and_mapping(pack):
    for skill in pack.skills.values():
        assert skill.workflow, skill.name
        assert skill.description, skill.name
        assert skill.csf or skill.atlas, skill.name


def test_no_excluded_names_or_categories_in_pack(pack):
    for skill in pack.skills.values():
        assert skill.name not in EXCLUDED_SKILL_NAMES
        assert skill.domain not in EXCLUDED_CATEGORIES
        assert skill.tier not in EXCLUDED_TIERS


def test_search_finds_skills(pack):
    hits = pack.search("ssh brute force")
    assert hits and hits[0].name == "detecting-ssh-brute-force"
    assert pack.search("prompt injection")[0].name == (
        "defending-llm-prompt-injection"
    )


def test_manifest_matches_pack(pack):
    manifest = json.loads((PACK_ROOT / "manifest.json").read_text())
    assert {e["name"] for e in manifest["included"]} == set(pack.skills)
    assert set(manifest["excluded_tiers"]) == set(EXCLUDED_TIERS)


def test_notice_carries_attribution_and_caveat():
    notice = (PACK_ROOT / "NOTICE.md").read_text()
    assert "Apache-2.0" in notice
    assert "Mahipal Jangra" in notice
    assert "NOT affiliated with" in notice and "Anthropic" in notice


def _write_skill(root: Path, name: str, tier: str, domain: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"---\nname: {name}\ndescription: test skill\ntier: {tier}\n"
            f"domain: {domain}\ncsf: [DE.CM]\n---\n\n# T\n\n## Workflow\n"
            "1. step one\n"
        )
    return path


def test_loader_refuses_offensive_tier(tmp_path):
    _write_skill(tmp_path, "some-attack-skill", "offensive", "red-team")
    with pytest.raises(DefensiveSkillPolicyError):
        load_defensive_skill_pack(tmp_path)


def test_loader_refuses_dual_use_tier(tmp_path):
    _write_skill(tmp_path, "some-osint-skill", "dual-use", "osint")
    with pytest.raises(DefensiveSkillPolicyError):
        load_defensive_skill_pack(tmp_path)


def test_loader_refuses_excluded_name_even_if_labelled_defensive(tmp_path):
    path = _write_skill(tmp_path, "phishing-simulation", "defensive", "soc-operations")
    with pytest.raises(DefensiveSkillPolicyError):
        load_skill_file(path)


def test_loader_refuses_excluded_category_even_if_labelled_defensive(tmp_path):
    path = _write_skill(tmp_path, "harmless-name", "defensive", "exploitation")
    with pytest.raises(DefensiveSkillPolicyError):
        load_skill_file(path)


def test_policy_gate_accepts_plain_defensive():
    check_skill_policy("detecting-things", "defensive", "soc-operations")


def test_missing_pack_dir_fails_closed(tmp_path):
    with pytest.raises(DefensiveSkillPolicyError):
        load_defensive_skill_pack(tmp_path / "does-not-exist")
