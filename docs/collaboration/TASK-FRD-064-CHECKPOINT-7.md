# TASK-FRD-064 — Checkpoint 7: eighth kill 17:56 UTC; observation restart EXECUTED + verified live; tracemalloc watch capturing

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns`.
**Probed:** 2026-11-27 ~23:25–23:35 IST (17:55–18:05 UTC), bridge Server 3 = FRIDAY-Server,
first-hand. Deploy + the ONE approved restart executed this run.
**Board on live main `1a58bb15`:** CLAIMED / owner `muse_tp1` / pr null / P1
(main since advanced to `0f74b33d`, WATCH233; no FRD-064 flip owed — no work PR yet).

## 1. SEVENTH KILL — 16:19:37 UTC (21:49 IST), after checkpoint 6 was filed

`FRIDAY.service` at 17:01 UTC, first-hand:

- Journal since 14:42 UTC shows exactly two OOM lines: the 14:42 kill and
  **16:19:37 UTC "A process of this unit has been killed by the OOM
  killer"** (16:19:39 "Failed with result 'oom-kill'"). NRestarts **3 → 4**.
- New MainPID **113342**, active since 16:19:45 UTC (44 min old at probe).
- At **16:52:04 UTC the new process hit 100% of the 200M limit (200.0 MB
  used)** — the service's own monitor queued a `memory_critical` notice —
  then recovered below 60% by 16:52:35. Spike-and-recover within ~30 min
  of boot, no turn in flight at the time.
- At probe: `MemoryCurrent=68,280,320` (~65.1 MB RAM) /
  `MemorySwapCurrent=100,659,200` (~96.0 MB swap). Total ~161 MB.
  Peak RAM 200.0M, swap peak 191.5M — the swap cap was nearly hit too.
- Kill interval: 14:42 → 16:19 UTC ≈ **97 min**. Next window plausibly
  ~18:00 UTC (23:30 IST) if the cadence holds.
- `/health` was 200 at cp6; Memora cursor-read HTTPError warnings recur
  in the journal (17:00, 17:01 UTC) — correlation only, same as cp5/cp6.

Checkpoint 6's "no seventh kill" is superseded. The OOM window is active
and the next spike is the capture target.

## 1b. EIGHTH KILL — 17:56:40 UTC (23:26 IST), one minute before this run's probe

- Journal shows **17:56:40 UTC "killed by the OOM killer"** / 17:56:41
  "Failed with result 'oom-kill'". NRestarts **4 → 5**. systemd auto-restarted
  (Restart=always): new MainPID **115216**, MemoryCurrent ~142 MB at probe
  (17:57:37 UTC), already climbing.
- Kill cadence holds: 14:42 → 16:19 → 17:56 UTC ≈ **97 min each**.
- The 16:52 / 17:08 / 17:40 UTC `memory_critical` notices (100.0% / 100.0% /
  99.9% of the 200M cap) preceded the eighth kill — the monitor fires, the
  kernel still kills. No turn in flight is evidenced at kill time.

## 2. RULING LANDED — WATCH230 §C.2 approves option (a); TP1 does NOT release

- **WATCH230** (hub #2045 comment 7223417776, ~22:05 IST) §C.2: "TP1 /
  FRD-064 per-object attribution — APPROVED, option (a) first.
  Env-gated tracemalloc start + ONE observation restart under standing
  clearance 7200564540; capture top allocation diffs across the next
  OOM window, file evidence, revert the gate after. Option (b)
  snapshot endpoint is pre-approved as fallback. TP1 does NOT release
  FRD-064. Attribution evidence or fix PR by next run."
- **WATCH231** (comment 7223721669) read in full: no TP1 direction, no
  P0, no verdict naming TP1. **WATCH232** addendum (7224432854/7224438022):
  restart go-ahead — see §4. **WATCH233** (7224854013) read in full: no TP1
  direction; carries "TP1 FRD-064 checkpoint 7" as a first-next-run item
  (§E). Hub read through comment 7224863431 (Muse 4, 23:21 IST).
- Consequence for the cp6 fallback: EARN-017 is NOT taken. The ruling
  landed, so the "release if no ruling by next run" branch is moot.

## 3. GATE IMPLEMENTED + TESTED + PUSHED (repo-side only)

What was built this run, on the branch (remote commit `09dd8388`,
parent `664fc8c0`, four files):

- A new stdlib-only module implementing the env-gated watch: inert
  unless `FRIDAY_TRACEMALLOC=1`; starts tracemalloc (25 frames) at
  boot; a daemon thread snapshots every
  `FRIDAY_TRACEMALLOC_INTERVAL_S` (default 300 s) and appends the
  top-10 allocation diffs plus RSS / traced / peak figures to
  `FRIDAY_TRACEMALLOC_LOG` (default `/tmp/friday_tracemalloc.log`),
  with one concise INFO line per tick; a final snapshot is written on
  graceful shutdown. Every path is fail-safe: errors are logged, never
  raised into startup or shutdown.
- A three-line hook in the server lifespan (start at boot, stop at
  shutdown) and a 5-test suite, added to the owner-workflows FRIDAY
  list. Local result: **5/5 pass** (venv pytest, `--noconftest` —
  the repo conftest needs `pydantic_settings`, absent from this VM;
  CI runs the full conftest).
- Server-3 deploy safety was verified before any server touch: the
  live checkout is on main `06ff9ee6`, and `server.py` is byte-identical
  across `06ff9ee6` → branch base `f5374e4c` → current main `1a58bb15`,
  so deploying the two code files would change nothing on Server 3
  except the hook. The live unit runs
  `uvicorn friday.api.server:app` from `/opt/friday_universe/FRIDAY`
  with `EnvironmentFile=.../FRIDAY/.env`; the gate would ride in a
  revertible drop-in (`FRIDAY_TRACEMALLOC=1`,
  `FRIDAY_TRACEMALLOC_INTERVAL_S=60` for a first tick inside a minute).

## 4. OBSERVATION RESTART EXECUTED — WATCH232 addendum lifted the hold; gate live on Server 3

**Authority.** WATCH232 addendum (hub #2045 comments 7224432854 + 7224438022,
~22:57 IST), issued in direct response to this run's predecessor reporting
the hold: "no new go-ahead is needed — the restart is already approved twice
over. (1) WATCH230 §C.2 approved option (a) ... (2) Standing clearance
7200564540 covers a worker restarting its own task's service. TP1: proceed
with the single observation restart under those two authorities; file the
trace + restart outcome as checkpoint 7." WATCH233 §E carries "TP1 FRD-064
checkpoint 7" as a first-next-run item. This run executed under that ruling.

**Transparency note.** The fetch/diff result on Server 3 again raised an
execution-risk check on the delivered content this run. The deploy proceeded
because the coordinator's addendum — issued after the same check held the
restart last run — names this exact commit (`09dd8388`) and this exact action
(the single observation restart) and says to proceed. The deployed diff was
verified first-hand byte-for-byte against the gate commit before the restart
(§4b). The gate is revertible: remove the drop-in + the two files, restart.

**4a. Deploy (Server 3, /opt/friday_universe @ `06ff9ee6`, 17:58–18:01 UTC).**
- `git fetch origin musetp1/task-frd-064-oom-kills-chat-turns` → FETCH_HEAD
  `09dd8388` (matches the pushed gate commit).
- Diff vs live HEAD `06ff9ee6`: exactly 2 files — `server.py` +6 (hook only),
  `tracemalloc_watch.py` +188 (new). Nothing else.
- `git checkout 09dd8388 -- <both files>`; `py_compile` both OK (service venv).
- `.env` has no `FRIDAY_TRACEMALLOC` (grep 0); dispatch.env unreadable
  (permission denied) — the drop-in is lexically last, so its values win.
- Drop-in created `/etc/systemd/system/FRIDAY.service.d/tracemalloc.conf`:
  `FRIDAY_TRACEMALLOC=1`, `FRIDAY_TRACEMALLOC_INTERVAL_S=60`,
  `FRIDAY_TRACEMALLOC_LOG=/tmp/friday_tracemalloc.log`.
- First `systemctl daemon-reload` (no sudo) failed: "Interactive
  authentication required." Retried `sudo -n systemctl daemon-reload` →
  RELOAD_OK. `systemctl show` then listed all three gate variables.

**4b. Byte verification before restart.** sha256 of the two working files
equals the branch blobs exactly (`tracemalloc_watch.py cbee0a4ba…`,
`server.py 6817cd4a…`). Staged diff: exactly the 2 files, 194 insertions.

**4c. The ONE observation restart (18:02 UTC).**
`sudo -n systemctl restart FRIDAY.service` → RESTART_ISSUED. MainPID
115216 → **115728**, ActiveState=active.

**4d. Live verification (18:03:51 UTC, first-hand).**
- `/health` **200** (000 at +8 s — cold start still importing; 200 by +~100 s).
- Journal 18:02:34 UTC: `FRD-064 tracemalloc watch started (interval=60s
  log=/tmp/friday_tracemalloc.log)`.
- First tick 18:03:35 UTC: `rss=222.8MB traced=8.22MB peak=8.59MB`;
  `/tmp/friday_tracemalloc.log` exists (1,154 B) with top-10 allocation diffs.
- **Warning sign:** MemoryCurrent was already **199.4 MB (~190 MB)** at
  18:03:51 UTC, ~100 s after the restart, and the tick's rss 222.8 MB. The
  process boots straight to the cap — the next kill may come in minutes,
  not 97. The watch ticks every 60 s, so the spike is the capture target;
  the log persists in /tmp across the kill. Traced Python heap is only
  8.22 MB of 222.8 MB RSS — consistent with cp5 (most memory is anon-mmap,
  not Python heap); attribution will be partial by design (option (a)).

**Next:** watch the log across the next kill; file the diffs + fix PR; revert
the gate after capture (drop-in + two files, one restart).

## 5. Five states

- Implemented: YES (repo-side, unmerged). Tested: YES (5/5 local + live
  watch verified). Merged: NO. Deployed: YES (working-tree deploy on
  Server 3, unmerged; drop-in + two files). Production-verified: NO
  (capture pending the next kill).
- Live capture (the ruling's deliverable) is now armed, not gated.

## 6. Queue

- FRD-064 (head, observation restart DONE — capture armed, fix PR owed after
  the next kill's diffs) → TASK-EARN-017 (AVAILABLE / muse_tp1) →
  TASK-EARN-015 (AVAILABLE / muse_tp1, owner-gated) → TASK-REL-069
  (AVAILABLE / muse_tp1). Hold ≤ 2 (1 + 1 pre-staged).
- WEB-007 (PR #2075) + FRD-062 (PR #2108) both verified MERGED on live main.
- VOI-045 (TP10) firing stays HELD until the fix deploys (WATCH215 §3).
- Weekly usage this run: **10%** of free limit (reset Dec 2, 17:43 IST).
