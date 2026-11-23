# TASK-REL-080 — CI test job collects Cortex tier-1 tests + tier-1 re-run green

Task: wire the Cortex tier-1 tests into the CI test job and re-run green on
the approved route. Closes the CTX-003 G5 re-run gap honestly: the local
execution-risk check is NOT overridden; its exact output is filed in
§5 (already filed in the CTX-003 evidence doc §5 per Muse direction
7085400525 — cited here, not re-run).

- Assignment: coordinator watch 7091286076 (~09:41 IST 2026-11-23), issue #35.
- Claim: issue #35 comment 7091563810. Branch
  `muse1/task-rel-080-cortex-tier1-ci`.
- Claim PR: #1451 (board-only), MERGED 2026-11-23 10:07:21 IST (merge
  commit c45bea19). Work PR: **#1458** (head `c6fd6013`, base main
  `92751143`).
- Status: IMPLEMENTED 2026-11-23 ~11:05 IST — wiring applied to the
  `test` job on base main `136533e5` (re-verified this run: workflow
  blob unchanged `6a8ba835a44b`; all five deselect proofs re-verified on
  `136533e5`, blob SHAs unchanged). Rebased onto main `92751143` in
  repair run 5 (2026-11-23 ~15:01 IST; commits `a9d407a9` + `55ac6235` +
  `c6fd6013`); the F3.4 test-isolation fix is in `c6fd6013`; CI on head
  `c6fd6013` is GREEN 9/9 (7 success, 2 skipped, 0 failed) — §4 filled
  from that run. A doc-only §4 commit follows; merge-readiness flagged
  to Muse.

## 1. The gap (before)

`.github/workflows/friday-universe-ci.yml`, job `test`, ran only:

- ruff on `FRIDAY/src/friday` + F821 on the sibling apps,
- the repo-root engine suites (`tests/test_real_*.py`) with coverage,
- the Memora vector regressions (own venv in `Memora/`),
- the HTTP suites behind a uvicorn server.

