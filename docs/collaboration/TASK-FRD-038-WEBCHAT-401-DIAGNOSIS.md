# TASK-FRD-038 — web-chat 401 diagnosis (checkpoint 1)

**Date:** 2026-11-23 ~20:30 IST (Muse 11)
**Status:** ROOT CAUSE FOUND (code + live proof). Fix NOT yet implemented.
**Branch:** `muse11/task-frd-038-webchat-401`

## 1. Live re-probe (2026-11-23 20:17 IST, direct curl, no credential)

- `POST https://friday-universe.duckdns.org/friday/api/chat` → **HTTP 401**
  `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.","detail":"A valid FRIDAY control API key is required.","success":false}`
- `POST https://friday-universe.duckdns.org/api/chat` → **HTTP 401**, same body.
- `GET /friday/health` → **HTTP 200**, `overall: healthy`, observed 2026-11-23T14:47:46Z, service friday_core 2.0.0, Oracle SELECT 1 OK, 71321.3 MB disk free.

Server-side corroboration (bridge `oracle_get_logs`, FRIDAY.service, Server 1):
- `20:17:43 POST /api/chat 401 Unauthorized` and `20:17:45 POST /api/chat 401 Unauthorized`
  (both probes; Caddy strips the `/friday` prefix — same endpoint).
- `20:17:46 GET /health 200`.

## 2. Root cause (read from main `0c974d26`, `FRIDAY/src/friday/api/server.py`)

- `POST /api/chat` is guarded by `Depends(_require_control_access)` (server.py ~5071).
  `_require_control_access` demands the control API key (`x-friday-api-key` /
  `Authorization: Bearer`) or a valid `fcs1` session token from every **remote**
  caller; loopback callers stay keyless.
- The gate was restored by **TASK-VAL-007, commit `1cd77f1d`, 2026-11-22T18:21:49Z**
  ("fix(friday): require control credential on POST /api/chat"), closing VAL-005
  finding F2 (the `Origin` header is client-controlled, so origin-only gating let
  any unauthenticated remote client drive the command pipeline).
- The endpoint docstring states the deploy consequence plainly: *"the keyless
  dashboard (D-025) sends no credential, so after deploy its chat answers 401
  until a credential flow is restored in the dashboard (paste-once key ->
  auto-refreshing fcs1 session, the D-023 design). Do not deploy this change
  without that clearance."*
- The deployed Halo console sends no credential: `FRIDAY/ui/lib/wire.ts`
  `sendChat()` posts `{ message }` with only `Content-Type`; no
  `x-friday-api-key`, bearer, or `fcs1` token, and no call to
  `GET /api/control/session` anywhere under `FRIDAY/ui/`. (The older
  `FRIDAY/src/friday/api/app.js` has a paste-once key flow; the Next.js console
  does not use it.)
- The mint endpoint `GET /api/control/session` (server.py ~1197) mints a 20-min
  HMAC `fcs1` token; for remote callers it also requires the key in the header —
  "the owner pastes the key exactly once per browser and it never leaves that
  browser's storage."

## 3. Timeline consistency

- MEM-017 run 1 (2026-11-22 23:19 IST) succeeded via the web UI — **before**
  the VAL-007 commit (23:51 IST).
- Break window 11:29–13:09 IST on 2026-11-23 (from the MEM-017 run-2 report) is
  when the gate's deploy reached Server 1; run 2 failed 13:17 IST on the same 401.
- This is therefore **intended gate behaviour meeting a credential-less
  dashboard**, not a key mismatch, not a config regression, and not a Memora
  fault. The Memora 401 fix is unaffected (see §5).

## 4. Fix direction (not yet implemented)

Restore the D-023 credential flow in the Halo console (`FRIDAY/ui`): paste-once
key → mint `fcs1` session via `GET /api/control/session` → attach the token to
chat calls → auto-refresh before the 20-min TTL elapses. Do **NOT** strip the
gate from `/api/chat` — that reopens VAL-005 F2. Live verification of the fix
needs the owner key pasted once in a browser session (the key itself is never
recorded here); code + unit tests can be proven without it, and a loopback-only
check cannot prove the remote path.

## 5. Adjacent state verified this run

- **Memora 401 fix HOLDS.** Bridge `oracle_get_logs` (Memora, 200 lines,
  window 20:20:32–20:23:45 IST): two `GET /v1/events/cursor?consumer_id=friday-cloud`
  200 OK, zero 401s in the whole window. Futuris cursor 200s continue.
- **FRIDAY restarts, actor unknown:** FRIDAY.service stopped gracefully and
  restarted at 20:00:43 IST (new PID 3072442) and again at 20:10:11 IST (new PID
  3077856). Both restarts were clean; the service is up and healthy on PID
  3077856. Who/what ordered them is not in these logs — flagged, not assumed.
- **RAM warning continues:** proactive notification queued 19:44 IST (91.8%) and
  19:49 IST (90.3%).
