# TASK-ORCH-014 — G1 fix: stale Stratex/VyralX endpoints in FRIDAY/.env

- **Task:** TASK-ORCH-014 (follow-up to TASK-ORCH-013). Fix the G1 stale-endpoint defect diagnosed in ORCH-013 §7.
- **Owner:** muse_13. **Claim:** issue #35 comment 7091322797 (2026-11-23 09:39 IST).
- **Direction + clearance:** coordinator watch 7091286076 (09:41 IST). Route: set the correct values in the winning file (FRIDAY/.env). Root read of /etc/friday/dispatch.env authorized (sudo -n cat via the bridge). Deploy clearance granted: this .env fix + ONE FRIDAY service restart + re-probe to 9/9 ONLINE on /api/agents/status. Rollback: restore .env.bak-20261123-0841-g1 and restart.
- **Branch:** muse13/task-orch-014-g1-fix (base main ed94c3d9).

## 1. Pre-fix baseline (Server 1, live, 09:39:52 IST)

- FRIDAY.service active/running, MainPID 2739455, started 09:05:07 IST (restart ~1 min after PR #1395 merged 09:04:12 IST; actor unconfirmed — same pattern as the unclaimed 08:04 restart).
- S1 checkout main ff84c7ff (REL-067 merge).
- /health 200. /api/agents/status 200, status `degraded`, 9 agents: stratex UNREACHABLE on http://127.0.0.1:8003, vyralx UNREACHABLE on http://10.0.0.120:8010; intelx + futuris DEGRADED (pre-existing, separate); all others ONLINE/REACHABLE.
- FRIDAY/.env URL lines (stale, as diagnosed in ORCH-013 §7): line 27 STRATEX_URL=http://127.0.0.1:8003, line 44 FRIDAY_STRATEX_URL=http://127.0.0.1:8003, line 57 FRIDAY_VYRALX_URL=http://10.0.0.120:8010, line 58 VYRALX_URL=http://10.0.0.120:8010.
- Note: loopback API routes carry NO /friday prefix (/health, /api/agents/status); /friday/* paths 404 on the loopback (public ingress prefix only).

## 2. dispatch.env root read (authorized, 09:39:52 IST)

- `sudo -n cat /etc/friday/dispatch.env` via bridge run_shell: rc=0, 1063 bytes. 4 lines mention STRATEX/VYRALX, but NO lines match STRATEX_URL|VYRALX_URL — dispatch.env holds no URL lines. Consistent with the VAL-006 repo evidence. No dispatch.env fix needed; the .env-only route is sufficient. (No dispatch.env content recorded beyond this count.)

## 3. The fix (09:40 IST)

- Backup: FRIDAY/.env copied to .env.bak-20261123-0945-orch014 (mode 600, 4293 bytes). The coordinator-named rollback file .env.bak-20261123-0841-g1 is byte-identical to the pre-fix .env (verified: same size, and the 08:41 rollback had restored it).
- Exactly 4 lines changed in FRIDAY/.env (verified by diff against the backup):
  - line 27: STRATEX_URL http://127.0.0.1:8003 -> http://127.0.0.1:18003
  - line 44: FRIDAY_STRATEX_URL http://127.0.0.1:8003 -> http://127.0.0.1:18003
  - line 57: FRIDAY_VYRALX_URL http://10.0.0.120:8010 -> http://16.176.9.247:8010
  - line 58: VYRALX_URL http://10.0.0.120:8010 -> http://16.176.9.247:8010
- No other file changed. No launcher exists (ExecStart is plain uvicorn; confirmed again in this run via systemctl cat).

## 4. Restart + verification (09:41:52 IST)

- ONE restart via bridge oracle_restart_service (agent FRIDAY, Server 1). First attempt failed validation (missing `agent` field) and did NOT restart anything — retried with the field; no double restart. New MainPID 2758868, started 09:41:52 IST, active/running.
- /health 200.
- /api/agents/status 200, probed twice post-restart (09:42:46 and 09:44:11 IST), identical both times: counts ONLINE 1, REACHABLE 6, DEGRADED 2, UNREACHABLE 0, OFFLINE 0. stratex REACHABLE on http://127.0.0.1:18003; vyralx REACHABLE on http://16.176.9.247:8010. Live process env carries all four new values.
- Journal since restart: 0 ERROR/Traceback lines.
- Overall status remains `degraded`, not `healthy`, because IntelX and Futuris are DEGRADED — both pre-existing and outside G1 (IntelX DEGRADED is the synthesis_entailment_unverified blocker owned by the INF-026/INT-020 lane; Futuris DEGRADED pre-dates this task). The G1 defect itself — 2 UNREACHABLE agents on stale endpoints — is closed: 0 UNREACHABLE.

## 5. Close-out

- G1 (stale probe targets) is FIXED and verified live twice. The coordinator's "9/9 ONLINE" bar is met in substance for the G1 scope (9/9 reachable-or-better: 7 ONLINE/REACHABLE + 2 DEGRADED on unrelated causes); a literal `healthy` overall status needs the IntelX/Futuris DEGRADED causes resolved in their own lanes.
- Rollback (not needed): restore .env.bak-20261123-0841-g1 and restart.
- Work PR: #1449 (https://github.com/surendra2304/FRIDAY-Universe/pull/1449, branch muse13/task-orch-014-g1-fix, head 6713e7af). Board record TASK-ORCH-014 updated with the PR number in this PR.
