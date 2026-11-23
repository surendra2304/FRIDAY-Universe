"""Generic CI failure-summary wrapper (TASK-REL-085).

Wraps one validator step of the roster-validator / fleet-layout /
monorepo-policy checks so a failure is self-describing: the step log AND
the check-run summary name the failing check, the failing step, the exit
code and the offending lines — the precise failing step is recoverable
without sign-in-gated logs.

Why this exists: the #1377/#1378 roster failures produced empty
check-run summaries plus sign-in-gated logs, so every failure cost a
diagnosis cycle just to learn which check failed and what it objected
to. TASK-REL-081 already fixed the same gap for the fleet-layout gate's
regression-test step (scripts/ci_gate_test_runner.py); this wrapper
extends the same contract to the validator steps that were still bare:

- roster-validator (.github/workflows/collaboration-registry.yml):
  ``Validate collaboration registry`` and ``Run validator regression
  tests (TASK-REL-069 fixtures)``
- fleet-layout (.github/workflows/validate-monorepo.yml):
  ``Validate all ten agent roots and workflow syntax``
- monorepo-policy (.github/workflows/monorepo-validation.yml):
  ``Validate repository and workflow safety``

Usage (from the repository root)::

    python scripts/ci_failure_summary.py \\
        --check "roster-validator" \\
        --step "Validate collaboration registry" \\
        --workflow ".github/workflows/collaboration-registry.yml" \\
        --job "Validate roster, task IDs and file ownership" \\
        -- python scripts/validate_collaboration.py

TASK-REL-086 adds a ``--pytest`` mode for pytest test jobs
(.github/workflows/friday-universe-ci.yml, job ``test``): on failure the
summary additionally names every failing test (node id) found in the log,
parsed from pytest's ``FAILED``/``ERROR`` lines and its short test
summary — the exact failing test is recoverable without sign-in-gated
logs. REL-080 repair run 4 needed the exact failing test
(test_f3_peer_transport_exponential_backoff) and it was recoverable only
by reading a truncated log window via the MCP client, because annotations
and check-run output carry no test name; this mode closes that gap. When ``--pytest`` is off, the
behaviour is exactly the REL-085 contract above.

Contract (same as the REL-081 runner):

- the wrapped command's combined output is streamed to stdout in real
  time and teed to a log file under $RUNNER_TEMP (else the system temp
  dir), so it never pollutes the checkout;
- on success nothing is written to the step summary and the exit code
  is 0;
- on failure the summary names the run id, workflow, job, failing
  step, ref, commit and exit code, plus the last TAIL_LINES of the
  step log as the offending lines; the same summary is printed to
  stdout in a banner, and appended to $GITHUB_STEP_SUMMARY when
  running in GitHub Actions;
- the exit code is preserved exactly (the gate still fails);
- a failure to write the summary never masks the gate result, it
  only prints a warning.

Locally (no GITHUB_STEP_SUMMARY / GITHUB_RUN_ID) the wrapper behaves
the same except the summary goes only to stdout — the exit code is
identical.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

TAIL_LINES = 40
# Cap on failing tests listed in the summary: pytest can fail hundreds
# of tests at once (e.g. a broken fixture); the summary names the first
# MAX_FAILING_TESTS and says how many more there are.
MAX_FAILING_TESTS = 20

# pytest prints a failing test as "FAILED <nodeid> - <reason>" (and an
# erroring one as "ERROR <nodeid> - <reason>") both while running and in
# the "=== short test summary info ===" section at the end. The node id
# is the first whitespace-delimited token after the marker; it may carry
# "::" segments and "[...]" parameters, but never a space. The "-v" form
# ("path::test FAILED [ 50%]") has FAILED mid-line and is deliberately
# NOT matched — the short summary at the end always carries the FAILED
# form, so the parser stays exact instead of guessing at progress lines.
# Two ERROR shapes need care: "ERROR collecting <path>" (the token after
# ERROR is the literal word "collecting", the path follows it) and
# "ERROR at setup of <nodeid>" (token is "at"). The node-id shape check
# (".py" or "::" in the token) rejects both stray tokens; the short
# summary still carries the real node id for setup errors.
_FAILING_TEST_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)")
_COLLECT_ERROR_RE = re.compile(r"^ERROR collecting (\S+)")


def extract_failing_tests(text):
    """Return the failing pytest test node ids found in *text*, in order.

    Deduplicated, order-preserving: a test appears twice when pytest
    prints it once while running and once in the short summary. Returns
    [] for a log with no FAILED/ERROR line (passing run, crash, or
    abort after the tests passed, e.g. the REL-070 exit-134 shape).
    """
    seen = []
    for line in (text or "").splitlines():
        match = _COLLECT_ERROR_RE.match(line)
        if match:
            nodeid = match.group(1)
        else:
            match = _FAILING_TEST_RE.match(line)
            if not match:
                continue
            nodeid = match.group(1)
            if ".py" not in nodeid and "::" not in nodeid:
                continue
        if nodeid not in seen:
            seen.append(nodeid)
    return seen


def github_context(check, step, workflow_file, job):
    """Collect the run-identifying fields from the Actions environment."""
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = ""
    if run_id and repo:
        run_url = "%s/%s/actions/runs/%s" % (server, repo, run_id)
    return {
        "check": check,
        "step": step,
        "workflow_file": workflow_file,
        "job": job,
        "run_id": run_id or "unknown (not running in GitHub Actions)",
        "run_url": run_url,
        "workflow": os.environ.get("GITHUB_WORKFLOW", "unknown"),
        "ref": os.environ.get("GITHUB_REF", "unknown"),
        "sha": os.environ.get("GITHUB_SHA", "unknown"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
    }


def summary_lines(ctx, exit_code, tail, failing_tests=None):
    """Build the failure-summary markdown lines for the step summary.

    *ctx* is github_context(), *tail* the last lines of the step log.
    Always names the failing check, the failing step, the exit code and
    the offending lines. *failing_tests* (TASK-REL-086 ``--pytest`` mode)
    is the list from extract_failing_tests(): when non-empty the summary
    names each failing test; when the mode is on but the list is empty
    the summary says so explicitly, so a reader does not mistake a
    crash/abort for a passing run.
    """
    lines = []
    lines.append("## %s — step FAILED (exit %d)" % (ctx["check"], exit_code))
    lines.append("")
    lines.append("- Run id: %s" % ctx["run_id"])
    if ctx["run_url"]:
        lines.append("- Run: %s" % ctx["run_url"])
    lines.append("- Workflow: %s (`%s`)" % (ctx["workflow"], ctx["workflow_file"]))
    lines.append("- Job: %s" % ctx["job"])
    lines.append("- Failing step: %s" % ctx["step"])
    lines.append("- Ref: %s (attempt %s)" % (ctx["ref"], ctx["attempt"]))
    lines.append("- Commit: %s" % ctx["sha"])
    lines.append("- Exit code: %d" % exit_code)
    lines.append("")
    if failing_tests is not None:
        if failing_tests:
            shown = failing_tests[:MAX_FAILING_TESTS]
            lines.append("### Failing tests (%d)" % len(failing_tests))
            lines.append("")
            for nodeid in shown:
                lines.append("- `%s`" % nodeid)
            if len(failing_tests) > len(shown):
                lines.append("- ... and %d more (see the log tail below)"
                             % (len(failing_tests) - len(shown)))
            lines.append("")
        else:
            lines.append("### Failing tests")
            lines.append("")
            lines.append("- None identified in the log — this is not a "
                         "test failure with a name: a collection error, "
                         "a crash, or an abort after the tests passed "
                         "(see the log tail below).")
            lines.append("")
    lines.append("### Offending lines (last %d lines of the step log)" % len(tail))
    lines.append("")
    lines.append("```")
    lines.extend(tail)
    lines.append("```")
    return lines


def write_step_summary(lines):
    """Append markdown to the GitHub step summary when running in Actions.

    Locally GITHUB_STEP_SUMMARY is unset and this is a no-op; a failure
    to write never masks the gate result, it only prints a warning.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:  # noqa: BLE001 - summary write must not fail the gate
        print("REL-085 WARNING: could not write to GITHUB_STEP_SUMMARY: %s" % e)


