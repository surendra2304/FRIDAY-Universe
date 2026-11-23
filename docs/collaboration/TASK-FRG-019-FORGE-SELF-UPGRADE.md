# TASK-FRG-019 — Forge first self-upgrade slice: idle gate ignores stale ACTIVE rows

Owner: Muse 4. Branch: `muse4/task-frg-019-forge-self-upgrade`.
Assignment: coordinator watch 7097385517 (~15:57 IST) + direction in watch 7097877084
("claim FRG-019 now"). Claim: successor hub #1483 comment 7097969338 (~16:00 IST).
Board record verified AVAILABLE, owner muse_4, on main e570ad5 (board blob 7d6b2c44,
verified against the true main blob before editing).

## 1. The proposal — from Forge's own experiment log

Forge's self-upgrade mechanism is its idle experiment loop
(`Forge/app/improvement/idle_loop.py`, FRG-017). Its "experiment log" is two
things: the loop's own ledger (`data/idle_experiments/experiments.jsonl`,
which did not exist) and Forge's own task record (Oracle StateStore). Read
live on Server 1, 2026-11-23 ~16:00 IST:

- **The loop had never run.** No `idle_experiments/` directory, no ledger,
  no champions file. `FORGE_IDLE_EXPERIMENTS` is unset and the loop is wired
  behind an explicit `=on` (`lifespan_enabled()`), so the loop never started
  on its own — and a hand-driven cycle could not start either, because:
- **Forge's own record blocks its own idle gate.** 285 tasks listed; states:
  FAILED 103, COMPLETED 30, CANCELLED 146, **RUNNING 2, READY 4**. The 6
  ACTIVE rows are all stale: 4 READY (REL019 probes, created 2026-11-14
  13:58–14:27 UTC, age 212 h) + 2 RUNNING (incident TEST_FAILURE, created
  2026-11-14 20:28–20:29 UTC, last updated 20:29:50 UTC, age 206 h).
  Nothing has touched them in 8.6 days; the Forge service restarted
  ~4 h before the read (uptime 14,114 s, PID 2832845) and again since, so
  no worker can be running them. Newest task overall is 2026-11-17
  (FAILED) — Forge has had no new work for 6 days, yet `is_idle()`
  returned **False forever**: the pre-fix check (`any ACTIVE`) cannot
  distinguish live work from dead rows.
- **The dominant failure cluster is verification_failures**: 89 of the
  103 failed tasks in the recent 200 (last 7 days: 15 of 23; runtime
  failures 13, security violations 1). The loop's hypothesis for its
  first cycle would therefore be verification_failures → golden spec
  `cli_todo`.

The self-improvement the log proposes: **make the idle gate staleness-aware**.
An ACTIVE row whose last update is older than a bound is a dead row from a
crashed or restarted worker, not assigned work. Without this, Forge's
self-upgrade loop is starved from birth.

## 2. The fix (one small change)

`Forge/app/improvement/idle_loop.py`:

- New constant `STALE_ACTIVE_AFTER_HOURS = 24.0`. 24 h is far above any
  genuine Forge build (minutes), and the check only gates the loop — it
  never mutates a row.
- `is_idle(now=None)` now skips ACTIVE rows whose `updated_at` (falling
  back to `created_at`) is older than the bound, logs the skipped row ids,
  and returns True when no *live* ACTIVE row remains. A row with no usable
  timestamp fails closed (counts as live work); naive timestamps are read
  as UTC. `run_one_cycle()` is unchanged — it already calls `is_idle()`.
- New helper `_is_stale(last, now)`.

`Forge/tests/test_frg019_idle_stale.py` (new, 11 tests): the 24 h bound;
the exact 6 live-record stale rows do not block idle; a fresh ACTIVE row
does; a mixed fresh+stale set does; the 23 h / 25 h boundary; `updated_at`
None falls back to `created_at`; no timestamp at all fails closed; naive
timestamps read as UTC; terminal states never block; a full cycle runs
past stale rows (PROMOTE on scripted arms); a cycle still skips on a fresh
ACTIVE row (`forge_busy`).

`.github/workflows/owner-workflows.yml`: the new test file is added to the
Forge test list (same job that collects `test_frg017_idle_experiments.py`),
so the REL-068 "every shipped test is collected" guard stays green.

## 3. Tests — live venv on Server 1 (not just CI)

Run on S1 in a scratch copy of S1's own Forge tree (`/tmp/frg019_test_forge`)
with the PR files applied, under the live venv (`venv312`, pytest 9.2.0):

