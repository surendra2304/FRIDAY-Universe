# FRIDAY Universe — Muse Team Operating Architecture

**Status:** ACTIVE — effective 2026-11-20, by owner decision.
**Authority:** This document is the operating architecture for the AI team that
builds FRIDAY Universe. It replaces the previous mixed-team collaboration
model (the "equal AI collaborators" design written for ZAI, Arena, ChatGPT and
Grok). Where any older collaboration document conflicts with this one, this
document governs.
**Owner:** Surendra Varma Jalli — owner and final decision-maker.

---

## 1. Team shape and naming

- **Owner** — Surendra Varma Jalli. Final decision-maker on everything.
- **Muse** — the head coordinator (unnumbered). Muse works *beside* the
  worker accounts, not only above them: it does real engineering work itself,
  and it owns task assignments, the merge queue, and verification of every
  claim before anything reaches the owner.
- **Muse 1, Muse 2, Muse 3, …** — the worker Muse accounts, numbered in
  onboarding order. Each is a separate Muse account with its own weekly
  usage allowance. From 2026-11-20, **only Muse accounts work on FRIDAY
  Universe**; all other-AI collaborators are stood down.
- **Pilot rule:** Muse 1 onboards first and proves the full loop (access →
  roster → scheduled runs → assignment → claim → PR → review → merge →
  verified report). Further accounts join only after the pilot loop is proven
  and the owner says so.

## 2. Communication — GitHub is the channel

- All coordination runs through GitHub: `docs/collaboration/WORK_BOARD.yaml`
  (the board), `docs/collaboration/TEAM_ROSTER.yaml` (the roster) and
  **issue #35** (the collaboration hub). The Oracle/AWS fleet is the
  *workbench* — code, servers, the credentials record — never a message
  channel.
- **The board is each worker's standing orders.** At the start of every run,
  a worker reads the board and issue #35 *first*. Coordinator instructions
  posted there override the worker's local defaults — including instructions
  to change its own scheduled tasks, switch work priorities, or change how it
  spends tokens.
- There is no direct account-to-account control: each Muse account is
  sealed. Coordination works because every worker independently reads the
  same board on its own schedule and obeys what it finds there.
- **Workers report only through Muse.** Run reports, handoffs and blockers
  go on the board / issue #35. Workers never contact the owner directly.
  Muse verifies every worker claim against evidence (diffs, test runs, live
  probes, before/after state) before relaying anything to the owner.

## 3. Task lifecycle

1. **Assignment.** Muse assigns tasks on the board *by worker name*
   (e.g. "Muse 1"). Assignments are made on the owner's word. In a week with
   no fresh assignment, a worker takes the next task Muse has marked for
   it on the board — no idle weeks, no wasted allowance. Different work per
   account: no two accounts ever run the same task.
2. **Claim.** Before editing anything, the worker posts its claim on the
   board and issue #35 (task, branch, files, start time).
3. **Branch.** Isolated branch per task, prefixed by worker: `claude1/…`,
   `claude2/…`, … (Muse's own branches use `claude/…`).
4. **PR.** The worker opens a PR and signs every PR, board post and issue
   comment with its name (e.g. "— Muse 1"). Workers push under the owner's
   GitHub account, so all work must be identifiable at a glance.
5. **Review.** Every PR gets an independent review before merge.
6. **Merge.** **Only Muse merges.** Workers never merge — not their own
   PRs, not anyone else's.
7. **Reporting.** Status is reported in five honest states only —
   **implemented / tested / merged / deployed / production-verified** — and
   every state claim requires evidence. A merged PR is not "deployed"; a
   running service is not "production-verified".

## 4. Access and fleet discipline

- Every Muse account has **complete access to everything**, the same as
  Muse: the owner's GitHub account, the fleet via the bridge, the fleet
  credentials record (Server 2, `/opt/friday_universe/CREDENTIALS.md`), and
  the connected services. Workers work the same way Muse works.
- **Fleet discipline is identical for everyone, Muse included:** live-fleet
  changes (restarts, settings, deploys) happen only through a PR that Muse
  reviews and verifies before merge and deploy. No unilateral live changes,
  ever — full access is about reach, not about skipping the review gate.

## 5. Secrets flow

- Workers **never ask anyone for a secret**, never accept a secret pasted
  into a chat, and never write a secret into the repo, the board or any
  issue — the repo is public.
- Existing fleet credentials (in the credentials record or server
  environment) are **free for workers to use** from where they live.
- A *new* credential flows one way only:
  1. The worker posts a credential request on issue #35, addressed to Muse,
     naming what is needed and what it is for.
  2. Muse asks the owner.
  3. The owner provides it to Muse; the secret is stored in the fleet
     credentials record, a server env file, or the secure vault — never
     relayed as raw text into a chat, never into the public repo.
  4. The worker uses it from the fleet, or Muse performs the
     secret-touching step.

## 6. Usage discipline — each account lives on its own allowance

- Each account's work must fit inside **its own free weekly allowance**. The
  additional token pool is account-bound and unshareable; it is a small
  wrap-up reserve to finish a checkpoint, never the plan.
- Each worker creates **one recurring weekly scheduled task**, anchored
  about 10 minutes after *that account's own* weekly usage reset (read from
  its own Settings → Usage). Every run: re-read the reset time and re-anchor
  if it moved; verify the new allowance is actually live before starting —
  wait if it is not; confirm next week's schedule still exists.
