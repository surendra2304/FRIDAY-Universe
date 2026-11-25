# TASK-FRD-045: WOOP goal-setting template inside FRIDAY's goal loop — evidence

- **Task:** TASK-FRD-045 — FRIDAY: WOOP goal-setting template inside FRIDAY's goal loop (P2, repo-side)
- **Branch:** `muse15/task-frd-045-woop-template` @ `937422fd` (parent: main `e0373ced`)
- **Acceptance:** "An owner goal created by voice/chat is structured as a WOOP record (Wish, Outcome, Obstacle, Plan) that the goal loop (TASK-IG-FRD-001) works against."
- **Verdict: MET on the acceptance as written, with one remaining leg named below** — the WOOP record is created, stored, and worked by the goal loop, verified by 25/25 tests run on the live FRIDAY host. The end-to-end leg (a goal created by voice through the deployed FRIDAY service) awaits merge + deploy, which is blocked fleet-wide by the broken CD (WATCH098) until the owner rules on the repair.

## What was built

| File | Change |
|---|---|
| `FRIDAY/src/friday/autonomous/woop.py` (new, +168) | Pure-data WOOP module (stdlib only): `normalise_woop` validates a record (Wish / Outcome / Obstacle non-empty; Plan a non-empty list of if-then entries, plain strings accepted); `woop_to_criteria` derives one `judge` success criterion from the Outcome; `woop_plan` builds the loop steps — opener (work the wish toward the outcome), one step per if-then plan entry, an obstacle-watch step, one evidence step per criterion; `format_woop_summary` one-line record. A half-formed WOOP raises `ValueError` and creates nothing. |
| `FRIDAY/src/friday/autonomous/goal_loop.py` (+43/-9) | `GoalLoopStore.create(..., woop=None)`: normalises the WOOP record, derives criteria from the Outcome when the caller passes none, builds WOOP plan steps, stores the record on the loop (`loop["woop"]`). `build_report` and `format_loop_summary` carry the WOOP record. No-WOOP creation is byte-identical in behaviour (existing tests pass unmodified). |
| `FRIDAY/src/friday/tools/builtin/goal_loop_tools.py` (+48/-5) | `start_goal_loop` (the voice/chat entry point) accepts an optional `woop` object `{wish, outcome, obstacle, plan}`; `criteria` is no longer required when `woop` is given. Tool description updated. `goal_loop_status` shows the WOOP record via the summary. |
| `FRIDAY/tests/test_frd_045_woop.py` (new, +220) | 14 tests: normalisation (full record, missing/empty fields, plain-string plan entries, missing `then`), Outcome→criterion derivation, plan-step coverage (wish / both if-thens / obstacle-watch / criterion evidence, exact step ids), store wiring (criteria derived, record stored, explicit criteria + WOOP kept together, bad WOOP creates nothing), loop-to-completion with fake executor/judge (WOOP in report), summary/report carry the record, tool round-trip with WOOP only, tool rejects bad WOOP, no-WOOP backwards compatibility. |
| `.github/workflows/friday-universe-ci.yml` (+6/-1) | `tests/test_ig_frd_001_goal_loop.py` (uncollected since it landed) and `tests/test_frd_045_woop.py` now ride in the FRIDAY tier-1 CI invocation, so the REL-068 collection guard sees them — the same pattern FRD-044 used. |

## Live evidence (real run on the real server)

- **Host:** FRIDAY-Server, AWS `15.134.130.145` — the live FRIDAY host (FRIDAY.service + FRIDAY-Voice.service both `active` at probe time). Route: bridge `run_shell` on Server 2 → ssh to the AWS host.
- **Run:** `2026-11-25 ~18:05–18:07 IST` (12:35–12:37 UTC). `git clone --depth 1 --branch muse15/task-frd-045-woop-template` into `/tmp/frd045-verify` (clone log: `937422f TASK-FRD-045: WOOP goal-setting template inside FRIDAY's goal loop`), then the service venv `/opt/friday_universe/venv/bin/python -m pytest tests/test_frd_045_woop.py tests/test_ig_frd_001_goal_loop.py -q`.
- **Result: `25 passed in 0.57s`, EXIT=0** — 14 new WOOP tests + 11 pre-existing goal-loop tests, all green on the live host's exact runtime (Python 3.10.22, production venv). Log tail recorded verbatim in the probe output; scratch `/tmp/frd045-verify` deleted afterwards (verified: `ls: cannot access '/tmp/frd045-verify'`). Net-zero production change: no service file touched, no restart, no deploy.
- **Local pre-check (this VM):** stdlib-only smoke of `woop.py` + `goal_loop.py` (`WOOP SMOKE OK`) and `py_compile` on all four touched files — passed. Full pytest could not run here (no `google-genai` etc. in this VM; the FRIDAY conftest imports the whole package tree). The live-host run is the authoritative test leg.

## Honest limits / remaining leg

1. **Not deployed on the live FRIDAY service.** The code is on the PR branch only; the running FRIDAY service does not yet have the `woop` parameter, so a goal created by voice through the live service cannot be WOOP-structured until this merges and deploys. That end-to-end voice leg is the remaining production-verification step — it is a deploy leg, not a code leg.
2. **Fleet CD is broken (WATCH098, hub 7161941236).** Every push to main currently triggers a failing CD run on both servers (S1 dirty checkout; S2 `.git/objects` not writable by the deploy user). Merging this PR will trigger a failing CD run until the repair lands; the repair needs the owner's word. Merge remains Muse's call.
3. **IG2-FRD-05 mic retest still owed** (WATCH098 demand on Muse 15) — needs a mic-capable browser run; not attempted here, unchanged from FRD-054.
4. CI on this PR was still running at filing time (the tier-1 job now collects the two goal-loop files for the first time); the live-host 25/25 is the verified leg, CI status to be confirmed on the PR.

## Five states

- **Implemented:** YES — WOOP module, goal-loop wiring, tool surface, tests, CI collection.
- **Tested:** YES — 25/25 on the live FRIDAY host (14 new + 11 existing); local smoke + py_compile.
- **Merged:** NO — work PR open, awaiting review/merge (never merge own PR).
- **Deployed:** NO — code is PR-branch only; live service untouched by design.
- **Production-verified:** PARTIAL — WOOP structuring + loop execution verified on the live host's runtime; end-to-end voice creation through the deployed service awaits merge + deploy (CD repair owed, owner word).

## Board flip (rides in this PR)

- TASK-FRD-045: AVAILABLE → IN_REVIEW (branch `muse15/task-frd-045-woop-template`, pr = this PR).

— Muse 15
