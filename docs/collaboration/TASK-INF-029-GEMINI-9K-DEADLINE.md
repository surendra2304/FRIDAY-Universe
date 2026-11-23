# TASK-INF-029 — Gemini completion times on ~9k-token prompts (n=5), routing deadline set from the numbers

Date: 2026-11-23, harness run ~14:47–14:51 IST. Prober: Muse 4. Assignment: coordinator watch 7096098820 (2026-11-23 14:30 IST) — re-slotted from Muse 2 (3 consecutive no-session self-checks, zero commits since claim 10:39 IST). Claim: branch `muse4/task-inf-029-gemini-9k-deadline` from main c97dacff (hub claim comment could NOT be posted — issue #35 hit exactly 2,500 comments and GitHub now refuses new comments, 403 "Commenting is disabled on issues with more than 2500 comments"; the board owner flip to muse_4 landed via coordinator board PR #1480, merge b1b04db2).

## What was measured

Same prompt and method as TASK-INF-LLM-003 (PR #1304, merged), so the samples are comparable: the exact INF-019 probe A construction — a code-review task over a 400-function Python module (400 identical `def add` helpers), 35,214 chars. Model requested: `gemini-flash-latest` (the INF-019 reroute target). Output: `max_tokens=200`, `temperature=0`.

Method: a harness process on Oracle Server 1 in the live Inference environment (venv312, cwd `/opt/friday_universe/Inference`, the service's own `.env`), separate from the running `Inference.service`, which was never touched, restarted, or reconfigured. Adapted from the LLM-003 harness (`/tmp/llm003_measure_harness.py`) with only the task label, output path, stage name, and trial count changed (3 → 5 direct trials). Two variants:

- **A. Direct Gemini adapter calls (5 trials)** — the adapter called directly with a 150 s timeout, so the gateway's 15 s primary-attempt slice cannot cut the call off. This measures Gemini's true completion time for the prompt.
- **B. Gateway path (1 call, explicit 60 s budget)** — the production reroute behaviour on the explicit-timeout path, to confirm it is unchanged since INF-019 / LLM-003. (An explicit caller timeout opts out of the TASK-INF-022 large-prompt direct-to-fallback bypass by design, so this trial exercises the primary slice itself.)

Live settings read on S1 during the run: `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`, so the primary slice is `min(60 x 0.6, 15) = 15.0 s`. S1 checkout `206cb79e` (main at harness time; board-only merges since). Gemini key pool: 15 keys, all active before and after.

## Results

### A. Direct Gemini completion times (full prompt, 35,214 chars) — n=5 fresh

| Trial | Elapsed | Upstream latency | Served model | Outcome |
|-------|---------|------------------|--------------|---------|
| 1 | 5.42 s | 2.41 s | gemini-3.6-flash | Served, 226 chars, finish STOP, 53 completion tokens |
| 2 | 150.13 s | — | — | **TimeoutError — did not complete within the 150 s cap** (right-censored) |
| 3 | 42.00 s | 6.51 s | gemini-3.6-flash | Served, 193 chars, finish STOP, 39 completion tokens |
| 4 | 14.27 s | 7.66 s | gemini-3.6-flash | Served, 244 chars, finish STOP, 54 completion tokens |
| 5 | 74.76 s | 9.35 s | gemini-3.6-flash | Served, 185 chars, finish STOP, 38 completion tokens |

All four served trials gave real, correct answers (each identifies the 400 redefined `add` functions). Gemini's own token count for the prompt is **13,519 prompt tokens on every served trial**.

- **Median: 42.00 s** (sorted: 5.42, 14.27, 42.00, 74.76, 150.13).
- **p95: 150.13 s by nearest-rank** (5th of 5; 135.06 s by linear interpolation). Trial 2 is right-censored — it never completed within 150 s — so the true p95 is **≥ 150 s** either way.
- **Inside the 15 s primary slice: 2 of 5** (trials 1 and 4; trial 4 at 14.27 s only just inside).
- **Combined with LLM-003 (n=8):** 5.42, 6.38, 14.27, 42.00, 67.32, 74.76, 99.32, >150 s — median **54.66 s**, 3 of 8 inside 15 s.

### A2. Direct call on the gateway-compressed prompt

The gateway's token compression shrinks the prompt to 32,814 chars / 12,620 est. tokens (-7%). This time the compressed attempt **completed in 23.52 s** (served gemini-3.6-flash, STOP, 125 completion tokens, Gemini's own count 12,719 prompt tokens) — unlike LLM-003, where the single compressed attempt timed out past 150 s. One sample each way; compression does not reliably rescue the deadline for this prompt shape, and the two runs disagree on it (see G4).

### B. Gateway path, explicit 60 s budget (INF-019 repeat)

Elapsed **18.34 s**. Gemini's primary attempt was cut at **15.0 s** — fallback provenance: requested `gemini/gemini-flash-latest`, actual `openrouter/nvidia/nemotron-3.5-lightning:free`, reason "Request deadline exceeded for provider 'gemini' after 15.0s". This is the **fourth** occurrence of the Gemini deadline cut on this prompt (INF-019 probe A 14.7 s ×2, LLM-003 14.7 s, now 15.0 s — same 15.0 s slice, the earlier cuts measured 14.7 s). The fallback served a correct answer end-to-end in 18.34 s.

## Decision: KEEP the deadline — set from these numbers

**Before:** `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` → primary slice `min(60 × 0.6, 15) = 15.0 s`.
**After:** unchanged — `60.0 / 0.6 / 15.0`, primary slice **15.0 s**. The decision is recorded in code: the `PRIMARY_ATTEMPT_MAX_SECONDS` field description in `Inference/app/core/config.py` now cites this measurement. A defaults-pinning test was NOT added in this PR: `Inference/tests/test_provider_gateway_deadlines.py` is collected by no PR-triggered workflow, and the TASK-REL-068 collection guard fails any PR that touches it; the pin belongs with the Inference-test CI-collection follow-up (see G6).

Why keep, on this evidence:

- Only **2 of 5** fresh direct attempts finished inside the 15 s primary slice, and the median is **42.0 s** with p95 **≥ 150 s**. A primary slice that covered the p95 would need to be ≥ 150 s — it would hold every timed-out primary for 2.5 minutes before the fallback ladder runs, which is exactly the failure the cap exists to prevent (TASK-INF-010).
- The fallback already serves a correct answer end-to-end in **18.34 s** on the gateway path. The reroute path works as a system; it is the Gemini rung, not the request, that misses.
- The TASK-INF-022 large-prompt bypass already routes default (no-explicit-timeout) large Gemini primaries directly to the fallback; the 15 s slice governs the explicit-timeout path and short prompts. No deadline value in a sane range changes the outcome for this prompt shape.
- The numbers are now filed at n=5 (this task) plus n=3 (LLM-003): combined median 54.66 s, 3/8 inside 15 s. No further sample size fixes the tail problem for a 15 s slice.

## Safety and service state

- No key value was read, printed, logged, or stored. Key pools unchanged (gemini 15 total / 15 active / 0 quarantined, before and after; groq 15/15/0, openrouter 15/15/0, nvidia 2/2/0).
- Failover log went 0 -> 1 event (the gateway trial only; the direct adapter calls bypass the gateway and log nothing, by design).
- Live service healthy before and after (`/health` 200, MainPID 2832486 unchanged). Direct adapter calls bypass the gateway rate limiter; 6 calls over ~5 minutes is a light load, noted here.
- S1 harness artefacts: `/tmp/inf029_measure_harness.py`, `/tmp/inf029_measure.json`, `/tmp/inf029_measure.log`.
- Bridge note: the first synchronous wait on the harness run timed out at the bridge client's 120 s read limit; the harness itself completed on S1 (~14:51 IST) and a fresh-session status check retrieved the results. No retry of the measurement was needed.

## Gaps and observations

- **G1 — the token estimator no longer understates Gemini's prompt size (LLM-003 G1, now resolved by TASK-INF-021).** The gateway's calibrated estimator gives **13,543 tokens** for this prompt vs Gemini's own **13,519** (0.2% apart). The "~9k-token" label in this task's title is the old `chars // 4` figure; the prompt is a ~13.5k-token prompt to Gemini by both counts.
- **G2 — every served trial came back as a different model than requested (LLM-003 G2, confirmed 5/5).** All five direct trials requested `gemini-flash-latest` and were served as `gemini-3.6-flash` (trials 1, 3, 4, 5; trial 2 timed out). The `-latest` alias resolution is not pinned, so the sub-15 s completions may not be the same model path as the slow ones — and the fast tail (5.42 s, 14.27 s) is entirely `gemini-3.6-flash`.
- **G3 — the fallback model answers with a thinking trace.** As in INF-LLM-002 G3 and LLM-003 G3, `nvidia/nemotron-3.5-lightning:free` returned a thinking trace ("Here's a thinking process: ...") instead of the requested review format. Observation, not a defect.
- **G4 — compression disagrees between runs.** 35,214 -> 32,814 chars (-7%) both runs; LLM-003's compressed attempt timed out past 150 s, this run's completed in 23.52 s. One sample each — not a general claim about compression, but it shows the compressed variant has the same heavy tail.
- **G5 — the gateway trial exercises the explicit-timeout path only.** The harness sets `extra_params={"timeout": 60.0}`, which opts out of the INF-022 large-prompt direct-to-fallback bypass by design. The 15.0 s cut measured here is the explicit-timeout path; the default path for a large prompt skips Gemini entirely. Both paths are consistent with the KEEP decision.
- **G6 — no PR-CI home for Inference unit tests.** `Inference/tests/test_provider_gateway_deadlines.py` (like most Inference tests) is collected by no PR-triggered workflow, so the TASK-REL-068 collection guard fails any PR that modifies it — this PR's `contracts` check failed on exactly that (guard reproduced locally: `UNCOLLECTED: Inference/tests/test_provider_gateway_deadlines.py`). A defaults-pinning test for the INF-029 decision was drafted and then omitted from this PR for that reason; it belongs with the systemic Inference-test collection follow-up.

## Reproduction

Harness (kept on Server 1): `PYTHONPATH=/opt/friday_universe/Inference /opt/friday_universe/venv312/bin/python /tmp/inf029_measure_harness.py` from `/opt/friday_universe/Inference`. It rebuilds the INF-019 prompt byte-identically, runs the direct trials (adapter timeout 150 s), the compressed trial, and one gateway-path trial, and writes `/tmp/inf029_measure.json`.

## States

- **implemented:** YES (this run)
- **tested:** YES — live measurement n=5 + compressed + gateway trials on S1; CI to be verified on the work PR head (Muse merges only)
- **merged:** NO — work PR opened this run, awaiting Muse
- **deployed:** NO — description/comment/test-only change; no behaviour change, nothing to deploy beyond the merge
- **production-verified:** YES — the measurement itself is the production evidence (live S1, live Gemini, live gateway path); the deadline decision is filed from those numbers

— Muse 4
