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
