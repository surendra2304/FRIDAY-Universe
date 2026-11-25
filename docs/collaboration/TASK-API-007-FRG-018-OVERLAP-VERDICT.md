# TASK-API-007 / FRG-018 overlap verdict — NOT PROVEN

Owner: Muse 15. Branch: `muse15/task-api-001-forge-task-execute` (work PR #1908).
Assignment: coordinator WATCH124 (hub #1483 comment 7177205785, 2026-11-26 ~04:39 IST),
queue pos 2 after FRD-043 (HELD). Claim: hub #1483 comment 7177725816, ~05:03 IST.
Board verified on main `a0a45bdf`: API-007 AVAILABLE / owner muse_18; FRG-018 MERGED / pr 1494.
Both source docs read first-hand from main `a0a45bdf` this run:
`docs/collaboration/TASK-FRG-018-FORGE-DISPATCH-ENDPOINT.md` (139 lines) and
`docs/collaboration/TASK-API-007-FORGE-TASK-EXECUTE.md` (98 lines).

## 1. The question as assigned

Read FRG-018's live proof (PR #1494) against API-007 checkpoint-1 evidence
(PR #1626) and determine whether API-007's remaining live-dispatch leg is
already proven by FRG-018. Verdict is evidence only — no change to M18's claim,
branch, or live leg; the coordinator rules on any close.

## 2. What FRG-018 proved live (PR #1494, MERGED)

Muse 4, S1 probe 2026-11-23 ~16:34–16:38 IST, main `958cc133` (FRG-018 doc §2–§4):

- `GET /openapi.json` → 200, 193 paths, **`POST /v1/task/execute` present**.
- `POST /v1/task/execute` ping, TaskEnvelopeModel shape → **200 SUCCESS**,
  `target_agent forge`, `engine_status ONLINE`, receipt `AUTHORIZED`.
- Same ping in the dispatch bus's exact wire shape (`source_agent "FRIDAY"`)
  → **200 SUCCESS**. Same ping with no key → **401 `{"error":"unauthorized"}`**.
- FRIDAY–Forge key chain hash-matched (`FRIDAY_FORGE_API_KEY` == Forge's
  `FORGE_API_KEY`, sha256 prefix `52fbca4598a8`): no auth gap on the bus path.
- Self-test real build: `action "build"`, `execute_now true`,
  `source_agent "muse4-selftest"`, tiny Python CLI `greeter` — task
  `task28623112026110614` **COMPLETED 11:10:21Z** (~4 min), status SUCCESS,
  verification manifest **14/14 stages passed**; built CLI re-run from disk
  prints `Hello, Ada!` (rc 0); pytest 1 passed.

FRG-018's own qualification, in its doc and on its board record — this is the
decisive point:

- Doc §4: "Self-test real build (**Muse 4's own verification — NOT the
  acceptance dispatch**) ... this self-test proves the path works, it does not
  satisfy the acceptance."
- Doc §5: "The acceptance's second half is still open: one real task
  dispatched to `POST /v1/task/execute` **by another agent** ... It cannot be
  done by Muse 4 — the dispatcher must be another agent."
- Board `next_action` (on main): "One real task dispatched by another agent
  is owed (FRIDAY-chat path blocked on FRD-038); Muse to direct the dispatch,
  proof rides in a follow-up PR."
- States: production-verified PARTIAL — "endpoint + auth proven live; the one
  real task dispatched by another agent is owed (§5)."

FRG-018's acceptance reads: "A task-execute endpoint exists in Forge, one real
task dispatched to it by another agent executes end-to-end, evidence filed with
the live response." It MERGED with the second half explicitly still owed.

## 3. What API-007 checkpoint 1 established (PR #1626)

Muse 11, 2026-11-24 ~10:30 IST, main `bc303ea0` (API-007 doc §1–§5):

- Route exists in code: `task_contract_router` in
  `Forge/app/api/delegate.py:915-926`, mounted `Forge/app/main.py:444`,
  shipped by FRG-002 (PR #1401, merge `fd4fb046`); contract tests in CI.
- Live proof cited from FRG-018 (ping, auth, self-test build — §2 above).
- Remaining leg, identical to FRG-018's owed item: one real task executed
  end-to-end through `POST /v1/task/execute` **dispatched by another agent**,
  with the live response filed. Blocked that run on bridge transport down +
  FRIDAY-chat 401 gate (FRD-038 fix merged, undeployed; FRD-042 owns deploy).
- Overlap flag (§5): "API-007 and FRG-018 now converge on the same single
  owed item (the other-agent dispatch). Coordinator call owed: either API-007
  carries that dispatch as its checkpoint 2, or API-007 closes as a duplicate
  of FRG-018's remaining leg."

## 4. What my repo-leg verification adds (PR #1908)

Muse 15, 2026-11-26 ~04:35 IST, base main `bf5a08b7` — mounted-app proof,
no live dispatch: 2 new tests booting the real `create_app()` (bus wire shape
ping → 200/SUCCESS/receipt; build `plan_only` → PLANNED, `plan_stages` 2, no
receipt); 4/4 local, ruff clean, CI fully green on the PR (8 success +
2 skipped, 0 failed). It re-confirms the route in the assembled app; it adds
no live dispatch evidence and does not change the verdict.

## 5. Verdict: NOT PROVEN

**FRG-018's live proof does not already prove API-007's remaining
live-dispatch leg.** The proof covers route existence, endpoint
executability, and auth — but its only live build was dispatched by the task
owner itself (`source_agent "muse4-selftest"`), which FRG-018's own doc
(§4, §5) and board `next_action` state does **not** satisfy the
by-another-agent acceptance leg. That leg is still owed in both records, and
it is **one shared owed item, not two**: a single dispatch by another agent,
with the live response filed, satisfies API-007's acceptance and FRG-018's
`next_action` at once. Nothing in PR #1494 shows a dispatch by another agent,
and nothing in PR #1626 or PR #1908 adds one.

## 6. Recommendation to the coordinator (evidence only — coordinator rules)

- Keep the dispatch as API-007's live leg with Muse 18 (already holding it);
  when one dispatch lands with the live response filed, it closes the owed
  item for both records.
- Do **not** close API-007 as a duplicate on this evidence: the owed item
  itself is still open, and closing API-007 would leave the dispatch tracked
  only in FRG-018's `next_action`, which already sat owed since 2026-11-23.
- The alternative M11 flagged — close API-007 as a duplicate and let the
  dispatch ride in FRG-018's follow-up PR — remains available; it is the
  coordinator's call, not this verdict's.

## 7. States (verdict task)

- Implemented: YES — endpoint by FRG-002 (PR #1401, merge `fd4fb046`); no new code.
- Tested: YES — contract tests in CI + FRG-018 live proof, cited first-hand.
- Merged: NO — work PR #1908 open (verdict doc + board evidence line ride in it).
- Deployed: YES (already) — live on S1 since the FRG-002 era, per FRG-018's
  S1 probe; **not re-probed this run** (verdict is a document-evidence
  comparison, per the assignment).
- Production-verified: PARTIAL — endpoint + auth proven live; the one real
  task dispatched by another agent is owed.

## 8. What would close the owed leg

One real task (a build, not a ping) dispatched to `POST /v1/task/execute`
by an agent other than the task owner — FRIDAY via her bus once FRD-038/FRD-042
lands, or a worker Muse via the bridge — executing end-to-end, with the live
response (status, forge task id, manifest, artifacts) filed. The FRIDAY-chat
path was 0/3 live runs at last check (Muse 15, 2026-11-26 ~04:35 IST); the
bridge path needs a live transport check at dispatch time.

— Muse 15
