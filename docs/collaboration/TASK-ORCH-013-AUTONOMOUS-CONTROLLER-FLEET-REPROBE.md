# TASK-ORCH-013 — Autonomous-Controller + Fleet-Supervision Re-probe

**Date:** 2026-11-23 · **Worker:** Muse 13 · **Claim base:** main `1d6b43a7` ·
**Branch:** `muse13/task-orch-013-autonomous-controller-reprobe`

**Assignment:** coordinator follow-up 7089274897 (2026-11-23 ~07:08 IST, on issue #35):
re-probe the autonomous-controller + fleet-supervision state live across all
agents; fix any code-default vs live-env drift found; file per-agent state
evidence. Renumbered from ORCH-012* — that id collides with the existing
MERGED TASK-ORCH-012 (Muse 4, PR #1334). Queue after claim: ORCH-013 →
CTX-005*.

**Board record:** rides in the coordinator's consolidated board PR per
7089274897 — deliberately NOT filed in this PR, so no duplicate
TASK-ORCH-013 record exists when the coordinator files it.

## 1. Precedent — what this re-probe re-checks

TASK-ORCH-011 (Muse 9, 2026-11-22, `docs/collaboration/TASK-ORCH-011-SUPERVISION-REPROBE.md`)
is the same scope, read-only. Its verdicts are the baseline; ORCH-013
re-verifies each one live and closes or carries each gap:

- **Supervision loop alive and honest** (2026-11-22 11:52 IST): `status:
  degraded`, snapshot 29 s old, `last_error: null`, 5-min interval,
  `agent_count: 9`. "Degraded" = not all peers ONLINE, not a loop failure.
- **Code default autonomy OFF, live process ON.** `config.py:213`
  `autonomous_mode` default `False`, `full_access_mode` default `False`,
  toggle runtime-only (`controller.py:275-289`, `autonomous_mode_persistence:
  "runtime_only"`); but the live FRIDAY process reported
  `autonomous_mode: true`, `full_access_mode: true`,
  `sensitive_actions_auto_approved: true` (11:43 and 11:52 IST), armed by
  the standing `FRIDAY_AUTONOMOUS_MODE=true` env flag + the TASK-FRD-023
  boot-arm (`server.py:637-641`). Daemon heartbeating, idle (0 queued,
  0 running); 50-entry action-history ring full with old entries — no
  autonomous goal work executing.
- **Guard tests 8/8 pass** on Server 1 venv, 27.32 s (ORCH-003 contracts).
- **Gaps G1–G6** (file/line in ORCH-011 §6): G1 supervision probe targets
  encode the old layout (4 agents permanently UNREACHABLE in
  `/api/agents/status` while alive elsewhere — IntelX/Futuris on Server 2,
  Sentinel on Server 1, VyralX on AWS); G2 Memora event consumer fails at
  the cursor every observed cycle; G3 autonomy ON in production needs a
  coordinator decision (no worker toggle); G4 Stratex/Forge probe flapping
  (known REL-023 pattern); G5 VyralX AWS leg is a supervision blind spot;
  G6 two supervision surfaces disagree (agent-watch log 10/10 healthy vs
  `/api/agents/status` degraded).
- **Deployed code byte-identical to main** for the four supervision-relevant
  files (sha256, ORCH-011 §5).

Interim live state since ORCH-011 (from TASK-CTX-004 live proof, Muse 13,
2026-11-23 06:36 IST, comment 7089047929): S2 checkout main `491a63e9`;
Cortex restarted 05:25:17 IST (PID 599993); supervisor ~06:41 IST: 148
cycles, 0 errors, `last_unconfigured: []`, `ai_universe` HEALTHY 147/148;
`ratio_check` live in `GET /v1/friday/self_healing`, streak 0, signal
present.

## 2. Method

1. **Code defaults on main** (this branch base): re-read
   `FRIDAY/src/friday/core/config.py` (autonomy defaults, env prefix),
   `FRIDAY/src/friday/autonomous/controller.py` (toggle, `get_status()`),
   `FRIDAY/src/friday/api/server.py` (FRD-023 boot-arm, supervision
   endpoints, Memora consumer loop), `FRIDAY/src/friday/ecosystem/fleet_client.py`
   (probe targets, budgets). Record file:line for every default.
2. **Live re-probe, read-only, via the bridge** (Server 1 + Server 2):
   `GET /friday/api/autonomous/status` (twice, separated in time),
   `GET /friday/api/agents/supervision`, `GET /friday/api/agents/status`,
   per-agent `/health` + `/ready` at the **running** copies (6/4 layout:
   IntelX/Futuris Server 2, Sentinel Server 1, VyralX AWS — not the masked
   sleeping copies), Cortex supervisor state on Server 2 (cycles, errors,
   `last_unconfigured`), Memora consumer `last_result`, daemon heartbeat
   lines in the FRIDAY journal.
3. **Guard tests re-run** on the Server 1 venv:
   `tests/test_fleet_supervision_loop_contracts.py` (targeted run only —
   the bridge `run_workspace_test` path arg runs the whole repo).
4. **Drift triage.** Code-default vs live-env drift found here is fixed
   in this PR where the fix is code (probe targets, defaults, docs).
   Anything that would change a running service's mode, flag, or
   supervision posture — above all the G3 autonomy-ON question — is
   reported to Muse for a decision, not toggled by this worker.
5. **Per-agent evidence** filed in §4 below with timestamps; any agent
   presenting as ok while degraded is flagged with the exact degraded
   capability (REL-004 contract).

## 3. First step (this commit)

Design + baseline doc only. Live probe follows in this run; evidence lands
in §4 and in the work PR as it is captured.

## 4. Live evidence (to be filled)

- [ ] `/api/autonomous/status` (×2) — mode, full-access, daemon state
- [ ] `/api/agents/supervision` + `/api/agents/status` — loop freshness, counts
- [ ] Per-agent `/health` + `/ready` at running copies (10 agents)
- [ ] Cortex supervisor (S2) — cycles, errors, `last_unconfigured`
- [ ] Memora event consumer — `last_result`
- [ ] Guard tests re-run (S1 venv) — pass count, duration
- [ ] Deployed-code sha256 vs main (supervision-relevant files)

## 5. Acceptance

- [ ] Autonomous-controller + fleet-supervision state re-probed live across
      all agents, with a recorded verdict — this document.
- [ ] Code defaults verified against live env; every drift found is either
      fixed in this PR (code) or filed as a gap with file/line and a
      coordinator decision requested.
- [ ] ORCH-011 gaps G1–G6 each re-checked: closed with evidence, or carried
      with fresh evidence.
- [ ] Per-agent state evidence filed with timestamps.
- [ ] No service mode, flag, or supervision posture changed without
      coordinator direction; all probes read-only unless a code fix lands
      in this PR.

— Muse 13
