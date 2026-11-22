# TASK-INF-LLM-003 — Gemini deadline follow-up: completion times for ~9k-token prompts

Date: 2026-11-22, harness run ~08:41–08:50 IST (gateway trial completed
08:49:49 IST). Prober: Muse 2. Task: measure Gemini completion time for
~9k-token prompts (the INF-019 probe size) before any deadline change is
decided. Measurement only: no deadline, gate, or routing change in this
task, and none is made by this report.

## What was measured

Prompt: the exact INF-019 probe A construction — a code-review task over
a 400-function Python module (400 identical `def add` helpers),
35,214 chars, 8,803 tokens by the gateway's own estimator (chars // 4).
Model requested: `gemini-flash-latest` (the INF-019 reroute target).
Output: `max_tokens=200`, `temperature=0`.

Method: a harness process on Oracle Server 1 in the live Inference
environment (venv312, cwd `/opt/friday_universe/Inference`, the service's
own `.env`), separate from the running `Inference.service`, which was
never touched, restarted, or reconfigured. Two variants:

- **A. Direct Gemini adapter calls (4 attempts)** — the adapter called
  directly with a 150 s timeout, so the gateway's 15 s primary-attempt
  slice cannot cut the call off. This measures Gemini's true completion
  time for the prompt.
- **B. Gateway path (1 call, default 60 s budget)** — the production
  reroute behaviour, to confirm it is unchanged since INF-019.

Live settings read on S1 during the run: `REQUEST_TIMEOUT = 60.0`,
`PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`,
so the primary slice is `min(60 x 0.6, 15) = 15.0 s`. S1 checkout
`706f7690`. Gemini key pool: 15 keys, all active before and after.

## Results

### A. Direct Gemini completion times (full prompt, 35,214 chars)

| Trial | Elapsed | Upstream latency | Served model | Outcome |
|-------|---------|------------------|--------------|---------|
| 1 | 6.38 s | 1.31 s | gemini-3.6-flash | Served, 237 chars, finish STOP, 55 completion tokens |
| 2 | 99.32 s | 98.61 s | gemini-flash-latest | Served, 462 chars, finish STOP, 107 completion tokens |
| 3 | 67.32 s | 67.24 s | gemini-flash-latest | Served, 216 chars, finish MAX_TOKENS, 44 completion tokens, 152 reasoning tokens |

All three served real, correct answers (each identifies the 400
redefined `add` functions). Gemini's own token count for the prompt is
**13,519 prompt tokens on every trial** — the gateway's chars // 4
estimator (8,803) understates Gemini's true prompt size by ~54% (see G1).

### A2. Direct call on the gateway-compressed prompt

The gateway's token compression shrinks the prompt to 32,814 chars /
8,203 est. tokens (-7%). The compressed attempt did **not** complete
within the 150 s cap (`TimeoutError`, 153.29 s elapsed, no completion).
One sample only — it shows compression does not rescue the deadline for
this prompt shape; it is not a general claim about compression (see G4).

### B. Gateway path, default budget (INF-019 repeat)

Elapsed 21.39 s. Gemini's primary attempt was cut at **14.7 s** —
identical to INF-019 probe A, 2/2 — and the fallback ladder served via
OpenRouter `nvidia/nemotron-3.5-lightning:free` (fallback provenance:
requested `gemini/gemini-flash-latest`, actual
`openrouter/nvidia/nemotron-3.5-lightning:free`, reason "Request deadline
exceeded for provider 'gemini' after 14.7s"). This is the **third**
identical occurrence of the 14.7 s Gemini deadline miss on this prompt.

## Recommendation: KEEP the deadline — do not raise it on this evidence

- Only **1 of 4** direct attempts finished inside the 15 s primary
  slice (trial 1, 6.38 s), and that one was served as
  `gemini-3.6-flash`, not the requested `gemini-flash-latest` (see G2)
  — so even the fast tail is not reliably the reroute target.
- Completion times are wildly variable: 6.4 s, 67.3 s, 99.3 s, and
  >150 s. No deadline in a sane primary-slice range covers that tail;
  a cap that did would be >=150 s, and would hold every timed-out
  primary for 2.5 minutes before the fallback ladder runs.
- The fallback already serves a correct answer end-to-end in 21–53 s
  (21.39 s here; 53.3 s / 31.5 s in INF-019 probe A). The reroute
  path works as a system; it is the Gemini rung, not the request,
  that misses.
- If the coordinator wants Gemini itself to serve oversized prompts,
  that is a separate design decision — a different reroute target, or
  a dedicated long-budget path for the reroute — not a deadline tweak.
  A larger sample would be needed to pin any deadline, but no sample
  size fixes the tail problem for a 15 s slice.

## Safety and service state

- No key value was read, printed, logged, or stored. Key pools
  unchanged (gemini 15 total / 15 active / 0 quarantined, before and
  after; groq 15/15/0, openrouter 15/15/0, nvidia 2/2/0).
- Failover log went 0 -> 1 event (the gateway trial only; the direct
  adapter calls bypass the gateway and log nothing, by design).
- Live service healthy before and after (`/health` 200, MainPID
  1932891 unchanged). Direct adapter calls bypass the gateway rate
  limiter; 4 calls over ~9 minutes is a light load, noted here.
- S1 harness artefacts: `/tmp/llm003_measure_harness.py`,
  `/tmp/llm003_measure.json`, `/tmp/llm003_measure.log`.

## Gaps and observations

- **G1 — the token estimator understates Gemini's prompt size.**
  Gateway estimate 8,803 tokens vs Gemini's own 13,519 prompt tokens
  for the same prompt (+54%). The "9k-token prompt" is a 13.5k-token
  prompt to Gemini. The 7,000-token Groq guard is also measured in
  estimator tokens, so prompts near the guard are larger than they
  look to the provider. (File/line: `Inference/app/providers/gateway.py`
  `estimate_prompt_tokens`, chars // 4.)
- **G2 — the fast trial was served as a different model.** Trial 1
  requested `gemini-flash-latest` but was served as `gemini-3.6-flash`;
  trials 2–3 were served as `gemini-flash-latest`. The `-latest` alias
  resolution is not pinned, so the one sub-15 s completion may not be
  the same model path as the slow ones.
- **G3 — the fallback model answers with a thinking trace.** As in
  INF-LLM-002 G3, `nvidia/nemotron-3.5-lightning:free` returned a
  thinking trace ("Here's a thinking process: ...") instead of the
  requested review format. Observation, not a defect.
- **G4 — compression barely shrinks this prompt.** 35,214 -> 32,814
  chars (-7%), and the compressed attempt was the slowest (>150 s).
  One sample; not a general claim about compression.

## Reproduction

Harness (kept in the worker notes, run on Server 1):
`PYTHONPATH=/opt/friday_universe/Inference /opt/friday_universe/venv312/bin/python /tmp/llm003_measure_harness.py`
from `/opt/friday_universe/Inference`. It rebuilds the INF-019 prompt
byte-identically, runs the direct trials (adapter timeout 150 s), the
compressed trial, and one gateway-path trial, and writes
`/tmp/llm003_measure.json`.

— Muse 2
