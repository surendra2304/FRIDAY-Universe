# TASK-FRD-065 — FRIDAY webchat 401 diagnosis run 2 (checkpoint 1)

**Date:** 2026-11-28 ~15:00 IST (Muse 3)
**Status:** 401 REPRODUCED for bare callers — intended gate, unchanged from run 1. Deployed console SHIPS the D-023 fix.
**Branch:** `muse3/task-frd-065-webchat-401-diagnosis-run-2`

## 1. Live re-probe (2026-11-28 14:59 IST, direct curl, no credential)

- `POST https://friday-universe.duckdns.org/friday/api/chat` → **HTTP 401** (1.79s)
  `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.","detail":"A valid FRIDAY control API key is required.","success":false}`
- `POST https://friday-universe.duckdns.org/api/chat` → **HTTP 401**, same body (1.51s)
- `GET /friday/health` → **HTTP 200** (2.06s), `overall: healthy`, `friday_core 2.0.0`, Oracle SELECT 1 OK, disk 40138.6 MB free, observed 2026-11-28T09:29:09Z.

## 2. Server-side corroboration (FRIDAY-Server, bridge run_shell)

- Journal `FRIDAY.service` (PID 140472): `09:29:06 UTC POST /api/chat 401`, `09:29:08 UTC POST /api/chat 401`, `09:29:10 UTC GET /health 200` — the exact probes above, Caddy having stripped the `/friday` prefix.
- `FRIDAY.service` active/running, MainPID 140472, active since 09:04:05 UTC (14:34 IST), NRestarts=9.
- Note: Oracle Server 1 `FRIDAY.service` is inactive (dead, disabled) and `caddy.service` failed — the gateway is served from FRIDAY-Server (AWS), not S1. S1 state flagged, not changed; no server move made.

## 3. Deployed console carries the D-023 fix

- `GET /friday/` → 200, Next.js Halo console; all 9 JS chunks fetched.
- Chunk `27fe61w12sxqu.js` contains the fix, verbatim: `X-FRIDAY-Control-Token` header constant, `friday_prime_key` localStorage key, `ControlAuthError`, `GET /api/control/session` with `x-friday-api-key` + `cache: "no-store"`, and `control-auth-required` — "No owner key is stored in this browser, so no control session can be minted." / "FRIDAY needs the owner key in this browser before it can answer — paste it once and the chat re…".
- Repo main also has `FRIDAY/ui/lib/controlSession.ts`, `FRIDAY/ui/lib/wire.ts`, `FRIDAY/ui/components/ControlGate.tsx` (all 200); FRD-042 deploy PR #1647 merged 2026-11-24.
- A bare browser therefore gets the paste-once ControlGate by design; the 401 is the gate doing its job, not a regression.

## 4. Verdict

- **401 reproduced; root cause unchanged from FRD-038 run 1:** intended gate (VAL-007) + credential-less caller.
- **Fix code is merged AND deployed.** What remains unproven is the owner-key browser path — one chat call answering 200 through the remote path after the key is pasted once. That needs a browser session with the owner key and cannot be proven from here; no key was read, pasted, or recorded.
- Next: work PR with this evidence; the owner-key live proof rides the coordinator/owner, not this task.

— Muse 3

## 5. Checkpoint 2 — live re-probe (2026-11-28 ~16:09 IST, direct curl, no credential)

- `POST https://friday-universe.duckdns.org/friday/api/chat` → **HTTP 401** (2.04s), identical body to checkpoint 1.
- `POST https://friday-universe.duckdns.org/api/chat` → **HTTP 401** (1.99s), identical body.
- `GET /friday/health` → **HTTP 200** (2.37s), `overall: healthy`, observed 2026-11-28T10:38:58Z.
- `GET /friday/` → 200; chunk `27fe61w12sxqu.js` still served (41,457 bytes, HTTP 200, 4.57s); all five D-023 markers still present: `X-FRIDAY-Control-Token`, `friday_prime_key`, `ControlAuthError`, `control-auth-required`, `/api/control/session` (1 occurrence each).
- Diagnosis unchanged since checkpoint 1 (~15:00 IST): the 401 is the intended gate; the deployed console still ships the D-023 fix.
- Work PR #2330 verified first-hand this run: OPEN, head 7fc4fcf0 = branch tip, mergeable True / clean, CI 9/9 (7 success + 2 skipped, 0 failed), 0 reviews — paired verdict + coordinator merge still owed; no verifier named for #2330 in the hub window through comment 7238004972 (WATCH269 not yet posted).
- Board verified first-hand (live main 3b5091de): FRD-065 CLAIMED / muse_3 / P1. Note: the board branch field reads `muse3/task-frd-065-webchat-401-diagnosis-r2` while the real branch is `muse3/task-frd-065-webchat-401-diagnosis-run-2`; board pr field is null (flip rides the coordinator board PR).
- Owner-key browser proof still owed (needs a browser session with the owner key; no key read, pasted, or recorded).

— Muse 3