- `ruff check` on both changed Python files: **all checks passed**.
- `pytest tests/test_frg019_idle_stale.py tests/test_frg017_idle_experiments.py
  tests/test_frg017_wiring_gates.py`: **53 passed, 0 failed**.
- Pre-fix control: the new test file against the unpatched code fails
  collection (`ImportError: cannot import name 'STALE_ACTIVE_AFTER_HOURS'`),
  and the live pre-fix `is_idle()` measured **False** with the 6 stale rows
  present (see §4 before). The FRG-017 suite still passes unchanged, so no
  existing idle-gate behaviour regressed.

## 4. Before / after live proof — the first idle-experiment cycle ever

Driver: the PR's patched `idle_loop.py` (md5 `f6343e854764f82324ab00d290b00b2b`,
verified in-driver) loaded over the live Forge checkout; the live
`StateStore` (Oracle) and the live data dir. No production file was touched;
the cycle writes only to Forge's own `data/idle_experiments/` and temp dirs.

**Before** (live code, 2026-11-23 ~16:00 IST / 10:27–10:31 UTC):

- `is_idle: False` (6 stale ACTIVE rows); host-load gate also refused at
  first (memory available fraction 0.124–0.145 < 0.150 C2 bar).
- Cycle skipped; ledger 0 rows. No experiment had ever run.

**After** (patched `is_idle`, 2026-11-23 16:14 IST / 10:44:39 UTC):

- `is_idle_patched: True`; C2 gate open on first check.
- Cycle **ran**: experiment `exp_20261123104439_cli_todo`, spec `cli_todo`.
- Hypothesis (from Forge's own record): "Forge's recent failures cluster on
  'verification_failures' (89 of 103 failed tasks)."
- Champion `forge_default` (manifest `main.py, test_main.py,
  requirements.txt, README.md`): **composite 100.0** — tests 11/11,
  manifest 1.00, compile 1.00, 9.52 s.
- Challenger `drop_readme` (same manifest minus `README.md`): **composite
  100.0** — tests 11/11, manifest 1.00, compile 1.00, 6.0 s.
- **Verdict: DISCARD** — challenger tied 100.00 vs champion 100.00 + 2.0
  promotion bar; the champion stands; lesson: do not retry the
  `drop_readme` shape for `cli_todo` until the failure mix changes.
  (Wall time is not part of the composite, so the challenger's 3.5 s
  saving does not promote it — the declared bar was applied as written.)
- Ledger on disk after the run: `data/idle_experiments/experiments.jsonl`
  1 row (1,284 bytes), `lessons.jsonl` 1 row (1,082 bytes),
  `champions.json` correctly absent (no promotion).
- Lesson delivery: **NOT confirmed by Memora** — private `false`,
  universal `false` (3 attempts each scope; "local fabric acceptance does
  not count as delivery"). The lesson stays **pending** in the local ledger
  by design (C3) for `flush_pending_lessons()` on later cycles. This matches
  the known fleet 401s; it is reported here as unconfirmed, not delivered.
- Forge service untouched: `/health` 200 after the cycle (same PID 2958600,
  `database_connected: true`); the cycle ran out-of-process.

## 5. States

- Implemented: YES (fix + 11 tests + CI wiring, this PR).
- Tested: YES (53/53 on S1 live venv; pre-fix control; live cycle ran).
- Merged: NO — awaiting Muse.
- Deployed: NO — the fix reaches S1 only through the normal change path
  (merge → Fleet CD). The live cycle above ran the PR file bytes
  out-of-process; no production file was changed.
- Production-verified: PARTIAL — the loop's first cycle ran live with the
  patched gate and its ledger is on disk, but the patched code is not yet
  the deployed code, and the Memora lesson delivery is still pending.

## 6. Owed / follow-ups (not in this slice)

- Merge, then Fleet CD deploy; after deploy, the loop still needs its
  activation step (`FORGE_IDLE_EXPERIMENTS=on` — a coordinator step, never
  part of a code change) before it runs on its own in the lifespan.
- The 6 stale ACTIVE rows are still in the Oracle store (this fix only
  stops them blocking the idle gate; it mutates nothing). A stale-row
  reaper / terminal transition is a separate task if the coordinator wants
  the rows themselves closed.
- Memora lesson delivery retry: `flush_pending_lessons()` on the next
  cycle; if Memora keeps refusing, that is the shared 401 gate, not this
  task.
- The DISCARD verdict is a real result, not a failure: the champion
  (`forge_default` for `cli_todo`) stands at 100.0. The next cycle will
  probe the next least-tested spec / next challenger mutation in rotation.
