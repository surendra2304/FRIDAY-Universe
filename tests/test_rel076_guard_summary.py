"""Contracts-guard step-summary tests (TASK-REL-076).

The guard (scripts/ci_test_collection_audit.py) must write its verdict to
$GITHUB_STEP_SUMMARY so a failure lists the failing files on the PR check
summary page — no truncated-log hunt (the #1395 hold cost a day).

These tests build tiny real git fixtures and run the guard as a subprocess,
the same way the contracts workflow runs it. This file itself is collected
by validate-monorepo.yml's directory run (`pytest -q tests`), so the guard
passes for it.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci_test_collection_audit.py"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "rel076-test",
    "GIT_AUTHOR_EMAIL": "rel076-test@example.invalid",
    "GIT_COMMITTER_NAME": "rel076-test",
    "GIT_COMMITTER_EMAIL": "rel076-test@example.invalid",
}

WORKFLOW_TEMPLATE = """name: fixture-ci
on:
  pull_request:
    branches: [main]
jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - name: run tests
        run: |
          python -m pytest -q {listed}
"""


def load_script():
    spec = importlib.util.spec_from_file_location(
        "ci_test_collection_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV,
                   check=True, capture_output=True, text=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit_all(cwd, message):
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", "-m", message)
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd,
                         env=GIT_ENV, check=True, capture_output=True,
                         text=True)
    return out.stdout.strip()


def build_fixture(tmp_path, listed, extra_files=None):
    """A git repo with one PR-triggered workflow listing `listed` tests."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    write(root / ".github" / "workflows" / "ci.yml",
          WORKFLOW_TEMPLATE.format(listed=" ".join(listed)))
    for name in listed:
        write(root / name, "def test_ok():\n    assert True\n")
    for name in (extra_files or []):
        write(root / name, "def test_ok():\n    assert True\n")
    base = commit_all(root, "base")
    return root, base


def run_guard(root, base, summary_path=None):
    env = {**os.environ}
    if summary_path is not None:
        env["GITHUB_STEP_SUMMARY"] = str(summary_path)
    else:
        env.pop("GITHUB_STEP_SUMMARY", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, "--root", str(root)],
        env=env, capture_output=True, text=True)
    return proc


def test_summary_lists_uncollected_files_on_failure(tmp_path):
    root, base = build_fixture(tmp_path, ["tests/test_collected.py"])
    write(root / "tests" / "test_uncollected.py",
          "def test_ok():\n    assert True\n")
    commit_all(root, "add uncollected test")
    summary = tmp_path / "summary.md"
    proc = run_guard(root, base, summary)
    assert proc.returncode == 1
    assert "UNCOLLECTED: tests/test_uncollected.py" in proc.stdout
    text = summary.read_text(encoding="utf-8")
    assert "Test-collection guard — FAIL" in text
    assert "`tests/test_uncollected.py`" in text
    assert "Uncollected test file(s) (1)" in text


def test_summary_pass_when_collected(tmp_path):
    root, base = build_fixture(tmp_path, ["tests/test_collected.py"])
    write(root / ".github" / "workflows" / "ci.yml",
          WORKFLOW_TEMPLATE.format(
              listed="tests/test_collected.py tests/test_new.py"))
    write(root / "tests" / "test_new.py", "def test_ok():\n    assert True\n")
    commit_all(root, "add collected test + workflow listing")
    summary = tmp_path / "summary.md"
    proc = run_guard(root, base, summary)
    assert proc.returncode == 0, proc.stdout
    text = summary.read_text(encoding="utf-8")
    assert "Test-collection guard — PASS" in text


def test_summary_lists_stale_references(tmp_path):
    # Workflow names tests/test_gone.py, but the file does not exist.
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    write(root / ".github" / "workflows" / "ci.yml",
          WORKFLOW_TEMPLATE.format(
              listed="tests/test_collected.py tests/test_gone.py"))
    write(root / "tests" / "test_collected.py",
          "def test_ok():\n    assert True\n")
    base = commit_all(root, "base")
    write(root / "README.md", "fixture\n")
    commit_all(root, "touch non-test file")
    summary = tmp_path / "summary.md"
    proc = run_guard(root, base, summary)
    assert proc.returncode == 1
    assert "STALE" in proc.stdout
    text = summary.read_text(encoding="utf-8")
    assert "Test-collection guard — FAIL" in text
    assert "Stale workflow reference(s) (1)" in text
    assert "`tests/test_gone.py`" in text


def test_summary_caps_long_lists():
    module = load_script()
    uncovered = ["tests/test_%03d.py" % i for i in range(60)]
    lines = module.summary_lines(
        "PR diff vs deadbeef", 100, 40, 60, uncovered, [])
    text = "\n".join(lines)
    assert "Uncollected test file(s) (60)" in text
    assert text.count("`tests/test_") == module.SUMMARY_LIST_CAP
    assert "…and 10 more — see the step log for the full list." in text


def test_summary_skipped_without_env_var(tmp_path):
    root, base = build_fixture(tmp_path, ["tests/test_collected.py"])
    write(root / "tests" / "test_uncollected.py",
          "def test_ok():\n    assert True\n")
    commit_all(root, "add uncollected test")
    proc = run_guard(root, base, summary_path=None)
    assert proc.returncode == 1
    assert "UNCOLLECTED: tests/test_uncollected.py" in proc.stdout
    assert not (tmp_path / "summary.md").exists()
