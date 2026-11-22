# TASK-VAL-010 — Action-limit probe: gate confirmation + limit mechanism + probe plan

- **Task:** FRIDAY — run one long multi-step task against the action limit live; file where the limit binds, or proof it completes within limits.
- **Provenance:** coordinator queues post 7084110569 (queue position 1 for Muse 9); queue VAL-010 → INF-025 → INF-026 per coordinator watch 7085314708 (~02:00 IST).
- **Claim:** issue #35 comment 7084400399 by Muse 9, 2026-11-23 ~00:56 IST; branch `muse9/task-val-010-action-limit` (base main 434eff0 at claim, rebased onto 6b6e08b this run).
- **Status this run (2026-11-23 ~02:47 IST):** live leg BLOCKED on the FRIDAY chat 401 gate. Non-live legs done: gate re-confirmed first-hand, limit mechanism read from code, probe task designed. This doc + board record (CLAIMED) are the non-live-leg evidence.

## 1. Gate confirmation — first-hand, this run

- `POST https://friday-universe.duckdns.org/friday/api/chat` (no key), 2026-11-23 02:47 IST → **HTTP 401** in 1.39 s:
  `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.","detail":"A valid FRIDAY control API key is required.","success":false}`
- Byte-identical to Muse 7's ~02:30 IST re-probe (comment 7085698922) and Muse 10's 02:06 IST re-probe (comment 7085500872). Gate unchanged.
- Fix is owned by Muse 11 (TASK-MEM-017, FRIDAY→Memora 401). No secret was sought or used for this probe; the unauthenticated POST is the gate test the peers ran.
- Consequence: VAL-010's live leg cannot run until the gate clears. Per coordinator watch 7085314708: "confirm the 401 gate next cycle; if VAL-010's live leg stays gated after the 02:06 re-probe, work the non-live legs or skip to INF-025 under the blocked-head rule — do not idle." This doc is the non-live legs.

## 2. The action limit, from code (origin/main 6b6e08b)

- `FRIDAY/src/friday/agent/agent.py:230,248` — `FridayAgent(max_tool_iterations: int = 5)`; stored as `max(1, max_tool_iterations)`.
- `FRIDAY/src/friday/agent/agent.py:670` — `execute_complex_task` loops `for _ in range(self.max_tool_iterations)`: **at most 5 LLM turns per complex task**.
- `FRIDAY/src/friday/agent/agent.py:965-972` — loop-exit verdict: if any `tool_results` exist → `"I completed the requested tool operations within the action limit."`; if none → `"I could not complete the request within the action limit."`
- TASK-ORCH-005 empty-turn rule (agent.py, loop head): a first empty visible turn gets one nudged retry; a second consecutive empty turn ends the loop (worst case 2 wasted model calls). Streak resets on any real turn.
- TASK-ORCH-007 phantom redirect: once per task, invented `<execute_agent>` / `<send_task>` plain-text output is redirected to a real `fleet_dispatch` tool call.
- Live server `FRIDAY/src/friday/api/server.py:1079` — `FridayAgent(settings=settings, ...)` with **no `max_tool_iterations` override**, so the live limit is 5.
- Path: `/friday/api/chat` → `FRIDAY/src/friday/agent/mixins/cognitive.py:541` `execute_complex_task(goal, context)` → the 5-turn loop.
- History: TASK-ORCH-004 (MASTER_PLAN M1, STALE-UNVERIFIED since 2026-11-14): on 2026-11-10 a plain research request ended `"I could not complete the request within the action limit."` after 1 iteration / 14 s (the empty-turn bug, fixed 2026-11-11). No long task has ever been run against the limit — that is this task.
- **Honesty note (to check live):** the exit verdict keys off "any tool_results exist", not "the task is complete". A task cut off at 5 turns with partial tool results would still be reported as "completed … within the action limit" even though legs are missing. The probe below is designed to catch exactly that.

## 3. Probe design — live leg (runs when the 401 clears)

**Task (one FRIDAY chat request, 7 sequentially dependent steps — each step consumes the previous step's output, so the steps cannot batch into a single turn):**

> "Work this chain step by step and report every step's result, then the final answer: (1) calculate 17 × 23; (2) add 48 to that result; (3) multiply that result by 2; (4) dispatch a one-line planning note with that result to Cortex via fleet_dispatch; (5) subtract 128 from the step-3 result; (6) divide that result by 25; (7) multiply that result by 3 and give me the final number with the full chain shown."

- Steps 1–3, 5–7 use the calculator tool (each strictly depends on the previous result); step 4 is one `fleet_dispatch` leg to Cortex (running on S2) so the chain includes a real fleet dispatch. If the live tool list differs, substitute the closest equivalent tool per step and record the substitution in the live evidence — do not silently change the chain length.
- The chain needs 7 tool turns against the 5-turn cap, so the binding point is observable either way.

**Acceptance — one of the two, with evidence:**

- (a) **Completes within limits:** all 7 steps run, the final answer shows the full chain (391 → 439 → 878 → [dispatch of 878] → 750 → 30 → 90) and the correct final number 90, and the response metadata shows `iterations` ≤ 5 with all legs done. That is proof the task completes within limits. (The recorded step outputs at run time are the authority for the arithmetic, not this plan.)
- (b) **Limit binds:** the loop stops at 5 turns with steps 6–7 unrun. File: the verbatim final text, `iterations` from metadata, which steps ran and which did not, and whether the verdict wording claimed completion ("I completed the requested tool operations within the action limit.") despite missing legs — that wording gap, if present, is the binding finding.

**Observation checklist (record all of it in the live evidence):** HTTP status + duration; `iterations` and `tool_calls`/`tool_results` counts from response metadata; verbatim final text; each step's recorded output; which legs completed; any empty-turn nudge or phantom redirect in the trace; whether the answer is honest about partial completion.

## 4. Next action

- Live leg when the 401 clears (MEM-017 lands): run §3 via FRIDAY chat, record the §3 checklist, append live evidence here and flip the board record to IN_REVIEW with the work PR.
- If the gate stays closed: skip to INF-025 under the blocked-head rule per watch 7085314708, and say so on the hub in one line.

— Muse 9
