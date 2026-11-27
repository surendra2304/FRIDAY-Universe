# TASK-INT-056 — Checkpoint 1: synthesis-failure analysis + stall record

- Task: IntelX: synthesis-failure path preserves extractive excerpts instead of discarding them
- Worker: Muse 3 (roster `muse_3`)
- Branch: `muse3/task-int-056-synthesis-failure-excerpts` @ `091bc349a99b4fb05284194346a3f59964caa663`
  (claim base = main at claim; main has since moved to `99e5fe12`)
- Claim: hub #2045 comment `7209191422`, 2026-11-27 09:11:20 IST
- Board on current main `8477b554` (blob `5b60a050abf6283c5959c26946deb18033806e45`,
  verified first-hand via git blob API): status AVAILABLE / owner `muse_3` /
  branch null / pr null — the CLAIMED flip is still owed in the coordinator's
  consolidated board PR (it was NOT in the WATCH201 §5 flips-owed list; flagged
  to the coordinator in the stall post this run).
- Five states: implemented YES / tested NO (regression tests filed, CI pending) /
  merged NO / deployed n/a / production-verified NO (failing-synthesis live case
  owed — bridge run_shell down this run, see checkpoint 2).

## Stall record (this run, 10:05 IST self-check)

- At 10:05 IST, ~55 min after claim: branch still at claim base, zero commits,
  no PR. Verified first-hand via API: branch GET returns head `091bc349`;
  pulls list for the branch head is empty.
- Cause: this run's local worktree checkout (`git worktree add`, /tmp/muse3-int056)
  tripped a system execution-risk flag on the checkout output. Per that flag, no
  local git / build / test / editor operations on the repo checkout were run this
  run. The worktree is left in place, inert, at /tmp/muse3-int056 (removal is a
  later run's call — it needs a git operation on the checkout).
- Repair done this run (API-only, no local execution of repo content): first-hand
  code reads below + this checkpoint filed on the claim branch via the GitHub
  contents API. Implementation + regression tests + live case are NOT done; they
  are the next run's work, either via the API-only path or once the execution-risk
  flag clears. Task HELD by Muse 3 (not released): the block is run tooling, not
  a task defect, and the checkpoint unblocks the next run. Re-slot is the
  coordinator's call — see the stall post on hub #2045.

## Failure point (verified first-hand on main `8477b554`)

`IntelX/intelx/agents/synthesizer.py` — `SynthesizerAgent.execute`:

- The LLM call `llm_res = await self.gateway.complete(messages=messages,
  role=self.role, schema_model=DraftReport, run_id=run_id)` is NOT wrapped in
  try/except. When the model gateway raises (ProviderError), the exception
  propagates out of `execute` and the whole answer fails: no executive answer,
  no findings, and the verified claims — the extractive excerpts — are
  discarded with it.
- This failure mode is real and observed: PR #78 (DRAFT, unmerged,
  "source-grounded research answers — LIVE ACCEPTANCE STILL FAILING") records
  "explicitSynthesizer still ProviderError" — the synthesizer path fails closed
  on a provider error while the deployed path kept working.

## The deployed extractive path (what must be preserved)

`IntelX/intelx/agents/deep_research_loop.py` — `IterativeDeepResearcher._synthesize`:

- "Build the deterministic cited brief (extractive — no invented prose)."
  Per subquestion it lists source snippets (first 300 chars) with citation
  indexes, then a Sources section with title, URL, quality. This is the
  pre-#78 deployed behaviour the acceptance criteria refers to: the answer
  carries the extractive excerpts.

## In-file precedent for the fallback

- `synthesizer.py` itself already falls back to claims when the LLM draft has no
  grounded findings: it builds `grounded_findings` directly from `claims[:5]`
  (claim text as statement, claim confidence, claim IDs). The synthesis-failure
  fallback should mirror this shape.
- `IntelX/intelx/agents/synthesis_engine.py` — `_generate_summary` catches a
  gateway failure and falls back to concatenating the top evidence claims.
  The synthesizer's `execute` has no equivalent catch — that is the gap.

## Fix design (for the implementation run)

1. Wrap the `gateway.complete(...)` call in `SynthesizerAgent.execute` in
   try/except (provider/model errors only; do not swallow programming errors
   from the grounding/report code).
2. On failure, build the fallback `DraftReport` from the verified claims:
   executive answer states synthesis failed and the answer is the extractive
   excerpts; key findings are the top-N claims verbatim (claim text, claim
   IDs, source title/URL); gaps record the synthesis failure + provider error
   type; overall confidence "Low".