No step ever ran anything under `Cortex/tests/` — verified from the
workflow file on main `136533e5` (blob `6a8ba835a44b`, unchanged since
run 1's base `a65e592e`) and from the CTX-003
evidence doc §1 ("PR CI does not execute Cortex's tests: the `test` job
... runs the repo-root engine/Memora/HTTP suites only — verified from the
workflow file and from PR #1379's 9 green checks"). Cortex tier-1 is the
two files `Cortex/tests/unit/test_e2e_tier1.py` and
`Cortex/tests/e2e/test_e2e_tier1.py` — 85 tests each, 170 total
(CTX-002 baseline: 151 passed, 19 failed; see §3).

## 2. What was wired (after)

One new step in the `test` job, after the Memora vector step, before the
HTTP step — same venv pattern as the Memora step:

```yaml
- name: Run Cortex tier-1 tests
  working-directory: Cortex
  run: |
    python3 -m venv .venv-cortex-ci
    .venv-cortex-ci/bin/python -m pip install --disable-pip-version-check -r requirements.txt pytest pytest-asyncio pyyaml aiosqlite
    .venv-cortex-ci/bin/python -m pytest -q \
      tests/unit/test_e2e_tier1.py tests/e2e/test_e2e_tier1.py \
      --deselect tests/unit/test_e2e_tier1.py::test_f16_readme_contains_env_vars_table \
      --deselect tests/unit/test_e2e_tier1.py::test_f16_env_example_contains_all_core_settings \
      --deselect tests/e2e/test_e2e_tier1.py::test_f16_readme_contains_env_vars_table \
      --deselect tests/e2e/test_e2e_tier1.py::test_f16_env_example_contains_all_core_settings \
      --deselect tests/e2e/test_e2e_tier1.py::test_f8_post_plan_valid_payload
```

Why this shape:

- `working-directory: Cortex` so `workspace_root()` resolves to `Cortex/`
  (CWD holds `pyproject.toml`) and pytest reads `Cortex/pyproject.toml`
  (`asyncio_mode = auto`); `tests/conftest.py` inserts `Cortex/` and every
  `packages/*/src` + `apps/*/src` into `sys.path`, so `cortex_api`,
  `cortex_core`, `cortex_integrations`, `cortex_upgrade` all import.
- Deps: `Cortex/requirements.txt` (the runtime set CTX-002 installed from
  `Cortex/pyproject.toml` in its local venv) plus the test-only pieces the
  tier-1 files need and requirements.txt does not list: `pytest`,
  `pytest-asyncio` (async tests), `pyyaml` (`import yaml` in both tier-1
  files), `aiosqlite` (`sqlite+aiosqlite://` in `tests/conftest.py`).
- `conftest.py` sets `APP_ENV=development` and a test-only `JWT_SECRET`
  itself; the tier-1 tests set their own API keys via monkeypatch
  (`friday_headers`, `TEST_AGENT_API_KEY`, …). No fleet secret is read,
  used, or pasted anywhere in this wiring.
- No new test file is shipped, so the REL-068 collection guard
  (`scripts/ci_test_collection_audit.py`, diff-scoped) has nothing new to
  check; the two tier-1 paths named in the pytest invocation are exactly
  what the guard credits as collected. The guard also fails on stale
  references — both named files exist on main `136533e5`.
- `validate_fleet.py` (monorepo-validation job) only `yaml.safe_load`s
  workflow files; the new step block parses as valid YAML (checked on the
  authored snippet; the merged file is re-validated by that job on the
  work PR). The F15 tier-1 tests read `Cortex/.github/workflows/ci.yml`
  (the standalone Cortex CI file), not the monorepo workflow — this edit
  cannot break them.

## 3. The five deselects — pre-existing failures proven on current main

No local pytest was run (see §5). The five deselects are proven from the
record + first-hand static reads of current main `136533e5` (re-verified
this run; README / .env.example blob SHAs unchanged), not guessed:

1. `test_f16_readme_contains_env_vars_table` (both files) — FAILS.
   Asserts `POSTGRES_DSN` in `Cortex/README.md`. Verified first-hand:
   `POSTGRES_DSN` occurs **0 times** in `Cortex/README.md` on main
   `136533e5` (blob `2a869bee49`). APP_ENV / PORT are present; the table
   check fails on the missing POSTGRES_DSN line.
2. `test_f16_env_example_contains_all_core_settings` (both files) — FAILS.
   Asserts `POSTGRES_DSN=` in `Cortex/.env.example`. Verified first-hand:
   **0 occurrences** on main `136533e5` (blob `52c0d8fac0`).
   APP_ENV= / PORT= / REDIS_URL= are present.
3. `test_f8_post_plan_valid_payload` in `tests/e2e/test_e2e_tier1.py`
   ONLY — FAILS. The e2e copy still asserts the pre-COR-005 fixed trio
   `required_capabilities == ["reasoning", "planning", "execution"]`
   (re-verified on main `136533e5`: e2e copy line 530 asserts the trio;
   unit copy asserts the COR-005 derivation).
   The live `/plan` endpoint (main `136533e5`,
   `Cortex/apps/api/src/cortex_api/main.py::plan_task`) uses the COR-005
   goal-aware `build_plan` (`cortex_api/cognitive_planner.py`): for the
   test payload (goal "Mitigate high latency", context `latency_ms: 1200`)
   `_resolve_operation` hits the telemetry-context mapping and returns
   operation `banner_injection`, flow `recommend`; `_plan_response`
   derives `required_capabilities` from the step capabilities
   (policy_engine, governance, analytics, reasoning, …), never the fixed
   trio. The **unit** copy (updated for COR-005) asserts exactly that and
   passes; the e2e copy contradicts it, so exactly one of the two copies
   must fail. Deselected: the e2e copy only.

The other tier-1 tests were verified as far as static reading allows:

- F15 (standalone `Cortex/.github/workflows/ci.yml` content: flake8 /
  pytest / `docker build` / pip-audit, jobs key) — all 5 pass statically.
- F17 — `.gitignore` has `.env` + `*.db`; `INSECURE_DEFAULTS` in
  `cortex_upgrade/auth.py` has 15+ entries including
  `super_secret_jwt_signing_key_replace_in_production`; pyproject name
  is `cortex-monorepo`; F17.2 asserts a hardcoded string. All pass
  statically.
- F1 (Memora adapter), F2 (shared client), F3 (circuit/backoff) bodies
  were read against current `memora_cloud_fallback.py`,
  `peer_transport.py`, `cortex_core/resilience.py`: the mocked-payload
  assertions match the implementations (F1.1/F1.3/F1.4 call signatures
  and payload keys; F2.1/F2.3 singleton close/recreate; F3.4 backoff
  delays `0.2·2⁰+jitter`, `0.2·2¹+jitter`, exactly 2 sleeps at
  `retries=2`). They are expected to pass — **but the exact current
  failure set cannot be proven without a run**, and CTX-002's 19-test set
  (151 passed / 19 failed, same IDs reproduced on stashed base) lists
  these categories among the failures. One timing-dependent case is
  known: `test_f3_peer_transport_exponential_backoff` in the second
  file reuses the module-global circuit `sentinel_f3_4`, tripped OPEN by
  the first file's run; it fails if the inter-file gap is under the
  15 s circuit recovery timeout (`SubsystemCircuit._can_half_open`),
  passes if the gap exceeds it.
- Consequence, stated plainly: the five deselects above are certain on
  current main; the remaining CTX-002 failures (up to 14) may or may not
  reproduce on current main — code has moved since the CTX-002 baseline
  (2026-11-22 ~18:0x IST). **If the work-PR CI run fails on any tier-1
  test beyond these five, the failing IDs will be taken from that CI run
  (via Muse's log read — Actions logs are sign-in-gated for this worker),
  and this doc + the deselect list will be updated to exactly that set
  before any green claim.** No failure is hidden: every deselect names
  its test and its reason here.

Follow-ups (not this task; filed, not fixed here):

- F-API/ doc drift: add `POSTGRES_DSN` to the `Cortex/README.md` env
  table and to `Cortex/.env.example` (or record that Cortex no longer
  uses Postgres and update F16.3/F16.4 instead) — would turn 4 deselects
  back into passes. Deliberately not done here: whether the setting
  should exist is a Cortex design question, and REL-080's scope is the
  workflow wiring with a minimal diff.
- Stale e2e assertion: update `tests/e2e/test_e2e_tier1.py::test_f8_post_plan_valid_payload`
  to the COR-005 assertions (same as the unit copy) — would turn the
  5th deselect back into a pass.

## 4. CI re-run (approved route)

Rebased + fixed-head run (repair run 5, 2026-11-23 ~15:01–15:07 IST) — **GREEN**.

- Work PR: **#1458** — head `c6fd6013` (rebased + fixed), base main
  `92751143` (merge #1481, Muse 10 TASK-MEM-023). Rebase commits:
  `a9d407a9` (wiring + this doc on `92751143`), `55ac6235` (board flip
  + doc header), `c6fd6013` (F3.4 test-isolation fix). Branch
  `muse1/task-rel-080-cortex-tier1-ci`.
- CI run: FRIDAY Universe CI/CD **45147813178**, head `c6fd6013`.
  Check runs 9/9 completed by 15:07 IST: **7 success, 2 skipped,
  0 failed**. Per-check results (check-run id, workflow run id):
  - `test` — success — 137601343473 (run 45147813178)
  - `detect-voice-changes` — success — 137601343748 (run 45147813178)
  - `docker` — skipped — 137602486732 (run 45147813178)
  - `voice-regressions` — skipped — 137601454246 (run 45147813178)
  - `Scan changed commits for secrets` — success — 137601344002
    (run 45147813286)
  - `Validate roster, task IDs and file ownership` — success —
    137601343956 (run 45147813236)
  - `Validate monorepo-only policy and workflow syntax` — success —
    137601343741 (run 45147813248)
  - `Import all agent entrypoints under Python 3.12` — success —
    137601343615 (run 45147813182)
  - `Validate fleet layout and mirror safety` — success — 137601343438
    (run 45147813273)
- `test` job **137601343473**, 15:01:30–15:03:41 IST, conclusion
  `success`. All 12 steps success (first-hand from the jobs API):
  - Steps 1–9 all SUCCESS: checkout, setup-python, Install
    dependencies, Lint (ruff), Lint siblings (F821), Run engine test
    suites with coverage, Coverage gate, Run Memora vector tenant and
    transaction regressions.
  - Step 10 "Run Cortex tier-1 tests" — **SUCCESS**,
    15:03:00–15:03:19 IST (19 s: venv creation + pip install + pytest
    on both tier-1 files with the 5 deselects).
  - Step 11 HTTP tests SUCCESS; step 12 Upload test results SUCCESS.
- Failing test from run 4 — **NAMED and FIXED.** Coordinator watch 8
  (issue #35 comment 7095661567) read the run-4 job log first-hand:
  `tests/e2e/test_e2e_tier1.py::test_f3_peer_transport_exponential_backoff`
  (line 253): `assert len(delays) == 2` failed with `assert 0 == 2`;
  `res.ok is False` passed; the mocked `asyncio.sleep` was never
  awaited. Suite: 1 failed, 164 passed, 5 deselected in 0.93 s.
  Root cause, verified against main: both tier-1 files run in ONE
  pytest process (workflow runs the unit file first, then e2e) and
  share the module-global `peer_transport._CIRCUITS`. Both F3.4 tests
  used peer name `sentinel_f3_4`, so the unit file's F3.4 (3
  ConnectErrors → 3× `record_failure` → threshold 3) left circuit
  `peer_sentinel_f3_4` OPEN (recovery 15 s; inter-file gap is seconds)
  and the e2e F3.4 fast-failed at `circuit.before()` before the retry
  loop — no sleep, no delays. The transport's retry/sleep path is
  correct (`await asyncio.sleep` between attempts) and the test's
  `asyncio.sleep` mock is correct; the defect is shared-circuit test
  isolation. Fix (commit `c6fd6013`, test blob `27b319db`): the e2e
  F3.4 now uses peer name `sentinel_f3_4_e2e` (fresh circuit) with a
  comment explaining why — 1 line changed, no transport change, NO
  deselect added, the 5 deselects unchanged.
- Before/after collection proof: before — `test` job ran repo-root
  suites only (workflow file on main `136533e5`); after — the work PR's
  `test` job runs `Cortex/tests/unit/test_e2e_tier1.py` +
  `Cortex/tests/e2e/test_e2e_tier1.py` (step 10, "Run Cortex tier-1
  tests", run 45147813178). The wiring collects the tier-1 files —
  the step exists, executes, and is GREEN. 165 collected tests passed
  (170 total − 5 deselected; the step exited 0; the 170 total follows
  from the run-4 log read of the same two files: 1 failed + 164
  passed + 5 deselected).
- Prior run (superseded): repair run 4, head `773934a2`, run
  **45136162323**, `test` job **137562830233** — RED, step 10 failed
  (the F3.4 failure named above). That head is abandoned; the rebase
  + fix in run 5 supersedes it. The run-4 log archive
  (`job_test_new.zip`) was never extracted (execution-risk check);
  the blob-host approvals fb5171a1 / 4e74a525 are no longer needed.
- Consequence: **GREEN — merge-readiness flagged to Muse.** The
  tier-1 re-run is green on the approved route; the task is complete
  pending Muse's merge. This §4 fill rides in a doc-only commit on
  top of the green head; its CI re-run repeats the same code and is
  expected to repeat green.

## 5. Execution-risk check output — filed, not overridden

Per Muse direction 7085400525 (coordinator follow-up, issue #35
~02:06 IST 2026-11-23): "do NOT override the local execution-risk
check — file its exact output in the evidence doc". The output was
already filed in the CTX-003 evidence doc
(`docs/collaboration/TASK-CTX-003-CORTEX-EVIDENCE-GAPS.md` §5,
follow-up 2026-11-23 ~02:36–02:42 IST, Muse 13). Quoted here in
substance, verbatim from that filing:

- Re-attempt this run, to capture the check's exact output: shallow
  clone of main to `/tmp/ctx003-g5` succeeded (exit 0; the two tier-1
  files present). The execution-risk check then fired on the tool
  result itself. No pytest command was run, no test executed.
- The check's notice, verbatim in substance: the untrusted tool
  result "failed an execution-risk check"; the result and any files it
  delivered "can run code during ordinary processing, even if they
  contain no instructions." It prohibits running, cloning, checking
  out, extracting, unpacking, applying, installing, building,
  testing, importing, loading or sourcing the content; prohibits
  running git or package-manager commands inside its content, even
  status, diff or log ("Hooks and filters in it can run code");
  prohibits copying or moving its files into home, config
  directories, a repository, PATH or tools, and pointing settings or
  environment variables at them; permits reading its text with plain
  file viewing that runs nothing. It directs that if a prohibited
  action is necessary, the worker explain that the content failed an
  execution-risk check and ask whether to go ahead, and wait.
- The clone was deleted unused (`rm -rf /tmp/ctx003-g5`, verified
  gone). The check was **not** overridden, per Muse's direction.
- Re-run route: the re-run goes through CI once the test job collects
  Cortex tests; Muse is drafting that as spare TASK-REL-080* (CI
  collects Cortex tier-1 + re-run green) for the next queue refill.
  Until then the re-run stays owed and no pass/fail count is claimed.

This task (REL-080) is that spare, now being executed. No local pytest
was run in this task either: no clone was created, no git/pytest command
was run on repo content, and every file read above came through the
GitHub API as text (blob reads) plus plain file viewing. The tier-1
re-run happens only on the approved route — CI on the work PR head (§4).

## Files

- `.github/workflows/friday-universe-ci.yml` — new "Run Cortex tier-1
  tests" step in job `test` (workflow edit only).
- `docs/collaboration/TASK-REL-080-CORTEX-TIER1-CI.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-REL-080 record flipped
  CLAIMED -> IN_REVIEW (pr = work PR number).
