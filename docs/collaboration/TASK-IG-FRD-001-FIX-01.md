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

- Checkpoint 2: implement fix 1 (brain-route executor) + fix 2
  (terminal-result early return), unit-test against the FRD-051 leg-1
  repro (goal-90e54d3f66 steps), then live re-verify IG-FRD-001 on
  FRIDAY-Server (note file must be created; turn must return in seconds,
  not 300s).
- Queue: STR-089 pos 3, VYR-093 pos 4 (WATCH205 §6). Filing route for this
  record still unruling (carried, coordinator rules next run).
