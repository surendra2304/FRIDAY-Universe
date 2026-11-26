# TASK-FRG-025 — CHECKPOINT 2 (read-only leg: IG2 deliverables located + CI gap + intake) — Muse 20 — 2026-11-25 ~18:35 IST

## Claim of record
- Hub comment 7160470331 (~16:31 IST). Queue: FRG-025 → STR-065 → SEN-033.
- Checkpoint 1 filed 17:32 IST (commit 556278e8, hub 7161833409). This run is the
  hourly self-check repair leg: ~1 h after checkpoint 1 with the named next
  read-only leg undone, the leg is done here instead of reporting the stall.
- Branch `muse20/task-frg-025` verified head `556278e8` at run start (unchanged,
  sane). Main has moved `e0373ced` → `f216e1bae` since checkpoint 1; rebase is
  owed before the work PR opens (routine, not a block).

## IG2 deliverables — ALL LOCATED, present on main `f216e1bae` (verified first-hand)
Landing PRs re-verified merged; every file fetched via the contents API
(`ref=main`) with size + blob sha:

| Item | Landing PR | Deliverable files on main |
|---|---|---|
| IG2-FRG-01 | #674 (merge ee16ef05) | `Forge/AGENT_GUIDELINES.md` 2,944 B sha 9e5c418e; `Forge/forge_upgrade/coding_principles.py` 4,761 B sha 865f6c9a; `Forge/tests/test_ig2_frg01_karpathy_principles.py` 2,858 B sha 02b9b1c3 |
| IG2-FRG-02 | #676 (merge d1dc1df1) | `Forge/docs/CODE_GRAPH.md` 2,044 B sha a01f6f37; `Forge/forge_upgrade/code_graph.py` 7,562 B sha e1670035; `Forge/tests/test_ig2_frg02_code_graph.py` 3,482 B sha afc06aae |
| IG2-FRG-03 | #681 (merge 62f7df13) | `Forge/docs/OCR_REVIEW.md` 1,819 B sha 1819a4b3; `Forge/forge_upgrade/ocr_review.py` 6,176 B sha 3ba75010; `Forge/tests/test_ig2_frg03_ocr_review.py` 3,469 B sha a6ea332f |
| IG2-FRG-04 | #687 (merge aee4d432) | `Forge/forge_upgrade/parallel_download.py` 6,444 B sha 4bd7f2df; `Forge/tests/test_ig2_frg04_parallel_download.py` 4,288 B sha 8bca82ff |

(Shas in the table are the first 8 hex chars of the full 40-hex blob shas
returned by the contents API. Full values on record: OCR_REVIEW.md
`1819a4b37d7bf6343ceb9f7e8c14e017623895c3f1`; IG_EVALUATION_NOTES.md
`7b06b633bb4f35a2d9089d4b652eec51a5628303`.)

## IG-FRG-08 notes file — presence re-check DONE
`Forge/docs/IG_EVALUATION_NOTES.md` present on main: 7,975 B, sha
`7b06b633bb4f35a2d9089d4b652eec51a5628303`. Read in full. The two follow-ups
are now quoted exactly from the doc (checkpoint 1 had them only as a summary):
- (a) §5.1 — **live preview endpoint** serving a completed build's static files
  read-only, **bound to the build's verification manifest** (FRG-011 snapshot
  binding is the mechanism). Proposed as a follow-up task; not built in this wave.
- (b) §3 — **per-agent budget + heartbeat as first-class board fields** for
  long-running build tasks. A board-schema suggestion for the coordinator, not
  a code change here.
Both are coordinator decisions; neither blocks the notes item itself.

## FINDING — five Forge test files have NEVER run in CI (same defect class as REL-068)
Files: `Forge/tests/test_ig2_frg01_karpathy_principles.py`,
`test_ig2_frg02_code_graph.py`, `test_ig2_frg03_ocr_review.py`,
`test_ig2_frg04_parallel_download.py`, `Forge/tests/test_ig_frg07_ig_templates.py`.
Evidence (all first-hand, this run):
- `.github/workflows/friday-universe-ci.yml` read in full (32,796 B): the Forge
  tier-1 job runs exactly three named files —
  `tests/unit/test_tier1_resilience.py`, `tests/unit/test_deep_upgrade_tier1.py`,
  `tests/unit/test_mem031_forge_session_capture.py`. Zero hits for any of the
  five files.
- `.github/workflows/owner-workflows.yml` read in full (17,191 B): the contracts
  job's Forge list is also named `Forge/tests/unit/*.py` files only. Zero hits.
- Code search `Forge/tests` (28 hits): the only workflow referencing it is
  owner-workflows.yml (path filters + the unit list above). No other workflow
  collects these files.
