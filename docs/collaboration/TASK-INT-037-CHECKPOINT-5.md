# TASK-INT-037 — Checkpoint 5: raw grep counts filed, leg 3 satisfied, CI 10/10 green

Filed 2026-11-24 ~17:10 IST, Muse 3. Branch `muse3/task-int-037-futuris-cursor-401s`.
PR #1661 head at filing: `d30d4447` (guard + tests + checkpoint 4).

## 1. Raw grep counts — LANDED (M8, hub comment 7129770264, ~16:30 IST)

M8's live S1 run ~13:05 IST, read-only `journalctl -u Memora.service`
(grant: watch 7124945395 ruling 5). Raw outputs kept in M8's workspace
(`~/workspace/muse8/mem-025/j_*.json`); counts filed verbatim here:

- Coverage window: **08:41:52 → 12:59:26 IST (~4h17m)**; 15,819 unit lines.
  The 24h window is NOT retained (journal rotation) — stated plainly.
- `consumer_id=futuris-cloud-v1` requests: **949**.
- True HTTP 401 statuses: **0** (first/last: none).
- The 5 loose "401" grep hits, verbatim — all are source ports on 200-OK lines:
  - `2026-11-24T09:34:20+0530 friday-universe-vnic python[3424928]: INFO: 10.0.0.120:40102 - "GET /v1/events/cursor?consumer_id=futuris-cloud-v1 HTTP/1.1" 200 OK`
  - `2026-11-24T10:32:58+0530 friday-universe-vnic python[3424928]: INFO: 10.0.0.120:40130 - "GET /v1/events/cursor?consumer_id=futuris-cloud-v1 HTTP/1.1" 200 OK`
  - `2026-11-24T10:33:58+0530 friday-universe-vnic python[3424928]: INFO: 10.0.0.120:40114 - "GET /v1/events/cursor?consumer_id=futuris-cloud-v1 HTTP/1.1" 200 OK`
  - `2026-11-24T11:49:34+0530 friday-universe-vnic python[3503374]: INFO: 10.0.0.120:40164 - "GET /v1/events/cursor?consumer_id=futuris-cloud-v1 HTTP/1.1" 200 OK`
  - `2026-11-24T12:12:18+0530 friday-universe-vnic python[3503374]: INFO: 10.0.0.120:40118 - "GET /v1/events/cursor?consumer_id=futuris-cloud-v1 HTTP/1.1" 200 OK`

This closes the "raw grep counts owed" item from checkpoint 3 §5 and the
15:05 hourly status. Summary counts were already in M8's hub comment
7125210506 (~13:08 IST); the raw lines above are the filing the ruling asked for.

## 2. Leg 3 — three consecutive scheduled cycles at zero cursor 401s: SATISFIED

Per the ruling (watch 7126818611, 14:17 run): "cycle" = IntelX scheduled
research cycle (AutonomousResearcher, RESEARCH_CHECK_INTERVAL_SECONDS = 900,
15 min); observation = M8's 15 s poll windows aggregated per cycle.

- Window 08:41:52 → 12:59:26 IST = 15,454 s ≈ **17.2 cycles** (15-min cycles).
- 949 cursor requests in the window ≈ 55 polls/cycle (15 s poll interval).
- True 401s: **0 in every cycle** — 17 consecutive clean cycles, exceeding the
  three-consecutive-cycles bar. No cycle in the window shows a 401.
- Caveat (unchanged): the journal retains only ~4h17m, so the window cannot be
  re-derived for an earlier period; the verbatim lines above are the durable
  record. No fresh S1 probe was run this cycle — none is needed for leg 3.

## 3. Acceptance legs — status at filing

- Leg 1 (401 source named with log evidence): DONE. Stale
  FUTURIS_MEMORA_API_KEY → Memora `authenticate_agent` rejection; live fix
  2026-11-23 ~16:14 IST (FUT-022); 0 true 401s in 949 requests since
  (checkpoint 2 + §1 above).
- Leg 2 (a fix is merged): PENDING MERGE. PR #1491 (FUT-022) is the live fix
  but its diff carries no code change (checkpoint 3 §3). The durable code
  guard is PR #1661 (this branch) — see §4.
- Leg 3 (three consecutive scheduled cycles, zero cursor 401s): SATISFIED
  per §2 (17 consecutive clean cycles in M8's window).

## 4. PR #1661 — CI 10/10 green, merge deferred to Muse's next run

Verified first-hand this run via the check-runs API on head `d30d4447`:
10 runs, 8 success, 2 skipped, 0 failed — entrypoints, monorepo policy,
test, workload images, roster/task-ID validation, fleet layout,
detect-voice-changes, secrets scan all success; docker + voice-regressions
skipped. `mergeable: true`, `mergeable_state: clean`. State open, not merged.

Coordinator watch 7130069033 (16:37 run): merges of #1661 and #1662 DEFERRED
this run — the bridge files endpoint failed 4/5 attempts on each and the
alternate git diff route hit a security flag, so no diff review was possible.
"Next run retries the diff read and merges. Not a worker fault; no action
needed from M3/M19." No action taken by Muse 3 on the PR this run; merge
awaits Muse + a successful diff review. Never merge own PR.

Note: M8's STR-047 PR #1663 carries a pre-existing Forge time-bomb test
failure in the `contracts` job (test freezes NOW 2026-11-23 10:32 UTC; wall
clock has passed the 24h stale bound). #1661 does NOT run a `contracts`
check — its 10 check-runs are all green/skipped, so that failure does not
touch this PR.

## 5. Owner stop order — noted, no INT-037 impact

Owner stop order ~16:42 IST (watch 7130069033): "Don't move anything now,
keep as it is how it is now." ALL server moves FROZEN until the owner's
explicit word. Other work continues. INT-037 needs no server move: the guard
is repo-side, the evidence is already filed, the merge is a repo action.
No live change attempted or planned by Muse 3.

## 6. Live state re-verified this run (bridge, S2 read-only)

- Both Oracle servers ONLINE (`get_system_info`; S2 git `23e146b9`, trails
  main `428a0ea5` — expected, S2 parked on worker branch).
- `IntelX/data/watches/outbox.jsonl`: **1,823 bytes** (same 2 digest
  envelopes, no instant alert) — via `list_directory` (read_file transport
  failed twice this run: "MCP event stream ended" / "request did not
  complete"; bridge transport still flaky, as in watch 7130069033).
- `IntelX/data/watches/state.json`: **1,269,513 bytes** (was 1,265,976 at
  16:05 IST — polling continues). CORRECTION to earlier notes: the file
  lives at `IntelX/data/watches/state.json`, NOT `IntelX/data/state.json`
  (that path returns "File not found" — my path error this run, not a
  missing file).
- Board re-verified first-hand on main `428a0ea5` (blob `2726ad92`,
  18,865 lines): INT-037 CLAIMED / owner muse_3 / branch correct /
  pr null / P1.

## 7. Open items (unchanged)

- PR #1661 merge — Muse's next run (diff review retry).
- After merge: board MERGED flip rides in the coordinator consolidated board
  PR (one-per-day rule; next files 2026-11-25 first run per watch 7129798495).
  Then queue head moves to REL-090.
- Usage 22% (reset Nov 28, 11:24 AM IST). Cron: self-check + weekly-reset
  armed; work-request absent (correct while mid-task).

— Muse 3
