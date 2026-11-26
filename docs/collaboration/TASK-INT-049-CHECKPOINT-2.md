# TASK-INT-049 — Checkpoint 2: live watch-cycle observation evidence (2026-11-26 ~11:15 IST)

- Task: PRODUCTION-VERIFY IntelX corpus items IG-INT-05, IG-INT-06, IG2-INT-01, IG2-INT-02 — live watch-cycle verification (wave 3), P2.
- Claim: hub #1483 comment 7175491565 (~03:15 IST, 2026-11-26); branch `muse6/task-int-049-intelx-watch-verify` from main `614e6b1d`.
- Checkpoint 1 (repo-side scoping, branch @ `2903f925`): all four items MERGED on main, code present, repo tests re-run 41/41 first-hand (7 + 5 + 20 + 9).
- This checkpoint files the LIVE observation leg. No live step was taken by Muse 6: the probe ran under the WATCH138 read-only grant, executed by the coordinator via bridge `run_shell` on server 6 (IntelX-Server). No alert dispatched, no burst triggered, no config changed, no live run started by this task.

## Probe execution (source: WATCH140 follow-up, hub #1483 comment 7183061017, ~10:57 IST)

- Grant: WATCH138 (hub 7182378812) — read-only `run_shell` on IntelX-Server for watch-cycle OBSERVATION only (state/logs/scheduler, DB-001 grant shape).
- Exact read-only command list: Muse 6 hub post #1843 (comment 7182846179, ~10:15 IST). Comparison base: main `bf41a6c4`.
- Step 0 (verbatim): checkout `/opt/friday_universe` present; `IntelX.service` active (running) since 2026-11-24 13:29 UTC, MainPID 4973, ExecStart venv uvicorn `intelx.app.main:app --port 8005 --workers 1`; soak timer active.

## Check 1 — deployed byte-identical — FAILS (verbatim)

- 10/11 hashes match main `bf41a6c4`. `browser_sidecar.py` live `196344941b5402a375ec12291e7f773042d036b0` != expected `0ac04c8e184664a9671f50421bed00f0e03bca09`.
- Coordinator archaeology (WATCH140 follow-up): the live hash is the pre-INT-051 blob (d51b82df-era); main's version came from commit `c11dbeb9` (TASK-INT-051 wave-3 wiring). The live checkout is stale for exactly this one file — no hot edit, a missed update. No live change.

### First-hand repo verification by Muse 6 this run (local clone, `origin/main` fetched to `4127456c`)

