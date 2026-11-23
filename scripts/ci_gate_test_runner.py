"""Fleet-layout gate test runner (TASK-REL-081).

Wraps the ``Run regression tests`` step of the fleet-layout gate
(.github/workflows/validate-monorepo.yml) so a failure is self-describing:
the step log AND the run summary name the run id, the failing step, the
exit code and the log tail — no diagnosis cycle is needed to identify it.

Why this exists: TASK-REL-070 fixed the exit-134 (SIGABRT) interpreter-
shutdown race that failed this gate 10 times in the 2026-11-21/22 window
(CPython finalizing while Stratex supervision daemon threads were still
logging). The fix joins those threads at session end, but a recurrence is
still possible (an incomplete fix, or a new shutdown race), and every
occurrence used to cost a diagnosis cycle: the step log is long, GitHub
truncates it, and the abort happens *after* every test passes, so the
failure looks like a passing run that died. This runner makes the next
occurrence identify itself:

- the exit code is preserved (the gate still fails),
- the summary names the run id, workflow, job, step, ref and sha,
- the last TAIL_LINES of the pytest log are printed in the summary,
- exit 134 gets an explicit EXIT-134 RECURRENCE banner plus a check of
  the known REL-070 signature markers, and a pointer to the REL-070
  evidence doc, so the reader knows immediately whether this is the
  known shutdown race or a new abort.

Locally (no GITHUB_STEP_SUMMARY / GITHUB_RUN_ID) the runner behaves the
same except the summary goes only to stdout — the exit code is identical.
The log file lives under $RUNNER_TEMP in Actions, else the system temp
dir, so it never pollutes the checkout.
"""

import os
import re
import subprocess
import sys
import tempfile

STEP_NAME = "Run regression tests"
WORKFLOW_FILE = ".github/workflows/validate-monorepo.yml"
JOB_NAME = "Validate fleet layout and mirror safety"
TAIL_LINES = 40
REL070_DOC = "docs/collaboration/TASK-REL-070-EXIT-134-ROOT-CAUSE.md"

EXIT_134 = 134

# Substrings of the REL-070 failure signature (from run 45082613824 and the
# 9 other identical occurrences). If the tail contains them, the abort is
# the known interpreter-shutdown daemon-thread race; if it does not, the
# abort is a NEW cause and must be diagnosed as one.
SIGNATURE_MARKERS = (
    "Fatal Python error: _enter_buffered_busy",
    "possibly due to daemon threads",
    "at interpreter shutdown",
    "friday_supervision.py",
    "(core dumped)",  # shell prints "Aborted  (core dumped)" (two spaces)
    "I/O operation on closed file",
)

# "3728 passed, 72 skipped, 261 warnings, 8 subtests passed in 109.51s ..."
_PYTEST_SUMMARY_RE = re.compile(r"^\d+ passed.* in [\d.]+s", re.MULTILINE)


def detect_exit134_signature(text):
    """Return the REL-070 signature markers found in *text* (possibly [])."""
    return [m for m in SIGNATURE_MARKERS if m in text]


def pytest_summary_line(text):
    """Return the pytest result summary line (``N passed ...``), or None."""
    match = _PYTEST_SUMMARY_RE.search(text or "")
    return match.group(0).strip() if match else None


