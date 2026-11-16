"""
Sentinel/app/services/defensive_skills.py — Defensive-only skill pack loader.

TASK-IG2-SEN-01: cherry-picks DEFENSIVE skills (detection, hardening,
incident response, threat hunting over the fleet's own telemetry,
vulnerability management, IAM hygiene, AI-security defence) from the
community cybersecurity-skills library into Sentinel's skill set, in the
agentskills.io SKILL.md format under ``Sentinel/skills/defensive/``.

Provenance / licence: adapted from
https://github.com/mukul975/Anthropic-Cybersecurity-Skills (Apache-2.0) by
Mahipal Jangra (mukul975). CAVEAT: despite the repository name, that is an
independent community project and is NOT affiliated with Anthropic PBC.
See ``Sentinel/skills/defensive/NOTICE.md`` for the full attribution and
exclusion policy.

Policy enforcement (fail-closed): this loader refuses — by raising
``DefensiveSkillPolicyError`` — any skill whose tier is not exactly
``defensive``, whose name is on the exclusion list, or whose domain is an
excluded offensive category. Offensive and dual-use skills have no place
in an always-on fleet agent, so a stray file placed in the pack directory
fails the whole load loudly instead of silently joining the skill set.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# Tiers that must never enter Sentinel's always-on skill set.
EXCLUDED_TIERS: frozenset[str] = frozenset({"offensive", "dual-use"})

# Offensive / dual-use categories from the source library, excluded by
# policy (see NOTICE.md). A skill whose domain matches one of these is
# refused even if its frontmatter claims tier=defensive.
EXCLUDED_CATEGORIES: frozenset[str] = frozenset({
    "red-team", "red-team-operations", "adversary-emulation", "c2",
    "phishing-simulation", "social-engineering", "exploitation",
    "payload-development", "credential-theft", "credential-access-attack",
    "defense-evasion", "malware-development", "wireless-attacks",
    "physical-intrusion", "offensive-osint", "humint", "sigint",
})

# Specific well-known offensive skill names in the source library's style;
# refused by name regardless of declared tier/domain.
EXCLUDED_SKILL_NAMES: frozenset[str] = frozenset({
    "phishing-simulation", "red-team-c2-operations", "exploit-development",
    "credential-dumping", "password-spraying-attack", "malware-development",
    "evasion-techniques", "privilege-escalation-attack",
})

DEFAULT_PACK_ROOT = Path(__file__).resolve().parents[2] / "skills" / "defensive"


class DefensiveSkillPolicyError(ValueError):
    """Raised when a skill file violates the defensive-only policy."""


@dataclass
class DefensiveSkill:
    """One adopted defensive skill, parsed from its SKILL.md."""

    name: str
    description: str
    domain: str
    tier: str
    attack: list[str] = field(default_factory=list)
    csf: list[str] = field(default_factory=list)
    d3fend: list[str] = field(default_factory=list)
    atlas: list[str] = field(default_factory=list)
    workflow: list[str] = field(default_factory=list)
    body: str = ""
    source_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "tier": self.tier,
            "frameworks": {
                "attack": self.attack, "csf": self.csf,
                "d3fend": self.d3fend, "atlas": self.atlas,
            },
            "workflow": self.workflow,
            "source_path": self.source_path,
        }


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the YAML frontmatter of a SKILL.md file.

    Uses PyYAML when available (it is a Sentinel dependency); falls back to
    a minimal parser covering the flat keys and inline lists this pack uses.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        raise DefensiveSkillPolicyError("SKILL.md has no YAML frontmatter")
    raw, body = match.group(1), match.group(2)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            raise DefensiveSkillPolicyError("frontmatter is not a mapping")
        return data, body
    except ImportError:
        pass
    data: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line or line.startswith((" ", "-")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            data[key.strip()] = [
                item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()
            ]
        else:
            data[key.strip()] = value.strip("'\"")
    return data, body


def _extract_workflow(body: str) -> list[str]:
    """Pull the numbered steps out of the body's ``## Workflow`` section."""
    section = re.search(
        r"##\s+Workflow\s*\n(.*?)(?:\n##\s+|\Z)", body, re.DOTALL | re.IGNORECASE
    )
    if not section:
        return []
    steps: list[str] = []
    current: list[str] = []
    for line in section.group(1).splitlines():
        step = re.match(r"^\d+\.\s+(.*)$", line.strip())
        if step:
            if current:
                steps.append(" ".join(current))
            current = [step.group(1)]
        elif current and line.strip():
            current.append(line.strip())
    if current:
        steps.append(" ".join(current))
    return steps


