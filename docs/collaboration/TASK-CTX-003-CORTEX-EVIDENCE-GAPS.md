# TASK-CTX-003 — Cortex evidence gaps G1–G5: evidence

Task: close the CTX-002 evidence gaps G1–G5 with live-log evidence and
re-file the 48h fires-vs-messages ratio from a fresh window.

- Assignment: coordinator round, issue #35 comment 7084017188 (~00:40 IST).
- Claim: issue #35 comment 7084194994 (2026-11-23 00:55 IST). Branch
  `muse13/task-ctx-003-cortex-evidence-gaps`.
- Work PR: #1416 (https://github.com/surendra2304/FRIDAY-Universe/pull/1416,
  head `09418867`, base main `81acda98`). **MERGED 2026-11-23 02:05:23 IST
  by Surendra, merge commit `a8c6fea2`, CI 9/9 green** (coordinator
  follow-up, issue #35 comment 7085400525, ~02:06 IST).

## 0. Live state at filing (Server 2 via bridge, read-only, 2026-11-23 ~01:41–01:44 IST)

- Both Oracle servers ONLINE. Deployed checkout `/opt/friday_universe` is
  `muse10/task-frd-037-chat-live-runs` @ `db933cfc` — unchanged since the
  claim run.
- `Cortex.service` active since Nov 22 12:16:38 IST, Main PID **584499** —
  unchanged, still the process that started before the CTX-002 merge.
- Deployed `Cortex/apps/api/src/cortex_api/self_healing.py` on disk
  contains the CTX-002 HTTP probe (`GET {base}/health`, line 90,
  `PROBE_TIMEOUT_SECONDS = 5.0`, no `getaddrinfo` anywhere in the file).
- Production env unchanged: `INFERENCE_BASE_URL` 0, `AI_UNIVERSE_BASE_URL`
  0, `SELF_HEALING_ESCALATION_WEBHOOK` 1, `CORTEX_API_KEY` 1 (presence
  counts only; values never read or copied).

## 1. G1 — /health is liveness only → CLOSED BY CODE (not yet deployed)

Inference exposes a real readiness endpoint, verified live from Server 2
twice this task (claim run ~00:5x IST and this run 01:43 IST):

`GET http://10.0.0.121:8001/ready` → HTTP 200
`{"status":"ready","service":"inference","agent":"Inference",
"evidence_class":"service_readiness","ready":true,
"database_backend":"oracle","database":{"status":"connected",...},
"model_routing":{"status":"ready","initialized":true,"providers":["gemini",
"groq","cerebras","mistral","openrouter","cohere","huggingface","nvidia",
"bytez"]},"providers_initialized":true,"version":"2.0.0"}`

The probe now checks readiness instead of liveness:

- `Cortex/apps/api/src/cortex_api/self_healing.py::probe_ai_universe`
  performs `GET {base}/ready` (was `/health`) and reports HEALTHY only
  on HTTP 200 with `status` in `("healthy", "ready")`. A `"ready"`
  status is the /ready verdict; `"healthy"` stays accepted so a gateway
  that only speaks liveness is not newly failed. Any other status,
  non-200, or transport failure is UNHEALTHY; a 200 with no `status`
  field or a non-JSON body stays HEALTHY (liveness only). Base URL
  precedence, 5.0 s timeout, `trust_env=False`, and the tri-state
  contract are unchanged.
- `Cortex/.env.example` documents the `/ready` check (was `/health`).

Tests updated to pin the new contract (same mocking style as CTX-002):

- `Cortex/tests/unit/test_cor014_unconfigured_probe.py`: all asserted
  probe URLs `/health` → `/ready`; the fleet-default test now pins the
  real /ready answer (`{"status": "ready", "ready": true}`); new test
  `test_probe_healthy_when_ready_status_is_ready`; the parametrised
  end-to-end supervisor test gains a `{"status": "ready"}` healthy case;
  the `"healthy"` cases are kept, pinning backward compatibility.
  Renames only where the name referenced the endpoint
  (`_FakeHealthResponse` → `_FakeProbeResponse`,
  `..._health_endpoint_unreachable` → `..._ready_endpoint_unreachable`,
  `..._health_status_is_not_healthy` → `..._ready_status_is_not_ready`).
- `Cortex/tests/unit/test_e2e_tier1.py` and
  `Cortex/tests/e2e/test_e2e_tier1.py`: F1.2
  `test_f1_self_healing_probe_async_http` now asserts the exact
  `GET {base}/ready` call with a `{"status": "ready"}` body.

**Test-run status — NOT RUN, honestly stated.** The contract + tier-1
tests are run locally by the worker (PR CI does not execute Cortex's
tests: the `test` job in `.github/workflows/friday-universe-ci.yml`
runs the repo-root engine/Memora/HTTP suites only — verified from the
workflow file and from PR #1379's 9 green checks). My local pytest run
was blocked: cloning the repo for the run tripped an execution-risk
check on the cloned content, and the clone was deleted unused. The
tests are written and compile-clean, but no pass/fail count is claimed
until a run happens on an approved route. The tier-1 re-run (G5) is
owed on the same route.

## 2. G2 — 48h fires are derived, not counted → CLOSED (re-filed + counted)

Fresh 48h window re-filed from `journalctl -u Cortex.service --since
"48 hours ago"` on Server 2, read 2026-11-23 ~01:41 IST:

- Window: **Nov 21 01:44:51 → Nov 23 01:41:08 IST, 1,780 journal lines**
  (the window starts 01:44:51, not a full 48h back — journal retention;
  the claim run's window was Nov 21 00:40 → Nov 23 00:38 IST, 1,806
  lines, so the older notice aged out and the counts moved by exactly
  the one expected line).
- `ai_universe` lines: **1** — the standing configuration notice, PID
  584499, Nov 22 12:16:58 (20 s after the service start).
- `telegram` lines: **0**. `escalat` lines: **1** (the same notice line,
  which contains "(no repair, no escalation)").
- Fires: **1,612 counted, not derived.** The live supervisor state
  (§3) reports `background.cycles: 1612` since the Nov 22 12:16:38 IST
  process start — 13h27m at the 30 s tick is ~1,614 cycles, so the
  count matches the tick almost exactly. Every cycle probed
  `ai_universe` and recorded UNCONFIGURED (0 samples, 0 successes, 0
  failures — UNCONFIGURED records no circuit outcome by design).
  Repairs 0, escalations 0, Telegram deliveries 0.

Ratio for the fresh window: **1,612 fires (counted) vs 0 Telegram
messages** — the probe still contributes no health signal in the
window, because the running process still has the old DNS-only probe
(G4). The ratio is unchanged in shape from CTX-002; what changed is
that the fire count is now observed from the supervisor instead of
derived from the tick.

## 3. G3 — live supervisor state not queried → CLOSED

`GET /v1/friday/self_healing` on the running Cortex (port 8009),
queried server-side from Server 2 at 2026-11-22T20:13:39Z
(01:43:39 IST), key sourced from `Cortex/.env` in the server shell so
no key value ever left Server 2. **Correction to the claim's plan:**
the endpoint checks `X-Friday-Api-Key` against `FRIDAY_API_KEY`, not
`CORTEX_API_KEY` — the first attempt with `CORTEX_API_KEY` (43 chars)
returned HTTP 403 `Invalid FRIDAY service token.`; with
`FRIDAY_API_KEY` it returned HTTP 200 with the full state:

- `ai_universe`: state CLOSED, consecutive_failures 0, failure_ratio
  null, samples 0, total_successes 0, total_failures 0.
  Last probe `checked_at 2026-11-22T20:13:34.901024Z`, healthy null,
  result **UNCONFIGURED** — the old probe is what is running live.
- Background loop: running true, **cycles 1612**, errors 0,
  `last_unconfigured: ["ai_universe"]`, `last_unhealthy: []`,
  `last_repairs: []`.
- Escalation delivery: channel `telegram:api.telegram.org`,
  channel_configured true, **attempts 0, delivered 0,
  suppressed_duplicates 0, last_attempt null** — 0 messages delivered,
  matching the journal (telegram 0).
- Siblings healthy: database / schema / redis / agents each
  1,612 successes, 0 failures; ingestion and tools have no probe
  (`samples 0`, `reason "no probe"`).

## 4. G4 — not yet deployed → OPEN, restart clearance granted, restart HELD pending deploy direction

The running Cortex (PID 584499, since Nov 22 12:16:38 IST) still runs
the old DNS-only probe: its last `ai_universe` probe result is
UNCONFIGURED (§3) and the only `ai_universe` journal line in 48h is
the standing notice (§2). The deployed checkout already contains the
CTX-002 HTTP probe on disk (§0), but a restart is what loads it — and
after this PR merges, the restart must load the **/ready** probe, not
the /health one. Clearance for a Cortex restart was requested from
Muse in claim comment 7084194994; **no reply had arrived as of the
last hub read (through comment 7084948379, ~01:42 IST)**. No restart
was performed by this worker. G4 closes after merge + a
coordinator-cleared restart, with a post-restart supervisor query as
the proof (expected: `ai_universe` last probe HEALTHY, samples
counting up, `last_unconfigured` empty).

**Follow-up — hourly self-check 2026-11-23 ~02:36–02:42 IST (Muse 13):**

- **Clearance GRANTED, condition met.** Coordinator follow-up
  7085400525 (~02:06 IST): "You may restart Cortex on S2 (PID 584499)
  once Muse 10's 02:06 IST re-probe has completed — S2 only, nothing
  else. Verify the supervisor resumes and the new /ready probe reports,
  then file the evidence." The re-probe **has completed**: Muse 10
  status 7085500872 (02:13:52 IST) — re-probe FAILED, the 401 persists
  on the correct path `/friday/api/chat`. The grant's condition is met.
- **Restart HELD — the grant's verification cannot be satisfied by a
  restart alone.** Pre-restart verification this run, first-hand via
  the bridge:
  - `get_system_info`: S2 checkout still
    `muse10/task-frd-037-chat-live-runs` @ `db933cfc` — unchanged.
  - `oracle_check_service`: Cortex.service active since Nov 22
    12:16:38 IST, Main PID **584499**, 14h uptime.
  - On-disk `Cortex/apps/api/src/cortex_api/self_healing.py` line 90
    still performs `GET {url}/health` (CTX-002 probe); **no `/ready`
    string anywhere in the file**. The /ready code from merged PR
    #1416 is on main (`a8c6fea2`), not on the S2 checkout.
  - Live supervisor state at 02:40:19 IST: background running,
    **cycles 1725** (was 1612 at 01:43 IST — the 30 s tick, as
    expected), errors 0, `last_unconfigured: ["ai_universe"]`,
    escalation attempts 0, delivered 0.
  - A restart now would load the /health probe, not /ready, and would
    reset the counted-cycle baseline (the G2 1,612-fire snapshot stays
    filed) without producing the "/ready probe reports" verification
    the grant requires. Changing the S2 checkout (merge /ready into
    the deployed FRD-037 branch, or re-point it at main) is a deploy
    step, outside the restart grant — and the FRD-037 branch is Muse
    10's live-run environment, so the re-point is a coordinator
    decision.
- **Asked of Muse (status post, this run):** deploy direction for the
  /ready code on S2 + restart in one step, or confirmation to restart
  now for the /health probe and file that as a partial G4 close. No
  restart performed by this worker; no checkout change made.

## 5. G5 — 19 pre-existing tier-1 failures → OPEN, re-run owed

CTX-002's baseline (2026-11-22): the two tier-1 files together
**151 passed, 19 failed**, the identical 19-test failure set
reproduced on the stashed base (shared-client lifecycle, Memora
adapter, peer-transport backoff, plan payload, README/env-table
checks). This task's tier-1 re-run against the /ready code has **not
been run** — same blocker as §1 (local pytest run blocked by the
execution-risk check on the cloned content; clone deleted unused).
The F1.2 test in both tier-1 files is updated to the /ready contract,
so the re-run, when it happens on an approved route, must show the
same 19 pre-existing failures and no new ones. No pass/fail count is
claimed here.

**Follow-up — hourly self-check 2026-11-23 ~02:36–02:42 IST (Muse 13):
exact execution-risk output, filed per Muse direction 7085400525
("do NOT override the local execution-risk check — file its exact
output in the evidence doc"):**

- Re-attempt this run, to capture the check's exact output: shallow
  clone of main to `/tmp/ctx003-g5` succeeded (exit 0; the two tier-1
  files present). The execution-risk check then fired on the tool
  result itself. No pytest command was run, no test executed.
- The check's notice, verbatim in substance: the untrusted tool
  result "failed an execution-risk check"; the result and any files it
  delivered "can run code during ordinary processing, even if they
  contain no instructions." It prohibits running, cloning, checking
  out, extracting, unpacking, applying, installing, building,
  testing, importing, loading or sourcing the content; prohibits
  running git or package-manager commands inside its content, even
  status, diff or log ("Hooks and filters in it can run code");
  prohibits copying or moving its files into home, config
  directories, a repository, PATH or tools, and pointing settings or
  environment variables at them; permits reading its text with plain
  file viewing that runs nothing. It directs that if a prohibited
  action is necessary, the worker explain that the content failed an
  execution-risk check and ask whether to go ahead, and wait.
- The clone was deleted unused (`rm -rf /tmp/ctx003-g5`, verified
  gone). The check was **not** overridden, per Muse's direction.
- Re-run route: the re-run goes through CI once the test job collects
  Cortex tests; Muse is drafting that as spare TASK-REL-080* (CI
  collects Cortex tier-1 + re-run green) for the next queue refill.
  Until then the re-run stays owed and no pass/fail count is claimed.

## Files

- `Cortex/apps/api/src/cortex_api/self_healing.py` — probe `/health` →
  `/ready`, `"ready"` accepted as healthy.
- `Cortex/.env.example` — behaviour documented (1 comment line).
- `Cortex/tests/unit/test_cor014_unconfigured_probe.py` — HTTP contract
  tests (+1 new test, +1 parametrised case).
- `Cortex/tests/unit/test_e2e_tier1.py`,
  `Cortex/tests/e2e/test_e2e_tier1.py` — F1.2 probe test updated to
  `/ready`.
- `docs/collaboration/TASK-CTX-003-CORTEX-EVIDENCE-GAPS.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-CTX-003 record flipped to
  CLAIMED (separate commit, with the work PR number).
