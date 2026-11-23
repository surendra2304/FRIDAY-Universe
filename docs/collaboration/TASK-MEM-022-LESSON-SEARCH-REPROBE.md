# TASK-MEM-022 — Memora: re-probe the MEM-019 lesson search after the MEM-021 fix (regression check)

**Worker:** Muse 10 · **Date:** 2026-11-23 · **Branch:** `muse10/task-mem-022-lesson-search-reprobe` · **Work PR:** (see board)
**Board:** TASK-MEM-022 (Memora: re-probe the MEM-019 lesson search after the MEM-021 fix lands — regression check)
**Assignment:** Muse coordinator watch 7093557479 (~12:10 IST). Queue: MEM-021 MERGED → MEM-022* assigned; MEM-015 already MERGED, so the queue was empty after MEM-021.

## Claim (done 2026-11-23 ~12:15 IST)
- Hub claim comment 7093639752 (issue #35).
- Board verified AVAILABLE, owner null, on main 23324fdd (board blob 6e69d6c0, via PAT helper git blobs API).
- Branch `muse10/task-mem-022-lesson-search-reprobe` created via PAT helper at main 23324fdd.
- Board flip (AVAILABLE → CLAIMED → IN_REVIEW, owner muse_10) rides in the work PR per coordinator order — no separate claim PR.
- Work-request job `muse10-work-request` removed (cron.remove, scheduler reconciled). Hourly self-check stays armed.

## Verdict (read this first)

**The MEM-019 lesson search regression check PASSES.** After the MEM-021 fix
deployed and the one stale UNIVERSAL copy repaired live, the MEM-019 lesson
copy `8cfcaeb6-cc9c-446c-88d1-4797a469fbce` now surfaces in search at **rank 1,
keyword 1.0** for both the non-owner (friday) and the owner (sentinel), on the
exact distinctive query that missed it in MEM-019 and MEM-021. The original
stays PRIVATE (friday 404, sentinel 200) and the copy stays UNIVERSAL and
directly readable (friday/futuris 200). MEM-019 G1 is closed by live evidence;
no new gap was found.

## Acceptance mapping

- **MEM-019 lesson search re-probed after MEM-021 merges** — yes: MEM-021
  merged 12:06 IST (merge d7d534cd, PR #1462); the re-probe ran ~12:18–12:21
  IST against the deployed fix (see below).
- **UNIVERSAL dual-copy search returns the lesson** — yes: friday distinctive
  search (limit 100) returns the copy at rank 1, keyword 1.0; friday prefix
  search (limit 50) returns exactly 1 result — the copy at 1.0; sentinel
  distinctive search returns 2 results — copy rank 1 and original rank 2,
  both 1.0.
- **(or the remaining gap filed)** — not needed; no remaining gap.

## Deploy state (verified live before the re-probe)

- GitHub main at claim time: `23324fdd` (board PR #1467 merge). MEM-021 merge
  `d7d534cd` is an ancestor.
- Fleet Continuous Deployment run 45125337599 on main `23324fdd`: **completed
  success** 12:07 IST.
- Server 1 checkout: `d7d534cd` (MEM-021 merge head). The fix is on disk:
  `_sign_copy_provenance` (`promotion.py:195`), `repair_universal_copies`
  (`:492`), repair CLI `Memora/scripts/repair_universal_copies.py` (dated
  Nov 23 12:07).
- `Memora.service` on Server 1: active (running) since **12:07:22 IST**,
  Main PID 2836425, uvicorn on port 8002, `/health` 200, version 2.0.0.
  The MEM-021 fix is deployed and live. (An earlier `systemctl show
  memora.service` read `inactive` — the unit name is case-sensitive:
  `Memora.service`.)
- Both Oracle servers ONLINE (bridge `get_system_info`).

## The ladder (all live, Server 1, `probe_mem022.py`, raw JSON in `/tmp/muse10_mem022/`)

Lesson original `270d1a53-7e3c-4f18-ad00-829ff3c734e1` (sentinel, PRIVATE).
Copy `8cfcaeb6-cc9c-446c-88d1-4797a469fbce` (UNIVERSAL). Distinctive query
`momentum breakout entry 2x ATR stop volume filter`; prefix
`MUSE10-TEST-MEM-019`.

### Baseline — defect still reproduces on the deployed code (~12:18 IST, pre-repair)

| Step | Call | Result |
| --- | --- | --- |
| Health | `GET /health` | **200**, `status: ok`, version 2.0.0 |
| Copy as non-owner | `GET /v1/memories/{copy}` (friday) | **200** |
| Copy as outsider | `GET /v1/memories/{copy}` (futuris) | **200** |
| Search as non-owner, distinctive | `GET /v1/memories/search?q=...&limit=100` (friday) | **200**, 100 results, **copy absent**, max keyword 0.0787 |
| Search as owner, distinctive | Same query (sentinel) | **200**, exactly 1 result: the original at 1.0, copy absent |
| Search as non-owner, prefix | `GET /v1/memories/search?q=MUSE10-TEST-MEM-019&limit=50` (friday) | **200**, 50 results, **copy absent**, max keyword 0.0 |

Identical to the MEM-019/MEM-021 defect signature: the deployed fix changes
*new* copies at creation time, but the pre-existing copy is still
stale-signed until repaired — exactly what the repair CLI is for.

### Repair — dry-run then apply (~12:18–12:19 IST)

Run from `/opt/friday_universe/Memora` with the service venv
(`venv312/bin/python`); settings resolve `MEMORA_MASTER_KEY` from
`Memora/.env` (presence checked, value never printed). The service was
**not** stopped: the repair touches only the single stale test copy
(provenance re-sign + embedding upsert, one committed transaction), which
has no concurrent writer; stopping the fleet memory service would have been
the larger interruption. Noted here as a deliberate choice, not an oversight.

| Step | Result |
| --- | --- |
| Dry-run `python scripts/repair_universal_copies.py` | exit 0: `scanned: 1, already_current: 0, would_repair: 1, unverifiable_ids: [], unsigned_ids: []` |
| Apply `MEMORA_REPAIR_UNIVERSAL_APPLY=1 python scripts/repair_universal_copies.py --apply` | exit 0: `scanned: 1, repaired: 1, would_repair: 0, unverifiable_ids: [], unsigned_ids: []`. Embedding upsert ran (Gemini `batchEmbedContents` 200 OK; vector table `memora_vector_store` initialised, dim 384). |

Exactly one record in the whole store needed repair — the MEM-019 copy — and
nothing was refused or left untouched.

### Re-probe — copy surfaces (~12:20 IST, post-repair)

| Step | Call | Result |
| --- | --- | --- |
| Health | `GET /health` | **200**, `status: ok`, version 2.0.0 |
| Copy as non-owner | `GET /v1/memories/{copy}` (friday) | **200** |
| Copy as outsider | `GET /v1/memories/{copy}` (futuris) | **200** |
| Search as non-owner, distinctive | `GET /v1/memories/search?q=...&limit=100` (friday) | **200**, 36 results, **copy rank 1, keyword 1.0** |
| Search as owner, distinctive | Same query (sentinel) | **200**, 2 results: **copy rank 1 (1.0), original rank 2 (1.0)** |
| Search as non-owner, prefix | `GET /v1/memories/search?q=MUSE10-TEST-MEM-019&limit=50` (friday) | **200**, exactly 1 result: **the copy at 1.0** |
| Original as non-owner | `GET /v1/memories/{orig}` (friday) | **404** — still PRIVATE |
| Original as owner | `GET /v1/memories/{orig}` (sentinel) | **200**, `scope: PRIVATE` |
| Copy as owner | `GET /v1/memories/{copy}` (sentinel) | **200**, `scope: UNIVERSAL` |

The copy passing search's Safety Invariant 2 leg (it is admitted at rank 1)
is itself the proof the re-sign verified: before the repair the same query
discarded it for every actor.

## Blast radius

- One test record re-signed + one embedding upserted (the MEM-019 copy,
  provenance-marked `test_data: true`, `task: TASK-MEM-019`). No other live
  memory was created, modified, or deleted; the repair scan found no other
  stale copy in the store. No live DB or config was written to directly, no
  service was restarted by this run (the 12:07:22 IST Memora restart was the
  Fleet CD deploy, before this task started), no sweep was run.
- No secrets in this doc, in any issue comment, or in any probe script (keys
  were read from the service env file at runtime on the server and never left
  it; only key *names* are recorded).

## Gaps found

- None new. MEM-019 G1 (UNIVERSAL dual-copy search invisibility) is **closed
  by this live evidence**. MEM-019 G2 (idempotent re-promotion writes a
  duplicate audit row) is untouched — out of scope for this re-probe task.

## What was NOT done

- No new promotion was run (the copy was repaired in place, not re-promoted).
- The auto-promotion variant was not re-exercised; new dual copies are fixed
  at creation time by the MEM-021 code, proven by the unit tests in MEM-021.
- FRD-037 stays CLAIMED and blocked: public-chat 401 gate (last re-verified
  ~11:26 IST by Muse 7; 401 persists across the latest FRIDAY restart).
  Live runs 0/3. Unchanged by this task.

— Muse 10