- Expected blob `0ac04c8e184664a9671f50421bed00f0e03bca09` is `IntelX/intelx/connectors/browser_sidecar.py` at main `bf41a6c4` AND at current main `4127456c` (`git rev-parse` on both) — the drift finding stands on current main, not only on the probe's base.
- Live blob `196344941b5402a375ec12291e7f773042d036b0` is the same file at `e36d1566` and at `c11dbeb9^` — the version in force before TASK-INT-051.
- `c11dbeb9` (2026-11-25, "TASK-INT-051: wire wave-3 adaptations into IntelX production paths + 32 tests + evidence doc + CI tier-1 registration") changed `browser_sidecar.py` by +43 lines: it added `CamofoxClient.fetch_macro` (site search macro via `camofox_macros.build_search_url`) and `CamofoxClient.fetch_transcript` (public YouTube timedtext captions). Those two methods are absent from the live file.
- Impact per item: **IG2-INT-01** (on-demand camofox sidecar) — the live service does NOT run the merged code for its sidecar module, so its live leg cannot pass until re-sync. The other 10/11 files (all four items' remaining code + all four test files) match main. `deployed` does NOT flip to YES for `browser_sidecar.py` (ruling, WATCH140 follow-up).

## Check 2 — IG-INT-06 registry live count — PASSES

- Registry count `102 102` (count field and entry count), matching checkpoint 1's repo-side count of 102 entries in `IntelX/intelx/registries/scouted_repos.json`.

## Check 3 — watch-cycle observation — MIXED, envelope-recency clause FAILS

- Watch cycles proven running today: every ~30 min, last 04:32 UTC, `alerted=0`, all dups.
- Newest outbox envelope `2026-11-24T21:30:32Z` (id `8ca3ca25...`, GPT-6 protein-design digest) — ~32 h old at probe time (~05:20 UTC 2026-11-26); **no envelope fired today**.
- `instant_outbox.jsonl` ABSENT from `IntelX/data/watches/`.
- Soak timer active; today's soak file `2026-11-26.json` exists, `triggered_by: timer`, `synthesis_status: failed`.

### Envelope-recency judgement (as asked by the coordinator)

- The acceptance requires "one real alert end-to-end per item" on a real watch cycle. The cycle itself is alive (runs every ~30 min), but it produced **zero alerts in the observation window** (`alerted=0`, all dups), the newest envelope is ~32 h stale, and today's soak synthesis **failed**. The recency clause therefore FAILS: no item's alert leg is proven by this observation. This is a live observation, not a code verdict — the merged code passed its repo tests; the live alert path has simply not fired a provable alert in the window.
- The failed soak synthesis (`synthesis_status: failed` on `2026-11-26.json`) is a second live finding, flagged to the coordinator for diagnosis. No cause is claimed here; no live step was taken to investigate it (outside the read-only grant).

## Check 4 — no stale duplicate of any of the four modules — PASSES

- 5 hits, all canonical modules (`scouted_repos.py`, `named_sources.py`) or legitimate importers (`retriever.py`, two `__init__.py`); no duplicate implementation.

## Ruling (WATCH140 follow-up)

- INT-049 stays open; checkpoint 2 files the observation evidence with the check-1 failure verbatim; `deployed` does NOT flip to YES for `browser_sidecar.py`; `production-verified` stays NO until the held alert/burst leg is cleared and run.

## Re-sync route proposed (no live change by Muse 6; any deploy needs hub clearance)

1. **Clearance first:** coordinator clears a re-sync of the live checkout on Server 6 (IntelX-Server). Owner stop order still in force; this proposal is not an execution.
2. **Minimal route (preferred):** `git -C /opt/friday_universe fetch origin`, then check out `IntelX/intelx/connectors/browser_sidecar.py` from current main into the live tree (single file; the other 10/11 already match). Alternative if the coordinator prefers the whole checkout aligned: `git pull --ff-only` to current main.
3. **Restart decision (separate clearance):** the running `IntelX.service` process holds the old module in memory — a file re-sync alone does not change the running code. Restarting `IntelX.service` to load the new code is a live change and needs its own hub clearance.
4. **Verify:** after re-sync (+ restart if cleared), re-run probe check 1 (same 11 `git hash-object` commands, same expected hashes) to confirm 11/11 against current main.
5. INT-051's 32 tests passed in CI on main; the re-sync aligns live with already-merged main — no new code is introduced.

## Five states

implemented YES (all four merged) / tested YES (repo tests re-run 41/41; CI green on main) / merged YES / deployed NO (`browser_sidecar.py` stale live; 10/11 match) / production-verified NO (alert/burst leg held + envelope-recency fail + soak synthesis failed today).

## Next

- Coordinator ruling on the re-sync route + service-restart decision; re-run of probe check 1 after re-sync.
- Clearance for the held alert/burst live leg (duplicate/flood burst + one real alert end-to-end per item) — still HELD on the owner stop order.
- Diagnosis of today's failed soak synthesis (`2026-11-26.json`, `synthesis_status: failed`) — flagged, owner/coordinator to route.
- Board flip AVAILABLE → CLAIMED rides in the work PR (rule 4); no work PR yet (rule 1 — one work PR when DONE/BLOCKED). INT-049 stays open per the WATCH140 ruling.
