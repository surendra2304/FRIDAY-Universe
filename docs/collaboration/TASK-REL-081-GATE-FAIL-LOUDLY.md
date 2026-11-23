# TASK-REL-081 — Fleet-layout gate fails loudly (run id + log tail on exit-134 recurrence)

**Worker:** Muse 9. **Branch:** `muse9/task-rel-081`. **Base:** main `1f8ed4f`.
**Assignment:** coordinator watch 7095390023 (2026-11-23 ~13:37–14:15 IST), queue head
REL-081 → FUT-023 → INT-023 final compilation (due 11-27).
**Claim:** issue #35 comment 7095427863.
**Lineage:** follow-on to TASK-REL-070 (exit-134 root cause + fix, PR #1452 merged
27b7d4e2a); sibling of TASK-REL-076 (contracts-guard self-describing failures,
PR #1461 merged ca2c586f, proof PR #1463 [DO NOT MERGE] open by design).

## Verdict

Implemented. The fleet-layout gate's `Run regression tests` step is now wrapped in
`scripts/ci_gate_test_runner.py`, which preserves the exit code and, on any
failure, writes a self-describing summary — run id, run URL, workflow, job,
failing step, ref, commit, exit code, the pytest result line, and the last 40
lines of the step log — to the step log and to `$GITHUB_STEP_SUMMARY`. An
exit-134 recurrence additionally gets an explicit `EXIT-134 RECURRENCE`
banner, a check of all 6 REL-070 signature markers against the log, and a
pointer to the REL-070 root-cause doc, so the reader knows at a glance whether
this is the known interpreter-shutdown daemon-thread race or a new abort.

## What changed

| File | Change |
|---|---|
| `scripts/ci_gate_test_runner.py` (new, ~230 lines) | Runs `python -m pytest -q tests`, tees combined output to stdout and a log file (under `$RUNNER_TEMP`, else the system temp dir — never the checkout), preserves the exit code, and on failure prints + writes the summary. Pure functions (`detect_exit134_signature`, `pytest_summary_line`, `summary_lines`, `github_context`) so the summary logic is unit-testable without a CI run. |
| `.github/workflows/validate-monorepo.yml` | `Run regression tests` step now runs `python scripts/ci_gate_test_runner.py` instead of `python -m pytest -q tests`. Same env (`DATABASE_URL` mock), same command inside the runner, exit code preserved — the gate fails exactly as before, only louder. |
| `tests/test_rel081_gate_failure_summary.py` (new, 10 tests) | Unit tests for signature detection, summary-line extraction and summary content (134 banner, signature verdicts, no-banner for exit 1); subprocess integration tests running the runner against fake pytest programs (pass / exit 1 / real REL-070 log + exit 134) and a no-GitHub-env local run. |
| `.github/workflows/owner-workflows.yml` | New test file added to the contracts workflow's explicit pytest list (standing order 5). It is also collected by validate-monorepo.yml's directory run (`pytest -q tests`), so the REL-068 guard passes for it. |

## Design decisions

- **Runner, not a step-level `if: failure()` block.** The tail and the
  signature check need the step's own output, which a later step can only get
  from a log file; teeing inside the runner keeps the whole mechanism in one
  tested Python file instead of shell spread across YAML.
- **Exit code preserved, nothing swallowed.** The runner returns pytest's exit
  code unchanged; a summary-write failure prints a warning and never masks
  the gate result (same contract as the REL-076 guard).
- **Signature check is a verdict, not a diagnosis.** All 6 markers →
  "known REL-070 race"; some → "PARTIAL" with the missing markers listed;
  none → "NEW abort cause — diagnose it as one". The summary never claims a
  root cause the log does not support.
- **"Tests passed" is called out on a 134.** The REL-070 failure shape is
  `N passed` first, abort after — the summary quotes the pytest result line
  and says so explicitly, because that is the fact that used to mislead
  readers into thinking the run was green.

## Verification (local, this run)

- New tests: **10/10 pass** locally (`pytest -q
  tests/test_rel081_gate_failure_summary.py`, venv, 0.32 s).
- Smoke, pass path: runner over a fake passing pytest → exit 0, no summary
  written.
- Smoke, exit-134 path: runner over a fake pytest printing the real REL-070
  log text and exiting 134 → exit **134** preserved; summary contains
  `EXIT-134 RECURRENCE`, run id `45123456789`, run URL, failing step, exit
  code, and `YES — all 6 REL-070 signature markers present in the log.`
- Smoke, exit-1 path: summary written, exit 1 preserved, no 134 banner.
- Full suite through the runner (local): ABANDONED, no result — the VM's
  shared CPU throttled the run (1:23 CPU-min in ~8 min wall, 0 bytes of
  pytest output because pytest block-buffers when piped) and the exec
  session stalled in `pending_user_confirmation`, which cannot be answered
  on a detached run; killed the tree (no pytest processes remain). This is
  NOT a failure of the change — the new tests (10/10) and the smoke paths
  above verify the runner, and the authoritative full-suite check is the
  work PR's CI, which runs the same suite through the same runner on a
  dedicated Actions runner. Recorded plainly so the gap is visible.

## Verification (CI)

- Work PR: #(to be filled when opened) — CI result recorded here before merge.
- Proof of a forced recurrence: a [DO NOT MERGE] proof PR from this branch
  plus a test that starts a never-joined daemon thread logging in a loop, so
  the real gate aborts with a real exit 134 at interpreter shutdown and the
  new summary appears on the run page. Run id + summary text recorded here
  once observed. (Pattern follows REL-076 proof PR #1463.)

## Open questions

- None for the implementation. The proof run's recurrence rate is the only
  unknown: the REL-070 race aborted on ~10 of 12 failed gate runs in the
  2026-11-21/22 window, so a tight logging loop at shutdown should reproduce
  it deterministically; if the proof run stays green, the proof test's loop
  interval is the first thing to tighten.
