# TASK-IG-FRD-006-FIX-01 — Fix intelx_research 30s timeout so IG-FRD-006 delivers a Sources: section live

- **Worker:** Muse 1
- **Task:** TASK-IG-FRD-006-FIX-01 (P1)
- **Claim:** hub #1483 comment 7172477590, 2026-11-26 ~01:04 IST, on coordinator assignment in watch108 (7169671316)
- **Branch:** `muse1/task-ig-frd-006-fix-01-intelx-timeout`
- **Base:** main `70ce108` (board verified AVAILABLE / owner muse_1 / branch null / pr null / P1 first-hand)
- **Board:** flip AVAILABLE → IN_REVIEW rides in the work PR
- **Queue:** IG-FRD-006-FIX-01 → EARN-028 (queue pos 3, AVAILABLE / owner muse_1 on main 70ce108)

## Verdict: fix implemented + unit-tested; live re-probe BLOCKED on Muse rulings

| Acceptance leg | State |
|---|---|
| (a) Find why `intelx_research` exceeds its 30s limit on FRIDAY-Server | DONE — two causes found, both verified first-hand (below) |
| (b) Longer timeout or fallback research path | DONE (code) — per-tool timeout now honored; no fallback added, reason below |
| (c) Re-probe with a current-events question until a `Sources:` section is delivered | BLOCKED — IntelX down on S2 + no route from friday-server; needs Muse rulings |

Five states: implemented YES (code + tests) / tested YES (unit, local run below; CI wiring added) /
merged NO / deployed NO / production-verified NO. IG-FRD-006 stays NOT VERIFIED.

## (a) Root cause — two independent breaks, both verified first-hand

### Break 1 (code): the agent's 30s default shadows the tool's declared 125s

`FRIDAY/src/friday/tools/builtin/intelx_research.py:82` declares `timeout = 125.0`.
The chat path never honors it:

- `FRIDAY/src/friday/agent/agent.py:233` — `tool_timeout: float = 30.0` (constructor default).
- `FRIDAY/src/friday/agent/mixins/tools.py:605` (pre-fix) —
  `effective_timeout = timeout if timeout is not None else self.tool_timeout`,
  passed explicitly as `timeout=effective_timeout` to the registry. The chat
  turn calls `_execute_single_tool_call(call)` with no timeout, so the
  registry always receives 30.0.
- `FRIDAY/src/friday/tools/registry.py:275` —
  `raw_timeout = kwargs.get("timeout") or getattr(tool, "timeout", 30.0)`.
  The explicit kwarg wins, so the tool's 125.0 is dead code in the chat path.
- `FRIDAY/src/friday/agent/agent.py:883` (pre-fix) — the parallel SAFE-batch
  fan-out waits `future.result(timeout=self.tool_timeout + 1)` = 31s, a second
  cap that would kill a long tool even if the registry allowed it.

The deployed FRIDAY-Server tree (`/opt/friday_universe/FRIDAY`, git HEAD
`5b245ffd`) carries the same code at the same lines — the bug is live there,
not just on main. The tool's `timeout = 125.0` has been in the file since
before the last change (2026-11-14, REL-007D); the shadowing predates it.

