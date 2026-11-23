"""Test-job failure-summary tests (TASK-REL-086).

The generic CI failure-summary wrapper (scripts/ci_failure_summary.py)
must name the failing test in its ``--pytest`` mode: on a pytest failure
the check-run summary lists every failing test node id plus the log tail,
so the exact failing test is recoverable without sign-in-gated logs.
REL-080 repair run 4 needed test_f3_peer_transport_exponential_backoff
and it was recoverable only by reading a truncated log window via the
MCP client, because annotations and check-run output carry no test name.

These tests run the wrapper as a subprocess against fake pytest programs
and against real pytest on a deliberately failing test file, the same way
the test job in .github/workflows/friday-universe-ci.yml runs it. This
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
SCRIPT = REPO_ROOT / "scripts" / "ci_failure_summary.py"

# A realistic pytest -q failure log: the test is printed once while
# running and once in the short test summary, plus one erroring test
# and one parametrized failure.
REAL_PYTEST_FAIL_LOG = textwrap.dedent("""\
    tests/test_x.py::test_ok PASSED
    FAILED tests/test_x.py::test_failing - assert 1 == 2
    ERROR tests/test_y.py::test_setup_broken - Failed: setup exploded
    FAILED tests/test_z.py::test_param[case-2] - assert 'a' == 'b'
    =========================== short test summary info ===========================
    FAILED tests/test_x.py::test_failing - assert 1 == 2
    FAILED tests/test_z.py::test_param[case-2] - assert 'a' == 'b'
    ERROR tests/test_y.py::test_setup_broken - Failed: setup exploded
    ============ 2 failed, 1 passed, 1 error in 0.42s ============
    """)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "ci_failure_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_wrapper(tmp_path, argv, extra_env=None):
    """Run the wrapper with a temp summary file; return (proc, summary)."""
    summary_path = tmp_path / "step_summary.md"
    log_path = tmp_path / "wrapper-output.log"
    env = {
        **os.environ,
        "GITHUB_RUN_ID": "45123456789",
        "GITHUB_REPOSITORY": "surendra2304/FRIDAY-Universe",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_WORKFLOW": "FRIDAY Universe CI/CD",
        "GITHUB_REF": "refs/pull/9999/merge",
        "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_STEP_SUMMARY": str(summary_path),
        **(extra_env or {}),
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log_path)] + argv,
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    return proc, summary_path


def wrapper_args(check="test-job", step="Run engine test suites with coverage",
                 pytest_mode=True):
    args = ["--check", check, "--step", step,
            "--workflow", ".github/workflows/friday-universe-ci.yml",
            "--job", "test"]
    if pytest_mode:
        args.append("--pytest")
    return args


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_extract_finds_failed_and_error_node_ids_in_order():
    module = load_script()
    assert module.extract_failing_tests(REAL_PYTEST_FAIL_LOG) == [
        "tests/test_x.py::test_failing",
        "tests/test_y.py::test_setup_broken",
        "tests/test_z.py::test_param[case-2]",
    ]


def test_extract_deduplicates_running_and_summary_lines():
    module = load_script()
    log = ("FAILED tests/test_x.py::test_a - assert 1 == 2\n"
           "FAILED tests/test_x.py::test_a - assert 1 == 2\n")
    assert module.extract_failing_tests(log) == ["tests/test_x.py::test_a"]


def test_extract_ignores_verbose_progress_lines():
    module = load_script()
    log = ("tests/test_x.py::test_a PASSED [ 33%]\n"
           "tests/test_x.py::test_b FAILED [ 66%]\n"
           "tests/test_x.py::test_c PASSED [100%]\n")
    # -v progress lines carry FAILED mid-line; only the short summary
    # at the end names failures in FAILED-first form, so this parses
    # to nothing rather than guessing from progress output.
    assert module.extract_failing_tests(log) == []


def test_extract_handles_collection_error_path():
    module = load_script()
    log = ("ERROR collecting tests/test_broken.py\n"
           "ImportError: cannot import name 'missing'\n"
           "!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection "
           "!!!!!!!!!!!!!!!!!!!\n")
    assert module.extract_failing_tests(log) == ["tests/test_broken.py"]


def test_extract_rejects_setup_error_stray_token():
    module = load_script()
    log = ("ERROR at setup of test_broken - Failed: setup exploded\n"
           "ERROR tests/test_y.py::test_setup_broken - Failed: setup exploded\n")
    assert module.extract_failing_tests(log) == [
        "tests/test_y.py::test_setup_broken"]


def test_extract_empty_for_passing_and_abort_logs():
    module = load_script()
    assert module.extract_failing_tests("5 passed in 1.0s\n") == []
    # REL-070 shape: tests pass, then the interpreter aborts at shutdown.
    assert module.extract_failing_tests(
        "3728 passed in 109.51s\nFatal Python error: _enter_buffered_busy\n"
    ) == []
    assert module.extract_failing_tests("") == []


def test_summary_lists_failing_tests_before_tail():
    module = load_script()
    ctx = module.github_context("test-job", "Run engine test suites",
                                ".github/workflows/friday-universe-ci.yml",
                                "test")
    failing = ["tests/test_x.py::test_failing",
               "tests/test_y.py::test_setup_broken"]
    lines = module.summary_lines(
        ctx, 1, ["FAILED tests/test_x.py::test_failing", "2 failed in 0.4s"],
        failing)
    text = "\n".join(lines)
    assert "### Failing tests (2)" in text
    assert "- `tests/test_x.py::test_failing`" in text
    assert "- `tests/test_y.py::test_setup_broken`" in text
    # Failing-tests section comes before the log tail section.
    assert text.index("Failing tests") < text.index("Offending lines")
    assert "FAILED tests/test_x.py::test_failing" in text


def test_summary_caps_long_failing_test_list():
    module = load_script()
    ctx = module.github_context("test-job", "Run engine test suites",
                                ".github/workflows/friday-universe-ci.yml",
                                "test")
    failing = ["tests/test_x.py::test_%02d" % i for i in range(25)]
    text = "\n".join(module.summary_lines(ctx, 1, ["tail"], failing))
    assert "### Failing tests (25)" in text
    assert "tests/test_x.py::test_19" in text
    assert "tests/test_x.py::test_20" not in text
    assert "... and 5 more (see the log tail below)" in text


def test_summary_says_so_when_pytest_mode_finds_no_test():
    module = load_script()
    ctx = module.github_context("test-job", "Run engine test suites",
                                ".github/workflows/friday-universe-ci.yml",
                                "test")
    text = "\n".join(module.summary_lines(ctx, 134, ["aborted"], []))
    assert "### Failing tests" in text
    assert "None identified in the log" in text


def test_summary_unchanged_without_pytest_mode():
    module = load_script()
    ctx = module.github_context("roster-validator",
                                "Validate collaboration registry",
                                ".github/workflows/collaboration-registry.yml",
                                "Validate roster, task IDs and file ownership")
    text = "\n".join(module.summary_lines(ctx, 1, ["offending line"]))
    assert "Failing tests" not in text
    assert "offending line" in text


# ---------------------------------------------------------------------------
# Subprocess integration tests (the wrapper as the test job runs it)
# ---------------------------------------------------------------------------

def test_pytest_failure_preserves_code_and_names_test(tmp_path):
    fake = tmp_path / "fake_pytest.py"
    fake.write_text(
        "import sys\n"
        "sys.stdout.write(%r)\n" % REAL_PYTEST_FAIL_LOG +
        "raise SystemExit(1)\n", encoding="utf-8")
    proc, summary_path = run_wrapper(
        tmp_path, wrapper_args() + ["--", sys.executable, str(fake)])
    assert proc.returncode == 1
    text = summary_path.read_text(encoding="utf-8")
    assert "## test-job — step FAILED (exit 1)" in text
    assert "Failing step: Run engine test suites with coverage" in text
    assert "Job: test" in text
    assert "### Failing tests (3)" in text
    assert "- `tests/test_x.py::test_failing`" in text
    assert "- `tests/test_y.py::test_setup_broken`" in text
    assert "- `tests/test_z.py::test_param[case-2]`" in text
    assert "2 failed, 1 passed, 1 error in 0.42s" in text
    # The same summary is also printed to the step log.
    assert "tests/test_x.py::test_failing" in proc.stdout


def test_pytest_pass_exits_zero_and_writes_no_summary(tmp_path):
    fake = tmp_path / "fake_pass.py"
    fake.write_text("print('5 passed in 1.0s')\n", encoding="utf-8")
    proc, summary_path = run_wrapper(
        tmp_path, wrapper_args() + ["--", sys.executable, str(fake)])
    assert proc.returncode == 0
    assert not summary_path.exists()


def test_non_pytest_failure_has_no_failing_tests_section(tmp_path):
    fake = tmp_path / "fake_fail.py"
    fake.write_text(
        "import sys; print('offending line'); sys.exit(3)\n",
        encoding="utf-8")
    proc, summary_path = run_wrapper(
        tmp_path, wrapper_args(pytest_mode=False)
        + ["--", sys.executable, str(fake)])
    assert proc.returncode == 3
    text = summary_path.read_text(encoding="utf-8")
    assert "Failing tests" not in text
    assert "offending line" in text


def test_real_pytest_deliberate_failure_names_the_test(tmp_path):
    """End-to-end proof: real pytest, one deliberately failing test.

    This is the acceptance shape — the summary must name the failing
    test node id, recoverable from the summary file alone.
    """
    failing_test = tmp_path / "test_rel086_demo.py"
    failing_test.write_text(
        "def test_rel086_demo_failing():\n"
        "    assert 1 == 2, 'deliberate REL-086 failure'\n"
        "\n"
        "def test_rel086_demo_passing():\n"
        "    assert 1 == 1\n", encoding="utf-8")
    proc, summary_path = run_wrapper(
        tmp_path, wrapper_args(step="Run engine test suites with coverage")
        + ["--", sys.executable, "-m", "pytest", "-q", str(failing_test)])
    assert proc.returncode == 1
    text = summary_path.read_text(encoding="utf-8")
    assert "### Failing tests (1)" in text
    assert "- `test_rel086_demo.py::test_rel086_demo_failing`" in text
    assert "test_rel086_demo_passing" not in text.split("Failing tests")[1].split("```")[0]
    assert "1 failed, 1 passed" in text
