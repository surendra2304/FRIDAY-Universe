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
import subprocess
import sys
import tempfile

TAIL_LINES = 40


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


def summary_lines(ctx, exit_code, tail):
    """Build the failure-summary markdown lines for the step summary.

    *ctx* is github_context(), *tail* the last lines of the step log.
    Always names the failing check, the failing step, the exit code and
    the offending lines.
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
    lines = summary_lines(ctx, exit_code, tail)
    print()
    print("=" * 72)
    print("REL-085: %s step FAILED (exit %d) — failure summary:" % (args.check, exit_code))
    print("=" * 72)
    print("\n".join(lines))
    write_step_summary(lines)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
