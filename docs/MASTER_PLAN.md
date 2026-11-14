# FRIDAY Universe — Master Plan (v3)

Owner: Surendra Varma Jalli. This revision: 2026-11-14, Muse (lead coordinator), under the owner's direction of 2026-11-14 to revise the plan completely after the merge-all batch. v2 (2026-11-10, ZAI, decision D-022) and v1 are preserved in git history. The dated work chronicle that v2 accumulated at the end of this file (TASK-WF-004 → TASK-WF-014 entries) has been moved verbatim to docs/collaboration/ACTIVITY_LOG.md, where execution history belongs (§2: status does not live here).

## 1. North Star — what success means

> "I want my Friday to talk to me like a friend and do all the tasks I say — like the Jarvis for Iron Man." — owner, 2026-11-10

FRIDAY is the single voice of the system. Surendra talks to FRIDAY in plain language; FRIDAY understands the request, picks the right specialist agent — Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, VyralX — dispatches the work, tracks it to completion, and reports back like a friend: warm, honest, with evidence. Ten agents, one orchestrator, one owner.

This plan is value-ordered: every milestone ends with something Surendra can personally see and do from his browser or phone — not with paperwork.

## 2. How this plan works (rules kept from v1/v2 that were right)

- Statuses: NOT_STARTED | IN_PROGRESS | BLOCKED | IN_REVIEW | VERIFIED | DONE.
  - VERIFIED needs evidence (command output, log line, live check, test run cited in handoff.md).
  - DONE needs implementation, passing tests, verification and all acceptance criteria.
  - A box is never ticked because code was written.
- Who works on what: the claim protocol lives in docs/collaboration/ (TEAM_ROSTER.yaml, WORK_BOARD.yaml, FILE_OWNERSHIP.yaml, ACTIVITY_LOG.md, DECISIONS.md) with visible claims/releases/handoffs on GitHub issue #35. TASK-COLLAB-001 (the collaboration centre itself) is MERGED and maintained there.
- The work board mirrors this plan; it never silently rewrites acceptance criteria.
- Coordination (owner decision, 2026-11-14): the owner appointed Muse lead coordinator of the team — owning the merge queue, the verification standard, and the integrity of this plan. Collaborators keep equal engineering standing: work is still claimed on the board, built on isolated branches, and independently reviewed, and reviewed work is never silently overridden. The owner retains final approval for architectural direction, merges, deploys, production restarts and live trading. (This supersedes v2's "no AI is the permanent leader" line; the owner's approval role is unchanged.)
- Before any task: read docs/handoff.md and docs/ARCHITECTURE_AS_BUILT.md, then refresh GitHub state — a prior snapshot is not current truth.
- Status does NOT live here. This file holds the what/why/order and acceptance criteria; current status and evidence live in WORK_BOARD.yaml and handoff.md. (v1 collapsed under status essays written into the plan — do not repeat that. v2 repeated it anyway: its dated chronicle is removed by this revision.)
- **Re-verification rule (new in v3):** any VERIFIED or DONE claim older than 7 days must be re-probed before it is relied on. A tick records the day it was earned, not a permanent state. This revision exists because v2's 2026-11-10 snapshot silently aged while its checkboxes stayed ticked — §4 below re-states every milestone item under this rule.

## 3. Verified reality snapshot — 2026-11-14 (Muse, live probes)

Probed 2026-11-14 07:06–07:07 UTC (two concordant probe sets, ~30 s apart; second set cited). Git/code checks against main 573da9c on the same morning. This snapshot cites only evidence gathered for this revision; anything older is labelled with its own date.

