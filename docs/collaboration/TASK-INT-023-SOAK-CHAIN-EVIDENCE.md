# TASK-INT-023 — INT-876 soak 7-day chain evidence (INTERIM, days 1–3)

**Worker:** Muse 9. **Claim:** issue #35 comment 7092399995, 2026-11-23 ~11:02 IST, on coordinator assignment in watch 7092357321. **Branch:** `muse9/task-int-023`. **Base:** main 136533e5.

**Status of this document:** INTERIM compilation. The chain runs 2026-11-21 → 2026-11-27 (day 7 = judgement day). Today is day 3. Days 4–7 have not run yet, so no final 7-day compilation or final judgement recommendation can be filed today. This document compiles what is verifiable for days 1–3 and states plainly what is not verifiable.

## 1. What the soak is claimed to be

Board record TASK-INT-023 (drafted by the coordinator 2026-11-23 ~10:30 IST, watch refill):

> "INT-876 soak D4 enablement judgement is due earliest 2026-11-27 (owner chose 1A, once-daily 09:30 IST silent run); the chain restarts 2026-11-21 and the judgement needs the compiled chain."

Acceptance: "The 7-day soak chain evidence compiled (runs, gaps, recoveries) and filed for the D4 enablement judgement; judgement recommendation stated with the evidence."

Related: TASK-INT-019 (Muse 3, still AVAILABLE / unclaimed on main 136533e5): "move the INT-876 soak state onto S2 (a sandbox cleanup already burned 4 days of the first chain) + one traced IntelX→Memora universal→FRIDAY consumption". Its evidence states: "the first soak chain (4 days) was lost in the 2026-11-20 sandbox workspace cleanup and restarted 2026-11-21; day 2 of 7 recorded 2026-11-22."

## 2. What was checked

- **Hub scan, complete:** every issue #35 comment from 2026-11-21 00:00 UTC through 2026-11-23 ~10:44 IST (202 pages at 5/page, scanned for `soak|INT-876`, plus a `D4|876` pass over 2026-11-22). Every comment containing "soak" in that window is cited in §3.
- **Live research archive:** `GET /v1/research/live?limit=100` on live IntelX (S2, 127.0.0.1:8005), authenticated server-side with the fleet key (key never printed). Returned all 36 stored runs (retention cap 200; the archive is the complete durable record).
- **IntelX journal (S2):** `journalctl -u IntelX.service`, persisted-run lines and restarts, 2026-11-21 → 2026-11-23. Journal retention starts 2026-11-22 00:30 IST; 2026-11-21 journal is gone.
- **FRIDAY journal (S1):** dispatch/chat lines 2026-11-23 08:58–09:05 and 09:28–09:35 IST; fleet health cycle 08:59 IST.
- **IntelX /health (S2):** live read 2026-11-23 ~11:09 IST.
- **Repo + board:** no soak definition, no soak state, and no "1A"/"D4" definition exist in the repo (grep over all `*.md`/`*.yaml`/`*.py`); no soak timer, cron, or unit exists on S2 (`systemctl list-timers`, `list-units`, `/etc/cron.d`); no `INT-876` file exists under `/opt/friday_universe/IntelX`.

## 3. The day records on the hub (all of them)

| Day | Date | Hub record |
|-----|------|------------|
| 1 | 2026-11-21 | Coordinator status 7058036493 (~11:06 IST): "IntelX soak: rebuilt, day 1 of 7 recorded." Coordinator status 7060081284 (~14:12 IST): "IntelX soak day 1 recorded." |
| 2 | 2026-11-22 | **No hub comment records day 2.** The INT-019 board evidence asserts "day 2 of 7 recorded 2026-11-22" but no comment in the 2026-11-22 window says so (full scan, §2). Wherever day 2 was recorded, it is not on the hub. |
| 3 | 2026-11-23 | **No hub comment records day 3** (scan through 10:44 IST). No 09:30 run is observable on the fleet (§4). |

No comment anywhere in the scanned window defines the soak run (query, endpoint, pass criteria), the "1A" option, or what "D4" enables. The coordinator runs/records the soak (their status posts are the only day records); the run's definition and record location live with the coordinator, not in the repo or on the fleet.

## 4. Live evidence, day by day

Times below are IST. The live archive timestamps are UTC; converted (+05:30).

### Day 1 — 2026-11-21: UNVERIFIED
- Live archive: **zero runs on 2026-11-21** (the archive is durable Oracle storage; it holds runs from 2026-11-14/15/16/17, then nothing until 2026-11-22).
- IntelX journal for 2026-11-21: **unavailable** (retention starts 2026-11-22 00:30 IST).
- Hub: coordinator says day 1 recorded (7058036493, 7060081284). No run id, query, or outcome is given anywhere.
- Verdict: **claimed by the coordinator, not verifiable from any live source I can read.**

### Day 2 — 2026-11-22: NO 09:30 RUN; only off-schedule DEGRADED runs
- Live archive runs on 2026-11-22 (IST): 22:53:47 `lr_20bd1d6f8e7d425aa5462b37`, 22:54:02 `lr_eddb842b40f840f4a27d31c7`, 23:28:50 `lr_7d551ec705b24dcbab1fceb9` — all DEGRADED, synthesis failed. (Five further runs 2026-11-23 00:45–00:49 IST belong to the INT-021 deploy verification, all DEGRADED.)
- Journal confirms the same three runs; **nothing at 09:25–09:40 IST** (the 09:30 slot is empty in the IntelX journal).
- Verdict: **no once-daily 09:30 run is observable on day 2.** The day-2 record asserted in the INT-019 evidence has no live corroboration.

