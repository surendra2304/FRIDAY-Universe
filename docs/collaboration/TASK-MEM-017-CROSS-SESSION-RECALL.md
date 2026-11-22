# TASK-MEM-017: Cross-session memory recall through FRIDAY — live proof

**Worker:** Muse 11 · **Date:** 2026-11-22 · **Branch:** `muse11/task-mem-017-cross-session-recall`
**Board:** TASK-MEM-017 (Memora: prove cross-session memory recall through FRIDAY, 3 consecutive live runs)
**Claim:** issue #35 comment 7081832744, on coordinator assignment in watch 7081706110 (~21:27 IST). Base: main `4a16d09f`.

## Verdict (read this first)

_RUN 1 FAILED honestly — 0/3. Not a recall failure: a write-path failure._ The marker never reached Memora. FRIDAY's shared write to Memora was rejected HTTP 401 at 23:19:37 IST; FRIDAY saved the marker locally and queued a re-sync, which exhausted at 23:21:37 IST — the marker remains local-only. Session B's recall did run (10 hits returned, other stored items surfaced) but the marker was not among them because it was never written to shared memory. **Do not retry until the FRIDAY→Memora 401 is fixed** — a retry would fail the same deterministic way. The fix (FRIDAY's Memora credentials) needs coordinator direction; no credential was read, changed or pasted by this worker.

## Probe design

- Each run: session A — ask FRIDAY (web chat) to remember a marker (test data only, prefix `MUSE11-TEST-MEM-017`, e.g. a nonsense phrase + number). Session B — a fresh FRIDAY chat session: ask FRIDAY what was remembered / to recall the marker. PASS = FRIDAY returns the marker verbatim in the fresh session, with no prompting of the marker content.
- 3 consecutive PASSes required. Any FAIL resets the count to 0 (same honesty rule as INT-020 run 1).
- Test data only; no live memory touched; no service restarted; no config changed.

## Route — established 23:13–23:19 IST

- FRIDAY web chat: `https://friday-universe.duckdns.org/` serves the FRIDAY Next.js web UI (verified 200). No login prompt; chat accepts typed messages. Chat endpoint is `POST /api/chat`; conversation history is `GET /api/v1/conversation/history`.
- Caveat: the UI has no visible new-chat button, and conversation history is shared across tabs — session B (fresh tab) loaded session A's history ("PICKED UP FROM BEFORE"). Session isolation for future runs needs a real new-conversation control or a cleared history; secondary to the 401 blocker, since the marker never reached Memora anyway.

## Preconditions verified live (2026-11-22 ~22:13–23:25 IST)

- MEM-016 fix is live: Memora.service on S1 active (running) since 21:25:29 IST, Main PID 2374327, `/health` 200; Muse 9's live probe re-run passed 26/26 (hub comment 7082275213, ~22:10 IST): promoted SHARED readable by friday/intelx (200, was 403), UNIVERSAL readable by futuris (200, was 403). The G1 watch item from the claim run is resolved — live Memora is post-fix.
- FRIDAY.service on S1 restarted 22:51:13 IST (FRD-036 deploy, PID 2418691, uvicorn :10000), `/health` 200. Both Oracle servers ONLINE. Gateway `/api/agents/status` 200 — 7 ONLINE (incl. memora, intelx, futuris), 2 UNREACHABLE (stratex, vyralx — not MEM-017 blockers).
- FRD-036 merged as PR #1394 → main `ebb9240e`; peer paths IntelX/Futuris/Sentinel confirmed ONLINE via the gateway.
- Board record for TASK-MEM-017 absent on main (verified 23:13 IST: zero hits in WORK_BOARD.yaml). Record to be created in the work PR, same pattern as MEM-016 / FRG-002 / INT-020.

## Run 1 — FAILED (2026-11-22 23:19–23:21 IST)

- **Session A (write), 23:19:37 IST:** asked FRIDAY to remember `MUSE11-TEST-MEM-017 — the violet kettle sings at 47`. FRIDAY replied verbatim: "Saved on the local memory backend, Boss: MUSE11-TEST-MEM-017 — the violet kettle sings at 47. I will ask you about it later in a new chat session.. Shared Memora synchronization is not confirmed."
- **Session B (recall), 23:20:25 IST, fresh tab:** asked "What did I ask you to remember earlier? Please repeat back anything you remember from our earlier conversation, exactly as I said it." (Marker never mentioned in the prompt.) FRIDAY replied verbatim: "Of course I remember, Boss. Here's what I'm holding onto: • my favorite chai is masala chai and I review the fleet every morning at 9 • my secret favorite number is owner favorite test marker ZQ1794340686". Neither `MUSE11-TEST-MEM-017` nor "the violet kettle sings at 47" appears. **FAIL.**
- **Root cause, from FRIDAY's own service log (Server 1, read-only):**
  - 23:19:37 `[WARNING] [friday.memory.memora_client]: Memora shared write failed (HTTP 401); saving locally and queueing re-sync.` — the write never reached Memora.
  - 23:19:49 / 23:20:49 / 23:21:49 `Memora cursor read failed (HTTPError)` / "Memora event consumption did not complete" — cursor reads also failing, same 401 class seen in Memora logs (`GET /v1/events/cursor?consumer_id=friday-cloud 401`).
  - 23:20:25 session B recall ran normally: primary draw returned 10 hits, owner-fact probe 10 hits (2 presentable) — the recall path works; it surfaced other stored items, just not a marker that was never written.
  - 23:21:37 `[WARNING] [friday.memory.memora_client]: Memora re-sync exhausted for local fact c20d738f-f6d2-4699-acab-68d29caeab23; it remains local-only.` — the queued re-sync gave up; the marker is permanently local-only.
- **Conclusion:** the 401 on FRIDAY→Memora shared writes (and cursor reads) is the blocker. It is the same 401 class watched since 22:15 IST, now proven as the cause of a failed run. Memora itself is healthy (`/health` 200, direct reads/writes by other agents proven 26/26 in MEM-016); FRIDAY's Memora credentials are what Memora rejects. Fix needs coordinator direction — this worker did not read, change or paste any credential.

## Run log

| Run | Session A (write) | Session B (recall) | Result |
| --- | --- | --- | --- |
| 1 | 23:19:37 IST, marker written locally only (Memora write 401) | 23:20:25 IST, marker absent; other items recalled | **FAIL** — write-path 401, count stays 0/3 |
| 2 | — | — | — |
| 3 | — | — | — |

Count: 0/3. No retry until the FRIDAY→Memora 401 is fixed.

## What was NOT done

- No live memory created, modified or deleted; no service restarted; no config changed; no secret read, changed or pasted in this doc. No Memora API call was made from this side (Memora auth is per-agent `X-API-Key`; keys were not touched).

— Muse 11
