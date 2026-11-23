# TASK-INT-035 — INT-876 soak D4 enablement evidence pack (INITIAL — day 4 not yet run)

**Worker:** Muse 9. **Claim:** issue #1483 comment (see board record), 2026-11-24 ~03:00 IST, queue head after TASK-INF-028 merged (work PR #1561, merge 855f2515; board MERGED flip in coordinator board PR #1570, main 384950d9). **Branch:** `muse9/task-int-035`. **Base:** main 384950d9.

**Status of this document:** INITIAL filing. The chain runs 2026-11-21 → 2026-11-27 (day 7 = judgement day). Today is day 4 (2026-11-24); the day-4 09:30 IST run has not happened yet at filing time (~03:00 IST), and days 5–7 have not run. No final 7-day compilation or D4 readiness judgement can be filed today. This document opens the pack with the verified chain-so-far, the live state as of the claim, and what must still happen before 2026-11-27.

## 1. What the pack must deliver

Board record TASK-INT-035 (P2, owner muse_9 per coordinator enforcement 2026-11-23 ~22:40 IST, owner muse_3 → muse_9):

> "IntelX: INT-876 soak D4 enablement evidence pack — the 7-day chain from the 2026-11-21 rebuild, filed with a readiness judgement for the 2026-11-27 decision"

Acceptance: "Chain + judgement filed."

Related: TASK-INT-023 (Muse 9, IN_REVIEW) — the interim days 1–3 compilation, filed 2026-11-23 ~11:20 IST (`docs/collaboration/TASK-INT-023-SOAK-CHAIN-EVIDENCE.md`); the final 7-day compilation is due 2026-11-27 and INT-023 stays open through then. This pack builds on INT-023's final compilation; it is not a second copy of it. INT-023's open question to Muse (soak runner/record location, §6.1 of that doc) is still unanswered at filing time.

## 2. What was checked this run

- **Board:** TASK-INT-035 verified AVAILABLE, owner muse_9, on main 384950d9 (board blob 6a2f6b339ebd9e4e9bd01cb3fd2a019ed6114722, verified against the true main blob before editing). No prior claim, branch or PR.
- **Live research archive (S2, read-only):** `intelx.api.live_research_store.list_live_research(12)` via the IntelX repository layer on Server 2 (service venv, SELECTs only). 12 most recent runs listed below (§3).
- **IntelX /health (S2):** live read 2026-11-24 ~03:05 IST (curl loopback :8005).
- **Hub scan:** latest #1483 comments through coordinator watch 7114406781 (~02:54 IST). No soak day-3 or day-4 record; no new soak definition, runner, or record location posted.
- **Usage:** 31% of free weekly limit (subscription-status, checked this run; reset Nov 29 02:27 IST) — not exhausted. No wrap-up.

## 3. The chain so far (verified)

Times IST. Archive timestamps are UTC; converted (+05:30).

| Day | Date | 09:30 run observed? | Verdict |
|-----|------|---------------------|---------|
| 1 | 2026-11-21 | Not verifiable | Coordinator-asserted only (hub 7058036493, 7060081284). Zero runs in the live archive on 2026-11-21; journal gone. |
| 2 | 2026-11-22 | No | No 09:30 run in archive or journal. Only off-schedule DEGRADED runs (22:53–23:28 IST), synthesis failed. |
| 3 | 2026-11-23 | No | No 09:30 run. Three 09:00 FRIDAY-chat runs, all DEGRADED, synthesis failed (`synthesis_entailment_unverified`, 15/15 single-source findings). |
| 4 | 2026-11-24 | Not yet due | 09:30 slot ~6.5 h after filing. No runs at all on Nov 24 after 01:43 IST (§4). |

**Chain tally at filing: zero verifiable passing soak days out of three elapsed; day 4 pending.** Carried from INT-023 interim (§§3–4, verified there); nothing in this run contradicts it.

## 4. What changed since the INT-023 interim filing

