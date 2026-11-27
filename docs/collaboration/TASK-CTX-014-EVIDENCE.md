# TASK-CTX-014 — Cortex escalation-ratio live check run 8 — fires vs messages actually sent (last 48h)

- Claim: issue #2045 (Muse 15 hourly self-check 2026-11-27 ~20:0x IST; comment id filed in the work PR before merge).
- Branch `muse15/task-ctx-014` from main `cf49af6b` (#2141 merge).
- Live leg: NOT YET RUN. Method: run 7 (`TASK-CTX-013-EVIDENCE.md`); endpoint snapshot `GET /v1/friday/self_healing` + `journalctl -u Cortex.service` counts and boundaries, via bridge `run_shell` on Oracle Server 1 under standing clearance 7200564540. Read-only throughout: no restart, no config change, no deploy, no key copied.
- Route verified at claim time: bridge reachable; local client allowlist already includes `run_shell` (read-only); live Cortex is on Server 1 (active since 2026-11-24 19:34:23 IST, PID 3771939 per run 7).

## 0. Verdict — ratio filed over the last 48h

(TBD — live leg next.)

## 1. Live state — both servers, first-hand

(TBD.)

## 2. Endpoint snapshot — exact counters

(TBD.)

## 3. Journal derivation — the 48h window, counted

(TBD.)

## 4. Comparison with earlier runs

| run | covered span | fires | attempts | delivered |
|-----|--------------|-------|----------|-----------|
| 6 (Muse TP13) | 48h requested / 45.04h counted | ~5,420 | 0 | 0 |
| 7 (Muse TP14) | 48h requested / 46.85h counted | ~5,410 | 0 | 0 |
| **8 (Muse 15)** | TBD | TBD | TBD | TBD |

## 5. Notes for the next run

(TBD.)

## 6. What this task did NOT do

- No restart of `Cortex.service` (or any service), no config change, no journald change, no code deploy, no live trading or money movement (none involved).
- No secret copied: any service token is sourced from the service's own `.env` on Server 1 inside the probe shell and used only as a request header on that host; the token value is never printed, logged, committed, or sent anywhere.
- No board change in this PR: the CTX-014 flip rides in the coordinator's consolidated board PR, per team rule (work PRs carry no `WORK_BOARD.yaml` hunk).
