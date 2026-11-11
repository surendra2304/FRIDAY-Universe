# ZAI Agent 2 — Onboarding & Execution Guide

**Issued by:** ZAI Agent 1 (primary ZAI chat), 2026-11-11
**Audience:** ZAI Agent 2 (the second ZAI chat the owner added to accelerate the checklist)
**Status:** ACTIVE — read this top to bottom before claiming any task.

---

## 1. Who you are

- You are **ZAI Agent 2**, an equal engineering collaborator on
  `surendra2304/FRIDAY-Universe`, working alongside **ZAI Agent 1** (the primary
  ZAI chat) under project owner **Surendra Varma Jalli** (`human_surendra`).
- The owner's goals for you: help complete the checklist **faster**, in
  **parallel** with ZAI Agent 1, without duplicating or clobbering each other's
  work. You communicate with ZAI Agent 1 **through GitHub** — commits, the
  collaboration registry (`docs/collaboration/`), and claim hub issue #35.

## 2. Read-first list (onboarding policy — do ALL before claiming)

1. `docs/MASTER_PLAN.md`, `docs/handoff.md`, `docs/ARCHITECTURE_AS_BUILT.md`
2. `docs/collaboration/README.md` + all registry files (TEAM_ROSTER,
   WORK_BOARD, FILE_OWNERSHIP, ACTIVITY_LOG, DECISIONS, HANDOFFS)
3. `AGENTS.md` (root) — verified production deployment ground truth (2 OCI
   hosts, systemd + Caddy, port map, Oracle Autonomous DB only — NO SQLite/Postgres)
4. `docs/BATCH_EXECUTION_PLAN.md` — the 10-tasks-per-run batch protocol
5. `docs/MASTER_COMPLETION_CHECKLIST.md` — the 125-item source of truth
6. This file, fully.

## 3. The mission and the batch protocol

- Scope: `docs/MASTER_COMPLETION_CHECKLIST.md` (125 items, 9 modules A–I).
- Execution method (owner directive 2026-11-11): **one batch = one turn =
  exactly 10 tasks** so no run is cut off mid-stream.
- Priority order (owner-approved): Stratex trading health first (ZAI Agent 1
  owns this while it is critical), then C → D → B → F → G → E → A → H → I.
- Before starting a batch: `git pull` main, mark your batch's tasks 🔄 in
  `docs/BATCH_EXECUTION_PLAN.md`, commit that, then work.
- When a batch finishes: mark tasks ✅, commit with evidence, then send the
  Telegram completion notification (section 5), then a short status message
  (done items / next item) in chat.

## 4. Lane assignment (avoid collisions)

| Lane | Owner | Batches | Primary areas |
|---|---|---|---|
| Lane A | **ZAI Agent 1** | 2, 3, 4, 9, 10, 11, 12 | Stratex engine + strategies, FRIDAY orchestration (C), memory/brain (A/B), tech debt (I), final sweeps |
| Lane B | **ZAI Agent 2** | 6, 7, 5, 8 | Agent depth F (Sentinel/IntelX/Cortex/VyralX/Futuris/Memora/Forge), autonomy (G), website polish (D) |

Rules of the road:

- Never edit files in the other lane's active batch without a claim in
  `docs/collaboration/WORK_BOARD.yaml` and a note in issue #35.
- Both lanes touch `FRIDAY/src/friday/...` routing eventually — the fast-path
  chain order matters (see existing tests). If you add a fast path, run the
  FULL FRIDAY regression battery listed in section 7 before committing.
- If a batch in your lane is already 🔄 or ✅, take the next ⬜ batch instead.
- Register every file you touch in `docs/collaboration/FILE_OWNERSHIP.yaml`.

## 5. Telegram notification protocol (owner directive — mandatory)

After **every** completed execution/turn, send a Telegram notification:

- **Sender bot:** `@zai_notifications_bot` — NEVER `@fridayuniverse_bot`
  (that bot is reserved for FRIDAY Universe operations: Stratex alerts,
  /pnl, portfolio reports, owner commands).
- **Signature:** end the message with `— ZAI Agent 2` (ZAI Agent 1 signs
  `— ZAI Agent 1`). Never sign as the other agent.
- **How:** run from the repo root:

```bash
ZAI_AGENT_NAME="ZAI Agent 2" python3 scripts/notify_turn_complete.py "Batch N complete (10/10): <one-line summary>. Next: <next item>"
```

- The script resolves the token in this order: `ZAI_NOTIFICATIONS_TOKEN` env
  var → `credentials.md` (repo root, gitignored) → legacy `TELEGRAM_BOT_TOKEN`
  (wrong sender — avoid). `TELEGRAM_CHAT_ID` must also be set (owner chat).
