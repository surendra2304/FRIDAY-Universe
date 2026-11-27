# TASK-FRG-026 — CHECKPOINT 3 (seven uncollected test paths as evidence + local test run: 55/56 pass, FRG-06 fails) — Muse TP7 — 2026-11-27 ~21:01 IST

Filed 2026-11-27 ~21:01 IST on branch `musetp7/task-frg-026-forge-verify-wave3`
(parent `132d137d`, checkpoint 2). No hub post with this checkpoint: Burn Enforcer
speed order (20:32 IST, hub #2045 comment 7221511972 §G, restated 20:54 §I) — post
only at claim, completion, genuine block, or wrap-up. This is mid-task progress.

## WATCH226 §D6 adopted (hub #2045 comment 7221115974)
- (a) **Seven uncollected FRG test files — filed here as evidence.** The
  owner-workflows edit itself is the coordinator's (shared fleet config);
  TP7 does NOT edit `.github/workflows/owner-workflows.yml`.
- (c) **Clearance — PROCEED.** TP7's own-task live verification is covered by
  standing clearance 7200564540. The test run below is that verification: it
  executes the repo's own tests in this sandbox — no server move, no Forge
  dispatch, no live host touched.
- (b)(d)(e) **still carried, owner = coordinator.** Live Forge host naming,
  FRG-06 prospect source, FRG-09 closure — WATCH227 §F.6 carried them again
  unresolved; Burn Enforcer 20:54 §D confirms still open / carried to the
  coordinator. No host or prospect source invented here.

## Evidence — the seven files (WATCH226 §D6a)
Verified first-hand on the FRG branch ref AND on live main `55a5a622`
(identical blob SHAs on both — files unchanged since the branch was cut):

| File (Forge/tests/) | Corpus | Bytes | Lines | Tests | Collected by CI? |
|---|---|---|---|---|---|
| test_ig2_frg01_karpathy_principles.py | FRG-01 | 2,858 | 90 | 8 | NO |
| test_ig2_frg04_parallel_download.py | FRG-04 | 4,288 | 138 | 8 | NO |
| test_ig2_frg05_ecc_harness.py | FRG-05 | 3,857 | 110 | 9 | NO |
| test_ig2_frg06_local_business.py | FRG-06 | 3,005 | 78 | 8 | NO |
| test_ig2_frg07_agent_creation.py | FRG-07 | 4,906 | 125 | 9 | NO |
| test_ig2_frg08_claudex_loop.py | FRG-08 | 7,307 | 195 | 9 | NO |
| test_ig2_frg10_review_wiring.py | FRG-10 | 6,104 | 159 | 5 | NO |

Total: 56 test functions. No `test_ig2_frg09` file exists on the branch or on
main — FRG-09 is docs-only (checkpoint 1 stands). Blob SHAs (branch = main):
frg01 `02b9b1c39b98`, frg04 `8bca82ff20a7`, frg05 `5b5ff35e47f1`, frg06
`68e7d724039c`, frg07 `2d7864efbdb6`, frg08 `4e884fa0e65b`, frg10 `c942a2858e26`.

## CI finding re-verified on current main `55a5a622`
- `.github/workflows/owner-workflows.yml` Forge pytest list still collects only
  `Forge/tests/test_ig2_frg02_code_graph.py` (line 176) and
  `Forge/tests/test_ig2_frg03_ocr_review.py` (line 177) from the `test_ig2_frg*`
  family (grep count = 2, first-hand on main). The seven files above are
  collected by NO workflow. (The list also collects other `test_frg*` files —
  frg001/frg017/frg019/frg022/frg028/frg030 — the gap is specific to the
  `test_ig2_frg*` family.)
- The FRD-049 fix persists on main: `tests/test_voice_task_board.py` is in the
  voice-regressions list in `.github/workflows/friday-universe-ci.yml` (line 823).

## LIVE VERIFICATION — the seven files run locally: 55 pass, 1 FAIL
Run 2026-11-27 ~21:01 IST in this sandbox (NOT CI, NOT a live host — see
environment note below). Command, from the Forge dir on the branch checkout:
`PYTHONPATH=<repo-root>:<repo-root>/Forge python -m pytest -q -p no:cacheprovider`
on the seven files. Collection: all 56 tests collected. Result:

- frg01 Karpathy principles: 8/8 pass.
- frg04 parallel download: 8/8 pass.
- frg05 ECC harness: 9/9 pass.
- frg06 local-business pipeline: **7/8 pass — 1 FAIL, deterministic**
  (re-run fails identically).
- frg07 agent creation: 9/9 pass.
- frg08 Claudex Loop: 9/9 pass.
- frg10 review wiring: 5/5 pass.

### FAILING TEST — FRG-06 (real defect, named fix task below)
`tests/test_ig2_frg06_local_business.py::test_pipeline_ranks_filters_and_stays_pending`
(line 53): `run_pipeline([low, _cafe()])` returns prospects
`['Sunrise Cafe', 'Tiny']`; the test expects `['Sunrise Cafe']` — the
2.0-rated, 0-review prospect "Tiny" must be FILTERED OUT, not just ranked last.
Root cause, read first-hand in `Forge/forge_upgrade/local_business_pipeline.py`:
`prospect_score` gives +0.5 for having no website and nothing else for a
prospect with no demand signal, so `prospect_score(Tiny)` = **0.5** (verified by
direct call; Cafe = 1.0). `run_pipeline` (line 196) filters on
`prospect_score(p) >= min_score` with default `min_score=0.3` — 0.5 >= 0.3, so
Tiny survives. A no-website prospect can never score below 0.5, so the 0.3 gate
is vacuous for exactly the class the test exercises: the filter can only ever
drop prospects that HAVE a website. Either the no-website weight (0.5) must be
tempered by demand evidence, or `min_score` must rise above it — that is the
fix decision, not taken here.
- **Named fix task: TASK-IG2-FRG-06-FIX-01** — make `run_pipeline` filter a
  2.0-rated / 0-review no-website prospect (or restate the test's contract).
  The fix is NOT made in this checkpoint; this task is PRODUCTION-VERIFY, and
  failing items get named fix tasks. FRG-06 prospect source (WATCH226 §D6d)
  is still owed from the coordinator and rides with the fix task.
- The other seven frg06 tests pass, including the approval gate
  (publish/contact-plan blocked until approved; "nothing auto-sent") and the
  no-outreach-sending-surface check.

## Environment note (so the next run can reproduce this)
- The sandbox ships NO pytest (`No module named 'pytest'`, system Python
  3.12.3, PEP 668 externally-managed). Built a venv at
  `~/workspace/.scratch-frg/venv` (pytest 9.2.0 + pytest-asyncio + httpx +
  pydantic + pydantic-settings + fastapi + sqlalchemy[asyncio] + aiosqlite +
  python-dotenv + anthropic + openai + redis + rich + psutil + beautifulsoup4
  + greenlet + uvicorn; `--no-cache-dir`, TMPDIR pointed at the scratch dir).
- `/tmp` is a 512M tmpfs (411M used at run start): the full
  `Forge/requirements.txt` install died with `Errno 28 No space left on
  device` — oracledb/gradio were NOT installed and were NOT needed for these
  tests. The venv is scratch; the recipe above rebuilds it.
- `Forge/tests/conftest.py` imports `pytest_asyncio`, `httpx`, and `app.*`;
  `app.verification.engine` imports `mesh.heavy_task` — `mesh/` lives at the
  REPO ROOT, so PYTHONPATH needs the root as well as `Forge/`. CI gets the root
  because its step runs `python -m pytest` from the repo root (cwd on
  sys.path); no CI defect is claimed here — the mesh import resolves in CI
  the same way.
- `git fetch` recovered this run (origin/main `fae3ee05..55a5a622` after the
  curl-56 failures at 20:01/20:52); the FRG branch was fetched and checked out
  in a worktree for the local run.

## Live legs — still HELD (no live build task run)
The sandbox test run is verification of the shipped tests, NOT a live Forge
build task on a live host: no Forge dispatch was attempted, no host was named,
no fleet move was made. The per-item live legs shaped in checkpoint 2 are
unchanged and still need the (b) host ruling before any of them can run.
FRD-049 live leg still HELD (merged, not production-verified).

## Hub + board at filing (21:01 run, first-hand)
- Hub #2045 read through comment 7222119112 (552 comments; 2 new since the
  20:52 prep): Burn Enforcer 20:54 (7221981244) read in full — TP7 (b)(d)(e) +
  Forge host naming still open/carried to coordinator (§D); speed order
  restated, TP7 named (§I); board PR #2151 HELD, do NOT merge as-is (§H).
  Muse 12 released TASK-FUT-038 → pool (7222119112) — no TP7 mention. **No TP7
  demand, no verifier duty, no competing claim on FRG-026.**
- Board on live main `55a5a622` (blob `28d48e4f`, 11,505 lines — same blob as
  20:01; #2159 merge did not touch the board): FRG-026 AVAILABLE/muse_tp7/P2
  (claim flip still rides the next board PR — #2151 HELD), FRD-059
  IN_REVIEW/muse_tp7/pr 1848 (stale — PR merged), FRD-049 MERGED/muse_tp7/pr 2104.
- Branch `musetp7/task-frg-026-forge-verify-wave3` head before this commit:
  `132d137d` (checkpoint 2), verified via ref GET + local fetch; no new
  commits this hour before checkpoint 3 — no stall.

## Five states
Implemented NO (verify only; no Forge code changed) / tested PARTIAL (56 tests
run locally, 55 pass, 1 real FRG-06 failure) / merged NO / deployed NO /
production-verified NO.

## Queue / schedules / usage
- Queue: FRG-026 (head) → FRD-059 (IN_REVIEW, pr 1848, live-gated).
- Work-request task stays absent while FRG-026 is claimed (guard — verified
  absent in the cron list this run). Hourly self-check + weekly reset armed
  (next self-check 22:01 IST; weekly reset Wed Dec 2 17:11 IST).
- Usage: 14% of free weekly limit (re-verified 21:01 IST, unchanged).
  Reset Wed Dec 2, 17:01 IST. Additional tokens 0%.
- Carried: FRG-06 fix task TASK-IG2-FRG-06-FIX-01 (named, not started);
  (b)(d)(e) rulings; FRD-049 live leg HELD.
