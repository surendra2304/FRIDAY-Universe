# TASK-INT-026 — IntelX: research-digest delivery proof — checkpoint 1 (claim + producer state + delivery-path map, 2026-11-28 ~16:30–17:00 IST)

**Task:** TASK-INT-026 (P2) — "IntelX: research-digest delivery proof — verify the last 3 digests reached Futuris/Stratex consumers".
**Worker:** Muse 10. **Claim:** hub #2045 comment 7238333115, 2026-11-28 ~16:36 IST, on assignment WATCH269 §C (hub 7238212243) — M10 ← TASK-INT-026.
**Branch:** `muse10/task-int-026-research-digest-delivery-proof`, created from main `3b5091de`.
**Usage:** 6% of free weekly limit (last checked 16:13 IST; resets Dec 5, 02:03 IST).

**Filename note:** the board record (coordinator board PR #2338, blob `34b00b7f`) names the evidence file `TASK-INT-025-EVIDENCE.md`, but INT-025 is a different, MERGED task (TP6, PR #2160) with no such file. Filed as `TASK-INT-026-EVIDENCE.md` per convention; coordinator to confirm / correct the board line in the next board PR. Board flip rides #2338; no board hunk in this PR, per the coordinator-only flip rule.

## Verdict (checkpoint 1)

**TRACED, NOT DELIVERED — no receipt evidence found yet for any of the last 3 digests on either consumer.** The producer (IntelX watch loop on IntelX-Server) is live and the last 3 digest envelopes are identified first-hand, but every delivery path I could trace is either down, mis-addressed, or missing its receiving end. This is a checkpoint, not a completion. No live change made anywhere — read-only probes only.

## Producer — IntelX-Server S6 (probed ~16:37–16:55 IST, read-only)

- **Watch loop LIVE.** `IntelX/uvicorn-8005.log` (2,243 bytes, mtime 10:53 UTC): fetches every ~30 min, `alerted=0` on every recent cycle (all dup / below threshold). `IntelX/data/watches/state.json` (1,564,863 bytes) rewritten 10:53 UTC, minutes before the probe.
- **Outbox unchanged since Nov 27 21:44 UTC.** `IntelX/data/watches/outbox.jsonl` — 6 envelopes, 5,608 bytes, mtime Nov 27 21:44 UTC. All `alert_class: digest`. No new envelope in ~19 hours.
- **Last 3 digests (by `fired_at`), identified first-hand:**
  1. `86591617…` — `india_tech_regulatory` — "RBI Clubs 25 Card Payment Circulars Into A Single Framework" — fired 2026-11-27T21:44:43Z, score 3, Inc42.
  2. `54ed70ea…` — `ai_model_releases` — "INT-878 proof: introducing a model routing probe for the IntelX alert leg" — fired 2026-11-27T07:20:09Z, score 4, OpenAI Blog.
  3. `8ca3ca25…` — `ai_model_releases` — "GPT-6 models demonstrate intrinsic protein-design capabilities" — fired 2026-11-24T21:30:32Z, score 4, OpenAI Blog.
- **INT-060 transport live.** S6 localhost `GET /v1/watches/outbox` → 401 without key (route mounted; was 404 pre-deploy). IntelX uvicorn PID 74894 holds :8005 (started Nov 27 08:52 UTC, the INT-063 deploy restart). A second IntelX uvicorn (PID 81891) appeared at 11:08 UTC and was gone by ~11:10 UTC — it never held :8005; treated as a transient failed start, not investigated further this run.
- **No delivery attempts in the IntelX log.** `uvicorn-8005.log` has zero `webhook` lines and zero `research` lines (watch lines only). Note the log is only 2.2 KB — it may rotate; absence here is not proof no attempt was ever made.

## Delivery paths mapped (code + live config, first-hand)

There are two distinct digest kinds, with different consumers — the task's "last 3 digests" needs the coordinator's read on which set counts (see G4).

### A. Watch-digest envelopes → FRIDAY drainer (pull)

- Consumer in code: `FRIDAY/src/friday/proactive/intelx_watch.py` — pulls `GET /v1/watches/outbox` (`INTELX_WATCH_OUTBOX_URL`) or reads the outbox file; delivers into FRIDAY chat.
- **Consumer down.** S1 FRIDAY down since 2026-11-24 13:42 IST (INT-063 ckpt 1); drainer state `FRIDAY/state/proactive_intelx_watch.json` offset 3644, last entry 2026-11-20. FRIDAY-Server (gateway `/friday/health` 200) is a separate deployment; whether its drainer runs is unprobed.
- **Receipt check:** none of the 3 envelope IDs appears anywhere under Futuris or mesh on S6 (`grep -rl` over both trees, 0 hits).

### B. Research findings → Futuris webhook (push)

- Sender: `IntelX/intelx/integrations/futuris_context.py` `notify_futuris_research_relevant()` (called from `orchestration/engine.py:88` and `api/v1/futuris.py:102`); also publishes a Memora notice.
- Target: `FUTURIS_WEBHOOK_URL`, default `http://futuris:8000/api/v1/webhooks/research-finding-relevant`. **No override** in `IntelX/.env` and none in the running IntelX process env (PID 74894).
- **Target unreachable with defaults.** Host `futuris` does not resolve on S6 (`getent hosts futuris` empty); nothing listens on :8000; Futuris actually listens on :8004. Delivery cannot succeed as configured.
- **Receiving end IS live.** Futuris on S6 (PID 63602, :8004, since Nov 27 05:10 UTC): `GET /v1/webhooks/research-finding-relevant` → **405** (route mounted, POST only). `app.py` includes `webhooks_router` under `/v1`. Futuris `/health` → 503 degraded by its own capability report (forecasting `NO_MODEL_PROBE`; storage 13/13 tables OK, DB round-trip OK).
- **Receipt store not yet queried.** Notices land in Futuris `intelx_notices` (`event_id = intelx-webhook:<run_id>`), but the store is Oracle Autonomous Database — no local file to read. Query path owed (see G3); no credential was sought or used.

### C. Research findings → Stratex webhook (push)

- Sender: `IntelX/intelx/integrations/stratex_context.py` `notify_stratex_trade_signal()` (called from `orchestration/engine.py:98`, `api/v1/stratex.py:307`, `ingestion/feed_service.py:81`).
- Target: `STRATEX_WEBHOOK_URL`, default `http://stratex:8000/api/v1/webhooks/intelx-signal`. **No override** in `IntelX/.env` or the running process env.
- **Target unreachable AND no receiving end.** Host `stratex` does not resolve on S6; Stratex API lives on Stratex-Server (S4) :8003; and Stratex code has **no `intelx-signal` inbound route anywhere** (`grep -rn` 0 hits) — its `api/webhooks.py` is an outbound emitter only.
- **Stratex's actual intake is a pull.** `Stratex/intelligence/intelx_client.py` (`IntelXMarketClient`) pulls from the gateway `https://friday-universe.duckdns.org/intelx` (env `INTELX_URL`/`INTELX_BASE_URL`). `bot.log` has zero `intelx` mentions. Stratex daemon PID 74531 running on S4; S4 API :8003 `/health` → 503 (trading_engine ok, market_data unknown).

## Gaps (smallest fix first)

- **G1 — Webhook targets mis-addressed (blocks B and C).** Defaults point at unresolvable docker hostnames on port 8000 (`futuris:8000`, `stratex:8000`); the real listeners are Futuris :8004 on S6 and Stratex :8003 on S4. Smallest fix: set `FUTURIS_WEBHOOK_URL` / `STRATEX_WEBHOOK_URL` (or base URLs) to reachable targets. Needs coordinator direction — no env change made.
- **G2 — Stratex has no inbound `intelx-signal` route.** Even with G1 fixed, the Stratex webhook has nowhere to land. Either add the receiver or bless the pull path (`IntelXMarketClient` → gateway `/intelx`) as the Stratex delivery proof and verify it end to end.
- **G3 — Futuris receipt query owed.** `intelx_notices` lives in Oracle Autonomous DB. Owed: a credential-free read path (Futuris read endpoint or coordinator direction). No receipt evidence for the last 3 digests can be claimed until this is answered.
- **G4 — "Last 3 digests" definition owed.** Outbox watch-digest envelopes (traced above, §A) vs IntelX research runs delivered as webhooks (§B/C). No research run was observed in the IntelX log this run. Coordinator to confirm which set counts; checkpoint 2 traces the confirmed set to receipt.
- **G5 — (observation, not a gap)** transient second IntelX uvicorn PID 81891 at 11:08 UTC, exited unaided; only PID 74894 holds :8005.

## States

- Implemented: NO (tracing only; no delivery proof yet)
- Tested: NO
- Merged: NO (work PR this run carries checkpoint 1 only)
- Deployed: N/A
- Production-verified: NO

## Files

- This evidence doc: `docs/collaboration/TASK-INT-026-EVIDENCE.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-026 CLAIMED / owner muse_10 in coordinator board PR #2338, blob `34b00b7f`; not yet on live main — no board hunk in this PR)
- Related: `docs/collaboration/TASK-INT-063-EVIDENCE.md` (INT-060 transport deploy), `docs/collaboration/TASK-INT-062-EVIDENCE.md` (fast-lane wait state)

— Muse 10, 2026-11-28 ~17:00 IST
