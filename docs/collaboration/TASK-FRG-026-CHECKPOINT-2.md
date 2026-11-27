# TASK-FRG-026 — CHECKPOINT 2 (live-leg shaping + CI-collection gap) — Muse TP7 — 2026-11-27 ~19:01 IST

Filed 2026-11-27 ~19:01 IST on branch `musetp7/task-frg-026-forge-verify-wave3`.
Every claim below was verified first-hand on the FRG branch ref at the 19:01 run
(`git grep`/`git show` against the branch); the prep draft's reads were on the
FRD-049 branch and are NOT asserted here.

## Checkpoint 1 (filed 18:01 IST)
- Branch `musetp7/task-frg-026-forge-verify-wave3` @ `efc59ffa` (parent `caa597bc`),
  `docs/collaboration/TASK-FRG-026-CHECKPOINT-1.md` (5,593 bytes), verified on the branch.
- All six corpus items MERGED via pulls API (PRs #734/#719/#762/#788/#790/#789).
- Board on live main `f0d575f1` (blob `409850b4`, 11,494 lines): FRG-026 AVAILABLE/muse_tp7/P2.
- Hub #2045 read through 7218287618; status posted, comment 7218451598. Usage 14%.

## FINDING — CI does not collect the FRG-05..08/10 tests (same REL-068 class as FRD-049)
- `.github/workflows/owner-workflows.yml` Forge pytest list collects only
  `Forge/tests/test_ig2_frg02_code_graph.py` (line 176) and
  `test_ig2_frg03_ocr_review.py` (line 177); last entry is
  `Forge/tests/test_frg030_gradio_layer.py` (line 179). Verified on the FRG branch.
- `git grep test_ig2_frg` across `.github/workflows/` on the FRG branch returns ONLY
  those two lines: the test files for FRG-01 (`test_ig2_frg01_karpathy_principles.py`),
  FRG-04 (`test_ig2_frg04_parallel_download.py`), FRG-05 (`test_ig2_frg05_ecc_harness.py`),
  FRG-06 (`test_ig2_frg06_local_business.py`), FRG-07 (`test_ig2_frg07_agent_creation.py`),
  FRG-08 (`test_ig2_frg08_claudex_loop.py`) and FRG-10 (`test_ig2_frg10_review_wiring.py`)
  are present under `Forge/tests/` on the branch but collected by NO workflow. (No
  `test_ig2_frg09` file exists — FRG-09 is docs-only, consistent with checkpoint 1.)
- Consequence: the merged FRG-05..08/10 code has never had its tests run in CI; a green
  CI badge is not evidence for these items. This is the same failure mode FRD-049 hit
  (contracts guard, fixed by inserting the test file before the last entry of the list).
- Proposed repo-side leg (NOT done in this checkpoint; decision owed from Muse): insert
  the seven missing files into the owner-workflows Forge pytest list, before its last
  entry `Forge/tests/test_frg030_gradio_layer.py` (REL-097 precedent: append-after-last
  does not work). Then watch CI on the work PR — these tests have never run in CI, so
  expect possible failures that would be real findings, not noise. Tests were NOT run
  locally (no venv/pytest in this sandbox, per the 13:01 record).

## Live entry points verified first-hand on the FRG branch
- Production intake: `Forge/app/api/delegate.py` — `delegate_task` (line 245): actions
  `status`/`health`/`ping`, `cancel` (via canonical lifecycle cancellation), `test`/`verify`
  → `verification_engine.verify_task(task_id)` + `generate_manifest`; `task_execute` (919),
  `get_task_status` (690), `cancel_task` (876). Envelope: `TaskEnvelopeModel` (37),
  result: `TaskResultModel` (48) with a Forge receipt.
- Verification battery: `Forge/app/verification/engine.py` — `VerificationEngine.verify_task`
  (392), `_run_review_stage` (195, the FRG-10 wiring: delegate → verify_task → review passes,
  `review_passes_report.json` persisted as a task artifact). Review models from env
  `FORGE_REVIEW_AUTHOR_MODEL` / `FORGE_REVIEW_REVIEWER_MODEL` (lines 80/85); fail-closed:
  configured-but-unrun audit = failed evidence; unconfigured reviewer = passed evidence
  that DISCLOSES the cross-model audit did not run (deterministic security review still gates).
- Claudex Loop: `Forge/app/verification/claudex_loop.py` — `run_claudex_loop` (183):
  build → cross-model audit → swap rounds until agreement; same model twice or unnamed
  model raises ValueError (self-grading refused loudly). `build_loop_prompt` (114),
  `parse_build_reply` (153).
- ECC harness: `Forge/app/harness/ecc_patterns.py` — `HarnessRun` (76) with `stage`/`advance`/
  `record_test_evidence`, `stage_gate` (62), `scan_agent_config` (162, AgentShield-class scan
  of agent/skill/hook/MCP configs), `InstinctStore` (229).
- Agent creation: `Forge/app/templates/agent_creation.py` — `derive_config` (155),
  `render_files` (393), `_check_compile` (484), `_run_probe` (521), `main` (270),
  `run_tool` (379); `derive_specialist` (110), `slugify_agent_name` (74).
- Local-business pipeline: `Forge/forge_upgrade/local_business_pipeline.py` —
  `run_pipeline` (196), `Prospect.validate` (60), `prospect_score` (69),
  `mine_review_themes` (90), `render_starter_site` (123), `PipelineRun.approve/reject`
  (161/164), `contact_plan` (179), `publish` (188).

## One real build task per item, shaped (pending live-leg ruling — none run yet)
- FRG-05 ECC: run `scan_agent_config` + a `HarnessRun` stage-gate over a REAL agent's
  config on the live host; the Shield findings + gate verdict must actually be used to
  fix or approve that config. Consuming agent: the agent whose config is scanned (TBD by Muse).
- FRG-06 pipeline: `run_pipeline` over REAL local-business prospects (source of prospects
  NOT yet named — do not invent prospects; Muse to name the set), starter site + contact
  plan actually handed to a consuming agent for outreach.
- FRG-07 agent creation: one prompt → `derive_config` → `render_files` → compile + probe
  checks; the created agent must be registered and then USED by a peer agent for a real task.
- FRG-08 Claudex Loop: `run_claudex_loop` on a real build goal with two DISTINCT models;
  loop result + agreement actually used by the requesting agent.
- FRG-09: no build task exists (evaluation notes only) — ask Muse whether it closes on the
  evaluation record or needs a named follow-up task.
- FRG-10 review wiring: delegate `test`/`verify` on a real completed task id through
  `delegate_task` → `verify_task`; review stage runs with the two models configured
  (needs the FRG-10 env decision) or with the disclosed absence.

## Live legs — HELD, ruling owed from Muse
No live step taken; no fleet move; no Forge dispatch attempted. Owner stop order still in
force. Owed before any live leg: (a) live Forge host, (b) clearance/grant under the stop
order, (c) one real build task + consuming agent per item (shaped above, FRG-06 prospect
source + FRG-09 closure still open questions for Muse). FRD-049 live leg still HELD/carried.

## Hub + board at filing (19:01 run, first-hand)
- Hub #2045 read through 7219539943 (Muse 15, ~18:59 IST); WATCH221/222/223 + Burn
  Enforcer 18:16/18:35 read in full — no TP7 demand, no competing claim on FRG-026.
  New: #2142 verifier → Muse TP10 (due ~20:15); REL-118 → Muse 13; merges #2132/#2134/
  #2135/#2137 landed; main now `fae3ee05`. Board PR deferred again (coordinator's leg).
- Board on live main `fae3ee05` (11,505 lines, `docs/collaboration/WORK_BOARD.yaml`):
  FRG-026 AVAILABLE/muse_tp7/P2; FRD-059 IN_REVIEW/muse_tp7/pr 1848.

## Next legs
1. Ask Muse: CI-list leg (add the seven missing test files to owner-workflows.yml — it
   touches a shared workflow), live Forge host + clearance, FRG-06 prospect source,
   FRG-09 closure.
2. Live legs per item once ruled; evidence doc + board flip ride in the single work PR.

## Five states
Implemented NO (scoping only) / tested NO / merged NO / deployed NO / production-verified NO.

## Queue / schedules / usage
- Queue: FRG-026 (head) → FRD-059 (IN_REVIEW, pr 1848, live-gated).
- Work-request task stays cancelled while FRG-026 is claimed (guard). Hourly self-check +
  weekly reset armed (next self-check 20:01 IST; weekly reset Wed Dec 2 17:11 IST).
- Usage: 14% of free weekly limit (re-verified 19:01 IST, unchanged from 18:01).
  Reset Wed Dec 2, 17:01 IST. Additional tokens 0%.
- Carried: FRD-049 live leg still HELD (merged, not production-verified).
