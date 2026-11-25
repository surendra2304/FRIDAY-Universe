# TASK-INT-049 — Checkpoint 1: repo-side scoping (2026-11-26 ~04:15 IST)

- Task: PRODUCTION-VERIFY IntelX corpus items IG-INT-05, IG-INT-06, IG2-INT-01, IG2-INT-02 — live watch-cycle verification (wave 3), P2.
- Claim: hub #1483 comment 7175491565 (~03:15 IST, 2026-11-26); branch `muse6/task-int-049-intelx-watch-verify` from main `614e6b1d`.
- Scoped against: origin/main `bf5a08b7`, verified first-hand this run.
- This checkpoint is REPO-SIDE ONLY. No live leg run. No item is production-verified yet.

## Per-item verdicts (repo state)

### IG-INT-05 — named research/archive source utilities — MERGED, code present, tests 7/7
- Board: TASK-IG-INT-05 MERGED, owner muse_ai, PR #510, merge `546e8471` (board on main `bf5a08b7`).
- Code on main: `IntelX/intelx/connectors/named_sources.py` — Archive.org advancedsearch + metadata working connector; WolframAlpha fail-closed on missing `WOLFRAMALPHA_APPID`; OpenCulture / AlternativeTo / JustWatch honest seed-site registry (no public API claimed) — plus `IntelX/tests/test_ig_named_sources.py`.
- Tests re-run first-hand this run (disposable venv `/tmp/muse6-venv`, pytest 9.2.0, IntelX `requirements.txt`): **7 passed**.
- Live probe owed: one Archive.org search + one metadata fetch from Server 1; Wolfram stays disabled (no AppID — owner's decision).

### IG-INT-06 — scouted repo registry — MERGED, 102 entries verified, tests 5/5
- Board: TASK-IG-INT-06 MERGED, PR #518, merge `52884b1a`; expansion PR #771, merge `79a5358a` (32 → 102 entries).
- Code on main: `IntelX/intelx/registries/scouted_repos.json` — entry count verified first-hand by direct JSON load on main: **102**. Plus `IntelX/intelx/scouted_repos.py`, `IntelX/scripts/generate_scouted_repos.py`, `IntelX/tests/test_ig_scouted_repos.py`.
- Tests re-run: **5 passed**.
- Live probe owed: `intelx.scouted_repos.summary()` on the deployed service returns count 102.

### IG2-INT-01 — on-demand camofox sidecar — MERGED, code present, tests 20/20
- Board: TASK-IG2-INT-01 MERGED, PR #702, merge `5c657f88`.
- Code on main: `IntelX/intelx/connectors/browser_sidecar.py` + `IntelX/tests/test_ig2_browser_sidecar.py` (`camofox_macros.py` extends it under TASK-INT-051).
- Tests re-run: **20 passed**.
- Live probe owed: one bot-walled fetch through the sidecar on the live IntelX service.

### IG2-INT-02 — iterative deep-research loop — MERGED, code present, tests 9/9
- Board: TASK-IG2-INT-02 MERGED, PR #705, merge `ad2f5f04`.
- Code on main: `IntelX/intelx/agents/deep_research_loop.py` + `IntelX/deep_research_pipeline.py` + `IntelX/tests/test_ig2_deep_research_loop.py`.
- Tests re-run: **9 passed**.
- Live probe owed: one iterative deep-research run end-to-end on live feeds, producing a cited report.

Total re-run: **41 passed (7 + 5 + 20 + 9)**. The 11 scoped files are byte-identical between branch base `614e6b1d` and main `bf5a08b7` (`git diff` empty), so the run verifies main's code.

## Live leg (not run — gated)

Acceptance per item: real watch cycle on IntelX-Server against live feeds + duplicate/flood burst + one real alert end-to-end. None of that has run.

Gate: (1) no bridge route from this VM to Server 2 (IntelX home); (2) owner stop order in force — WATCH122 carries no lift and no live-leg clearance for INT-049. Ask to coordinator: grant a read-only watch-cycle observation route for INT-049 (same shape as the DB-001 read-only `run_shell` grant, watch075/076) or re-route the live leg to a bridge-capable worker. No live moves attempted this run.

## Five states

implemented YES (all four merged) / tested YES (repo tests re-run 41/41) / merged YES / deployed NO (live probe owed) / production-verified NO.

## Next

- Checkpoint 2: live watch-cycle evidence per item, once the route/clearance exists; or a blocked-with-reason report if the gate stands.
- Board flip AVAILABLE → CLAIMED rides in the work PR (rule 4); no work PR yet (rule 1 — one work PR when DONE/BLOCKED).
