# TASK-OBS-022 — FRIDAY.service restart actor: checkpoint 1 (2026-11-24 ~01:20 IST)

**Task:** TASK-OBS-022 (P2, owner muse_17) — "OBS: identify the FRIDAY.service
restart actor - 3 clean restarts on S1 (20:00 / 20:10 / 21:28 IST, PID changes,
no OOM kill)."

**Claim:** hub claim on #1483, comment 7111808699; branch `muse17/obs-022`
created from main `0ea5accc`. Board record verified first-hand on main (blob
`ff45b1f5`): status AVAILABLE, owner null, P2. Queue context: VYR-050 is
blocked on Muse's clearance (request 7111797017), so OBS-022 was taken next
per the blocked-head rule.

**Status of this checkpoint:** SUPERSEDED by checkpoint 2 below — the webhook
leg is corrected and the actor is proven. No live change was made to any service
in either run.

## The actor: the GitHub deploy webhook + pull + restart

All times IST, 2026-11-23, first-hand unless noted.

**Deploy pulls (S1 checkout reflog, `git reflog --date=iso`):**
- `93d5fd5e` HEAD@{20:00:22} — merge 93d5fd5e (PR #1501)
- `c71a1179` HEAD@{20:09:53} — merge c71a1179 (PR #1498)
- `2acdf19e` HEAD@{21:27:38} — merge 2acdf19e (PR #1515)
- `13cdf268` HEAD@{22:58:44}, `8c0ef142` HEAD@{23:41:12},
  `49126a41` HEAD@{23:59:37} — merge 49126a41 (PR #1537)

The three evening pulls land at 20:00:22 / 20:09:53 / 21:27:38 — the task
title's "20:00 / 20:10 / 21:28" to within seconds. The coordinator's
"restart times" are the deploy pull times. The same sequence is fully
observed at midnight: pull 23:59:37 (49126a41) → FRIDAY stop 23:59:57 →
start 00:00:01 IST (graceful shutdown logged, 20 s pull-to-restart lag).

**Webhook path (Caddy access log via journal):** GitHub-Hookshot POST
`/api/deploy/github` at 23:50:16 IST (X-Github-Event: pull_request, two
deliveries, status 308 redirect to https). The endpoint exists and receives
GitHub events on S1. The Caddyfile's first 80 lines show no deploy route;
the route lives below line 80 or in an included file (not yet located).

**Merges cluster at the same times (GitHub API, main):** 3 merges 19:59:35–47
IST (PRs #1506/#1501/#1498), merges 20:11:32/20:13:31/20:13:56 (PRs
#1508/#1500/#1512), merges 21:23–21:27 (PRs #1515/#1518/#1519). A merge →
webhook → pull → restart chain with a ~1–5 min lag fits all three times.

## What is RULED OUT (first-hand)

- **No systemd timer or cron restarts her.** Full timer list (22 timers):
  none fires at 20:00/20:10/21:28 and none restarts FRIDAY. ubuntu crontab
  has only the duckdns updater (`*/5 * * * * update_duckdns.sh`); /etc/cron.d
  has only .placeholder + e2scrub_all; no "friday" in any cron file.
- **No watchdog restarts her.** friday-deploy-watchdog-report only reports
  deployed HEAD + tree cleanliness to Sentinel (decisions live in Sentinel);
  friday-webhook-watchdog checks Telegram webhook presence;
  fleet-health-watcher does crash-loop detection + /health alerting;
  friday-self-heal is a daily 07:30 sweep that alerts. None of their unit
  files contains a restart of FRIDAY.service. (Side finding:
  friday-deploy-watchdog-report.service is currently **failed**; its timer
  is still active.)
- **No OOM kill.** dmesg (OBS-015): last kill Nov 23 08:03:47 IST; none in
  the evening. No OOM event Nov 24.
- **No logrotate involvement.** No friday entry in /etc/logrotate.d/.

## The open question

The FRIDAY.service journal (18:00–23:00 Nov 23, two independent greps) has
ZERO start/stop/restart lines, and FRIDAY-Voice.service likewise (NRestarts=0
for both; voice current run since 23:43:10 IST). The midnight restart DID
leave systemd lines (Stopping 23:59:57, Stopped + Started 00:00:01). So
either the evening pulls did not restart her (the deploy pulls but restarts
only on some condition, and the title's "restarts" are really "deploys"), or
the journal is incomplete for that window. Probe 5 (journal completeness in
the evening windows, Caddy access-log deliveries near the three pulls, the
deploy receiver's identity) was launched to settle this but is BLOCKED: the
bridge endpoint became unreachable ~01:22 IST — two full probe runs (4
initialize attempts, 60 s + 90 s caps) plus a direct reachability check (GET
000 after 20 s, POST initialize 000 after 30 s) all failed. The bridge was
working at ~01:19 IST (probe 4 completed). Probe 5 will be retried when the
bridge recovers; the finding above does not depend on it.

## Side correction (OBS-015)

The hourly self-check's note that "`systemctl show` reports MemoryMax=
infinity for both services" is wrong for FRIDAY.service: `systemctl show
FRIDAY.service` returns MemoryMax=209715200 (200M), MemorySwapMax=201326592
(192M), matching the unit file (MemoryMax=200M) and the swapmax.conf
drop-in (MemorySwapMax=192M). The OBS-015 cgroup-kill root cause stands;
only that caution note was mistaken.

## What this run did not do

- No service started, stopped, restarted or changed; no board edit; no
  claim of implemented / tested / merged / deployed / production-verified
  status. This is a checkpoint, not a completion.

— Muse 17

---

# Checkpoint 2 — CORRECTION + VERDICT (2026-11-24 ~03:00 IST)

**Status: DIAGNOSIS COMPLETE — actor PROVEN.** Acceptance met: the restart
actor is identified from S1 logs, systemd evidence and GitHub records, with
proof. No code change, no live change, no service touched in this run.

## CORRECTION — checkpoint 1's webhook leg is WRONG

The "GitHub deploy webhook → pull → restart" chain is refuted:

- The repo's webhook list is EMPTY — no webhooks are configured on
  surendra2304/FRIDAY-Universe (verified 2026-11-24 ~02:00 IST, first-hand).
- No deploy route exists in the S1 Caddyfile, no deploy handler exists in
  the FRIDAY code, and the Caddy access log holds zero deploy lines.
- The 23:50:16 "GitHub-Hookshot POST /api/deploy/github" line in
  checkpoint 1 was a misread of the journal.

There is no webhook receiver on S1. The trigger is a push event consumed by
GitHub Actions itself.

## The actor, PROVEN — the Fleet CD workflow on push to main

**Workflow:** "FRIDAY Universe Fleet Continuous Deployment"
(`.github/workflows/deploy-monorepo.yml`, `on: push, branches: [main]`,
plus `workflow_dispatch`). Re-read first-hand this run on main `384950d9`
(blob `c1868fe8`, 31,199 bytes).

**How it restarts her (workflow definition, verbatim logic):** the
`deploy-server1` job SSHes to S1, fast-forwards `/opt/friday_universe` to
the pushed SHA, then runs the restart loop over
`SERVER1_AGENTS=("FRIDAY" "Inference" "Memora" "Stratex" "Forge"
"Sentinel")` — `sudo systemctl restart "${AGENT}.service"` fires when the
agent's own folder changed **or `mesh/`, `deploy/` or `scripts/` changed**
(or on manual dispatch). FRIDAY-Voice.service restarts when `FRIDAY/`
changed. There is no per-merge approval and no restart gate.

**Run → pull → restart, all four merges (Actions API + S1 reflog,
first-hand this run; times IST, 2026-11-23):**

| Merge (PR) | Workflow run created | S1 pull | Run conclusion |
|---|---|---|---|
| `93d5fd5e` (#1501) | 19:59:44 (run 45194805918) | 20:00:22 | failure |
| `c71a1179` (#1498) | 19:59:51 (run 45194823669) | 20:09:53 | failure |
| `2acdf19e` (#1515) | 21:27:04 (run 45210942426) | 21:27:38 | failure |
| `49126a41` (#1537) | 23:58:53 (run 45238845137) | 23:59:37 → stop 23:59:57 → start 00:00:01 | failure |

**The restart condition fired every time:** all four merges touch
`scripts/` (commit-files API, first-hand this run — #1501: docs/scripts/
tests; #1498: .github/docs/scripts; #1515: .github/Sentinel/docs/scripts/
tests; #1537: .github/docs/scripts/tests). `scripts/` in the diff is
enough, by the loop's own condition, to restart FRIDAY.service on every
one of these deploys.

**Why the 20:09 pull lagged 10 minutes:** the workflow's concurrency
group `deploy-monorepo-${{ github.ref }}` has `cancel-in-progress: false`,
so deploys serialize — each S1 job runs ~10 min. The 19:59:51 run waited
behind the 19:59:44 run; its pull landed 20:09:53. The three "restart
times" in the task title (20:00 / 20:10 / 21:28) are the S1 pull times of
three serialized deploys, to within seconds.

## Checkpoint 1's open question — RESOLVED

The evening pulls DID restart her. The missing systemd lines are explained,
not by pulls-not-restarting, but by journald retention: journald caps at
200M, ~2h retention — at the 02:07 IST check the whole journal was empty
18:00–23:00 Nov 23 (oldest entry 00:19:12 IST Nov 24). Absence of lines in
that window proves nothing. The midnight restart, inside the retained
window, left full stop/start lines and is observed end to end.

## What is still RULED OUT (unchanged from checkpoint 1)

No systemd timer or cron restarts her; no watchdog restarts her (all four
watchdog/self-heal units report or alert only); no OOM kill in the evening;
no logrotate involvement. The only actor is the Fleet CD workflow.

## New observation, FLAGGED (not this task's to fix)

All four S1 deploy jobs concluded **failure** — yet each one demonstrably
pulled and restarted the fleet. The failure lands inside the single SSH
step, AFTER the restart: the midnight S1 job ran 10m14s while the
pull-to-restart lag is ~20s, and the restart itself is observed
(stop 23:59:57, start 00:00:01). The exact failing point inside the
script (most plausibly the post-restart health-probe section) is NOT
identified from the jobs API — the job log was not pulled this run. The
S2 job on the same run failed in 12s. Consequence: deploys report red
while having restarted the fleet. Recommend Muse route a follow-up
reliability task; OBS-022's acceptance (identify the actor) does not
cover fixing the deploy job.

## Verdict

- **Actor:** the GitHub Actions workflow "FRIDAY Universe Fleet
  Continuous Deployment" (`.github/workflows/deploy-monorepo.yml`),
  `deploy-server1` job, on push to main.
- **Trigger:** any merged PR whose diff touches `FRIDAY/`, `mesh/`,
  `deploy/` or `scripts/` (all four evening merges touched `scripts/`).
- **Scheduled or removed:** the restart IS scheduled by workflow design —
  every qualifying push restarts FRIDAY.service. Narrowing the trigger
  (e.g. restart only when `FRIDAY/` itself changes) is Muse's call, not
  this task's.
- **States:** implemented NO / tested NO / merged NO / deployed N/A /
  production-verified NO. This is a diagnosis, not a change. No live
  change was made to any service in either checkpoint run.

## Board

Board record verified first-hand on main `384950d9` (blob `6a2f6b33`,
17,969 lines) this run: TASK-OBS-022 CLAIMED, owner muse_17, branch
`muse17/obs-022`, pr null. The CLAIMED → IN_REVIEW flip with this work
PR is owed to the coordinator's next consolidated board PR — this branch
is based on main `0ea5accc`, so its board copy is stale and must not be
hand-edited into this PR. TASK-VYR-050 (blocked on clearance 7111797017,
unchanged) still shows AVAILABLE / owner muse_17 / branch null on main —
its CLAIMED flip is likewise owed to the next board PR.

— Muse 17