def check_skill_policy(name: str, tier: str, domain: str) -> None:
    """Fail-closed policy gate for one candidate skill."""
    if tier != "defensive":
        raise DefensiveSkillPolicyError(
            f"skill {name!r} has tier {tier!r}; only 'defensive' is permitted "
            f"(excluded tiers: {sorted(EXCLUDED_TIERS)})"
        )
    if name in EXCLUDED_SKILL_NAMES:
        raise DefensiveSkillPolicyError(
            f"skill {name!r} is on the offensive/dual-use exclusion list"
        )
    if domain in EXCLUDED_CATEGORIES:
        raise DefensiveSkillPolicyError(
            f"skill {name!r} is in excluded category {domain!r}"
        )


def load_skill_file(path: Path) -> DefensiveSkill:
    """Parse and policy-check one SKILL.md file."""
    frontmatter, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    name = str(frontmatter.get("name", "")).strip()
    tier = str(frontmatter.get("tier", "")).strip().lower()
    domain = str(frontmatter.get("domain", "")).strip().lower()
    if not name:
        raise DefensiveSkillPolicyError(f"{path}: frontmatter has no name")
    check_skill_policy(name, tier, domain)

    def _str_list(key: str) -> list[str]:
        value = frontmatter.get(key) or []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    return DefensiveSkill(
        name=name,
        description=str(frontmatter.get("description", "")).strip(),
        domain=domain,
        tier=tier,
        attack=_str_list("attack"),
        csf=_str_list("csf"),
        d3fend=_str_list("d3fend"),
        atlas=_str_list("atlas"),
        workflow=_extract_workflow(body),
        body=body,
        source_path=str(path),
    )


class DefensiveSkillPack:
    """The loaded, policy-verified defensive skill set."""

    def __init__(self, skills: Iterable[DefensiveSkill], root: Path) -> None:
        self.skills: dict[str, DefensiveSkill] = {s.name: s for s in skills}
        self.root = root

    def __len__(self) -> int:
        return len(self.skills)

    def get(self, name: str) -> DefensiveSkill | None:
        return self.skills.get(name)

    def by_domain(self, domain: str) -> list[DefensiveSkill]:
        return [s for s in self.skills.values() if s.domain == domain]

    def search(self, query: str) -> list[DefensiveSkill]:
        """Substring search over name, description, domain and workflow."""
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        if not terms:
            return []
        scored: list[tuple[int, DefensiveSkill]] = []
        for skill in self.skills.values():
            haystack = " ".join([
                skill.name.replace("-", " "), skill.description, skill.domain,
                " ".join(skill.workflow),
            ]).lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                scored.append((hits, skill))
        scored.sort(key=lambda pair: (-pair[0], pair[1].name))
        return [skill for _, skill in scored]

    def audit(self) -> dict[str, Any]:
        """Self-audit proving the pack honours the defensive-only policy."""
        tiers = {s.tier for s in self.skills.values()}
        return {
            "skill_count": len(self.skills),
            "tiers_present": sorted(tiers),
            "all_defensive": tiers == {"defensive"},
            "domains": sorted({s.domain for s in self.skills.values()}),
            "excluded_tiers": sorted(EXCLUDED_TIERS),
            "excluded_categories": sorted(EXCLUDED_CATEGORIES),
            "source": "https://github.com/mukul975/Anthropic-Cybersecurity-Skills",
            "license": "Apache-2.0",
            "affiliation_caveat": (
                "Independent community project by Mahipal Jangra (mukul975); "
                "NOT affiliated with Anthropic PBC."
            ),
        }


def load_defensive_skill_pack(root: Path | None = None) -> DefensiveSkillPack:
    """Load every SKILL.md under the pack root, enforcing the policy.

    Fails closed: any policy violation raises and no partial pack is
    returned. When a manifest.json sits beside the skills, the loaded set
    must match its ``included`` list exactly.
    """
    pack_root = Path(root) if root is not None else DEFAULT_PACK_ROOT
    if not pack_root.is_dir():
        raise DefensiveSkillPolicyError(f"skill pack directory missing: {pack_root}")
    skills = [
        load_skill_file(skill_md)
        for skill_md in sorted(pack_root.glob("*/SKILL.md"))
    ]
    manifest_path = pack_root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = {entry["name"] for entry in manifest.get("included", [])}
        loaded = {s.name for s in skills}
        if declared != loaded:
            raise DefensiveSkillPolicyError(
                f"manifest/pack mismatch: declared-only={sorted(declared - loaded)}, "
                f"loaded-only={sorted(loaded - declared)}"
            )
        for entry in manifest.get("included", []):
            check_skill_policy(
                str(entry.get("name", "")), str(entry.get("tier", "")).lower(),
                str(entry.get("domain", "")).lower(),
            )
    return DefensiveSkillPack(skills, pack_root)
