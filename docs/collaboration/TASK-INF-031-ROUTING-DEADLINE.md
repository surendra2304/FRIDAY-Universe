# TASK-INF-031: Inference — set the routing deadline from the INF-019 9k-token timing evidence

**Worker:** Muse 11 · **Date:** 2026-11-24 · **Branch:** `muse11/task-inf-031-routing-deadline`
**Board:** TASK-INF-031 (Inference: set the routing deadline from the INF-019 9k-token timing evidence)
**Assignment:** coordinator queue top-up, watch 7111833560 (~01:05 IST): queue pos 3 after MEM-017 (blocked) → MEM-024. Taken immediately on MEM-024 completing (work PR #1555 open, awaiting merge), per Muse's follow-up "when a task finishes, take the next immediately". **Claim:** issue #1483 comment 7113828676 (~02:29 IST).

> STATUS: CHECKPOINT 2 — deadline filed from the measured times and proven live on the default path. Acceptance met; work PR #1567 open, awaiting merge. Board flip to IN_REVIEW owed via coordinator board PR (see Gaps).

## Acceptance (board)

The INF-019 evidence is read; a routing deadline is set in the router from the measured ~9k-token completion times; a probe proves slow completions route correctly and the deadline is filed with numbers.

## INF-019 evidence read first-hand

Source: `docs/verification/INF019_ROUTING_PROBES.md` (Muse 1, 2026-11-21 ~22:39–22:42 IST, live S1 Inference, `POST http://127.0.0.1:8001/v1/providers/execute`). Board record TASK-INF-019 (MERGED, PR #1241) corroborates.

- **Probe A — oversized, ~8.8k tokens** (code_generator, 35,214 chars, ~8,803 est tokens; journal ~8,880 incl. system instruction; over the 7,000-token guard). Ran twice:
  - A1 22:39:55 — HTTP 200, wall 53.3 s, gateway latency **29,802 ms**, `provider_used=openrouter`, `model_used=qwen/qwen-2.5-coder-32b-instruct`, fallback_reason "Request deadline exceeded for provider 'gemini' after **14.7s**".
  - A2 22:41:22 (repeat) — HTTP 200, wall 31.5 s, gateway latency **25,902 ms**, same provider/model/fallback.
  - Both: `status=success`, `degraded=false`, real answer served (~980 chars). Served by the openrouter fallback rung, not Gemini.
- **Probe B — under-limit control, ~43 tokens** (173 chars): HTTP 200, wall 4.63 s, latency **1,116 ms**, `provider_used=groq`, `model_used=openai/gpt-oss-120b`, `fallback_reason=null`, `degraded=false`. Real answer served.
- **Size-guard steering VERIFIED:** the oversized prompt never reached Groq — the unified path logged the TASK-INF-017 reroute warning (groq → gemini) before dispatch, both runs.
- **The intended gemini serve did NOT happen:** Gemini exceeded its 14.7 s provider deadline 2/2 on ~8.8k-token prompts.
- **Open question (INF-019, for Muse):** raise the Gemini provider deadline for the reroute path, pick a different reroute target, or accept the openrouter fallback as the working outcome for oversized prompts. No code changed in INF-019.

## Checkpoint 2 — the deadline as set, and the default-path live probe (2026-11-24 ~03:24 IST)

### The deadline, set from the measured times (TASK-INF-029, merged PR #1484)

The routing deadline for this prompt shape was set by TASK-INF-029 (Muse 4, 2026-11-23, n=5 fresh direct Gemini trials: 5.42 / 14.27 / 42.00 / 74.76 / >150 s, median 42.0 s, p95 >=150 s right-censored; combined n=8 with INF-LLM-003: median 54.66 s, 3/8 inside 15 s). Decision: **KEEP** — `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`, so the primary slice is `min(60 x 0.6, 15) = 15.0 s`. The decision is recorded in code, verified first-hand this run on main: `Inference/app/core/config.py` (`PRIMARY_ATTEMPT_MAX_SECONDS` field description cites the INF-029 numbers verbatim) and `Inference/app/providers/gateway.py` (TASK-INF-022 large-prompt bypass + INF-029 citations; `LARGE_PROMPT_TOKEN_THRESHOLD = GROQ_PROMPT_TOKEN_LIMIT = 7000`).

No new code change in this task: the deadline was already set and merged by INF-029. What INF-031 adds is the missing half of the acceptance — a live probe of the **default path** (no explicit timeout), which INF-029 did not exercise (its gateway trial used an explicit 60 s budget, which opts out of the INF-022 bypass by design; INF-029 G5).

### Live state probed

- `Inference.service` on Server 1: active (running) since 2026-11-24 00:00:06 IST, Main PID 3187253, `/health` 200 (checked via bridge `oracle_check_service`, 03:20 IST).
- S1 checkout `49126a41` (verified first-hand via bridge `run_shell`): gateway.py at that ref contains the INF-022 bypass (`fallback_direct`), the INF-029 citations, and `PRIMARY_ATTEMPT_MAX_SECONDS` — the live service runs the merged deadline code. No deploy was needed for this probe.
- Bridge transport flaked repeatedly this run (RemoteDisconnected / IncompleteRead, ~10 failed calls across the session, same class as the 00:47–01:35 IST outage); every call recovered on retry.

### Probe method

Script `/tmp/inf031_probe.py` on Server 1: byte-identical copy of the INF-019 probe (`/tmp/inf019_probe.py`) except the output prefix (`/tmp/inf031_*.json`), so the INF-019 artefacts are untouched. Same prompt construction (400-function module, 35,214 chars), same endpoint (`POST http://127.0.0.1:8001/v1/providers/execute`), `provider=auto`, `agent_role=code_generator`, `max_tokens=200`, `temperature=0`, `no_cache=true`, **no explicit timeout in the request body** — the default path, so the INF-022 large-prompt bypass applies. Launched in background (PID 3281982, 03:23 IST) to stay inside the bridge client's 45 s per-call limit; completed 03:24–03:25 IST. Summaries: `/tmp/inf031_probeA_oversized.json`, `/tmp/inf031_probeB_control.json`.

### Results

| Probe | HTTP | Wall | Gateway latency | provider_used | model_used | fallback_reason |
|-------|------|------|-----------------|---------------|------------|-----------------|
| A oversized (35,214 chars, 8,803 est tokens; gateway calibrated 12,738) | 200 | 20.12 s | 14,412.84 ms | openrouter | qwen/qwen-2.5-coder-32b-instruct | large deadline class (over 7,000); Gemini primary skipped, direct to fallback ladder without a primary attempt |
| B control (173 chars, 43 tokens) | 200 | 1.09 s | 999.82 ms | groq | openai/gpt-oss-120b | null |

- **A: `status=success`, `degraded=false`, `finish_reason=stop`, real answer served (944 chars, correctly identifies the 400 identical `add` functions).** The `fallback_reason` is the gateway's own receipt for the TASK-INF-022 bypass firing: the Gemini primary was **skipped entirely — zero seconds burned on a primary attempt that would miss** — and the request routed directly to the fallback ladder, served end-to-end in 20.12 s wall, inside the 60 s budget.
- **B: control passes** — under-limit prompt served from Groq with no fallback, as designed.
- **Comparison across runs (same prompt shape):** INF-019 A1/A2 wall 53.3 / 31.5 s with a 14.7 s Gemini burn before fallback; INF-029 explicit-path gateway 18.34 s with a 15.0 s cut; this run (default path) **20.12 s with no primary burn at all**. The slow completion now routes correctly by skipping the doomed primary instead of timing it out.

### Verdict

Acceptance met: the deadline is set in the router from the measured ~9k-token completion times (INF-029 KEEP: 60.0 / 0.6 / 15.0 s, filed in code), the probe proves slow completions route correctly on the default path, and the numbers are filed here.

## States

- **implemented:** YES — by TASK-INF-029 (merged PR #1484); no new code change in this task.
- **tested:** YES — live default-path probe on S1, both legs green (this run).
- **merged:** NO — work PR #1567 open (checkpoint 1 + 2), awaiting Muse.
- **deployed:** YES — live S1 already runs the code (checkout 49126a41 contains it; service started 00:00:06 IST); nothing further to deploy for this task.
- **production-verified:** YES — the live probe on S1 is the production evidence.

## Plan (from checkpoint 1, closed)

1. ~~Locate the routing deadline in the router code~~ — done: `gateway.py` (`GROQ_PROMPT_TOKEN_LIMIT = 7000`, large-class bypass) + `config.py` (60.0 / 0.6 / 15.0).
2. ~~Set the deadline from the measured times~~ — done by INF-029 (KEEP 15.0 s slice); filed in code + here with the numbers.
3. ~~Probe: rerun the INF-019 oversized probe and prove slow completions route correctly~~ — done, default path, 03:24 IST.
4. No live trading, no paid services. Code change rides in the work PR; I do not merge my own PR.

## Preconditions

- Board record on main 855f2515 (board blob c217c91c): INF-031 AVAILABLE, owner muse_11, branch null, pr null. Queue: MEM-017 (blocked, 0/3) → MEM-024 (IN_REVIEW, PR #1555) → INF-031.
- MEM-024 COMPLETE this run (probe 02:21–02:22 IST, all legs green, PR #1555 head 040520d1, CI pending on the new head).

## Gaps and observations

- **G1 — journal corroboration not captured this run.** `oracle_get_logs` (agent inference) returns a window ending 02:20 IST at both 200 and 600 lines — it does not reach the 03:24 probe, so no server-side "Large prompt ... skipping the primary attempt" journal line was captured. The routing proof rests on the gateway's own response receipts (`fallback_reason` + `provider_used` + latency), which are decisive on their own.
- **G2 — S1 config.py layout differs from main.** On S1 the settings sit at lines 277 / 444 / 456 vs main's 479 / 812 / 836, with the same description text; the live values are those INF-029 read on S1 (60.0 / 0.6 / 15.0) and the probe behaviour confirms the 15.0 s slice + bypass. A `.env` override was not re-checked this run (bridge flaked on that call); the probe outcome is the operative check and it matches the filed values.
- **G3 — defaults-pinning test still owed with the systemic Inference-test collection follow-up** (INF-029 G6): `Inference/tests/test_provider_gateway_deadlines.py` is collected by no PR-triggered workflow, and the TASK-REL-068 collection guard fails any PR that touches it. Not added here, for the same reason.
- **G4 — board flip to IN_REVIEW owed via coordinator board PR, not filed solo.** The claim hunk in PR #1567 was built on main 855f2515; main has since moved to 384950d9, and a solo 2.4 MB board edit risks the conflict class that dirtied Muse 15's PRs #1564/#1565/#1566 after board PR #1570. Flagged in the hub status for the next coordinator board PR (watch004 already carries flips).
- **G5 — token labels:** the "~9k-token" label is the old `chars // 4` figure; the gateway's calibrated estimate for this prompt is 12,738 tokens (INF-029 G1: Gemini's own count 13,519).

## Test data / live state

- Probe script: `/tmp/inf031_probe.py` on Server 1 (copy of `/tmp/inf019_probe.py`, output prefix `inf031_`).
- Summaries: `/tmp/inf031_probeA_oversized.json`, `/tmp/inf031_probeB_control.json` on Server 1. No test data left in any service; no keys read, printed, or stored.

— Muse 11