- Board on main `0c974d26`: TASK-FRD-038 CLAIMED / owner muse_11 / branch
  `muse11/task-frd-038-webchat-401`; TASK-MEM-017 IN_PROGRESS / owner muse_11.
  No board change rides in this checkpoint.

## 6. Next (superseded by §7 — checkpoint 2 landed 22:13 IST)

Implement the console credential flow + tests (checkpoint 2), then live-verify
with an owner-key browser session and run MEM-017 recall run 2 of 3 through
FRIDAY chat. Coordinator watch 7104166018 demands a status report now and warns
of re-slotting if none lands by the next run — this checkpoint + the hourly
status post answer that demand.

## 7. Checkpoint 2 — D-023 credential flow implemented (2026-11-23 ~22:13 IST)

**Status:** IMPLEMENTED, unit-tested, work PR open. NOT yet live-verified
(the owner key has to be pasted once in a real browser session; no key was
read, pasted, or recorded here) and NOT yet deployed.

**Direction honoured:** the gate stays. `POST /api/chat` is untouched
server-side; the console now presents a credential, exactly as the D-023
design and the legacy console (`FRIDAY/src/friday/api/app.js`) do it.

**What changed** (branch `muse11/task-frd-038-webchat-401`):

- `FRIDAY/ui/lib/controlSession.ts` (new) — the flow, window-independent:
  paste-once key in `localStorage` under the legacy key name
  `friday_prime_key` (same origin, so a key pasted in the old console
  works here) → `GET /api/control/session` with `x-friday-api-key`
  → 20-min HMAC `fcs1` token, cached, refreshed 5 min before the TTL
  elapses (`startControlSessionRefresh`, same margin as app.js) →
  `X-FRIDAY-Control-Token` header on calls. Typed errors:
  `control-auth-required` (no key in this browser),
  `control-key-rejected` (stored key refused / rotated),
  `control-unavailable` (mint 503 / network). Fetch, storage, base
  URL and clock are injectable, so it runs under plain Node.
- `FRIDAY/ui/lib/wire.ts` — `requestJson` gains an opt-in `{ auth: true }`
  path: attach the session header when one can be minted, one
  refresh-and-retry on a 401 with a stored key, then a
  `ControlAuthError` (no silent generic failure). `sendChat` and
  `fetchHistory` use it; every other caller is byte-identical. Without
  a stored key the request goes out bare, so loopback callers keep
  working keyless. `sendChat`'s ceiling timer now uses the global
  `setTimeout` (identical in browsers, node-testable).
- `FRIDAY/ui/components/ControlGate.tsx` (new) — the paste-once prompt,
  shown when a chat call answers 401. Stores the key, mints, starts the
  refresh timer; a rejected key is cleared from storage and the error
  says so. `FRIDAY/ui/app/globals.css` gains the `.control-gate` rules.
- `FRIDAY/ui/components/stage/Conversation.tsx` — a 401 from `sendChat`
  raises the gate (`required` vs `rejected`) with an honest bubble
  instead of the old generic "didn't get through"; a stored key starts
  the background refresh on mount.

**Tests (plain Node, no runner — the repo's `*.test.ts` convention):**

- `FRIDAY/ui/lib/controlSession.test.ts` (new): mint request shape
  (path, `x-friday-api-key`, `no-store`), 401 → key-rejected, 503 →
  unavailable, token-shape validation, storage round-trip, cache reuse
  inside the TTL, re-mint inside the 5-min margin, no-key → no mint and
  empty headers, refresh timer re-mints before expiry.
- `FRIDAY/ui/lib/wire.test.ts` (extended): `sendChat` with a stubbed
  fetch — bare call with no key, 401 → `control-auth-required` with no
  retry, mint + token header with a key, stale-token 401 → refresh +
  retry with the fresh token, mint 401 → `control-key-rejected` with no
  chat attempt, double 401 → `control-key-rejected`.
- Results this run: `node lib/wire.test.ts` — all expectations passed;
  `node lib/controlSession.test.ts` — all expectations passed;
  `npx tsc --noEmit` in `FRIDAY/ui` — zero errors; `eslint` on the six
  changed files — clean. (First `tsc` run caught a real bug in the new
  `requestJson` — a missing return path, TS2366 — fixed before filing.
  The first `npm install` in this run was truncated by a full /tmp
  tmpfs and produced empty `.d.ts` files; a clean reinstall on the
  workspace disk fixed it.)

**Deliberately NOT in this checkpoint:** no server change; no key in the
repo, in logs, or in this doc; the thread-restore call rides the same
auth path but its failure mode is unchanged (a fresh thread, not an
error wall); the activity WebSocket still opens without a token
(`?token=` upgrade is a separate, later piece of work if the socket
starts 401ing remotely).

**Still owed:** live verification — owner pastes the key once in the
deployed Halo console, one chat call answers 200 through the remote
path, then MEM-017 recall run 2 of 3. That needs a browser session
with the owner key and cannot be proven from here. Until it lands, the
401 gates WF-002 live leg, FRD-037, INT-020 run 3, and VAL-009 re-probe
exactly as before — the code is ready, the proof is not.

— Muse 11
