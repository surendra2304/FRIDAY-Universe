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
