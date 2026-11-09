#!/usr/bin/env python3
"""Validate FRIDAY Universe's shared multi-AI collaboration registry."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
COLLAB = ROOT / "docs" / "collaboration"
ALLOWED_TASK_STATES = {
    "PROPOSED",
    "AVAILABLE",
    "CLAIMED",
    "IN_PROGRESS",
    "BLOCKED",
    "IN_REVIEW",
    "MERGED",
    "DEPLOYED",
    "VERIFIED",
    "CLOSED",
}
REQUIRED_FILES = (
    "README.md",
    "TEAM_ROSTER.yaml",
    "WORK_BOARD.yaml",
    "FILE_OWNERSHIP.yaml",
    "ACTIVITY_LOG.md",
    "DECISIONS.md",
    "HANDOFFS.md",
    "TASK_TEMPLATE.yaml",
    "HANDOFF_TEMPLATE.md",
)
REQUIRED_COLLABORATORS = {
    "human_surendra",
    "claude",
    "chatgpt",
    "grok",
    "zai",
    "vercel_v0",
}
CANONICAL_AGENTS = (
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


class RegistryValidationError(Exception):
    """Raised when the shared collaboration registry is inconsistent."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise RegistryValidationError(f"Missing required YAML file: {path.relative_to(ROOT)}") from exc
    except yaml.YAMLError as exc:
        raise RegistryValidationError(f"Invalid YAML in {path.relative_to(ROOT)}: {exc}") from exc

    if not isinstance(value, dict):
        raise RegistryValidationError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistryValidationError(message)


