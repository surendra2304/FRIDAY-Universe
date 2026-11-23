#!/usr/bin/env python3
"""Tests for scripts/validate_collaboration.py (TASK-REL-069).

Standalone runner -- no pytest dependency. Run from the repository root:

    python3 scripts/tests/test_validate_collaboration.py

Each case builds a scratch copy of the live registry files in a temp
directory and runs the real validator against it, so the fixtures are
the real board/roster/ownership files plus one deliberate break.

Cases:
  A. Pristine registry -> VALID, exit 0.
  B. Duplicate ``evidence:`` key in one board record -> INVALID, exit 1.
  C. Duplicate (non-evidence) key in TEAM_ROSTER.yaml -> INVALID, exit 1.
  D. Duplicate (non-evidence) key in FILE_OWNERSHIP.yaml -> INVALID, exit 1.
  E. Evidence-count diff, in-process: a parse whose per-record evidence
     count differs from the raw text fails even with duplicate-key
     detection bypassed (defence in depth).
  F. MERGED-with-null-pr (TASK-REL-087): flipping the TASK-REL-087 record
     to MERGED while its ``pr`` stays null fails, exit 1.
  G. MERGED-with-unmerged-pr (TASK-REL-087): flipping it to MERGED citing
     PR 999999, with a merged-PR list built from every PR the live board
     cites, fails -- the cited PR is not in the merged set.
  H. Positive control: the same flip citing PR 1372 (in the merged-PR
     list) passes, exit 0.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate_collaboration.py"

REGISTRY_FILES = (
    "docs/MASTER_PLAN.md",
    "docs/handoff.md",
    "docs/ARCHITECTURE_AS_BUILT.md",
    "docs/collaboration/README.md",
    "docs/collaboration/TEAM_ROSTER.yaml",
    "docs/collaboration/WORK_BOARD.yaml",
    "docs/collaboration/FILE_OWNERSHIP.yaml",
    "docs/collaboration/ACTIVITY_LOG.md",
    "docs/collaboration/DECISIONS.md",
    "docs/collaboration/HANDOFFS.md",
    "docs/collaboration/TASK_TEMPLATE.yaml",
    "docs/collaboration/HANDOFF_TEMPLATE.md",
)


def build_tree(tmp: Path) -> Path:
    """Copy the live registry files into a scratch repo-shaped tree."""
    for rel in REGISTRY_FILES:
        src = ROOT / rel
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    validator_dst = tmp / "scripts" / "validate_collaboration.py"
    validator_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(VALIDATOR, validator_dst)
    return tmp


def run_validator(tree: Path, args: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/validate_collaboration.py", *args],
        cwd=tree,
        capture_output=True,
        text=True,
        timeout=300,
    )


def set_rel087_merged(board_path: Path, pr: str | None) -> None:
    """Flip the TASK-REL-087 record to MERGED with the given ``pr`` line.

    Anchored on the record's own segment so edits to other records do not
    move it. ``pr=None`` keeps the live ``pr: null`` (case F); otherwise
    the record cites that PR number (cases G/H). The record was created
    2026-11-23, so the REL-087 rule applies to it either way.
    """
    text = board_path.read_text(encoding="utf-8")
    start = text.index("  - id: TASK-REL-087\n")
    next_record = text.find("\n  - id: ", start + 1)
    end = len(text) if next_record == -1 else next_record + 1
    segment = text[start:end]
    assert segment.count("    status: CLAIMED\n") == 1, "REL-087 status line not found"
    segment = segment.replace("    status: CLAIMED\n", "    status: MERGED\n", 1)
    if pr is not None:
        assert segment.count("    pr: null\n") == 1, "REL-087 pr line not found"
        segment = segment.replace("    pr: null\n", f"    pr: {pr}\n", 1)
    board_path.write_text(text[:start] + segment + text[end:], encoding="utf-8")


def live_merged_prs(tree: Path) -> set[int]:
    """Every PR number the live board's in-scope post-merge records cite.

    Reuses the validator's own scope rule, so the fixture set is exactly
    "the PRs the board already treats as merged" -- the only bad citation
    in cases G/H is the injected one.
    """
    module = load_validator_module(tree)
    board = yaml.safe_load((tree / "docs/collaboration/WORK_BOARD.yaml").read_text(encoding="utf-8"))
    cited: set[int] = set()
    for task in board.get("tasks", []):
        if not isinstance(task, dict):
            continue
        if task.get("status") not in module.POST_MERGE_STATES:
            continue
        created = module._record_date(task.get("created_at"))
        updated = module._record_date(task.get("updated_at"))
        in_scope = (
            created is not None and created >= module.MERGED_PR_RULE_EFFECTIVE
        ) or (updated is not None and updated >= module.MERGED_PR_RULE_EFFECTIVE)
        if not in_scope:
            continue
        pr = task.get("pr")
        if isinstance(pr, int) and not isinstance(pr, bool) and pr > 0:
            cited.add(pr)
    return cited


def inject_duplicate_evidence_key(board_path: Path) -> None:
    """Add a second ``evidence:`` block to the TASK-REL-069 record.

    Mirrors the PR #1241 defect: the plain parse keeps only the second
    block and drops the real evidence while reporting VALID. The
    injection is anchored on the record's own ``blockers:`` line so it
    survives edits to the record's other fields.
    """
    text = board_path.read_text(encoding="utf-8")
    start = text.index("  - id: TASK-REL-069\n")
    next_record = text.find("\n  - id: ", start + 1)
    end = len(text) if next_record == -1 else next_record + 1
    segment = text[start:end]
    assert segment.count("    blockers: []\n") == 1, "REL-069 blockers line not found"
    duplicate = (
        "    evidence:\n"
        "    - 'DUPLICATE-KEY FIXTURE - this line must never survive a parse silently'\n"
    )
    segment = segment.replace("    blockers: []\n", duplicate + "    blockers: []\n", 1)
    board_path.write_text(text[:start] + segment + text[end:], encoding="utf-8")


def inject_duplicate_key(path: Path, anchor_line: str, duplicate_line: str) -> None:
    """Insert a duplicate mapping key directly after its first occurrence."""
    text = path.read_text(encoding="utf-8")
    assert text.count(anchor_line) >= 1, f"anchor not found in {path.name}: {anchor_line!r}"
    path.write_text(text.replace(anchor_line, anchor_line + duplicate_line, 1), encoding="utf-8")


def load_validator_module(tree: Path):
    spec = importlib.util.spec_from_file_location(
        "validate_collaboration_under_test",
        tree / "scripts" / "validate_collaboration.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_a_pristine() -> None:
    with tempfile.TemporaryDirectory(prefix="rel069-valid-") as tmp:
        result = run_validator(build_tree(Path(tmp)))
    assert result.returncode == 0, f"pristine registry must be VALID:\n{result.stderr}"
    assert "COLLABORATION REGISTRY VALID" in result.stdout
    print("A. pristine registry -> VALID (exit 0)")


def case_b_duplicate_evidence_key() -> None:
    with tempfile.TemporaryDirectory(prefix="rel069-dup-evidence-") as tmp:
        tree = build_tree(Path(tmp))
        inject_duplicate_evidence_key(tree / "docs/collaboration/WORK_BOARD.yaml")
        result = run_validator(tree)
    assert result.returncode == 1, f"duplicate evidence: key must FAIL:\n{result.stdout}"
    assert "duplicate key 'evidence'" in result.stderr, result.stderr
    print("B. duplicate evidence: key -> INVALID (exit 1):", result.stderr.strip().split(": ", 1)[-1][:120])


def case_c_duplicate_roster_key() -> None:
    with tempfile.TemporaryDirectory(prefix="rel069-dup-roster-") as tmp:
        tree = build_tree(Path(tmp))
        roster = tree / "docs/collaboration/TEAM_ROSTER.yaml"
        inject_duplicate_key(
            roster,
            '  - id: "human_surendra"\n',
            '    id: "human_surendra"\n',
        )
        result = run_validator(tree)
    assert result.returncode == 1, f"duplicate roster key must FAIL:\n{result.stdout}"
    assert "duplicate key 'id'" in result.stderr, result.stderr
    print("C. duplicate roster key -> INVALID (exit 1)")


def case_d_duplicate_ownership_key() -> None:
    with tempfile.TemporaryDirectory(prefix="rel069-dup-ownership-") as tmp:
        tree = build_tree(Path(tmp))
        ownership = tree / "docs/collaboration/FILE_OWNERSHIP.yaml"
        inject_duplicate_key(
            ownership,
            "  - path: FRIDAY/ui/components/VoiceCall.tsx\n",
            "    path: FRIDAY/ui/components/VoiceCall.tsx\n",
        )
        result = run_validator(tree)
    assert result.returncode == 1, f"duplicate ownership key must FAIL:\n{result.stdout}"
    assert "duplicate key 'path'" in result.stderr, result.stderr
    print("D. duplicate ownership key -> INVALID (exit 1)")


def case_e_evidence_count_diff() -> None:
    """Diff check alone: raw text 3 evidence items, parsed board 1."""
    with tempfile.TemporaryDirectory(prefix="rel069-diff-") as tmp:
        tree = build_tree(Path(tmp))
        module = load_validator_module(tree)
        board_text = (
            "tasks:\n"
            "  - id: TASK-FIXTURE\n"
            "    evidence:\n"
            "    - 'first block, item one'\n"
            "    - 'first block, item two'\n"
            "    evidence:\n"
            "    - 'second block, item three'\n"
        )
        board_path = tree / "fixture-board.yaml"
        board_path.write_text(board_text, encoding="utf-8")
        parsed = yaml.safe_load(board_text)  # plain parse: keeps only the last block
        assert len(parsed["tasks"][0]["evidence"]) == 1
        try:
            module.check_board_evidence_counts(board_path, parsed)
        except module.RegistryValidationError as exc:
            assert "TASK-FIXTURE" in str(exc) and "3 evidence items" in str(exc), str(exc)
            print("E. evidence-count diff (3 raw vs 1 parsed) -> INVALID:", str(exc)[:120])
            return
        raise AssertionError("evidence-count diff missed the mismatch")


def case_f_merged_null_pr() -> None:
    with tempfile.TemporaryDirectory(prefix="rel087-null-pr-") as tmp:
        tree = build_tree(Path(tmp))
        set_rel087_merged(tree / "docs/collaboration/WORK_BOARD.yaml", None)
        result = run_validator(tree)
    assert result.returncode == 1, f"MERGED-with-null-pr must FAIL:\n{result.stdout}"
    assert "TASK-REL-087" in result.stderr and "null/invalid pr citation" in result.stderr, result.stderr
    print("F. MERGED-with-null-pr -> INVALID (exit 1):", result.stderr.strip().split(": ", 1)[-1][:120])


def case_g_merged_unmerged_pr() -> None:
    with tempfile.TemporaryDirectory(prefix="rel087-unmerged-pr-") as tmp:
        tree = build_tree(Path(tmp))
        merged = live_merged_prs(tree)  # pristine board, before the mutation
        assert 999999 not in merged
        set_rel087_merged(tree / "docs/collaboration/WORK_BOARD.yaml", "999999")
        prs_file = tree / "merged_prs.txt"
        prs_file.write_text("\n".join(str(n) for n in sorted(merged)) + "\n", encoding="utf-8")
        result = run_validator(tree, ("--merged-prs", "merged_prs.txt"))
    assert result.returncode == 1, f"MERGED-with-unmerged-pr must FAIL:\n{result.stdout}"
    assert "TASK-REL-087" in result.stderr and "not in the merged-PR list" in result.stderr, result.stderr
    print("G. MERGED citing unmerged PR 999999 -> INVALID (exit 1):", result.stderr.strip().split(": ", 1)[-1][:120])


def case_h_merged_cited_pr_ok() -> None:
    with tempfile.TemporaryDirectory(prefix="rel087-merged-pr-ok-") as tmp:
        tree = build_tree(Path(tmp))
        merged = live_merged_prs(tree)  # pristine board, before the mutation
        assert 1372 in merged
        set_rel087_merged(tree / "docs/collaboration/WORK_BOARD.yaml", "1372")
        prs_file = tree / "merged_prs.txt"
        prs_file.write_text("\n".join(str(n) for n in sorted(merged)) + "\n", encoding="utf-8")
        result = run_validator(tree, ("--merged-prs", "merged_prs.txt"))
    assert result.returncode == 0, f"MERGED citing a merged PR must be VALID:\n{result.stderr}"
    assert "COLLABORATION REGISTRY VALID" in result.stdout
    assert "verified against" in result.stdout and "merged PRs" in result.stdout, result.stdout
    print("H. MERGED citing merged PR 1372 -> VALID (exit 0)")


def main() -> int:
    cases = (
        case_a_pristine,
        case_b_duplicate_evidence_key,
        case_c_duplicate_roster_key,
        case_d_duplicate_ownership_key,
        case_e_evidence_count_diff,
        case_f_merged_null_pr,
        case_g_merged_unmerged_pr,
        case_h_merged_cited_pr_ok,
    )
    for case in cases:
        case()
    print(f"All {len(cases)} validate_collaboration tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
