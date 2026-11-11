"""TASK-CI-004 regression: .gitignore must not block deliberate bridge commits.

History: the blanket `bridge/**` rule (commit 08a8606, added 2026-11-08 to
ignore *runtime artifacts* before any bridge source existed in this repo)
forced every deliberate bridge commit through `git add -f` and silently hid
new source files.  Bridge source IS tracked (auth.py, server_auth.patch) and
the root test suite imports it (`from bridge.auth import BridgeAuthMiddleware`
in tests/test_bridge_auth.py), so a rule that hides bridge source is a defect.

Contract locked by this file, verified against the real git machinery:
- Bridge SOURCE paths are addable without force:  .py, patch files, .md docs,
  nested source packages (e.g. bridge/tools/whatever.py).
- Bridge ARTIFACT paths stay ignored: logs, .deploy-backups, *.bak, *.tmp,
  state/ and workspaces/ directories, sqlite/db files.
- The global artifact rules must keep working outside bridge/ as well.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (path, should_be_ignored) — evaluated against the live git index machinery.
CASES = [
    # --- bridge SOURCE: must be committable without `git add -f` ---
    ("bridge/auth.py", False),                      # already-tracked middleware
    ("bridge/server_auth.patch", False),            # already-tracked patch
    ("bridge/README.md", False),                    # future docs commit
    ("bridge/handoff_run.md", False),               # ad-hoc engineering notes
    ("bridge/tools/laptop_proxy.py", False),        # new nested source package
    ("bridge/tools/sub/deep_module.py", False),     # deeper nesting
    ("bridge/requirements.txt", False),             # dependency manifest
    # --- bridge ARTIFACTS: must remain ignored ---
    ("bridge/run.log", True),                      # runtime logs
    ("bridge/logs/session.json.log", True),
    ("bridge/server.log.20261110", True),
    ("bridge/.deploy-backups/pre-auth", True),      # backup snapshots
    ("bridge/state/session_store.json", True),     # runtime state dirs
    ("bridge/workspaces/task-77/out.txt", True),
    ("bridge/scratch.bak", True),
    ("bridge/temp.tmp", True),
    ("bridge/ledger.sqlite", True),
    ("bridge/ledger.sqlite3", True),
    ("bridge/queue.db", True),
    # --- global rules outside bridge/ unchanged ---
    (".deploy-backups/anything", True),
    ("FRIDAY/.deploy-backups/x.tar", True),
    ("docs/notes.bak", True),
]


def _git_check_ignore(paths: list[str]) -> set[str]:
    """Return the subset of `paths` that git ignores, using real git semantics."""
    proc = subprocess.run(
        ["git", "check-ignore", "--no-index", "--", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # exit 0: some paths ignored; exit 1: none ignored; >1: real failure.
    if proc.returncode > 1:
        raise AssertionError(
            f"git check-ignore failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return {line for line in proc.stdout.splitlines() if line}


def test_gitignore_allows_deliberate_bridge_commits() -> None:
    """Bridge source paths must NOT be ignored; artifacts must stay ignored."""
    paths = [p for p, _ in CASES]
    ignored = _git_check_ignore(paths)

    failures: list[str] = []
    for path, should_ignore in CASES:
        actually_ignored = path in ignored
        if actually_ignored is not should_ignore:
            expected = "ignored" if should_ignore else "NOT ignored (committable)"
            failures.append(f"  {path}: expected {expected}")

    assert not failures, (
        "TASK-CI-004 regression: .gitignore no longer matches the bridge "
        "source/artifact contract. Discrepancies:\n" + "\n".join(failures)
    )


def test_tracked_bridge_files_are_listed_source() -> None:
    """Every tracked bridge/ file must be source-like, never an artifact.

    Guards against someone force-adding a runtime artifact to work around the
    old blanket rule (the exact failure mode TASK-CI-004 removes).
    """
    proc = subprocess.run(
        ["git", "ls-files", "bridge/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"git ls-files failed: {proc.stderr.strip()}"
    tracked = [p for p in proc.stdout.splitlines() if p.strip()]
    assert tracked, "bridge/ should contain tracked source (auth.py et al.)"

    allowed_suffixes = {".py", ".patch", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
    for path in tracked:
        suffix = Path(path).suffix.lower()
        assert suffix in allowed_suffixes, (
            f"Tracked bridge file {path} looks like an artifact "
            f"(.{suffix.lstrip('.')}); artifacts must stay untracked."
        )


if __name__ == "__main__":  # manual evidence run: python tests/test_gitignore_bridge_source.py
    ignored = _git_check_ignore([p for p, _ in CASES])
    ok = True
    for path, should_ignore in CASES:
        actual = path in ignored
        mark = "PASS" if actual is should_ignore else "FAIL"
        ok = ok and (actual is should_ignore)
        print(f"[{mark}] {'ignored    ' if actual else 'committable '} {path}")
    print("RESULT:", "ALL GREEN" if ok else "FAILURES PRESENT")
    sys.exit(0 if ok else 1)
