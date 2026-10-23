"""Validate FRIDAY Universe monorepo structure and safe mirroring rules.

This deliberately checks repository/CI wiring, not the behavior of individual
agents. Each standalone agent's CI remains responsible for its own test suite.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

AGENTS = (
    "FRIDAY",
    "Inference",
    "Memora",
    "Stratex",
    "Forge",
    "Cortex",
    "Sentinel",
    "IntelX",
    "Futuris",
    "VyralX",
)
MIRROR_WORKFLOW = Path(".github/workflows/mirror-subrepos.yml")


def mirror_workflow_violations(content: str) -> list[str]:
    """Enforce the explicit monorepo-only policy for the legacy mirror workflow.

    The workflow is intentionally a manual no-op. These checks inspect shell
    commands and event triggers, rather than relying on comments or step names,
    so a future edit cannot quietly re-enable external repository writes.
    """
    problems: list[str] = []

    if re.search(r"(?m)^\s*git\s+push\b[^\n]*--force(?:-with-lease)?\b", content):
        problems.append("mirror workflow must not force-push")
    if re.search(
        r"(?m)^\s*git\s+push\b[^\n]*(?:split-[^\s]*:main|HEAD:refs/heads/main|origin\s+main)\b",
        content,
    ):
        problems.append("mirror workflow must not push directly to a standalone default branch")
    if "secrets.GH_PAT_MIRROR || github.token" in content or re.search(
        r"secrets\.GH_PAT_MIRROR\s*\|\|\s*(?:github\.token|secrets\.GITHUB_TOKEN)",
        content,
    ):
        problems.append("cross-repository writes must not fall back to GITHUB_TOKEN")

    if re.search(r"(?m)^\s*rsync\b[^\n]*--delete\b", content):
        problems.append("mirror workflow must not automatically delete standalone-only files")
    elif re.search(r"(?m)^\s*rsync\b", content):
        problems.append("mirror workflow must not synchronize files into standalone repositories")
    if re.search(r"(?m)^\s*git\s+push\b", content):
        problems.append("mirror workflow must not push to any external repository")
    if re.search(r"(?m)^\s*gh\s+pr\s+create\b", content):
        problems.append("mirror workflow must not create pull requests in external repositories")
    if "secrets.GH_PAT_MIRROR" in content:
        problems.append("monorepo-only mirror workflow must not use external-repository write credentials")

    if re.search(r"(?m)^\s*(?:push|pull_request):\s*(?:#.*)?$", content):
        problems.append("mirror workflow must be manual-only, without automatic push or pull_request triggers")
    if not re.search(r"(?m)^\s*workflow_dispatch:\s*(?:#.*)?$", content):
        problems.append("mirror workflow must expose only a manual workflow_dispatch entry point")

    return problems

def validate_repository(root: Path) -> list[str]:
    """Check agent completeness, embedded CI configs, and workflow YAML syntax."""
    problems: list[str] = []
    root = root.resolve()
    for agent in AGENTS:
        agent_dir = root / agent
        if not agent_dir.is_dir():
            problems.append(f"missing agent directory: {agent}")
            continue
        ci_file = agent_dir / ".github" / "workflows" / "ci.yml"
        if not ci_file.is_file():
            problems.append(f"{agent}: missing standalone CI workflow at {ci_file.relative_to(root)}")
        elif "pull_request:" not in ci_file.read_text(encoding="utf-8"):
            problems.append(f"{agent}: CI workflow does not declare pull_request")
        if not (agent_dir / "tests").is_dir():
            problems.append(f"{agent}: missing tests directory")

    mirror_path = root / MIRROR_WORKFLOW
    if not mirror_path.is_file():
        problems.append(f"missing workflow: {MIRROR_WORKFLOW}")
    else:
        mirror_content = mirror_path.read_text(encoding="utf-8")
        problems.extend(f"{MIRROR_WORKFLOW}: {problem}" for problem in mirror_workflow_violations(mirror_content))

    workflow_files = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    for agent in AGENTS:
        workflow_files.extend(sorted((root / agent / ".github" / "workflows").glob("*.y*ml")))
    for workflow_file in workflow_files:
        try:
            yaml.safe_load(workflow_file.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            problems.append(f"invalid YAML in {workflow_file.relative_to(root)}: {exc}")

    return problems


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = validate_repository(root)
    if problems:
        print(f"Fleet validation failed with {len(problems)} problem(s):")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"Fleet validation passed: {len(AGENTS)} agents, embedded CI workflows, and safe mirror rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
