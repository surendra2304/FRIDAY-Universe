# TASK-INF-043 — checkpoint 2 (first live timing batch) — Muse TP10

Claim: hub #1483 comment 7194179426 (2026-11-26 19:31 IST). Branch
`musetp10/task-inf-043` from main `28cc4ecb`; scoping checkpoint 1
`caa1b2d8`. Coordination for this batch: hub 7195705037 (20:32 IST).
Batch run 2026-11-26 15:06:43–15:07:41 UTC (20:36–20:37 IST) via Friday
Bridge `run_shell` server 3 (FRIDAY-Server) under WATCH164 (hub
7193691912). Read-only HTTP probes only: no restart, no deploy, no env
flip, no server move, no live money.

## Live legs verified before probing (this run)

- Echo probe server 2 (Oracle Server 2, `friday-universe-vnic-2`): exit 0,
  expected output — `run_shell` route proven after schema review +
  one-line `ALLOWED_TOOLS` addition in TP10's bridge client.
- Server 3 (`friday-server`, up 2d10h, load 0.09): `Inference.service` and
  `FRIDAY.service` both active (since 2026-11-26 06:43 UTC); ports 8001
  and 10000 listening. Live checkout `/opt/friday_universe` @ `5b245ffd`
  (unchanged since INF-033).
- Live client timeout still **150.0 s**: live `escalation.py:318` default
  `"150"`, `_inference_timeout_s()` = 150.0 in-process (FRIDAY venv
  `/opt/friday_universe/venv/bin/python`), no env override in `.env` /
  `dispatch.env`. INF-032's 70 s wiring (60 s + 10 s) is merged on main
  (blob `ec979e19`, identical on main `49cfd862` and this branch) but
  **not deployed** — deploy still owed, needs coordinator clearance, not
  attempted here.
- Gateway live values: `REQUEST_TIMEOUT` 60.0 s (`config.py:283`),
  `PRIMARY_ATTEMPT_MAX_SECONDS` 15.0 (`config.py:462`).

## Method

Same prompt family as INF-019/031/033 (400/175/1 `add`-function module,
bug/style review), cache-busted with a run marker + helper offset so
numbers are fresh (INF-033 recorded a 0.01 s cache hit on identical
content). Oversized = 35,782 chars (~8,945 est. tokens by chars/4;
gateway tokenizer counted ~12,984 — see journal). Client path =
live `InferenceChatProvider.generate()` → `POST /v1/chat/completions`
(FRIDAY venv, live checkout). Direct leg = provider-identical payload
(`openai/gpt-oss-120b`, temperature 0.7, max_tokens 4096). Probe script
`/tmp/inf043_probe.py` on server 3 (PID 62999, backgrounded, result-file
polling; MCP client timeout is 45 s so no blocking long calls). Raw
results `/tmp/inf043_summary.json` + per-probe JSONs on server 3.

## Fresh results (2026-11-26, UTC)

| Probe | Prompt | Result | Wall | Served by | Notes |
|---|---|---|---|---|---|
| B control (client) | 231 chars (~57 tok) | HTTP 200 | **5.65 s** | gemini-3.5-flash-lite (as requested) | Routing `simple/math_expression`. Real answer, 325 chars. Slower than INF-033's 0.21 s (different route/model), still fast. |
| C mid (client) | 15,757 chars (~3,939 tok) | HTTP 200 | **1.12 s** | openai/gpt-oss-120b (as requested) | Routing `complex/long_input`. Real answer, 1,230 chars. |
| A oversized (client) | 35,782 chars (~8,945 tok) | HTTP 503 `provider_degraded` | **50.69 s** | — | `LLMProviderError: INFERENCE_UNAVAILABLE: HTTP 503`. Inside the 60 s budget; 150 s client timeout never binding. See journal. |
| D oversized (direct) | 35,782 chars | HTTP 503 `provider_degraded` | **0.01 s** | — | Instant typed rejection: "could only be served by a model outside the verified catalogue" (`requested_provider: groq`, `retryable: true`). No ladder wait on this leg. |

## Gateway journal (Inference.service, 15:06:50–15:07:41 UTC)

- `15:06:50` — `GATEWAY: Prompt over the Groq size guard (~12984 tokens > 7000); skipping the Groq primary and routing to the fallback ladder.`
- `15:07:13` — `GATEWAY: Provider 'gemini' timed out after 15.0s (TimeoutError, model=gemini-3.8-flash). Escalating to the fallback ladder instead of failing the request.`
- `15:07:13` — `GATEWAY: Primary provider 'gemini' failed. Initiating capability fallback for 'reasoning'.`
- `15:07:41` — two `POST /v1/chat/completions 503` (client A at 50.69 s wall; direct D instant).

Reading: size-guard bypass fires fresh; the Gemini primary attempt is
cut at exactly the 15.0 s slice (attempt start offset ~8 s after guard,
same shape as INF-033); the ladder then runs to a typed 503 inside the
60 s budget. No successful Gemini ~9k-token completion this batch —
the Gemini attempt timed out at the slice. INF-031 baseline (20.12 s
wall @ 9k tokens) has no fresh served counterpart yet.

## Provisional verdict (checkpoint 2 — not the task verdict)

- **60 s deadline: evidence supports KEEP.** Every return landed inside
  the budget (worst 50.69 s typed 503); failures are model
  availability / catalogue policy, not deadline breaches. No reset
  warranted on this batch.
- **Oversized (>7000) chat path: 0/2 served today** (INF-033: 1/2 served,
  40.39 s via gemini-3.6-flash). Ladder fragility persists; do not read
  INF-033's retry success as "fixed".
- **Still owed before the work PR:** (1) fresh served Gemini ~9k-token
  completion time (retry batch; acceptance leg 1), (2) direct
  `/v1/providers/execute` fresh probe (INF-033 served 1/1 there at
  10.52 s), (3) final confirm/reset filing with all numbers. INF-032
  deploy (150 s → 70 s live) remains a separate cleared-deploy item.

## Five states

implemented NO (no code change; reset only if final evidence warrants) /
tested NO (batch 1 executed and filed above; acceptance legs still
owed) / merged NO / deployed NO / production-verified NO.

## Next

Retry + execute-endpoint batch, then one work PR at completion (peer
full-diff review + fully green CI; never merge own PR; paired
verification by a different chat before complete). DB-011 live leg +
paired verification remain held pending coordinator ruling (asked in
hub 7195705037).

— Muse TP10
