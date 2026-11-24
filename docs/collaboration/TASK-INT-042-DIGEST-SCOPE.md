# TASK-INT-042 — Digest end-to-end: scope checkpoint 1

- Task: TASK-INT-042 — one real IntelX digest end-to-end, kill switch OFF.
- Claim: hub #1483 comment 7132849658 (2026-11-24 ~18:57 IST).
- Branch: `muse12/task-int-042-intelx-digest-end-to-end`, fast-forwarded this run
  404f5014 → d86b4b92 (main at checkpoint time; compare: ahead 9, behind 0,
  merge-base 404f5014 — verified first-hand via the compare API).
- Stall repaired: zero work commits in the ~1 h after claim (branch still at
  claim base, no PR). This checkpoint is the first work commit. No code
  changed; this file maps the path and pins the gates from first-hand reads.
- Usage at checkpoint: 17% of free weekly limit (subscription-status, fresh
  this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.

## End-to-end path (read first-hand on main d86b4b92)

1. **Producer (IntelX):** `IntelX/intelx/watches/engine.py` —
   `WatchService.poll_once` fetches feeds, scores items, `build_envelope`
   (L734, `alert_class="digest"` by default; `"instant"` only when the
   score reaches the watch's `instant_min_score`) appends the envelope to
   the outbox (`data/watches/outbox.jsonl`). `IntelX/intelx/watches/run_once.py`
   runs one poll on demand. Default watch `ai_model_releases` is
   `enabled=True` (engine.py L174; live proof passed 2026-11-15/16: 1 alert +
   1 cap-suppressed, dedupe exact, zero false positives); the other declared
   watches are `enabled=False` pending their own live proofs.
2. **Transfer (S2 → S1):** the only mechanism is the TASK-INT-040 shipper
   (`IntelX/intelx/watches/outbox_shipper.py`, work PR #1672, head `2f2fe6bd`,
   open). It tails the S2 outbox by byte offset and appends new lines to the
   S1 outbox; `audit()` compares source vs destination envelope_ids and
   reports MISSING explicitly.
3. **Consumer (S1 FRIDAY):** `FRIDAY/src/friday/proactive/intelx_watch.py` —
   the drainer tails the S1 outbox and posts each envelope through the real
   notification path (`NotificationManager`). Digest-class envelopes carry
   `quiet_hours_exempt=false`, so in quiet hours (23:00–07:00 IST) they are
   held and flush as ONE digest notification at/after 07:00 (`_flush_held`,
   L415). Delivered keys persist, so a key is delivered at most once ever.

## Kill switch — pinned

- The kill switch is the `FRIDAY_PROACTIVE_INTELX_WATCH` env flag, read by
  `drain_enabled()` (`intelx_watch.py` L96). Code default is OFF (fail-safe);
  enabling it in production is a separate coordinator step
  (`IntelX/docs/STANDING_WATCHES.md` §7). "Kill switch OFF" therefore means
  the drainer is inert: no owner notification posts.
- Consequence for acceptance: with the switch OFF, `run_cycle` returns early
  (`enabled: False`) and never reads the outbox. A kill-switch-OFF proof run
  can verify poll → envelope → outbox → ship → S1 outbox arrival, but NOT
  the post through `NotificationManager`. The delivery proof needs the flag
  ON (coordinator step) after the first-cycle silent baseline: envelopes
  already sitting in the outbox on a fresh drainer state are recorded as
  seen, never announced.

## Gates on the live leg (all still closed at checkpoint time)

1. **Owner stop order 16:42 IST still in force.** M11 status 19:48 IST:
   GO-vs-freeze conflict unresolved; M14 status: OBS-018 leg (b) still
   frozen. No live dispatch and no flag enablement until the owner lifts it.
2. **Shipper PR #1672 HELD on rebase.** Per the 19:37 coordinator watch
   (hub 7134320067): Muse 5 must rebase onto current main, restore both
   FUT-029 files, re-green CI, then merge. Until #1672 lands there is no
   merged S2 → S1 transfer mechanism.
3. **Oracle consolidation (~19:47 IST) may change the topology.** Per the
   19:37 watch: Server 1 now holds all 10 agents; Server 2 holds only the
   bridge + the fleet repo checkout + CREDENTIALS.md. The agent-map update
   rides in the consolidated board PR. Whether IntelX now runs on S1 (which
   would make the shipper moot — shared filesystem, drainer tails the local
   outbox directly) is UNVERIFIED. Asked Muse in the status post.
4. **S2 IntelX runtime location NOT FOUND via bridge read tools this run.**
   Bridge `get_system_info`: both servers ONLINE; S2 checkout commit
   `09603dff` (stale vs main d86b4b92). `list_directory` on the S2 workspace
   root shows no `IntelX/` directory; `IntelX/data`, `IntelX/data/watches`
   and workspace-root `data/watches` all return "Directory not found". The
   S2 outbox file `IntelX/data/watches/outbox.jsonl` is not reachable through
   the bridge read tools. The live leg needs S2 shell access (clearance-gated)
   or the coordinator's direction on the post-consolidation layout.

## What the live proof needs (when the gates clear)

Real poll of `ai_model_releases` → digest envelope in the S2 outbox →
shipper → S1 outbox → drainer cycle with the flag ON after baseline →
posted digest (or held → flushed as one digest at/after 07:00 IST if fired
in quiet hours). Each hop must be observed, not assumed; the shipper's
`audit()` and the drainer's persisted `delivered_keys` are the loss checks.

## Queue

- INT-042 (head, this task) → FUT-028 (held, empty cohort; hold-vs-re-scope
  ruling still owed) → FUT-030 (parked to Nov 25) → STR-061 (queued).
- Implementation-push pool (30 tasks) not yet landed at checkpoint time; when
  it lands, queues refill from it first (Stratex/VyralX first).

## Checkpoint 2 — 20:53 IST hourly self-check (2026-11-24)

- No new work commit since checkpoint 1 (5f9c450b, 20:05 IST); live leg still
  gated on external decisions, so this checkpoint records the changed gate
  state first-hand. No code changed.
- **Gate 2 MOVED — shipper rebase landed:** PR #1672 CLOSED unmerged
  (~20:36 IST, superseded). Replacement PR #1676 (Muse 15, branch
  `muse15/task-int-040-envelope-shipper-rebase` @ `dd77835e`, base
  `36c8e857`) is OPEN, mergeable True, CI 10/10 verified first-hand this
  run (8 success, 2 skipped: docker, voice-regressions). INT-040 now owned
  by Muse 15 per the 20:17 coordinator watch (7135284142). Live leg now
  waits on #1676 merging, not on #1672.
- **Gate 1 unchanged — owner stop order still in force.** M13 status 20:36
  IST and M2 status 20:37 IST both confirm; 20:17 watch restates the hold.
  No live dispatch, no flag enablement.
- **Gate 3 sharpened — S2 producer stopped.** M1 status 19:52 IST (hub
  7134523678): Oracle consolidation stopped the S2 producer — "fast lane
  no longer armed anywhere; direction owed from Muse". M18 status 20:20
  IST: S2 VyralX/Futuris gone. If IntelX no longer runs on S2, the
  poll → S2-outbox → shipper leg may not exist in its old form at all, and
  the digest proof may need to run wherever IntelX now lives. Asked Muse
  in the status post: confirm IntelX's post-consolidation home before any
  live leg is attempted.
- **No Muse 12 directive in the 20:17 watch** (7135284142, read in full):
  no re-slot, no new assignment. Implementation-push pool still not landed
  (deadline 00:00 IST tonight); queues refill from it first when it lands.
- Branch now behind main by 6 (main `36c8e857`); no rebase this run —
  rebase at work-PR time. No work PR yet: board record + flip ride in it.
- Usage at checkpoint: 18% of free weekly limit (subscription-status,
  fresh this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.
- Work-request task muse12-work-request stays cancelled (mid-task).
  Hourly self-check + weekly reset verified armed this run.

## Checkpoint 3 — 21:53 IST hourly self-check (2026-11-24)

- Owed verification DONE this run (20:57 watch, hub 7136585984): the
  read-only, first-hand check of the outbox path + watch state on
  IntelX-Server. No code changed; gate state only.
- **Gate 2 CLEARED — shipper merged:** PR #1676 MERGED (merge `4bc4159c`,
  2026-11-24T15:29:47Z / 20:59:47 IST), coordinator-merged by the 20:37
  watch (hub 7136251890) after a full-diff review + `git merge-tree`
  simulation proving the merged tree intact. INT-040's shipper code is now
  on main — but see the re-scope note below: its S2 source no longer exists.
- **Gate 3 RULED — IntelX lives on IntelX-Server:** 20:57 watch
  (7136585984): IntelX + Futuris moved to IntelX-Server (32.236.185.237)
  ~19:12 IST, production-verified — watches cycling with synced state
  there. Oracle Server 1 holds only a sleeping copy (IntelX.service MASKED
  + failed since Nov 20); Oracle Server 2 holds nothing but the bridge +
  repo checkout. The poll → S2-outbox → shipper leg in its OLD form does
  NOT exist: S2 producer stopped clean 19:09:21 IST,
  `/opt/friday_universe/IntelX` absent on S2.
- **Verification (read-only, first-hand, this run — bridge `read_text`,
  server=6):**
  - Outbox path EXACT: `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`
    on IntelX-Server (32.236.185.237). 3 envelopes, all `alert_class`
    `digest`, `quiet_hours_exempt` false. Tail-read from line 4 returns
    empty — exactly 3 lines total.
  - Envelope 1: `ai_model_releases`, fired 2026-11-20T18:26:48Z (Hugging
    Face harness adapters, score 4).
  - Envelope 2: `india_tech_regulatory`, fired 2026-11-23T16:33:10Z (RBI
    stop switch, score 5).
  - Envelope 3: `india_tech_regulatory`, fired 2026-11-24T14:30:07Z
    (20:00:07 IST, SEBI GMP, score 3) — AFTER the ~19:12 IST move and
    after the S2 producer stop (19:09:21 IST). This is the cycling proof:
    the poll loop runs on IntelX-Server with synced state, not a stale copy.
  - State file: `/opt/friday_universe/IntelX/data/watches/state.json`,
    version 1. The `ai_model_releases` seen map matches the Nov 20 poll
    (`first_seen` 2026-11-20T18:26:50Z, baseline entries). The
    `india_tech_regulatory` section was not reached in the read window
    (large baseline load); its fires are proven by the outbox itself.
  - Enabled watches on current main (`IntelX/intelx/watches/engine.py`,
    read first-hand): `ai_model_releases` (L174, enabled=True) AND
    `india_tech_regulatory` (L298, enabled=True, live proof passed
    2026-11-15/16). CORRECTION to checkpoint 1: TWO watches are enabled,
    not one — both have fired envelopes in the IntelX-Server outbox.
  - Route note: `bridge.py` allow-list extended with `read_text`
    (read-only, `server` param) for this coordinator-directed verification;
    write tools (`run_shell`, `edit_file`, `write_file`, restarts) remain
    blocked without Muse clearance.
- **Gate 1 UNCHANGED — owner stop order still in force.** M13 status
  21:36 IST and M2 status 21:37 IST both confirm; no lift in any watch
  through 21:17 (hub 7137288514). No live dispatch, no flag enablement.
- **Re-scope consequence:** INT-040's shipper tails the S2 outbox, which
  no longer exists — the transfer leg must be re-pointed at the
  IntelX-Server outbox (or the drainer reads it where it now lives) before
  any live leg is scoped. Drainer offset defect carried from the 20:57
  watch: offset 3644 > outbox 1823 B — restart behaviour against the
  shrunk outbox is unverified; it is a re-scope item for the live legs.
- **Live leg now waits on:** gate 1 lifting. The "verified armed on
  IntelX-Server" half of the 20:57 ruling is satisfied for the producer
  side (20:00 IST envelope); the drainer/flag side on the new home is
  still unscoped and frozen.
- **Pool model (owner directive 7136890552, ~21:25 IST):** queue is now
  INT-042 (current) + STR-064 (pre-staged next, P2, BSM-vs-market option
  mispricing scan — research report, no trading; verified AVAILABLE /
  owner null on main `cc66b42d`, no hub claim through the 21:17 watch).
  FUT-028 RELEASED this run (blocked, empty cohort, ruling owed — board
  flip AVAILABLE / owner null rides in the consolidated board PR).
  FUT-030 is in the central pool now. Aggressive burn order (7137435150)
  noted: usage 18% is low against a full-week burn; INT-042's live leg is
  frozen, so progress stays read-only until the freeze lifts.
- Branch now behind main by 19 (main `cc66b42d`); no rebase this run —
  rebase at work-PR time. No work PR yet: board record + flip ride in it.
- Usage at checkpoint: 18% of free weekly limit (subscription-status,
  fresh this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.
- Work-request task muse12-work-request stays cancelled (mid-task).
  Hourly self-check + weekly reset verified armed this run.

## Checkpoint 4 — 22:53 self-check (~23:00 IST, 2026-11-24)

- Outbox re-read (bridge `read_text`, server=6, first-hand this run): still
  exactly 3 envelopes; latest fired 2026-11-24T14:30:07Z (20:00:07 IST, SEBI
  GMP) — NO new digest material since checkpoint 3 (~3 h). Producer still
  cycling (polls firing, alerted=0 per M1 18:52 status); nothing new to drain.
  Verified negative, not absence of check. One bridge flake on the first
  attempt (`RemoteDisconnected` at initialize); retry succeeded — matches the
  22:17 watch LAG item 9 (bridge endpoints flaking).
- **Gate 1 UNCHANGED — owner stop order still in force.** No lift in the
  21:57 watch (7138466832) or the 22:17 watch (7138911209). M2 released
  VOI-036 this hour because its run leg stays held under the stop order. No
  live dispatch, no flag enablement.
- New direction read this run: 21:57 watch ruling 3 — read-only live legs are
  NOT moves and proceed now under the owner's implement-all order; this
  checkpoint's read-only verification sits inside that ruling. Owner scope
  clarification 7138538710 (pull model, cap 2: 1 current + 1 pre-staged) —
  holdings compliant: INT-042 current + STR-064 pre-staged. 22:17 watch
  ruling 5 — do NOT re-attempt the flagged WORKER_PROMPT re-read; no re-read
  attempted, working under the verified directives already in force.
- STR-064 re-verified on current main `3a2009b8` (board blob 21,025 lines,
  first-hand via git blob API; contents API returns empty above 1 MB):
  AVAILABLE, owner null, branch null, pr null, P2, title 'BSM-vs-market
  option mispricing scan - ranked research report, no trading'. Pre-staged
  next intact. No hub claim for STR-064 in the last 100 comments.
- Branch now behind main by 31 (main `3a2009b8`); no rebase this run — rebase
  at work-PR time. No work PR yet: board record + flip ride in it.
- Usage at checkpoint: 18% of free weekly limit (subscription-status, fresh
  this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.
- Work-request task muse12-work-request stays cancelled (mid-task). Hourly
  self-check + weekly reset verified armed this run.

## Checkpoint 5 — 23:53 self-check (2026-11-24)

- Outbox re-read (bridge `read_text`, server=6, first-hand this run): still
  exactly 3 envelopes; latest fired 2026-11-24T14:30:07Z (20:00:07 IST, SEBI
  GMP) — NO new digest material since checkpoint 3 (~4 h). Verified
  negative, not absence of check. One self-inflicted arg error on the first
  attempt (sent `filepath`; the tool expects `path`) — retry with `path`
  succeeded; not a bridge outage.
- **Gate 1 UNCHANGED — owner stop order still in force.** No lift in the
  22:57 watch (7140361664, read in full). No Muse 12 directive in it. TP3's
  live-trial clearance request for VYR-077 is HELD under the same order.
  INT-032 timer install + IntelX home still await owner clearance (watch
  LAG item 4). No live dispatch, no flag enablement.
- 22:57 watch notes: main head now `28efad19` after coordinator merges
  #1688–#1693 (all CI green, full-diff reviewed first-hand). Burn list
  shows M12 at 18% (stale — fresh 19% this run, see below). STR-068
  duplicate-claim ruling (M20 holds, TP4 releases) does not touch INT-042.
- STR-064 re-verified on current main `28efad19` (board blob 21,039 lines,
  first-hand via git blob API): AVAILABLE, owner null, branch null, pr
  null, P2, title 'BSM-vs-market option mispricing scan - ranked research
  report, no trading'. Pre-staged next intact. STR-061 still has NO board
  record on main (re-slot noted in the watch only).
- Branch now behind main by 52 (main `28efad19`); no rebase this run —
  rebase at work-PR time. No work PR yet: board record + flip ride in it.
- Usage at checkpoint: 19% of free weekly limit (subscription-status,
  fresh this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.
- Work-request task muse12-work-request stays cancelled (mid-task). Hourly
  self-check + weekly reset verified armed this run.

## Checkpoint 6 — 00:53 self-check (2026-11-25)

- Outbox re-read (bridge `read_text`, server=6, first-hand this run): still
  exactly 3 envelopes; latest fired 2026-11-24T14:30:07Z (20:00:07 IST, SEBI
  GMP) — NO new digest material since checkpoint 3 (~5 h). Verified
  negative, not absence of check. First attempt failed with IncompleteRead
  (bridge transport flaking — matches both watches' LAG item 1); retry
  succeeded.
- **Gate 1 UNCHANGED — owner stop order still in force.** No lift in the
  23:57 watch (7141455808, read in full) or the 00:17 watch (7141869992,
  read in full). No Muse 12 directive in either. INT-032 timer + IntelX
  home still await owner clearance (LAG item 7 in both). No live dispatch,
  no flag enablement.
- Watches this run: 23:57 watch merged #1703/#1698/#1700, ruled STR-075
  CLOSED, assigned FUT-017→M5 and SEN-022→M6 (not M12). 00:17 watch merged
  #1695/#1694/#1701/#1708/#1711; main head now `dfbe6ce3`. Consolidated
  board PR still owed (first item next run) — INT-042's board record still
  rides in my work PR.
- STR-064 re-verified on current main `dfbe6ce3` (board blob 21,051 lines,
  first-hand via git blob API): AVAILABLE, owner null, branch null, pr
  null, P2, title 'BSM-vs-market option mispricing scan - ranked research
  report, no trading'. Pre-staged next intact. STR-061 still has NO board
  record on main. INT-042 still has no board record on main.
- Branch now behind main by 82 (main `dfbe6ce3`); no rebase this run —
  rebase at work-PR time. No work PR yet: board record + flip ride in it.
- Usage at checkpoint: 19% of free weekly limit (subscription-status,
  fresh this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.
- Work-request task muse12-work-request stays cancelled (mid-task). Hourly
  self-check + weekly reset verified armed this run. FUT-019 / FUT-026
  scoring runonce jobs still armed (Nov 25 / Nov 26 10:00 IST).

## Checkpoint 7 — 01:53 self-check (2026-11-25)

- Outbox re-read (bridge `read_text`, server=6, first-hand this run): still
  exactly 3 envelopes; latest fired 2026-11-24T14:30:07Z (20:00:07 IST, SEBI
  GMP) — NO new digest material since checkpoint 3 (~6 h). Verified
  negative, not absence of check. Single attempt succeeded (no IncompleteRead
  this run).
- **Gate 1 UNCHANGED — owner stop order still in force.** No lift in the
  00:37 watch (7142399844), the 00:57 watch (7142822375), or the 01:17 watch
  (7143301930), all read in full. No Muse 12 directive in any of them.
  INT-032 timer install + IntelX home still await owner clearance
  (watch054 LAG item 7). No live dispatch, no flag enablement.
- **STR-064 REASSIGNED — no longer my pre-staged next.** Watch054 ruling 1:
  STR-064 → M15 (free, pre-staged too). Reserve order if M15's claim lapses:
  M16 (earliest pre-stage), then M12. Watch056: M15 STR-064 still unclaimed
  after the one nudge — no second nudge per rule; watch next run. My queue
  is now INT-042 only; STR-064 is second reserve. STR-061 still has NO board
  record on main (carried).
- Watches merged since checkpoint 6: #1710 (VYR-056) + #1705 (VYR-075) in
  watch054; #1709 (VYR-077) + #1712 (VYR-072) in watch056. Main head now
  `b0276946`. Watch054 correction: watch052's FUT-017/SEN-022 assignments
  VOID (both already MERGED) — does not touch INT-042.
- Branch now behind main by 101 (main `b0276946`); no rebase this run —
  rebase at work-PR time. No work PR yet: board record + flip ride in it.
- Usage at checkpoint: 19% of free weekly limit (subscription-status, fresh
  this run; reset Nov 29 6:04 PM IST). Not nearly gone — no wrap-up.
- Work-request task muse12-work-request stays cancelled (mid-task). Hourly
  self-check + weekly reset verified armed this run.
