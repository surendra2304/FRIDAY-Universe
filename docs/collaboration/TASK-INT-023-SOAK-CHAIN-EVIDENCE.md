# TASK-INT-023 — INT-876 soak 7-day chain evidence (INTERIM, days 1–3)

**Worker:** Muse 9. **Claim:** issue #35 comment 7092399995, 2026-11-23 ~11:02 IST, on coordinator assignment in watch 7092357321. **Branch:** `muse9/task-int-023`. **Base:** main 136533e5.

**Status of this document:** INTERIM compilation (days 1–3) + FINAL-LEG PROGRESS (§8, day 4). The chain runs 2026-11-21 → 2026-11-27 (day 7 = judgement day). Days 5–7 have not run yet, so no final 7-day compilation or final judgement recommendation can be filed today. This document compiles what is verifiable for days 1–4 and states plainly what is not verifiable. Final-leg claim: coordinator watch 7136251890 (20:37 run, 2026-11-24), answering work request 7136053755 — INT-023 stays open with Muse 9 through 2026-11-27.

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
- **Open question for Muse (coordinator):** confirm the soak runner/record location (§6.1) and whether INT-023 stays open with Muse 9 through 2026-11-27 for the final compilation, or closes on this interim filing with the final compilation as a follow-up task. **Answered in part 2026-11-24:** coordinator watch 7136251890 (20:37 run) assigns INT-023 to Muse 9 as interim head through 2026-11-27; and TASK-INT-032 (Muse 7, PR #1553, merged b63d0f30) now defines the runner in the repo — `IntelX/scripts/run_int876_soak.py` + `deploy/intelx-soak-runner.service/.timer`, daily 09:30 IST, day records `/var/lib/friday-universe/intelx-soak/YYYY-MM-DD.json` + the live archive. The timer itself is NOT installed on any server (§8); "1A"/"D4" definitions are still undefined in any readable source.

## 8. Final-leg progress — day 4 (2026-11-24)

**Filed 2026-11-24 ~21:40 IST. Claim:** coordinator watch 7136251890 (20:37 run), answering work request 7136053755 (hub #1483 comment 7136549618). Board on main 4bc4159c: IN_REVIEW, owner muse_9, pr 1460, branch muse9/task-int-023 (fully merged, fast-forwarded to main 4bc4159c). Work PR: this PR.

**Day 4 verdict: NO 09:30 soak run on 2026-11-24.**

What was checked this run (all read-only):

- **Live research archive (Oracle-backed, complete; 40 most recent runs listed):** the most recent run overall is `lr_84b50db5`, 2026-11-24 06:29:59 IST, query "Oracle Cloud Infrastructure Always Free Ampere A1 …", SUCCESS, task `disp_bddae31fb8af` — a bus dispatch run, not the soak (wrong slot, wrong query). **Zero runs after 06:30 IST on Nov 24; zero runs in the 09:30 slot; zero runs with task_id `soak-876-2026-11-24`; zero runs with the standing soak query "latest AI model releases" on Nov 24.** Read via the S1 IntelX checkout (`/opt/friday_universe/IntelX`, .env present) because the S2 IntelX directory is gone (see below) — same durable store, same read path as INT-023 §4 / INT-035 §3.
- **S2 journal, IntelX.service 09:20–09:45 IST:** two lines only — watch polls at 09:38:33/34 (`ai_model_releases`, `india_tech_regulatory`). No `research_live` dispatch. IntelX was still running on S2 at 09:38 (PID 622490, the INF-028 restart).
- **S1 journal, IntelX.service 09:20–09:45 IST:** no entries — IntelX was not running on S1 at 09:30.
- **Hub scan:** every #1483 comment 2026-11-24 07:41–21:15 IST (390 comments, pages 95–172; first-150-char bodies) — no soak/876/INT-023/INT-032/INT-035 mention except this run's claim (7136549618). **Zero #1483 comments at all 09:30–13:35 IST** (4-hour hub silence). No coordinator day-4 record. Caveats: scan bodies truncated to 150 chars; the 20:37 watch was read in full (no day-4 record); the 02:54–07:41 IST window is covered by INT-035's scan, which found no soak record.
- **Soak runner state:** timer NOT installed — no `intelx-soak-runner.timer` unit on S2 or S1, no `/var/lib/friday-universe/intelx-soak/` record dir on either server. The INT-032 deploy step (install/enable timer) never happened; the owner stop order (17:26 IST) then froze live moves, and the Oracle consolidation (owner order 19:31 IST) moved IntelX off S2.
- **IntelX has no running home right now (verified both servers):** S2 — `IntelX.service` inactive (MainPID 0), `/opt/friday_universe/IntelX` directory gone, `/health` empty. S1 — `IntelX.service` MASKED (`ActiveState=failed`), `/health` empty; S1 checkout at `b51ef05f` (merge PR #1669), behind main 4bc4159c. Where IntelX runs after the consolidation is unanswered — the same open question as INT-042 gate 3 (20:37 watch).

**Chain tally after day 4: zero verifiable passing soak days out of four elapsed days.** Days 1–3 as before (§§3–4); day 4 joins them — no 09:30 run observable in any live source. The INF-028 fix is live (5 SUCCESS runs Nov 24 01:18–01:43 IST), so a green soak day is possible in principle — but no soak run was executed to prove it.

**Block (posted on the hub this run):** the soak chain cannot produce days 5–7 while (a) the INT-032 timer is not installed on any server and (b) IntelX has no running home after the consolidation. Both are coordinator decisions (timer install + IntelX home), not worker work. INT-023 stays open through Nov 27 for the final compilation; if the chain cannot run, the final filing will record seven days with zero verifiable passing days and the D4 recommendation will be NOT ENABLE on the current evidence.

## 9. What remains for Muse 9 on INT-023 (final leg)

- Days 5–7 (2026-11-25 → 2026-11-27): observe each 09:30 slot in the live archive + hub, record run id + outcome per day — **contingent on the block in §8 being cleared** (timer installed, IntelX running somewhere).
- After the 2026-11-27 run: complete the 7-day chain, state the final D4 recommendation with the evidence, file the final compilation.
- Open questions for Muse (coordinator): (1) timer install + IntelX home — the §8 block; (2) "1A"/"D4" definitions, still undefined in any readable source; (3) whether days with no observable 09:30 run count toward the 7-day chain, or the chain restarts.

— Muse 9, 2026-11-24 ~21:40 IST
