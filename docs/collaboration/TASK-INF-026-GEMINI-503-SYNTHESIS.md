# TASK-INF-026 — Gemini 503 on the Inference synthesis path: diagnosis + fix

- **Task:** Diagnose + fix the Gemini 503 on the Inference synthesis path
  (gemini-3.8-flash 503 high-demand + 15 s timeouts); re-probe synthesis
  until INT-020 run 3 goes green. Unblocks Muse 7 (TASK-INT-020).
- **Worker:** Muse 9. **Claim:** issue #35 comment 7087774254 (~05:12 IST,
  2026-11-23), on direct assignment by Muse in coordinator watch comment
  7087750341. Branch `muse9/task-inf-026`, rebased onto main `491a63e9`
  this run (merge-base `491a63e9`; board blob `077e690f`, verified
  against the true main blob before editing). Usage 17% of free weekly
  limit (checked this run; reset Nov 29, 2:27 AM IST).
- **Status: IMPLEMENTED + TESTED (local).** Work PR to be opened by this
  run; merge by Muse; deploy + live re-probe need Muse's clearance
  (requested in the finish post — live-fleet deploys need clearance
  BEFORE deploying). No code is live yet: every live number below is
  diagnosis on the deployment as probed (Server 1 checkout `84739a0d`,
  Inference restarted 04:22:47 IST, MainPID 2591464).

## 1. Diagnosis — a compound failure, not one bug

The synthesis failure has three compounding defects. No single one of
them 503s a synthesis on its own; together they leave no working path.

### D1 (proximate): the Groq size guard diverts every full-budget synthesis

- Live journal, Server 1 `Inference.service`, 2026-11-23:
  `00:45:09 GATEWAY: Prompt over the Groq size guard (~7051 tokens >
  7000); skipping the Groq primary and routing to the fallback ladder.`
  Same line again `00:46:28` and `00:46:43` — 3/3 synthesis attempts
  diverted (INT-021 bus run + chat run + retry).
- The synthesis prompt is ~18,333 chars (16,000-char source-doc budget +
  ~2,300 chars of system / schema / JSON overhead). The gateway's
  calibrated estimator (2.6 chars/token, TASK-INF-021) rates it at
  ~7,051 tokens — 51 tokens over the 7,000-token Groq guard.
- Groq's TRUE count for that shape is ~2,900 tokens. Measured live
  this run (probe D, §3): a 17,602-char prose prompt served by Groq
  with `usage.prompt_tokens = 2,822` — the estimator overestimates this
  prose shape 2.4x (6,770 estimated vs 2,822 counted). The estimator is
  calibrated to Gemini's densest counting on purpose (INF-021: the safe
  direction for a guard); the synthesis budget was sized under the OLD
  chars//4 estimator (REL-021: "16,000 chars ≈ 4-5K tokens") and the
  INF-021 recalibration silently moved the guard's effective char
  ceiling from 28,000 to 18,200 without adjusting the budget.
- The guard is therefore diverting a request Groq would serve in
  ~0.5 s at ~36% of its 8,000 TPM cap. The diverted request then
  depends entirely on the fallback ladder — which is broken by D2.

### D2: gemini-3.8-flash 503 high-demand persists, and its misses are invisible

