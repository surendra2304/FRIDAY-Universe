#!/usr/bin/env python3
"""Validate FRIDAY Universe's shared multi-AI collaboration registry.

Strictness notes (TASK-REL-069):
- PyYAML's default loader silently keeps the LAST value for a repeated
  mapping key. PR #1241 carried a duplicate ``evidence:`` key that the
  parser AND this validator swallowed, dropping evidence while reporting
  VALID. Every YAML file loaded here is therefore also scanned at the
  node-tree level (``yaml.compose`` preserves duplicate keys) and any
  duplicate mapping key fails validation.
- As a second line of defence, the per-task ``evidence`` item counts in
  the parsed board are diffed against the raw-text counts taken from the
  node tree. A parse that silently drops an evidence block fails even if
  the duplicate-key scan were ever bypassed.
"""

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
    "muse_ai",
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


def _collect_duplicate_keys(node: Any, rel_path: str, errors: list[str]) -> None:
    """Recursively record duplicate mapping keys found in a YAML node tree.

    ``yaml.compose`` keeps every key node, unlike ``yaml.safe_load`` which
    silently drops all but the last value for a repeated key. A key is
    identified by its (tag, scalar value): ``1`` and ``"1"`` are different
    keys to the parser, so they are different here too.
    """
    if isinstance(node, yaml.MappingNode):
        seen: dict[tuple[str, str], int] = {}
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode):
                identity = (key_node.tag, key_node.value)
                line = key_node.start_mark.line + 1
                if identity in seen:
                    errors.append(
                        f"{rel_path}: duplicate key {key_node.value!r} "
                        f"at line {line} (first occurrence at line {seen[identity]})"
                    )
                else:
                    seen[identity] = line
            _collect_duplicate_keys(value_node, rel_path, errors)
    elif isinstance(node, yaml.SequenceNode):
        for item_node in node.value:
            _collect_duplicate_keys(item_node, rel_path, errors)


def load_yaml(path: Path) -> dict[str, Any]:
    rel_path = str(path.relative_to(ROOT))
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RegistryValidationError(f"Missing required YAML file: {rel_path}") from exc
    try:
        node = yaml.compose(text)
        errors: list[str] = []
        _collect_duplicate_keys(node, rel_path, errors)
        if errors:
            raise RegistryValidationError(
                "Duplicate YAML keys (silently dropped by a plain parse): " + "; ".join(errors)
            )
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RegistryValidationError(f"Invalid YAML in {rel_path}: {exc}") from exc

    if not isinstance(value, dict):
        raise RegistryValidationError(f"{rel_path} must contain a YAML mapping")
    return value


def _raw_evidence_counts(board_path: Path) -> dict[str, int]:
    """Count ``evidence:`` list items per task straight from the raw text.

    The counts come from the YAML node tree, so every ``evidence:`` block
    in the text contributes -- including one a plain parse would drop
    because its key is duplicated.
    """
    text = board_path.read_text(encoding="utf-8")
    root = yaml.compose(text)
    counts: dict[str, int] = {}
    if not isinstance(root, yaml.MappingNode):
        return counts
    tasks_node = None
    for key_node, value_node in root.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == "tasks":
            tasks_node = value_node
            break
    if not isinstance(tasks_node, yaml.SequenceNode):
        return counts
    for task_node in tasks_node.value:
        if not isinstance(task_node, yaml.MappingNode):
            continue
        task_id: str | None = None
        raw_count = 0
        for key_node, value_node in task_node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == "id":
                task_id = value_node.value if isinstance(value_node, yaml.ScalarNode) else None
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == "evidence":
                if isinstance(value_node, yaml.SequenceNode):
                    raw_count += len(value_node.value)
                else:
                    raw_count += 1
        if task_id is not None:
            counts[task_id] = raw_count
    return counts


def check_board_evidence_counts(board_path: Path, board: dict[str, Any]) -> None:
    """Fail when a task's parsed evidence count differs from the raw text.

    A mismatch means the parse silently dropped evidence -- the PR #1241
    defect class -- and the board must not report VALID.
    """
    tasks = board.get("tasks")
    if not isinstance(tasks, list):
        return
    raw_counts = _raw_evidence_counts(board_path)
    mismatches: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or task_id not in raw_counts:
            continue
        evidence = task.get("evidence")
        if isinstance(evidence, list):
            parsed_count = len(evidence)
        elif evidence is None:
            parsed_count = 0
        else:
            parsed_count = 1
        if raw_counts[task_id] != parsed_count:
            mismatches.append(
                f"{task_id}: raw text has {raw_counts[task_id]} evidence items, "
                f"parsed board has {parsed_count}"
            )
    if mismatches:
        raise RegistryValidationError(
            "WORK_BOARD.yaml: evidence counts differ from raw text "
            "(silently dropped evidence?): " + "; ".join(mismatches)
        )


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
    require(authority.get("model") == "claude_lead_coordination",
            "TEAM_ROSTER.yaml: authority model must be claude_lead_coordination")
    require(authority.get("lead_coordinator_id") == "muse_ai",
            "TEAM_ROSTER.yaml: lead_coordinator_id must be muse_ai")

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

    check_board_evidence_counts(COLLAB / "WORK_BOARD.yaml", board)

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
    print("Strict YAML checks: no duplicate keys; per-task evidence counts match raw text")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
