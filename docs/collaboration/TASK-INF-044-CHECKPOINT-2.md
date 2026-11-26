# TASK-INF-044 — Checkpoint 2: repo-leg re-run + first live harvest

Date: 2026-11-26 ~20:45 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing
receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `3f10d754`, checkpoint 1).
Main at re-run: `49cfd862` (#1992 merged; WATCH167).

## 1. INF-022 test re-run on current main — 7/8 pass

Fresh shallow clone of main `49cfd862`; `Inference/tests/test_inf022_routing_receipts.py`
run first-hand in a local venv (pytest + fastapi/pydantic/httpx/sqlalchemy/
pytest-asyncio installed locally): **7 passed, 1 failed in 0.47 s.**

Passing (receipt shape, deadline classes, direct routing all intact):
- `test_deadline_class_boundary_is_the_groq_guard_limit` — boundary 7000 =
  GROQ guard; 18,200 chars short, 18,203 large.
- `test_inf019_prompt_is_large_class` — INF-019 shape 35,214 chars,
  ~13,519 tokens, large.
- `test_execute_routes_large_gemini_prompt_directly_to_fallback` — large
  Gemini prompt never attempts Gemini; served by openrouter; receipt
  fallback_used=true, fallback_direct=true.
- `test_explicit_timeout_opts_out_of_direct_skip` — explicit timeout:
  primary attempted even for large prompts.
- `test_execute_records_short_prompt_receipt_from_primary` — receipt fields
  (provider/model requested vs served, deadline_class short, timeout
  budget 60.0, latency) all present.
- `test_execute_records_error_receipt_and_reraises` — see failure below.
- `test_receipt_store_caps_at_limit_and_counts` + `test_receipts_newest_first`
  — ring caps at 100, counts correct, newest first.

## 2. The one failure is a STALE TEST, not a receipt regression

`test_execute_records_error_receipt_and_reraises` — FAILED: DID NOT RAISE
GatewayError. Fails with gemini + openrouter + groq all failing.

Root cause (verified first-hand, twice):
- `gateway.py` moved twice after INF-022: `dc201f5b` TASK-INF-030
  (2026-11-24, APInex as fallback provider) and `e020d882` TASK-INF-038
  (2026-11-25, needle fast-path). Confirmed via GitHub commits API on
  `Inference/app/providers/gateway.py`; test file unchanged since INF-022
  (`ca2587cd`).
- INF-030 added APInex as a FOURTH waterfall rung (gateway.py:1346:
  "Groq -> OpenRouter -> Gemini -> APInex"). The test's fail set covers
  only three providers, so with all three failing, execute() is served by
  the APInex fake: reproduced first-hand — calls
  `['gemini', 'openrouter', 'groq', 'apinex']`, served by `apinex`
  (model `free/qwen-3.8-max`), receipt outcome=success, fallback_used=true.
- The test's assumption ("three failures ⇒ GatewayError") predates the
  fourth rung. Fix (NOT applied here — audit scope; owed as a follow-up):
  add `"apinex"` to the fail set in that test.

## 3. Receipt coverage on current main — no gaps

- Receipts are recorded by the outer `execute()` wrapper (gateway.py:605
  error path / :614 success path), which wraps `_execute_inner`. The
  needle fast-path early return (INF-038, :674), the LiteLLM path, and the
  local tier all sit INSIDE `_execute_inner`, so every execute() records
  exactly one receipt, success or error. No coverage gap from INF-038.
- Receipt fields observed live (see §4): observed_at, capability, stage,
  provider_requested, model_requested, prompt_tokens_est, deadline_class,
  timeout_budget_s, outcome, provider_served, model_served, latency_ms,
  fallback_used, fallback_direct (+ `error` on error receipts).
- NOTE for the audit (INF-045's scope, but the audit's "silent-fallback"
  acceptance depends on it): success receipts carry NO fallback-reason
  field. Fallback cases can be listed from receipts, but the reason
  (timeout vs 429 vs 503) is not in the receipt — only the error text on
  error receipts. Flagged, not fixed here.

## 4. First live harvest — serving host identified, 4 real receipts

Clearance: owner ruling 7192682851 (run_shell granted to all worker chats,
18:25 IST) + WATCH164 reversing the live-gate closure. Bridge `tools/list`
flaky (2 failed runs, IncompleteRead/stream-ended — known SSE issue),
recovered on retry; `run_shell` confirmed in the tool list. All probes
below are READ-ONLY (curl /status, sha256sum, grep, ps, systemctl show).
No restarts, no deploys, no env flips, no key reads.

### Serving topology (corrected vs checkpoint 1's assumption)

- S1 port 8001 is NOT a local Inference service: it is
  `inference-aws-tunnel.service`, an SSH tunnel (process up since Tue Nov 24
  16:40:55) forwarding S1:8001 → FRIDAY-Server (15.134.130.145):8001.
- The serving Inference is on FRIDAY-Server (bridge server 3):
  `Inference.service` active running, uvicorn :8001, PID 58827, started
  Thu 2026-11-26 06:43:04 UTC (12:13 IST), NRestarts=0, up 8h26m at read.
- S1 checkout `/opt/friday_universe/Inference/app/providers/gateway.py`
  sha256 `2d5ef49d4881125b7b674a123d01f497e9ed08736760398074498f7fe95133cd`
  == main `49cfd862` EXACTLY (CD-synced copy; not the serving code).
- Serving code on FRIDAY-Server: gateway.py sha256
  `e884457c8a7dadf52e71b646a08fa02bb715cf32d98e5e50ef46ac7950e5c0ac`,
  mtime 2026-11-24 04:31:59 UTC. Contains INF-022 receipts (5 matches) AND
  INF-030 APInex (waterfall line 1327); NO needle fast-path (no matches) —
  serving code is the Nov 24 checkout: INF-030 in, INF-038 out, one day
  stale vs main. A deploy of current main to FRIDAY-Server is a coordinator
  decision (server move — stop order stands); reported, not attempted.

### Receipts (direct read, FRIDAY-Server, 15:09:53 UTC / ~20:39 IST)

First read via S1 tunnel (~20:2x IST): total 0 — ring empty. Direct read
minutes later: **total 4, success 4, error 0, fallback_used 2,
fallback_direct 0.** Traffic began 15:06:43–15:06:58 UTC (~20:36 IST);
all four receipts are capability `reasoning`, stage `unified_direct`
(not from this worker — my probes were read-only /status curls).

| # | observed (UTC) | requested | tokens | class | served | latency | fallback |
|---|----------------|-----------|--------|-------|--------|---------|----------|
| 1 | 15:06:43 | gemini / gemini-3.5-flash-lite | 233 | short | gemini | 5,517.7 ms | no |
| 2 | 15:06:49 | groq / openai/gpt-oss-120b | 6,205 | short | groq | 1,056.7 ms | no |
| 3 | 15:06:50 | groq / openai/gpt-oss-120b | 13,907 | large | openrouter / nvidia/nemotron-3.5-super-vl:free | 8,080.1 ms | yes, direct=false |
| 4 | 15:06:58 | gemini / gemini-3.8-flash | 13,907 | large | openrouter / nvidia/nemotron-3.5-super-vl:free | 42,513.8 ms | yes, direct=false |

Per-class so far (n=4, NOT a week — first harvest only):
- short (n=2): fallback rate 0/2, both served by primary, max latency 5.5 s.
- large (n=2): fallback rate 2/2, both served by openrouter after a primary
  attempt (fallback_direct=false — receipt #4's timeout_budget_s 51.9, not
  the 60.0 default, indicates a caller-set timeout, which opts out of the
  direct skip per the passing test in §1). Receipt #4's 42.5 s latency is
  the INF-019 failure mode in the wild: Gemini slow on a large prompt,
  fallback served it.
- error rate 0/4; deadline compliance cannot be judged on n=4.

### What the one-week audit still needs

- The ring holds the last 100 only, in-memory, and resets on restart
  (service up 8h26m; a restart wipes the week). A single end-of-week read
  cannot recover a week. Harvest design owed next: repeated /status reads
  (hourly snapshots into the evidence doc) + a note of every service
  restart, so the week's receipts are captured before they age out.
  Traffic has now started flowing (first receipts 20:36 IST) — the
  harvest window is open.
- Serving code is one day stale (INF-038 missing); the audit must state
  which code served each receipt batch. If FRIDAY-Server is re-deployed
  to current main mid-week, the batch boundary must be recorded.

## Five states (honest)

- Implemented: no (audit in progress). Tested: partial — repo leg 7/8
  (1 stale test, finding filed). Merged: no. Deployed: no (no deploy by
  this task). Production-verified: no — first live receipts harvested,
  one-week audit still open.

— Muse 5
