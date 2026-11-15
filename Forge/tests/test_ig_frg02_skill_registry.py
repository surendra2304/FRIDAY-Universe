"""TASK-IG-FRG-02: specialised build-agent roster + skill registry.

Corpus source: Dc_iv4YKCAh (a library of specialised agents + skills).
Pinned properties: the registry is internally consistent, lookups are
deterministic, file/role scoping works, and a broken registry is
*reported* broken rather than silently trusted.
"""
from __future__ import annotations

import pytest

from app.agents.skill_registry import (
    DEFAULT_REGISTRY,
    ROLES,
    Skill,
    SkillRegistry,
    Specialist,
)


def test_default_registry_validates_clean():
    assert DEFAULT_REGISTRY.validate() == []


def test_registry_has_substance():
    # The corpus pattern is a real library, not a token gesture: the
    # default registry must carry a meaningful spread across roles.
    assert len(DEFAULT_REGISTRY.skills) >= 20
    assert len(DEFAULT_REGISTRY.roster) >= 8
    for role in ROLES:
        assert DEFAULT_REGISTRY.skills_for_role(role), role


def test_skill_ids_unique_and_fragments_written():
    ids = [s.id for s in DEFAULT_REGISTRY.skills]
    assert len(ids) == len(set(ids))
    for skill in DEFAULT_REGISTRY.skills:
        assert skill.prompt_fragment.strip(), skill.id


def test_specialist_skills_resolve():
    skills = DEFAULT_REGISTRY.specialist_skills("security-reviewer")
    ids = {s.id for s in skills}
    assert "sec.sql-injection" in ids
    assert "sec.xss" in ids


def test_red_teamer_carries_adversarial_skills():
    skills = DEFAULT_REGISTRY.specialist_skills("red-teamer")
    foci = {f for s in skills for f in s.review_focus}
    assert "trust-boundary" in foci
    assert "privilege-escalation" in foci


def test_skills_for_file_python():
    skills = DEFAULT_REGISTRY.skills_for_file("app/api/users.py", "python")
    ids = {s.id for s in skills}
    assert "dev.sql-safety" in ids
    assert "dev.python-services" in ids


def test_skills_for_file_frontend():
    skills = DEFAULT_REGISTRY.skills_for_file("web/app.js", "javascript")
    ids = {s.id for s in skills}
    assert "sec.xss" in ids
    assert "dev.web-frontend" in ids


def test_skills_for_file_unrelated_gets_nothing_scoped():
    skills = DEFAULT_REGISTRY.skills_for_file("notes/readme.md", "markdown")
    assert skills == []


def test_skills_for_review_focus():
    skills = DEFAULT_REGISTRY.skills_for_review_focus("sql-injection")
    assert {s.id for s in skills} >= {"sec.sql-injection", "dev.sql-safety"}


def test_prompt_fragments_deterministic_registry_order():
    text_a = DEFAULT_REGISTRY.prompt_fragments(["sec.xss", "sec.sql-injection"])
    text_b = DEFAULT_REGISTRY.prompt_fragments(["sec.sql-injection", "sec.xss"])
    assert text_a == text_b  # registry order, not request order
    assert "[sec.sql-injection]" in text_a
    assert text_a.index("[sec.sql-injection]") < text_a.index("[sec.xss]")


def test_unknown_lookups_raise():
    with pytest.raises(KeyError):
        DEFAULT_REGISTRY.get_skill("nope")
    with pytest.raises(KeyError):
        DEFAULT_REGISTRY.specialist("nope")
    with pytest.raises(KeyError):
        DEFAULT_REGISTRY.skills_for_role("nope")
    with pytest.raises(KeyError):
        DEFAULT_REGISTRY.prompt_fragments(["nope"])


def test_broken_registry_reports_problems():
    broken = SkillRegistry(
        skills=(
            Skill(id="a", title="A", roles=("developer",), prompt_fragment="x"),
            Skill(id="a", title="A2", roles=("developer",), prompt_fragment="y"),
            Skill(id="b", title="B", roles=("wizard",), prompt_fragment=""),
        ),
        roster=(
            Specialist("s1", "developer", "p", ("a", "missing-skill")),
            Specialist("s2", "developer", "p", ()),
        ),
    )
    problems = broken.validate()
    text = "\n".join(problems)
    assert "duplicate skill id: a" in text
    assert "unknown role wizard" in text
    assert "empty prompt fragment" in text
    assert "unknown skill missing-skill" in text
    assert "carries no skills" in text
