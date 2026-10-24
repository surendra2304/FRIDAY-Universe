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
    """Enforce a PR-based, non-destructive, safe mirror workflow.

    The workflow may stage monorepo subtree changes into a temporary sync
    branch and open a pull request in the standalone repository. It must never
    push directly to a standalone default branch, force-push, delete
    standalone-only files automatically, or fall back to GITHUB_TOKEN for
    cross-repository writes.
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

    # Direct pushes to external repositories are unsafe; cross-repo writes
    # must go through a pull request on a temporary sync branch.
    push_lines = re.findall(r"(?m)^\s*git\s+push\b[^\n]*", content)
    for line in push_lines:
        # Allow pushes that target a sync branch (literal or variable-based).
        if re.search(r"refs/heads/sync/", line):
            continue
        if re.search(r"HEAD:refs/heads/\$?[A-Za-z_]*SYNC", line):
            continue
        if re.search(r"refs/heads/\$?[A-Za-z_]*SYNC_BRANCH", line):
            continue
        problems.append("mirror workflow must not push directly to any external repository branch")
        break

    if re.search(r"(?m)^\s*gh\s+pr\s+create\b", content) is None:
        problems.append("mirror workflow must open a pull request for cross-repository changes")

    if not re.search(r"(?m)^\s*workflow_dispatch:\s*(?:#.*)?$", content):
        problems.append("mirror workflow must expose only a manual workflow_dispatch entry point")
    if re.search(r"(?m)^\s*(?:push|pull_request):\s*(?:#.*)?$", content):
        problems.append("mirror workflow must be manual-only, without automatic push or pull_request triggers")

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
