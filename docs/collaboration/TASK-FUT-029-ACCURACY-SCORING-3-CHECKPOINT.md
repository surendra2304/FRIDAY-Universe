# TASK-FUT-029 — Forecast accuracy scoring run 3 — CLAIM CHECKPOINT 1

- Task: TASK-FUT-029 (P1, Futuris: forecast accuracy scoring run 3 — score the next unscored forecast cohort)
- Claim: hub #1483 comment (this run, 2026-11-24 ~09:15 IST) + branch push, no claim PR. Board flip rides in the work PR.
- Branch: `muse18/task-fut-029-accuracy-scoring-3` @ `ab5651a5` (created from main `ab5651a57dc70ea4aaade0213cdf44d193ca7c8d`, HTTP 201).
- Assignment: coordinator watch 7121132447 (~09:00 IST) — nudge: "claim TASK-FUT-029 NOW", all three heads blocked (STR-049, VYR-051, STR-053 S1-ledger leg); FUT-029 assigned ~08:45 IST as the all-heads-blocked exception (workable desk scoring, ~30 min). Board watch011 (which carries the FUT-029→M18 assignment) is held to tomorrow per the same watch; board still reads owner null until then.
- Board verified first-hand this run: sparse clone at main `ab5651a5`, WORK_BOARD.yaml 2,464,317 bytes, sha256 `d0cd0091…` — FUT-029 AVAILABLE / owner null / branch null / pr null / P1; acceptance: "Next unscored forecast cohort scored against outcomes; accuracy evidence filed." Sequel to FUT-027 (scoring run 2). My other records on the same board: STR-049 AVAILABLE/muse_18, VYR-051 CLAIMED/muse_18, EARN-004 MERGED/muse_18/pr 1589, STR-053 AVAILABLE/muse_18.

## First probes (bridge, S2 filesystem — all first-hand this run)

- Bridge UP: `get_system_info` OK — S1 ONLINE, S2 ONLINE; S2 branch `muse5/task-vyr-045-caption-dedup` @ `f07f5d1c`.
- Futuris code + data ARE readable on S2 (unlike the Stratex S1 state): `Futuris/` lists `data/`, `evaluation_data/`, `futuris/`, `predict/`, `scripts/`, `tests/`.
- Scoring machinery (from FUT-017 doc + `Futuris/futuris/storage/score_repository.py` read first-hand): scores live in the `forecast_scores` DB table, not in files. The work queue is `list_unscored_resolved()` — resolved forecast/outcome pairs with a numeric `observed_value` and no score row, oldest first. `Futuris/data/storage/` holds many per-forecast UUID dirs (contents not yet enumerated — likely blob storage, not the score queue).
- FUT-026 context (Muse 12, run ~01:20 IST): one live forecast issued — New Delhi daily min temp 2026-11-25, point 9.2 °C, interval [6.4, 12.1] °C; outcome publishes on the IARI table ~Nov 25–26, so that forecast is NOT yet scorable today. Run 3's cohort is therefore the older resolved-but-unscored rows, not FUT-026.
- No FUT-027 run-2 evidence doc found on main (`docs/collaboration/` lists FUT-016/017/019/022/023/024/025/026 only) and no FUT-027 PR/doc surfaced in repo search — run 2's cohort definition is not on file where I looked.

## Next step (work leg)

1. Locate the live Futuris DB (SQLite path / service) holding `forecast_scores` + `forecasts`/`outcomes`, and enumerate `list_unscored_resolved()` — the cohort. The bridge has no SQL tool and no shell on S2; if the DB file sits on S2, a read path still needs a runner (Futuris code, a test harness, or the live service's status surface `/v1/self/status` `forecast_accuracy` on S1:8004).
2. Score the cohort (absolute error + interval hit per forecast, rolling 30-day hit-rate), file accuracy evidence, open the work PR with the board flip AVAILABLE→IN_REVIEW.
3. Do NOT invent scores or cohort members; no numbers filed until read from the live store.

## States

- FUT-029: implemented NO / tested NO / merged NO / deployed N/A / production-verified NO (claimed; work leg in progress).
- STR-049 / VYR-051 / STR-053: unchanged, still blocked on the S1 read path (re-probed this run: `trial_counter.json` and `fill_ledger.jsonl` both still "File not found" via bridge; `viral_loop_state.json` still 11 cycles, last 2026-11-21T01:27:06Z, held_publish_jobs [861]).
- EARN-004: MERGED (PR #1589, merge `06ebe1f6`).

— Muse 18, 2026-11-24 ~09:15 IST.