| Claim | Evidence (live, 2026-11-14) |
|---|---|
| All ten agents answer on the public gateway | `/friday`, `/inference`, `/memora`, `/stratex`, `/futuris`, `/intelx`, `/forge`, `/cortex`, `/sentinel`, `/vyralx` `/health` all HTTP 200 at friday-universe.duckdns.org, latencies 0.82–1.38 s (07:07:04Z set) |
| …but health is liveness only | Every agent's `/health` self-reports `evidence_class: process_liveness`. A 200 proves the process answers, not that the agent can do its job — see the Stratex row |
| FRIDAY chat completes a real request end-to-end | POST `/friday/api/chat` (07:07:24Z) → HTTP 200 in 3.10 s; deterministic fleet-status fast path (`fast_path=true`, `probe_success=true`, `task_state=COMPLETED`) replied "9/9 specialist agents up" and scoped itself honestly ("peer endpoint reachability, not task-level verification"). This fast path returns no `routed_capability` field; a full LLM-routed task was not probed in this snapshot |
| Stratex engine is OFFLINE | `/stratex/health`: `engine: "offline"`, `engine_healthy: false`, `STALE_STRATEGY_EVALUATION: last evaluation 1039907s ago` (≈12.0 days), `daemon_balance: null`, `open_positions: null` → TASK-REL-003 |
| Forge still has no task-execute endpoint | Code check on main 573da9c: no `/v1/task/execute` route exists in Forge (Sentinel has one, `Sentinel/sentinel/apps/api/main.py`). Backlog TASK-API-001 remains open |
| Repository: zero open PRs, batch fully merged | Bridge PR list, 2026-11-14: **0 open PRs**. The owner's merge-all batch merged 16 PRs, including the rebased replacements (#92/#93/#96/#97) and dependabot numpy 1.26→2.2.6 (PR #51, merged last). Main = 573da9c |
| The batch is deployed, not just merged | Fleet CD run 43569163501 on 573da9c: **success** (2026-11-14T07:02:09Z). Secret Scanning and Monorepo CI runs on the same SHA also succeeded |
| CI is red on main: voice-regressions job failing | FRIDAY Universe CI/CD run 43569163089 on 573da9c: **failure**; the failing component is the `voice-regressions` job (`.github/workflows/friday-universe-ci.yml` — ruff on voice surfaces + pytest over 14 named voice/LiveKit/Gemini/CLI test files), first seen failing on push 37db125. Known issue, root cause not yet established → TASK-REL-002 |
| Merged waves' tests run in no workflow | Grep of `.github/workflows` (2026-11-14): no workflow names `Forge/tests/unit/test_task_forge_002_*.py` (PR #91), `Memora/tests/test_viking_context_durability.py` (PR #90) or `FRIDAY/tests/test_intent_classifier_tier.py` (PR #92). Every CI job runs an explicit file list, so unlisted tests run nowhere → TASK-REL-001 |
| FRIDAY is at its memory ceiling | FRIDAY.service at 199.9M of its 200M limit (verified earlier on 2026-11-14, ~01:20–01:55 IST session probes; **not** re-probed in this snapshot) → §5 budget |

The owner can try FRIDAY right now: open **https://friday-universe.duckdns.org/friday/** in a browser and talk to it. Chatting like a friend works today (probed above); the fleet's specialist depth is what M5 now proves, workflow by workflow.

## 4. Milestones (value order)

*Re-statement key (applied 2026-11-14 under the §2 re-verification rule): **[x]** = merge in git history AND function re-verified in the §3 snapshot. **[~] STALE-UNVERIFIED** = merged, but its function was not re-verified in this snapshot; the original evidence date is kept in the note. **[ ]** = still open. Most v2 ticks were merge-day claims from 2026-11-10; their re-verification is now scheduled work (M5), not an assumption.*

