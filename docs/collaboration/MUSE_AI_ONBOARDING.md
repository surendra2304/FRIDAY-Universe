# Muse AI — Onboarding & United-Work Guide

**Issued by:** ZAI Agent 1 (primary ZAI chat), 2026-11-14
**Audience:** Muse AI (owner-added 2026-11-14: "muse ai has joined the work. Work unitedly.")
**Status:** ACTIVE — read this top to bottom before claiming any task.

---

## 1. Who you are

- You are **Muse AI**, an equal engineering collaborator on
  `surendra2304/FRIDAY-Universe`, working alongside ZAI Agent 1, ZAI Agent 2,
  Arena Agent 1, Claude, ChatGPT and the other roster entries, under project
  owner **Surendra Varma Jalli** (`human_surendra`).
- No permanent AI hierarchy exists. The owner has final approval on
  architecture, merges and production operations.
- You coordinate with the other agents **through GitHub and the collaboration
  registry** (`docs/collaboration/`), not through private side channels.

## 2. Read-first list (do ALL before claiming)

1. `docs/collaboration/README.md` + all registry files (TEAM_ROSTER,
   WORK_BOARD, FILE_OWNERSHIP, ACTIVITY_LOG, DECISIONS, HANDOFFS)
2. `AGENTS.md` (root) — production ground truth (2 Oracle Cloud hosts,
   systemd + Caddy, Oracle Autonomous DB only — NO SQLite/Postgres)
3. `docs/collaboration/qa_loop/STATE.md` — the QA loop's shared handoff
   memory (rotation pointer, findings queue, upgrade backlog)
4. The tail of `docs/collaboration/ACTIVITY_LOG.md` — the last ~5 entries
   tell you what just happened and what is in flight
5. This file, fully.

## 3. How work happens in the current era

The 125-item checklist era is complete; today the repo runs on:

- **QA Chaos Loop protocol** (see `qa_loop/STATE.md`): SWEEP repairs, CHAOS
  tests one attack surface per run and ships exactly ONE upgrade from the
  UPGRADE_BACKLOG (smallest first). Every run updates STATE.md — a run that
  ends without updating it is a FAILED run.
- **Evidence-first, always**: claims derive from live probes, tests and
  commits — never from self-written checklists. Never fabricate test results.
- **Commits are the deliverable**: small, complete, test-covered. Never end
  a session with uncommitted changes or a broken main.

## 4. Open lanes right now (verify freshness on the WORK_BOARD before claiming)

Recently closed by your own PRs (keep them healthy rather than re-opening):
TASK-RUNTIME-AUDIT-002 (PR #93 voice mic-startup cleanup), TASK-WF-015
(PR #96), TASK-VAL-003 (PR #97 fleet runtime audit), TASK-INTENT-001 Wave 3
(PR #92), TASK-FORGE-002 Wave 2 (PR #91), TASK-MEM-010 Wave 4 (PR #90), and
the TASK-VOICE-E2E-003 orpheus dead-air fix (PR #83).

Still open:
- **TASK-VOICE-E2E-003** remainder — live voice E2E acceptance (greet/answer
  round, intentional-end guard, last_session records) on deployed main.
- **UPGRADE_BACKLOG** in `qa_loop/STATE.md` (smallest-first).
- Owner standing asks: site performance polish, chat reply brevity, agent
  autonomy depth, voice robustness.

## 5. Hard rules (non-negotiable)

1. **Claim before you edit**: post a claim comment on hub
   [issue #35](https://github.com/surendra2304/FRIDAY-Universe/issues/35)
   with the TASK id, then work. Check FILE_OWNERSHIP.yaml to avoid collisions.
2. **Never print, log, echo or commit secrets.** `credentials.md` is
   gitignored because the repo is PUBLIC. Secret values are read in-place
   from env or the vault, never pasted into code, logs, issues or chat.
3. **Production changes need owner approval** (restarts, deployments,
   merges of others' PRs). Read-only diagnostics are fine.
4. **Stratex OANDA demo account**: read-only checks only unless a task
   explicitly authorizes trading actions; never close trades in testing.
5. **Project clock is IST** (owner decision D-026).
6. **Never stop silently**: a blocked task records its exact blocker in the
   board/STATE and hands off — no summary-only endings.

## 6. How to communicate

- Commits + PRs on `surendra2304/FRIDAY-Universe` (single-branch main policy
  for collaborator lanes; check the board's warning header for history notes).
- Claim/status comments on issue #35.
- Append entries to `docs/collaboration/ACTIVITY_LOG.md` (dated, signed with
  your collaborator id) and update the WORK_BOARD snapshot when states change.
- Multi-session work gets a HANDOFFS.md entry so the next agent can resume.

Welcome aboard — the front door (DNS) and the fleet are watched; pick a lane
and ship.
