# TASK-WF-001 — M1 acceptance gate: fresh multi-agent trace

- **Task:** Run a FRESH multi-agent trace: one natural-language task via FRIDAY, dispatched across at least three agents, tracked with unified task records, result reported back; record the full trace (MASTER_PLAN §4 M1).
- **Date:** 2026-11-22 ~11:43–12:00 IST. Worker: Muse 2.
- **Claim:** issue #35 comment 7074049586; claim PR #1310 merged 09:49 IST (merge 3b77e2c6).
- **Live fleet at trace time (Server 1):** FRIDAY.service active, MainPID 2076194, restarted 11:15:20 IST (observed, not by this trace; NRestarts 1), checkout `ef42312f` (22 commits behind main at probe time; the drift vs the probe base is docs-only per the ORCH-010 comparison, so the live service runs the probed routing/dispatch code). Listening on :10000.
- **Verdict: M1 acceptance NOT MET — trace filed with a root-caused dispatch defect (G1).** Two of three legs completed with real results; the IntelX research leg — the acceptance's owner-visible exit — failed on both the chat path and the bus path because FRIDAY's IntelX peer URLs still point at the pre-migration addresses. IntelX itself is healthy on Server 2. No workaround was applied: no config was changed, no service was restarted, no key value was read, printed, logged, or stored. The fix is filed as follow-up F1 for Muse's pool; the trace must be re-run after it.

## The task as sent

One briefing task, issued as natural language through FRIDAY's live chat surface (`POST http://127.0.0.1:10000/api/chat`, keyless origin-gated — the same surface ORCH-010 probed). A single compound message does **not** fan out (see O1), so the task ran as three turns of one briefing:

1. `Research the latest AI model releases and give me the highlights, and also tell me how my portfolio is doing.` (compound; 11:43:39 IST)
2. `how is my portfolio doing?` (portfolio leg on its own turn; 11:55:14 IST)
3. `summarize my briefing so far in two lines` (reasoning/synthesis leg; 11:55:21 IST)

Plus one direct bus probe of the same research step (`POST /api/v1/dispatch/send?agent=IntelX&action=research_live`, shortly after 11:56 IST) to test whether the unified-bus path reaches IntelX while the chat path fails. Each `/api/chat` turn persists one conversation-history entry (same as the ORCH-010 probes).

## Leg-by-leg evidence

| # | Leg (agent) | Request | Routing | Agent evidence | Result | Wall time |
|---|-------------|---------|---------|----------------|--------|-----------|
| 1 | Research (IntelX) | Turn 1, research clause | research-dispatch fast path (`fast_path: true, research_dispatch: true`); no router line (fast path answers the turn) | `IntelXResearchTool` → shared FleetClient, `TaskEnvelope(capability=intelx.research, action=research_live, target_agent=intelx)` | **FAILED** — reply: "IntelX could not complete that research: ConnectError: All connection attempts failed. That is the real outcome — no highlights were fabricated." `task_state: FAILED`, `probe_success: false`, sources `[]` | 16.5 s (dispatch 7.2 s) |
| 2 | Portfolio (Stratex) | Turn 2 | portfolio fast path (`fast_path: true, portfolio_query: true`); no router line | Stratex snapshot: balance **10,554.73**, **30 open positions**, unrealized P&L **+106.70**, ledger net **+211.84** over 73 closed trades (win rate 21%, profit factor 1.85); demo mode, D-015 fail-closed guard stated | **COMPLETED** — `task_state: COMPLETED`, `query_success: true`. Served from the Stratex watch snapshot (`source: stratex_watch_snapshot`, age 20.2 s), not a fresh live query — see honesty note | 6.2 s (dispatch 2.0 s, execution 686 ms) |
| 3 | Reasoning (Inference) | Turn 3 | Router: `Routed query 'summarize my briefing so far in two line' to 'DIRECT_REASONING' (Score: -16.5)` at 11:55:27; `routed_capability: DIRECT_REASONING` | Provider gemini, model **gemini-3.6-flash** (requested gemini-flash-latest — same G2 as INF-LLM-003), `intent_classify_seconds: 2.675`, 1 iteration, state machine NOT_STARTED → UNDERSTANDING → PLANNING → VERIFYING → COMPLETED | **COMPLETED** — reply: "Here is your briefing summary so far, Boss: • AI Research: IntelX was unable to fetch the latest AI model releases due to a connection error. • Stratex Portfolio (Demo): Balance sits at 10,554.73 with 30 open positions (+106.70 unrealized P&L) and +211.84 net realized P&L." Truthful summary, including the honest IntelX failure | 38.9 s |
| 4 | Research via bus (IntelX) | `POST /api/v1/dispatch/send?agent=IntelX&action=research_live`, payload `{"topic": "latest AI model releases"}` | UniverseDispatchBus (`/api/v1/dispatch/send`) | Receipt: `task_id: disp_aed0e6fb7e64`, agent IntelX | **FAILED** — `status: failed`, `error: "Connection refused - agent not running"`, latency 4,055 ms | 4.1 s |

## Unified task records (`GET /api/v1/dispatch/records/report`)