Journal proof, re-read first-hand on friday-server (FRIDAY.service journal,
2026-11-25 11:41:25–11:41:55 UTC — TP7's attempt 1):

- `Requesting authorization for tool 'intelx_research' [Safety: SAFE]` →
  APPROVED (automatic for SAFE tools); executing with query
  'India vs South Africa cricket Test series latest news'.
- `ERROR [friday.tools.registry]: Tool 'intelx_research' execution exceeded timeout of 30.0s.`
- `Tool 'intelx_research' execution completed in 30.0024s (Success: False)`.

### Break 2 (fleet): the dispatch can never reach IntelX from friday-server

- friday-server is `172.26.12.144` (hostname `friday-server`). TCP connect
  from it to `10.0.0.120:8005` **times out** (blackhole, not refused) — and to
  `10.0.0.120:443` too. There is no route from friday-server to the
  `10.0.0.0/24` Oracle VCN at all. FRIDAY's `intelx_url` is unset in the
  service drop-ins and in `/opt/friday_universe/FRIDAY/.env`, so the dispatch
  uses the code default `http://10.0.0.120:8005`
  (`FRIDAY/src/friday/ecosystem/fleet_client.py:242`).
- The dispatch itself would hang: `fleet_client.py` posts the envelope with
  `timeout=115.0 if envelope.action == "research_live" else 15.0`, and as a
  float httpx applies 115s to every component including connect. The
  registry's 30s timer fires first — which is why the journal shows a tool
  timeout rather than a connect error.
- Separately, **IntelX is not running on Server 2 at all**: no listener on
  8005, no `intelx` process, unit `IntelX.service` exists but is disabled and
  inactive. It was stopped cleanly (`Deactivated successfully`) on
  2026-11-24 19:09:21 UTC (2026-11-25 00:39:21 IST) — before TP7's probe.
  `Futuris.service` stopped the same minute (19:09:23 UTC); `Cortex.service`
  stopped 19:43:41 UTC. Server 2 uptime is 34 days (no reboot); the stops
  were deliberate, not crashes. No agent service runs on S2 now except
  `friday-bridge.service`; S2 disk is 91% (4.5G free).
- Even with a route, the dispatch would fail fast (connection refused) until
  IntelX is restarted — the route break and the service break are independent.

Related fleet drift found while verifying (flagged for Muse, not this task):
Cortex.service is RUNNING on Server 1 (10.0.0.121, port 8009) although the
6/4 layout records Cortex on Server 2. S1 otherwise matches the layout
(Inference 8001, Memora 8002, Forge 8006, Sentinel 8008 running; no FRIDAY
listener on 10000 — stopped by design; `IntelX.service` masked on S1).

## (b) Fix — honor per-tool timeouts (this PR)

Precedence, implemented in a new `FridayAgent._effective_tool_timeout`
(`FRIDAY/src/friday/agent/mixins/tools.py`):

1. an explicit per-call timeout, when given;
2. the tool's declared `timeout`, when it differs from `BaseTool`'s class
   default (30) — a value equal to the default carries no override;
3. the agent default `self.tool_timeout` otherwise.

Changes:

- `FRIDAY/src/friday/agent/mixins/tools.py` — new `_effective_tool_timeout`
  helper; `_execute_single_tool_call_internal` uses it instead of always
  passing the agent default; `_execute_single_tool_call_with_timeout`
  default is now `None` (was a hardcoded `30.0`), so callers that pass
  nothing also honor the declared timeout. The only in-repo caller of the
  latter passes an explicit value (`tests/test_reliability.py:143`), so its
  behavior is unchanged.
- `FRIDAY/src/friday/agent/agent.py` — the parallel SAFE-batch fan-out now
  waits `max(effective timeout over the batch) + 1` instead of the flat
  `tool_timeout + 1` (31s).
- No change to the registry (it already honors `tool.timeout` when no
  explicit kwarg is given) and no change to the FleetClient dispatch timeout
  (115s for `research_live` stays the binding cap below the tool's 125s, so a
  slow-but-live IntelX returns or fails with its own error instead of being
  killed by the tool timer).

Fallback considered and NOT added: there is no second research provider in
the fleet, and a fallback that answers news without IntelX citations would
break the `Sources:` contract this task exists to satisfy (URLs must match
the tool results). The timeout fix plus a restored IntelX path is the
proportionate answer; if IntelX research turns out to exceed even 115s once
measured live, the next step is the IntelX-side latency work, not a
second provider.

## Tests

New regression tests in `FRIDAY/tests/test_reliability.py` (next to the
existing `test_tool_timeout_enforcement`):

- `test_tool_declared_timeout_honored` — a tool declaring 5s completes a 1s
  run with the agent default at 0.1s (fails before the fix: killed at 0.1s).
- `test_tool_explicit_timeout_still_wins` — an explicit 0.1s call timeout
  still kills the same tool (precedence leg 1).
- `test_tool_agent_default_caps_undeclared_tool` — a tool with no declared
  timeout is still capped by the agent default (precedence leg 3; pins the
  fix against turning the agent default into a no-op).

CI wiring (FUT-030 lesson — a test that runs nowhere is not a test):
`FRIDAY/tests/test_reliability.py` is collected by NO PR-triggered workflow
on main 70ce108, so the REL-068 diff-scoped collection guard would fail this
PR. This PR adds the file to the "Run FRIDAY tier-1 tests" step in
`.github/workflows/friday-universe-ci.yml` (the established pattern — same
reason STR-082/078/083/086 files were added there), with `--deselect` for
the three pre-existing failures below.

Local test run (this VM, venv from `FRIDAY/requirements.txt` + pytest,
2026-11-26 ~01:50 IST): the exact CI-wired invocation —
`pytest -q tests/test_reliability.py` with the three deselects —
**6 passed, 3 deselected in 4.63s**. The three new tests pass
(`test_tool_declared_timeout_honored`, `test_tool_explicit_timeout_still_wins`,
`test_tool_agent_default_caps_undeclared_tool`); the pre-existing
`test_tool_timeout_enforcement` also passes. `ruff check` on the two changed
source files: all checks passed. (First venv attempt failed with "No space
left on device" — `/tmp` is a 512M tmpfs; rebuilt the venv under the workspace
on the 7.5G overlay instead.)

Pre-existing failures (NOT this PR — proven on unmodified main 70ce108 via
`git stash` + rerun in the same venv, identical errors):
`test_retry_on_network_failure`, `test_retry_on_rate_limit`,
`test_no_retry_on_auth_error` all fail with
`httpx.InvalidURL: Invalid port: ':1]'` inside the mocked `httpx.Client.post`
path — a newer-httpx mock incompatibility, untouched by this change.

## Live leg — BLOCKED, rulings owed from Muse

The re-probe (acceptance leg (c)) cannot run until all three are cleared:

1. **IntelX restart on Server 2** — `IntelX.service` stopped 2026-11-24
   19:09:21 UTC and disabled; was the stop deliberate (owner stop order /
   INT-036 pause), and is a restart cleared? Futuris/Cortex stopped in the
   same window — same question for them if the re-probe needs them (it does
   not; IntelX only).
2. **Route friday-server → 10.0.0.120** — friday-server (172.26.12.144) has
   no route to the Oracle VCN; this is a network change (owner/Muse call).
3. **Deploy clearance for this fix** — CD is broken and the owner stop order
   is in force; the fix must reach friday-server's deployed tree
   (`/opt/friday_universe/FRIDAY`, HEAD `5b245ffd`) before the re-probe can
   pass. Live-fleet deployments need Muse's hub clearance.

Re-probe procedure once unblocked (same shape as TP7's FRD-052 legs, on
FRIDAY-Server via the bridge): loopback `POST http://127.0.0.1:10000/api/chat`
with a current-events question (e.g. the cricket series), backgrounded curl
(the bridge client times out at 45s; the turn may take up to ~125s), then
read the reply for a `Sources:` section and the friday-server journal for
the `intelx_research` completion line, and check every URL against the tool
results. Do NOT mark IG-FRD-006 verified until that lands.

## Queue and usage

- **Head:** TASK-IG-FRD-006-FIX-01 (this task; fix implemented, live leg blocked).
- **Next:** TASK-EARN-028 (queue pos 3, AVAILABLE / owner muse_1 on main 70ce108).
- **Usage:** 76% of free weekly limit (WATCH114 lag table; my last self-report 77%).
  Free usage remains; work-request stays disarmed while claimed.
- **Schedules:** hourly self-check + weekly reset armed; `muse1-work-request`
  absent — correct mid-task state.

## Notes for Muse (not this task)

- S2 agent outage: IntelX, Futuris, Cortex all stopped+disabled on Server 2
  since 2026-11-24 ~19:09–19:43 UTC; only the bridge runs there now.
- Cortex runs on Server 1, contradicting the recorded 6/4 layout — the
  layout record may be stale.
- S2 disk 91% (4.5G free) — still climbing; owner word owed (carried).
