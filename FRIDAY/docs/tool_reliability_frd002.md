# TASK-FRD-002 — FRIDAY tool-use reliability audit (2026-11-15)

**Crew:** Muse (`muse_ai`), Wave 5. **Claim:** issue #35 comment 6891586665.
**Method:** (1) static inventory from fresh main `ef3ca99f`; (2) live exercise on
Server 1 against the *deployed* code (checkout `56e28e63` at exercise time) using a
harness that constructs `FridayAgent` exactly as `friday.api.server` does
(`get_settings()` + `DefaultSecureAuthorizer`) and drives every tool through the
production sequence — authorizer verdict first, then `ToolRegistry.execute` with
the minted capability. Side-effecting tools were never executed by the harness
(real sends, host power, self-modification, process kills); for those, the
authorizer verdict — the exact decision production would act on — is the evidence.
Scratch writes were confined to `FRIDAY/.frd002_scratch/` and removed afterwards.

## Headline facts about the live system

- **90 tools registered, 90 schemas exposed, 90 unique names** (live registry
  count == register()-call count, so no registration silently overwrote another).
- **Production runs with `autonomous_mode=true` and `full_access_mode=true`.**
  Consequences, verified live: the headless authorizer auto-approves every SAFE
  tool unconditionally and every SENSITIVE tool under autonomous mode. Only
  DANGEROUS tools (`kill_process`) are always refused headless. The safety
  classification of each tool is therefore the *only* gate for almost every
  action FRIDAY can take from web/voice chat.
- Agent construction mode for the exercise: the real `FridayAgent`
  (memory: `OracleConversationMemory`).

## Defects found

### D1 — FIXED IN THIS PR: ungated process termination inside a SAFE tool
`system_control` (SAFE) exposed a working `terminate_process` action — real
`psutil.Process.terminate()` calls behind only a six-name protected list
(`system`, `smss.exe`, `csrss.exe`, `wininit.exe`, `services.exe`, `lsass.exe` —
a Windows-era list; nothing on the production Linux host is on it). The
dedicated `kill_process` tool is DANGEROUS and always refused headless, but the
same capability was reachable with no authorization at all via `system_control`.
An LLM tool call from the owner's web chat could have terminated arbitrary
processes on Server 1 (other agents, the Stratex daemon, FRIDAY itself).
**Fix:** `terminate_process` removed from `system_control` (schema + branch);
termination remains available only via `kill_process` behind its DANGEROUS
gate. Pinned by `FRIDAY/tests/test_frd002_tool_gates.py`; the pre-existing
assertion in `test_futuristic_tools.py` was updated to the new contract.

### D2 — `ai_universe_query` rejects its own answers (live failure)
Probe "Which agents are online right now?" ran 35.1s and returned an error:
*"AI Universe Verification Result: Needs Human Review (Confidence: 0.55 < 0.70
threshold …). Answer rejected."* The multi-agent query path discards completed
work below a 0.70 confidence threshold and surfaces no answer at all. FAIL.

### D3 — Delegation tools time out under load (live failure, corroborated)
`stratex_portfolio` with no arguments ran 15.8s and errored:
*"Stratex could not answer that: ReadTimeout: outcome unconfirmed after
dispatch…"* — an honest error (no fabricated figures; the TASK-STR-ANS-001
honesty behaviour holds), but the tool fails end-to-end under the fleet load
present during the exercise. `intelx_research` passed but took **85.9s** for a
one-headline brief; `ai_universe_query` took 35.1s to fail; `futuris_forecast`
36.4s. Delegation latency under load is the dominant reliability theme.

### D4 — `futuris_forecast` returns success-flagged hollow output
The call returned `is_error=false` with content *"Point estimate: 0.0
(80–90% band: 0.0 – 0.0) • Status: BLOCKED | Confidence: INSUFFICIENT…"* (the
known statsforecast-absent state). The BLOCKED label is honest in the text, but
the success flag means the agent layer can present a 0.0 "forecast" as a
completed tool result. PARTIAL — recommend the tool return `is_error=true`
(or a refused result) whenever the forecast status is BLOCKED.

### D5 — Residual classification notes (catalogued, not changed)
- `system_power_control` is SAFE, but self-refuses `shutdown`/`restart` in its
  own code; only `lock`/`sleep` execute. On the headless server these are
  inert; on the owner's laptop they would run without confirmation. Recommend
  SENSITIVE for consistency; not changed here (behaviour decision for the
  coordinator, interacts with the laptop-controller flows).
- `execute_command` is SAFE but allowlist-confined by design (diagnostic
  commands only; destructive commands and shell redirection blocked in code).
  No change.
- `file_operations` / `write_code_file` / `replace_file_content` are SAFE but
  confined by the shared workspace PathPolicy. No change.
- Tools defined but not in the LLM registry, by design or otherwise:
  `VyralXScriptTool`, `CortexWebOpsTool`, `MemoraMemoryTool` are reachable via
  deterministic fast paths (`agent/mixins/fast_paths.py`) — not defects.
  `ExecuteComputerActionTool` has no caller anywhere (only the proposal-only
  `propose_computer_action` is exposed) — consistent with the known
  computer-control gap (TASK-LAP-001). `LookupWebAppTemplateTool` is dead code.

## Per-tool results — Batch A (fleet, delegation, core)

Live on Server 1, deployed head `56e28e63`, 2026-11-15 ~14:54 IST.
"Verdict-only" = authorizer decision recorded; harness never executed the tool.

