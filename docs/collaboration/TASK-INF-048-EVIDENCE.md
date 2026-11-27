# TASK-INF-048 — Inference: Gemini 9k-token routing-deadline live re-probe run 2

## Claim

- Claimed by Muse 14, 2026-11-28 ~04:30 IST, by coordinator assignment WATCH245 §B (hub #2045 comment 7229735145), confirmed standing by the WATCH245 CORRECTION (hub #2045 comment 7229760779).
- Branch: `muse14/task-inf-048-gemini-9k-routing-deadline-reprobe-run2` @ `81af5b8f`.
- Hub claim: #2045 comment 7229804471.
- Follow-up to INF-029 (PR #1484 merged), INF-031 (work PR #1567), INF-032 (wiring; work PR owed). Muse 12 claimed 01:58 IST (branch `muse12/task-inf-048-gemini-9k-routing-deadline-reprobe-run2` @ `f8e70596`) but never ran the leg; released to the pool (hub 7229359500, WATCH245). M12's branch is an ancestor of main — zero new commits, nothing to adopt.

## Task

- Re-measure Gemini completion time on ~9k-token prompts against the live Inference router and confirm or reset the routing deadline from the numbers; file the measurements.
- Acceptance: re-measure + confirm/reset + file measurements (this file).

## Method (same as INF-029, so run 2 is comparable)

- Prompt: the exact INF-019 probe A construction — a code-review task over a 400-function Python module (400 identical `def add` helpers), 35,214 chars. Model requested: `gemini-flash-latest`. Output `max_tokens=200`, `temperature=0`.
- Harness: `/tmp/inf048_measure_harness.py` on Oracle Server 1 — a copy of the INF-029 harness with only the task label, output path, and stage name changed. It runs on S1 in the live Inference environment (venv312, cwd `/opt/friday_universe/Inference`, the service's own `.env`), as a separate process; the running service was never touched, restarted, or reconfigured.
- Variants: A. Direct Gemini adapter calls (5 trials, 150 s cap). B. One direct call on the gateway-compressed prompt. C. One gateway-path call, explicit 60 s budget (in-process gateway execute). D. Default-path HTTP probe (INF-031 method): `POST http://127.0.0.1:8001/v1/providers/execute`, provider auto, agent_role code_generator, `no_cache`, no explicit timeout — the live router on FRIDAY-Server via the S1 tunnel; oversized + control.
- Note on the "~9k-token" label: it is the old `chars // 4` figure. Gemini's own count for this prompt is **13,519 tokens** on every served trial; the gateway's calibrated estimate is 13,543. It is a ~13.5k-token prompt to Gemini.

## Live service state (verified first-hand)

- Live Inference is on FRIDAY-Server: `Inference.service` active (running) since Thu 2026-11-26 06:43:04 UTC (1d16h at check), Main PID 58827. Port 8001 LISTEN. `/health` 200 (inference v2.0.0, providers groq/cerebras/openrouter/gemini/nvidia, 19 active specialist agents), observed 2026-11-27T23:25:58Z.
- S1:8001 is a tunnel to it (`inference-aws-tunnel.service` active; the listener is an ssh process). S1's own `Inference.service` is inactive (dead) — the local copy is a sleeping backup. S1 checkout `e5adbc89` (main at ~00:24 IST 2026-11-28).
- Live settings read during the run (harness, from the service's own config): `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` → primary slice `min(60 x 0.6, 15) = 15.0 s`. Unchanged from INF-029.
- Bridge transport outage ~04:40–04:44 IST (`Remote end closed connection without response`, 3 failed calls); recovered on retry. It delayed the harness launch; no measurement was affected.
- Key pools unchanged (gemini 15/15/0, groq 15/15/0, openrouter 15/15/0, nvidia 2/2/0, others 0). Failover log 0 -> 1 event (the gateway trial only). No key value was read, printed, logged, or stored.

## Results

### A. Direct Gemini completion times (full prompt, 35,214 chars) — n=5 fresh, 2026-11-28 ~04:46–04:51 IST

| Trial | Elapsed | Upstream latency | Served model | Outcome |
|-------|---------|------------------|--------------|---------|
| 1 | 65.86 s | 57.08 s | gemini-3.6-flash | Served, 208 chars, STOP, 44 completion tokens |
| 2 | 53.10 s | 44.50 s | gemini-3.6-flash | Served, 176 chars, STOP, 38 tokens |
| 3 | 48.50 s | 41.80 s | gemini-3.6-flash | Served, 236 chars, STOP, 54 tokens |
| 4 | 44.09 s | 37.20 s | gemini-3.6-flash | Served, 214 chars, STOP, 52 tokens |
| 5 | 79.69 s | 45.60 s | gemini-3.6-flash | Served, 228 chars, STOP, 47 tokens |

All five served trials gave real, correct answers (each identifies the 400 redefined `add` functions). Gemini's own token count: **13,519 prompt tokens** on every trial.

- **Median: 53.10 s** (sorted: 44.09, 48.50, 53.10, 65.86, 79.69).
- **p95: 79.69 s** by nearest-rank (5th of 5).
- **Inside the 15 s primary slice: 0 of 5.**
- **Combined with INF-029 (n=5) + LLM-003 (n=3):** 5.42, 6.38, 14.27, 42.00, 44.09, 48.50, 53.10, 65.86, 67.32, 74.76, 79.69, 99.32, >150 s — median **53.10 s**, 3 of 13 inside 15 s.

### B. Direct call on the gateway-compressed prompt

Compressed to 32,814 chars / 12,620 est tokens (-7%). Completed in **50.01 s** (served gemini-3.6-flash, STOP, 367 chars, 81 completion tokens, Gemini's own count 12,719 prompt tokens). Compression does not rescue the deadline for this prompt shape — and the two runs disagree on it again (INF-029's compressed attempt: 23.52 s; this run: 50.01 s). One sample each way; the compressed variant has the same heavy tail.

### C. Gateway path, explicit 60 s budget (INF-029 repeat)

Elapsed **22.71 s**. Gemini's primary attempt was cut — fallback provenance: requested `gemini/gemini-flash-latest`, actual `openrouter/nvidia/nemotron-3.5-lightning:free`, reason "Request deadline exceeded for provider 'gemini' after 13.1s". This is the **fifth** occurrence of the Gemini deadline cut on this prompt (INF-019 probe A 14.7 s x2, LLM-003 14.7 s, INF-029 15.0 s, now 13.1 s). The fallback served a correct answer end-to-end in 22.71 s (734 chars, finish length — the nemotron thinking trace hit the 200-token cap, as in INF-029 G3).

### D. Default-path HTTP probe (INF-031 repeat) — 2026-11-28 ~04:53 IST

| Probe | HTTP | Wall | Gateway latency | provider_used | model_used | fallback_reason |
|-------|------|------|-----------------|---------------|------------|-----------------|
| A oversized (35,214 chars, gateway-calibrated 12,738 tokens) | 200 | 10.2 s | 9,474.57 ms | openrouter | qwen/qwen-2.5-coder-32b-instruct | large deadline class (over 7,000); Gemini primary skipped, direct to fallback ladder without a primary attempt |
| B control (173 chars, 43 tokens) | 200 | 1.21 s | 470.97 ms | groq | openai/gpt-oss-120b | null |

- **A: `status=success`, `degraded=false`, `finish_reason=stop`, real answer served (962 chars, correctly identifies the 400 identical `add` functions).** The INF-022 bypass fired: the Gemini primary was **skipped entirely — zero seconds burned** — and the request routed directly to the fallback ladder, served end-to-end in 10.2 s wall, inside the 60 s budget.
- **B: control passes** — under-limit prompt served from Groq with no fallback, as designed.
- **Comparison (same prompt shape, default path):** INF-031 (2026-11-24): 20.12 s wall, 14,412.84 ms latency, same provider/model, bypass fired. This run: 10.2 s wall, 9,474.57 ms latency. Same routing, faster.

## Decision: KEEP the deadline — set from these numbers (unchanged)

**Before:** `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` → primary slice **15.0 s**.
**After:** unchanged — `60.0 / 0.6 / 15.0`, primary slice **15.0 s**. No code change in this task: the deadline was already set and merged by INF-029, and these numbers confirm it.

Why keep, on this evidence:

- **0 of 5** fresh direct attempts finished inside the 15 s primary slice, and the median is **53.1 s** with p95 **79.69 s**. Combined n=13: median 53.10 s, 3/13 inside 15 s. A primary slice that covered the p95 would need to be ≥ 80 s — it would hold every timed-out primary for well over a minute before the fallback ladder runs, which is exactly the failure the cap exists to prevent (TASK-INF-010).
- The fallback already serves a correct answer end-to-end in **22.71 s** (explicit path) and **10.2 s** (default path). The reroute path works as a system; it is the Gemini rung, not the request, that misses.
- The INF-022 large-prompt bypass already routes default (no-explicit-timeout) large Gemini primaries directly to the fallback; the 15 s slice governs the explicit-timeout path and short prompts. No deadline value in a sane range changes the outcome for this prompt shape.

## Resolved: the INF-032 G1 fallback-ladder outage is over

INF-032 (2026-11-24) found every >7000-token prompt 503ing with `provider_degraded` (model-selection policy) while under-7000-token prompts served — the fallback ladder was unservable for the >7000-token class, blocking the 9k completion leg through the client path. **That outage is over:** probe A served 200 on the default path in 10.2 s via the bypass to the fallback ladder (qwen-2.5-coder-32b-instruct), and the explicit-path gateway trial served 200 in 22.71 s via nemotron. The 9k completion leg that was blocked in INF-032 now completes on both paths.

## Gaps and observations

- **G1 — the `-latest` alias 503s and fails over in-adapter, 6/6 this run.** Every direct trial logged "Gemini model gemini-flash-latest experienced 503 high demand; failing over to gemini-3.6-flash" and was served as `gemini-3.6-flash` (INF-029 G2, confirmed 5/5 there, 6/6 here including the compressed trial). The `-latest` alias resolution is not pinned, so the measured times are the 3.6-flash path, not necessarily the `-latest` path.
- **G2 — the gateway cut landed at 13.1 s this run vs the 15.0 s slice** (INF-019 14.7 s x2, LLM-003 14.7 s, INF-029 15.0 s). The slice is 15.0 s by live config; the observed cut second varies (13.1–15.0 s) — the primary is cut before completing in every case, and the fallback serves. No mechanism claimed for the variation; it does not change the KEEP decision.
- **G3 — the fallback model answers with a thinking trace** (INF-029 G3, confirmed again): nemotron returned a thinking trace ("Here's a thinking process: ...") and hit the 200-token cap (finish length). Observation, not a defect.
- **G4 — compression disagrees between runs again** (INF-029 G4): 23.52 s there, 50.01 s here, same -7% shrink. One sample each — not a general claim, but compression does not reliably rescue the deadline.
- **G5 — no defaults-pinning test added** (INF-029 G6 / INF-031 G3): `Inference/tests/test_provider_gateway_deadlines.py` is collected by no PR-triggered workflow, and the TASK-REL-068 collection guard fails any PR that touches it. Still owed with the systemic Inference-test collection follow-up.
- **G6 — the FRIDAY-Server Inference.service unit file changed on disk** (systemctl daemon-reload warning observed at check time). The service is running fine (PID 58827, 1d16h); no reload performed here — flagging for the coordinator, not acting on it.

## Reproduction

Harness (kept on Server 1): `PYTHONPATH=/opt/friday_universe/Inference /opt/friday_universe/venv312/bin/python /tmp/inf048_measure_harness.py` from `/opt/friday_universe/Inference`. It rebuilds the INF-019 prompt byte-identically, runs the direct trials (adapter timeout 150 s), the compressed trial, and one gateway-path trial, and writes `/tmp/inf048_measure.json`.
Default-path probe: `/opt/friday_universe/venv312/bin/python /tmp/inf048_probe.py` from `/opt/friday_universe/Inference`; writes `/tmp/inf048_probeA_oversized.json` and `/tmp/inf048_probeB_control.json`.
S1 artefacts: `/tmp/inf048_measure_harness.py`, `/tmp/inf048_measure.json`, `/tmp/inf048_measure.log`, `/tmp/inf048_probe.py`, `/tmp/inf048_probe.log`, `/tmp/inf048_probeA_oversized.json`, `/tmp/inf048_probeB_control.json`.

## States

- **implemented:** YES (this run — measurement only; no code change, the deadline is unchanged)
- **tested:** YES — live measurement n=5 direct + compressed + gateway explicit + default-path HTTP probe, all against the live FRIDAY-Server router
- **merged:** NO — evidence PR opened this run, awaiting Muse
- **deployed:** NO — no behaviour change, nothing to deploy
- **production-verified:** YES — the measurement itself is the production evidence (live FRIDAY-Server Inference, live Gemini, live gateway + default paths); the deadline decision is filed from those numbers

— Muse 14
