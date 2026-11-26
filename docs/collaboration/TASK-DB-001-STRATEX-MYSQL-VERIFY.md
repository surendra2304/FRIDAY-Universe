# TASK-DB-001 — Stratex MySQL production-usage verification — Checkpoint 1 (repo-side scoping)

- Task: TASK-DB-001 (P1). Claim: hub #1483 comment 7146570115, Muse 6, 2026-11-25 ~04:08 IST, per coordinator ruling (watch060 7146031769 + escalation 7145448295).
- Branch: muse6/task-db-001-stratex-mysql-verify, rebased to main 07c526b (was 2c51d17; zero unique commits, nothing lost).
- Status: CHECKPOINT 1 — repo-side scoping only. Live leg NOT attempted: gated on a coordinator-cleared read-only MySQL route; owner stop order still in force. No bridge/server access from this VM.

## Decided arrangement (owner orders 2026-11-25 ~02:56 and ~02:59 IST)

Memora -> Autonomous DB #1; IntelX + Futuris research -> Autonomous DB #2, named "IntelX DB" (TASK-DB-002); Stratex research -> MySQL HeatWave "FRIDAY Stratex Research" (this task verifies production usage; do NOT migrate); VyralX -> FILES ONLY, no database; Cortex -> Redis + files; FRIDAY/Sentinel/Forge -> files; Inference -> stateless.

## Repo-side findings (main 07c526b, searched 2026-11-25 ~05:15 IST)

1. No MySQL writer code exists in the repo. Searched `stratex_research`, `10.0.0.182`, and case-insensitive `mysql` across the whole tree and `Stratex/` specifically: zero connection strings, zero driver usage, zero host references in Stratex code. The only Stratex hit is `Stratex/self_experiments/counter.py`, which asserts RD-025 trials 3,904-3,979 are "independently proven by the MySQL store's RD-025 rows" — a claim with no code behind it in the repo. (Other `mysql` hits are security-scanner regexes, Sentinel port tables, and a test fixture string — unrelated.) No credentials anywhere in the repo; none printed here.
2. The live writer candidate is the Stratex daemon on Stratex-Server (server 4, AWS 13.211.78.20): `Stratex-Daemon.service` verified UP (Main PID 13273, active since 2026-11-24 06:57:34 UTC) in the TASK-STR-049 probe ~04:00 IST 2026-11-25. The live trial counter is 3991 (`/opt/friday_universe/Stratex/self_experiments_data/trial_counter.json`, updated 2026-11-24T08:27:43Z). Research records on that box are files (`experiments.jsonl`, `admissions.json`, `lessons.jsonl`). Whether the daemon also writes to MySQL HeatWave cannot be determined from the repo — that is exactly what the live leg must prove.
3. The 3 most recent research runs to match end-to-end (acceptance item 2) are the loop trials 3989 (PROVEN), 3990 (FORWARD_TEST), 3991 (FORWARD_TEST), per the STR-049 record. Matching them needs the live MySQL read.
4. Stale reference flagged (not fixed here — out of scope): `docs/collaboration/WORKER_PROMPT.md` still says "Autonomous Database #2 -> VyralX — her data store". The owner decision ~02:59 IST moved VyralX to files-only and made ADB #2 the "IntelX DB". Belongs to TASK-DB-002 (rename verification) / TASK-DB-003 (fleet audit).

## Live leg — gated, not attempted

- Needs: (a) coordinator-cleared read-only route to MySQL HeatWave `FRIDAY Stratex Research` (10.0.0.182:3306, database `stratex_research`) from an authorised host; (b) bridge/server access from this VM (none exists in this run). Credentials from the fleet record/env only, never printed.
- Then: list tables, row counts, newest-row timestamps; match trials 3989-3991 against the file records; show the production writer's live connection settings (host + database name only).
- Any gap found is fixed inside this task per the acceptance (fix + one real research write + new row with timestamp). Not reached yet.

## Board flips in this PR

- TASK-DB-001 AVAILABLE -> CLAIMED (owner muse_6).
- TASK-EARN-008 IN_REVIEW -> MERGED (work PR #1625 merged 2026-11-24 12:43 IST, head d3dc1ee0, CI 9/9 green).
- TASK-VOI-031 CLAIMED -> AVAILABLE (released back to the pool 2026-11-24 22:08 IST).
- TASK-STR-075 untouched: released to M15 per watch060; its flip rides in M15's PR when M15 claims.

## Next action

Await coordinator clearance for the read-only MySQL route; then run the live leg. No live moves until then (owner stop order in force).
