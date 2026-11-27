# TASK-REL-002 — voice-regressions root cause and fix evidence

## Verdict

The `voice-regressions` failure was deterministic, not flaky. One test failed:
`tests/test_voice_live_features.py::test_env_example_documents_every_settings_field`.
The test was correct: two `Settings` fields were missing from `FRIDAY/.env.example`.
No test was weakened.

## CI evidence (first failure on main)

- Commit: `37db125d66f61b5c4d3a17dff90d3cff80f0e67a` (2026-11-14T06:55:43Z, merge PR #54).
- Workflow run: `43568677299`; job: `voice-regressions` (`132368066302`), completed `failure`.
- Failed step: `Run voice, LiveKit, Gemini, and CLI regressions`.
- Pytest summary: `1 failed, 157 passed`.
- Failure: `Undocumented fields in .env.example: ['FRIDAY_INTENT_CLASSIFY_TIMEOUT', 'FRIDAY_INTENT_CLASSIFY_ENABLED']` at `tests/test_voice_live_features.py:450`.

The merge commit itself only changed `FRIDAY/pyproject.toml` (`mypy>=1.11.0` -> `mypy>=2.4.1`).
That pin was not the cause: dependency install and lint passed, and the failure was the
settings-documentation assertion. The pyproject change mattered only because
`FRIDAY/pyproject.toml` is in the voice path filter, so the merge exercised the job and
exposed the latent documentation gap.

## Root cause

Commit `101dd85213610c5c75942f887a8639e4881b16b4` (TASK-INTENT-001, 2026-11-14T05:46:36Z)
added `intent_classify_timeout` and `intent_classify_enabled` to
`FRIDAY/src/friday/core/config.py` `Settings`, but did not add the corresponding
`FRIDAY_INTENT_CLASSIFY_TIMEOUT` / `FRIDAY_INTENT_CLASSIFY_ENABLED` entries to
`FRIDAY/.env.example`. The voice regression test enumerates `Settings.model_fields` and
requires every field to be documented as `FRIDAY_<FIELD>` in `.env.example`, so it failed
as soon as the job next ran.

## Fix

The surface fix already landed on main in commit
`4ac6b270e12643ac1713824e587fcec88a1b6d1d` (2026-11-14T07:31:47Z,
"TASK-REL-002: document FRIDAY_INTENT_CLASSIFY_* in .env.example"), adding:

```text
FRIDAY_INTENT_CLASSIFY_TIMEOUT=2.5
FRIDAY_INTENT_CLASSIFY_ENABLED=true
```

Those values match the `Settings` defaults (`intent_classify_timeout=2.5`,
`intent_classify_enabled=True`). This PR adds explanatory comments for the two settings
and records this evidence; it does not change the test or weaken any assertion.

## Current proof

- Main commit `a284c307` ran `voice-regressions` successfully (job `140462401566`):
  `776 passed, 1 skipped`.
- Comparing `a284c307...cf49af6b` shows no changed files in the REL-106 voice filter
  paths, so the green voice surface at `a284c307` is the same voice surface carried into
  the current main line; later main pushes show `voice-regressions` as `skipped` because
  their diffs do not touch voice paths.
- This PR touches `FRIDAY/.env.example`, which is in the voice filter, so the
  `voice-regressions` job runs on the PR head rather than skipping.

## Acceptance mapping

- Root cause established from CI logs and recorded here: yes.
- Fix merged: the `.env.example` documentation fix is on main (`4ac6b270`); this PR
  records the evidence and clarifies the two settings.
- Job green on main: yes when triggered (`a284c307`, 776 passed); this PR re-exercises
  the job on its head.
- No test weakened: yes — the failing surface (`.env.example`) was fixed, not the test.
