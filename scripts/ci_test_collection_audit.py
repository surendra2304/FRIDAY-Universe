#!/usr/bin/env python3
"""CI test-collection guard (TASK-REL-068).

Fails loudly when a PR ships a test file that no PR-triggered workflow
collects, so a merged test can never again run nowhere (the REL-001 defect
class: PR #936-era files, DAEMON-002 follow-up, REL-001 itself).

Design (evidence, main 3dd7cfba, 2026-11-22, verified by running this
  script's --full mode against the live tree and workflow files):
  * The repo holds 1,899 test files. Only 269 (14.2%) are collected by a
    PR-triggered workflow, even after crediting directory runs
    (validate-monorepo.yml's `pytest -q tests`, monorepo-validation.yml's
    `pytest -q tests`). A full-repo guard would fail with 1,630 violations
    on day one, so this guard is DIFF-SCOPED: it checks only test files
    the PR itself adds or modifies. Pre-existing debt is reported by
    --full for a future cleanup task, never a PR failure.
  * A changed test file counts as collected when some PR-triggered workflow
    names it (exact path, trailing-path suffix, glob, or a directory pytest
    invocation covering it). References are matched leniently on purpose:
    a false PASS is a missed warning, a false FAIL blocks every PR.
  * Files that legitimately cannot run in PR CI belong in EXCLUDED with a
    reason, printed in the CI log. The exclusion list starts empty.
  * Also fails on stale references: a workflow naming a test file that no
    longer exists (the lists rotting the other way).

Usage (CI, .github/workflows/owner-workflows.yml, contracts job, first step):
    python3 scripts/ci_test_collection_audit.py --base <base-sha>
Locally:
    python3 scripts/ci_test_collection_audit.py --full        # whole-repo report
    python3 scripts/ci_test_collection_audit.py --base <sha>  # this PR's diff

Exit codes: 0 collected (or nothing to check); 1 uncovered/stale files;
2 the guard itself could not run (no git, no base, no workflows dir).
"""
import argparse
import fnmatch
import os
import re
import subprocess
import sys

# path -> reason. A test file listed here passes the guard, and the reason is
# printed in CI output. Add entries only for files that cannot run in PR CI.
EXCLUDED = {
    "Futuris/scripts/e2e_system_test.py": (
        "Standalone __main__ E2E harness, 0 pytest tests; runs the full "
        "pipeline against the configured database engine and needs "
        "FUTURIS_API_KEY — cannot run in PR CI."
    ),
}

REF_RE = re.compile(r"[A-Za-z0-9_./\-\*?\[\]]*test_[A-Za-z0-9_./\-\*?\[\]]*\.py")
TEST_RE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py)$")


def run_git(args, cwd):
    out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                         text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), out.stderr.strip()))
    return out.stdout


def repo_test_files(root):
    """All test files tracked in the checkout (git ls-files, no clone needed)."""
    out = run_git(["ls-files"], cwd=root)
    return [p for p in out.splitlines() if TEST_RE.search(p)]


