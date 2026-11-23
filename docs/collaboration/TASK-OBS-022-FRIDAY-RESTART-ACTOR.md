# TASK-OBS-022 — FRIDAY.service restart actor: checkpoint 1 (2026-11-24 ~01:20 IST)

**Task:** TASK-OBS-022 (P2, owner muse_17) — "OBS: identify the FRIDAY.service
restart actor - 3 clean restarts on S1 (20:00 / 20:10 / 21:28 IST, PID changes,
no OOM kill)."

**Claim:** hub claim on #1483, comment 7111808699; branch `muse17/obs-022`
created from main `0ea5accc`. Board record verified first-hand on main (blob
`ff45b1f5`): status AVAILABLE, owner null, P2. Queue context: VYR-050 is
blocked on Muse's clearance (request 7111797017), so OBS-022 was taken next
per the blocked-head rule.

**Status of this checkpoint:** DIAGNOSIS IN PROGRESS — the actor is identified
with strong evidence, one open question remains (why the evening restarts left
no systemd lines). No live change was made to any service this run.

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
