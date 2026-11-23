# TASK-INT-031 — IntelX digest pipeline: non-instant alerts batched, not dropped

**Task:** TASK-INT-031 — verify the digest pipeline batches non-instant alerts correctly, from live records.
**Worker:** Muse 7. **Claim:** issue #1483 comment 7101918141, 2026-11-23 ~18:30 IST, on coordinator direction in push 7100469274 (~17:40 IST), under the blocked-head rule (TASK-INT-020 stays blocked head of record).
**Branch:** `muse7/task-int-031-digest-pipeline`, base main `3e8a4a14` (board PR #1504 merged 19:11 IST).
**Verification:** 2026-11-23 ~18:25 IST (leg 1) and re-verified first-hand ~19:30–19:35 IST (leg 2, this run). All probes read-only; no config changed, no restart, no merge by me.

## Verdict

**Acceptance met.** Every non-instant alert in the live record was batched into the morning digest (or posted directly outside quiet hours) — **0 dropped, 0 sent instantly, 0 duplicates delivered.** The pipeline does what the task asks it to prove.

| # | dedupe_key | Alert | Fired (UTC) | Drainer handling | Delivered |
|---|-----------|-------|-------------|------------------|-----------|
| 1 | `intelx.watch:india_tech_regulatory:55fa9a3b9e05db08` | SEBI AI usage guidelines (YourStory, score 3) | 2026-11-16 23:51:57 | held quiet hours 2026-11-17 05:23:37 IST | digest 2026-11-17 07:00:08 IST |
| 2 | `intelx.watch:ai_model_releases:8f6af8c44a4a1bfb` | GPT-6.2 Astra and Sol (OpenAI Blog, score 8) | 2026-11-17 18:24:44 | held quiet hours 2026-11-18 00:01:22 IST | digest 2026-11-18 07:00:43 IST |
| 3 | `intelx.watch:ai_model_releases:056cf0b58a3dbace` | Gemini API Tool Retrieval (Google AI Blog, score 5) | 2026-11-19 18:41:01 | held quiet hours 2026-11-20 00:11:21 IST | digest 2026-11-20 07:01:00 IST |
| 4 | `intelx.watch:ai_model_releases:701a571706ec6c00` | Harness adapters (Hugging Face Blog, score 4) | 2026-11-20 13:45:38 | outside quiet hours — posted directly | posted 2026-11-20 19:16:14 IST |

## How it was verified (live records, both servers)

**Consumer (Server 1, FRIDAY drainer).** `FRIDAY/src/friday/proactive/intelx_watch.py` (TASK-PRO-002) tails IntelX's outbox `data/watches/outbox.jsonl` under the sibling IntelX checkout. Kill switch `FRIDAY_PROACTIVE_INTELX_WATCH=on` confirmed in `/opt/friday_universe/FRIDAY/.env:77`. Drainer state `/opt/friday_universe/FRIDAY/state/proactive_intelx_watch.json`, re-read 2026-11-23 ~19:30 IST, unchanged since the 18:25 leg:

- `offset: 3644`, `instant_offset: 0`, `held: []`, `malformed_total: 0`.
- `delivered_keys`: all 4 dedupe keys above, each exactly once.
- `alert_log`: 7 entries — 3× `held_quiet_hours` → 3× `quiet_hours_digest` (posted), 1× daytime `posted`. No `instant` delivery anywhere.

**Outbox file (Server 1).** `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: 4 lines, 3,644 bytes, last modified 2026-11-20 19:16 IST. Drainer offset 3644 = the entire file consumed. All 4 envelopes carry `quiet_hours_exempt: false`; envelopes 3–4 carry `alert_class: "digest"` (envelopes 1–2 predate the field and are treated as digest-class by the drainer). Each envelope's `dedupe_key` matches `delivered_keys` exactly.

**Producer (Server 2, IntelX).** `IntelX/intelx/watches/engine.py`: `alert_class` defaults to `"digest"` (line 741); `instant = alert_class == "instant"` (line 747) — digest-class envelopes go to the main outbox only, instant-class additionally to the sibling `instant_outbox.jsonl` (lines 850–860, `default_outbox_path` / `default_instant_outbox_path`). No code change was needed for this task; the routing is as designed.

**Instant lane never fired.** `instant_outbox.jsonl` is absent on Server 1 (`/opt/friday_universe/IntelX/data/watches/`) and on Server 2 — no instant-class envelope has ever been produced, so nothing could have bypassed the digest.

## The one duplicate — by design, not a loss

Server 2's producer re-fired envelope 4 (`701a571706ec6c00`, same `envelope_id f7f7b3f3…`) at 2026-11-20 23:56:48 IST: it is the only line in S2's `outbox.jsonl` (855 bytes, modified 2026-11-20 23:56) and the key appears twice in S2's producer `state.json`. The S1 drainer already held it in `delivered_keys`, so it was deduped — no second delivery, no second digest entry. A re-fire that the drainer absorbs is the designed behaviour; it is not a dropped or duplicated alert.

## Caveats (stated, not hidden)

- **Coverage window is Nov 16–20, not 7 days.** No alert has fired since 2026-11-20 19:16 IST: S2 watch polls since then all report `alerted=0`, and the S1 outbox is untouched since 19:16 IST Nov 20. The evidence covers every alert the pipeline has ever produced (4/4); there is no older record to check.
- **This task verifies the digest leg only.** It does not prove the INT-020 research path: the FRIDAY web-chat 401 gate and the IntelX synthesis entailment gate are unchanged (see § Gates below) and are owned by Muse 11 (FRD-038) and Muse 9 (INT-033).

## Gates re-verified this run (INT-020 blocked head, for the record)

- **Gate 1 — FRIDAY web-chat 401, UNCHANGED.** `POST https://friday-universe.duckdns.org/friday/api/chat` → HTTP 401, byte-identical body (`"A valid FRIDAY control API key is required."`), ~19:26 IST. Owned by Muse 11 (FRD-038, diagnosis still not started per coordinator watch 7103106790).
- **Gate 2 — IntelX synthesis, UNCHANGED.** `IntelX.service` on S2 active/running, MainPID 605920 since 2026-11-23 12:00:36 IST (no restart since the 12:25 check); `/healthz` 200, `/health` 503-by-design (REL-067); `INFERENCE_URL=http://10.0.0.121:8001` (INT-021 fix in place). Journal since 12:00 IST shows **zero** synthesis attempts — last observed remain the three 09:00:29/09:01:31/09:01:58 IST 200s, all persisted DEGRADED (Muse 9 entailment blocker). Run 3 still waits on Gate 1 per coordinator direction 7094281062.

## States

- Implemented: YES (verification task; no code change — the pipeline already behaves as specified)
- Tested: YES (4/4 live envelopes accounted for end-to-end, producer → outbox → drainer → delivery)
- Merged: NO (awaiting Muse)
- Deployed: N/A (no code change)
- Production-verified: YES (live records on both servers, re-verified twice this day)

## Files

- This evidence doc: `docs/collaboration/TASK-INT-031-DIGEST-PIPELINE-VERIFICATION.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-031 CLAIMED → IN_REVIEW, this PR)
