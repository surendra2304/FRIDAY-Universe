# TASK-FRD-054 — CHECKPOINT 1 — 2026-11-25 ~15:30 IST — Muse 15

Claim: hub #1483 comment 7158925963 (WATCH091 assignment 7158754888).
Branch: muse15/task-frd-054-production-verify, from main 76fc7dda.
Task: PRODUCTION-VERIFY FRIDAY corpus IG2-FRD-03, IG2-FRD-04, IG2-FRD-05, IG2-FRD-06
(live extreme-condition verification, wave 2, P1).

## Scope (board, main 76fc7dda, read first-hand)

| Item | Title | Board status | Implementing PR | Production probe owed |
|---|---|---|---|---|
| IG2-FRD-03 | Delegated lead-generation errand (directory -> contact table) | MERGED | #736 (registry wiring #772) | `lead_generate` answers through the live agent's production registry |
| IG2-FRD-04 | Post-meeting follow-up automation | MERGED | #740 (registry wiring #772) | `meeting_followup_create/list/decide` answer through the live agent's production registry |
| IG2-FRD-05 | Opt-in browser wake word for the FRIDAY stage (multi-word phrases, this tab only) | MERGED | #786 (build fix #833) | Real-tab wake-word hearing test: arm in a real browser tab on the live site, fires on a multi-word phrase, inert on bare "friday" |
| IG2-FRD-06 | Local-business patterns F-30/F-35 (prospect qualification + website/appointment prompt building; generation only, no outreach) | MERGED | #785 | `local_business` answers through the live agent's production registry |

## Code side — VERIFIED live on S1 checkout (read-only, 2026-11-25 ~15:24 IST)

S1 checkout `/opt/friday_universe`, HEAD b51ef05f (behind main, dirty — same as
the INF-035/036 runs). `FRIDAY/src/friday/agent/mixins/tools.py`,
`_create_default_registry()` registers all four tools:

- `LocalBusinessTool()` — with the IG F-30/F-35 comment, "Registered at creation".
- `LeadGenerateTool()` — with the TASK-IG2-FRD-03 comment, "previously export-only".
- `MeetingFollowUpCreateTool()`, `MeetingFollowUpListTool()`,
  `MeetingFollowUpDecideTool()` — with the TASK-IG2-FRD-04 comment.
- Tool implementation files present: `lead_gen_tools.py`,
  `meeting_followup_tools.py`, `local_business_tools.py` under
  `FRIDAY/src/friday/tools/builtin/`; `WakeListener` (`lib/wakeWord.ts`) is
  the IG2-FRD-05 implementation (per board evidence, PR #786).

The registry wiring is present in the deployed checkout. Whether the tools
answer through the *running* agent is the live leg — and it is blocked (below).

## Live state — FRIDAY IS DOWN on S1 (read-only probes, 2026-11-25 ~15:24 IST)

Probes via bridge `run_shell` on S2 -> `ssh ubuntu@10.0.0.121` (read-only):

- `FRIDAY.service`: **inactive (dead)**. Unit file exists
  (`/etc/systemd/system/FRIDAY.service`, disabled). Journal last entries:
  **2026-11-24 13:42:13 IST — graceful shutdown, "Deactivated successfully",
  "Stopped FRIDAY Universe - Operating System & Master Dispatcher"**
  (pid 3577788). No entries since.
- `FRIDAY-Voice.service`: **inactive (dead)**. Last journal entries:
  **2026-11-24 12:54:15 IST — LiveKit worker shutdown, service stopped.**
- Nothing listens on :10000 or :8000; no FRIDAY process runs on S1
  (only Memora :8002, Forge :8006, Cortex, Sentinel running; Stratex inactive).
- S1 itself is calm: load 0.43, 294 MB available. A REL-096 fleet backup was
  running on S1 from ~15:23 IST (owner job, not mine).
- Public ingress `https://friday-universe.duckdns.org/friday/health` answers
  **healthy** (`overall: healthy`, `service: friday_core`, Oracle SELECT 1 ok)
  — but its platform string is `Linux-7.0.0-1014-aws-x86_64`: the answering
  host is AWS, not Oracle S1. Same shape as the INF-035/036 Inference
  finding (S1 service dead, live gateway AWS-hosted behind a tunnel/ingress).

## Discrepancy — flagged, not resolved

TASK-VOI-038 acceptance run 23 (Muse 15, 2026-11-24 ~17:00 IST) recorded
FRIDAY.service active/running with /health 200. Today's journal shows no
FRIDAY.service activity since the 13:42 shutdown. Either the run-23 probe
read a different process/host than it reported, or the service cycled without
journal trace (no evidence for the latter). The ruling question stands either
way: S1 FRIDAY is down *now*, and the live-leg target needs a decision.
The run-23 note should not be relied on until this is reconciled.

## Blocked — rulings owed from Muse

1. **Live-leg target:** restore/restart S1 `FRIDAY.service` +
   `FRIDAY-Voice.service`, OR re-target the FRD-054 live legs at the
   AWS-hosted `friday_core` behind the public ingress. Until one is settled,
   no live probe can run — there is no live FRIDAY on FRIDAY-Server to probe.
   (TP7's FRD-052 faces the same block: its WATCH091 clearance for
   IG-FRD-006/009 read-only probes assumed live FRIDAY on S1.)
2. **Failure injection** (acceptance: "a downstream agent down" per item):
   not run and not cleared. Once the target is settled I will file
   checkpoint 2 with the exact commands, drill window and rollback per leg,
   and run nothing until cleared — per the WATCH091 ruling on FRD-052.
3. **IG2-FRD-05 real-tab test:** needs the live stage URL plus a browser-tab
   run with microphone — same clearance, and the stage is served from
   `/srv/friday-static` via S1 Caddy (`/friday*` handler) per the S1
   Caddyfile read this run.

## Not done this run (no live moves made)

- No service restart, no deployment, no code change on any live server.
- No live probe executed (nothing to probe against on S1; public-health read
  only). No failure injection attempted.
- No work PR yet — one work PR when DONE or genuinely BLOCKED (owner rule 1).
  Board flip (FRD-054 AVAILABLE -> CLAIMED) rides in the work PR.

## Five states (TASK-FRD-054)

- implemented: YES (items merged; registry wiring present in the S1 checkout)
- tested: NO (live legs blocked)
- merged: NO (work PR not opened)
- deployed: PARTIAL (code in the S1 checkout; services down)
- production-verified: NO (0 of 4 items verified live)

## Schedules / usage

- `muse15-work-request`: CANCELLED this run (claim made). Hourly self-check +
  weekly reset stay armed.
- Usage: 25% of free weekly limit (checked this run; reset Mon Nov 30, 7:04 PM IST).

— Muse 15
