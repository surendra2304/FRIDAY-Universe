# TASK-REL-097 — CI canary: every shipped voice test file collected by CI

- Task: TASK-REL-097 (P1). Assigned by Muse (coordinator) in watch 7130910007 (17:17 run, hub #1483): "CI canary for the voice-regression test files — prove CI collects every shipped voice test file, incl. the VOI-032 set."
- Claim: hub #1483 comment 7131531240 by Muse 15, 2026-11-24 ~18:05 IST. Branch `muse15/task-rel-097-ci-canary-voice-tests` from main `404f5014`.
- Verified against: main `404f5014` (merges #1668 REL-098, #1665 FUT-029).
- Verdict: **the gap was real, and it is now closed.** 17 of the 44 shipped `FRIDAY/tests/test_voice_*.py` files were collected by NO PR-triggered workflow (REL-068 guard `--full`, main `404f5014`). All 17 are now named in the `voice-regressions` job of `.github/workflows/friday-universe-ci.yml`; the guard reports 0 uncollected voice files and 0 stale references. The 17 files initially failed 8 tests on a local run — all 8 were stale-test drift against deliberate implementation changes (see below), fixed in the tests; the full job list now runs **688 passed, 0 failed** locally.

## Per-file verdict (44 shipped files)

`tests` = `def test_` lines in the file. "Before" = collector on main `404f5014`; "After" = collector with this change. VR = `friday-universe-ci.yml` / `voice-regressions` / "Run voice, LiveKit, Gemini, and CLI regressions". Contracts = `owner-workflows.yml` / `contracts`.

| File | Tests | Collected before | Collected after |
|---|---|---|---|
| `test_voice_agent_integration.py` | 15 | VR | VR |
| `test_voice_brain_delivery_frd012.py` | 18 | NONE | VR |
| `test_voice_brain_latency_frd011.py` | 13 | NONE | VR |
| `test_voice_confirmation_policy.py` | 18 | VR | VR |
| `test_voice_dead_input_voi016.py` | 30 | VR | VR |
| `test_voice_dictation.py` | 10 | VR | VR |
| `test_voice_fleet_terms.py` | 19 | VR | VR |
| `test_voice_fragment_guard_frd015.py` | 12 | NONE | VR |
| `test_voice_fragment_recovery_frd019.py` | 16 | NONE | VR |
| `test_voice_frame_counters_voi017.py` | 13 | VR | VR |
| `test_voice_gemini_only.py` | 15 | VR | VR |
| `test_voice_greeting_onset_voi026.py` | 10 | VR | VR |
| `test_voice_greeting_onset_voi028.py` | 4 | VR | VR |
| `test_voice_greeting_recall.py` | 15 | NONE | VR |
| `test_voice_greeting_single_owner.py` | 12 | NONE | VR |
| `test_voice_greeting_trigger.py` | 13 | NONE | VR |
| `test_voice_input_forward_voi022.py` | 18 | VR | VR |
| `test_voice_instant_routing.py` | 14 | NONE | VR |
| `test_voice_key_resolution.py` | 17 | VR | VR |
| `test_voice_language_profiles.py` | 10 | VR | VR |
| `test_voice_live_features.py` | 34 | VR | VR |
| `test_voice_livekit_health_route.py` | 6 | Contracts | Contracts |
| `test_voice_noise_interruption_voi032.py` | 15 | VR | VR |
| `test_voice_noise_robustness_voi018.py` | 8 | VR | VR |
| `test_voice_personality.py` | 8 | VR | VR |
| `test_voice_recall_concurrency_frd016.py` | 5 | NONE | VR |
| `test_voice_recall_draw_logging_frd017.py` | 3 | NONE | VR |
| `test_voice_recall_fact_frd014.py` | 16 | NONE | VR |
| `test_voice_recall_gate_frd019.py` | 11 | NONE | VR |
| `test_voice_recall_remote_deadline_frd020.py` | 5 | NONE | VR |
| `test_voice_recall_retry_frd017.py` | 3 | NONE | VR |
| `test_voice_recovery_ladder.py` | 26 | VR | VR |
| `test_voice_send_path_voi024.py` | 11 | VR | VR |
| `test_voice_session_build_overlap.py` | 10 | NONE | VR |
| `test_voice_session_pinning.py` | 14 | VR | VR |
| `test_voice_silent_path_frd018.py` | 22 | NONE | VR |
| `test_voice_subsystem_audit.py` | 6 | VR | VR |
| `test_voice_surface_contract.py` | 5 | VR | VR |
| `test_voice_tool_security.py` | 12 | VR + Contracts | VR + Contracts |
| `test_voice_vad_default_consistency_voi025.py` | 9 | VR | VR |
| `test_voice_verbatim_watch_frd018.py` | 12 | NONE | VR |
| `test_voice_vision.py` | 3 | VR | VR |
| `test_voice_vision_advanced.py` | 7 | VR | VR |
| `test_voice_warm_pool.py` | 4 | VR | VR |

Totals: 44 files, 547 `def test_` lines. Before: 27 collected (26 VR + `livekit_health_route` via Contracts), 17 uncollected (200 `def test_` lines). After: 44/44 collected (43 VR + 1 Contracts). The VOI-032 set (`test_voice_noise_interruption_voi032.py`, 15 tests) was already collected before this change; the acceptance's "incl. the VOI-032 set" is satisfied and re-verified.

## The fix (workflow)

`.github/workflows/friday-universe-ci.yml`, `voice-regressions` job: the 17 files appended to the existing `python -m pytest -q` invocation, in FRD-number order then the unnumbered files. No change to the `detect-voice-changes` filter — it already matches `FRIDAY/tests/test_voice_*.py`, so any future change to any of the 17 triggers the job. No change to the lint step (it curates a subset, as it already does for the VOI files). No source change.

## Guard check (REL-068, live)

`python3 scripts/ci_test_collection_audit.py --full` run locally against the working tree:

- Before (main `404f5014`): 1,954 test files in repo, 344 covered, 11 PR-triggered workflows scanned; the 17 files above listed UNCOLLECTED.
- After (this change): 1,954 test files, **361 covered** (+17), **0 uncollected `FRIDAY/tests/test_voice_*`**, **0 stale references**.
- Repo-wide uncollected debt (1,592 other files) is unchanged and out of this task's scope — the guard is diff-scoped in CI by design.

Guard-parser subtlety worth recording (found the hard way): the guard only credits a test-file reference while its line scanner is inside a pytest invocation — a line not ending in `\` ends the invocation, and a `#` comment line inside the `run:` block ends it too. My first edit put a comment block inside the pytest list and left the previous last line without a trailing `\`, so the guard still reported all 17 uncollected. The fix is a single unbroken continuation chain (trailing `\` on every line but the last) with the explanatory comment as YAML above the step, not inside the `run:` block. Workflow YAML still parses.

## The 8 failing tests (found by the local run, fixed in the tests)

Running the 17 newly-wired files locally first gave **197 passed, 8 failed** — wiring them into CI as-shipped would have reddened the `voice-regressions` job on the next voice-touching PR. All 8 are stale-test drift against deliberate implementation changes; no source change was needed. The underlying properties were re-verified against current source before each fix.

1. `test_voice_greeting_recall.py` (3: `test_keeper_refreshes_before_expiry`, `test_failed_refresh_keeps_still_valid_key_and_cache`, `test_unjudged_refresh_keeps_verified_key`): the tests set the cache age to 200 s assuming the old 240 s TTL ("~40 s remain — inside the refresh window"). TASK-VOI-020 deliberately raised the TTL to 1800 s (`_KEY_CACHE_TTL_S`, "trust a verified key for 30 minutes", probe-bucket saving), so a 200 s-old key has 1600 s left — outside the 75 s refresh-ahead window — and `_key_keeper_step()` correctly returns `fresh`. Fix: age the cache to `(TTL - 40)` s, i.e. `time.time() - (w._KEY_CACHE_TTL_S - 40.0)`, so ~40 s remain under the current TTL. Post-refresh assertion (`remaining > 200`) still holds (renewed TTL is 1800 s).
2. `test_voice_greeting_trigger.py` (1) + `test_voice_session_build_overlap.py` (1): source-shape assertions searched for the single-line `session, agent = await _make_session(instructions)`. TASK-VOI-028 made the call multi-line (`artifacts={"model": _proof_model}` on the next line). Fix: match the call head `session, agent = await _make_session(`. Ordering re-verified in current `entrypoint` source: connect (line 3652) < greeting launch (3790) < session build (3842) < `_start` — both properties still hold.
3. `test_voice_instant_routing.py` (3): the implementation now calls `agent.process_message(text, channel="voice")` (`gemini_live_session.py` lines 657, 1223); the real signature is `process_message(self, user_input, channel="chat")` (`agent.py:475`) — the channel kwarg is deliberate. Fix: the three assertions now expect `channel="voice"`.

Re-run after the fixes: **205 passed, 0 failed in 28.61 s** (the 17 files).

## Local execution proof (full job list)

The exact `voice-regressions` pytest invocation (all 49 files: 43 `test_voice_*` + `test_livekit_token.py`, `test_gemini_live_voice.py`, `test_gemini_model_configuration_audit.py`, `test_model_configuration_consistency.py`, `test_gemini_provider_runtime_audit.py`, `test_ux_and_cli.py`), run locally in a fresh venv with the CI job's own install steps (`pip install -r requirements.txt`, `pip install -e ".[dev]"`, Python 3.12 vs CI's 3.11):

- **688 passed, 0 failed, 47 warnings, in 50.73 s.** Well inside the job's 25-minute timeout.

## Method and limits

- Local pytest, not CI: this worker VM has a repo clone, so the full job list was executed here (unlike REL-072, which relied on CI as arbiter). CI on this PR will NOT execute the new list: the `voice-regressions` job is path-gated by `detect-voice-changes`, and this PR changes the workflow file + docs + tests, not a `FRIDAY/tests/test_voice_*.py` path — the job will be skipped on this PR. First CI execution of the 17 files happens on the next PR that touches a voice path; the local 688-pass run is the execution proof for this PR.
- VM quirks, both worked around and neither a repo defect: (a) `/tmp` is a 512 MB tmpfs — the venv had to live under `~/workspace/.tmp-rel097` (removed after the run); (b) this VM exports proxy env vars whose bracketed-IPv6 `NO_PROXY` entries make httpx raise `InvalidURL: Invalid port: ':1]'` at `livekit_worker` import — the local runs unset the proxy vars, matching CI (no proxy vars on ubuntu-latest). With the vars set, 7 of the 17 files error at collection; with them unset, all collect.
- The 4 edited test files are not in the job's ruff lint list (same as the other VOI files), so no lint change was made. `ruff check` on the edited test files: clean (run in the same venv).
- Change set of this task: workflow list (+17 files) + 4 test files (8 stale assertions) + this evidence doc + the board record flip (new record, CLAIMED → IN_REVIEW). No source, no dependency, no other workflow change.

## Before / after

- Before: 27/44 voice test files collected by CI; 17 files (200 tests) ran nowhere — a merged regression in any of them would have stayed green.
- After: 44/44 collected; the 17 files run green (205 tests locally, 688 across the full job list); the guard confirms 0 uncollected voice files, 0 stale references.

— Muse 15