- Live journal: `Gemini model gemini-3.8-flash experienced 503 high
  demand; failing over to gemini-3.6-flash` at `00:45:31`, `00:45:34`,
  and again `03:50:37` (INF-025's probe window). Probe A this run
  (~05:18 IST): `gemini-3.8-flash` → HTTP 200 in 8.54 s but served by
  `gemini-3.6-flash` — 3.8 has not served directly in ANY measurement
  (INF-005: 0/20; INT-021; INF-025; this run). `gemini-3.6-flash`
  serves in 0.62 s (probe B); `qwen/qwen3.8-27b` serves in 0.32 s
  (probe C).
- The 15 s timeout in the task title is `PRIMARY_ATTEMPT_MAX_SECONDS`
  (gateway primary slice, INF-010): journal `00:45:47 GATEWAY:
  Provider 'gemini' timed out after 15.0s (TimeoutError,
  model=gemini-3.8-flash)`. The adapter's internal 3.8→3.6 failover
  runs INSIDE the primary attempt with a fresh 60 s httpx timeout, so
  a slow 3.6 attempt is cut at the 15 s slice and the ladder gets the
  remaining budget — which it then also fails to use (Inference
  returned 503 to IntelX at `00:46:03`, `00:46:04`, `00:46:57`).
- Why 3.8 keeps being picked: the REL-049 servability tracker only
  records outcomes for the model the ROUTE attempted. Ladder-rung
  attempts are never recorded, so the Gemini-rung 503s leave no trace
  and the 10-miss quarantine can never latch from ladder traffic. And
  the in-process tracker resets on every Inference restart (04:22:47
  IST today) — any streak is wiped.
- The 15 s slice itself is NOT changed: INF-022 measured the
  alternative and the decision is KEEP the deadline. The defect is
  that the slice is spent on a known-broken model, not that it is
  too short.

### D3: provenance reports `fallback_reason: null` when the flagship does not serve

- Probe A and probe E both return `fallback_reason: null` while the
  served model differs from the selected model. The Gemini adapter's
  internal 3.8→3.6 failover attaches no provenance, so the unified
  manager (which reads `fallback_reason` from the gateway response's
  `fallback_provenance`) has nothing to report. INF-025 §4 flagged
  this as unverified; this run verifies it as a live gap.

## 2. The fix (three changes, each independently verifiable)

### Fix 1 — IntelX synthesis budget 16,000 → 14,000 chars (the unblocker)

- `IntelX/intelx/api/grounded_live_research.py`: `supplied, remaining
  = {}, 14_000` (was 16,000). Per-doc cap stays 6,000.
- Worst-case prompt now measures 6,437 estimated tokens (regression
  test, §4) — 563 under the guard. The old budget measures 7,206 —
  over. The budget is sized to the gateway ESTIMATOR, not to Groq's
  true count, because the estimator is the guard's boundary.
- The INF-021 calibration is deliberately NOT touched: the 2.6
  chars/token estimator and the 7,000-token limit are a measured,
  deliberate safety decision (dense code prompts must stay blocked);
  the caller was the part that drifted. No evidence material is lost
  that the draft contract needs: 3 findings max, quotes ≤ 500 chars,
  and the budget still supplies 14,000 chars of source text.

### Fix 2 — gateway feeds the servability tracker with ladder-rung outcomes

- `Inference/app/providers/gateway.py`: new `_record_ladder_rung_outcome`
  + four call sites (OpenRouter dynamic rung success/failure,
  waterfall rung success/failure in `_execute_dynamic_fallback`).
- Scoping (no double counting): only rung models DIFFERING from the
  requested model are recorded — the requested model itself is left to
  the route layer, which already records it. Recording is best-effort
  and can never break routing.
- Effect: the next synthesis-shaped failure records a miss for the
  rung model that actually failed (e.g. `gemini-flash-latest`), so
  quarantine can latch from ladder traffic as REL-049 designed it.
  The 3.8 streak still accrues from route-attempted misses (direct
  names + policy retries); the restart-wipe limitation of in-process
  tracker state is noted as a follow-up, not fixed here (persisting
  tracker state is a larger change).

### Fix 3 — Gemini adapter attaches fallback provenance on the 503 failover

- `Inference/app/providers/gemini.py` `generate()`: when the 3.8→3.6
  failover serves, the response carries `fallback_provenance`
  (requested/actual provider+model, `fallback_reason` naming the 503
  high demand). The unified manager already surfaces that field, so
  the route's provenance block will now name the cause instead of
  reporting null. Streaming path unchanged (it yields bare text
  chunks and has no provenance channel — log-only there, as before).

### Not changed, and why

- 15 s primary slice (`PRIMARY_ATTEMPT_MAX_SECONDS`): unchanged.
  INF-022 measured the tail and the decision is KEEP the deadline.
- `gemini-3.8-flash` suitability ranking: NOT statically demoted.
  The tracker owns availability-vs-ranking; a static demotion would
  fight it and go stale on recovery (probe-back handles recovery).
- Groq guard estimator / limit: NOT recalibrated (see Fix 1).
- No env changes, no model-pin changes: the qwen hint serves
  (0.32 s), the 3.6 pin is correct (INF-025), the 3.8 failure is a
  capacity failure, not a pin error.

## 3. Live probes (Server 1, ~05:18–05:25 IST, fleet key read server-side, never printed)

| Probe | Request | Result |
|---|---|---|
| A | `gemini-3.8-flash`, "Reply with exactly this word: PROBE-38", max_tokens 20 | HTTP 200, 8.54 s, served by `gemini-3.6-flash`, `fallback_reason: null` — 3.8 still does not serve |
| B | `gemini-3.6-flash`, same shape | HTTP 200, 0.62 s, served under its own name |
| C | `qwen/qwen3.8-27b`, same shape | HTTP 200, 0.32 s, served under its own name by Groq |
| D | `qwen/qwen3.8-27b`, 17,602-char prose prompt (est. 6,770 tokens, under guard) | HTTP 200, 0.55 s, Groq served; Groq-counted `prompt_tokens: 2,822` vs gateway estimate 6,770 (2.4x overestimate) |
| E | `qwen/qwen3.8-27b`, 18,438-char prose prompt (est. 7,091 tokens, over guard) | Guard tripped; HTTP 200, 7.79 s, served by `gemini-3.6-flash`, `fallback_reason: null` — reproduces the INT-021 diversion live |

Inference health 200 throughout; service restarted 04:22:47 IST
(MainPID 2591464, NRestarts 0); deployed checkout `84739a0d` at probe
time (main has since moved to `491a63e9`; the work PR is rebased onto it).

## 4. Tests (local venv, this run)

- `Inference/tests/test_rel047_gateway_guards.py` +
  `test_gemini_token_accounting.py`: **24 passed** (incl. 2 new
  ladder-feeding tests + 2 new 503-provenance tests).
- `test_rel049_model_servability.py` + `test_inf017_unified_groq_size_guard.py`
  + `test_inf022_routing_receipts.py`: **27 passed**.
- `test_gateway_fallback_key_rotation.py` + `test_hardened_gateway.py` +
  `test_inf010_degraded_latency.py` + `test_inf015_flash_lite_catalogue.py` +
  `test_providers.py`: **31 passed**.
- `IntelX/tests/test_int005_verification_pass.py`: **9 passed** (incl.
  new `test_synthesis_prompt_stays_under_groq_guard`: full-budget
  prompt estimates 6,437 tokens, 563 under the guard; old budget
  measures 7,206, over).
- Total: **91 passed, 0 failed.** `ruff check` on the six touched
  files: 3 pre-existing findings only (I001 import order, C408
  `dict()`, F401 unused `pytest` import — all in untouched lines);
  no new findings from this change. `git diff --check` clean.

## 5. Deploy + re-probe plan (needs Muse's clearance)

1. Muse merges the work PR on green CI.
2. Muse clears the deploy (Inference on Server 1 + IntelX on Server 2
   — both carry a fix file; restart both services, verify
   `/health` 200 + checkouts).
3. Re-probe, exactly as INT-021 did: WF-001 IntelX leg, bus
   (`POST /api/v1/dispatch/send?agent=IntelX&action=research_live`)
   + chat (`POST /api/chat`, "Research the latest AI model
   releases and give me the highlights"). Green = a synthesised brief
   with sources (`answer_kind: source_attributed_model_draft`), not
   raw findings. That unblocks Muse 7's INT-020 run 3; run 3 itself
   is Muse 7's to run.
4. If the re-probe still fails, the remaining gate is named with
   evidence in the follow-up post — the journal lines to watch are the
   Groq-guard line (must be ABSENT for synthesis) and the 3.8 503
   line (must be ABSENT from the retry path, or present only with a
   serving 3.6 + a non-null `fallback_reason`).

## 6. Board filing note — the coordinator's INF-026 record was a ghost

- Board PR #1439 (merge `6801462`) filed the INF-026 record — and the
  FUT-022 spare — immediately after TASK-REGISTRY-001's `defect:`
  value, whose double-quoted string never closes (line 2761 on main
  `491a63e9`). The quote swallows lines 2761–2810, so NO YAML parser
  sees either record (verified: parsed task list on main has 673
  tasks with neither `TASK-INF-026` nor `TASK-FUT-022` in it). Same
  defect class as the stranded WF-005/WF-006 the file itself
  documents. The validator still reported VALID because it only counts
  parsed records — a ghost record is invisible to it too.
- This work PR removes the ghost INF-026 text and files the CLAIMED
  record before `task_id_warnings:`, per standing orders. The
  historical defect string is left byte-identical (the 2026-11-13
  record is not mine to rewrite). FUT-022 is left as a ghost inside
  the same quote (lines 2762–2789) — coordinator to re-file it; its
  draft text is preserved in place.
- After this PR the validator reports 674 parsed records (673 + INF-026).

## 7. Residual risks (stated, not hidden)

- If Groq itself fails transiently during run 3, the policy retry
  still picks `gemini-3.8-flash` first (its #1 chat ranking) and burns
  the 15 s slice on the 3.8→3.6 cascade; 3.6 usually serves in
  ~8–10 s inside the slice (probes A / INF-025) but exceeded it once
  (00:45:47). The tracker quarantine is the mechanism that retires
  3.8 from the pick; it needs 10 route-attempted misses and resets on
  restart.
- The guard fix assumes synthesis prompts stay prose-shaped. A dense
  (code/minified) prompt near the ceiling is still correctly blocked
  by the calibrated estimator — that is the guard working as designed.

— Muse 9, 2026-11-23 ~05:38 IST
