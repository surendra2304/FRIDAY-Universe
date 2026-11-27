"""Fleet-layout gate fail-loudly tests (TASK-REL-081).

The gate runner (scripts/ci_gate_test_runner.py) must make a failing
``Run regression tests`` step self-describing: the run summary names the
run id, the failing step, the exit code and the log tail, and an exit-134
recurrence gets an explicit banner plus the REL-070 signature check — so
no diagnosis cycle is needed to identify it.

These tests run the runner as a subprocess against fake pytest programs
(a passing one, one failing with exit 1, one aborting with the real
REL-070 shutdown text and exit 134), the same way the gate runs it. This
file itself is collected by validate-monorepo.yml's directory run
(``pytest -q tests``) and by the contracts workflow list.
"""
import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci_gate_test_runner.py"

# The real REL-070 failure signature (docs/collaboration/
# TASK-REL-070-EXIT-134-ROOT-CAUSE.md, run 45082613824): tests pass, then
# the interpreter aborts at shutdown while a daemon thread is logging.
REAL_134_LOG = textwrap.dedent("""\
    3728 passed, 72 skipped, 261 warnings, 8 subtests passed in 109.51s (0:01:49)
    Traceback (most recent call last):
      File ".../logging/__init__.py", line 1164, in emit
        self.flush()
    ValueError: I/O operation on closed file.
    Call stack:
      File ".../threading.py", line 1012, in run
      File ".../Stratex/api/friday_supervision.py", line 442, in _refresh_market_analysis
    Fatal Python error: _enter_buffered_busy: could not acquire lock for
    <_io.BufferedWriter name='<stderr>'> at interpreter shutdown, possibly due to daemon threads
    Python runtime state: finalizing
    /home/runner/work/_temp/...sh: line 1:  2501 Aborted  (core dumped) python -m pytest -q tests
    """)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "ci_gate_test_runner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_fake_pytest(tmp_path, name, body):
    """Write a fake pytest program that prints *body* and exits as coded."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def run_runner(tmp_path, fake_pytest, extra_env=None):
    """Run the runner against *fake_pytest*; return (proc, summary_path)."""
    summary_path = tmp_path / "step_summary.md"
    log_path = tmp_path / "gate-test-output.log"
    env = {
        **os.environ,
        "GITHUB_RUN_ID": "45123456789",
        "GITHUB_REPOSITORY": "surendra2304/FRIDAY-Universe",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_WORKFLOW": "Monorepo Structure and Safety CI",
        "GITHUB_REF": "refs/pull/9999/merge",
        "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_STEP_SUMMARY": str(summary_path),
        **(extra_env or {}),
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log_path),
         "--", sys.executable, str(fake_pytest)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    return proc, summary_path


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_detect_exit134_signature_finds_all_markers_in_real_log():
    module = load_script()
    found = module.detect_exit134_signature(REAL_134_LOG)
    assert found == list(module.SIGNATURE_MARKERS)


def test_detect_exit134_signature_empty_for_ordinary_failure():
    module = load_script()
    assert module.detect_exit134_signature(
        "FAILED tests/test_x.py::test_y - assert 1 == 2\n1 failed in 0.5s\n"
    ) == []


def test_pytest_summary_line_extracted():
    module = load_script()
    assert module.pytest_summary_line(REAL_134_LOG).startswith("3728 passed")
    assert module.pytest_summary_line("no summary here") is None


def test_summary_names_run_step_exit_and_tail():
    module = load_script()
    ctx = module.github_context()
    lines = module.summary_lines(
        ctx, 1, ["FAILED tests/test_x.py::test_y", "1 failed in 0.5s"],
        "FAILED tests/test_x.py::test_y\n1 failed in 0.5s\n")
    text = "\n".join(lines)
    assert "Run id:" in text
    assert "Run regression tests" in text
    assert "Exit code: 1" in text
    assert "FAILED tests/test_x.py::test_y" in text
    assert "EXIT-134" not in text


def test_summary_134_banner_names_signature_and_tests_passed():
    module = load_script()
    ctx = module.github_context()
    lines = module.summary_lines(
        ctx, 134, REAL_134_LOG.splitlines()[-5:], REAL_134_LOG)
    text = "\n".join(lines)
    assert "EXIT-134 RECURRENCE" in text
    assert "Exit code: 134" in text
    assert "tests passed" in text
    assert "TASK-REL-070-EXIT-134-ROOT-CAUSE.md" in text
    assert "all 6 REL-070 signature markers present" in text


def test_summary_134_without_signature_says_new_cause():
    module = load_script()
    ctx = module.github_context()
    log = "3728 passed in 109.51s\nprocess aborted, no further detail\n"
    lines = module.summary_lines(ctx, 134, log.splitlines(), log)
    text = "\n".join(lines)
    assert "EXIT-134 RECURRENCE" in text
    assert "NEW abort cause" in text


def test_summary_minus6_is_the_same_abort_as_134():
    """A SIGABRT death under the runner reports returncode -6 (shell 250).

    TASK-REL-070 follow-up: every post-fix recurrence arrived as -6/250,
    not 134, so the banner and the signature check must key on -6 too.
    """
    module = load_script()
    ctx = module.github_context()
    lines = module.summary_lines(
        ctx, -6, REAL_134_LOG.splitlines()[-5:], REAL_134_LOG)
    text = "\n".join(lines)
    assert "EXIT-134 RECURRENCE" in text
    assert "Exit code: -6" in text
    assert "SIGABRT" in text
    assert "tests passed" in text
    assert "all 6 REL-070 signature markers present" in text


# ---------------------------------------------------------------------------
# Subprocess integration tests (the runner as the gate runs it)
# ---------------------------------------------------------------------------

def test_passing_pytest_exits_zero_and_writes_no_summary(tmp_path):
    fake = make_fake_pytest(tmp_path, "fake_pass.py",
                            "print('5 passed in 1.0s')\n")
    proc, summary_path = run_runner(tmp_path, fake)
    assert proc.returncode == 0
    assert not summary_path.exists()


def test_exit1_failure_preserves_code_and_summarizes(tmp_path):
    fake = make_fake_pytest(
        tmp_path, "fake_fail1.py",
        "print('FAILED tests/test_x.py::test_y - assert 1 == 2')\n"
        "print('1 failed in 0.5s')\n"
        "raise SystemExit(1)\n")
    proc, summary_path = run_runner(tmp_path, fake)
    assert proc.returncode == 1
    text = summary_path.read_text(encoding="utf-8")
    assert "Run id: 45123456789" in text
    assert "https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45123456789" in text
    assert "Failing step: Run regression tests" in text
    assert "Exit code: 1" in text
    assert "FAILED tests/test_x.py::test_y" in text
    assert "EXIT-134" not in text
    # The same summary is also printed to the step log.
    assert "Run id: 45123456789" in proc.stdout


def test_exit134_recurrence_preserves_code_and_names_signature(tmp_path):
    fake = make_fake_pytest(
        tmp_path, "fake_abort134.py",
        "import sys\n"
        "sys.stdout.write(%r)\n" % REAL_134_LOG +
        "raise SystemExit(134)\n")
    proc, summary_path = run_runner(tmp_path, fake)
    assert proc.returncode == 134
    text = summary_path.read_text(encoding="utf-8")
    assert "EXIT-134 RECURRENCE" in text
    assert "Run id: 45123456789" in text
    assert "Failing step: Run regression tests" in text
    assert "Exit code: 134" in text
    assert "3728 passed, 72 skipped" in text
    assert "all 6 REL-070 signature markers present" in text
    assert "friday_supervision.py" in text
    assert "(core dumped)" in text


def test_sigabrt_death_reports_250_and_names_recurrence(tmp_path):
    """A real SIGABRT death under the runner is returncode -6 -> exit 250.

    TASK-REL-070 follow-up: the post-fix recurrences all arrived in this
    shape (the runner's subprocess was killed by signal 6), and the old
    banner keyed on 134 only, so none of them was recognised.
    """
    fake = make_fake_pytest(
        tmp_path, "fake_abort_sig.py",
        "import os, sys\n"
        "sys.stdout.write(%r)\n" % REAL_134_LOG +
        "sys.stdout.flush()\n"
        "os.abort()\n")
    proc, summary_path = run_runner(tmp_path, fake)
    assert proc.returncode == 250
    text = summary_path.read_text(encoding="utf-8")
    assert "EXIT-134 RECURRENCE" in text
    assert "Exit code: -6" in text
    assert "SIGABRT" in text
    assert "3728 passed, 72 skipped" in text
    assert "all 6 REL-070 signature markers present" in text


def test_summary_still_written_without_github_env(tmp_path):
    """Local runs (no Actions env) still print the summary to the log."""
    summary_path = tmp_path / "step_summary.md"
    log_path = tmp_path / "gate-test-output.log"
    fake = make_fake_pytest(
        tmp_path, "fake_fail1.py",
        "print('1 failed in 0.5s')\nraise SystemExit(1)\n")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GITHUB_")}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log_path),
         "--", sys.executable, str(fake)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "Run id: unknown" in proc.stdout
    assert not summary_path.exists()  # no GITHUB_STEP_SUMMARY locally