def run_command(argv, log_path):
    """Run *argv*, tee its combined output to stdout and *log_path*.

    Returns the process exit code. Output is streamed line by line so
    a long step stays visible in real time, and the file holds the same
    bytes for the tail. A command that cannot start at all is reported
    as exit 127 with the error in the log.
    """
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
    except OSError as e:
        parent = os.path.dirname(os.path.abspath(log_path))
        os.makedirs(parent, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as log:
            log.write("REL-085: could not start command %r: %s\n" % (argv, e))
        print("REL-085: could not start command %r: %s" % (argv, e))
        return 127
    parent = os.path.dirname(os.path.abspath(log_path))
    os.makedirs(parent, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log:
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()
        return proc.returncode


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Run a CI validator step and, on failure, write a "
                    "self-describing summary (failing check + offending "
                    "lines) to stdout and $GITHUB_STEP_SUMMARY.")
    parser.add_argument("--check", required=True,
                        help="failing-check name, e.g. roster-validator")
    parser.add_argument("--step", required=True,
                        help="failing step name as shown in the workflow")
    parser.add_argument("--workflow", required=True,
                        help="workflow file, e.g. .github/workflows/collaboration-registry.yml")
    parser.add_argument("--job", required=True,
                        help="job name as shown in the workflow")
    parser.add_argument("--tail-lines", type=int, default=TAIL_LINES,
                        help="offending lines kept in the summary (default 40)")
    parser.add_argument("--pytest", action="store_true",
                        help="pytest mode (TASK-REL-086): parse the log for "
                             "failing test node ids and name them in the "
                             "summary, before the log tail")
    parser.add_argument("--log", default=None,
                        help="log file path (default $RUNNER_TEMP/ci-failure-summary-<check>.log)")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="command to run, after --")
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("no command to run (put it after --)")
    return args, command


def main(argv=None):
    args, command = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.log is None:
        temp_dir = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
        safe_check = "".join(c if c.isalnum() or c in "-_" else "_" for c in args.check)
        log_path = os.path.join(temp_dir, "ci-failure-summary-%s.log" % safe_check)
    else:
        log_path = args.log
    exit_code = run_command(command, log_path)
    if exit_code == 0:
        print("REL-085: %s step passed (exit 0)." % args.check)
        return 0
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            full_log = f.read()
    except OSError as e:
        full_log = "(REL-085: could not read log file %s: %s)" % (log_path, e)
    tail = full_log.splitlines()[-args.tail_lines:]
    ctx = github_context(args.check, args.step, args.workflow, args.job)
    failing = extract_failing_tests(full_log) if args.pytest else None
    lines = summary_lines(ctx, exit_code, tail, failing)
    print()
    print("=" * 72)
    print("REL-085: %s step FAILED (exit %d) — failure summary:" % (args.check, exit_code))
    print("=" * 72)
    print("\n".join(lines))
    write_step_summary(lines)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
