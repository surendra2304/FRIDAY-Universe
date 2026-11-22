# TASK-FRD-037 — FRIDAY chat: prove M5 workflow 1, 3 consecutive live runs through FRIDAY chat

Owner: Muse 10. Assigned: coordinator assignment 7083871277 (~00:17 IST, 2026-11-23), on work request 7083828691. Branch: `muse10/task-frd-037-chat-live-runs`. Status: BLOCKED (0/3 live runs) — production chat 401, re-probed 02:06 IST, skipped to TASK-MEM-018 per coordinator follow-up 7084721822.

## Claim

- Claim comment: issue #35 comment 7084019535 (~00:29 IST).
- Board record: created in this work PR from main blob `081f6189` (pool-10 filing rides in the next consolidated board PR). Status CLAIMED, owner `muse_10`.
- Work-request cycle stands down while claimed.
- Correction noted (assignment 7083871277): TASK-FRG-002 is NOT complete — route merged (PR #1401, `fd4fb046`), acceptance count stands 0/3, deploy step owed (clearance-gated; deploy plan to follow when ready). Its board record stays IN_REVIEW under me.

## Live runs: 0/3

- Production chat path: https://friday-universe.duckdns.org/friday/ (per MASTER_PLAN §3). Each run: a real multi-turn chat conversation with FRIDAY, recorded with its trace (request, routing, agent evidence, result). A wrong answer presented as success resets the count.

## Run 1 — (pending)

## Run 2 — (pending)

## Run 3 — (pending)


## Blocker — production chat 401 (2026-11-23)

- Run 1 of 3 FAILED. `POST https://friday-universe.duckdns.org/friday/api/chat` returns HTTP 401 `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.","detail":"A valid FRIDAY control API key is required.","success":false}` on every send. Seen 00:37 IST (two attempts), re-probed 01:09 IST (identical), re-probed 02:06 IST (identical, hub 7085500872). Console `GET /friday/` still 200. No FRIDAY reply on any attempt; the message never reached any agent. Live runs 0/3.
- Correct send path is `/friday/api/chat` (confirmed from the console's own JS chunk this run; a first probe at the guessed `/friday/api/chat/send` returned 405 and does not count).
- Blocker posted on the hub 2026-11-23 ~01:10 IST (comment 7084601978). Coordinator follow-up 7084721822 (~01:19 IST) grants bounded read-only diagnosis clearance (health/journal/process reads + chat-path probe only; no credential reads, no config changes, no restarts, no deploys) and orders: if the 02:06 IST re-probe still fails, skip to queue position 1 (TASK-MEM-018) and keep FRD-037 as blocked-head — the coordinator re-slots it next run. The 401 fix itself is in Muse 11's scope (MEM-017); the clearance is held, not exercised this run, so the same key path is not diagnosed twice.
- OBS-009 note: the 02:06 IST re-probe is complete and no fleet-touching 401-diagnosis work is in flight from Muse 10 (hub 7085500872), satisfying condition (a) of the OBS-009 conditional grant (watch 7085314708) from my side.

— Muse 10
