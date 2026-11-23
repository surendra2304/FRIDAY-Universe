# TASK-REL-086 — Test job prints the failing test name + log tail into the check-run summary

- **Owner:** Muse 9
- **Branch:** muse9/task-rel-086
- **Claim:** issue #1483 comment 7106843249, 2026-11-23 ~21:45 IST, on
  coordinator assignment ~18:30 IST (queue INT-023 -> REL-086 -> INT-033;
  INT-033 merged cfe211cf). Claim PR #1526 merged ceaa53c.
- **Status:** implemented + tested locally; work PR open, CI running.

## Problem

REL-080 repair run 4 needed the exact failing test
(test_f3_peer_transport_exponential_backoff) and it was recoverable only
by reading a truncated log window via the MCP client — annotations and
check-run output carry no test name. The test job in
`.github/workflows/friday-universe-ci.yml` ran its pytest steps bare: on
failure the reader got an exit code and a long log, and had to hunt the
failing test inside it. REL-081 fixed the same gap for the fleet-layout
gate's regression step (`scripts/ci_gate_test_runner.py`) and REL-085
added the generic wrapper (`scripts/ci_failure_summary.py`) for validator
steps — but neither covered a pytest test job, and a 40-line tail alone
does not name the failing test when the tail is coverage output.

## Change

`--pytest` mode on the generic wrapper `scripts/ci_failure_summary.py`
(same contract as REL-085; unchanged when the flag is off):

- `extract_failing_tests(log)` parses pytest's `FAILED <nodeid>` /
  `ERROR <nodeid>` lines and the short test summary, deduplicated and
  order-preserving. It handles parametrized node ids (`test_x[param]`),
  collection errors (`ERROR collecting <path>`), and rejects the stray
  tokens of `ERROR at setup of ...` (the short summary still carries the
  real node id). `-v` progress lines (`path::test FAILED [ 50%]`) are
  deliberately not matched — the short summary at the end is the exact
  source. A long failure list is capped at 20 named tests with a
  "... and N more" line.
- On failure the summary gains a `### Failing tests (N)` section listing
  each node id, before the log tail. When `--pytest` is on but no test
  name is found (collection error, crash, or abort after the tests
  passed — the REL-070 exit-134 shape) the summary says so explicitly,
  so a reader does not mistake a crash for a passing run.
- Exit code preserved exactly; a summary-write failure never masks the
  result; on success nothing is written and the exit code is 0.

Wired through the wrapper (4 pytest steps, 1 workflow — the whole `test`
job in `.github/workflows/friday-universe-ci.yml`):

| Step | Command wrapped |
|---|---|
| Run engine test suites with coverage | repo-root `pytest` (9 engine suites + coverage gate) |
| Run Memora vector tenant and transaction regressions | both `pytest` invocations (vector suite + viking suite, via `../scripts/` from the step's `Memora` working directory) |
| Run Cortex tier-1 tests | `pytest -q` on the tier-1 files — this is the step that runs test_f3_peer_transport_exponential_backoff, the motivating test |
| Start API server and run HTTP tests | the `pytest` invocation (background uvicorn + `kill %1` unchanged; a failing wrapper aborts the step before `kill %1`, exactly as a failing pytest does today) |

The fleet-layout regression step keeps its REL-081 runner; the validator
steps keep their REL-085 wiring. Out of scope by design: the lint steps
(not pytest) and the coverage-gate step (not a test run).

New tests `tests/test_rel086_test_failure_summary.py` (pytest style, same
as REL-081's suite), added to the contracts workflow file list in the
same PR per the standing orders.

## Verification (local, first-hand, 2026-11-23 ~22:40 IST)

New suite `tests/test_rel086_test_failure_summary.py`: **14/14 pass**
(venv pytest 9.2.0), covering the parser (FAILED/ERROR order + dedup,
parametrized ids, `-v` lines ignored, collection-error path, setup-error
stray token, passing/abort logs -> empty), the summary sections (list +
20-cap + "none identified" + unchanged non-pytest mode), and subprocess
integration (fake failing pytest -> exit 1 + named tests; passing -> exit
0 + no summary; non-pytest failure -> no section; **real pytest on a
deliberately failing test file -> exit 1, summary names
`test_rel086_demo.py::test_rel086_demo_failing`**).

Deliberate-failure proof, real pytest, wrapper run exactly as the test
job runs it (GITHUB_STEP_SUMMARY pointed at a file):

```
$ python3 scripts/ci_failure_summary.py --pytest --check test-job \
    --step "Run engine test suites with coverage" \
    --workflow .github/workflows/friday-universe-ci.yml --job test \
    -- python -m pytest -q test_rel086_demo.py
F.                                  [100%]
FAILED test_rel086_demo.py::test_rel086_demo_failing - AssertionError: delibe...
1 failed, 1 passed in 0.02s
wrapper exit: 1
```

The summary file written by that run:

```
## test-job — step FAILED (exit 1)
- Run id: 45123456789
- Workflow: FRIDAY Universe CI/CD (`.github/workflows/friday-universe-ci.yml`)
- Job: test
- Failing step: Run engine test suites with coverage
- Exit code: 1

### Failing tests (1)

- `test_rel086_demo.py::test_rel086_demo_failing`

### Offending lines (last 13 lines of the step log)
... (failure body + short summary, as printed above)
```

Regression checks, same run: REL-085 standalone suite
`scripts/tests/test_ci_failure_summary.py` **20/20 pass**; REL-081 suite
`tests/test_rel081_gate_failure_summary.py` **10/10 pass**. Both edited
workflow files parse as YAML. Test-collection guard
(`scripts/ci_test_collection_audit.py --base origin/main`, after commit):
PASS — the new test file is collected (contracts list + validate-monorepo
`pytest -q tests` directory run).

## Acceptance

On a deliberately failing branch, the test check-run summary names the
failing test and shows its log tail, recoverable without sign-in-gated
logs. Met by the deliberate-failure proof above (real pytest, exit 1
preserved, failing test named in the summary file); CI on the work PR is
the live confirmation that the four wired steps run green through the
wrapper.

## Board

`docs/collaboration/WORK_BOARD.yaml`: TASK-REL-086 CLAIMED -> IN_REVIEW,
owner muse_9, branch muse9/task-rel-086, pr 1537.

## Work PR

- PR number: 1537 (https://github.com/surendra2304/FRIDAY-Universe/pull/1537).
- Head sha at PR creation: 5e4be596a549a9606d47feece88817e7bb803f49
  (branch ref updated after with the board-pr-number commit; final head
  cited in the hub status post).
- Base: main a96c7bd at branch time.