def validate_registry() -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = COLLAB / relative
        if not path.is_file():
            errors.append(f"Missing required collaboration file: docs/collaboration/{relative}")

    if errors:
        return errors

    roster = load_yaml(COLLAB / "TEAM_ROSTER.yaml")
    board = load_yaml(COLLAB / "WORK_BOARD.yaml")
    ownership = load_yaml(COLLAB / "FILE_OWNERSHIP.yaml")

    collaborators = roster.get("collaborators")
    require(isinstance(collaborators, list), "TEAM_ROSTER.yaml: collaborators must be a list")

    collaborator_ids: list[str] = []
    for index, person in enumerate(collaborators):
        require(isinstance(person, dict), f"TEAM_ROSTER.yaml: collaborator {index} must be a mapping")
        collaborator_id = person.get("id")
        require(isinstance(collaborator_id, str) and collaborator_id.strip(),
                f"TEAM_ROSTER.yaml: collaborator {index} has no valid id")
        collaborator_ids.append(collaborator_id)

    require(len(collaborator_ids) == len(set(collaborator_ids)),
            "TEAM_ROSTER.yaml: collaborator IDs must be unique")
    missing_people = REQUIRED_COLLABORATORS - set(collaborator_ids)
    require(not missing_people,
            f"TEAM_ROSTER.yaml: missing required contributors: {sorted(missing_people)}")

    authority = roster.get("authority", {})
    require(isinstance(authority, dict), "TEAM_ROSTER.yaml: authority must be a mapping")
    owner_id = authority.get("project_owner_id")
    require(owner_id in collaborator_ids,
            "TEAM_ROSTER.yaml: project_owner_id must exist in collaborators")
    require(authority.get("no_permanent_ai_hierarchy") is True,
            "TEAM_ROSTER.yaml: no_permanent_ai_hierarchy must be true")

    board_tasks = board.get("tasks")
    require(isinstance(board_tasks, list), "WORK_BOARD.yaml: tasks must be a list")
    task_ids: list[str] = []
    for index, task in enumerate(board_tasks):
        require(isinstance(task, dict), f"WORK_BOARD.yaml: task {index} must be a mapping")
        task_id = task.get("id")
        require(isinstance(task_id, str) and task_id.strip(),
                f"WORK_BOARD.yaml: task {index} has no valid id")
        task_ids.append(task_id)
        state = task.get("status")
        require(state in ALLOWED_TASK_STATES,
                f"WORK_BOARD.yaml: {task_id} has invalid status {state!r}")
        owner = task.get("owner")
        require(owner is None or owner in collaborator_ids,
                f"WORK_BOARD.yaml: {task_id} owner {owner!r} is not registered")
        require(isinstance(task.get("title"), str) and task["title"].strip(),
                f"WORK_BOARD.yaml: {task_id} has no title")
        require(isinstance(task.get("next_action"), str) and task["next_action"].strip(),
                f"WORK_BOARD.yaml: {task_id} has no next_action")
        require(isinstance(task.get("files", []), list),
                f"WORK_BOARD.yaml: {task_id} files must be a list")

    require(len(task_ids) == len(set(task_ids)),
            "WORK_BOARD.yaml: task IDs must be unique")

    claims = ownership.get("claims")
    require(isinstance(claims, list), "FILE_OWNERSHIP.yaml: claims must be a list")
    claim_paths: list[str] = []
    for index, claim in enumerate(claims):
        require(isinstance(claim, dict), f"FILE_OWNERSHIP.yaml: claim {index} must be a mapping")
        path = claim.get("path")
        require(isinstance(path, str) and path.strip(),
                f"FILE_OWNERSHIP.yaml: claim {index} has no path")
        claim_paths.append(path)
        require(isinstance(claim.get("prs", []), list),
                f"FILE_OWNERSHIP.yaml: {path} prs must be a list")
        require(isinstance(claim.get("branches", []), list),
                f"FILE_OWNERSHIP.yaml: {path} branches must be a list")
    require(len(claim_paths) == len(set(claim_paths)),
            "FILE_OWNERSHIP.yaml: each path must have one consolidated claim record")

    conflict_ids: list[str] = []
    conflicts = ownership.get("conflicts_to_resolve", [])
    require(isinstance(conflicts, list),
            "FILE_OWNERSHIP.yaml: conflicts_to_resolve must be a list")
    for index, conflict in enumerate(conflicts):
        require(isinstance(conflict, dict),
                f"FILE_OWNERSHIP.yaml: conflict {index} must be a mapping")
        conflict_id = conflict.get("id")
        require(isinstance(conflict_id, str) and conflict_id.strip(),
                f"FILE_OWNERSHIP.yaml: conflict {index} has no id")
        conflict_ids.append(conflict_id)
        paths = conflict.get("files")
        require(isinstance(paths, list) and paths,
                f"FILE_OWNERSHIP.yaml: {conflict_id} must list affected files")
        missing_paths = set(paths) - set(claim_paths)
        require(not missing_paths,
                f"FILE_OWNERSHIP.yaml: {conflict_id} references unregistered paths {sorted(missing_paths)}")
    require(len(conflict_ids) == len(set(conflict_ids)),
            "FILE_OWNERSHIP.yaml: conflict IDs must be unique")

    master_plan = ROOT / "docs" / "MASTER_PLAN.md"
    handoff = ROOT / "docs" / "handoff.md"
    architecture = ROOT / "docs" / "ARCHITECTURE_AS_BUILT.md"
    for path in (master_plan, handoff, architecture):
        require(path.is_file(), f"Missing central project document: {path.relative_to(ROOT)}")

    master_text = master_plan.read_text(encoding="utf-8")
    for agent in CANONICAL_AGENTS:
        require(agent in master_text,
                f"MASTER_PLAN.md does not contain canonical agent {agent}")
    require("TASK-COLLAB-001" in master_text,
            "MASTER_PLAN.md must track TASK-COLLAB-001")
    require("issues/35" in master_text or "issue #35" in master_text,
            "MASTER_PLAN.md must reference the shared GitHub claim hub (#35)")

    readme_text = (COLLAB / "README.md").read_text(encoding="utf-8")
    require("issues/35" in readme_text,
            "docs/collaboration/README.md must reference GitHub claim hub #35")

    return errors


def main() -> int:
    try:
        validate_registry()
    except RegistryValidationError as exc:
        print(f"COLLABORATION REGISTRY INVALID: {exc}", file=sys.stderr)
        return 1

    print("COLLABORATION REGISTRY VALID")
    print(f"Contributor roster: {len(load_yaml(COLLAB / 'TEAM_ROSTER.yaml')['collaborators'])}")
    print(f"Task records: {len(load_yaml(COLLAB / 'WORK_BOARD.yaml')['tasks'])}")
    print(f"File claims: {len(load_yaml(COLLAB / 'FILE_OWNERSHIP.yaml')['claims'])}")
    print(f"File conflicts: {len(load_yaml(COLLAB / 'FILE_OWNERSHIP.yaml').get('conflicts_to_resolve', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
