# TASK-IG-FRD-001-FIX-01 — FRIDAY: fix goal-loop engine step-allowlist + chat-turn timeout

Follow-up to FRD-051 leg 1 (IG-FRD-001 NOT VERIFIED, 2026-11-27 ~03:55 IST):
goal loop goal-90e54d3f66 ran 2/3 cycles, terminal BLOCKED; all 6 steps failed —
the engine's own step instructions were rejected by its own command allowlist
("Command 'work'/'for' is not allowed"); note file never created; chat turn hung
the full 300s though the loop finished in <1s.

Task: TASK-IG-FRD-001-FIX-01, P1, owner muse_17. Claimed 2026-11-27 ~11:08 IST
(hub #2045 comment 7210815349). Branch muse17/ig-frd-001-fix-01 @ c1aa53b9.
Board flip (AVAILABLE -> IN_PROGRESS) is coordinator-only (WATCH182 §2b);
board on live main e4018092 still shows AVAILABLE/muse_17, branch null, pr null.

## Checkpoint 1 — scoping DONE (2026-11-27 ~12:09 IST, live on FRIDAY-Server)

Bridge healthy first-hand: initialize 200 + session, get_system_info 200,
run_shell exit 0 (6 calls). M16's broken-transport report NOT reproduced
from here. FRIDAY.service active/running, NRestarts=1.

### Defect 1 — step-allowlist (ROOT CAUSE FOUND, in code)

- Planner: `FRIDAY/src/friday/autonomous/goal_loop.py::default_plan` emits
  natural-language steps, e.g. s1 "Work on this goal and report concrete
  progress: {goal}", s2+ "For the goal '{goal}', produce evidence for this
  success criterion: ...".
- Executor: `goal_loop.py::_default_executor` passes the step instruction
  VERBATIM to `friday.tools.execute_command.execute_command`.
- Allowlist: `FRIDAY/src/friday/tools/execute_command.py::ALLOWED_COMMANDS`
  = {chcp, dir, driverquery, echo, findstr, getmac, hostname, ipconfig,
  netstat, ping, systeminfo, tasklist, tree, type, ver, vol, where, whoami,
  python} — a Windows-flavoured shell-command set. First word "Work"/"For"
  is not in it, so every step fails with "Command 'work'/'for' is not
  allowed". This reproduces the FRD-051 leg-1 failure exactly.
- Design mismatch (docstring vs code): `_default_executor` claims to be
  "the same brain entry the mission queue uses", but it calls the shell
  runner, not the brain. The mission queue executes through the real chat
  brain via `_run_brain_sync` (server.py). The planner writes brain
  instructions; the executor runs shell commands. One of the two is wrong.
- Fix direction: route step instructions through the real brain entry
  (same as the mission queue), OR make the planner emit shell commands
  the allowlist accepts. Brain route matches the docstring and the
  planner's intent; implementation next (checkpoint 2).

### Defect 2 — chat-turn timeout (LOCATION FOUND, exact waiter TBD)

- `_chat_timeout_seconds()` (`FRIDAY/src/friday/api/server.py:3097`) = 300s
  default (FRIDAY_CHAT_TIMEOUT_SECONDS, TASK-REL-023; covers the 210s Forge
  dispatch budget + overhead). `_run_brain_sync` waits
  `future.result(timeout=300)` (server.py:497).
- In FRD-051 leg 1 the loop finished in <1s (all steps failed fast) yet the
  HTTP turn hung the full 300s: the turn holds the whole budget even when
  the tool result is already terminal. The post-tool dispatch/response path
  is the suspect waiter — trace it in implementation.
- Fix direction: return as soon as the tool result is terminal instead of
  holding the full budget; split tool budget vs response budget, or
  short-circuit the post-tool dispatch when the tool already produced a
  terminal report.

### Next

- Checkpoint 2: DONE — see below. IG-FRD-001 VERIFIED live (probe 3).
- Queue: STR-089 pos 3, VYR-093 pos 4 (WATCH205 §6). Filing route for this
  record: RULED CLOSED as used (WATCH209 §6, hub #2045 comment 7212015170)
  — no longer carried.

## Checkpoint 2 — IMPLEMENTED + LIVE-VERIFIED (2026-11-27 ~14:15 IST)

Root causes, traced first-hand in live server code (FRIDAY-Server checkout
main 06ff9ee6):

- Defect 1 CONFIRMED as a name collision, not an allowlist gap:
  `goal_loop._default_executor` called `friday.tools.execute_command`
  (read-only shell tool, Windows-flavoured allowlist) while the module
  docstring + the mission queue both mean the CHAT brain. The mission
  queue's brain is the chat dispatch (`_run_brain_sync`, server.py:485,
  scheduling the `/api/command` endpoint onto the main loop); the shell
  tool is a different thing with the same name. The planner writes brain
  instructions; the executor ran them through the shell.
- Defect 2 waiter FOUND: the turn's only bound is the outer
  `asyncio.wait_for(..., 300)` in `/api/command` (server.py:3142-3145);
  inside, `agent.process_message` runs the LLM tool loop with NO bound on
  the post-tool `llm.generate` (agent.py:688 loop + :950 final). Provider
  chain is Gemini (60s timeout, max_retries 3) with Groq failover, no
  overall bound — one post-tool generate can consume the whole 300s.
  FRD-051 leg 1: loop finished <1s, turn hung 300s on the post-tool LLM
  call.

Fix (branch commits 2f8636f7–c1351c81; work PR to follow):

- Fix 1 (`FRIDAY/src/friday/autonomous/goal_loop.py`): `_default_executor`
  routes steps through `_run_brain_sync` (lazy import), mapping the brain
  result dict → (ok, output) with mission-queue semantics (refused /
  security_blocked → fail; timeout → fail). Success is read from BOTH
  the top level and the metadata: the endpoint reports it only inside
  `metadata`, so the mission queue's top-level-only check would score a
  timeout as a success. Docstring corrected.
- Fix 2a (`FRIDAY/src/friday/tools/builtin/goal_loop_tools.py`):
  `StartGoalLoopTool.timeout = 240` (declared timeout honoured per
  TASK-IG-FRD-006-FIX-01; a multi-step brain loop cannot fit the 30s
  default; 240s stays inside the 300s chat budget). Terminal loops set
  `metadata["terminal_reply"] = True`.
- Fix 2b (`FRIDAY/src/friday/agent/agent.py`): `_terminal_reply()` helper
  + early return in the tool loop — a single-call batch whose result is
  a terminal reply returns its content as the turn's answer with no
  further LLM round-trip.
- Hardening (found live in probe 2): the endpoint returns a
  `JSONResponse` (not a dict) on error paths (refusal 403, exception 500,
  failed turn 502); the first executor version called `.get()` on it and
  crashed `start_goal_loop` mid-cycle. The executor now coerces
  `JSONResponse.body` back to the dispatch dict and never raises; and
  `run_cycle` now fails the STEP (not the run) if an executor ever
  raises.
- Tests (`FRIDAY/tests/test_ig_frd_001_goal_loop.py`, +10): brain routing,
  refusal honesty, timeout-is-failure (incl. empty-reply code path),
  unavailable-brain failure, JSONResponse body coercion, unreadable
  result failure, raising-executor step failure, leg-1 repro through the
  tool (COMPLETED + terminal_reply), tool timeout 240, `_terminal_reply`
  helper. 21/21 PASS on FRIDAY-Server (venv pytest, 2.93s).

Live legs (FRIDAY-Server, branch files overlaid on main 06ff9ee6,
service restarted between legs; server restored to main after):

- Probe 1 (~13:20 IST): loop goal-1ca0841b03, judge-type criteria (LLM
  passed plain strings). Steps all DONE via the brain; note
  `/tmp/m17-frd051-goal-note.txt` created with exact `FRIDAY-10000-OK`.
  Loop ended FAILED after 3 cycles — judge criteria unmet ("no judge
  wired"). Outer turn hit the 300s budget (tool finished 194.19s, 1s
  after the budget fired). Engine defect fixed; latency provider-bound.
- Probe 2 (~13:35 IST): loop goal-a76257da4b, contains criteria. s1
  done (note2 created), s2's nested turn hit Gemini 400
  INVALID_ARGUMENT (function-response sequencing) → endpoint 502
  JSONResponse → executor AttributeError crashed the tool at 76s
  (Success: False). Outer turn returned in 165.88s with the file-saved
  reply (error recovery, not the loop report). Crash fixed same run
  (see Hardening above).
- Probe 3 (~14:10 IST): loop goal-405f765194, contains criteria.
  **COMPLETED cycle 1/3, 2/2 criteria MET.** All 3 steps done via the
  brain (s2 read the file back from disk and quoted the exact content).
  Note `/tmp/m17-frd051-goal-note3.txt` = `FRIDAY-10000-OK`. Turn
  returned in 207.90s dispatch (success true, task COMPLETED), reply is
  the terminal loop report verbatim (iterations 1 — no second LLM
  round-trip). Evidence: `/tmp/m17-fix01-probe3.json`,
  `FRIDAY/.data/goal_loops/loops.json` (goal-405f765194).

## Verdict

**IG-FRD-001 — VERIFIED live.** Both acceptance clauses hold: (1) the
goal-loop engine's own step instructions are no longer rejected by its
own command allowlist — they run through the chat brain and do real
work; (2) a chat turn that starts a goal loop returns within the client
timeout (207.9s < 300s) and the loop completes, creating the requested
note file.

Follow-ups found (not this task — for the coordinator to route):

- No production judge wiring: `start_goal_loop` never passes a judge,
  so `judge`-check criteria (the default for plain-string criteria) can
  never be met in production — probe 1's loop FAILED honestly on this.
  Candidate: wire the brain as the criterion judge, or default plain
  strings to a text check.
- Nested-turn latency under provider exhaustion dominates the turn
  budget (Gemini credential exhaustion → failover chains; nested turns
  30–356s). Probe 1 missed the 300s budget by 1s for this reason.
- Cosmetic: the `terminal_tool_reply` marker does not survive the
  CognitiveMixin metadata rebuild (absent from the response metadata);
  the early return itself is proven by iterations 1 + verbatim report.
- The LLM sometimes passes `criteria` as a string instead of an array;
  registry validation rejects it ("expected array, received str") and
  the agent retries — recovered live, no action needed.

Server state after the live legs: 4 fix files restored to main blobs
(63068612/9ba206ac/fdaedff2/2369d079), working tree clean for those
paths, FRIDAY.service restarted on main, /health 200, pid 98045.
Probe files left on the server: /tmp/m17-fix01-probe{1,2,3}.json,
/tmp/m17-frd051-goal-note{,2,3}.txt; loops goal-1ca0841b03 (failed),
goal-a76257da4b (active, orphaned cycle), goal-405f765194 (completed).

