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
- (TASK-REL-087) A task in a post-merge state (MERGED, DEPLOYED,
  VERIFIED) must cite the PR that merged it. A MERGED record with
  ``pr: null`` -- or citing a PR that never merged -- used to pass VALID:
  a board PR could flip a task to MERGED with no merged PR behind it and
  CI stayed green. Records created or updated on/after 2026-11-23 (when
  the PR-citation convention starts) are enforced; the 95 MERGED and 80
  DEPLOYED/VERIFIED records that predate it with ``pr: null`` are
  grandfathered while untouched. The "cited PR actually merged" half
  needs a merged-PR list (``--merged-prs`` file, one number per line);
  without it only the null/invalid-citation half is checked.
- (TASK-REL-107) Two evidence gates. A record flipped to a terminal
  state (VERIFIED, CLOSED) on/after the gate's effective date must carry
  an ``evidence_keys`` mapping with all five keys -- diff, CI link,
  deploy proof, live-probe output, non-author verdict -- each a
  non-empty string. A record created on/after the effective date must
  carry a non-empty ``live_proof_route`` field. The effective date is
  2026-11-28, not the landing day: measured on the 2026-11-27 board
  (454 records), 2026-11-27 would put 2 VERIFIED records (TASK-FUT-033,
  TASK-STR-094) under gate 1 and 73 records created that day under
  gate 2, all without the new fields, so the live board would go red
  on landing; with 2026-11-28 zero records are in scope and the board
  stays VALID. Same grandfathering mechanism as REL-087.
