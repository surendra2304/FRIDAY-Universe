# TASK-SEN-033 — Checkpoint 1: scoping (REPO-IMPLEMENT, Sentinel wave 3)

**Worker:** Muse 20 · **Date:** 2026-11-27 ~08:30 IST · **Base:** branch
`muse20/task-sen-033` @ `a3c3140e` (main post-#2042 merge); main now
`5fd32fdf`, board blob `f572e413e` (3,114,950 bytes, read first-hand)

## Claim

- Hub #2045 comment 7208156385 (~07:58 IST): TASK-SEN-033 claimed.
  Board at claim: AVAILABLE / muse_20, P2. Branch
  `muse20/task-sen-033` @ `a3c3140e` verified first-hand via ref API.
- **Stall repaired this run:** the claiming work-request run's record is
  `cancelled` with a null result summary (its 07:47:32 IST run was cut
  off when it cancelled its own schedule on claim). No checkpoint had
  been filed ~30 min after the claim and no run was active. This
  checkpoint files the read-only scope; no live step run.
- Board flip to CLAIMED rides in the coordinator's board PR (ruling
  7200564540 §3 — never touch WORK_BOARD.yaml in a work PR). Board on
  main `5fd32fdf` still reads SEN-033 AVAILABLE / muse_20 — expected,
  not a gap.

## Task (board acceptance, TASK-SEN-033)

REPO-IMPLEMENT (owner order 2026-11-24: implement ALL 102 scouted
repos): PentAGI (reference-only), Anthropic Cybersecurity Skills
(adapt) — target Sentinel. Source: PRODUCTION-VERIFICATION-PROGRAMME.md
§A/B/C via `IntelX/intelx/registries/scouted_repos.json` (102 entries).

- Adapt: the adapted component must run in the target agent's live
  production path, proven by one real end-to-end use filed as evidence
  incl. a failure case.
- Reference-only: a paper judgement is NOT a result — prove with live
  evidence whether it works in the agent or not (live trial or
  guardrail proof of absence from every production path), file that
  evidence per repo.
- Approval path: one low-risk auto-approve + one high-risk Telegram
  prompt, each exactly once, on the live Sentinel service, per item
  where the item touches the approval path; otherwise the item's own
  live security check against the real surface.

## Item 1 — PentAGI (vxcontrol/pentagi) — reference-only

Registry entry verified first-hand (`scouted_repos.json`): fit
`reference-only`; MIT; Go + TypeScript/React; self-hosted autonomous
multi-agent penetration-testing platform (researcher/planner/executor/
adviser/memorist running 20+ real security tools in Docker sandboxes,
PostgreSQL/pgvector + optional knowledge graph). Rationale: far too
heavy for the fleet (Docker sandboxes + Postgres + Neo4j on ~1GB VMs)
and offensive in remit; Sentinel is defensive. Mine the
specialised-agent role design only.

Upstream re-verified this run (GitHub API, public repo): alive, not
archived; default branch `main`; latest release **v2.2.0**
(2026-10-05); last push 2026-11-13.

What exists on main (verified first-hand):

- `Sentinel/docs/SECURITY_REFERENCE_IG.md` §4 — PentAGI role-design
  notes: role → defensive-analogue mapping (Researcher → recon +
  threat-feed adapters; Planner → baseline/delta evaluation; Executor
  → allowlist-bound read-only probes of IG-SEN-01; Adviser/reflector
  → AlertEngine triage + SEN-006 approval dispatch; Memorist →
  baseline store + this doc series). Explicit non-adoptions: no
  autonomous offensive execution; no tool-sandbox fleet (hardware);
  no targets outside the owner's assets.

Owed for this item: the **live evidence** the acceptance demands —
guardrail proof of absence from every production path (prove no
PentAGI-style offensive execution exists anywhere in Sentinel's live
production path). No new code expected; the deliverable is the
evidence doc + the guardrail check itself, run against the live S1
Sentinel service.

## Item 2 — Anthropic Cybersecurity Skills (mukul975/Anthropic-Cybersecurity-Skills) — adapt

Registry entry verified first-hand: fit `adapt`; Apache-2.0; 818
structured skills across 34 security domains (agentskills.io format,
mapped to MITRE ATT&CK v19.1, NIST CSF 2.0, ATLAS, D3FEND, NIST AI
RMF, F3). Independent community project by Mahipal Jangra (mukul975)
— explicitly NOT affiliated with Anthropic PBC. Includes
offensive/dual-use skills flagged "authorized use only" upstream.
Rationale: cherry-pick the defensive skills (cloud/fleet hardening,
SOC playbooks, threat hunting, vulnerability management, AI-security /
prompt-injection checks); do NOT import wholesale; each adopted
skill's script needs review before it runs near production.

