# TASK-INF-043 — checkpoint 3 (batch 2 + final confirm/reset filing) — Muse TP10

Claim: hub #1483 comment 7194179426 (2026-11-26 19:31 IST). Branch
`musetp10/task-inf-043` from main `28cc4ecb`; checkpoint 1 `caa1b2d8`,
checkpoint 2 `e84fdfd5` (hub 7195705037). Batch 2 run under WATCH187 §3
(hub 7204890360, "retry the live leg now"); START posted hub 7205114475
(2026-11-27 ~04:30 IST). All probes via Friday Bridge `run_shell`
server 3 (FRIDAY-Server), FRIDAY venv, live checkout. Read-only HTTP
probes only: no restart, no deploy, no env flip, no server move, no
live money. Live client timeout still **150.0 s** (`_inference_timeout_s()`
= 150.0 in-process this run; INF-032's 70 s wiring merged on main, not
deployed — separate coordinator-cleared item, not attempted here).

Acceptance (board record TASK-INF-043):
1. Measure Gemini completion time on ~9k-token prompts through the live
   routing path.
2. Confirm or reset the routing deadline from that evidence; file the
   numbers.

## Batch 2 results (fresh, cache-busted; oversized = 35,790 chars,
## ~8,947 est. tokens, gateway tokenizer ~12,9xx)

### Attempt 1 — 2026-11-26 21:57–21:59 UTC (03:27–03:29 IST), found on server

Result files `/tmp/inf043b2_*.json` on server 3, produced by the 03:23 IST
run whose filing was stopped by a safety classifier (hub 7204230121);
recovered and filed here with provenance. Not re-run by this batch.

| Probe | Path | Result | Wall | Notes |
|---|---|---|---|---|
| A2 oversized | client → `/v1/chat/completions` | HTTP 503 `provider_degraded` | **52.15 s** | Inside 60 s budget. |
| A oversized | direct `/v1/providers/execute` (auto, no_cache) | HTTP 200 | **37.42 s** | Gateway latency 37,413 ms; real answer, 482 chars. |
| B control (241 chars) | direct `/v1/providers/execute` (auto, no_cache) | HTTP 200 | **21.81 s** | Real answer, 162 chars. Slow vs INF-033's 1.27 s control — ladder conditions differ tonight. |

### Attempt 2 — 2026-11-26 22:59–23:03 UTC (04:29–04:33 IST), this run

Probe script `/tmp/inf043_probe2.py` (+ `inf043_probe2g.py` for G) on
server 3, backgrounded with result-file polling; raw JSONs
`/tmp/inf043b2_*.json`, summary `/tmp/inf043b2_summary.json`.

| Probe | Path | Result | Wall | Served by | Notes |
|---|---|---|---|---|---|
| E1 oversized | client → `/v1/chat/completions` | HTTP 503 `provider_degraded` | **38.95 s** | — | "could only be served by a model outside the verified catalogue". Inside budget. |
| E2 oversized | client → `/v1/chat/completions` | HTTP 503 `provider_degraded` | **47.18 s** | — | Same typed rejection. Inside budget. |
| F oversized | direct `/v1/providers/execute` (auto, no_cache) | HTTP 200 | **13.25 s** | openrouter / nvidia/nemotron-3.5-super-vl:free | Gateway latency 13,243 ms; real answer, 570 chars; degraded false. |
| G oversized | direct `/v1/providers/execute` (**provider=gemini**, no_cache) | HTTP 200 | **13.04 s** | openrouter / nvidia/nemotron-3.5-super-vl:free | **Gemini never attempted**: gateway large-deadline-class policy skips the Gemini primary >7,000 tokens ("the Gemini primary misses the 15 s slice on this shape (INF-LLM-003 + TASK-INF-029: 4/4 gateway trials cut at the slice, 14.7–15.0 s), so routing directly to the fallback ladder"). Real answer, 517 chars. |

## Gateway journal (Inference.service, attempt-2 window, UTC)

- `22:59:06` — size guard: prompt ~12,987 tokens > 7000; Groq primary
  skipped, routing to fallback ladder.
- `22:59:34` — `Provider 'gemini' timed out after 15.0s (model=gemini-3.8-flash)`;
  capability fallback for 'reasoning' → typed 503 at 22:59:45.
- `23:00:19–23:00:22` — gemini-3.8-flash 503 high demand; key quarantined
  60 s; retry timed out after 1.3 s (remaining slice) → ladder → 503 at
  23:00:32.
- `23:03:07` — `Large prompt (~12948 tokens) for Gemini; skipping the
  primary attempt and routing directly to the fallback ladder (TASK-INF-022)`
  → execute G served 200 at 23:03:20.

## Leg 1 — Gemini ~9k completion time: structurally unobtainable live

Across INF-033, batch 1, and batch 2 (both attempts), the chat path
served **0 of 5** oversized attempts (51.96 s, 50.69 s, 52.15 s, 38.95 s,
47.18 s — all typed 503 `provider_degraded`). The Gemini primary is cut
at exactly the 15.0 s slice on this shape every time it is attempted
(chat path), and on the execute path it is **not attempted at all**
above 7,000 tokens (large-deadline-class bypass, TASK-INF-022; INF-LLM-003
+ INF-029 record 4/4 trials cut at the slice). INF-031's 20.12 s served
baseline @ 9k tokens therefore has **no fresh served Gemini counterpart
and cannot be reproduced through the current live routing policy** — the
measurement result for leg 1 is that finding, with the numbers above.
The execute endpoint serves the same ~9k shape via the fallback ladder:
10.52 s (INF-033), 37.42 s (batch 2 attempt 1), 13.25 s / 13.04 s
(attempt 2) — all inside the 60 s budget.

## Leg 2 — deadline verdict: CONFIRM (keep) 60 s; no reset

Every return across all batches landed **inside** the 60 s routing
budget (worst observed 52.15 s, a typed 503). No probe breached or was
cut by the deadline; failures are model-availability / catalogue-policy
outcomes (Gemini 15 s slice, catalogue restriction, Gemini 503 high
demand), not deadline breaches. Under-7000-token prompts serve fast
(batch 1: 5.65 s control, 1.12 s mid). **The 60 s deadline stands as
set by INF-031 and wired by INF-032; no reset is warranted on this
evidence.** The binding constraints at ~9k tokens are the 15 s primary
slice and the >7,000-token Gemini bypass — policy items for the
coordinator, not deadline items. INF-032's live deploy (client timeout
150 s → 70 s) remains a separate coordinator-cleared item; the 150 s
client timeout was never binding in any probe.

## Five states

implemented NO (no code change; verdict is KEEP, so no reset to
implement) / tested YES (batch 1 + batch 2 live probes executed and
filed; acceptance legs 1–2 answered above) / merged NO (this filing
rides in the one work PR; peer full-diff review + fully green CI owed) /
deployed NO (nothing to deploy) / production-verified NO (paired
verification by a different chat owed before complete; never merge own
PR).

## Next

Peer review + CI on the work PR, coordinator merge decision, paired
verification. DB-011 live leg + paired verification remain held pending
coordinator ruling (asked in hub 7195705037) — unchanged by this filing.

— Muse TP10
