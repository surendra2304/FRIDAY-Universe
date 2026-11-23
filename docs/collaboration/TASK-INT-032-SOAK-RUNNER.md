# TASK-INT-032 — INT-876 soak runner: definition filed, first scheduled run owed

**Worker:** Muse 7. **Claim:** issue #1483 comment 7109490137, 2026-11-23 ~23:25 IST, on coordinator re-slot (enforcement board PR #1534; Muse 6 claimed with no branch and zero commits — owner muse_6 → muse_7). **Branch:** `muse7/task-int-032-soak-runner`. **Base:** main 49126a41 (branch fast-forwarded from 13cdf268; zero unique commits before this work).

**Status of this document:** DEFINITION FILED. The runner (timer/cron/unit + run-record location) is now defined in the repo — acceptance leg 1 is met. Leg 2 (one scheduled run observed end-to-end) is NOT met yet: the next 09:30 IST run is 2026-11-24 09:30 IST, ~9 hours after this filing, and the timer is defined in the repo but not installed/enabled on S2 (install needs the coordinator deploy step — no fleet mutation in this PR). Leg 3 (no duplicate) is met by construction: the runner is idempotent per date and its single schedule IS the 09:30 slot.

## 1. What the soak is (from the record)

- INT-876 soak: 7-day chain, once-daily 09:30 IST silent run, D4 enablement judgement due earliest 2026-11-27 (owner chose option 1A). Chain restarted 2026-11-21 after the first 4-day chain was lost in the 2026-11-20 sandbox cleanup (INT-019 evidence).
- INT-023 interim evidence (Muse 9, PR #1460): days 1–3 have **zero verifiable passing days** — day 1 is coordinator-asserted only (status lines 7058036493, 7060081284); days 2–3 have no 09:30 run in any live source (live archive + journals); every live research run 2026-11-22 → 2026-11-23 is DEGRADED on `synthesis_entailment_unverified`. No soak timer/cron/unit/file existed on S2 and no run definition lived in the repo — that gap is what this task closes.
- INT-033 (Muse 9, PR #1511, merge cfe211cf): the entailment blocker is root-caused (three tokenisation defects in `statement_support`) and the fix is MERGED. **Not deployed:** S2 IntelX is still PID 605920 since 2026-11-23 12:00:36 IST (§2), and the S2 checkout is on a feature branch — the fix cannot be live. Deploy + live re-probe needs coordinator clearance; the re-probe leg belongs to INF-028 (Muse 2) per INT-033 §6. A soak day runs DEGRADED until that deploy lands; the runner records that honestly.

## 2. S2 state verified first-hand this run (bridge v1.30.0)

- Both Oracle servers ONLINE (`get_system_info`, ~00:26 IST). S2 host `friday-universe-vnic-2`; system date Tue 2026-11-24 00:41:57 IST — **S2 local time is IST**, so the timer's 09:30 is 09:30 IST with no UTC conversion.
- `systemctl list-timers` (14 timers): **no soak / IntelX / 876 timer exists**. `fleet-health-watcher.timer` is cycling (last run 00:41:22 IST); `friday-self-heal.timer` next 07:30 IST. `/etc/cron.d/` holds only `e2scrub_all`.
- `find /opt/friday_universe -maxdepth 3 -iname '*soak*'` / `'*876*'`: only pre-existing unrelated files (Stratex `battery_soak_runner.py`, FRIDAY `research/soak.py`, Inference `scripts/soak_mixed.py`, this task's predecessor doc `TASK-INT-023-SOAK-CHAIN-EVIDENCE.md`). **No INT-876 file, no soak state dir, no soak record.**
- `IntelX.service`: active, MainPID 605920, started Mon 2026-11-23 12:00:36 IST — unchanged since the 16:25 IST check. INT-033 fix not deployed (§1).
- Install facts verified first-hand (second bridge probe, ~00:51 IST; 3 attempts — timeouts/SSL flap before success): `IntelX.service` reads `EnvironmentFile=/opt/friday_universe/IntelX/.env` (the exact file the runner unit declares), `User=ubuntu`, `WorkingDirectory=/opt/friday_universe/IntelX`, `ExecStart=/opt/friday_universe/venv/bin/python -m uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1`. That `.env` exists (0600, ubuntu, 2192 bytes, Nov 23 00:43) and carries the `FRIDAY_API_KEY` name (count 1 — name only, value never read). Fleet venv python exists at `/opt/friday_universe/venv/bin/python`; `/var/lib/friday-universe` exists; IntelX `/healthz` returns **200** (`status ok`, `mock_mode false`, v2.0.0, observed 2026-11-23T19:21:14Z). The runner unit's paths are therefore correct as written; only the install/enable step itself remains (§5.4).

## 3. The runner as defined (this PR)

| Piece | File | What it is |
|---|---|---|
| Runner script | `IntelX/scripts/run_int876_soak.py` | Stdlib-only. POSTs `research_live` to local IntelX (`POST /v1/task/execute`, `task_id` `soak-876-YYYY-MM-DD`), writes the day record. Exit 0 = a run was observed and recorded (even DEGRADED); 2 = no run could be triggered; 3 = day record unwritable. |
| Unit | `deploy/intelx-soak-runner.service` | `Type=oneshot`, `WorkingDirectory=/opt/friday_universe`, `EnvironmentFile=/opt/friday_universe/IntelX/.env` (fleet key `FRIDAY_API_KEY`; never printed/logged), `ExecStart` = fleet venv python + the script, `User=ubuntu`, `StateDirectory=friday-universe`. Pattern follows `deploy/fleet-health-watcher.service`. |
| Timer | `deploy/intelx-soak-runner.timer` | `OnCalendar=*-*-* 09:30:00`, `Persistent=true`, `AccuracySec=30s`. S2 is IST (§2), so this is the 09:30 IST slot. |
| Day record | `/var/lib/friday-universe/intelx-soak/YYYY-MM-DD.json` on S2 | Run time (IST+UTC), `task_id`, `run_id`, envelope status, synthesis status/reason, source/finding counts, summary, delivery path (archive recall URL + record path), `pass` boolean. |
| Durable run record | IntelX live research archive (Oracle-backed) | The run itself, recallable at `GET /v1/research/live/{run_id}` (proven durable by INT-023: 36 runs back to 2026-11-14). |

Trigger path (verified against main): `POST http://127.0.0.1:8005/v1/task/execute`, header `X-API-Key: <FRIDAY_API_KEY>`, body `{"task_id": "soak-876-YYYY-MM-DD", "action": "research_live", "payload": {"query": "<standing query>"}}` — the same `research_live` action FRIDAY dispatch uses (`IntelX/intelx/api/router.py:105-188`). Query must be 5–1000 chars; the pipeline persists the run via `persist_live_research` and sets `durable_run`.

Pass criterion: a day passes iff the envelope status is `SUCCESS` (synthesised brief). DEGRADED is recorded honestly, counts as a failed day for the D4 judgement, and never retries — one timer fire, one run, one record per date.

## 4. Reconciliation — the runner and the silent run are one run

- **No duplicate created.** There is exactly one schedule: the timer's daily 09:30 IST. The script refuses a second run for the same date (record file exists → exit 0, no call) unless `--force` is given, and `--force` still writes the same day's record — so a late `Persistent=true` catch-up, a manual re-run, or a proving run can never create a second 09:30 run or a second day record.
- **The coordinator's silent run becomes the runner's run.** Days 1–3 were recorded only in coordinator status lines (INT-023 §3); those records stand as history and are not re-counted. From the install date, the 09:30 run is executed by this timer, recorded in the archive + the day-record file, and the day record is what the D4 judgement reads. The coordinator no longer needs to run or record it by hand.
- **Days 1–3 are not rewritten.** Day 1 stays coordinator-asserted-only; days 2–3 stay "no 09:30 run observable" (INT-023). The chain's verifiable days start when the runner first fires.

## 5. Open items (for the coordinator, not blockers for this definition)

1. **Standing query (default set, confirmation wanted).** No authoritative soak query exists in any readable source — no comment, doc, or board record defines it. The runner defaults to `latest AI model releases`: the exact query of the last observed live runs (2026-11-23 09:00 IST, `lr_6d6a71…` etc.), so soak days stay comparable with the observed baseline. Override is one line (`SOAK_QUERY` env / `--query`). If the coordinator's silent run used a different query, say so and the default changes with it.
2. **"1A" / "D4" definitions.** Still undefined in any readable source (INT-023 §3). The runner defines the run; it does not define what D4 enables. The D4 judgement (due 2026-11-27) still needs that definition from the coordinator.
3. **INT-019 adjacency (Muse 16).** INT-019 moves the soak state onto S2 + one traced consumption. This runner's record dir (`/var/lib/friday-universe/intelx-soak`) is the state location it writes; if Muse 16 picks a different state dir, the change is the single `SOAK_RECORD_DIR` constant. No file is duplicated: the archive is the run record, the JSON is the day record, the hub comment is the day notice.
4. **Install / enable (deploy step, not in this PR).** Copy the unit + timer to S2, `systemctl daemon-reload`, `enable --now intelx-soak-runner.timer`, verify `is-active` + `list-timers` shows 09:30 IST next. Install facts are verified (§2): the unit's `EnvironmentFile`, venv path, and `StateDirectory` parent all exist on S2 as written. No fleet mutation was made in this PR.
5. **INT-033 deploy.** Until the entailment fix is deployed to S2 IntelX, soak days will record DEGRADED (the same systematic failure INT-023 found). That is honest data, not a runner defect — but a green chain needs the deploy (coordinator clearance; INF-028 owns the re-probe).

## 6. Observation leg — owed, with a named time and procedure

The first scheduled run under this runner is **2026-11-24 09:30 IST** (day 4 of the chain), ~9 hours after this filing — no scheduled run exists to observe before then, and no proving run was triggered in this run (triggering one needs the fleet key, which is not handled by this worker; the timer install is the deploy step). The observation procedure for the next run:

1. After 09:30 IST 2026-11-24: read `/var/lib/friday-universe/intelx-soak/2026-11-24.json` on S2 (bridge `read_file`) and recall the run at `GET /v1/research/live/{run_id}`.
2. File: run time, `run_id`, envelope status, synthesis status, counts, delivery path (archive + day-record file) — as an addendum here or in the INT-023 final compilation (Muse 9, due 2026-11-27).
3. Post the hub day record (day 4) on issue #1483.

**Work PR:** #1553 (branch `muse7/task-int-032-soak-runner`, base main 49126a41). Board record CLAIMED → IN_REVIEW rides in the PR. **Stall repaired this run:** branch was at its claim base with zero commits ~60 min after claim; the definition leg + this evidence + the work PR are the repair. The observation leg is time-bound to the next 09:30 run, not stalled.

— Muse 7, 2026-11-24 ~00:45 IST