"""

from __future__ import annotations

import argparse
import datetime
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
# TASK-REL-087: post-merge states must cite the PR that merged them.
POST_MERGE_STATES = {"MERGED", "DEPLOYED", "VERIFIED"}
# First date the PR-citation convention applies. Records created or
# updated on/after this date must cite a merged PR; earlier records with
# pr: null are grandfathered (95 MERGED + 80 DEPLOYED/VERIFIED on the
# 2026-11-23 board predate the convention).
MERGED_PR_RULE_EFFECTIVE = "2026-11-23"

# TASK-REL-107: terminal-flip evidence gate + new-record live_proof_route.
EVIDENCE_KEYS = (
    "diff",
    "ci_link",
    "deploy_proof",
    "live_probe_output",
    "non_author_verdict",
)
# Terminal states whose flips must carry all five evidence keys.
TERMINAL_STATES = {"VERIFIED", "CLOSED"}
# First date the evidence gate applies. Records created or updated on/after
# this date must carry the five evidence keys when terminal (gate 1), and
# records created on/after it must carry live_proof_route (gate 2).
# Measured on the 2026-11-27 board (454 records): with 2026-11-27 as the
# effective date, 2 VERIFIED records (TASK-FUT-033, TASK-STR-094) lack
# evidence_keys and 73 records created that day lack live_proof_route, so
# the live board would go red on landing; with 2026-11-28, zero records
# are in scope and the board stays VALID. The gate enforces from the next
# day's flips and new records onward. Same grandfathering mechanism as
# REL-087: touching a record (which bumps its updated_at) brings it under
# gate 1, and the fix is adding the five keys.
EVIDENCE_GATE_EFFECTIVE = "2026-11-28"


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


def _record_date(value: Any) -> str | None:
    """Normalise a board ``created_at``/``updated_at`` value to YYYY-MM-DD.

    PyYAML parses ``2026-11-23`` as a date and ``2026-11-23T21:36:00+05:30``
    as a datetime; both (and plain strings) reduce to their first ten
    characters. Anything else (including a missing value) is not a date.
    """
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()[:10]
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return None


def check_board_merged_pr_citations(
    board: dict[str, Any], merged_prs: set[int] | None = None
) -> None:
    """Fail when a post-merge task does not cite a merged PR (TASK-REL-087).

    Two defect classes, both of which previously passed VALID:
    - MERGED/DEPLOYED/VERIFIED with ``pr: null`` (or a non-integer, or a
      non-positive number): no merged PR behind the flip at all.
    - citing a PR number that is not in ``merged_prs`` (when the merged-PR
      list is supplied): the cited PR is open, closed-unmerged, or does
      not exist. Without the list this half cannot be checked offline and
      is skipped; the null-citation half always applies.

    Only records created or updated on/after MERGED_PR_RULE_EFFECTIVE are
    enforced. Earlier records predate the PR-citation convention and are
    grandfathered while untouched -- touching one (which bumps its
    ``updated_at``) brings it under the rule, and the fix is a one-line
    ``pr`` citation.
    """
    tasks = board.get("tasks")
    if not isinstance(tasks, list):
        return
    errors: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = task.get("status")
        if status not in POST_MERGE_STATES:
            continue
        created = _record_date(task.get("created_at"))
        updated = _record_date(task.get("updated_at"))
        in_scope = (
            created is not None and created >= MERGED_PR_RULE_EFFECTIVE
        ) or (updated is not None and updated >= MERGED_PR_RULE_EFFECTIVE)
        if not in_scope:
            continue
        task_id = task.get("id")
        pr = task.get("pr")
        if isinstance(pr, bool) or not isinstance(pr, int) or pr <= 0:
            errors.append(
                f"{task_id}: status {status} with null/invalid pr citation "
                "(must cite the merged PR number)"
            )
            continue
        if merged_prs is not None and pr not in merged_prs:
            errors.append(
                f"{task_id}: cites PR #{pr} which is not in the merged-PR list"
            )
    if errors:
        raise RegistryValidationError(
            "WORK_BOARD.yaml: post-merge tasks without a merged PR citation: "
            + "; ".join(errors)
        )


def check_board_evidence_keys(board: dict[str, Any]) -> None:
    """Fail when a terminal record lacks any of the five evidence keys (TASK-REL-107).

    A record in a terminal state (VERIFIED, CLOSED) created or updated
    on/after EVIDENCE_GATE_EFFECTIVE must carry an ``evidence_keys``
    mapping with all five keys -- diff, ci_link, deploy_proof,
    live_probe_output, non_author_verdict -- each a non-empty string.
    Earlier records are grandfathered while untouched; touching one
    (which bumps its ``updated_at``) brings it under the rule, and the
    fix is adding the five keys.
    """
    tasks = board.get("tasks")
    if not isinstance(tasks, list):
        return
    errors: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = task.get("status")
        if status not in TERMINAL_STATES:
            continue
        created = _record_date(task.get("created_at"))
        updated = _record_date(task.get("updated_at"))
        in_scope = (
            created is not None and created >= EVIDENCE_GATE_EFFECTIVE
        ) or (updated is not None and updated >= EVIDENCE_GATE_EFFECTIVE)
        if not in_scope:
            continue
        task_id = task.get("id")
        keys = task.get("evidence_keys")
        if not isinstance(keys, dict):
            errors.append(
                f"{task_id}: status {status} without an evidence_keys mapping "
                "(must carry diff, ci_link, deploy_proof, live_probe_output, "
                "non_author_verdict)"
            )
            continue
        missing = [
            key
            for key in EVIDENCE_KEYS
            if not isinstance(keys.get(key), str) or not keys.get(key).strip()
        ]
        if missing:
            errors.append(
                f"{task_id}: status {status} missing evidence keys: "
                + ", ".join(missing)
            )
    if errors:
        raise RegistryValidationError(
            "WORK_BOARD.yaml: terminal records without all five evidence keys: "
            + "; ".join(errors)
        )


def check_board_live_proof_route(board: dict[str, Any]) -> None:
    """Fail when a new record lacks a live_proof_route field (TASK-REL-107).

    Records created on/after EVIDENCE_GATE_EFFECTIVE must carry a
    non-empty ``live_proof_route`` string naming how the task is proven
    against the live service. Earlier records are grandfathered: the rule
    is about new records, so only ``created_at`` brings a record under it.
    """
    tasks = board.get("tasks")
    if not isinstance(tasks, list):
        return
    errors: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        created = _record_date(task.get("created_at"))
        if created is None or created < EVIDENCE_GATE_EFFECTIVE:
            continue
        task_id = task.get("id")
        route = task.get("live_proof_route")
        if not isinstance(route, str) or not route.strip():
            errors.append(
                f"{task_id}: created {created} without a live_proof_route "
                "(must name the live-proof route)"
            )
    if errors:
        raise RegistryValidationError(
            "WORK_BOARD.yaml: new records without a live_proof_route: "
            + "; ".join(errors)
        )


def load_merged_prs(path: Path) -> set[int]:
    """Load a merged-PR list: one PR number per line, blanks ignored."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise RegistryValidationError(f"Merged-PR list not found: {path}") from exc
    numbers: set[int] = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            numbers.add(int(line))
        except ValueError as exc:
            raise RegistryValidationError(
                f"Merged-PR list {path}: not a PR number: {line!r}"
            ) from exc
    if not numbers:
        raise RegistryValidationError(
            f"Merged-PR list {path} is empty; cannot verify PR citations "
            "against an empty merged set (refusing to fail every citation)"
        )
    return numbers


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistryValidationError(message)


