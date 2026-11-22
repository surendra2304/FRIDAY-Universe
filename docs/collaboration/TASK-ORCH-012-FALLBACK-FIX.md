# TASK-ORCH-012 — Fallback fix: generic fallback loses to candidates naming `required_tools`

- **Task:** ORCH-010 F1 — the generic fallback candidate outranks specific tools (live fetch misroute).
- **Owner:** Muse 4. **Branch:** `muse4/task-orch-012-fallback-fix`. **Work PR:** #1334 (claim PR, carries the implementation).
- **Assignment:** Coordinator pool-7 draft, 2026-11-22 ~11:53 IST (issue #35 comment 7075301485, item 5); coordinator watch 7075432505 (~12:05 IST). Claimed 2026-11-22 ~12:10 IST (issue #35 comment 7075462674; claim PR #1334, head 1eaa3e24).
- **Status:** Implemented + tested. Merged pending Muse. Deployed / production-verified pending merge + FRIDAY restart (coordinator clearance) + P7 `/api/chat` re-probe — see §5.

## 1. The defect (ORCH-010 F1)

`FRIDAY/src/friday/routing/capability_router.py:757` (pre-fix): the tool-less generic
fallback candidate was appended whenever the utterance matched a generic verb
(`write`/`read`/`delete`/`create`/`list`/…), regardless of what else matched.
Candidates are score-sorted at the end, and the fallback scores −9.9 — higher
than every specific tool candidate that was itself negative — so any utterance
matching a specific table AND a generic verb routed to a `TOOL_EXECUTION` with
no tool. Proven by the ORCH-010 S1 probe (cases 8, 33, S1–S4) and live by P7:
`read this page https://example.com` → `TOOL_EXECUTION` score −9.9 instead of
`web_fetch_summarize` (106.0). The page was still fetched only because the
generic LLM loop happened to pick `fetch_webpage_content`. Full proof in
`docs/collaboration/TASK-ORCH-010-ROUTING-REPROBE.md` (§Evidence A/B, Follow-ups F1).

## 2. The fix

`FRIDAY/src/friday/routing/capability_router.py` — the fallback candidate
(step 6) is now only offered when no candidate names a concrete tool:

```python
if self._matches(clean_input, {"write", "read", ...}) and not any(
    c.required_tools for c in candidates
):
```

This is the first of the two proposed fixes in ORCH-010 F1 ("make the fallback
lose to any candidate that names `required_tools`"). No scoring change, no
table change, no fast-path change: the fallback is excluded exactly where a
specific table matched, and is preserved exactly as before where none did
(`click the button` still reaches the fallback at −9.9 — pinned by test).

## 3. Verification (local, fixed code)

Run in a venv (Python 3.12.3, pytest 9.2.0) against the fixed router,
2026-11-22 ~13:12–13:16 IST. Test env vars are the sanctioned pytest-only
ones from `FRIDAY/tests/conftest.py` (`FRIDAY_MEMORY_BACKEND=sqlite`,
`FRIDAY_INTENT_CLASSIFIER=off`).

- **New regression tests** `FRIDAY/tests/test_orch_012_fallback_fix.py` — **10/10
  passed.** Pins the three acceptance phrases (`read this page` →
  `web_fetch_summarize` 106.0; `write me a script` → `forge_code_task`;
  `create a video about` → `vyralx_project`), three further F1 phrases
  (`read the security findings` → `sentinel_security`; `list the agents` →
  `get_fleet_status`; `summarize this article …` → `web_fetch_summarize`),
  the two-table-match case (case 33, winner must still name a tool), and
  fallback preservation (`click the button` → fallback −9.9; `list the files in
  the folder` and a greeting → `DIRECT_REASONING`, unchanged).
- **Full ORCH-010 matrix re-run** (`~/workspace/muse4/task-orch-012/orch010_matrix_check.py`,
  all 36 + 6 cases, expectations copied from the re-probe Evidence A) —
  **42/42 pass.** The six F1 cases (8, 33, S1–S4) now name their specific tool;
  the two F2 cases (13, 34) are unchanged (still `get_fleet_status` — F2 is a
  separate task); every other case keeps its pre-fix winner.
- **Pre-fix control:** with the fix stashed, the matrix is **36/42** — exactly
  the six F1 cases fail, all `tools=None` score −9.9, reproducing ORCH-010.
  The fix was restored after the control run (`git stash pop`, diff intact).
- **Existing routing suites, no regressions:** `test_capability_routing.py` +
  `test_router_word_boundaries.py` + `test_intent_classifier_tier.py` —
  **36 passed.**
- **CI collection:** the new test file is added to the FRIDAY contracts list in
  `.github/workflows/owner-workflows.yml` (after `test_memora_hardening.py`).

## 4. Live state (bridge, Server 1)

Checked 2026-11-22 ~13:13 IST via the FRIDAY-Cloud-Engineering-Bridge
(v1.30.0), read-only:

- S1 `/opt/friday_universe` is at commit `ef42312f` — the same commit ORCH-010
  probed. The live `capability_router.py` still carries the pre-fix fallback
  line (`if self._matches(...)` with no `required_tools` guard).
- `FRIDAY.service` is `active` (MainPID 2076194, NRestarts 1).

So the misroute is still live, as expected: the fix is not deployed. No live
service file was touched and FRIDAY was not restarted — deployment follows the
merge, with coordinator clearance, exactly as the FRD-033 precedent requires.

## 5. What remains

1. **Merge** — Muse reviews/merges PR #1334. CI on the implementation head is
   the gate (see the PR checks).
2. **Deploy** — FRIDAY redeployed/restarted on Server 1 with coordinator
   clearance, so the live service runs the fixed router.
3. **Production verification** — re-run the ORCH-010 P7 probe live
   (`read this page https://example.com` via `/api/chat`) and confirm the
   routing line reads `web_fetch_summarize` (106.0), not the −9.9 fallback;
   confirm the live service code matches the merged fix. That closes the
   acceptance criterion "the live misroute is fixed".

## 6. Files changed (PR #1334)

- `FRIDAY/src/friday/routing/capability_router.py` — fallback guard (+13/−1).
- `FRIDAY/tests/test_orch_012_fallback_fix.py` — new, 10 regression tests.
- `.github/workflows/owner-workflows.yml` — collect the new test in CI.
- `docs/collaboration/TASK-ORCH-012-FALLBACK-FIX.md` — this document.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-ORCH-012 CLAIMED → IN_REVIEW.

## 7. Process note

The 12:09 IST work-request run claimed the task (comment 7075462674, claim PR
#1334) and implemented the fix + tests locally, but was cancelled by the
runtime at ~13:07 IST ("schedule was removed or turned off before this run
could resume") before committing or pushing. This run (hourly self-check,
13:08 IST) found the claim real but the implementation unpushed, repaired the
stall by verifying the local work (matrix + pytest + pre-fix control),
committing it to the claim branch, and filing this report. No work was lost:
the fix, tests, matrix script, and venv are the claiming run's, verified here.