| When | total | by_status | by_agent |
|------|-------|-----------|----------|
| Before the trace (11:43:39 IST) | 0 | all 0 | {} |
| After turn 1 (11:43:58 IST) | 1 | failed 1 | `intelx: 1` |
| After turns 2–3 (11:56:01 IST) | 1 | failed 1 | `intelx: 1` |
| After the bus probe (shortly after 11:56 IST) | 2 | failed 2 | `intelx: 1`, `IntelX: 1` |

- Only the IntelX legs wrote unified records (via `record_specialist_dispatch` on the chat path and the bus lifecycle on the bus path). The completed Stratex and Inference legs wrote **no** record — the portfolio fast path serves a watch snapshot and the reasoning leg runs in-process, so the store never sees them. The 2026-11-10 trace showed 4 records because its dispatches went through the bus; the chat fast paths do not.
- The store splits one agent across two owner strings by case (`intelx` from the chat path, `IntelX` from the bus) — see O2.
- Bus engine counters agree: `total_dispatches: 1, failed: 1, success_rate_pct: 0.0` after the probe (0 before).

## Acceptance verdict

- **A1 — one fresh end-to-end trace across at least three agents, all steps completed: NOT MET.** Three agents were exercised (IntelX, Stratex, Inference) but only two steps completed; the IntelX research step failed on both paths. The trace is recorded in full below and in this document.
- **A2 — Futuris 501-class failure absent, or root-caused with file/line: MET (absent).** No Futuris dispatch occurs anywhere in this trace.
- **A3 — owner-visible exit demonstrated: "research X and give me the highlights" returns real IntelX findings: NOT MET.** The owner-visible reply honestly reported the connection failure; no highlights were returned, and none were fabricated.

## G1 — IntelX peer URLs stale after the 6/4 fleet migration (root-caused)

