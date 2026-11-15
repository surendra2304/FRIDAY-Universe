# IG Corpus — Forge Evaluation Notes (TASK-IG-FRG-08)

Evaluations of the Instagram reference corpus items that map to Forge
but are **reference-only** (per their repo cards in
`~/workspace/ig-references/repos/`, whose fit verdicts bind) or are
product/workflow references with no repo to integrate. For each: what
it is, what the corpus actually shows (evidence limits stated),
Forge's verdict, and the concrete pattern worth adopting — if any.
No code was integrated from any item in this document.

Companion PRs in the same wave implement the corpus's buildable
Forge ideas: TASK-IG-FRG-01 (review passes), -02 (skill registry),
-03 (design import), -04 (sketch-to-prompt), -05 (checkpoints),
-06 (plan-to-ship), -07 (build templates).

---

## 1. JCode — coding-agent harness (1jehuang/jcode)

- **Source:** Da5fhPriu3n. **Card fit:** adapt; **coordinator ruling
  for this wave: reference-only** — evaluation plus cheap adoptable
  patterns, no integration.
- **What it is:** a Rust coding-agent harness whose pitch is
  efficiency (~71MB first headless session, ~3.3MB per extra session,
  per its README benchmarks), with automatic semantic memory, parallel
  sessions coordinated by a server, a swarm tool for agent
  collaboration/conflict resolution, and many provider backends.
- **Evidence limit:** the footprint/speed figures are the project's
  own README claims, not measured on FRIDAY hardware.
- **Verdict:** do not adopt the harness. Forge is a Python service
  embedded in a 10-agent fleet with its own orchestrator, memory
  (Memora) and model gateway (Inference); replacing its runtime with
  a Rust CLI harness would be a rewrite, not an integration, and its
  headline benefit (small footprint) matters for a *local* harness,
  not for Forge's server-side build path.
- **Adoptable patterns (cheap, no rewrite):**
  1. *Lean session context* — JCode's sessions carry a compact,
     explicit context rather than an ever-growing transcript. Forge's
     equivalent is TASK-IG-FRG-05's `project_context_digest` (bounded,
     deterministic) — the pattern is already picked up there.
  2. *Parallel sessions with file-conflict resolution* — Forge builds
     are single-workspace today; if parallel build waves are ever
     introduced, conflict detection must come first (checkpoint diffs
     from FRG-05 give the detection half).
  3. *Lead + helper session shape* — mirrors the fleet's existing
     coordinator/crew structure; no Forge change needed.

## 2. OpenMausBot — unified desktop shell for agent CLIs (milind-soni/OpenMausBot)

- **Source:** DeZ-JEFNTpR. **Card fit: reference-only.**
- **What it is:** an Electron desktop app that unifies many agent
  CLIs (Claude Code, Codex, Hermes, OpenClaw, …) behind one
  chat-style UI, each bot with its own model/memory, approval cards
  before acting, data kept local.
- **Verdict:** not a Forge component. It is a heavyweight desktop
  shell for a *developer's machine*; Forge runs server-side on ~1GB
  hosts and FRIDAY already has its own coordination surface (the
  website + the board). Running an Electron shell in the fleet is
  not viable and not needed.
- **Adoptable pattern:** the *approval card* — a structured,
  human-readable "I am about to do X" prompt before a consequential
  action. Forge's dangerous-action gates already refuse silently
  (fail-closed); presenting the refusal/approval in the owner's chat
  surface as a card is a FRIDAY-website concern, noted here for the
  Website-UI lane, not a Forge build task.

## 3. Paperclip — agent-team orchestration platform (paperclipai/paperclip)

- **Source:** DeihJQuCpdp (also the source of FRG-01's security-review
  idea). **Card fit: reference-only.**
- **What it is:** a self-hosted Node.js platform that "hires" agents
  into an org chart with goals, tickets, heartbeats, per-agent
  budgets, approvals/governance and audit logs.
- **Verdict:** do not run it — a second orchestration server
  alongside the fleet on ~1GB VMs is not viable, and its governance
  model is one FRIDAY already implements in its own shape:
  WORK_BOARD.yaml (tickets/goals), the merge queue (approvals),
  per-task budgets (Forge's budget tests), and issue #35 (audit log).
- **Adoptable pattern:** *per-agent budget + heartbeat as first-class
  board fields*. Forge's board entries already carry status and
  next_action; adding an explicit budget/heartbeat field for
  long-running build tasks is a board-schema suggestion for the
  coordinator, not a code change here.

## 4. Codex feature tracking (OpenAI Codex)

- **Source:** Ddlk8oQyOVO — a reel teasing "a must-know Codex
  feature"; **the feature itself is not visible in the data we hold**
  (caption/gist only), so there is no specific feature to adopt and
  none is invented here.
- **Method adopted instead of a feature:** Forge evaluates external
  coding-agent features against three questions before adopting —
  (1) does it change a *measured* Forge defect (the FRG-003 battery
  failure modes are the standing list)? (2) does it run within the
  fleet's constraints (Python 3.10, ~1GB hosts, free tiers)?
  (3) can it land as a small module + fail-on-main tests, the shape
  every task in this wave took? A feature that fails any question is
  a note, not a task.

## 5. Agentic-IDE / builder-environment references

- **Sources:** DXMg0D9jD3Y (VS Code extensions: Live Server, Quokka.js
  inline evaluation, Copilot), DdjTV_zCTUH (coding agent inside the
  editor via API-key config), DahPUsHOkrC (Google Antigravity agentic
  IDE used to build a site). Antigravity/Stitch are hosted Google
  products (no repo); the corpus's design-pipeline idea from the same
  cluster is implemented in TASK-IG-FRG-03.
- **What Forge genuinely lacks, stated plainly:** two builder-loop
  capabilities these references assume —
  1. **Live preview of generated web output.** Forge verifies static
     output with checkers but does not *serve* a generated site for
     the owner to look at before delivery. Smallest honest version:
     a preview endpoint that serves a completed build's static files
     read-only, bound to the build's verification manifest (so what
     is previewed is exactly what was verified — FRG-011's snapshot
     binding is the mechanism). Proposed as a follow-up task; not
     built in this wave.
  2. **Inline evaluation in the dev loop** (Quokka-style: expression
     results beside the code). Forge's loop is batch (generate ->
     battery -> repair); inline eval is an editor-side feature of the
     *owner's* IDE, not of the server-side builder. No Forge task;
     noted so the gap is a decision, not an oversight.
- **Agent-in-the-IDE setup pattern** (DdjTV_zCTUH): configuration,
  not code — an owner-side option for his own editor, recorded here
  so it is not mistaken for a Forge feature gap.

## 6. claude-mem — persistent memory for coding agents (thedotmack/claude-mem)

- **Source:** DeihJQuCpdp. **Card fit: adapt — Memora owns the
  pattern; Forge is a consumer.**
- **What it is:** an observer agent records a coding session,
  compresses it, and injects a compact index into future sessions.
- **Forge-side note:** Forge already persists build lessons in its
  pattern library (TASK-FRG-006) and task lifecycle store; the
  claude-mem delta worth having — *automatic* session capture +
  compression rather than hand-written patterns — belongs to the
  Memora lane's implementation of this card. No Forge code in this
  wave; if Memora lands session compression, Forge's consumer half
  is: query it at build start with the goal text, inject the returned
  index into the developer prompt (the FRG-05 digest is the local
  fallback when Memora has nothing).

---

*Method note: every verdict above traces to a repo card or a triage
item in `~/workspace/ig-references/`; where the corpus data does not
show the thing itself (notably §4), this document says so instead of
reconstructing it.*
