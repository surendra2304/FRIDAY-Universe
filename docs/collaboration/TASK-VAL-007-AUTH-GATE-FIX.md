# TASK-VAL-007 — Fix the D-023 auth gate on POST /friday/api/chat

- **Task:** TASK-VAL-007 (pool 10, P1), owner muse_4
- **Assignment:** Muse (coordinator) watch 2026-11-22 ~23:35 IST, issue #35 comment 7083334971, item 2
- **Claim:** issue #35 comment 7083407621, 2026-11-22 ~23:45 IST
- **Branch:** muse4/task-val-007-auth-gate-fix (base main c40a2d2d)
- **Source:** VAL-005 finding F2 (docs/collaboration/TASK-VAL-005-FLEET-CAPABILITY-REPROBE.md)

## 1. Finding (baseline re-probed live by this task)

2026-11-22 23:45 IST (18:15:33Z), unauthenticated `POST
https://friday-universe.duckdns.org/friday/api/chat`
(`{"message": "hello FRIDAY"}`, gateway `Origin`, no key, no cookie) returned
**HTTP 200** in 10.1 s with a live reply:

```json
{"reply": "Burning the midnight oil again, Surendra? What are we doing?",
 "metadata": {"fast_path": true, "conversational": true, ...}}
```

This is the VAL-005 finding F2, confirmed again on the current deploy: the
validator's `friend_persona_greeting` probe FAILs (it expects 401/403/503).

## 2. Root cause

`chat_endpoint` (`FRIDAY/src/friday/api/server.py:4884`) depended on
`_require_origin_gate` — origin-gated only, by the 2026-11-10 IST owner
decision ("Remove that authentication", D-025). The origin gate
(`_origin_allowed`) lets through any request carrying the service's own
origin, and lets through requests with no `Origin` at all ("not a browser ...
judged by the credential rules instead"). But `/api/chat` had **no credential
rule behind it** — so a direct remote client sending the gateway's own
`Origin` (or none) reached the handler. And the handler is not a
greeting-only surface: it calls `execute_command`, the full command
pipeline. An `Origin` header is client-controlled; D-023 itself says it is
not an authentication boundary — the same flaw it fixed for the
`/api/control/session` mint (TASK-SEC-005). The chat endpoint was the one
control surface left without a credential rule.

## 3. The D-025 tension, stated plainly

The owner directive behind the keyless chat (D-025, 2026-11-10 IST: "open
the site and just talk") still stands and was never superseded. This fix
restores the credential gate on the chat endpoint, which means **after
deploy, the keyless dashboard's chat answers 401** — the dashboard
(`FRIDAY/ui/lib/wire.ts`, `sendChat`) sends no key and no token today.
The owner's browser chat only keeps working after deploy if a credential
flow is restored in the dashboard (paste-once key -> auto-refreshing fcs1
session, the D-023 design). That dashboard work is NOT part of this task.

This is exactly why the assignment says "no deploy without the in-task
clearance step": the code fix is done and tested here, but deploying it
changes the owner's chat UX, so deploy waits for coordinator/owner
clearance. Nothing in this task deploys, restarts, or touches live config.

## 4. Fix

One dependency swap in `FRIDAY/src/friday/api/server.py` (`chat_endpoint`):

```python
# before
async def chat_endpoint(req: ChatRequest, _: None = Depends(_require_origin_gate)) ...
# after
async def chat_endpoint(req: ChatRequest, _: None = Depends(_require_control_access)) ...
```

`_require_control_access` runs the origin gate first (defence in depth,
unchanged), then demands the control API key (`x-friday-api-key` or
`Authorization: Bearer`, constant-time) or a valid fcs1 control token from
remote callers; loopback callers stay keyless (the owner on the box). The
endpoint docstring now records the F2 hole, the fix, and the deploy
consequence. No other endpoint touched: the remaining `_require_origin_gate`
routes (status/telemetry/memory reads) are out of scope for VAL-007.

## 5. Tests

New file `FRIDAY/tests/test_val007_chat_auth_gate.py` (13 tests), modelled
on `test_control_session_hardening.py` (SEC-005); registered in the CI
contracts list in `.github/workflows/owner-workflows.yml`.

Local pytest (vyr035-venv, pytest 9.2.0), repo at branch head:

- **New suite: 13/13 pass.** Remote unauthenticated chat (validator probe
  shape, gateway Origin, no credential) -> 401; no Origin -> 401; wrong
  key -> 401; refusal names the missing credential; owner key -> 200;
  Bearer -> 200; minted fcs1 token -> 200; foreign origin + key -> 403;
  null origin + key -> 403; loopback without key -> 200; no usable key
  configured -> 503; example key -> 503.
- **Attack replay (SEC-005 pattern): 6/13 fail against pre-fix
  `server.py`** (git stash of the one-line change only): all four
  remote-refusal cases + both fail-closed cases. The other 7 pass on both
  versions (accepted/loopback/origin behaviour is unchanged). Fix
  restored; suite back to 13/13.
- **Adjacent suites: 116/116 pass** — `test_control_session_hardening.py`,
  `test_api_origin_enforcement.py`, `test_api_command_truthfulness.py`,
  `test_batch3_part2.py`.
- **Chat suites: 84/85 pass** — `test_chat_chaos_battery.py`,
  `test_proactive_greeting_memory.py`, `test_empty_turn_resilience.py`,
  `test_four_owner_workflows.py`. The one failure,
  `test_secret_siphon_never_leaks_real_values` ("no credential values
  found to guard — battery misconfigured"), **fails identically on clean
  main** (verified via git stash): pre-existing sandbox gap, the battery
  finds no credential values to guard in this environment. Untouched by
  this diff.
- **Collection guard:** `scripts/ci_test_collection_audit.py` — no STALE
  reference once the new test file is tracked; the workflow list entry
  matches the file. (Local run with the file staged; CI on the PR branch
  is the authoritative check.)
- **py_compile** clean on both changed Python files.

## 6. States

- implemented: YES
- tested: YES locally (above); CI on the PR is the remaining verification
- merged: NO (PR open, awaiting Muse)
- deployed: NO — HELD, clearance required (see §3)
- production-verified: NO — the live acceptance (unauthenticated re-probe
  returns 401; fleet validator `friend_persona_greeting` passes on a fresh
  run) can only be measured after deploy, on a fresh validation run

## 7. Files

- `FRIDAY/src/friday/api/server.py` — `chat_endpoint` dependency
  `_require_origin_gate` -> `_require_control_access` + docstring
- `FRIDAY/tests/test_val007_chat_auth_gate.py` — 13 regression tests (new)
- `.github/workflows/owner-workflows.yml` — new test added to the CI
  contracts list
- `docs/collaboration/TASK-VAL-007-AUTH-GATE-FIX.md` — this evidence doc
- `docs/collaboration/WORK_BOARD.yaml` — TASK-VAL-007 record (IN_REVIEW)

## 8. What this task does not do

- No deploy, restart, or live-config change. No server touched.
- No dashboard change: the credential flow the dashboard will need after
  deploy is a separate decision (clearance step).
- No change to any other endpoint's gate, and no change to the validator
  probe itself.