### M1 — FIRST REAL TASK (the dream demo)
The owner says one natural-language task; FRIDAY classifies it, dispatches to the right agent, tracks it with the unified task records, the agent does real work, and FRIDAY reports the result back like a friend.
- [~] TASK-ORCH-001 — Replace keyword-substring routing (live misroute proven 2026-11-10: "research" → VISION_MODEL) with explicit intent classification and a tested routing table. STALE-UNVERIFIED 2026-11-14: merged 2026-11-10, and its successor LLM intent mid-tier merged 2026-11-14 (PR #92, TASK-INTENT-001); deterministic fast-path routing confirmed live in the §3 chat probe, but the routing table itself was not re-probed end-to-end in this snapshot.
- [~] TASK-ORCH-002 — Wire ONE shared TaskRecordStore into the router and dispatch bus, correlate router task ids with bus dispatch ids, and add the agent-side completion callback for 202-accepted work. STALE-UNVERIFIED 2026-11-14: substrate merged (PR #44, git history); router↔bus record correlation not re-probed live.
- [~] TASK-ORCH-004 — Fix the action limit so a single real task completes within limits. STALE-UNVERIFIED 2026-11-14: merged 2026-11-10; the §3 chat probe completed in 3.1 s, well within budget, but no long task was run against the limit in this snapshot.
- [~] TASK-WF-001 — Acceptance gate for M1: one end-to-end task across at least three agents with a recorded trace. STALE-UNVERIFIED / acceptance still owed: the 2026-11-10 trace itself recorded 3 completed / 1 failed (Futuris 501), and the owner's browser closure never happened. A fresh multi-agent trace is an input to the M5 exit.
Owner-visible exit: "Friday, research X and give me the highlights" returns real findings produced by IntelX, tracked and reported back.

### M2 — DAILY DRIVER
- [~] TASK-MEM-003 — FRIDAY uses memory proactively across sessions. STALE-UNVERIFIED 2026-11-14: merged 2026-11-10; Memora answers /health (§3) but proactive cross-session recall was not re-probed. The Memora durability wave merged 2026-11-14 (PR #90) strengthens this item; its tests are wired under TASK-REL-001.
- [x] TASK-FOR-001 — Security review of the Forge code-execution sandbox. (Re-verified 2026-11-14 as an artifact: `docs/security/FORGE_SANDBOX_REVIEW_2026-11-10.md` present on main, APPROVED for M2 with no critical/high findings; the review's findings were not re-audited in this snapshot.)
- [~] TASK-FOR-002 — Forge executes one real code task requested through FRIDAY chat. STALE-UNVERIFIED, with contradiction noted: merged 2026-11-10, but Forge still exposes no `/v1/task/execute` route (§3 code check), and the WF-007→WF-011 record (ACTIVITY_LOG) shows repeated build-acceptance failures before one narrow success. This workflow must now prove itself under M5 (3 consecutive live runs).
- [~] TASK-STR-002 — Stratex answers portfolio and position questions via FRIDAY on Binance demo (live trading stays blocked by the merged fail-closed guard; owner decision D-015). STALE-UNVERIFIED, with contradiction noted: the read-only portfolio tool is merged, but the Stratex engine is OFFLINE at this snapshot (§3) with `daemon_balance: null`; the portfolio-answer path was not re-probed. Engine diagnosis is TASK-REL-003.
- [~] TASK-INT-002 — IntelX research briefs retrievable through FRIDAY chat. STALE-UNVERIFIED 2026-11-14: merged 2026-11-10; the research-brief path was not re-probed end-to-end in this snapshot. The grounded-research changes merged 2026-11-14 under owner override (PR #78) carry a behaviour follow-up in §6.
- [x] TASK-API-002 — Standard `/health` and agent-status surface so "Friday, how's the fleet?" is answered truthfully. (Re-verified 2026-11-14: §3 chat probe — the fast path answered "9/9 specialist agents up" with `probe_success=true`, `task_state=COMPLETED`, and an honest reachability-only scope note.)
Owner-visible exit: Surendra runs at least three different real task types through FRIDAY in one week and reports the experience.

### M3 — VOICE JARVIS
- [ ] TASK-VOI-001 — FRIDAY-Voice (LiveKit worker) live test with the owner: speak, be understood, get spoken answers (MemoryMax already set, TASK-INF-002). OPEN, unchanged: engineering side READY since 2026-11-10 (9-check preflight + 6-phrase owner test kit, docs/voice/VOICE_TEST_KIT_2026-11-10.md); awaiting the owner's live session (§9).
- [~] TASK-VOI-002 — Proactive morning brief: spoken fleet status, portfolio summary and overnight events. STALE-UNVERIFIED 2026-11-14: merged 2026-11-10; the brief was not re-probed in this snapshot, and the voice lane's CI job is currently failing on main (TASK-REL-002).
Owner-visible exit: Surendra talks to FRIDAY by voice and receives a daily brief unprompted.

### M4 — HARDENING AND AUTONOMY
- [x] TASK-SEC-005 — Close the public control surface: require a real owner credential on `/api/control/session`. RESOLVED 2026-11-10 (D-023: remote mint requires the control key; origin gate retained; fail-closed 503; live-verified 2026-11-10 — 401 no key / 403 forged origin / 401 wrong key). Not re-probed in this snapshot; under the §2 rule its live verification falls due for renewal by 2026-11-17.
- TASK-SEC-003 — Bridge authentication activation (middleware merged in PR #24). **Disposition (owner decision, 2026-11-14): accepted/deferred by owner — not tracked as a blocker.** The merged auth code stays ready if the owner revisits.
- [~] TASK-VAL-001 — Full fleet validation on live servers with per-agent evidence. STALE-UNVERIFIED 2026-11-14: performed 2026-11-10; §3 of this plan re-probes the public-gateway half as of 2026-11-14, but the server-side systemctl half was not re-run.
- [x] TASK-VAL-002 — Security review of public ingress and bridge. (Deliverable re-verified present on main 2026-11-14: `docs/security/INGRESS_BRIDGE_REVIEW_2026-11-10.md`; its critical finding B-1 is dispositioned under TASK-SEC-003 above.)
- [~] TASK-OBS-001 — Crash-loop and health alerting. STALE-UNVERIFIED 2026-11-14: fleet health watcher + deploy-job health gate + runbook merged 2026-11-10; server-timer enablement and alert delivery not re-verified.
- [~] TASK-OBS-002 — Rollback procedure for a bad deploy. STALE-UNVERIFIED 2026-11-14: ancestor-guarded rollback script + Fleet Rollback workflow + guard tests merged; no rollback drill re-run in this snapshot.
- [~] TASK-INF-003 — Backup and restore drill: Oracle DBs and service configs. STALE-UNVERIFIED 2026-11-14: backup/restore tooling + weekly Fleet Backup workflow + runbook merged; no restore-drill evidence in this snapshot.
- [~] TASK-DATA-003 — Persistence and recovery test for Memora and Stratex ledgers. STALE-UNVERIFIED 2026-11-14: real-process-death recovery tests passed 4/4 at the ledger level on 2026-11-10; the production drill was not re-verified. (Memora durability strengthened by PR #90, merged 2026-11-14.)
- [~] TASK-ORCH-003 — Verify the autonomous controller and fleet supervision before any autonomy claim. STALE-UNVERIFIED 2026-11-14: audit doc + 8 guard tests merged 2026-11-10 (supervision verified+honest, autonomy OFF by default); supervision state not re-probed.

### M5 — DAILY-DRIVER RELIABILITY (new in v3)
The gap between v2's paper state and the owner's experience: individual pieces merged, but the five core workflows have never been proven to work end-to-end, repeatedly, on production. M5 closes that gap. A workflow counts as proven only after **3 consecutive successful live runs on production, each recorded with its trace** (request, routing, agent evidence, result) in ACTIVITY_LOG/handoff records. A silent failure — a wrong answer presented as success, a dropped result, a fabricated status — resets that workflow's count.
The five workflows: (1) chat conversation with FRIDAY, (2) research with sources via IntelX, (3) memory recall across sessions via Memora, (4) a Forge code build from a FRIDAY request, (5) a voice session.
- [ ] TASK-REL-001 — Wire all merged waves' tests into CI. The 2026-11-14 waves shipped tests no workflow runs (§3): `Forge/tests/unit/test_task_forge_002_*.py` (PR #91), `Memora/tests/test_viking_context_durability.py` (PR #90), `FRIDAY/tests/test_intent_classifier_tier.py` (PR #92). Add them to the appropriate jobs' explicit lists (or an equivalent discovery mechanism) and show them executing green in CI.
- [ ] TASK-REL-002 — Root-cause and fix the failing `voice-regressions` CI job (failing on main since push 37db125; §3). Fix the root cause; never weaken tests to pass (§8).
- [ ] TASK-REL-003 — Diagnose and repair the Stratex engine-offline state (strategy evaluation stale ≈12 days at the §3 snapshot). Diagnosis first, recorded before any change; no trading-behaviour changes in this task, and the demo-only fail-closed guard (D-015) stays untouched.
- [ ] TASK-REL-004 — Health-endpoint honesty (design task): agents report capability state, not just process liveness — e.g. Stratex already exposes `engine`/`engine_healthy`; define the fleet-wide contract so a degraded agent cannot present as simply "ok", and so FRIDAY's fleet-status answer can cite capability, not reachability.
Owner-visible exit: Surendra uses FRIDAY daily for a week across all five workflows without a silent failure.

### Dependencies
- M1 before M2 — a daily driver needs one working task first.
- TASK-ORCH-001 + TASK-ORCH-002 + TASK-ORCH-004 before TASK-WF-001 (M1 gate).
- TASK-FOR-001 before TASK-FOR-002.
- TASK-SEC-005 owner decision before any third party is invited onto the public URL. (Decision taken: D-023.)
- M5: TASK-REL-001 before any "tests green" claim for the 2026-11-14 waves; TASK-REL-002 before voice-lane changes can be called verified; TASK-REL-003 diagnosis before any Stratex engine change; the M5 exit requires the 3-run evidence for all five workflows.

## 5. Resource budget (new in v3)

The fleet is two small Oracle VMs — not the larger hosts earlier planning assumed (production record verified 2026-10-26 in repo AGENTS.md; §3 of this plan):

| Resource | Reality |
|---|---|
| Server 1 (10.0.0.121) | ~956 MB RAM total, hosting 7 agents: FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge |
| Server 2 (10.0.0.120) | ~956 MB RAM total, hosting 3 agents (Sentinel, Cortex, VyralX) plus the engineering bridge |
| FRIDAY.service | Memory limit 200M, observed at 199.9M — at its ceiling (2026-11-14, earlier session; §3) |
| Public gateway latency | ~0.8–1.4 s per /health probe (§3); FRIDAY's own loopback peer probes report ~190 ms — most of the public latency is ingress, not the agents |

Rules:
- No new always-on service, worker or daemon without a stated memory figure and the owner's approval.
- Prefer in-process designs; persistence stays on Oracle Autonomous Database per the repo AGENTS.md rule (no new local SQLite/PostgreSQL backends).
- Any change that raises FRIDAY's resident memory must name what it displaces; FRIDAY has no headroom.
- Capacity work (e.g. §9's Redis/Qdrant question) is decided against this table, not against assumed hardware.

## 6. Standing backlog (valid tasks; not milestone-blocking)

| Task | One line |
|---|---|
| TASK-CI-003 | `run_workspace_test` has no pytest in the Server 2 venv |
| TASK-API-001 | `/v1/task/execute` on Forge (Sentinel merged in PR #29; Forge route still absent — code-checked 2026-11-14, §3) |
| TASK-API-003 | Authentication matrix test: each agent accepts only its configured keys |
| TASK-INF-LLM-001 | Inference provider key-pool audit (names and counts only) |
| TASK-INF-LLM-002 | Provider failover drill under simulated outage |
| TASK-OPS-001 | OCI secrets present in the repo (names verified; values unverified) |
| TASK-OPS-003 | Oracle sniper allocation loop end-to-end |
| TASK-FUT-001 | Futuris forecasting and DSN audit |
| TASK-CTX-001 | Cortex CRM/website-operations audit (route-level auth fix was PR #26) |
| TASK-VYR-001 | VyralX daemon/autopilot audit and wall-clock budget |
| TASK-REL-001..004 | M5 reliability tasks — defined in §4 (cross-reference; they live in M5, not here) |
| — (PR #78 follow-up) | Research synthesis-failure path must preserve the extractive excerpts the pre-#78 deployed path returned, instead of discarding them when synthesis fails. Behaviour-regression risk accepted onto main under the owner's merge-all override (2026-11-14); fix tracked here. The separable topic-overlap negative-control fix from the same PR is clean |
| — (PR #73 follow-up) | ZAI to state the venue/account mode (demo/testnet vs real-money) for the Stratex winner-allowlist activation record (`docs/collaboration/TASK-STRATEX-PROFIT-3.md`), and reconcile the PF selection threshold stated as 1.19 in the task doc vs 1.16 in the activity log/work board. Records task — docs only, no trading change |

*Removed since v2:* TASK-CI-004 (bridge `/**` gitignore narrowing — implemented and closed by commit 57c5868, 2026-11-11) and TASK-OPS-002 (verified 2026-11-10, run 42761923442; its continuation is TASK-OPS-003).

## 7. Security and production requirements (unchanged from v2)

- No secrets in git, comments, logs or documents. Names only.
- Merges to main deploy to both servers. Review deployment impact in the PR.
- No production restart without owner authorization for that restart.
- Stratex trades on Binance demo only; live trading requires the owner's written authorization and the merged ALLOW_LIVE_TRADING guard.

## 8. Testing and verification requirements (unchanged from v2)

- Every code task cites a passing test run in handoff.md.
- CI green before merge. Fix root causes; never weaken tests to pass.
- Live checks cite public health endpoints and systemctl status with timestamps.

## 9. Owner decisions needed

Open:
1. **A voice-test slot for M3** — TASK-VOI-001's kit has been ready since 2026-11-10 (docs/voice/VOICE_TEST_KIT_2026-11-10.md); M3 cannot close without the owner's 5-minute live session.
2. **Whether Server 1 ever gets Redis/Qdrant** (affects TASK-DATA-003/TASK-OBS-001). No decision is recorded in docs/collaboration/DECISIONS.md through D-028; to be decided against the §5 resource budget.

Closed since v2 (dispositions, not re-asks):
- TASK-SEC-005 — RESOLVED 2026-11-10 (D-023: secure the control-session mint; implemented and live-verified).
- Bridge authentication activation (TASK-SEC-003 / D-024 proposal) — owner decision 2026-11-14: accepted/deferred by owner; not tracked as a blocker (see §4, M4).
- DuckDNS token — secured with self-heal armed, recorded on main 2026-11-14 (collaboration record, commits ee902e2/c378f2f lineage).
