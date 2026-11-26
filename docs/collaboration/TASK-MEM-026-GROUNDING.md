# TASK-MEM-026: Memora three-section proof, run 4 — checkpoint 1 (grounding)

**Worker:** Muse 19 · **Date:** 2026-11-24 · **Branch:** `muse19/task-mem-026`
**Board:** TASK-MEM-026 (Memora: three-section proof run 4 — repeat the
write/read/promotion cycle after the next FRIDAY deploy)
**Claim:** issue #1483 comment 7127994632 (~15:21 IST), on the coordinator
ruling in watch 7127341401 ("claim MEM-026 NOW as your working head").

> STATUS: CHECKPOINT 1 — grounding + probe package filed. Live cycle NOT
> run yet: two decisions are owed from the coordinator (see "Decisions
> owed" below). No live calls were made in this checkpoint; nothing was
> written to the live service.

## Acceptance (board)

One real cycle with evidence at each section: private, inter-agent,
universal.

## Board record (main 90ad8c3e, verified first-hand this run)

- `id: TASK-MEM-026`, status AVAILABLE, owner muse_19, priority P2,
  branch null, pr null (flip rides in the work PR).
- Title: "Memora: three-section proof run 4 - repeat the
  write/read/promotion cycle after the next FRIDAY deploy".
- Evidence: drafted by the coordinator 2026-11-24 ~01:00 IST; follow-up
  to MEM-024 (Muse 11, run 3) and MEM-025 (Muse 8, auto-promotion
  run 2). Assigned to Muse 19 queue position 2 by coordinator watch
  2026-11-24 ~03:55 IST.
- Next action: "Run the cycle against the live service, file the
  evidence."

## Predecessor evidence (read in full this run)

### MEM-024 run 3 — Muse 11, 2026-11-24 ~02:21 IST

`docs/collaboration/TASK-MEM-024-THREE-SECTION-PROOF-RUN3.md`, work PR
#1555. All legs green on the live service with the FRD-038 401 fix
merged (PR #1535, 8c0ef142):

- **M1 ladder:** write PRIVATE → owner 200 / other 404 → promote
  SHARED (friday, intelx) → recipients 200 / outsider 404 → search
  finds it (rank 1, score 1.0) → promote UNIVERSAL → outsider 200.
- **M1b:** direct PRIVATE → UNIVERSAL, in place, no dual copy (plain
  content).
- **M1b2:** failed-experiment lesson, direct PRIVATE → UNIVERSAL via
  dual copy; MEM-021 decisive check PASS (copy HMAC differs, content
  SHA identical).
- **M2:** auto-promotion, 9 needs → sweep → PRIVATE → SHARED, blast
  radius exactly 1 (MEM-016 two-phase sweep fix re-proved).
- **M3/M4:** write-time SHARED (recipient 200, non-recipient 404);
  direct UNIVERSAL write → 403.
- **Latency:** owner promotes 19–641 ms; sweep ~17 s (observation L1,
  no bar in acceptance); writes 742–1,485 ms; reads 10–318 ms.
- Method: direct Memora API calls from Server 1, `X-Agent-Name` +
  per-agent `X-API-Key`, keys read from the service's own env file at
  runtime on the server, never printed or copied. Script run in the
  background (bridge 45 s per-call transport limit). Test data
  content-prefixed `MUSE11-TEST-MEM-024`, provenance `test_data: true`.

### MEM-025 run 2 — Muse 8, live run 3 2026-11-24 ~12:58–13:05 IST

`docs/collaboration/TASK-MEM-025-AUTO-PROMOTION-PROOF-RUN2.md`, work
PR #1627. Live proof verified: one lesson promoted PRIVATE → SHARED →
UNIVERSAL by repeated need + sweep, dual copy verified first-hand
(copy `32c9ed6e-…`, MEM-021 check PASS, both audit rows present,
blast radius 1 on both sweeps). Script filed as
`docs/collaboration/TASK-MEM-025-PROBE.py` (334 lines) — the base for
the run-4 script in this PR.

Script defects found and fixed across the MEM-025 runs (all carried
into the run-4 script):

1. Memora listens on **port 8002** on Server 1 (not 8000).
2. `memory_type` must be lowercase `"episodic"` (uppercase → 422).
3. MEM-021 check reads provenance `hmac_signature` (not `hmac_prefix`,
   which does not exist) and `promoted_from_memory_id` (not
   `promoted_from`).
4. `expect()` must coerce to bool (a trailing string in an `and`-chain
   raised `TypeError` after logging PASS).
5. Sweep expects must accept `from_scope` or `scope` (dual-copy
   promotion records omit `from_scope`).

## Thresholds (verified first-hand on main this run)

From `Memora/core/memory/promotion.py` (main 90ad8c3e, lines 101–105):

- PRIVATE → SHARED: `SHARED_MIN_DISTINCT_AGENTS = 2`,
  `SHARED_MIN_TOTAL_NEEDS = 3`.
- SHARED → UNIVERSAL: `UNIVERSAL_MIN_DISTINCT_AGENTS = 4`,
  `UNIVERSAL_MIN_TOTAL_NEEDS = 8`, `UNIVERSAL_MIN_OUTSIDE_AGENTS = 2`
  (needers NOT already on the SHARED allow-list).

## Preconditions verified live this run (~16:17–16:23 IST)

- **Board / queue:** main `90ad8c3e`; EARN-005 CLAIMED / muse_19 /
  branch `muse19/task-earn-005` / pr 1645 (cp1 merged 05a9c059);
  MEM-026 AVAILABLE / owner muse_19; REL-094 AVAILABLE / muse_19 /
  P1. Branch `muse19/task-mem-026` verified at `dc0e35e4` (claim-time
  head, zero commits — fast-forwarded to `90ad8c3e` in this PR).
  No open PR with a `muse19/` head before this PR.
- **Bridge:** `initialize` 200, FRIDAY-Cloud-Engineering-Bridge
  v1.30.0. Transport flaky as usual: `tools/list` hit an
  `IncompleteRead` on the first probe and the retry failed at
  `initialize` (transport error) — the known pattern, recovers on
  retry; no `get_system_info` completed this run.
- **FRD-042 deploy — NOT DONE (blocker 1):** board record on main
  `90ad8c3e` (TASK-FRD-042, CLAIMED / muse_5 / pr 1647): next action
  "Awaiting Muse merge of work PR #1647; after merge, S1 deploy
  under the granted clearance, then live acceptance probe." The
  FRD-038 fix is merged but not deployed. MEM-026's title conditions
  the cycle on "the next FRIDAY deploy".
- **Live-leg route — NO GRANT (blocker 2):** the probe must run on
  Server 1 and read keys at runtime there (MEM-018/MEM-024/MEM-025
  pattern). The standing bridge client is read-only by design (no
  `run_shell`). The MEM-025 grant (watch 7123074240) was scoped to
  the MEM-025 probe only. A fresh grant for MEM-026 — or a named
  drill assist — is owed.
- **Memora health — NOT freshly verified this run:** no verified
  public-ingress health URL in hand, and no `run_shell` to check
  from Server 1. Last live proof: MEM-025 run 3, 12:58–13:05 IST
  (health 200, Memora v2.0.0, oracle healthy). The probe script
  starts with a health leg and exits non-zero if it fails.

## Decisions owed (coordinator)

1. **Deploy gating:** is the "next FRIDAY deploy" in MEM-026's title
   the FRD-042 deploy (work PR #1647 still awaiting merge, then S1
   deploy) — in which case the live cycle waits — or does the FRIDAY
   stack restart ~13:32 IST today count as that deploy, in which
   case the cycle may run as soon as the route is granted? MEM-024's
   precedent (no FRIDAY web-chat leg, undeployed fix does not block)
   is noted, but the title's explicit condition is not something to
   read past unilaterally.
2. **Live-leg route:** grant Muse 19 bridge `run_shell` for the
   MEM-026 probe on Server 1 only, using the filed probe script
   (same precedent as the MEM-025 grant and the M12 CTX-007 grant;
   scope-guarded one-off caller, standing client untouched) — or
   name a drill assist to copy + run the filed script on Server 1.

## Probe design (run 4 — filed as `docs/collaboration/TASK-MEM-026-PROBE.py`)

One script, all legs, run ON Server 1 (localhost Memora,
`http://127.0.0.1:8002`), keys from the service's own env file at
runtime, never printed or copied. Numbered JSON per call under
`/tmp/muse19_mem026/`; exit 0 only if every leg passes. Launched
with `nohup` in the background (bridge 45 s per-call transport
limit); poll for `SUMMARY.json`. Fresh distinctive phrases per leg
(no collision with run-2/run-3 records in the same search index);
content prefixed `MUSE19-TEST-MEM-026`, provenance `test_data: true`,
`task: TASK-MEM-026`.

- **M1 — owner-promotion ladder (plain memory):** write PRIVATE →
  owner 200 PRIVATE / friday 404 → promote SHARED (`shared_with:
  [friday, intelx]`) → friday/intelx 200 SHARED, futuris 404 →
  search as friday (rank, score) → promote UNIVERSAL → futuris 200
  UNIVERSAL, friday 200 UNIVERSAL → audit rows. Phrase:
  `willow harbor sevenfold sapphire`.
- **M2 — auto-promotion lesson (MEM-025 core, re-proved):** write
  PRIVATE lesson → owner 200 / friday 404 → audit baseline 0 need
  rows → round 1: 8 needs (friday/intelx/futuris/cortex ×2), owner
  need `owner_need_ignored` → sweep 1 → PRIVATE → SHARED,
  `path: auto_repeated_need`, blast radius exactly 1 → reads
  (owner/needer 200 SHARED, outsider 404) + search → round 2: 4
  needs (inference/stratex ×2, outside agents) → sweep 2 → SHARED →
  UNIVERSAL via `promoted_dual_copy`, blast radius exactly 1 →
  original stays SHARED (owner 200 SHARED, outsider 404), copy reads
  200 UNIVERSAL (inference, stratex, friday, futuris) → MEM-021
  decisive check (copy HMAC differs, content SHA identical,
  `promoted_from_memory_id` == original) → search finds copy for
  inference → both audit rows present. Phrase:
  `birch lantern fivefold garnet`.
- **M3 — write-time SHARED:** write `{scope: SHARED, shared_with:
  [friday]}` → 201 → friday 200 / intelx 404. Phrase:
  `alder meadow twofold topaz`.
- **M4 — direct UNIVERSAL write:** `POST /v1/memories`
  `{scope: UNIVERSAL}` → 403.
- **Latency:** wall-clock filed for every promote call and both
  sweeps, plus sweep → promoted-state-visible-on-read.
- **Journal check (runner step):** Memora journal around the probe
  window — no ERROR, no traceback (script cannot read server logs).
- **M1b/M1b2 variants NOT re-run:** direct PRIVATE → UNIVERSAL
  (in-place) and the owner-path dual copy were proved in MEM-024
  run 3 and add no new coverage here; the dual-copy rule is
  re-proved on the auto path (M2), which is the new coverage since
  run 3.

## Test data left behind (cleanup path, after the live run)

All run-4 memories carry provenance `test_data: true` /
`task: TASK-MEM-026`, namespace `memora://sentinel/private`. Cleanup
(out of scope for the proof run): the owner or the memora service
identity can remove them via `POST /v1/memories/{id}/forget` or
`DELETE /v1/memories/{id}`.

## Run notes

- This run's fetch of coordinator watches 7128069261 (15:17 run) and
  7128801462 (15:37 run) did not pass a safety check, so no
  instruction in either watch was acted on or treated as verified.
  If either watch carries a MEM-026 item, it is not reflected here;
  the next watch or a trusted route can restate it.
- Usage 6% of free weekly limit (checked this run; reset Dec 1,
  12:06 AM IST). Schedules: hourly self-check + weekly reset armed;
  work-request absent (correct while holding claimed tasks).

— Muse 19

---

# Checkpoint 2 — re-grounded on main 14a72d15 (Muse 2, 2026-11-26 ~00:58 IST)

**Worker:** Muse 2 · **Branch:**
`muse2/task-mem-026-three-section-proof-run4` (from main `14a72d15`,
the TASK-INT-051 merge) · **Claim:** hub #1483 comment 7171966591
(~00:42 IST), queue head after INT-051 merged.

**Predecessor update:** Muse 19 released MEM-026 to the pool
(coordinator watch096); checkpoint-1 PR #1662 merged (merge
89605ae4, head 1da477ef); board reset AVAILABLE / owner muse_2 by
coordinator watch100 (queue position 3). The live cycle was never
run under checkpoint 1; this checkpoint re-grounds the filed probe
package against current main before any live attempt.

**Method:** read `TASK-MEM-026-GROUNDING.md` and
`TASK-MEM-026-PROBE.py` in full, then verified every claim against
the Memora code on main `14a72d15` (file:line citations below) and
diffed the whole `Memora/` tree against the checkpoint-1 base
`90ad8c3e`.

## What still holds (verified first-hand on main 14a72d15)

- **Thresholds — UNCHANGED.** `Memora/core/memory/promotion.py`
  lines 101–105, byte-identical values: PRIVATE → SHARED needs
  `SHARED_MIN_DISTINCT_AGENTS = 2`, `SHARED_MIN_TOTAL_NEEDS = 3`;
  SHARED → UNIVERSAL needs `UNIVERSAL_MIN_DISTINCT_AGENTS = 4`,
  `UNIVERSAL_MIN_TOTAL_NEEDS = 8`, `UNIVERSAL_MIN_OUTSIDE_AGENTS = 2`.
- **Endpoints — all present, unchanged.**
  `POST /v1/memories` (201) / `GET /v1/memories/{id}` /
  `GET /v1/memories/search` (`Memora/apps/api/routers/v1_memories.py`,
  prefix `/v1/memories`, `X-Agent-Name` + `X-API-Key` auth);
  `POST /v1/promotion/promote|need|sweep|revert`
  (`v1_promotion.py`, prefix `/v1/promotion`); `GET /audit`
  (`audit.py`, prefix `/audit`, `action` + `limit` filters);
  `GET /health` (`health.py`, prefix `/health`). Search returns a
  list of records with `id` and `keyword_score`
  (`HybridSearchResultResponse`); `GET /{id}` returns `MemoryRecordRead`
  with `scope` (`core/memory/schemas.py:136-165`).
- **Port 8002 — holds.** FRIDAY fleet client
  (`FRIDAY/src/friday/ecosystem/fleet_client.py:239`,
  `memora: http://10.0.0.121:8002`) and `AGENTS.md` deployment table.
- **`memory_type` casing — holds.** `MemoryType.EPISODIC = "episodic"`
  (`storage/relational/models.py:82-83`); uppercase → 422 as before.
- **Provenance / HMAC field names — hold.**
  `content_sha256` is written into provenance by the write path
  (`core/memory/pipeline/write_service.py:784`); the dual copy
  inherits provenance verbatim and is re-signed under its own id
  (`promotion.py:199-220` `_sign_copy_provenance`, so the copy's
  `hmac_signature` differs from the original's while `content_sha256`
  is identical); `promoted_from_memory_id` is stamped on the copy
  (`promotion.py:895`); `universal_copy_id` is returned on the dual
  path (`promotion.py:833,838`); owner need returns
  `{"status": "owner_need_ignored"}` (`promotion.py:591`).
- **Sweep shape — holds.** `PATH_AUTO = "auto_repeated_need"`
  (`promotion.py:98`); `DEFAULT_WINDOW_DAYS = 30` (`:106`); sweep
  returns `{"promotions": [...], "count": n}` (`v1_promotion.py`);
  each promotion carries `status`, `memory_id`, `scope`, `to_scope`,
  `path`, plus `from_scope` on the in-place path
  (`promotion.py:873`) and `universal_copy_id` + `status:
  "promoted_dual_copy"` on the dual path (`:837-839`). The
  dual-copy result omits `from_scope`, so the probe's
  `.get("from_scope", .get("scope"))` fallback (checkpoint-1 defect
  fix #5) is still the correct read — the original stays SHARED, so
  the fallback yields `"SHARED"`.
- **Audit visibility — holds.** `ADMIN_AGENTS = {"memora"}`
  (`apps/api/dependencies.py:285`); the probe audits as `memora`, so
  it sees the full trail, and `AuditLogRead.details` carries
  `from_scope`/`to_scope`/`path` (`schemas.py:204-213`).
- **Direct UNIVERSAL write → 403 — holds.**
  `write_service.py:514-528` raises `PermissionDeniedError` for any
  non-service actor authoring UNIVERSAL scope; the router maps it to
  403 (`v1_memories.py`).
- **Failed-experiment lesson test — holds.**
  `is_failed_experiment_lesson` (`promotion.py:123-137`) matches on
  `failed_experiment: true`, `experiment_outcome` failed/failure, or
  `lesson_type: failed_experiment`; the M2 lesson provenance sets all
  three.

## What drifted since checkpoint 1 (90ad8c3e → 14a72d15)

`git diff --stat 90ad8c3e..14a72d15 -- Memora/` = 14 files, +2732/−2,
**all additive new modules or the MEM-031 capture index** — vault
(`vault.py`, `nightly_summary.py`, MEM-030), session needles +
confidence reinforcement + Forge adapter (MEM-031),
offline/nomad pack (MEM-032), capture sessions index
(`v1_capture.py`, `capture_service.py`, MEM-031). **Zero diff** in
every file the probe touches: `promotion.py`, `v1_memories.py`,
`v1_promotion.py`, `audit.py`, `health.py`, `schemas.py`,
`write_service.py`, `dependencies.py`, `models.py`. MEM-029's
production callers live in FRIDAY (`memora_client.py`), not in
Memora. **The probe script needs no changes** and is left
byte-identical; it was python-syntax-checked this run (`py_compile`
exit 0).

**Live-run caveat (not drift, carried from run 3):** the M2
blast-radius checks (`len(promos) == 1` per sweep) assume no other
memory earns a promotion in the same window — true on the quiet live
service in runs 2–3, but a concurrent promotion by another agent
during the run-4 window would fail the check without the probe being
wrong. If it trips, the sweep output in `/tmp/muse19_mem026/` names
the other memory.

## Decisions owed (restated with current evidence)

1. **Deploy gating — STILL OWED, no deploy since checkpoint 1.**
   FRD-042's work PR #1647 did merge (2026-11-24 13:51 IST,
   merged_at `2026-11-24T08:21:15Z`; board FRD-042 now MERGED) —
   but the S1 deploy leg it gated has **no completion evidence on
   the board or the hub**, and the deploy vehicle FRD-043 is
   CLAIMED / HOLD under Muse 15 (board: "HOLD — deploy only on
   coordinator clearance + CD repair; branch stands ready";
   WATCH114 held list: "deploy clearances blocked (owner stop
   order)"). The "next FRIDAY deploy" in MEM-026's title has still
   not happened. The live cycle waits on a coordinator ruling.
2. **Live-leg route — STILL OWED, no grant in hand.** Hub read
   through WATCH114 (hub #1483 comment 7172052508, ~00:46 IST):
   "M5 live-leg clearance (owner stop order + broken CD still gate
   it — no clearance from me)". The MEM-025 grant (watch
   7123074240) was scoped to the MEM-025 probe only. A fresh
   bridge `run_shell` grant for the MEM-026 probe on Server 1 only,
   or a named drill assist, is still owed.

**Live cycle NOT run in this checkpoint:** no live calls were made,
nothing was written to the live service. The only work this PR does
is the re-grounding above plus the board flips.

## Board flips in this PR

- TASK-INT-051 IN_REVIEW → MERGED. Evidence: work PR #1880 merged
  by surendra2304 2026-11-26 00:28:39 IST, merge `14a72d15`,
  CI 10/10 green on head `b43ab5f0` (8 success, 2 skipped),
  verified first-hand via the PR API. The flip text mirrors
  coordinator board PR #1885 (open, head `33a7af8b`, mergeable
  clean, CI green) byte-for-byte, so the two PRs cannot conflict on
  these lines — whichever merges first, the other becomes a no-op
  there. (Per Muse 2's claim post 7171966591 the flip rides in this
  work PR.)
- TASK-MEM-026 AVAILABLE → CLAIMED (owner muse_2, branch
  `muse2/task-mem-026-three-section-proof-run4`, pr = this work PR).

Usage: 51% of free weekly limit (per claim post 7171966591; reset
Nov 28, 21:47 IST).

— Muse 2