- `scripts/tier1_collection_gate.py` checks a FIXED 21-file tier-1 list; for
  Forge it lists only the two unit files above — so the gate passes while the
  five files stay uncollected. The REL-068 guard is diff-scoped (only checks
  test files the PR itself touches); the IG2 PRs merged 2026-11-16, before the
  guard covered this shape.
- **Tests themselves are green:** all four IG2 modules + tests are stdlib-only;
  run locally in a scratch venv (files fetched from main): **32/32 passed**.
  One first-attempt failure was my scratch layout (missing
  `AGENT_GUIDELINES.md` at the resolved Forge root) — copied it in and the
  suite went 32/32. The IG-FRG-07 test was not run locally (imports
  `Forge/app/templates`, heavier tree); its CI collection is the same gap.
- **Fix rides in the FRG-025 work PR** (same pattern as STR-068's
  owner-workflows.yml fix and SEN-030's tier-1 registration): add the five
  files to the Forge tier-1 pytest invocation in `friday-universe-ci.yml`.

## Forge intake / delegate surface — read first-hand (shapes the live legs)
- `Forge/app/api/delegate.py` (41,081 B): `delegate_router`, prefix `/forge`.
  `POST /forge/delegate` takes `TaskEnvelopeModel` — `task_id`,
  `source_agent`, `target_agent` (default `forge`), `action` (default `build`),
  `payload`, `priority`, `trace_id` — and returns `TaskResultModel` with
  `status`, `result`, `summary`, `verification_manifest`, and a `receipt`
  (requested action + target + non-empty evidence). Status:
  `GET /forge/tasks/{task_id}/status`; cancel: `POST /forge/tasks/{task_id}/cancel`.
- `Forge/app/api/routes.py`: `GET /health`, `GET /projects`, `POST /ask-inference`,
  `POST /tasks/{task_id}/cancel`, `GET /runs/{run_id}`.
- Gateway per `Forge/README.md`: `https://friday-universe.duckdns.org/forge/*`;
  private mesh `http://forge:8000`.
- **Gap recorded:** `render_goal` exists ONLY in `Forge/app/templates/ig_templates.py`
  + its test (code search: 2 hits). The IG-FRG-07 board next_action — expose
  templates at Forge intake (template name + project name → render_goal → build)
  — is NOT wired: no intake route references `ig_templates`. The live leg can
  still run by carrying the template-rendered goal text as the delegate
  payload; the wiring itself is a follow-up, not a live-leg blocker.

## Live-leg shape per item (draft — executes only after Muse's ruling)
One real build task per item through Forge via `POST /forge/delegate`, output
actually used by another agent in production, evidence = verification manifest
+ receipt + consumer confirmation:
- IG-FRG-07: saas-stack build from the template pack (rendered goal as payload).
- IG2-FRG-01: build run with the Karpathy-principles guidance in the loop.
- IG2-FRG-02: build run through the code-graph step; graph produced + consumed.
- IG2-FRG-03: build whose PR review passes through the OCR review supplement.
- IG2-FRG-04: build using the parallel range-chunk downloader for a large fetch.
- IG-FRG-08: notes-only — no live leg until the coordinator decides (a)/(b) above.

## Live legs — STILL HELD, ruling owed from Muse
No live step taken; no fleet move; no Forge dispatch attempted.
- Owner stop order still holds live probe/deploy legs fleet-wide (no lift in
  WATCH098 7161941236 / WATCH099 7162851838, read in full this run).
- Owed: (a) ruling naming the live Forge host, (b) clearance/grant under the
  stop order, (c) one real build task + consuming agent per item.
- Fleet context (not mine to fix): CD broken on both servers per WATCH098
  (S1 dirty tree; S2 `.git/objects` permissions) — fix needs the owner's word.
- Carried: Muse's ruling on TASK-STR-085 still owed (duplicate of
  TASK-IG-STR-06; no ruling in WATCH098/099). No new direction naming Muse 20
  in either watch; WATCH099 notes this task's checkpoint 1.

## Next legs
1. Request the live-leg ruling from Muse on the hub (this checkpoint's post).
2. Live legs per item once ruled; evidence doc + board flip AVAILABLE → IN_REVIEW
   ride in the single work PR when DONE or genuinely BLOCKED (owner rule 1),
   together with the CI-collection fix above.
3. Rebase branch onto current main before the work PR.

## Five states
Implemented NO (read-only scoping; no repo edits) / tested PARTIAL (IG2 tests
32/32 green locally; never run in CI — gap filed above) / merged NO /
deployed NO / production-verified NO.

## Queue / schedules / usage
- Queue: FRG-025 (head) → STR-065 → SEN-033.
- Work-request task stays cancelled while FRG-025 is claimed (guard; verified
  absent via cron.list this run). Hourly self-check + weekly reset armed.
- Usage: 14% of free weekly limit (verified this run via subscription-status;
  reset Dec 1, 11:00 AM IST). Additional tokens 0% used. Free usage remains —
  no wrap-up.
