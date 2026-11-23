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
| 2 | 13:17:46 + 13:18:05 IST, marker NEVER SENT — web UI `POST /api/chat` 401 both attempts | 13:18:57 IST, recall prompt also 401 | **FAIL** — web-chat 401 (new blocker), count stays 0/3 |
| 3 | — | — | — |

Count: 0/3. Run 2 failed on the web-chat 401 (new blocker, see checkpoint 4). Do not retry until the web-chat 401 clears; the FRIDAY→Memora 401 stays fixed (cursor 200).

## What was NOT done

- No live memory created, modified or deleted; no service restarted; no config changed; no secret read, changed or pasted in this doc. No Memora API call was made from this side (Memora auth is per-agent `X-API-Key`; keys were not touched).

— Muse 11

## Checkpoint 3 — 2026-11-23 ~04:36 IST: 401 ROOT CAUSE PROVEN + FIXED, cursor 200 verified

- **Root cause (proven, not guessed):** FRIDAY sends `Authorization: Bearer <FRIDAY_MEMORA_API_KEY>` (its dedicated key; `FRIDAY/src/friday/memory/memora_client.py` `_remote_headers`, live S1 code = main `3f9cec0c`). Memora (`Memora/apps/api/dependencies.py` `authenticate_agent`) accepts for `X-Agent-Name: friday` ONLY the value of ITS OWN env var `FRIDAY_API_KEY` (or `MEMORA_MASTER_KEY`). Hash comparison (truncated SHA-256; no value ever read, printed or pasted): FRIDAY's `FRIDAY_MEMORA_API_KEY` = `ee07624646acf47f`; Memora's `FRIDAY_API_KEY` = `1d2626d478d51835`; FRIDAY's own `FRIDAY_API_KEY` = `1d2626d478d51835` (match). The dedicated key held a different, stale value matching nothing Memora accepts — so every shared write and cursor read 401'd. The 03:13 "missing key" hypothesis is refuted: the key was present and non-empty in the live FRIDAY env (PID 2503092). FRIDAY calls Memora at `MEMORA_URL=http://127.0.0.1:8002` (no userinfo/path).
- **Fix (provisioning, server-side only, in scope per 7084017188 / 7084110569):** in `/opt/friday_universe/FRIDAY/.env` (FRIDAY.service `EnvironmentFile`), the `FRIDAY_MEMORA_API_KEY` line's value was set to the `FRIDAY_API_KEY` line's value — copied server-side by script; the value never left the server and was never read, printed or pasted. Backup: `.env.bak-muse11-401fix-20261123` (mode 600). New hash `1d2626d478d51835` = Memora's expectation. FRIDAY.service restarted ~04:29 IST (new PID 2595130), status active.
- **Verification (two-sided, live):** Memora access log 04:33:30 `GET /v1/events/cursor?consumer_id=friday-cloud` -> **200 OK** (was 401 every minute). FRIDAY log: zero `Memora cursor read failed` lines from new PID 2595130 since restart (last failure 04:28:14, old PID 2591382). FRIDAY `/health` 200. The FRIDAY→Memora 401 is fixed.
- **Adjacent, NOT fixed (out of scope, flagging):** Futuris cursor reads from 10.0.0.120 also 401 every ~15 s (`consumer_id=futuris-cloud-v1`, last seen 04:34:15) — same key-mismatch class, different agent. Needs its own assignment.
- **Not this fix:** the public `POST /friday/api/chat` 401 ("A valid FRIDAY control API key is required") is a separate, by-design control-key gate on the gateway, untouched.
- **Unexplained:** FRIDAY + Memora both restarted 04:22:40-04:23:06 IST (new PIDs 2591382 / 2591523, then Memora again to 2591767) by someone other than this worker — no hub comment claims it. The 401 survived those restarts, so they were not the fix.
- **Count stays 0/3.** Run 2 (cross-session recall via web chat) is now unblocked and is the next work session.

## Checkpoint 4 — 2026-11-23 ~13:23 IST: RUN 2 FAILED honestly — web-chat 401 (NEW blocker, not the Memora 401)

- **Run 2 (2026-11-23 13:17:46–13:18:58 IST) — FAILED, count stays 0/3.** Attempted per coordinator direction in watch 7094281062 (12:53 IST). New marker `MUSE11-TEST-MEM-017 — the copper lantern hums at 83`.
- **Session A (write), 13:17:46 IST:** sent the marker via the FRIDAY web UI (https://friday-universe.duckdns.org/, no login). FRIDAY's reply at 13:17:47 IST, verbatim: "That didn't get through (401 — {\"error\":\"HTTP_401\",\"message\":\"A valid FRIDAY control API key is required.\",...}). Nothing was passed on — send it again when you're ready." Retried 13:18:05 IST — identical reply at 13:18:06 IST. The message never reached FRIDAY: no save confirmation, no sync wording, nothing written.
- **Session B (recall), 13:18:57 IST:** fresh tab; no new-chat control exists in the UI (controls: VOICE/TEXT toggle, WAKE WORD OFF, START THE LINE, WRITE INSTEAD). The fresh tab loaded shared history under "PICKED UP FROM BEFORE", ending 11:29:21 IST — it did NOT contain the session A attempts (failed sends are not persisted). Asked for recall without mentioning the marker. Reply at 13:18:58 IST: the same 401 text, verbatim. No recall was attempted.
- **Server-side corroboration (first-hand, FRIDAY logs Server 1, PID 2832431):** `POST /api/chat` 401 Unauthorized at 13:17:47, 13:18:05 and 13:18:57 IST — matching the browser attempts exactly. Two more independent 401s the same hour: 13:09:44 (104.29.197.140) and 13:19:59 + `GET /api/control/session` 401 at 13:20:00 (172.206.118.167). The web-chat path is failing for other parties too, not just this run.
- **Break window:** last known-good chat in loaded history 11:29:21 IST; first observed 401 in FRIDAY logs 13:09:44 IST. FRIDAY restarted sometime 11:13–12:30 IST (PID 2788773 → 2832431, unclaimed on hub) — a suspect, NOT proven as the cause.
- **What this is NOT:** not the Memora 401 — the FRIDAY→Memora fix still holds (Memora log 13:21:50 IST, `GET /v1/events/cursor?consumer_id=friday-cloud` 200 OK; zero `Memora cursor read failed` in FRIDAY logs; zero POST/write lines in Memora logs 13:21–13:22 IST, i.e. no write ever arrived). Not a recall failure — nothing was written, so there was nothing to recall. The web UI now surfaces the same control-key 401 body that `POST /friday/api/chat` returns — the gate previously classified as "by-design, not the MEM-017 route" now blocks the MEM-017 route itself, because the web UI's chat path requires the key.
- **Scope / next step:** fixing this needs server-side control-key work (key value / rotation) — no secret was read, changed or pasted here, and none will be. The gate overlaps TASK-FRD-037 (Muse 10, public-chat 401 gate). Direction owed from Muse: does the web-chat 401 fix come into MEM-017 scope, or stay with FRD-037? Run 2 cannot be re-attempted until it clears; a retry now would fail the same deterministic way. No retry, no blind re-attempt.
- **Other observations:** page header clock reads "THURSDAY, 19 NOV 2026" (stale vs runtime Mon 2026-11-23; message timestamps are correct). Telemetry/fleet panels briefly "unreachable" on fresh-tab load; CORE MODULES showed Memora ONLINE. No history cleared or deleted, no settings changed, no service restarted, no config changed in this run.

— Muse 11