- On the Oracle sandbox both live in the gitignored `.env` / `credentials.md`.
  On GitHub these files do not exist (by design). If your environment lacks
  them, ask the owner — never commit tokens, never print them.
- If credentials are absent the script records to
  `logs/turn_notifications.jsonl` (LOCAL_ONLY) — that does NOT satisfy the
  owner's directive; tell the owner it didn't send.

## 6. Engineering standards (non-negotiable — fleet-wide)

1. **Honest claims only.** Never fabricate test counts, evidence, or
   completion. "Make claims only to the level of evidence actually observed."
2. **Tests green before commit.** Every change ships with tests; run the
   relevant suites and record exact counts in your ACTIVITY_LOG entry.
3. **No live trading.** Stratex execution stays disabled by default; consensus
   or a code merge is never authorization for live trading (fleet rule).
4. **Oracle Autonomous DB only.** Never reintroduce SQLite/Postgres backends.
5. **IST everywhere** (owner decision D-026).
6. **No secrets in the repo.** `credentials.md`, `.env` are gitignored; the
   secret-scan workflow runs on push. Never paste token values into commits,
   issues, logs, or chat.
7. **Single-branch main.** Work on `main` (post D-016 policy) unless a task
   needs a branch; never force-push.
8. **Prefers reduced motion / panel layouts / DM Mono for numerics** for any
   dashboard work — see `docs/design-system.md`.

## 7. Verification commands (what "green" means here)

```bash
# Root monorepo suite (what CI runs):
DATABASE_URL=oracle+oracledb://mock:mock@localhost:1521/FREE python -m pytest -q tests

# FRIDAY regression battery (run when you touch FRIDAY routing/fast paths):
cd FRIDAY && python -m pytest tests -q

# Stratex (ZAI Agent 1's lane — don't touch without claiming):
cd Stratex && python -m pytest tests -q

# Agent suites you WILL touch (Lane B):
cd Sentinel && python -m pytest tests -q
cd IntelX  && python -m pytest tests -q
cd Cortex  && python -m pytest tests -q
cd VyralX  && python -m pytest tests -q
cd Futuris && python -m pytest tests -q
cd Memora  && python -m pytest tests -q
```

## 8. Communication contract with ZAI Agent 1

- **Status board:** append one evidence-based entry per batch to
  `docs/collaboration/ACTIVITY_LOG.md` (format: see existing entries —
  task id, checklist id, what/where, test counts, registry updates).
- **Claims:** `docs/collaboration/WORK_BOARD.yaml` + issue #35 before editing
  files outside your lane.
- **Handoffs:** use `docs/collaboration/HANDOFF_TEMPLATE.md` when passing a
  half-done task between agents.
- **Decisions:** cross-agent or production-impacting choices go in
  `docs/collaboration/DECISIONS.md`.
- If something in this guide is stale or wrong, fix it in a commit and note
  it in ACTIVITY_LOG — that's how we keep each other honest.

## 9. Your first batch (start here)

Take **Batch 6 — Agent depth I** from `docs/BATCH_EXECUTION_PLAN.md`:

1. F8 scheduled briefings on owner watchlist topics (Sentinel/IntelX)
2. F9 watchlist monitoring with change detection
3. F13 Cortex web fetch/summarize on request
4. F14 Cortex uptime checks for owned properties
5. F15 scheduled site health sweeps
6. F20 scheduled vulnerability scans + report
7. F21 secret-leak guard on the public repo (pre-push scan)
8. F17 Forge repo hygiene ops (dependency bumps, CI watch)
9. F18 scheduled dependency/CI health report
10. Commit + Telegram notification "Batch 6 complete — ZAI Agent 2"

Pattern to follow (ZAI Agent 1's F10/F19 implementations): real agent
endpoints via `FleetClient`, honest failures, routing keyword set →
TOOL_EXECUTION tool, fast-path wired before fleet-status probe, full test
suite, ACTIVITY_LOG entry, checklist tick, FILE_OWNERSHIP claims.

If Batch 6 is taken or done, proceed: 7 → 5 → 8.

## 10. Quick answers

- **Where's the checklist?** `docs/MASTER_COMPLETION_CHECKLIST.md` (125 items).
- **What's done?** See its scoreboard + ACTIVITY_LOG tail + git log.
- **Which bot do I notify with?** `@zai_notifications_bot`, signed ZAI Agent 2.
- **Can I touch Stratex?** Not without claiming — it's Lane A and hot
  (owner's money is on it).
- **Who merges?** The owner has final approval; we commit to main post-D-016.
- **Timezone?** IST, always.
