# TASK-SEN-034 — Checkpoint 1: scoping + gap verified

- **Task:** TASK-SEN-034 — Sentinel: compromised-laptop OPSEC checklist in the owner-device hygiene set
- **Claimed:** 2026-11-25 ~22:55 IST by Muse 12 (hub #1483; queue head after SEN-031 merged, EARN-005 head blocked on product identity)
- **Branch:** `muse12/task-sen-034-compromised-laptop-checklist` @ main `a759a031`
- **Board:** AVAILABLE → CLAIMED rides in this work PR

## Source (verified first-hand on main a759a031)

- Sentinel package **SE-04**, item **DXrixKzEVza** — a sectioned "CYBER SECURITY // OPSEC"
  infographic: "COMPROMISED LAPTOP? HOW TO SPOT A MACHINE THAT MAY NO LONGER BE CLEAN".
- The infographic's five sections are already implemented as a runnable tool under
  **TASK-IG2-SEN-05**: `Sentinel/app/services/compromised_host_triage.py`
  (01 warning signs, 02 system indicators, 03 network & account flags,
  04 quick triage sequence, 05 escalation / next steps; weighted scoring with hard signs;
  verdicts NO_SIGNS / MONITOR / SUSPICIOUS / LIKELY_COMPROMISED).
- Tests exist: `Sentinel/tests/test_ig2_sen_compromised_host_triage.py`.
  Referenced in SEN-032 production-verify evidence
  (`docs/collaboration/TASK-SEN-032-PRODUCTION-VERIFY-IG2-SEN-02-06.md`) and
  `Sentinel/scripts/sen032_live_probes.py`.

## Gap verified first-hand (this run, main a759a031)

The checklist is **not** in the owner-device hygiene set:

- `Sentinel/sentinel/modules/endpoint/device_posture.py` (429 lines) contains no
  reference to the triage checklist — grep for `triage|compromised` finds only the
  word "hygiene" in comments (Private DNS + resolver hygiene, SEN-030 DP-012/DP-013).
- `Sentinel/skills/defensive/` (manifest + 9 skill dirs: containing-active-incident,
  defending-llm-prompt-injection, detecting-ssh-brute-force, hardening-linux-fleet-hosts,
  reviewing-iam-least-privilege, threat-hunting-fleet-logs, tls-certificate-hygiene,
  triaging-soc-alerts, triaging-vulnerabilities, verifying-backup-integrity) has no
  compromised-laptop / compromised-host checklist skill.

So the runnable tool exists but is not wired into the hygiene set the board acceptance
names. That wiring is the work.

## Plan

1. Add the checklist to the hygiene set in the source's own order and wording:
   the five sections as a runnable step-by-step checklist tool (posture-rule surface
   and/or defensive skill — form to be confirmed against the hygiene set's own
   structure; the tool's step text is already the source's wording).
2. Walk it through once in a drill (owner-device scenario, observations in, verdict
   + action plan out), and file the drill evidence.
3. Done = checklist live in the hygiene set + drill walked through once.

## Queue behind

- **EARN-005 (head, skipped):** still blocked on product identity — the $19 product
  cannot be identified from board, repo, or any coordinator watch through WATCH108;
  owner answer owed since 2026-11-24 ~12:20 IST, none arrived. No copy written.
- **SEN-034 is the head now** (this claim). No further queue items assigned to Muse 12;
  WATCH108 notes the top-up rides in the next coordinator board PR.

— Muse 12
