# TASK-FRD-068 — FRIDAY memory reporting fix: cgroup memory, not host memory

- **Worker:** Muse 13. **Assignment:** BE 01:56 §B (hub #2045 comment 7227510023), answers the idle post. P1, follow-up of FRD-067 (NOT VERIFIED, review 6092948836, 0/3).
- **Claim:** hub #2045 comment 7227539045 (01:58 IST). Branch `muse13/task-frd-068-memory-reporting-fix` @ main `02249160` (fast-forwarded from `f8e70596` at claim time; no other commits on the branch).
- **Board:** TASK-FRD-068 CLAIMED/muse_13 on live main `02249160` (blob `fd85a2a1`, verified first-hand); flip landed via board PR #2202 (merged 02:14:35 IST).

## Acceptance

"FRIDAY reports its own cgroup memory (200 MB limit), not host memory, in every status/memory path; the OOM guard notice matches the value FRIDAY reports; evidence filed with before/after probes on the live FRIDAY service."

## The defect (before)

FRD-067 (PR #2191 evidence, 3 live loopback runs ~00:46–00:55 IST, 0/3 correct): every reply quoted host memory — 45.9% (875 MB of 1,905 MB), 45.5% (866 MB), 45.8% (872 MB) — while the service cgroup sat at 97.7% / 99.9% / 95.0% of its 200 MB cap, and claimed "no active alerts" while the reply's own guard notices listed 93–100% readings.

**Fresh before-probe at fix time (this task, bridge `run_shell` server 3, standing clearance 7200564540; read-only recon + one loopback turn, no production change):**

- Recon 2026-11-27T21:33:35Z (03:03:35 IST): `FRIDAY.service` active, MainPID 120811, NRestarts 3. Cgroup `memory.max` 209,715,200, `memory.current` 204,009,472 = **97.3% of cap**. Host `free`: 866 MB used of 1,905 MB = **45.5%**.
- Loopback turn 21:34:22–21:35:27Z: HTTP 200 in 75.4 s, `task_state: COMPLETED`, confidence 1.0, provider gemini, model `gemini-3.6-flash`. Reply (verbatim): "Here's a quick snapshot of the FRIDAY service right now: **Health status:** HEALTHY — **Memory usage:** 46.6% (888 MB / 1,905 MB) — All metrics are nominal with no active alerts."
- Same response's `proactive_notice`: "my memory use is at **97.4% of the 200.0 MB service limit (194.7 MB used). If it keeps climbing the kernel will kill me without warning.**" plus a second notice at 81.9%. The guard notice and the reply's own figure contradict — the exact mismatch this fix removes.
- Cgroup after the turn: 208,605,184 = **99.5% of cap** (the turn itself pushed it up). Recalled memory shows FRD-067 run 3's wrong reply (45.8%, 872 MB) at score 0.6667 — the wrong answer persists in memory, compounding across runs.
- **Before verdict: defect reproduces, 0/1 on the fresh run (0/3 on FRD-067).** Full record: `~/workspace/muse13/frd068/before_probe.json`.

## Root cause

The memory guard (`FRIDAY/src/friday/observability/proactive_engine.py`, TASK-FRD-041/043) already reads the service's own cgroup (`read_cgroup_memory()`, own-cgroup resolution from `/proc/self/cgroup`) — that is why the guard notices were right. But every other status/memory path read host RAM via `psutil.virtual_memory()`: the `health_check` tool's report (the exact text FRD-067's replies quoted — "RAM: 45.9% (875 MB / 1,905 MB)" + "No active alerts"), `get_system_resources`, `system_control` `system_status`, the `/api/telemetry` and `/api/system_telemetry` endpoints, the self-repair diagnostic, the audit skill, the HUD diagnostics, and the briefing line.

## The fix

One shared helper, then every reporting path prefers it:

- `FRIDAY/src/friday/observability/proactive_engine.py` — new `service_memory()`: returns `{"percent", "used_mb", "limit_mb", "scope": "cgroup"}` when the process runs under a **capped** memory cgroup, else `None`. Built on the existing `read_cgroup_memory()` (v2 + v1 fallback, own-cgroup resolution). A present-but-unlimited cap yields `None`.
- `FRIDAY/src/friday/tools/builtin/health_monitor.py` — `collect_health_report()` reports the cgroup figure as RAM when capped, with `memory_scope` + explicit `host_ram_*` fields kept for diagnostics; memory alerts now fire on the **same 75%/90% thresholds the OOM guard uses**, so the report can never say "no active alerts" while the guard is warning. `HealthCheckTool` labels the line "... MB service limit" when cgroup-scoped.
- `FRIDAY/src/friday/tools/builtin/system_monitor.py` — `get_current_system_resources()` reports the cgroup figure as RAM (MB figures in the content line so the 200 MB cap does not collapse to "0.2 GB / 0.2 GB"); `memory_scope` + `host_ram_*` in the dict.
- `FRIDAY/src/friday/tools/builtin/system_control.py` — `system_status` action reports the cgroup figure, labeled "service limit".
- `FRIDAY/src/friday/api/server.py` — `_sample_telemetry()` (`/api/telemetry`) and `_sample_system_telemetry()` (`/api/system_telemetry`) report the cgroup figure as RAM, with `memory_scope` + `host_ram_*` fields.
- `FRIDAY/src/friday/autonomous/controller.py` — `execute_self_repair()` memory check uses the service figure (same 90% DEGRADED threshold, now on the right denominator).
- `FRIDAY/src/friday/skills/builtins/system_health_audit.py` — fallback (tools unavailable) uses the service figure; the canned "OPTIMAL" rating is now conditional on the reported memory pressure (`ATTENTION` ≥90%, `CAUTION` ≥75%).
- `FRIDAY/src/friday/agent/agent.py` — `get_system_diagnostics()` (HUD) reports the cgroup figure as RAM, with `host_ram_*` keys.
- `FRIDAY/src/friday/workflows/master_briefing.py` — `_local_status()` briefing line reports the cgroup figure ("97.7% of the service limit") when present.

In every path, when no capped cgroup exists (dev machines, CI, Windows, containers without a cap) the host figures are used **exactly as before** — the change is behavior-preserving off the live host. All cgroup reads go through the existing reader with a `try/except` fallback to host, so a tool can never break on an unavailable observability import.

Deliberately untouched, with reasons:

- `FRIDAY/src/friday/cognition/reflex.py` `scan_resources()` — a **host**-pressure trigger by design ("Report host pressure that is demonstrably real"); changing what it triggers belongs to FRD-064 (TP1, OOM-kill prevention), not this reporting fix.
- `FRIDAY/src/friday/devices/windows_friday.py` and the `server.py` Windows fast-path metadata — Windows has no cgroup; host memory is the correct figure there.
- `FRIDAY/src/friday/tools/builtin/system_info.py` (`get_system_info`) — reads total physical RAM only on Windows; on Linux it reports no memory at all.
- `proactive_engine.capture_snapshot()` `ram_*` fields — they describe the **host**; the service's own memory is in the adjacent `cgroup_*` fields and is what the guard announces. Switching `ram_*` to cgroup would double-announce `ram_critical` + `memory_critical` for the same condition.

## Tests (scratch venv, `FRIDAY/tests/`, first-hand)

- **New `FRIDAY/tests/test_frd068_memory_reporting.py`: 12/12 passed.** Fabricated cgroup trees (same pattern as the FRD-041 guard tests) + the FRD-067 live host figures (45.9%, 875/1,905 MB) as the mock host, so any test still quoting host memory fails. Covers: `service_memory()` capped/unlimited/missing; `health_check` at 97.7% (reports cgroup, `healthy` False, "Service memory usage is very high" alert, no "No active alerts", no host figure leaked) and at 50% (calm — "No active alerts" still appears); host fallback without a cgroup; `get_system_resources` cgroup + fallback; `system_control system_status` cgroup; audit skill rating `ATTENTION` at 97.7% / `OPTIMAL` at 50%; controller self-repair memory check `DEGRADED` with "service limit" evidence.
- **Existing suites, same run: all pass** — `test_system_monitor_phase25.py`, `test_frd041_memory_guard.py`, `test_proactive_automation_and_intelligence.py`, `test_proactive_phase17.py`, `test_proactive_greeting_memory.py`, `test_api_command_truthfulness.py`, `test_effect_truthfulness.py` (74 passed across the last two files' run; 31 passed in the proactive/guard run).
- **Two pre-existing failures on main `02249160`, unrelated to this change (verified first-hand, not fixed here — out of scope):**
  1. `test_autonomous_diagnostics_truth.py::test_self_diagnostic_never_claims_repairs_without_performing_them` — expects the old fleet-check scope string "HTTP health/status endpoint responses only"; pristine `controller.py:742` on main already carries the new wording ("Capability report from each peer's /health..."). My diff to `controller.py` touches only the memory check (lines 707–721); the scope string is untouched.
  2. `test_frd002_tool_gates.py::test_default_registry_tool_names_are_unique` — expects exactly 97 registered tools; the registry now holds 162 (tool inventory grew since the test was written). This change adds, removes, and renames no tools.
- Server telemetry samplers (`server.py`) and `agent.get_system_diagnostics` / briefing remaps are covered by the shared-helper unit tests plus syntax check; their full-path tests run in CI (the `server.py` import chain needs the full app stack).

## After-leg (owed)

The fix changes what FRIDAY reports; the live service still runs the old code. **After-probe owed after deploy:** re-run the FRD-067 question (same loopback turn) and expect the reply to quote the cgroup figure (~97–99% of the 200 MB service limit) with the memory alert listed — then M8 re-probes FRD-067. Deploy of this fix to FRIDAY-Server needs Muse's clearance on the hub under the live-servers rule; requested in the completion post. The remote-gateway 401 stays with TP8 (FRD-065); unchanged by this task.

## Five states

- implemented: YES (9 files, +289/−0 changed lines approx., 1 new test file, this evidence doc)
- tested: YES — 12 new tests + existing suites first-hand (see above; 2 pre-existing main failures noted, unrelated)
- merged: NO (work PR open)
- deployed: NO (deploy clearance requested)
- production-verified: NO — after-probe + M8 FRD-067 re-probe owed after deploy

— Muse 13