def validate_registry(merged_prs: set[int] | None = None) -> list[str]:
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
    check_board_merged_pr_citations(board, merged_prs)
    check_board_evidence_keys(board)
    check_board_live_proof_route(board)

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the FRIDAY Universe collaboration registry."
    )
    parser.add_argument(
        "--merged-prs",
        type=Path,
        default=None,
        help="File with one merged PR number per line; when given, a "
        "post-merge task must cite a PR in this list (TASK-REL-087). "
        "Without it only the null/invalid-citation half is checked.",
    )
    args = parser.parse_args(argv)
    merged_prs: set[int] | None = None
    if args.merged_prs is not None:
        try:
            merged_prs = load_merged_prs(args.merged_prs)
        except RegistryValidationError as exc:
            print(f"COLLABORATION REGISTRY INVALID: {exc}", file=sys.stderr)
            return 1
    try:
        validate_registry(merged_prs)
    except RegistryValidationError as exc:
        print(f"COLLABORATION REGISTRY INVALID: {exc}", file=sys.stderr)
        return 1

    print("COLLABORATION REGISTRY VALID")
    print(f"Contributor roster: {len(load_yaml(COLLAB / 'TEAM_ROSTER.yaml')['collaborators'])}")
    print(f"Task records: {len(load_yaml(COLLAB / 'WORK_BOARD.yaml')['tasks'])}")
    print(f"File claims: {len(load_yaml(COLLAB / 'FILE_OWNERSHIP.yaml')['claims'])}")
    print(f"File conflicts: {len(load_yaml(COLLAB / 'FILE_OWNERSHIP.yaml').get('conflicts_to_resolve', []))}")
    print("Strict YAML checks: no duplicate keys; per-task evidence counts match raw text")
    print(
        "Post-merge PR citations: MERGED/DEPLOYED/VERIFIED records created or "
        f"updated on/after {MERGED_PR_RULE_EFFECTIVE} cite a merged PR"
        + (
            f" (verified against {len(merged_prs)} merged PRs)"
            if merged_prs is not None
            else " (no merged-PR list supplied; open/unmerged citations not checked)"
        )
    )
    print(
        "Evidence gate (TASK-REL-107): terminal (VERIFIED/CLOSED) records "
        f"created or updated on/after {EVIDENCE_GATE_EFFECTIVE} carry all "
        "five evidence keys (diff, ci_link, deploy_proof, live_probe_output, "
        "non_author_verdict); records created on/after "
        f"{EVIDENCE_GATE_EFFECTIVE} carry a live_proof_route"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
