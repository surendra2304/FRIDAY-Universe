# TASK-REL-002 — voice-regressions CI failure: root cause and verification

- **Task:** TASK-REL-002 (P0) — root-cause and fix the failing voice-regressions CI job
  (failing on main since push 37db125).
- **Owner:** muse_4 (Muse 4). Assigned by Muse (Head Manager) in coordinator watch,
  issue #35 comment 7072956811 (~08:00 IST, 2026-11-22; board PR #1293).
- **Claim:** issue #35 comment 7073219023 (~08:27 IST); board claim PR #1299.
- **Branch:** `muse4/task-rel-002-voice-regressions`. This PR (#1299) carries the claim
  plus this report and the board IN_REVIEW flip. No code change: the fix was already
  on main (see below); duplicating it would be wrong.
- **Status:** implemented (report + verification). Awaiting Muse review/merge.
  Not merged, not deployed. Only Muse merges.

## 1. The failure

- **Run:** FRIDAY Universe CI/CD run 43569163089, 2026-11-14T07:02:09Z, head
  `573da9c1` (merge of PR #51, the numpy merge chain; the board record cites push
  37db125 as the first-seen push), conclusion `failure`.
- **Failing job:** `voice-regressions` (job 132369557100) — step 6,
  "Run voice, LiveKit, Gemini, and CLI regressions", exit code 1.
  All other jobs green (`test`, `detect-voice-changes`, `docker` success;
  the ruff lint step 5 passed, "All checks passed!").
- **Failing test (exactly one):**
  `tests/test_voice_live_features.py::test_env_example_documents_every_settings_field`
  — `AssertionError: Undocumented fields in .env.example:
  ['FRIDAY_INTENT_CLASSIFY_TIMEOUT', 'FRIDAY_INTENT_CLASSIFY_ENABLED']`.
  Summary: **1 failed, 157 passed in 8.93s**.

## 2. Root cause

PR #92 (commit `101dd85`, TASK-INTENT-001, the LLM intent-classification mid-tier)
added two fields to `Settings` in `FRIDAY/src/friday/core/config.py` —

- `intent_classify_timeout: float = Field(default=2.5, ge=1, le=30, ...)`
- `intent_classify_enabled: bool = Field(default=True, ...)`

— without documenting them in `FRIDAY/.env.example`. The contract test requires
every `Settings.model_fields` entry to have a `FRIDAY_<NAME>` line in
`FRIDAY/.env.example`, so the two new fields failed it. The defect was in the
PR #92 change (missing docs), not in the test: the test did exactly what it is
for, and no assertion was weakened or test skipped here.

## 3. The fix — already on main before this claim

Surendra fixed it directly on main the same day, ~30 minutes after the failure:

- **Commit `4ac6b270`** — "TASK-REL-002: document FRIDAY_INTENT_CLASSIFY_* in
  .env.example", author Surendra, 2026-11-14 13:01:47 +0530, parent `573da9c1`
  (the failing head itself). Diff: `FRIDAY/.env.example` +2 lines, nothing else:
  `FRIDAY_INTENT_CLASSIFY_TIMEOUT=2.5` and `FRIDAY_INTENT_CLASSIFY_ENABLED=true`.
- The board record still read "root cause not yet established" because no worker
  had re-checked the job since; the fix predates this assignment by 8 days.

## 4. CI verification — the job is green on main

The `voice-regressions` job is conditional
(`if: needs.detect-voice-changes.outputs.voice == 'true'`), so most main pushes
skip it — which is why the board record looked stale. Where it actually ran
after the fix, it passed every time (3 runs, all on main, all `success`):

| run | date (UTC) | head | voice-regressions |
| --- | --- | --- | --- |
| 44489048264 | 2026-11-19 08:36 | `0fa7b016` | success |
| 44489413337 | 2026-11-19 08:39 | `9d11d708` | success |
| 44864933295 | 2026-11-21 04:12 | `1b8d7b23` | success |

Latest green run (44864933295, job 136726421317): lint step "All checks passed!",
pytest step success, **406 passed, 1 warning in 10.38s**, 0 failed. At that head
the workflow still listed the contract test, the test file still contained it,
and `.env.example` already held both lines — so the green run exercised the fix.

## 5. Local verification (this run)

Venv built from current main (`FRIDAY/requirements.txt` + `pip install -e ".[dev]"`,
pytest 9.2.0; note CI uses Python 3.11, this VM has 3.12.3):

- **Reproduced the failure at the failing head:** worktree at `573da9c1`,
  `pytest tests/test_voice_live_features.py::test_env_example_documents_every_settings_field`
  → `1 failed`, the exact CI assertion
  (`Undocumented fields in .env.example: ['FRIDAY_INTENT_CLASSIFY_TIMEOUT',
  'FRIDAY_INTENT_CLASSIFY_ENABLED']`, `test_voice_live_features.py:450`).
- **Pass at current main** (`ed3385da`): the same test → `1 passed in 0.40s`;
  the CI ruff step over the 12 listed voice surfaces → "All checks passed!";
  the full 27-file voice-regressions list exactly as CI runs it →
  **406 passed in 18.45s** (same 406 count as the latest green CI run).
- **Static cross-check:** all 165 `Settings` fields have a `FRIDAY_<NAME>` entry in
  `FRIDAY/.env.example` on current main — zero undocumented.
- **Local-environment note (not a repo defect):** the full list first failed at
  collection with `httpx.InvalidURL: Invalid port: ':1]'` — this VM exports
  `HTTP(S)_PROXY`/`no_proxy` with bracketed IPv6 entries (`[::1]`, `[fd8b:...]`),
  which httpx mis-parses while importing `friday.voice.livekit_worker` at
  module level. Unsetting the proxy variables reproduces CI's clean environment
  and the suite collects and passes. No repo change was made for this; the same
  failure appeared in the FWD-036 run (`test_async_pipeline_defaults_to_demo_fapi`)
  and is pre-existing environment behaviour, out of scope here.

## 6. Acceptance

- [x] Failing test(s)/lint identified from CI logs and reproduced locally —
  §1 (CI log) + §5 (local reproduction at `573da9c1`).
- [x] Root cause fixed at the cause; no assertion weakened, no test skipped —
  §2 (cause) + §3 (fix `4ac6b270`, already on main; this PR adds no code).
- [x] voice-regressions job green on main — §4 (3 green runs since the fix,
  latest 2026-11-21, 406 passed) + §5 (local full-list green at `ed3385da`).

## 7. Observation (no change made — Muse's call)

The conditional trigger is why this failure sat unnoticed: the job only runs
when a push touches a voice path, so a broken voice suite can sit on main
until the next voice change (here the gap was 2026-11-14 → 2026-11-19 before
the job ran again). Running `voice-regressions` unconditionally on main pushes
would close that gap at ~1–2 min of runner time per push. I did not change the
trigger — it is a CI-design decision outside this task's acceptance — flagging
it for Muse.

## Files in this PR

- `FRIDAY/docs/REL-002-VOICE-REGRESSIONS-ROOT-CAUSE.md` (new, this report)
- `docs/collaboration/WORK_BOARD.yaml` (TASK-REL-002 CLAIMED → IN_REVIEW, pr 1299)

— Muse 4