### Day 3 — 2026-11-23: NO 09:30 RUN; three 09:00 FRIDAY-chat runs, all DEGRADED
- Live archive runs: 09:00:29 `lr_6d6a7103193348adb29bd4e8`, 09:01:31 `lr_645ee1c10a6a42c2b0df427c`, 09:01:58 `lr_eaa4e3d30b724b5ea94a22c8` — all DEGRADED, synthesis failed.
- FRIDAY journal (S1) shows these came through FRIDAY chat/dispatch: `POST /api/v1/dispatch/send?agent=IntelX&action=research_live` 09:00:30 and 09:01:59, and user-turn processing at 09:01:17 ("Research the latest AI model releases and give me the highli…"). Three runs in two minutes through FRIDAY chat is the INT-020 3-consecutive-runs shape (Muse 7), not a once-daily 09:30 silent run. They are **not counted as the day-3 soak run**.
- FRIDAY journal 09:28–09:35 IST: no IntelX research activity at all — **the 09:30 slot is empty again**.
- IntelX /health at ~11:09 IST: **HTTP 503, status degraded** (`research: unknown/NO_LIVE_PROBE`, `model_provider: unknown/CONFIG_ONLY`; database/storage ok). FRIDAY fleet cycle 08:59 IST: 4/8 healthy; IntelX unhealthy (`IntelX:SERVICE_DOWN` suppressed in cooldown).
- IntelX restarts on 2026-11-23: 00:43 (INT-021 deploy, Muse 9), 04:22, 07:37, 08:58 (INF-026 deploy, Muse 9), 09:04 (unattributed — after the 09:00 runs). Five restarts in one day; the 04:22/07:37/09:04 restarts are unattributed in this evidence.
- Verdict: **no 09:30 soak run observable on day 3.**

### The systematic failure behind every recent run
Sampled run `lr_6d6a7103193348adb29bd4e8` (2026-11-23 09:00:29, query "latest AI model releases"), read back in full from the live archive:

- status DEGRADED; `synthesis_status: failed`; `synthesis_error.reason: synthesis_entailment_unverified`.
- 5 sources retrieved, 4 distinct domains, 15 findings — **15/15 single-source** (`single_source_share: 1.0`, `min_independent_sources_required: 2`); `primary_source_count: 0`; `question_answered: false`.
- `summary`: "Retrieved 5 source document(s); synthesis failed (synthesis_entailment_unverified) — returning 15 unsynthesised raw finding(s) (verbatim source excerpts), not a synthesised brief."

All 11 live-research runs on 2026-11-22 → 2026-11-23 are DEGRADED with synthesis failed. The Gemini 503 that blocked synthesis before (INF-026) is gone from the path — synthesis now reaches Inference (HTTP 200) — but entailment verification fails systematically because the findings are single-source. This is the same finding as the INF-026 deploy evidence (2/2 DEGRADED, `synthesis_entailment_unverified`); it is not a new regression.

## 5. Gaps and recoveries

- **Gap 1 — the first chain (4 days) is gone.** Lost in the 2026-11-20 sandbox workspace cleanup (INT-019 evidence). Nothing recoverable: no archive rows, no journal, no hub records with run ids.
- **Gap 2 — the soak still lives in a sandbox, not on the fleet.** No soak timer/cron/unit/file exists on S2 (§2). INT-019 (move the state onto S2) is still AVAILABLE and unclaimed. Until it lands, a sandbox cleanup can burn the chain again.
- **Gap 3 — the run definition and the day records are not in any source I can read.** No query, endpoint, pass criterion, or record location is documented; the only day records are two coordinator status lines for day 1. The INT-019 evidence's day-2 assertion has no discoverable source.
- **Recovery (partial):** the live research archive (`/v1/research/live`, Oracle-backed, 36 runs) is a durable, queryable record of every live run since 2026-11-14 — the chain can be rebuilt on it once the soak runs through the live service. Today it proves the negative: no 09:30 run exists in it.

## 6. Judgement recommendation (INTERIM — not the D4 judgement)

**Do not enable on the current evidence.** The chain as defined (7 consecutive once-daily 09:30 runs, judgement due 2026-11-27) has **zero verifiable passing days**: day 1 is coordinator-asserted only, days 2–3 have no 09:30 run in any live source, and every live research run on 2026-11-22 → 2026-11-23 is DEGRADED with synthesis failing on `synthesis_entailment_unverified` (15/15 single-source findings). IntelX /health is 503/degraded today.

The D4 judgement cannot be made before 2026-11-27 in any case (day 7 has not run). For the judgement to be evidence-based, three things must happen first:

1. **Name the runner and the record:** who executes the 09:30 run, by what route (endpoint/query), what counts as a pass, and where each day's record (run id + outcome) is filed. Until then the chain is unverifiable by any worker.
2. **Land INT-019:** move the soak state onto S2 so the chain survives a sandbox cleanup, and verify the daily run writes there.
3. **Fix or disposition the systematic synthesis failure:** 11/11 recent runs DEGRADED on `synthesis_entailment_unverified`. A soak that records seven DEGRADED days is a chain of failures, not an enablement case — the judgement needs either green days or a filed disposition of why DEGRADED days still count.

## 7. What remains for Muse 9 on INT-023

- Days 4–7 (2026-11-24 → 2026-11-27) have not run. The final 7-day compilation and the final D4 recommendation can only be filed after the 2026-11-27 run.
- This interim compilation is filed now so the evidence gap is on the record before more days pass silently. The work PR carries this doc + the board record (IN_REVIEW).
- **Open question for Muse (coordinator):** confirm the soak runner/record location (§6.1) and whether INT-023 stays open with Muse 9 through 2026-11-27 for the final compilation, or closes on this interim filing with the final compilation as a follow-up task.

— Muse 9, 2026-11-23 ~11:20 IST
