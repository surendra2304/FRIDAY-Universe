# TASK-INT-037 — S1 Memora journal evidence (checkpoint 2)

Task: IntelX — root-cause and fix the Futuris cursor 401s so scheduled research
cycles stop failing auth. Owner: Muse 3. Branch:
`muse3/task-int-037-futuris-cursor-401s`. Filed 2026-11-24 ~14:05 IST.

## The journal evidence (filed by Muse 8, verified first-hand here)

- Probe: Muse 8 live run 3, ~13:05 IST 2026-11-24, granted S1 route
  (coordinator watch 7124945395 RULING 5: the S1 Memora journal probe leg was
  re-slotted from Muse 3 to Muse 8, watch 7123816690).
- Result, M8's words (hub #1483 comment 7126149734, ~13:53 IST):
  "INT-037 journal: 0 true 401s in surviving ~4h17m (949 requests)."
- Corroborated from a second read: the MEM-025 board record on main
  `d953ad4a` (blob `1e73dd2f`, 18,761 lines, read via git blobs API this run)
  carries the same line verbatim in its evidence list.
- Context of the run: same S1 session verified lesson `b5bfbf85`
  PRIVATE -> SHARED -> UNIVERSAL and dual copy `32c9ed6e` (MEM-025 live run 3);
  the journal count is the INT-037 leg of that run.

## What this establishes

- Post-FUT-022-fix live rate for the Futuris cursor path is 0 true 401s over
  a ~4h17m surviving journal window covering 949 requests
  (`GET /v1/events/cursor?consumer_id=futuris-cloud-v1`, 15 s poll).
- Together with checkpoint 1 (alias-chain read, commit `9f3c9ab6`) and FUT-022
  (merged PR #1491), the 401 source is now named with log evidence on both
  sides: the storm leg (174 cursor 401s in 45 min before 16:07 IST
  2026-11-23, FUT-022 evidence doc) and the post-fix leg (0 in 949, this
  document). Rejecting check: Memora `authenticate_agent` —
  `hmac.compare_digest` against the registry value for agent `futuris`;
  the presented value was the stale `FUTURIS_MEMORA_API_KEY` from the
  Futuris `.env` on S2, removed live 2026-11-23 ~16:14 IST (FUT-022).

## What this does NOT establish (open questions for Muse)

1. "True" 401s is M8's qualifier, not a defined count. The raw grep counts
   (total 401 lines in the window, split by consumer/path) were not filed.
   If the acceptance needs the raw numbers, ask M8 for them — do not assume
   0 total 401s.
2. Leg 2 — "a fix is merged": FUT-022's fix was a live env edit + service
   restart, not a code change; its PR #1491 (merged) carries the root-cause
   doc. Checkpoint 1 proved the alias-chain order is deliberate
   (MEM-005-R2 test) and must NOT change. So: is PR #1491 the merged fix
   for this acceptance, or is a new durable code guard owed (e.g. startup
   validation that the presented key is accepted, or a regression test)?
   No code change is filed in this checkpoint — the chain-order change
   hypothesised earlier is wrong and stays out.
3. Leg 3 — "three consecutive scheduled IntelX/Futuris cycles run with zero
   cursor 401s": the word "cycle" is undefined. M8's window already covers
   ~1,000 consecutive clean 15 s cursor polls. If "cycle" means the 15 s
   cursor poll, leg 3 is effectively satisfied by this window; if it means
   IntelX scheduled research cycles, those need a definition and a way to
   observe them (the IntelX outbox has held at the same 2 digest envelopes
   since 2026-11-20; `state.json` polling continues, 1,257,794 bytes this
   run).

## State this run (verified first-hand, 2026-11-24 ~14:05 IST)

- Board on main `d953ad4a` (blob `1e73dd2f`): INT-037 CLAIMED / owner muse_3
  / branch `muse3/task-int-037-futuris-cursor-401s` / pr null / P1.
- Branch tip still `9f3c9ab6` before this commit (checkpoint 1); no new
  commits since 02:05 IST — the wait was on the journal probe, which has
  now landed (this checkpoint files it).
- Bridge: both Oracle servers ONLINE; S2 git `51084d19`. S2-side check:
  `IntelX/data/watches/outbox.jsonl` 1,823 bytes, same 2 digest envelopes,
  no instant alert (`instant_outbox.jsonl` absent); `state.json`
  1,257,794 bytes (polling continues). Note: bridge `read_file` truncates
  large files (returned 23,132 bytes for `state.json`); sizes above are
  from `list_directory` with `subpath`, which is the correct argument —
  `path` silently lists the workspace root.
- Usage: 20% (coordinator burn list, watch 7126072996, 13:37 run); reset
  Nov 28, 11:24 AM IST. Cron: self-check + weekly-reset armed;
  work-request absent (correct while mid-task).

## Next

Await Muse's ruling on open questions 2 and 3 above (merged-fix scope and
cycle definition). No live change, no restart, no chain-order change.
Checkpoint 2 is evidence filing only.

— Muse 3
