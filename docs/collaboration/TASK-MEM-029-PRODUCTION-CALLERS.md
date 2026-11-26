# TASK-MEM-029 — Memora: production callers for the three shipped-but-never-invoked services

- **Work PR:** #1765 (head `6ca296fb`, branch `muse2/task-mem-029-production-callers`)
- **Claim:** hub #1483 comment 7150521485, 2026-11-25 ~07:50 IST
- **Board:** MEM-029 verified AVAILABLE / owner null on main `72f5a7ae` (board blob
  `067e47f3`, 22,497 lines, verified against the true main blob before editing).
  Branch merged main `242e5de3` before the work commit; board re-verified on the
  new main blob `9d829aad` (22,540 lines) before the flips below.
- **Status:** implemented YES / tested YES / merged NO / deployed NO /
  production-verified NO (see §5).

## 1. The audit gap (verified first-hand)

GAP-LIST.md §2, TASK-MEM-WIRE (IG package ME-02 + ME-D1) audited zero production
callers for three shipped services. Re-verified by code search on main
`72f5a7ae` this run: the only references to `/v1/skills`, `/v1/user-model` and
`/v1/capture` outside Memora itself were the routers, their wiring tests and
`apps/api/main.py`. A mounted router is an address, not a caller — no agent ever
invoked any of the three, so no outcome was ever recorded, no field ever set, no
session ever captured. (The one other hit, `tools/universe_agent_marketplace.py`,
references `/api/v1/skills`, a different marketplace surface, not Memora.)

Note: GAP-LIST.md itself is not in the repo tree (no such path on main); the
task's source line is the board record's citation, and the gap was re-proven by
the search above rather than by reading the list.

## 2. The callers (all in FRIDAY, the production agent)

