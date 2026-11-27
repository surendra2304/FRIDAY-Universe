"""
TASK-SEN-033 — Sentinel repo-implement wave 3 tests.

Anthropic Cybersecurity Skills is the adapt item: the defensive-only pack
under ``Sentinel/skills/defensive/`` must be wired into the running
``CyberSkillsService`` production path, not merely loadable by a standalone
loader test. PentAGI is reference-only: Sentinel may bank its role-design
notes, but no PentAGI code, import or dependency may enter the runtime.
"""

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Sentinel.app.services.cyber_skills_service import (  # noqa: E402
    CyberSkillsService,
    ds,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def service():
    return CyberSkillsService()


def test_service_loads_defensive_pack_into_catalog(service):
    assert service.defensive_pack is not None
    audit = service.defensive_pack.audit()
    assert audit["all_defensive"] is True
    assert audit["skill_count"] >= 10

    skill = service.catalog.get("detecting-ssh-brute-force")
    assert skill is not None
    assert skill.tier == "defensive"
    assert skill.requires_authorization is False
    assert "T1110" in skill.mapping.attack

    capabilities = service.capabilities()
    assert capabilities["defensive_skill_pack"]["all_defensive"] is True


def test_triage_recommends_defensive_pack_skill(service):
    payload = service.triage(
        "SSH brute force against fleet host",
        [
            {
                "timestamp": "2026-11-27T21:40:00+05:30",
                "description": "Repeated SSH password guessing from one source",
                "technique": "T1110",
                "host": "server-1",
                "source": "auth.log",
            }
        ],
    )
    assert "detecting-ssh-brute-force" in payload["skills"]
    assert "detecting-ssh-brute-force" in payload["crosswalk"]["skills"]


def test_search_and_authorise_defensive_pack_skill(service):
    matches = service.search("T1110 ssh brute force")
    assert matches[0]["skill"] == "detecting-ssh-brute-force"

    decision = service.authorise(
        "detecting-ssh-brute-force",
        target="server-1",
        engagement="sen033-test",
    )
    assert decision["allowed"] is True


def test_authorise_denies_offensive_skill_under_defensive_scope(service):
    decision = service.authorise(
        "wireless-security-assessment",
        target="server-1",
        engagement="sen033-test",
        allowed_tiers=["defensive"],
    )
    assert decision["allowed"] is False
    assert "tier" in decision["reason"]


def _write_skill(root: Path, name: str, tier: str, domain: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\ntier: {tier}\n"
        f"domain: {domain}\ncsf: [DE.CM]\n---\n\n# T\n\n## Workflow\n"
        "1. step one\n",
        encoding="utf-8",
    )


def test_service_refuses_offensive_pack_fail_closed(tmp_path):
    _write_skill(tmp_path, "some-attack-skill", "offensive", "red-team")
    with pytest.raises(ds.DefensiveSkillPolicyError):
        CyberSkillsService(defensive_pack_root=tmp_path)


def test_service_refuses_missing_pack_fail_closed(tmp_path):
    with pytest.raises(ds.DefensiveSkillPolicyError):
        CyberSkillsService(defensive_pack_root=tmp_path / "does-not-exist")


def test_pentagi_is_not_imported_or_depended_on_by_sentinel_runtime():
    runtime_roots = [
        REPO_ROOT / "Sentinel" / "app",
        REPO_ROOT / "Sentinel" / "sentinel",
    ]
    import_re = re.compile(
        r"^\s*(?:import|from)\s+(pentagi|vxcontrol)\b", re.IGNORECASE
    )
    for root in runtime_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                assert not import_re.search(line), f"{path} imports PentAGI: {line}"

    for relpath in [
        "Sentinel/pyproject.toml",
        "Sentinel/requirements.txt",
        "Sentinel/requirements.lock",
        "Sentinel/Dockerfile",
        "Sentinel/docker/Dockerfile.api",
    ]:
        path = REPO_ROOT / relpath
        if path.exists():
            text = path.read_text(encoding="utf-8").lower()
            assert "pentagi" not in text, relpath
            assert "vxcontrol" not in text, relpath
