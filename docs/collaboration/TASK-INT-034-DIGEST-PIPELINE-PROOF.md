# TASK-INT-034 — IntelX digest pipeline: last 7 days of non-instant alerts batched, not dropped

**Task:** TASK-INT-034 — prove the digest pipeline batched (not dropped) the last 7 days of non-instant alerts; file per-alert batch/delivery evidence.
**Worker:** Muse 1. **Claim:** hub issue #1483 comment 7106321457, 2026-11-23 ~21:25 IST, on direct assignment by Muse (coordinator watch 7106041874, ~21:14 IST; queue INT-034 head -> FUT-025 -> FRD-040). Claim PR #1522 (board-only) MERGED 2026-11-23 21:41:28 IST (merge commit 892e1d16).
**Branch:** `muse1/task-int-034-digest-pipeline-proof`, base main `9a6b99a15568a815e211c1a9a8e34965d1de7f02` (branch advanced onto current main for the work PR; the claim commit `2ab73c37` is already in main via PR #1522, merge `892e1d16`).
**Verification:** 2026-11-23 ~21:29–21:40 IST, live records on both servers via the bridge (read-only probes; no config changed, no restart, no merge by me). Re-checked 2026-11-23 ~22:00–22:02 IST (S1 drainer state + outbox, S2 producer state + journal): unchanged — still exactly the 4 alerts below, no new alert since 2026-11-20 19:16 IST. Follows up TASK-INT-031 (Muse 7, work PR #1509 merged e3c4b5f2), which verified the same 4 alerts on 2026-11-23 ~18:25 and ~19:30 IST; this task re-verifies them first-hand and extends the window to 2026-11-23 22:02 IST.

## Verdict

**Acceptance met.** In the last 7 days (2026-11-16 → 2026-11-23 22:02 IST) exactly **4 non-instant alerts** fired, and **all 4 were batched into the morning digest or posted directly outside quiet hours — 0 dropped, 0 sent instantly, 0 duplicates delivered.** No new alert has fired since 2026-11-20 19:16 IST.

| # | dedupe_key | Alert | Fired (UTC) | Batch / delivery |
|---|-----------|-------|-------------|------------------|
| 1 | `intelx.watch:india_tech_regulatory:55fa9a3b9e05db08` | SEBI AI usage guidelines (YourStory, score 3) | 2026-11-16 23:51:57 | held quiet hours 2026-11-17 05:23:37 IST → **digest posted 2026-11-17 07:00:08 IST** |
| 2 | `intelx.watch:ai_model_releases:8f6af8c44a4a1bfb` | GPT-6.2 Astra and Sol (OpenAI Blog, score 8) | 2026-11-17 18:24:44 | held quiet hours 2026-11-18 00:01:22 IST → **digest posted 2026-11-18 07:00:43 IST** |
| 3 | `intelx.watch:ai_model_releases:056cf0b58a3dbace` | Gemini API Tool Retrieval (Google AI Blog, score 5) | 2026-11-19 18:41:01 | held quiet hours 2026-11-20 00:11:21 IST → **digest posted 2026-11-20 07:01:00 IST** |
| 4 | `intelx.watch:ai_model_releases:701a571706ec6c00` | Harness adapters (Hugging Face Blog, score 4) | 2026-11-20 13:45:38 | outside quiet hours → **posted directly 2026-11-20 19:16:14 IST** |

## How it was verified (live records, both servers)

**Consumer (Server 1, FRIDAY drainer).** Drainer state `/opt/friday_universe/FRIDAY/state/proactive_intelx_watch.json`, re-read 2026-11-23 ~21:30 IST — byte-identical in substance to the INT-031 leg-2 read:

- `offset: 3644`, `instant_offset: 0`, `held: []`, `malformed_total: 0`.
- `delivered_keys`: all 4 dedupe keys above, each exactly once.
- `alert_log`: 7 entries — 3× `held_quiet_hours` → 3× `quiet_hours_digest` (posted), 1× daytime `posted`. No `instant` delivery anywhere.
- FRIDAY.service active, MainPID 3114851; kill switch `FRIDAY_PROACTIVE_INTELX_WATCH=on` in `/opt/friday_universe/FRIDAY/.env`. The drainer is alive and polling: the state file was re-touched 2026-11-23 21:27:59 IST with the offset unchanged (no new envelopes to consume).

**Outbox file (Server 1).** `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: 4 lines, 3,644 bytes, last modified 2026-11-20 19:16 IST — untouched since. Drainer offset 3644 = the entire file consumed. All 4 envelopes carry `quiet_hours_exempt: false`; envelopes 3–4 carry `alert_class: "digest"` (envelopes 1–2 predate the field and are treated as digest-class by the drainer). Each envelope's `dedupe_key` matches `delivered_keys` exactly.

**Producer (Server 2, IntelX).** IntelX.service active, MainPID 605920, NRestarts 0 (same PID as INT-031 leg 2, running since 2026-11-23 12:00:36 IST). Producer state `/opt/friday_universe/IntelX/data/watches/state.json` (1,214,709 bytes, updated 2026-11-23 21:02 IST — still polling):

- `alerts_by_day`: `ai_model_releases {'2026-11-20': 1}`, `india_tech_regulatory {}` — no alert counted on Nov 21, 22 or 23.
- `seen` map covers first_seen 2026-11-20 18:26:50 → 2026-11-23 15:32:58 UTC with exactly 1 fired item (the Nov 20 harness-adapters alert, `701a571706ec6c00`); `ai_model_releases` statuses: 25 below_threshold, 2329 baseline, 1 alerted, 1 suppressed_budget; `india_tech_regulatory`: 333 below_threshold, 24 excluded, 0 fired.
- S2 `outbox.jsonl`: 855 bytes, 1 line, modified 2026-11-20 23:56 — only the re-fire of envelope 4 (see below).

**Watch polls (Server 2 journal).** `journalctl -u IntelX.service` retains ~31.5 h (earliest entry Nov 22 19:33 IST). In the retained window (Nov 22 19:33 IST → Nov 23 21:32 IST): **134 watch poll lines, every one `alerted=0`** (both watches, 30-minute cadence; latest polls Nov 23 21:02:57/21:02:58 IST). Zero poll lines with `alerted>0` in the retained window.

**Instant lane never fired.** `instant_outbox.jsonl` is absent on Server 1 (`/opt/friday_universe/IntelX/data/watches/`) and on Server 2 — no instant-class envelope has ever been produced, so nothing could have bypassed the digest.

**Code unchanged since INT-031.** No commits on `IntelX/intelx/watches/engine.py` or `FRIDAY/src/friday/proactive/intelx_watch.py` since 2026-11-23 13:00 UTC (GitHub commits API, both paths empty). Producer: `alert_class` defaults to `"digest"` (`engine.py`, `build_envelope`, `alert_class: str = "digest"`); `instant = alert_class == "instant"` — digest-class envelopes go to the main outbox only, instant-class additionally to the sibling `instant_outbox.jsonl` (`default_outbox_path` / `default_instant_outbox_path`). Drainer: `intelx_watch.py` lines ~401–429 — quiet-hours holds queue into `state["held"]` and `_flush_held` posts them as ONE digest notification at/after 07:00 (`"IntelX watch alerts held for you:\n"`, up to 6 lines). No code change was needed for this task; the routing is as designed.

## The one re-fire — by design, not a loss

Server 2's producer re-fired envelope 4 (`701a571706ec6c00`, same `envelope_id f7f7b3f3…`) at 2026-11-20 23:56:48 IST: it is the only line in S2's `outbox.jsonl` (855 bytes, modified 2026-11-20 23:56). The S1 drainer already held it in `delivered_keys`, so it was deduped — no second delivery, no second digest entry. A re-fire that the drainer absorbs is the designed behaviour; it is not a dropped or duplicated alert. (Same finding as INT-031; unchanged.)

## Caveats (stated, not hidden)

- **No alert has fired since 2026-11-20 19:16 IST.** The 7-day window therefore contains exactly the 4 alerts INT-031 already verified; this task re-verifies all 4 first-hand and proves nothing new arrived Nov 20–23. The evidence covers every alert the pipeline has ever produced (4/4); there is no older record to check.
- **Producer `seen` map is a rolling window.** S2 `state.json` now covers first_seen Nov 20–23 only; the Nov 16–19 fired alerts are no longer in the producer `seen` map (pruned/rotated since INT-031, when the key still appeared twice). The S1 outbox + drainer state retain all 4 envelopes and the full delivery log, so the per-alert proof does not depend on the producer map.
- **Journal retention is ~31.5 h.** Poll-level `alerted=0` evidence is direct only for Nov 22 19:33 IST → Nov 23 21:32 IST. For Nov 20 19:16 → Nov 22 19:33 IST the no-new-alert proof rests on the S1 outbox mtime (unchanged Nov 20 19:16), the S2 outbox mtime (Nov 20 23:56, re-fire only), and `alerts_by_day` (only 2026-11-20 has a count).
- **Delivery standard is the drainer's own record.** "Posted" means the drainer's `alert_log` records `delivery: "posted"` for the digest / direct post (the same standard INT-031 used). No separate Telegram-side receipt was pulled this run.
- **This task verifies the digest leg only.** It does not prove the INT-020 research path or the FRIDAY web-chat / IntelX synthesis gates.

## Note on the git-hold question (context, not part of the proof)

The owner has now answered the git-hold question directly: hub #1483 comment 7106289183 (~21:24 IST, via Muse) — Surendra did NOT impose any git hold; no hold exists, none was imposed, no clearance is needed or pending; the INT-034/FUT-025/FRD-040 queue is unblocked. The "cite it or claim INT-034" direction was discharged by claiming INT-034 (comment 7106321457, claim PR #1522).

## States

- Implemented: YES (verification task; no code change — the pipeline already behaves as specified)
- Tested: YES (4/4 live envelopes accounted for end-to-end, producer → outbox → drainer → delivery; re-verified first-hand 2026-11-23 ~21:30 IST; 134/134 retained polls alerted=0)
- Merged: NO (work PR pending; claim PR #1522 merged 2026-11-23 21:41:28 IST, merge commit 892e1d16)
- Deployed: N/A (no code change)
- Production-verified: YES (live records on both servers)

## Files

- This evidence doc: `docs/collaboration/TASK-INT-034-DIGEST-PIPELINE-PROOF.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-034 CLAIMED → IN_REVIEW, this PR)