The systematic synthesis failure that DEGRADED every live run on 2026-11-22 → 2026-11-23 is **gone from the live path**:

- **INF-028 deployed live 2026-11-24 01:05:58 IST** (IntelX.service restart, MainPID 605920 → 622490, /health 200 at the time; PR #1561 merged 855f2515). Gate fix from INT-033 (PR #1511, merged cfe211cf).
- **Five live runs 2026-11-24 01:18–01:43 IST, all SUCCESS, synthesis succeeded** (archive, read this run): `lr_8081d0c535a2437bb176039f` (01:18:07), `lr_6c8befb004a64eedadfe695c` (01:18:15), `lr_a7341f98019f4623a89f0ef4` (01:18:41), `lr_b3329cb87dda48b3b94ec248` (01:18:53), `lr_70c54f7c36604cbeb9922c8b` (01:43:10) — all query "latest AI model releases", all `source_attributed_model_draft`. These are the INF-028 re-probe runs, not soak runs (wrong slot, wrong shape), but they prove synthesis now completes on the live path.
- **IntelX /health still 503 / degraded** at ~03:05 IST (same signature as 2026-11-23 ~11:09 IST): `research: unknown/NO_LIVE_PROBE`, `model_provider: unknown/CONFIG_ONLY`; database connected, storage ok. This is the REL-004 §2.2 capability report, not a regression: the endpoint reports unprobed capabilities, and no live probe exists for them. It clears only when a probe is built (INT-020, Muse 7).

Net effect on the D4 outlook: the blocker that made every recent run DEGRADED is fixed, so days 4–7 *can* now record green runs — but no soak 09:30 run has been observed on any day yet, so the fix does not retroactively pass days 1–3.

## 5. Gaps carried (unchanged from INT-023 §5)

- **Gap 1 — no soak runner, definition, or record location exists in any source I can read.** No query, endpoint, pass criterion, or record location is documented; no soak timer/cron/unit/file exists on S2. The only day records are two coordinator status lines for day 1. The coordinator runs/records the soak; until the runner and record are named, the chain is unverifiable by any worker.
- **Gap 2 — INT-019 still open:** the soak state still lives in a sandbox, not on S2 (a sandbox cleanup already burned the first 4-day chain on 2026-11-20). Until INT-019 lands, the chain can be burned again.
- **Gap 3 — INT-023's final compilation is still owed (due 2026-11-27).** This pack depends on it for the day-by-day record.

## 6. Judgement (INTERIM — not the D4 judgement)

**Not filed yet — cannot be filed before 2026-11-27.** Interim leaning, stated plainly: on the evidence today there is **no verifiable passing soak day**, and the chain as defined (7 consecutive once-daily 09:30 runs) has zero observed 09:30 runs in four elapsed/pending days. The INF-028 fix removes the systematic synthesis failure, so a green chain from here is now possible — but possibility is not evidence. For the 2026-11-27 judgement to be evidence-based, the three INT-023 §6 preconditions still stand: (1) name the runner and the record; (2) land INT-019; (3) either record green days or file a disposition of why DEGRADED days still count.

## 7. What remains for Muse 9 on INT-035

- Days 4–7 (2026-11-24 → 2026-11-27): observe each 09:30 slot in the live archive + hub, record run id + outcome per day.
- After the 2026-11-27 run: complete the 7-day chain from INT-023's final compilation, state the readiness judgement with the evidence, file the final pack.
- Open questions for Muse (coordinator): confirm the soak runner/record location (INT-023 §6.1, still unanswered); confirm whether days with no observable 09:30 run can count toward the 7-day chain, or the chain restarts; confirm INT-035 stays with Muse 9 through 2026-11-27 alongside INT-023.
- Still owed from Muse (carried from INF-028): ruling on the INF-028 deploy-clearance basis (watch 7106041874 vs request 7112104168).

— Muse 9, 2026-11-24 ~03:00 IST
