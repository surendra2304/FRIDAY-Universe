# TASK-FRD-065 — FRIDAY webchat 401 diagnosis run 2 (checkpoint 2)

**Date:** 2026-11-27 ~17:40 IST (Muse TP8)
**Status:** DEPLOYED CONSOLE VERIFIED live — the D-023 credential flow is in
  the deployed Halo console bundle. Owner-key live 200 owed to the owner
  (owner-gated browser session).
**Branch:** `musetp8/task-frd-065-webchat-401-diagnosis` (base `b1fe4365`)
**Board:** TASK-FRD-065 CLAIMED / owner muse_tp8, on live main `fdecf5f7`
  (next_action: "Claimed by muse_tp8; FRD-065 live leg next.")

## 1. Live probes this run (direct curl, first-hand)

- `GET https://friday-universe.duckdns.org/friday/health` → **HTTP 200
  in 3.57s**, `overall: healthy`, observed `2026-11-27T12:07:15Z`
  (17:37:15 IST), platform `Linux-7.0.0-1014-aws-x86_64` — the gateway
  serves the FRIDAY-Server (Server 3) copy, which is live. (Checkpoint 1:
  200 in 6.39s; faster this run.)
- `POST https://friday-universe.duckdns.org/friday/api/chat`
  (`{"message":"FRD-065 self-check probe 17:34 (no credential)"}`) →
  **HTTP 401 in 1.43s**, body byte-identical to FRD-038 run 1 and to
  checkpoint 1:
  `{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.","detail":"A valid FRIDAY control API key is required.","success":false}`
  The gate is unchanged and live — keyless remote callers still 401, as
  designed (the gate must NOT be stripped, VAL-005 F2).

## 2. Deployed console bundle carries the D-023 flow — VERIFIED

- `GET https://friday-universe.duckdns.org/` → **HTTP 200 in 1.99s**,
  `<title>FRIDAY</title>`, Next.js console (`/friday/_next/static/...`).
- All 9 initial chunks fetched first-hand. Chunk
  `27fe61w12sxqu.js` (41,457 bytes,
  md5 `467cc86091043d6cf31cda7e279c615d`) contains the D-023 flow verbatim
  from `FRIDAY/ui/lib/controlSession.ts` (on main since merge `768e18da`):
  the `X-FRIDAY-Control-Token` header constant, the `friday_prime_key`
  storage key, the `ControlAuthError` class (`control-auth-required`),
  the `fcs1` session token, the `/api/control/session` mint path and the
  1200-second TTL. The flow is in the initial bundle, not lazy-loaded.
- Interpretation: the deployed console DOES present a credential path.
  The 401 in §1 is the gate meeting a credential-less caller, not a
  missing fix. The remaining clean-pass step — owner pastes the key once
  in a real browser session and chat answers 200 — is owner-gated: the
  key is never read, pasted, or recorded here.

## 3. Adjacent state this run

- Fleet (bridge `oracle_fleet_health`, 17:38 IST): S1 disk 51% (48G
  avail), uptime 44d — stable. **S2 disk 95% (2.7G avail)** — worse than
  91% / 4.9G at checkpoint 1 (15:39); REL-096 media backup running on
  S2. S2 memory 293 MB available. Flagged, not a TP8 action; M10 S2
  `/tmp` cleanup report still owed.
- S2 FRIDAY copy DOWN (OOM-killed 15:07 IST, `:10000` HTTP 000 per TP6);
  restart HOLDS per WATCH219 §D / Burn Enforcer 17:47 §A until the
  REL-096 backup finishes AND TP1's FRD-064 floor quantification lands.
  The gateway is unaffected — it serves the live Server-3 copy (§1).
- CD deploy failure REL-116 now CLAIMED by Muse 4 (hub 7217683270).
- Board on live main `fdecf5f7`: FRD-065 CLAIMED owner muse_tp8;
  REL-109 AVAILABLE owner muse_tp8 (queue pos 3); EARN-038 AVAILABLE
  owner muse_tp8. Queue FRD-065 → REL-109 → EARN-038. No re-slot.
- Weekly usage 15% of free weekly limit (reset Dec 2, 5:10 PM IST;
  additional tokens 0% used).
- Hub rule in force (WATCH218 §E, Burn Enforcer 17:01 §F, 17:47 §F):
  TP8 hourly self-check posts are out — post only at claim, completion,
  genuine block, wrap-up. This checkpoint filing is posted as the owed
  work product (≤5 lines with evidence), not as a self-check.

## 4. Next (owner leg)

Owner pastes the control key once in a real browser session against the
deployed console; a chat call then answers 200 through the remote path.
TP8 cannot perform that step. No TP8-side work remains on FRD-065
except recording the owner-leg result when it lands.

— Muse TP8
