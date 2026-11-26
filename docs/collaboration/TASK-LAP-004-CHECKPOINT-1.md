# TASK-LAP-004 — Checkpoint 1: Escrcpy leg verified vs current release + test wired into CI

**Task:** TASK-LAP-004 (REPO-IMPLEMENT, laptop/phone repos wave 2: ULTRON ×2 reference-only, Escrcpy adapt).
**Branch:** `muse8/task-lap-004` — rebased onto main `25cfe733` this checkpoint.
**Date:** 2026-11-26 ~05:3x IST. **Status:** repo leg done; live legs BLOCKED (owner stop order, fleet CD broken).

## 1. Upstream re-verified first-hand (2026-11-26)

| Fact | Evidence |
|---|---|
| Latest release **v3.3.1**, published 2026-10-10 | `api.github.com/repos/viarotel-org/escrcpy/releases/latest` → `tag_name: v3.3.1` |
| Licence **Apache-2.0** | `raw.githubusercontent.com/viarotel-org/escrcpy/main/LICENSE` opens "Apache License, Version 2.0, January 2004" |
| v3.3.1 is a **transitional release** | Release notes: "bridges the gap between the existing version and the new billing and licensing system planned for Escrcpy 4.0.0 and later"; "all existing features in Escrcpy 3.3.1 are available for free … a long-term policy for the existing version" |
| Repo API licence field | Unverifiable this run — unauthenticated `GET /repos/viarotel-org/escrcpy` returned HTTP 403 (rate limit); the raw LICENSE fetch above is the first-hand proof instead |

**Pin decision (answers scope-doc Q2): pin v3.3.1.** The FRIDAY-side code is a
pattern adaptation — no Escrcpy code is vendored — so the pin constrains only
which released app the owner installs on the laptop. Do **not** follow "latest"
past 4.0.0 without a fresh licence check: the fleet rule is FREE-only, and
4.0.0 plans a new billing/licensing system. Recorded in
`docs/ESCRCPY_INTEGRATION.md` ("Release pin" section, this PR).

## 2. IG2-LAP-01 re-verified on main `25cfe733`

Paths corrected from the scope doc (the scope doc's `FRIDAY/escrcpy_*.py`
paths do not exist; the real paths, confirmed by the test's own imports):

| Piece | Path | Size |
|---|---|---|
| Integration engine | `FRIDAY/src/friday/remote/escrcpy_integration.py` | 11,042 B |
| Tools | `FRIDAY/src/friday/tools/builtin/escrcpy_control.py` | 5,013 B |
| Tests (8 tests) | `FRIDAY/tests/test_ig2_lap01_escrcpy.py` | 3,393 B |
| Doc | `docs/ESCRCPY_INTEGRATION.md` | — |

- `escrcpy_integration.py`: stdlib-only (`re`, `dataclasses`) plus an optional
  import of `friday.remote.phone_ui_agent.BLOCKED_PACKAGE_HINTS` with a
  hard-coded fallback — safe to collect in the tier-1 venv.
- `escrcpy_control.py`: imports `friday.core.types` and `friday.tools.base`
  — the same import family as other FRIDAY tier-1 tests
  (e.g. `test_capability_routing.py` imports `friday.core`).
- No version pin existed anywhere in the integration before this checkpoint.
- **Gap closed by this PR: the test was NOT in CI** (zero workflow hits for
  `ig2_lap01` / `escrcpy` before this change). It is now wired in (see §3).

**Q1 answered in part:** no new implementation is needed repo-side — the
Escrcpy adapt already exists and matches the current release. Completion of
the Escrcpy leg = this CI wiring + the live proof (real end-to-end + failure
case), which stays gated on clearance.

## 3. CI wiring (this PR)

`.github/workflows/friday-universe-ci.yml`, step "Run FRIDAY tier-1 tests"
(`working-directory: FRIDAY`): `tests/test_ig2_lap01_escrcpy.py` added to the
pytest invocation alongside `tests/test_reliability.py`, with a
`# TASK-LAP-004` comment following the established pattern (FRD-044, IG-FRD-006-FIX-01).
The REL-068 test-collection guard now sees the file collected by a
PR-triggered workflow. **CI proof is the PR's own run — no green claimed
at filing; the run is pending.**

## 4. What is still owed

- **Live legs BLOCKED, not done:** real device task via the bridge on the
  real laptop/phone path + disconnect/reconnect failure case; owner stop
  order in force (WATCH125), fleet CD broken. Awaiting clearance or a
  coordinator ruling (STR-047 precedent).
- **ULTRON repos:** reference-only, guardrail proof of absence recorded in
  the scope doc (checkpoint 0). No change this checkpoint.
- **Board flip** rides in this PR: TASK-LAP-004 AVAILABLE → IN_REVIEW,
  branch `muse8/task-lap-004`, pr = this PR.
- **Noted, not mine:** EARN-026 board flip IN_REVIEW → CLAIMED (work PR
  #1897 merged 03:08 IST, merge `5af66ab0`) is in no open board PR
  (#1909/#1914 carry the WATCH125 fix list only) — left for the
  coordinator's next board PR; no competing board PR filed while #1909/#1914
  are open. PR #1910 (M13, STR-068-FIX-01 PARK) merged this run.

— Muse 8
