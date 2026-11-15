# TASK-FRD-003 — FRIDAY chat latency profile and fix

Base: main `ef3ca99` (fresh clone, 2026-11-15). Crew: muse_ai (Wave 5, FRIDAY).
Claim: issue #35 comment 6891640114. Branch: `claude/task-frd-003-chat-latency`.

## 1. Live measurements (Server 1, 2026-11-15 ~13:56–14:05 IST)

Host state during probing: load average 5.19 / 4.73 / 3.43, 76 MB RAM free of
956 MB (Wave-5 load — numbers are honest for a loaded host, not best-case).

**Production journal — cognitive turns (`process_message` durations), 29 turns
in the 12 h window 03:45–13:58 IST:** min 5.39 s, **median 20.47 s**, max
46.47 s. A chat answer taking ~20 s at the median is the problem statement.

**Timed probe 1 — fast path** ("what time is it in tokyo right now",
server-local `POST /api/chat`, no network leg): **5.53 s end to end**, of
which `duration_seconds` inside `process_message` was **1.38 s**. ≈4.2 s is
spent *outside* the agent loop on a purely deterministic answer:
persist-first history write, dispatch, default-executor queueing on the
loaded loop, finalize write.

**Probes 2/3 (simple-factual lane, full cognitive loop)** were attempted
twice; the bridge dropped the shell calls mid-flight under Wave-5 load
(initialize failures). One cognitive turn completing at 13:58:31 IST in
35.69 s falls inside the first probe batch's window. Probe 2/3 end-to-end
numbers are therefore reported as NOT CAPTURED rather than estimated.

## 2. The serial map (code-evidenced, main ef3ca99)

`execute_command` (server.py):
1. `_begin_conversation_entry` — durable Oracle insert **awaited before any
   dispatch** (TASK-REL-007B/029 persist-first contract).
2. `_dispatch_command` (300 s overall budget).
3. Response formatting, activity emit.
4. `_finalize_conversation_entry` — Oracle upsert **awaited before the
   response returns**.

`_dispatch_command`: injection scan → ~15 deterministic gate groups (cheap,
regex) → memory recall gate (Memora HTTP, `recall_timeout` 15 s; a second
serial recall when the first is empty and the question is personal) →
device gates → general-knowledge lane (one no-tools LLM call, 25 s cap) →
`process_message` on the default executor.

`process_message` (cognitive.py): ~14 fast paths → **intent mid-tier LLM
call (≤2.5 s, weak-signal only)** → cognitive evaluate → capability route →
**local hybrid recall** → `execute_complex_task`. All serial.

`execute_complex_task` (agent.py), before the first LLM call:
**Memora `build_context_block` (recall; 15 s timeout) then Memora
`build_self_upgrade_context` (experience; 3.5 s timeout) — strictly
serial**, then the REL-022 recall guard, then the LLM tool loop.

Worst-case pre-LLM serial waiting: 15 + 3.5 + 2.5 = **21 s** before the
model is even asked, plus two awaited Oracle writes and (for recall-shaped
messages) the dispatch recall gate.

## 3. Fix landed

1. **Parallel Memora context legs** (agent.py): the two independent reads
   now run concurrently on a 2-thread pool. Block content and prompt
   ordering are byte-identical (context block first, self-upgrade second);
   each leg keeps its own fail-open behaviour (an exception in one leg
   yields "" for that leg only — previously a context-leg exception
   skipped *both* blocks via the shared try, so this is strictly more
   fail-open, disclosed here). Per-leg + wall timings are recorded.
2. **Instrumentation at all three layers** (pure measurement):
   - `execute_complex_task` metadata `latency`:
     `memora_context_wall_seconds`, `memora_context_leg_seconds`,
     `memora_self_upgrade_leg_seconds` (on all six return paths).
   - `process_message` metadata: `intent_classify_seconds`,
     `local_recall_seconds`, `latency` (forwarded).
   - `execute_command` metadata `latency_ms`: `persist_begin_ms`,
     `dispatch_ms`, `persist_finalize_ms`, `total_ms` — so the ~4.2 s
     outside-the-loop cost from probe 1 is attributable per stage in
     production from now on.

## 4. Before / after (local harness, identical fakes)

Simulated Memora legs of 0.4 s each + instant stub LLM, `Settings(env=
"testing")` (the REL-027 harness pattern):

- BEFORE: the two legs composed serially = **0.855 s** for the Memora
  stage alone.
- AFTER: full `execute_complex_task` wall = **0.479 s**, Memora stage wall
  **0.463 s** (legs 0.456 / 0.405 s, concurrent).

Saving ≈ the shorter leg's latency on **every** cognitive turn: ~0.39 s at
the harness scale, ~0.5–3.5 s at production leg latencies under load, and
the pre-LLM worst case drops from 18.5 s to 15 s for the Memora stage.
Production after-numbers will be readable directly from the new
`latency` / `latency_ms` metadata once deployed.

## 5. Tests

- New `FRIDAY/tests/test_frd003_chat_latency.py` (3 tests): parallel wall
  + content/order preservation + latency metadata; one-leg failure stays
  fail-open; `execute_command` attaches the four-key `latency_ms`
  breakdown. **3 passed.**
- Regression batch 1 (rel027 reply hygiene, intent-classifier tier,
  rel039 turn-context isolation, memora hardening, rel022 memory
  integrity): **60 passed.**
- Regression batch 2 (api command truthfulness, agent, rel025 race):
  **64 passed, 1 failed** — `test_agent.py::
  test_agent_multi_turn_context_retention` fails **identically on pristine
  HEAD** (verified by restoring the three touched files from HEAD and
  re-running): pre-existing, not caused by this change.

## 6. Residuals (measured, deliberately not changed here)

- Persist-begin/finalize Oracle writes remain serial — that is the
  REL-007B/029 durability contract (a turn must be durable before work
  starts). They are now measured per stage; making the begin-write
  concurrent with dispatch is a coordinator-level contract decision.
- Intent tier (≤2.5 s) still runs serially before local recall; the two
  could overlap — follow-up, now measurable via `intent_classify_seconds`
  vs `local_recall_seconds`.
- Executor/loop queueing under host load (probe 1's gap) is structural on
  a 956 MB host at load 5+; the free-ARM wait remains the structural fix.
