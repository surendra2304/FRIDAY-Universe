# TASK-MEM-017 — Cross-session memory recall through FRIDAY: live-run prep (checkpoint 1)

**Date:** 2026-11-26 ~04:2x IST (Muse TP3)
**Status:** PREPPED, repo-side only. Zero live runs attempted (0/3). Live leg gated.
**Branch:** `musetp3/task-mem-017-cross-session-recall`
**Board:** TASK-MEM-017 AVAILABLE / owner muse_tp3 / P2 (verified on main `bf5a08b7`, board blob `49eaef16`).

## 1. Acceptance (from board)

Three consecutive live runs: FRIDAY recalls across sessions via Memora with
the recalled content cited in the answer, each run recorded with its trace;
a wrong or fabricated recall resets the count.

## 2. History that shapes this run (verified)

- **Run 1 FAILED honestly** (board evidence): FRIDAY → Memora write 401,
  root cause filed (hub 7083191831); self-check 7083846733, 0/3, no retry.
- **The 401 was later root-caused as the FRIDAY web-chat control gate, not
  Memora** (`docs/collaboration/TASK-FRD-038-WEBCHAT-401-DIAGNOSIS.md`):
  TASK-VAL-007 (commit `1cd77f1d`) restored `_require_control_access` on
  `POST /api/chat`; the keyless Halo console sent no credential, so remote
  chat answered 401. Memora's own 401 fix HOLDS (bridge logs: cursor 200s,
  zero 401s in window).
- **Fix merged:** TASK-FRD-038 MERGED as PR #1535 (merge `8c0ef142`,
  2026-11-23): 8 files — Halo console credential flow
  (`FRIDAY/ui/lib/controlSession.ts`, `ControlGate.tsx`, `wire.ts`) +
  diagnosis doc. Board status MERGED proves code on main only; per owner
  rule 2 it is NOT live proof. Live verification needs the fix deployed to
  Server 1 + owner key pasted once in a browser (key never recorded).
- **Recall path in code:** `FRIDAY/src/friday/memory/memora_client.py`
  (2,477 lines; HMAC-signed requests, sensitive-pattern redaction),
  `FRIDAY/src/friday/memory/cross_session.py` (pattern learning — adjacent,
  not the recall path), Memora API `Memora/apps/api/routers/v1_memories.py`
  + `v1_events.py`. Existing tests: `FRIDAY/tests/test_multiturn_memora_friday.py`,
  `test_memora_recall_guard.py`, `test_fleet_memory_recall.py`.

## 3. Run protocol (each of the 3 runs)

Preconditions (all must hold before run 1; verify, do not assume):

1. FRD-038 fix deployed on Server 1 (FRIDAY.service) — fleet CD currently
   broken + owner stop order in force (WATCH122); deploy needs clearance.
2. Control session established via the Halo console (paste-once key → `fcs1`
   token, 20-min TTL, auto-refresh). Loopback-only checks do NOT prove the
   remote path (FRD-038 diagnosis §4).
3. Memora healthy: `GET /v1/events/cursor?consumer_id=friday-cloud` 200,
   zero 401s in the run window (bridge `oracle_get_logs`).
4. Fresh session boundary per run: seed fact in session A, recall probe in
   session B (new conversation), no in-context leakage of the seeded fact.

Per run, record: seed utterance + timestamp, Memora write trace (memory id),
recall probe, FRIDAY answer with citation, Memora read trace, verdict
(pass / fail / fabricated → count resets). File traces in the work PR.

Failure taxonomy (name the failing layer, never retry blind):

- 401 at `/api/chat` → control gate / session TTL (FRD-038 surface).
- 401/5xx at Memora write/read → Memora auth/service (check HMAC + logs).
- Write OK, recall miss → retrieval/ranking (memora_client + v1 routers).
- Recall present but uncited or fabricated → FAIL, count resets to 0.

## 4. Gates

- Owner stop order in force; no deploy, no service restart, no live chat
  run without Muse clearance on #1483. This prep makes no server change.
- The owner key is pasted by the owner only; TP3 never asks for, receives,
  or records it.
- Completion = 3 consecutive passing live runs with traces in the work PR
  (owner rule 2). Merged code (FRD-038) does not count toward the 3.

## 5. Next

- Repo-side: run-protocol checklist + trace template (this branch);
  read `test_multiturn_memora_friday.py` to align seed/probe phrasing with
  the existing harness.
- Live leg: clearance request stands with this checkpoint.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per owner
  rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 1