3. Mark the run degraded: append a degradation entry ("Synthesis provider
   failed (<error type>); answer is extractive excerpts from verified
   claims") and set execution_mode to a distinct synthesis-failure value
   (the existing modes are MOCK / LIVE CONFIGURED / NO SYNTHESIS / MOCK
   FALLBACK / LIVE MODEL CALL — add e.g. "SYNTHESIS FAILED / EXTRACTIVE
   FALLBACK").
4. Success path unchanged: when the gateway succeeds, byte-identical behaviour
   (same draft, same grounding, same rendering). No change to the
   insufficient-evidence path (claims empty) or to `deep_research_loop.py`.
5. Callers to check at implementation time: `IntelX/intelx/orchestration/engine.py`
   (the other `SynthesizerAgent` caller found by code search) — confirm it does
   not need its own catch once `execute` never raises on gateway failure.

## Regression tests (for the implementation run)

- New file, e.g. `IntelX/tests/test_int056_synthesis_failure.py` (no existing
  synthesizer-specific test file found; `test_agents.py` covers agents
  generally — place the tests where the implementation run finds the best fit):
  - Failing gateway stub (raises ProviderError) with verified claims →
    `execute` returns normally; executive answer contains the claim excerpts;
    findings are grounded to the input claim IDs; degradation recorded.
  - Failing gateway with empty claims → insufficient-evidence answer (unchanged).
  - Succeeding gateway → normal LLM draft path (success-path behaviour
    unchanged; existing tests keep passing).
- CI must be 9/9 green on the work PR head before merge (team standard).

## Live case plan (for the implementation run)

- Failing-synthesis live case: run the research path live with a synthesis
  provider that fails (same failure shape as the PR #78 probe — provider
  error from the explicit synthesizer), via bridge `run_shell` under standing
  clearance `7200564540`; capture the returned answer and verify it carries
  the extractive excerpts with citations. No service restart, no server move,
  no deploy (owner stop order `7130069033` still stands).
- Evidence to file: the live answer (excerpts present), the provider error
  observed, test run output, CI status. Then work PR (one PR, evidence doc +
  code + tests) for Muse to merge; paired verification mandatory.

## Sources read first-hand this run

- Board `WORK_BOARD.yaml` blob `5b60a050ab` on main `8477b554` (TASK-INT-056
  record, lines ~24169-24234 of the decoded board).
- `IntelX/intelx/agents/synthesizer.py` (571 lines, full read).
- `IntelX/intelx/agents/synthesis_engine.py` (289 lines, full read).
- `IntelX/intelx/agents/deep_research_loop.py` (384 lines; `_synthesize` read).
- PR #78 (DRAFT, unmerged) via API.
- Code search: `SynthesizerAgent` callers = `synthesizer.py`, `__init__.py`,
  `orchestration/engine.py`, `deep_research_loop.py`; `ProviderError` in
  `intelx/models/gateway.py`, `providers.py`, `ai_universe_provider.py`.

— Muse 3

## Checkpoint 2: implementation + regression tests (this run, 12:05 IST self-check)

- Implementation commit `c29502e2` (`IntelX/intelx/agents/synthesizer.py`, +66 lines):
  `gateway.complete(...)` in `SynthesizerAgent.execute` is now wrapped in
  try/except for `(ProviderError, StructuredOutputError)` — the two failure
  types `ModelGateway.complete` raises (all providers failed; schema
  validation failed after retry). Other exceptions still propagate.
- On failure the fallback `DraftReport` is built from the priority-sorted
  verified claims (`sorted_claims[:5]`): executive answer states synthesis
  failed and the answer is the extractive excerpts; key findings are the
  claim texts verbatim with claim IDs and claim confidences (clamped to
  [0.05, 0.95] for the `DraftFinding` field bounds; dict-claim accessor
  matches the `claim_priority` shape so dict claims keep their confidence);
  gaps record the failure + provider error type; overall confidence forced
  "Low"; execution mode `SYNTHESIS FAILED / EXTRACTIVE FALLBACK`; a
  degradation entry is appended ("Synthesis provider failed (<error type>);
  answer is extractive excerpts from verified claims").
- Success path unchanged: same draft, grounding, rendering. The
  insufficient-evidence path (no claims) is untouched — the gateway is never
  called there. No change to `deep_research_loop.py`.
- Callers checked: `IntelX/intelx/orchestration/engine.py` calls
  `synthesizer.execute` in two places (resumption path + stage 8) with no
  try/except of its own; no caller change is needed now that `execute` never
  raises on gateway failure.
- Regression tests commit `822a8e7b`
  (`IntelX/tests/test_int056_synthesis_failure.py`, 4 tests, repo conventions:
  `ModelGateway` subclass stubs, dict claims, `@pytest.mark.asyncio`):
  ProviderError → excerpts returned, findings grounded to c1/c2, Low, mode +
  degradation in the report; StructuredOutputError → same fallback;
  failing gateway + no claims → insufficient-evidence path unchanged;
  succeeding gateway → LLM draft returned, High, no failure markers.
- Work PR: opened this run (number filed in the PR body / hub post once CI
  reports). CI 9/9 green required before merge (team standard).
- LIVE CASE OWED: the failing-synthesis live case (run the research path live
  with a failing synthesis provider via bridge `run_shell`, clearance
  7200564540) could NOT run this run — bridge `run_shell` is down fleet-wide
  (5 failed attempts across servers 2 and 3 this run; `get_system_info` works,
  both Oracle servers ONLINE). The same outage blocked the live re-derivation
  of the paired verification for PR #2082 (verdict PARTIAL, review 6084491169).
  Retry the live case once `run_shell` recovers; no restart, no server move,
  no deploy (owner stop order 7130069033 still stands).
- Board flip: INT-056 CLAIMED/owner muse_3 already landed on main `c1aa53b9`
  via board PR #2077 (verified 11:05 IST run). The MERGED flip rides in the
  coordinator's board PR after this work PR merges.


- CI round 1 (head `94716a60`): 9/10 green; `test` job failed on the IntelX
  tier-1 step — 2 of the 4 new tests failed (job log read first-hand): (a)
  the executive-summary excerpt assertion was wrong (the excerpts live in
  the findings and the rendered report, not in the executive answer, which
  states the failure); (b) the new execution mode rendered as UNSPECIFIED
  because `render_report_markdown` only recognises four modes. Fixes:
  `IntelX/intelx/core/report.py` allowlist gains the
  `SYNTHESIS FAILED / EXTRACTIVE FALLBACK` branch (commit `058c3efc`);
  test assertion corrected (commit `aa8d637d`). The earlier `contracts`
  failure on head `3f80daa5` was the collection guard — the new test file
  was in no PR-triggered pytest invocation; fixed by adding it to the
  IntelX tier-1 list in `.github/workflows/friday-universe-ci.yml`
  (commit `94716a60`), after which `contracts` went green.

— Muse 3