def parse_workflows(workflows_dir, root):
    """Return (references, pr_workflows).

    references: list of (workflow, working_dir, raw_ref) where raw_ref is a
    test-file path, glob, or directory named in a pytest invocation.
    A workflow counts as PR-triggered when its text has a pull_request trigger.
    working-directory context is tracked per step (best effort, line based);
    matching is suffix-based so a stale context cannot hide a real file.
    """
    references, pr_workflows = [], []
    for name in sorted(os.listdir(workflows_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        path = os.path.join(workflows_dir, name)
        text = open(path, encoding="utf-8").read()
        if "pull_request:" not in text:
            continue
        pr_workflows.append(name)
        wd, in_run, in_pytest = "", False, False
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^ *- name:", line) or re.match(r"^  [a-zA-Z0-9_-]+:", line):
                wd, in_run, in_pytest = "", False, False
            m = re.match(r"^ *working-directory: (.+)$", line)
            if m:
                wd = m.group(1).strip().strip("\"'")
                continue
            if re.match(r"^ *run: *[|>]", line):
                in_run = True
                continue
            if not in_run:
                continue
            if "pytest" in stripped:
                in_pytest = True
            if in_pytest:
                for ref in REF_RE.findall(stripped):
                    references.append((name, wd, ref.strip("./")))
                # directory invocation: a bare directory token that is an
                # ARGUMENT to pytest (after the `pytest` token) — e.g.
                # `pytest -q tests`. Tokens before `pytest` (such as `cd`
                # targets) are not pytest arguments and must not credit
                # whole directories.
                toks = stripped.replace("\\", " ").split()
                try:
                    pi = toks.index("pytest")
                except ValueError:
                    pi = -1
                for tok in toks[pi + 1:]:
                    tok = tok.rstrip(");,")
                    if not tok or tok.startswith("-") or tok in ("-m",):
                        continue
                    if any(ch in tok for ch in "(&|"):
                        continue
                    cand = os.path.normpath(os.path.join(wd, tok)) if wd else tok
                    if os.path.isdir(os.path.join(root, cand)):
                        references.append((name, wd, cand + "/"))
                if not stripped.endswith("\\"):
                    in_pytest = False
    return references, pr_workflows


def covers(ref, wd, test_files):
    """Test files covered by one workflow reference (path, glob, or dir)."""
    raw = ref
    if any(ch in raw for ch in "*?["):
        base = os.path.join(wd, raw) if wd else raw
        return [t for t in test_files if fnmatch.fnmatch(t, base)]
    if raw.endswith("/"):  # directory invocation
        d = os.path.normpath(os.path.join(wd, raw)) if wd else raw.rstrip("/")
        return [t for t in test_files if t == d or t.startswith(d.rstrip("/") + "/")]
    cands = []
    if wd:
        cands.append(os.path.normpath(os.path.join(wd, raw)))
    cands.append(raw)
    out = []
    for t in test_files:
        if t in cands or any(t.endswith("/" + c) for c in cands):
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=os.environ.get("GUARD_BASE_SHA", ""),
                    help="base sha for the PR diff (or GUARD_BASE_SHA)")
    ap.add_argument("--full", action="store_true",
                    help="audit every test file in the repo, not just the diff")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    workflows_dir = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(workflows_dir):
        print("GUARD ERROR: no workflows dir at %s" % workflows_dir)
        return 2
    try:
        test_files = repo_test_files(root)
    except Exception as e:
        print("GUARD ERROR: cannot list tracked test files: %s" % e)
        return 2
    references, pr_workflows = parse_workflows(workflows_dir, root)
    covered = {}
    for wf, wd, ref in references:
        for t in covers(ref, wd, test_files):
            covered.setdefault(t, []).append(wf)

    # Stale references: a workflow names a test file that matches nothing.
    stale = sorted({(wf, ref) for wf, wd, ref in references
                    if not ref.endswith("/") and not covers(ref, wd, test_files)})

    if args.full:
        changed = test_files
        scope = "full-repo audit"
    else:
        if not args.base or set(args.base) <= {"0"}:
            print("GUARD ERROR: no base sha given (--base or GUARD_BASE_SHA); "
                  "the PR diff cannot be determined, so the guard cannot run.")
            return 2
        try:
            diff = run_git(["diff", "--name-only", "--diff-filter=ACMRT",
                            "%s...HEAD" % args.base], cwd=root)
        except Exception as e:
            print("GUARD ERROR: cannot compute the PR diff: %s" % e)
            return 2
        changed = sorted({p for p in diff.splitlines() if TEST_RE.search(p)})
        scope = "PR diff vs %s" % args.base[:12]

    print("Test-collection guard (%s): %d test files in repo, %d covered by "
          "a PR-triggered workflow, %d PR-triggered workflows scanned."
          % (scope, len(test_files), len(covered), len(pr_workflows)))
    uncovered = [t for t in changed
                 if t not in covered and t not in EXCLUDED]
    for t in sorted(EXCLUDED):
        if t in changed:
            print("EXCLUDED (reason on record): %s — %s" % (t, EXCLUDED[t]))
    if uncovered:
        print("FAIL: %d test file(s) shipped in this PR are collected by NO "
              "PR-triggered workflow. CI would stay green while they never "
              "run. Add each file to a workflow pytest invocation (or to "
              "EXCLUDED in scripts/ci_test_collection_audit.py with a "
              "reason), then re-run:" % len(uncovered))
        for t in uncovered:
            print("  UNCOLLECTED: %s" % t)
    if stale:
        print("FAIL: %d stale workflow reference(s) to test files that do "
              "not exist:" % len(stale))
        for wf, ref in stale:
            print("  STALE: %s names %s" % (wf, ref))
    if uncovered or stale:
        return 1
    if not changed:
        print("PASS: no test files in scope to check.")
    else:
        print("PASS: every test file in scope is collected by a PR-triggered "
              "workflow (%d checked)." % len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