Upstream re-verified this run (GitHub API, public repo): alive, not
archived; default branch `main`; latest release **v1.3.0**
(2026-06-22); last push 2026-08-31. (Upstream skill count to
re-confirm at work time against the registry's 818.)

What exists on main (verified first-hand) — the adapt is largely
already implemented under TASK-IG2-SEN-01:

- `Sentinel/app/services/defensive_skills.py` (277 lines):
  fail-closed defensive-only skill-pack loader. Refuses (raises
  `DefensiveSkillPolicyError`) any skill whose tier is not exactly
  `defensive`, whose name is on the exclusion list, or whose domain is
  an excluded offensive category.
- `Sentinel/skills/defensive/` — **10 defensive skills** (manifest.json
  verified): hardening-linux-fleet-hosts, detecting-ssh-brute-force,
  triaging-soc-alerts, containing-active-incident,
  threat-hunting-fleet-logs, triaging-vulnerabilities,
  tls-certificate-hygiene, defending-llm-prompt-injection,
  verifying-backup-integrity, reviewing-iam-least-privilege; plus
  `NOTICE.md` (provenance, Apache-2.0, affiliation caveat, exclusion
  policy: no upstream script is executed by the pack).
- `tests/test_ig2_sen_defensive_skills.py` (133 lines).

Gaps found first-hand (the work of this task):

1. **Loader not wired into Sentinel's runtime.** GitHub code search
   for `defensive_skills` returns 5 hits only: the loader itself,
   NOTICE.md, TASK-SEN-031-CHECKPOINT-1.md, the INT-044 tracker, and
   the test. No import or call in `Sentinel/app/` or
   `Sentinel/sentinel/` runtime code. Wiring the loader into the live
   production path (or a recorded decision not to wire it, with the
   reason) is the main repo delta for the adapt leg.
2. **Defensive-skills test is not collected by CI** (REL-068 defect
   class). `tests/test_ig2_sen_defensive_skills.py` appears in no
   pytest list in `.github/workflows/friday-universe-ci.yml` (the
   Sentinel tier-1 list names 5 files; this is not one) and no
   workflow references it (code search total 2, both docs). Fix in the
   work PR: add it to a collected list (note: it lives at repo-root
   `tests/`, while the Sentinel tier-1 job runs with working-directory
   `Sentinel` — the invocation needs the root-relative path).
3. **Live proof owed:** one real end-to-end use of the adapted skills
   in Sentinel's live production path incl. a failure case, on the
   live S1 Sentinel service; plus the approval-path exercise (one
   low-risk auto-approve + one high-risk Telegram prompt, each once).
   Approval code exists on main (`Sentinel/sentinel/gatekeeper/
   approval_policy.py`, `approval_dispatcher.py`,
   `Sentinel/sentinel/core/auth/approvals.py`, alembic
   `0004_approval_records.py`, dashboard Approvals page).
4. **Overlap check owed:** TASK-SEN-031 (Muse 12, MERGED via PR
   #1847) production-verified corpus items incl. IG2-SEN-01
   (defensive skills). Its checkpoint 1 scoped the same live check
   ("run the defensive-skills service in the live agent on a real
   task") but its live legs were NOT run at checkpoint-1 time (stop
   order). Whether PR #1847 already contains the live approval-path
   evidence is NOT verified in this run — check PR #1847's contents
   before repeating that leg; do not run the approval exercise twice.

## Live-leg plan (checkpoint 2, not run here)

Route named in the claim: S1 Sentinel service via bridge run_shell.
Planned legs, in order: (a) read-only probe of the live S1 Sentinel
service state (running? which version?); (b) defensive-skills
end-to-end use on a real task + failure case, once wired; (c)
approval-path exercise (1× low-risk auto-approve + 1× high-risk
Telegram prompt); (d) PentAGI guardrail proof of absence from every
production path. No live step in checkpoint 1; no bridge call made.

## Grant position (reported plainly, not resolved here)

Coordinator correction 7197725825, burn order 7200414167 and ruling
7200564540 §1 all state the owner run_shell grant stands (owner's own
tap, main chat, 2026-11-26 18:25:56 IST) and live verification is
pre-approved fleet-wide. My first-hand permissions record (21:28 IST
Nov 26) shows no run_shell grant on record for approval 7113152293;
the correction explains main-chat approvals do not surface in
permissions.history — an explanation I have not verified first-hand.
No live leg is run on the strength of the coordinator's ruling alone
in this checkpoint; the live legs in checkpoint 2 will proceed under
the standing ruling, and any grant evidence I can produce first-hand
will be filed with them. If Muse rules otherwise, I will hold them.

## Queue / usage

- Queue: SEN-033 (head, claimed) → INT-056 (AVAILABLE / owner null on
  main `5fd32fdf` — was CLAIMED / muse_20 at 03:28 IST; released or
  re-slotted by a board PR since) → VYR-067 (AVAILABLE / muse_20,
  staged).
- Usage: 25% of free weekly limit (verified this run via
  subscription-status; was 24% at 07:28 IST). Reset Dec 1, 11:00 AM
  IST. Additional tokens 0% used. Free usage remains; no wrap-up.

## Five states

- implemented: PARTIAL — adapt code + skill pack on main via IG2-SEN-01;
  wiring + live evidence owed
- tested: NO — defensive-skills test exists but is uncollected by CI;
  no live proof yet
- merged: NO
- deployed: NO
- production-verified: NO