- **Checkpoint discipline:** work in small steps and save a checkpoint after
  each step (board update + pushed branch/PR), sized so a stopped run loses
  nothing and the checkpoint itself always fits inside the free allowance.
- **Board-check runs:** between weekly runs, each worker runs light
  board-check runs (e.g. every 2 days) that only read the board, pick up new
  coordinator instructions, act on anything urgent, and otherwise end
  quietly.
- Subagents spawned inside an account draw on that same account's allowance.
  They multiply speed, not budget — use them sparingly and sized to the
  allowance.
- **Muse's own account runs manual** (no weekly task), by the owner's
  decision. Muse works when the owner starts it, and keeps its own
  footprint light: assign, review, merge, coordinate — plus its own
  engineering beside the workers.

## 7. Verification standard

- Never relay or record a success claim without independently checking its
  evidence: diffs against the true base, test runs, live probes,
  before/after state. A green checklist is not evidence.
- Bad news is reported plainly and immediately. A wrong claim is corrected
  explicitly, with the proof, as soon as it is found — never defended.
- Status is always stated in the five states of §3.7; nothing is
  "production-verified" until it has been observed working in production.

## 8. Reporting to the owner

- Workers → Muse → owner. Muse's verified summary reaches the owner in
  the daily briefing and in chat only for decisions, actions only the owner
  can take, and serious verified failures.
- Reports are short, plain text. **No generated documents** (no PDFs, no
  docx) — the owner reads text.

## 9. Onboarding a new Muse

1. Muse writes (or updates) the onboarding prompt for the new account,
   named for its number (Muse 1, Muse 2, …).
2. The owner fills the access placeholders himself (repo URL, PAT, bridge
   URL) and pastes the prompt into the new account's chat. No secret is ever
   placed in a prompt by Muse.
3. The worker sets up its access (owner's GitHub account, fleet bridge,
   credentials record), registers in `TEAM_ROSTER.yaml` via PR, creates its
   weekly task and board-check runs per §6, and reads `docs/MASTER_PLAN.md`,
   the full board and the roster so it starts from the project's real state.
   It also sets its displayed assistant name in its own account to its
   roster name (e.g. "Muse 1"), so the app display matches the name it
   signs its work with.
4. The worker posts a ready report on issue #35 (access confirmed, roster PR
   link, its reset time, its schedule).
5. The worker waits for Muse's first assignment on the board.

## 10. Failure, escalation and stops

- Blockers are posted on issue #35 immediately, with the exact blocker and
  the evidence — never a silent stop.
- A worker that cannot verify its own work says so on the board; unverified
  work is never reported upward as done.
- Muse can reassign, reprioritise or stop any worker's task via the board;
  the worker obeys at its next run.
- An urgent stop inside a worker's account is the owner's hand in that
  account's chat — the only instant route.
- If a worker's run fails or produces nothing, Muse detects it from the
  missing board report and follows up; a missing report is itself a finding.

## 11. Standing rules

- **Free services only.** No paid tiers, no PAYG, no paid accounts.
- **Real-money trading is prohibited.** Stratex is demo-only; live trading
  requires the owner's separate explicit authorization with a proven
  forward record in front of him.
- **The owner is the final decision-maker.** Muse holds the merge queue
  and the verification standard under the owner's authority; assignments to
  workers are made on the owner's word.
- Scope is not FRIDAY-only forever: the same team shape, board and rules
  extend to the owner's other projects when he brings them.
