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
     to MERGED while its ``pr`` stays null fails, exit 1. The record is
     synthesised by the fixture (see ``ensure_rel087_record``): the
     2026-11-27 board shrink archived REL-087 off the live board.
  G. MERGED-with-unmerged-pr (TASK-REL-087): flipping it to MERGED citing
     PR 999999, with a merged-PR list built from every PR the live board
     cites, fails -- the cited PR is not in the merged set.
  H. Positive control: the same flip citing a PR drawn from the
     merged-PR list (``live_merged_prs``) passes, exit 0. The old
     hard-coded PR 1372 is cited 0x on the shrunk live board.
  I. VERIFIED without evidence_keys (TASK-REL-107): a terminal record
     created/updated on the gate's effective date (2026-11-28) with no
     ``evidence_keys`` mapping fails, exit 1.
  J. New record without live_proof_route (TASK-REL-107): a record
     created on the effective date with no ``live_proof_route`` fails,
     exit 1.
  K. Positive control: the same record VERIFIED with all five evidence
     keys and a live_proof_route (and a cited merged PR) passes, exit 0.
  L. Grandfathering: the same record VERIFIED but dated 2026-11-27
     (before the effective date), with neither new field, passes --
     the gates do not reach back before they land.
"""

from __future__ import annotations

import importlib.util
import re
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


def ensure_rel087_record(board_path: Path) -> None:
    """Insert a synthetic TASK-REL-087 record if the live board lacks one.

    The 2026-11-27 board shrink archived REL-087 (and REL-069) off the
    live board, so cases F/G/H synthesise the record in the fixture:
    created 2026-11-23, CLAIMED, pr null, no owner -- the REL-087 rule
    applies to it either way. It is inserted before the
    ``task_id_warnings:`` key, i.e. at the end of the ``tasks:`` list,
    and carries every field the validator requires (title, next_action,
    files) so the pristine-board checks still pass with it present.
    """
    text = board_path.read_text(encoding="utf-8")
    if "  - id: TASK-REL-087\n" in text:
        return
    marker = "\ntask_id_warnings:\n"
    assert text.count(marker) == 1, "task_id_warnings key not found exactly once"
    record = (
        "  - id: TASK-REL-087\n"
        "    title: \"Fixture record for TASK-REL-069 validator tests (synthesised: archived off the live board by the 2026-11-27 shrink)\"\n"
        "    status: CLAIMED\n"
        "    owner: null\n"
        "    branch: null\n"
        "    pr: null\n"
        "    contributors: []\n"
        "    priority: P2\n"
        "    created_at: \"2026-11-23T00:00:00+05:30\"\n"
        "    updated_at: \"2026-11-23T00:00:00+05:30\"\n"
        "    evidence: []\n"
        "    blockers: []\n"
        "    next_action: \"Fixture record for the validator regression tests; not a real task.\"\n"
        "    files: []\n"
    )
    board_path.write_text(text.replace(marker, "\n" + record + "task_id_warnings:\n", 1), encoding="utf-8")


def set_rel087_merged(board_path: Path, pr: str | None) -> None:
    """Flip the TASK-REL-087 record to MERGED with the given ``pr`` line.

    Anchored on the record's own segment so edits to other records do not
    move it. The status and ``pr`` lines are replaced whatever they
    currently say. ``pr=None`` forces ``pr: null`` (case F); otherwise the
    record cites that PR number (cases G/H). The record was created
    2026-11-23, so the REL-087 rule applies to it either way.
    """
    ensure_rel087_record(board_path)
    text = board_path.read_text(encoding="utf-8")
    start = text.index("  - id: TASK-REL-087\n")
    next_record = text.find("\n  - id: ", start + 1)
    end = len(text) if next_record == -1 else next_record + 1
    segment = text[start:end]
    status_match = re.search(r"^    status: \w+\n", segment, re.M)
    assert status_match is not None, "REL-087 status line not found"
    segment = (
        segment[: status_match.start()]
        + "    status: MERGED\n"
        + segment[status_match.end() :]
    )
    pr_match = re.search(r"^    pr: .*\n", segment, re.M)
    assert pr_match is not None, "REL-087 pr line not found"
    new_pr = "null" if pr is None else pr
    segment = (
        segment[: pr_match.start()]
        + f"    pr: {new_pr}\n"
        + segment[pr_match.end() :]
    )
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
    """Add a second ``evidence:`` block to the TASK-INTENT-001 record.

    Mirrors the PR #1241 defect: the plain parse keeps only the second
    block and drops the real evidence while reporting VALID. The
    injection is anchored on the record's own ``blockers:`` line so it
    survives edits to the record's other fields. TASK-INTENT-001 is the
    first record on the live board with exactly one ``evidence:`` block
    and one ``blockers: []`` line (verified against the 2026-11-27 shrunk
    board); the old TASK-REL-069 anchor was archived off the live board
    by that shrink.
    """
    text = board_path.read_text(encoding="utf-8")
    start = text.index("  - id: TASK-INTENT-001\n")
    next_record = text.find("\n  - id: ", start + 1)
    end = len(text) if next_record == -1 else next_record + 1
    segment = text[start:end]
    assert segment.count("    blockers: []\n") == 1, "INTENT-001 blockers line not found"
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


def ensure_rel107_fixture(board_path: Path) -> None:
    """Insert a synthetic TASK-REL-107-FIXTURE record if absent.

    Created/updated 2026-11-28, i.e. on the REL-107 effective date, so
    both gates apply to it: gate 1 when its status is terminal, gate 2
    always (it is a new record). It is inserted before the
    ``task_id_warnings:`` key, i.e. at the end of the ``tasks:`` list,
    and carries every field the validator requires (title, next_action,
    files) so the pristine-board checks still pass with it present. The
    record starts CLAIMED with neither new field, so cases I/J fail on
    the missing field and case K passes once both are added.
    """
    text = board_path.read_text(encoding="utf-8")
    if "  - id: TASK-REL-107-FIXTURE\n" in text:
        return
    marker = "\ntask_id_warnings:\n"
    assert text.count(marker) == 1, "task_id_warnings key not found exactly once"
    record = (
        "  - id: TASK-REL-107-FIXTURE\n"
        "    title: \"Fixture record for TASK-REL-107 validator tests (synthesised)\"\n"
        "    status: CLAIMED\n"
        "    owner: null\n"
        "    branch: null\n"
        "    pr: null\n"
        "    contributors: []\n"
        "    priority: P2\n"
        "    created_at: \"2026-11-28T00:00:00+05:30\"\n"
        "    updated_at: \"2026-11-28T00:00:00+05:30\"\n"
        "    evidence: []\n"
        "    blockers: []\n"
        "    next_action: \"Fixture record for the validator regression tests; not a real task.\"\n"
        "    files: []\n"
    )
    board_path.write_text(text.replace(marker, "\n" + record + "task_id_warnings:\n", 1), encoding="utf-8")


def set_rel107_fixture(
    board_path: Path,
    *,
    status: str | None = None,
    created: str | None = None,
    updated: str | None = None,
    pr: str | None = None,
    evidence_keys: dict[str, str] | None = None,
    live_proof_route: str | None = None,
) -> None:
    """Mutate the TASK-REL-107-FIXTURE record in place.

    Anchored on the record's own segment so edits to other records do
    not move it. ``evidence_keys`` (a mapping) and ``live_proof_route``
    (a string) are inserted after the record's ``pr:`` line when given;
    the inserted fixture record carries neither, so each case adds only
    what it needs. ``pr`` cites a PR number when given (cases I/K/L
    cite a merged PR so the REL-087 check does not fire first and mask
    the gate under test). Dates are written verbatim; case L rewinds
    both to 2026-11-27 to prove the grandfathering.
    """
    ensure_rel107_fixture(board_path)
    text = board_path.read_text(encoding="utf-8")
    start = text.index("  - id: TASK-REL-107-FIXTURE\n")
    next_record = text.find("\n  - id: ", start + 1)
    end = len(text) if next_record == -1 else next_record + 1
    segment = text[start:end]
    if status is not None:
        status_match = re.search(r"^    status: \w+\n", segment, re.M)
        assert status_match is not None, "REL-107-FIXTURE status line not found"
        segment = (
            segment[: status_match.start()]
            + f"    status: {status}\n"
            + segment[status_match.end() :]
        )
    for field, value in (("created_at", created), ("updated_at", updated)):
        if value is not None:
            date_match = re.search(rf"^    {field}: .*\n", segment, re.M)
            assert date_match is not None, f"REL-107-FIXTURE {field} line not found"
            segment = (
                segment[: date_match.start()]
                + f'    {field}: "{value}"\n'
                + segment[date_match.end() :]
            )
    if pr is not None:
        pr_match = re.search(r"^    pr: .*\n", segment, re.M)
        assert pr_match is not None, "REL-107-FIXTURE pr line not found"
        segment = (
            segment[: pr_match.start()]
            + f"    pr: {pr}\n"
            + segment[pr_match.end() :]
        )
    if evidence_keys is not None:
        lines = "".join(f'      {key}: "{value}"\n' for key, value in evidence_keys.items())
        block = "    evidence_keys:\n" + lines
        pr_match = re.search(r"^    pr: .*\n", segment, re.M)
        assert pr_match is not None, "REL-107-FIXTURE pr line not found"
        segment = segment[: pr_match.end()] + block + segment[pr_match.end() :]
    if live_proof_route is not None:
        pr_match = re.search(r"^    pr: .*\n", segment, re.M)
        assert pr_match is not None, "REL-107-FIXTURE pr line not found"
        segment = (
            segment[: pr_match.end()]
            + f'    live_proof_route: "{live_proof_route}"\n'
            + segment[pr_match.end() :]
        )
    board_path.write_text(text[:start] + segment + text[end:], encoding="utf-8")


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
        assert merged, "live board cites no merged PRs"
        good_pr = sorted(merged)[0]
        set_rel087_merged(tree / "docs/collaboration/WORK_BOARD.yaml", str(good_pr))
        prs_file = tree / "merged_prs.txt"
        prs_file.write_text("\n".join(str(n) for n in sorted(merged)) + "\n", encoding="utf-8")
        result = run_validator(tree, ("--merged-prs", "merged_prs.txt"))
    assert result.returncode == 0, f"MERGED citing a merged PR must be VALID:\n{result.stderr}"
    assert "COLLABORATION REGISTRY VALID" in result.stdout
    assert "verified against" in result.stdout and "merged PRs" in result.stdout, result.stdout
    print(f"H. MERGED citing merged PR {good_pr} -> VALID (exit 0)")


def case_i_terminal_without_evidence_keys() -> None:
    with tempfile.TemporaryDirectory(prefix="rel107-no-keys-") as tmp:
        tree = build_tree(Path(tmp))
        merged = live_merged_prs(tree)  # pristine board, before the mutation
        good_pr = sorted(merged)[0]
        set_rel107_fixture(
            tree / "docs/collaboration/WORK_BOARD.yaml",
            status="VERIFIED",
            pr=str(good_pr),
            live_proof_route="validator run against the REL-107 fixture",
        )
        prs_file = tree / "merged_prs.txt"
        prs_file.write_text("\n".join(str(n) for n in sorted(merged)) + "\n", encoding="utf-8")
        result = run_validator(tree, ("--merged-prs", "merged_prs.txt"))
    assert result.returncode == 1, f"VERIFIED-without-evidence-keys must FAIL:\n{result.stdout}"
    assert "TASK-REL-107-FIXTURE" in result.stderr and "evidence keys" in result.stderr, result.stderr
    print("I. VERIFIED without evidence_keys -> INVALID (exit 1):", result.stderr.strip().split(": ", 1)[-1][:120])


def case_j_new_record_without_live_proof_route() -> None:
    with tempfile.TemporaryDirectory(prefix="rel107-no-route-") as tmp:
        tree = build_tree(Path(tmp))
        ensure_rel107_fixture(tree / "docs/collaboration/WORK_BOARD.yaml")
        result = run_validator(tree)
    assert result.returncode == 1, f"new-record-without-live_proof_route must FAIL:\n{result.stdout}"
    assert "TASK-REL-107-FIXTURE" in result.stderr and "live_proof_route" in result.stderr, result.stderr
    print("J. new record without live_proof_route -> INVALID (exit 1):", result.stderr.strip().split(": ", 1)[-1][:120])


def case_k_terminal_with_all_keys_and_route() -> None:
    with tempfile.TemporaryDirectory(prefix="rel107-gates-ok-") as tmp:
        tree = build_tree(Path(tmp))
        merged = live_merged_prs(tree)  # pristine board, before the mutation
        good_pr = sorted(merged)[0]
        set_rel107_fixture(
            tree / "docs/collaboration/WORK_BOARD.yaml",
            status="VERIFIED",
            pr=str(good_pr),
            evidence_keys={
                "diff": "https://github.com/surendra2304/FRIDAY-Universe/pull/2093/files",
                "ci_link": "https://github.com/surendra2304/FRIDAY-Universe/actions/runs/1",
                "deploy_proof": "deployed on main cb3a9c6d",
                "live_probe_output": "validator run: fixture fails both gates, passes after fix",
                "non_author_verdict": "Muse TP6 VERIFIED review 6086258484",
            },
            live_proof_route="validator run against the REL-107 fixture",
        )
        prs_file = tree / "merged_prs.txt"
        prs_file.write_text("\n".join(str(n) for n in sorted(merged)) + "\n", encoding="utf-8")
        result = run_validator(tree, ("--merged-prs", "merged_prs.txt"))
    assert result.returncode == 0, f"VERIFIED with all five keys + route must be VALID:\n{result.stderr}"
    assert "COLLABORATION REGISTRY VALID" in result.stdout
    assert "Evidence gate (TASK-REL-107)" in result.stdout, result.stdout
    print("K. VERIFIED with all five evidence keys + live_proof_route -> VALID (exit 0)")


def case_l_grandfathered_before_effective_date() -> None:
    with tempfile.TemporaryDirectory(prefix="rel107-grandfather-") as tmp:
        tree = build_tree(Path(tmp))
        merged = live_merged_prs(tree)  # pristine board, before the mutation
        good_pr = sorted(merged)[0]
        set_rel107_fixture(
            tree / "docs/collaboration/WORK_BOARD.yaml",
            status="VERIFIED",
            created="2026-11-27T00:00:00+05:30",
            updated="2026-11-27T00:00:00+05:30",
            pr=str(good_pr),
        )
        prs_file = tree / "merged_prs.txt"
        prs_file.write_text("\n".join(str(n) for n in sorted(merged)) + "\n", encoding="utf-8")
        result = run_validator(tree, ("--merged-prs", "merged_prs.txt"))
    assert result.returncode == 0, f"pre-effective-date VERIFIED must be VALID:\n{result.stderr}"
    assert "COLLABORATION REGISTRY VALID" in result.stdout
    print("L. VERIFIED dated 2026-11-27, no new fields -> VALID (grandfathered, exit 0)")


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
        case_i_terminal_without_evidence_keys,
        case_j_new_record_without_live_proof_route,
        case_k_terminal_with_all_keys_and_route,
        case_l_grandfathered_before_effective_date,
    )
    for case in cases:
        case()
    print(f"All {len(cases)} validate_collaboration tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
