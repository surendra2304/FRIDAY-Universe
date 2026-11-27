# TASK-FRD-064 — Checkpoint 3: floor quantification (live numbers)

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns` (@ `f0d575f1`).
**Probed:** 2026-11-27 ~17:56–18:05 IST (12:26–12:35 UTC), bridge Server 3 = FRIDAY-Server,
Server 2 and Server 1 sweeps, first-hand, read-only throughout.
**Board on live main `f0d575f1`:** CLAIMED / owner `muse_tp1` / pr null / P1.
Board note (unchanged, correction still owed in the coordinator's board PR):
the record's `branch` field reads `musetp1/task-frd-064-oom-kill-root-cause`;
the real branch is `musetp1/task-frd-064-oom-kills-chat-turns` (verified via
ref read-back: head `10646a4a`). WEB-007 (PR #2075, merge `bb503981`) and
FRD-062 (PR #2108, merge `ff08b859`) both verified MERGED via the PR API.

## 1. Live state now (Server 3, FRIDAY-Server)

- `FRIDAY.service`: active / running, MainPID `100296`, active since 09:37:09 UTC
  (~8 h stable). `MemoryCurrent=39,571,456` (~37.7 MB) / `MemoryMax=209,715,200`
  (200M) / `MemorySwapCurrent=131,149,824` (~125 MB) / `MemoryPeak=209,715,200`
  (the 200M cap was touched at least once this activation).
- `/proc/100296/status` at ~12:26 UTC: `VmRSS 74,180 kB`, `VmSwap 128,076 kB`,
  `VmSize 1,128,088 kB`, `VmPeak 1,192,600 kB`. `/health` healthy.
- **No OOM kill since 09:37 UTC — still FOUR kills today** (00:56 / 06:21 / 08:07 /
  09:37 UTC), journal re-read this run.

## 2. The quantification — conversation history is EXONERATED

Oracle `conversation_history` (FRIDAY schema, read-only query via the service's
own venv + env — no credential read or copied):

| Measure | Value |
|---|---|
| Rows | **481** (`MIN(id)=1`, `MAX(id)=938`; trim cap 10,000 not binding) |
| Avg `user_input` chars | 60.4 |
| Avg `friday_reply` chars | 380.7 |
| Avg `agents_json` chars | 3.8 |
| Avg `metadata_json` chars | 1,028.1 |
| Raw text per row | ~1,473 chars → **~0.7 MB total** |

Live in-memory deque (`GET /api/v1/conversation/history`, safe — hydration
already happened at startup, journal line 09:37:29 UTC "restored ... 481 entries"):

- `total` = **481** — identical to the Oracle row count. Newest entry
  `2026-11-27T08:13:16Z` — **zero new turns since the 09:37 restart**.
- Newest-200 sample (computed on-server): `user_input` mean 79.3 / max 393 chars;
  `friday_reply` mean 397.1 / max 4,131 chars; 95,286 chars user+reply per 200
  entries (~476 chars/entry); 35/200 carry `agents_involved`, 197/200 carry metadata.
- In-process estimate for the whole deque (Pydantic overhead included): **~1–5 MB**.

**Verdict: the history deque is ~1–5 MB. It cannot be the ~150–165 MB floor.**
The cp2-planned fix (bound/shrink the history, lazy hydrate) is OFF the table
as the floor fix. `MAX_HISTORY_ENTRIES = 10000` (code) would only matter if the
table ever grew toward 10k rows — at 481 rows it is not the problem.

## 3. Floor split — anonymous mmap memory, not the heap, not history

`smaps_rollup` (12:26 UTC) + per-mapping `smaps` (12:3x UTC), PID 100296:

- `Rss 74,180 kB`, `Pss 54,006 kB`, `Swap 128,076 kB`.
- Anonymous total ≈ **162 MB** (34.5 MB resident + 128 MB swapped out).
  `Pss_Anon 34,520 kB`, `Pss_File 19,486 kB` (shared libs), `Pss_Shmem 0`.
- `[heap]` segment: Size 43,420 kB, Rss 11,708 kB — the classic brk heap is
  only ~43 MB virtual / ~12 MB resident.
- The rest of the anonymous memory sits in **dozens of MB-scale anonymous
  mmap regions** (top resident-anon regions 5.2 / 2.8 / 2.1 / 2.1 / 2.0 MB,
  high addresses `0x7b535...–0x7b537...`); total resident anonymous across
  mappings 47,332 kB at the second read (sawtooth moves the numbers).
- Thread stacks: 13 threads, `VmStk 208 kB`. `VmData 341,444 kB` virtual.

So the ~150–165 MB floor is **anonymous mmap memory** — not the brk heap
(~43 MB), not the history deque (~1–5 MB), not file-backed libraries
(~19 MB PSS), not thread stacks. Which Python-level owner holds those mmap
regions cannot be told from outside the process.

## 4. Sawtooth continues in this activation

Monitor lines (cgroup RAM % of 200M), PID 100296, since 11:30 UTC:

- 11:45 warn 76.4% (152.9 MB) → 11:45:31 **critical 100.0%** (200.0 MB) →
  11:46:02 recovered <60%.
- 12:01 warn 77.1% (154.2 MB) → 12:01:34 **critical 100.0%** (199.9 MB) →
  12:02:05 recovered <60%.
- 12:17 warn 82.9% (165.8 MB) → 12:17:36 **critical 100.0%** (200.0 MB) →
  12:18:06 recovered <60%.

Three 100% criticals this activation, each recovered within ~30 s by the
kernel swapping pages out — not by freeing. Corroborates M13's FRD-066
receipt (two 100% criticals 11:45:31 + 12:01:34 UTC) and adds a third
(12:17:36). `MemoryPeak=200M` agrees: the cap is touched repeatedly and the
process survives only because swap absorbs the spikes. Swap cap 192M (cp2):
at 12:26 the process held 125–128 MB swapped — ~65% of the swap cap.

## 5. S2 restart re-check — the hold is MOOT, no S2 FRIDAY exists

WATCH219 §D held the S2 restart until (a) the REL-096 backup finishes and
(b) TP1's FRD-064 quantification lands. Both legs now checked first-hand:

- **(b) Quantification: LANDED** — this checkpoint (§2–§3).
- **(a) REL-096 backup: FINISHED.** S2 journal (sudo lines, IST): 17:31 rsync
  sender → 17:37 fleet-state dir listing → 17:39 `backup_fleet_databases.py`
  fetched → 17:41 `--finalize --from-dir .../20261127T171539Z --bundle-dir
  .../20261127T172027Z-fleetstate/` → 17:44 prune (`rm -rf` one old set,
  `--prune-only --keep 3`) → 17:44 listing → 17:46 sha256 manifest verify.
  No backup process running now. S2 disk improved 95% / 2.9G (WATCH220) →
  **91% / 4.9G** (the prune freed a set; M10's `/tmp` cleanup report still
  owed by 19:00 IST per WATCH220 §E).
- **S2 (bridge server 2) has no FRIDAY to restart.** No `FRIDAY.service`
  unit file (`systemctl cat`: "No files found"); no FRIDAY process — only the
  bridge `server.py` (pid 641785, the same pid TP6 saw); nothing listening on
  :10000 / :8001. S2 memory 308 MB available, disk 91% / 4.9G.
- **Server 1:** a `FRIDAY.service` unit EXISTS (`MemoryMax=200M`, same
  uvicorn `friday.api.server:app` on :10000) but is **inactive, MainPID 0,
  no journal entries retained** (never ran in retained history); Inference
  also inactive; :10000 / :8001 both HTTP 000; 259 MB available.
- TP6's "FRIDAY OOM-killed 15:07 IST" is the **09:37 UTC kill on
  FRIDAY-Server** (pid 82582 → 98045 → 100296 chain; run 1/3 used pid 82582).
  TP6's S2 probe (bridge run_shell, :10000 HTTP 000) correctly found no
  listener on S2 — because no FRIDAY copy was ever deployed there
  (consistent with the fleet record: Oracle Server 2 hosts no agents).

**CALL (TP1, owns the restart call per WATCH219 §D): the S2 restart HOLD is
MOOT — there is no S2 FRIDAY to restart, and none is needed on Server 3
(live, PID 100296, `/health` 200). TP6's INT-025 run 2/3 block lifts by
re-pointing at the live FRIDAY-Server copy — coordinator to confirm the
route (TP6 reached pid 82582 for run 1/3, so the route exists). Starting
Server 1's never-run unit is a deploy decision for the coordinator, not a
restart. No restart executed by TP1 this run.**

## 6. What the fix needs now

1. **Heap attribution before any fix PR.** The anonymous mmap regions need a
   Python-level owner — `tracemalloc`, `pympler`/`py-spy`, or an in-process
   hook. That needs a code change and/or a restart with env — **coordinator
   clearance**; not done unilaterally. Until attributed, no fix PR can
   target the floor. (Per-turn sampling of `MemoryCurrent` + swap around one
   chat turn of each type, cp2 §6.2, still stands as the spike leg once the
   owner is known.)
2. Carried fixable items (ride the eventual fix PR, still valid): the
   `goal_loop.py:273` `JSONResponse` reply-extraction bug (real defect, on
   the 08:07 kill path); a cap on escalation-provenance retention (spike
   suspect, unproven).
3. VOI-045 (TP10) firing stays HELD until the fix deploys (WATCH215 §3) —
   no change; TP10 re-checks each run.

## 7. Five states

- Implemented: NO. Tested: NO. Merged: NO. Deployed: NO. Production-verified: NO.
- Investigation (this checkpoint): DONE — numbers above are first-hand live reads.

## 8. Queue

- FRD-064 (head) → TASK-EARN-015 (pre-staged next) → TASK-REL-069 (pos 3 top-up,
  board AVAILABLE / muse_tp1) → TASK-EARN-017 (queued). Hold ≤ 2 (1 + 1 pre-staged).