| Tool | Safety | Verdict | Result |
|---|---|---|---|
| get_system_info | SAFE | APPROVED | PASS (88 ms) |
| get_fleet_status | SAFE | APPROVED | PASS (8.7 s) — "7/9 specialist agents up" |
| get_ai_universe_status | SAFE | APPROVED | PASS (1.3 s) |
| ai_universe_query | SAFE | APPROVED | **FAIL** (35.1 s) — answer self-rejected, conf 0.55 < 0.70 (D2) |
| fleet_dispatch (unknown agent) | SAFE | APPROVED | PASS — honest error listing the nine agents |
| task_status | SAFE | APPROVED | PASS (94 ms) — honest empty-ledger answer |
| forge_code_task | SAFE | APPROVED | Verdict-only — would dispatch a real Forge build in production |
| intelx_research | SAFE | APPROVED | PASS but slow (85.9 s) (D3) |
| stratex_portfolio | SAFE | APPROVED | **FAIL** (15.8 s) — ReadTimeout after dispatch (D3) |
| sentinel_security [posture] | SAFE | APPROVED | PASS (1.9 s) |
| futuris_forecast | SAFE | APPROVED | PARTIAL (36.4 s) — success flag on BLOCKED 0.0 forecast (D4) |
| get_time_date | SAFE | APPROVED | PASS (0.5 s) |
| calculator | SAFE | APPROVED | PASS — 2+3*4 = 14 |
| health_check | SAFE | APPROVED | PASS (0.8 s) |
| get_system_resources | SAFE | APPROVED | PASS (5.5 s) |
| system_control [system_status] | SAFE | APPROVED | PASS (0.1 s) |
| system_control [list_processes] | SAFE | APPROVED | PASS (0.5 s) |
| system_control [terminate_process] | SAFE | APPROVED | **D1 — removed by this PR** (not executed; code-verified) |
| list_skills | SAFE | APPROVED | PASS — 24 skills |
| run_skill (unknown skill) | SENSITIVE | APPROVED (autonomous) | PASS — honest refusal listing skills |
| self_develop | SENSITIVE | APPROVED (autonomous) | Verdict-only — self-modification would execute in production |
| self_repair | SENSITIVE | APPROVED (autonomous) | Verdict-only — self-modification would execute in production |

## Per-tool results — Batches B and C

**NOT RUN — infrastructure.** The engineering bridge (Server 2) became
unreachable during the Wave-5 peak (MCP initialize timeouts, one HTTP 502,
while the public site itself answered 200 in ~2 s — the bridge service, not
the network). Batch A and the static inventory were already complete, and the
D1 fix does not depend on B/C. The harness (`/tmp/frd002_harness.py` on
Server 1, hash-verified copy in the crew workspace) covers the remaining
tools in batches B (web, memory, files, dev, comms) and C (desktop, OS,
Android, media, VyralX) and can be run verbatim by any crew once the bridge
recovers: `sudo -u ubuntu /opt/friday_universe/venv/bin/python
/tmp/frd002_harness.py B` (then `C`). Until those runs land, the per-tool
verdicts for B/C tools in this catalogue rest on the static evidence cited
in D5 and the inventory, and are marked as such wherever relied upon.
The scratch directory the harness creates (`FRIDAY/.frd002_scratch/`) is
removed by the follow-up runbook in the crew's completion comment.

## Inventory (all 90 exposed tools)

Source: `FRIDAY/src/friday/agent/mixins/tools.py` register() calls resolved to
classes at fresh main `ef3ca99f`; confirmed against the live registry (90/90).
Names are the LLM-facing tool names. (Full machine-readable inventory with
parameters was produced by the crew's extractor and is summarised in the
completion comment on issue #35.)

get_system_info, get_fleet_status, fleet_dispatch, task_status, forge_code_task,
intelx_research, stratex_portfolio, sentinel_security, futuris_forecast,
web_fetch_summarize, vyralx_project, vyralx_render, vyralx_publish,
get_time_date, calculator, read_file, list_dir, search_memory,
get_screen_snapshot, propose_computer_action, open_application, type_text,
close_application, manage_volume, system_power_control, manage_windows,
web_search, fetch_webpage, browser_action, file_operations, execute_command,
read_screen_text, find_on_screen, get_active_app_context,
read_active_window_text, git_status, git_commit, git_push, list_github_issues,
create_github_issue, get_system_resources, kill_process, launch_application,
system_control, health_check, write_code_file, replace_file_content, run_tests,
create_git_branch, control_light, control_plug, fetch_webpage_content,
synthesize_information, toggle_dark_mode, toggle_bluetooth, toggle_wifi,
get_todays_events, send_email, draft_email, read_gmail_inbox, draft_gmail,
send_gmail, send_whatsapp_message, open_whatsapp, read_own_codebase,
ai_universe_query, get_weather, get_news, manage_tasks, open_website, youtube,
location_and_maps, wikipedia_summary, dictionary, media_control, remember_fact,
verify_face_identity, enroll_face_identity, android_tap, android_swipe,
android_open_app, android_type, android_keyevent, android_device_info,
list_skills, run_skill, get_ai_universe_status, screen_prediction,
self_develop, self_repair.

## Harness limitations (stated plainly)

- The harness ran as a second agent instance on the same host (same code,
  settings, authorizer and registry as the service); it did not route through
  the owner's browser session or the LLM tool-selection loop — tool *selection*
  quality is TASK-FRD-001/004 territory; this audit covers tool *execution*
  reliability once selected.
- `/etc/friday/dispatch.env` is root-only; systemd injects it into the service
  process. The harness (running as `ubuntu`) could not read it, so any
  dispatch-env-only variables were absent. No exercised tool showed an effect
  attributable to this.
- Batch timings were taken under heavy fleet load (82 crews active); treat
  latencies as load-condition evidence, not idle-host benchmarks.
