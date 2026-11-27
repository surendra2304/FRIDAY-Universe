# TASK-FRD-065 — FRIDAY webchat 401 diagnosis run 2 (checkpoint 1)

**Date:** 2026-11-27 ~15:43 IST (Muse TP8)
**Status:** 401 REPRODUCED live — same gate, same message as FRD-038 run 1.
**Branch:** `musetp8/task-frd-065-webchat-401-diagnosis` (base `b1fe4365`)
**Board:** TASK-FRD-065 CLAIMED / owner muse_tp8, on live main `841bec7f`
  (next_action: "Claimed by muse_tp8; FRD-065 live leg next.")

## 1. Live probe this run (direct curl, no credential)

- `POST https://friday-universe.duckdns.org/friday/api/chat`
  (`{"message":"FRD-065 checkpoint-1 probe (no credential)"}`) → **HTTP 401
  in 2.37s**, body byte-identical to FRD-038 run 1 (2026-11-23):
  `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.","detail":"A valid FRIDAY control API key is required.","success":false}`
- `GET https://friday-universe.duckdns.org/friday/health` → **HTTP 200
  in 6.39s**, `overall: healthy`, observed `2026-11-27T10:09:40Z`
  (15:39:40 IST), Oracle SELECT 1 OK. Service alive; the 401 is the auth
  gate, not an outage.
- Bridge `oracle_curl_health` for the same `/friday/health` endpoint
  **timed out** ("The read operation timed out") while the direct probe
  answered in 6.39s — bridge-side read timeout, not gateway-down evidence.
  (TP10 also reported slow /health this run; gateway is slow but alive.)

## 2. Run-1 baseline (FRD-038, Muse 11, 2026-11-23)

- Root cause found: `POST /api/chat` is guarded by
  `_require_control_access` (`FRIDAY/src/friday/api/server.py` ~5071),
  restored by TASK-VAL-007 commit `1cd77f1d` (2026-11-22); the deployed
  Halo console sent no credential, so remote chat answered 401. Intended
  gate behaviour meeting a credential-less dashboard — not a key mismatch,
  not a config regression.
- Checkpoint 2 (2026-11-23 ~22:13 IST) implemented the D-023 credential
  flow in `FRIDAY/ui` (`controlSession.ts`, `wire.ts`, `ControlGate.tsx`,
  `Conversation.tsx`), unit-tested, work PR open at the time.
- **Fix code is on main now:** `FRIDAY/ui/lib/controlSession.ts` present
  on live main `841bec7f` (first added in merge `768e18da`, PR #1788,
  2026-11-25 13:10 IST). The FRD-038 branch
  `muse11/task-frd-038-webchat-401` still exists on remote (`124b97cd`).

## 3. Interpretation (checkpoint 1 scoping)

- The 401 reproduces exactly: keyless remote caller → gate → 401. The
  diagnosis is unchanged from run 1 — the question for run 2 is whether
  the deployed console now presents a credential, i.e. whether the
  FRD-038 fix is DEPLOYED and live-verified, not whether the gate exists.
- **Not yet verified this run:** whether the deployed Halo console bundle
  carries the `controlSession` flow, and the owner-key live 200 (owner
  pastes the key once in a real browser session — the key is never read,
  pasted, or recorded here). That is checkpoint 2.
- No server change is proposed: stripping the gate would reopen VAL-005 F2.

## 4. Adjacent state this run

- Fleet (bridge `oracle_fleet_health`, 15:39 IST): S1 disk 51% (48G
  avail), uptime 44d; **S2 disk 91% (4.9G avail)** — flagged, not a TP8
  action (was 90% at 13:34, 4.9G avail at 14:34).
- Board on live main `841bec7f`: FRD-065 CLAIMED owner muse_tp8;
  REL-109 AVAILABLE owner muse_tp8 (queue pos 3); EARN-038 queued pos 3
  (earning lane). WEB-008 pool (→ muse_17 per WATCH214 §2). VYR-061
  VERIFIED owner muse_tp8 pr 1692 (unchanged).
- Burn Enforcer 15:20 §H: first commit owed by ~15:48 (2h bar) — this
  commit answers it.

## 5. Next (checkpoint 2)

Verify the deployed console bundle carries the D-023 flow; then the
owner-key live 200 through the remote path (owner-gated browser session),
or record the exact failing step if the deployed console still 401s with
the fix in place.

— Muse TP8
