# TASK-REL-002 — voice-regressions root cause and fix evidence

## Verdict

The `voice-regressions` job failed deterministically on main in two successive
single-test failure modes. Neither was flaky, and no test was weakened to pass:

1. `test_env_example_documents_every_settings_field` — two `Settings` fields were
   missing from `FRIDAY/.env.example`.
2. `test_voice_direct_desktop_command_delegates_to_local_agent` — the test asserted
   the old delegation call after voice turns began binding `channel="voice"`.

## Failure mode 1: undocumented Settings fields

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

Root cause: commit `101dd85213610c5c75942f887a8639e4881b16b4` (TASK-INTENT-001,
2026-11-14T05:46:36Z) added `intent_classify_timeout` and `intent_classify_enabled` to
`FRIDAY/src/friday/core/config.py` `Settings`, but did not add the corresponding
`FRIDAY_INTENT_CLASSIFY_TIMEOUT` / `FRIDAY_INTENT_CLASSIFY_ENABLED` entries to
`FRIDAY/.env.example`. The voice regression test enumerates `Settings.model_fields` and
requires every field to be documented as `FRIDAY_<FIELD>` in `.env.example`, so it failed
as soon as the job next ran.

Fix: the surface fix landed on main in commit
`4ac6b270e12643ac1713824e587fcec88a1b6d1d` (2026-11-14T07:31:47Z,
"TASK-REL-002: document FRIDAY_INTENT_CLASSIFY_* in .env.example"), adding:

```text
FRIDAY_INTENT_CLASSIFY_TIMEOUT=2.5
FRIDAY_INTENT_CLASSIFY_ENABLED=true
```

Those values match the `Settings` defaults (`intent_classify_timeout=2.5`,
`intent_classify_enabled=True`). This PR adds explanatory comments for the two settings.

## Failure mode 2: stale delegation assertion after channel binding

After the `.env.example` fix, main still failed in a different single test. Representative
main runs: `3b7cf71c` (2026-11-15, job `132957730746`), `3446a02d` (2026-11-17, job
`133764853393`), and `2392b23f` (2026-11-17, job `134033923216`) all failed with:

```text
FAILED tests/test_voice_agent_integration.py::test_voice_direct_desktop_command_delegates_to_local_agent[asyncio]
Expected: mock('search Telugu latest movies in Chrome')
  Actual: mock('search Telugu latest movies in Chrome', channel='voice')
```

Root cause: TASK-REL-044 routing (`2798ed86`) made voice turns delegate with
`channel="voice"` so they bind the voice route and never complexity-escalate to
Inference. The integration test still asserted the pre-REL-044 call without the channel
argument. The production behaviour was the intended new contract; the test assertion was
stale.

Fix: commit `48c5ea709960e9edf06a43402d02ae71a74aa44c` (2026-11-17T14:54:55Z,
"test(voice): fix stale delegation assertion — voice turns bind channel="voice"
(TASK-REL-044)") corrected the assertion to
`assert_called_once_with("search Telugu latest movies in Chrome", channel="voice")`.
That is a test correction with the reason recorded in the commit, not a weakening: it
asserts the exact delegation call including the channel. The `voice-regressions` job is
`success` on `48c5ea70` (job `134127528001`).

Later `voice-regressions` failures found in the failure-run search are on voice feature
PR branches (for example VOI-032/VOI-043 work), not on main; the main line after the two
fixes above is green when the job is triggered.

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

- Root cause established from CI logs and recorded here: yes — two deterministic
  failure modes, each with run/job evidence above.
- Fix merged: yes — `.env.example` documentation fix `4ac6b270` and delegation-assertion
  correction `48c5ea70` are on main; this PR records the evidence and clarifies the two
  intent settings.
- Job green on main: yes when triggered (`48c5ea70`, then `a284c307` with 776 passed);
  this PR re-exercises the job on its head.
- No test weakened: yes — failure mode 1 fixed the documented surface; failure mode 2
  corrected a stale exact-call assertion to the intended `channel="voice"` contract.