def github_context():
    """Collect the run-identifying fields from the Actions environment."""
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = ""
    if run_id and repo:
        run_url = "%s/%s/actions/runs/%s" % (server, repo, run_id)
    return {
        "run_id": run_id or "unknown (not running in GitHub Actions)",
        "run_url": run_url,
        "workflow": os.environ.get("GITHUB_WORKFLOW", "unknown"),
        "job": JOB_NAME,
        "step": STEP_NAME,
        "ref": os.environ.get("GITHUB_REF", "unknown"),
        "sha": os.environ.get("GITHUB_SHA", "unknown"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
    }


def summary_lines(ctx, exit_code, tail, full_log=""):
    """Build the failure-summary markdown lines for the step summary.

    *ctx* is github_context(), *tail* the last lines of the step log.
    Always names run id, step, exit code and tail; exit 134 additionally
    gets the recurrence banner and the REL-070 signature check.
    """
    lines = []
    if exit_code == EXIT_134:
        lines.append("## Fleet-layout gate — EXIT-134 RECURRENCE (test step failed)")
    else:
        lines.append("## Fleet-layout gate — test step FAILED (exit %d)" % exit_code)
    lines.append("")
    lines.append("- Run id: %s" % ctx["run_id"])
    if ctx["run_url"]:
        lines.append("- Run: %s" % ctx["run_url"])
    lines.append("- Workflow: %s (`%s`)" % (ctx["workflow"], WORKFLOW_FILE))
    lines.append("- Job: %s" % ctx["job"])
    lines.append("- Failing step: %s" % ctx["step"])
    lines.append("- Ref: %s (attempt %s)" % (ctx["ref"], ctx["attempt"]))
    lines.append("- Commit: %s" % ctx["sha"])
    lines.append("- Exit code: %d" % exit_code)
    summary = pytest_summary_line(full_log)
    if summary:
        lines.append("- Pytest result line: `%s`" % summary)
        if exit_code == EXIT_134:
            lines.append("  (tests passed — the abort happened at interpreter "
                         "shutdown, after the summary; this is the REL-070 "
                         "failure shape, not a test failure)")
    lines.append("")
    if exit_code == EXIT_134:
        found = detect_exit134_signature(full_log)
        lines.append("### Is this the known REL-070 shutdown race?")
        lines.append("")
        if len(found) == len(SIGNATURE_MARKERS):
            lines.append("- YES — all %d REL-070 signature markers present in "
                         "the log." % len(SIGNATURE_MARKERS))
        elif found:
            lines.append("- PARTIAL — %d of %d REL-070 signature markers "
                         "present: %s." % (len(found), len(SIGNATURE_MARKERS),
                                           ", ".join("`%s`" % m for m in found)))
            lines.append("  Missing: %s." % ", ".join(
                "`%s`" % m for m in SIGNATURE_MARKERS if m not in found))
        else:
            lines.append("- NO — none of the REL-070 signature markers are in "
                         "the log. This is a NEW abort cause: diagnose it as "
                         "one, do not assume the REL-070 race.")
        lines.append("- Root cause + fix history: `%s`." % REL070_DOC)
        lines.append("")
    lines.append("### Log tail (last %d lines of the test step)" % TAIL_LINES)
    lines.append("")
    lines.append("```")
    lines.extend(tail)
    lines.append("```")
    return lines


def write_step_summary(lines):
    """Append markdown to the GitHub step summary when running in Actions.

    Same contract as the REL-076 guard (scripts/ci_test_collection_audit.py):
    locally GITHUB_STEP_SUMMARY is unset and this is a no-op; a failure to
    write never masks the gate result, it only prints a warning.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:  # noqa: BLE001 - summary write must not fail the gate
        print("REL-081 WARNING: could not write to GITHUB_STEP_SUMMARY: %s" % e)


def run_command(argv, log_path):
    """Run *argv*, tee its combined output to stdout and *log_path*.

    Returns the process exit code. Output is streamed line by line so a
    long suite stays visible in real time, and the file holds the same
    bytes for the tail.
    """
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()
        return proc.returncode


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Usage: ci_gate_test_runner.py [--log PATH] [--] [pytest args...]
    # Default command is the gate's regression run.
    log_path = None
    command = [sys.executable, "-m", "pytest", "-q", "tests"]
    i = 0
    while i < len(argv):
        if argv[i] == "--log" and i + 1 < len(argv):
            log_path = argv[i + 1]
            i += 2
            continue
        if argv[i] == "--":
            command = argv[i + 1:] or command
        else:
            command = argv[i:]
        break
    if log_path is None:
        temp_dir = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
        log_path = os.path.join(temp_dir, "gate-test-output.log")
    exit_code = run_command(command, log_path)
    if exit_code == 0:
        print("REL-081: test step passed (exit 0).")
        return 0
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            full_log = f.read()
    except OSError as e:
        full_log = "(REL-081: could not read log file %s: %s)" % (log_path, e)
    tail = full_log.splitlines()[-TAIL_LINES:]
    lines = summary_lines(github_context(), exit_code, tail, full_log)
    print()
    print("=" * 72)
    print("REL-081: test step FAILED (exit %d) — failure summary:" % exit_code)
    print("=" * 72)
    print("\n".join(lines))
    write_step_summary(lines)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