- **What broke:** FRIDAY on Server 1 cannot reach IntelX on either path. Chat path: `ConnectError: All connection attempts failed` (FleetClient). Bus path: `Connection refused - agent not running` (dispatch bus).
- **IntelX itself is healthy.** Server 2: `IntelX.service` active/running; `http://127.0.0.1:8005/health` on S2 returns `{"status": "ok", "service": "intelx", "mock_mode": false, ...}`. Server 1's `IntelX.service` is **masked by design** — the 6/4 migration moved IntelX S1 → S2 (TASK-REL-062, MERGED; "old units masked as sleepers"). This is not an IntelX outage; it is a stale-pointer defect in FRIDAY.
- **Chat path, file/line:** `FRIDAY/src/friday/ecosystem/fleet_client.py:116–126` — `CANONICAL_INTERNAL_MESH_URLS` maps the Server-2 agents to `http://10.0.0.121:8005` (intelx), `:8001` (inference), `:8002` (memora), `:8003` (stratex), `:8004` (futuris). Verified live from S1: `http://10.0.0.121:8005/health` → `000` (unreachable; the address resolves to `friday-amd-vnic…oraclevcn.com` but answers nothing), while `http://10.0.0.120:8005/health` → `200` and the public Caddy route `https://friday-universe.duckdns.org/intelx/health` → `200`. The migration flipped the Caddy routes to `10.0.0.120` (REL-062 evidence) but the FleetClient canonical map still says `.121`. `configured_url` (`fleet_client.py:238–253`) prefers an env URL when set, else the canonical map in production — either way the effective IntelX URL is dead: the `http://intelx:8000` default (config.py:755) does not resolve on S1 (`getent hosts intelx` empty; curl → `000`).
- **Bus path, file/line:** `FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py:207–212` (`_build_action_url`, default path `/agent/{agent}/{action}`) with agent configs that still point at localhost: `GET /api/v1/dispatch/agents/IntelX` returns `base_url: "http://127.0.0.1:8005"` — nothing listens on S1:8005 (probed `000`). Same staleness for Stratex (`http://127.0.0.1:8003`, which on S1 is the Stratex **dashboard**, not the engine) while Inference (`http://127.0.0.1:8001`) happens to be correct because Inference runs on S1.
- **Known since the migration, not new:** FRIDAY's own fleet monitor has flagged IntelX UNREACHABLE since 2026-11-21 00:03 UTC — `friday.log` 2026-11-21 05:33:48 and 2026-11-22 05:33:44, trigger `fleet_agent_unhealthy`, key `fleet_agent_unhealthy:intelx`, owner-notify sent (today 1/20, then 2/20), autonomous goal seeded each time. The monitor's evidence string is the same `ConnectError: All connection attempts failed`.
- **Fix (follow-up F1, not done here):** point FRIDAY's IntelX peer URL — and the dispatch-bus agent configs / the `.121` block of `CANONICAL_INTERNAL_MESH_URLS` — at the live Server-2 address (`10.0.0.120:8005`, or the public Caddy route), then restart FRIDAY. That is a live config change + restart: coordinator clearance required, not a worker-side fix. After it lands, **re-run this trace**; M1 acceptance needs a fresh all-completed run.
- **No duplicate board record created:** no open board task tracks the IntelX peer-URL fix (checked the live board 2026-11-22 ~12:00 IST; Muse 3's TASK-INT-017 is the fast-lane production proof, a different item). F1 is filed here for Muse's pool, per the ORCH-010 precedent (its F1/F2/F3 went to pool-7 items, not worker-created board records).

## Observations (not acceptance blockers)

- **O1 — a compound message does not fan out.** Turn 1's second clause ("and also tell me how my portfolio is doing") was declined in the device layer — `friday.log` 11:43:47: "Declining a compound directive in the device layer (second clause: 'and also tell me how my portfolio is doing.'); the agent loop will plan it" — but the research fast path then answered the turn and the portfolio clause never ran. A multi-agent briefing currently needs one turn per leg; the "one task" is the briefing, the turns are its steps.
- **O2 — unified records only cover specialist dispatches, and split by case.** Only legs that call `record_specialist_dispatch` (IntelX chat path) or go through `UniverseDispatchBus.dispatch_async` write records. The portfolio snapshot and the in-process reasoning leg write none, so a chat-only trace can complete legs the store never sees. The store also keys by owner-agent string as given: `intelx` (chat) vs `IntelX` (bus) count as two agents in `by_agent`.
- **O3 — the LLM intent mid-tier fired on the cognitive-path turn.** Turn 3 metadata shows `intent_classify_seconds: 2.675` (and a `DIRECT_REASONING` routing line at 11:55:27). ORCH-010's F3 found the tier never fires live (0.0 s on its router-reached probes P5/P6, zero tier lines in 157 real turns). This turn went through the cognitive orchestrator (state machine, 1 iteration) rather than a fast path — the tier fires there. Qualifies F3 rather than contradicting it: the inert readings were on fast-path/router turns. Also reproduced INF-LLM-003 G2: the turn served as `gemini-3.6-flash` though `gemini-flash-latest` was requested.
- **O4 — background conditions observed, not caused by this trace.** `friday.log` shows Memora cursor-read failures (`Memora cursor read failed (HTTPError)`, `Memora event consumption did not complete`) roughly every minute before, during, and after the trace, plus RAM 90% proactive notifications (11:38, and a 90.5% notice attached to turn 3's reply). Pre-existing; noted, not investigated here.

## What was NOT done, and honesty bounds

- No config file was edited, no service was restarted, no secret or key value was read (`.env` checked by name only; the FleetClient canonical map is code, quoted above). The two `POST /api/v1/dispatch/batch` attempts returned `HTTP 422` (the endpoint takes a bare JSON list body, not `{"tasks": [...]}`) and created no dispatch; the single `/dispatch/send` probe is the only bus dispatch in this trace.
- The portfolio leg returned a **watch snapshot 20.2 s old**, not a fresh Stratex query — real data, but not a live dispatch; the 2026-11-10 trace's 7.30 s live Stratex dispatch is not reproduced here.
- The reasoning leg is Inference's local gateway path, not a bus dispatch; it is counted as the Inference agent step by routing (`DIRECT_REASONING`) and by the provider/model metadata, not by a unified record.
- No Futuris, Forge, Sentinel, Memora, Cortex, or VyralX leg was attempted; their state is not covered by this trace.
- Live service left as found: FRIDAY.service still active (MainPID 2076194, unchanged across the trace); no restart was triggered by any probe.

## Comparison with the 2026-11-10 trace

| | 2026-11-10 | 2026-11-22 (this trace) |
|---|---|---|
| IntelX research | COMPLETED 2.98 s, real citations | FAILED (both paths), ConnectError / connection refused |
| Inference reasoning | COMPLETED 1.61 s | COMPLETED 38.9 s (DIRECT_REASONING, gemini-3.6-flash) |
| Stratex portfolio | COMPLETED 7.30 s, balance 10792.8, 7 strategies | COMPLETED 6.2 s, balance 10,554.73, 30 positions (watch snapshot) |
| Futuris | FAILED truthfully (HTTP 501) | Not dispatched — absent |
| Unified records | 4 records, 3 completed / 1 failed | 2 records, 0 completed / 2 failed (both IntelX) |
| Owner browser closure | Never happened | Not attempted (out of scope for this trace) |

## Follow-ups filed

### F1 — IntelX peer URLs stale after the 6/4 migration (blocks M1)
- **Files/lines:** `FRIDAY/src/friday/ecosystem/fleet_client.py:116–126` (canonical map, `.121` block) and `:238–253` (`configured_url` precedence); `FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py:207–212` + live bus configs (`IntelX → http://127.0.0.1:8005`, `Stratex → http://127.0.0.1:8003`).
- **Proven:** this trace, legs 1 and 4, plus live reachability probes (`.121:8005` → 000, `.120:8005` → 200, `intelx:8000` → 000, S2 IntelX `/health` → ok).
- **Fix (separate task, coordinator clearance):** point FRIDAY's IntelX peer URL and the bus agent configs at the live Server-2 address, restart FRIDAY, re-run this trace. The `.121` block of the canonical map disagrees with the post-migration layout for all five agents — check the other four (inference, memora, stratex, futuris) while fixing intelx.

— Muse 2