| Service | Production caller | Trigger |
|---|---|---|
| Skill-learning (TASK-IG2-MEM-02, `SkillLearningService`) | `MemoraClient.report_task_outcome_async` — fans every task outcome out to `POST /v1/skills/outcomes` alongside the existing learn-outcome path; pattern key = task name, success/failure mapped onto the loop's outcome vocabulary | Tool-execution failures (`FRIDAY/src/friday/agent/mixins/tools.py`), deterministic desktop actions + fast-path actions (`mixins/fast_paths.py` ×2), OS directives (`cli/main.py`) |
| User-model (TASK-IG2-MEM-03, `UserModelService`) | `record_owner_correction_async` → `POST /v1/user-model/corrections` from the owner-correction fast path (`api/server.py`, applied corrections only — refused/unconfirmed corrections never become standing rules); `fetch_user_model_render` → `GET /v1/user-model/render` as a third parallel context leg on every turn (`agent/agent.py`) | Owner corrects a fact; every cognitive turn consults the model |
| Session capture (PR #709, `SessionCaptureService`) | `record_interaction` captures every turn as a `POST /v1/capture/events` observation (the choke point — every turn flows through it, no per-call-site wiring); `compress_session` → `POST /v1/capture/compress` at CLI text-loop end and voice-session end | Every recorded turn; session end |

New client surface in `FRIDAY/src/friday/memory/memora_client.py` (+358/−1):
`record_skill_outcome(_async)`, `report_task_outcome_async`,
`update_user_model_field(_async)`, `record_owner_correction(_async)`,
`fetch_user_model_render`, `capture_session_event(_async)`, `compress_session`,
plus a process-stable `session_id` (`friday-<12 hex>` — one process is one
capture session unless a caller passes an explicit id). All writes share one
`_post_json` helper and are fail-soft by the client's standing contract: a dead
Memora is logged at WARNING and reported (`stored/updated/compressed: false` +
reason), never raised into the caller, never changes the turn's own record.
There is no local fallback for these writes — the services live in Memora, so a
missed write is reported as missed, not kept local and silently diverged.

What was deliberately NOT wired: the skill-review gate (`POST
/v1/skills/drafts/{id}/review`, admin-only) — FRIDAY must never activate its
own drafted skill; activation stays the Memora service identity's act. The
background evaluation pass in Memora's lifespan already runs the loop's trigger
pass every 300 s, so recording outcomes is the complete caller contract on the
FRIDAY side; no separate evaluate call is made from FRIDAY.

## 3. Evidenced cycles (repo-side, CI-run)

New suite `FRIDAY/tests/test_mem029_production_callers.py` (21 tests, stub
Memora, no live server) locks:

- **Skill-learning:** `record_skill_outcome` POSTs the router's exact
  `OutcomeRequest` shape (incl. the `corrected` + correction-text form); the
  fan-out posts BOTH `/v1/memories/learn-outcome` and `/v1/skills/outcomes`
  for one event, with pattern key = task name and failure mapping (incl.
  `detail` falling back to `error_log`).
- **User-model:** field PUT and correction POST payloads exact; render returns
  the profile string, and returns `""` when nothing is recorded yet
  ("nothing assumed" is never injected into a prompt) or remote is off.
- **Session capture:** `record_interaction` captures the same turn (session
  id = the client's process id, kind `observation`, sanitized content),
  exactly once, on the remote-success path AND the remote-failure path; a
  capture miss leaves the turn's result unchanged; `compress_session` POSTs
  the process session id.
- **Fail-soft:** every new write reports `stored/updated/compressed: false` +
  reason (e.g. `URLError`, `remote_disabled`) instead of raising; remote-off
  posts nothing.

The file is added to the FRIDAY CI step in
`.github/workflows/friday-universe-ci.yml`, so repo CI executes it. Server-side
halves of each cycle are already locked by the existing wiring suites — the
same payload shapes this client sends drive a draft
(`Memora/tests/test_ig2_mem02_skill_wiring.py`), a standing rule at confidence
1.0 (`test_ig2_mem03_user_model_wiring.py`), and a compressed session
(`test_ig2_mem01_capture_wiring.py`).

## 4. Files changed (work PR #1765)

- `FRIDAY/src/friday/memory/memora_client.py` (+358/−1) — client methods, choke point, session id
- `FRIDAY/src/friday/agent/mixins/tools.py` (+3/−1) — fan-out swap (tool failures)
- `FRIDAY/src/friday/agent/mixins/fast_paths.py` (+2/−2) — fan-out swaps (×2)
- `FRIDAY/src/friday/cli/main.py` (+21/−1) — fan-out swap + compress at text-loop and voice-session end
- `FRIDAY/src/friday/agent/agent.py` (+21/−8) — user-model render leg (3rd parallel leg, pool 2→3)
- `FRIDAY/src/friday/api/server.py` (+13/−0) — owner-correction hook (applied only)
- `FRIDAY/tests/test_mem029_production_callers.py` (+374/−0, new) — 21 tests
- `.github/workflows/friday-universe-ci.yml` (+2/−1) — new test file in the FRIDAY CI step
- `docs/collaboration/TASK-MEM-029-PRODUCTION-CALLERS.md` (this file, new)
- `docs/collaboration/WORK_BOARD.yaml` — flips (§6)

Method note: all work through the GitHub REST API only (API-only per the
STR-077 execution-risk precedent). No local clone, no local run/build/test of
repo code; files were read as text via the API and repo CI is the test runner.
A mid-task `/tmp` wipe (2026-11-25 ~02:45 UTC) destroyed the first working
copies; everything was rebuilt from the conversation record under
`~/workspace/mem029-work/` (persistent) and re-verified before committing.

## 5. Five states

- **implemented: YES** — this PR.
- **tested: YES** — 21 new tests, repo CI is the runner; check-runs on the PR
  head are the verdict (see the PR).
- **merged: NO** — peer merge only; never my own PR.
- **deployed: NO** — deploy needs coordinator clearance; live-fleet proof is
  GATED by the standing owner stop order (in force since ~2026-11-24 16:42 IST).
- **production-verified: NO** — no live cycle is claimed. Owed after deploy
  clearance: one live learned skill (3 outcomes → draft via the background
  pass), one live user-model update (owner correction → standing rule), one
  live captured session (events → compress → digest).

## 6. Board flips (ride in this PR)

- **MEM-029 AVAILABLE → IN_REVIEW** (owner `muse_2`, branch
  `muse2/task-mem-029-production-callers`, pr 1765). Note: the assignment brief
  said CLAIMED, but no claim PR exists for this task (claim was hub comment
  only), so the single work PR carries the flip straight to IN_REVIEW — the
  state every prior work PR used at open (FRD-041, INF-030, VOI-032).
- **INF-030 IN_REVIEW → MERGED** (work PR #1620, merge `3db55adf`,
  2026-11-24 10:01 IST, by Surendra).
- **VOI-032 IN_REVIEW → MERGED** (work PR #1630, merge `421fee87`,
  2026-11-24 14:27 IST, by Surendra).
- **VOI-036 CLAIMED → AVAILABLE** (owner null, branch null — released
  2026-11-24 22:40 IST per coordinator ruling 7137935600; re-pullable if the
  freeze lifts and run 21 is sequenced).

All four old lines were verified against the true main board blob (`9d829aad`,
22,540 lines, main `242e5de3`) before editing — exact-match only. STR-077 and
REL-069 untouched per the assignment (STR-077 VOID, REL-069 already MERGED).

— Muse 2
