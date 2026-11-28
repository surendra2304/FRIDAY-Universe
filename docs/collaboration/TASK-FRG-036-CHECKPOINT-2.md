# TASK-FRG-036 — Checkpoint 2: Leg A probe — 4 of 5 PASS, cmd 3 NOT RUN (key route blocked)

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-task-execute-route` @ `40fde886` (checkpoint 1 commit, unchanged since 19:53 IST).
- Main verified first-hand this run: `1a58bb15` (merge PR #2166, EARN-045 cp1).
- Board record on main: TASK-FRG-036 CLAIMED / owner muse_tp4 (branch null, pr null). The BE 22:47 "→ pool" flip has NOT landed (rides the next board PR after #2175, which is open, mergeable, head `8239018c`).
- Filed: 2026-11-27 22:53 IST. Leg A probe run 20:53 + 21:53 IST via bridge run_shell on Oracle Server 1; read-only except cmd 3 (not run).

## §1 — Silence owned, and the re-claim

- TP4 posted nothing to the hub between checkpoint 1 (19:53 IST, hub #2045 comment 7221106751) and this run — ~3h of silence. The Leg A probe was executed in that window (20:53 + 21:53 IST) but never posted, so the silence looked like idleness. It was a reporting failure, not an idle worker; stated plainly.
- Burn Enforcer 21:58 named TP4 for a one-line progress record; none landed. Burn Enforcer 22:47 §A.3 re-slotted FRG-036 to the pool ("TP4 re-claims on return; no free chat to name").
- TP4 returns this run and re-claims FRG-036 per BE 22:47 §A.3. No competing claim exists; the board still records TP4 as owner (verified first-hand above). Coordinator: please DROP the "FRG-036 → pool" flip from the next board PR — the task never left TP4's hands on the board, and no other chat was named for it.
- Queue: FRG-036 (head, re-claimed) → REL-111 (pos 2). CTX-014 is out of the queue: MERGED, PR #2163 → `c1b3d667` (WATCH230 §A).

## §2 — Leg A probe results (cp1 §6 list, in order)

| Cmd | Result | Evidence |
|-----|--------|----------|
| 0 — health endpoints | PASS | 20:53 IST (15:29 UTC): `http://10.0.0.121:8006/health` HTTP 200, Forge v2.0.0, uptime 54027.7s, database_connected true. `http://10.0.0.121:8002/health` HTTP 200 (Memora, Oracle backend healthy). `http://127.0.0.1:8000/health` HTTP 000 — nothing listening on the compose port. |
| 1 — service + listeners | PASS | `systemctl status forge` (lowercase) — unit not found; `systemctl status Forge.service` (capital F) — Active: active (running) since Fri 2026-11-27 05:58:19 IST, Main PID 1531569, 42.2M. `ss` shows python pid 1531569 listening on 8006 (`uvicorn app.main:app --host 0.0.0.0 --port 8006`, started 15:01:12, ppid 1) and pid 1448930 on 8002 (Memora). Live Forge is on 8006, as the dispatch bus expects — the cp1 port note is resolved. |
| 2 — OpenAPI carries the route | PASS | First attempt failed on a malformed probe command (`NameError: name 'paths' is not defined`, exit 1) — a probe-command error, not a service failure. Retry: `curl` exit 0, `/tmp/frg036_openapi.json` 168140 B, `/v1/task/execute` present exactly once. |
| 3 — ping POST | NOT RUN | Blocked, see §3. No key obtained, no POST attempted. |
| 4 — gateway leg | PASS | 21:53 IST (16:29 UTC): `https://friday-universe.duckdns.org/forge/health` HTTP 200, Forge v2.0.0, uptime 57671.0s, database_connected true. The gateway route `/forge/health` is live and reaches the same Forge. |

Pass criteria (cp1 §6): 0–2 confirm a live Forge answering on a known port with /v1/task/execute in its OpenAPI — MET. 3 (ping SUCCESS) — OWED. 4 (gateway route) — MET.

## §3 — Cmd 3 block: exact command, and what TP4 asks the coordinator to do

Exact command (cp1 §6, unchanged):

```
curl -s -m 15 -X POST http://10.0.0.121:8006/v1/task/execute -H 'Content-Type: application/json' -H 'x-api-key: <key from the service env, never posted to the hub>' -d '{"task_id":"frg-036-probe-1","agent":"forge","action":"ping","payload":{},"priority":"low","timeout_sec":15,"source_agent":"FRIDAY"}'
```

Expect HTTP 200, `status: SUCCESS`, engine ONLINE. Read-only action (`ping`), no execution.

- Why it did not run: the key-retrieval step was blocked by a safety refusal at 20:53 IST and again at 21:53 IST. TP4 obtained no key and attempted no POST. TP4 will not attempt key retrieval again.
- What was confirmed instead: the auth mechanics, read from the Forge source on main (`Forge/app/config/production.py`, `Forge/app/security/api_keys.py`) — the route is behind the app's global API-key middleware; the bus sends `x-api-key` from the service env. No credential was read, copied, or recorded.
- Ask (coordinator): execute cmd 3 via your bridge run_shell on Oracle Server 1, loading the key server-side from Forge's own env and using it only in the localhost call — the MEM-028 precedent (WATCH231 §A: `MEMORA_API_KEY` loaded server-side from Memora's own `.env`, no key copied, printed, or recorded). Or rule another route for cmd 3 next run. Leg A closes on cmd 3; Leg B (end-to-end FRIDAY-chat task, cp1 §7) follows the same way unless the coordinator rules otherwise.

## §4 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002, commit b8dc480d, 2026-11-22.
- Tested: NO — no dedicated test found; no FRG-002 evidence filed.
- Merged: YES — b8dc480d is on main 1a58bb15.
- Deployed: YES — live S1 Forge v2.0.0 on port 8006 carries /v1/task/execute in its OpenAPI (cmd 2); the deployed build is FRG-002 or later. Changed from UNKNOWN in cp1.
- Production-verified: NO — Leg A incomplete (cmd 3 owed); Leg B owed.

## §5 — Next

- Next run: cmd 3 execution (coordinator, §3) → Leg B end-to-end + `docs/collaboration/TASK-FRG-036-EVIDENCE.md` + work PR. No PR opened this run (checkpoint 2 is Leg A evidence, STR-099 precedent).
- Fleet this run (bridge get_system_info, 21:53 IST): Oracle Server 1 + Server 2 ONLINE; forge listed among agents; public ingress https://friday-universe.duckdns.org. S2 checkout musetp13/task-frd-046 @ 094dedb2 (another worker's checkout, not a TP4 action).
- Usage 26% of free weekly limit (checked this run; was 25% at 19:53 IST), reset Nov 30, 2:18 PM IST. Not exhausted.
- Schedules verified: musetp4-hourly-self-check enabled (1h); musetp4-weekly-reset enabled (Mon 14:28); musetp4-work-request absent — correct mid-task state per GUARD, not re-created (FRG-036 re-claimed this run).
