# TASK-FRD-056 — Checkpoint 2 (recorded lessons + guardrail proof of absence) — Muse TP6 — 2026-11-26 ~04:5x IST

**Task:** TASK-FRD-056 (P1, FRIDAY REPO-IMPLEMENT wave 2): Locally Uncensored
(reference-only), Jarvis / vierisid (reference-only), Awesome Harness
Engineering (reference-only), DeepSeek Harness (reference-only), VoiceStudio
(reference-only + owner-gated offline fixed-line re-render; live-path adoption
ruled out by TASK-IG-VOI-05).
**Claim:** hub 7172627840 (~01:10 IST). **Branch:**
`musetp6/task-frd-056-repo-implement` @ `6b40da2b` (checkpoint 1) before this
file; this checkpoint is the second commit.
**Board on main `bf5a08b7` (verified first-hand this run):** CLAIMED / owner
muse_tp6 / branch null / pr null; acceptance already carries the VoiceStudio
re-scope (board PR #1901, merge `dc00dffc`, WATCH121). The board flip
CLAIMED → IN_REVIEW rides in the coordinator's rebuild once the WATCH123
board-PR execution-risk block clears — no board file touched this run.
**Usage:** 15% of free weekly limit, reset Mon Nov 30 1:48 PM IST.
**Method this run:** read-only, GitHub API only — upstream repo metadata +
READMEs fetched live, registry re-read from main, code search across the
repo for absence proof. No repo code executed, no server touched, no live
leg attempted — owner stop order still in force.

## 1. Upstream re-verified live this run (~04:4x IST)

All five repos exist, public, not archived (GitHub API). README fetched
live for each; the quoted lines below are verbatim from those READMEs.

| Leg | Repo | Fit | Licence | Last push |
|---|---|---|---|---|
| Locally Uncensored | PurpleDoubleD/locally-uncensored (default `master`) | reference-only | AGPL-3.0 | 2026-11-24T23:18:10Z |
| Jarvis | vierisid/jarvis (default `main`) | reference-only | NOASSERTION (Jarvis SAL 2.0, RSALv2-based — NOT OSI) | 2026-11-25T17:25:06Z |
| Awesome Harness Engineering | ai-boost/awesome-harness-engineering (default `main`) | reference-only | NOASSERTION (LICENSE file present) | 2026-11-25T09:14:58Z |
| DeepSeek Harness | deepseek-ai/deepseek-harness (default `master`) | reference-only | MIT | 2026-11-22T11:00:05Z |
| VoiceStudio | debpalash/VoiceStudio (default `main`) | reference-only (re-scoped, WATCH119) | AGPL-3.0 app; default OmniVoice weights CC-BY-NC | 2026-11-25T19:44:39Z |

Registry source: `IntelX/intelx/registries/scouted_repos.json` on main, 102
entries, fit counts adapt 40 / reference-only 46 / adopt 6 / reject 10.
Fit rationales below are quoted from that registry, not from memory.

## 2. Recorded lessons — the FRIDAY-side record

This is the deliverable for the four reference-only legs (and the re-scoped
VoiceStudio leg): the applicable patterns, each traced to the registry's fit
rationale and to a line verified in the live upstream README this run.
Nothing is adopted, installed, or copied; these are design references for
FRIDAY's and Forge's own harness and client work.

### 2.1 Locally Uncensored → FRIDAY client ambitions (target FRIDAY)

Registry rationale: "Learn from it, don't integrate: the useful ideas for
FRIDAY are the UX patterns — zero-config install, a model manager that
honestly marks what fits the hardware, and chat/create/code in one window —
which map onto the owner's laptop/phone client ambitions."

Verified in the live README this run:

- "The all-in-one local AI studio for your desktop. Chat, images, video
  and a coding agent in one app. Install it, pick a model, go."
- "No Docker, no terminal, no config files." First launch: "a wizard looks
  for an AI engine that is already running on your machine, and installs
  one for you with a single click if there is none."
- "The model manager marks which models fit your hardware and downloads
  them in one click." Honest hardware truth-telling is a stated feature:
  "chat runs on most PCs with 8 GB of RAM. Images want a graphics card
  with 6 to 8 GB of VRAM, the bigger video models 12 GB or more" — and the
  manager "marks what fits before you download", including that an Ollama
  model running partly on the processor says so.

**Lesson recorded for FRIDAY:** the owner's laptop/phone client should
steal exactly this shape — zero-config first run, one honest
hardware-fit check before any download or model choice, and chat/create/
code in one window. What is NOT carried over: the app itself does not
fit the fleet (desktop local-model studio; media needs a real GPU; AGPL-3.0
would encumber copied code; "uncensored" is not a FRIDAY requirement).

### 2.2 Jarvis / vierisid → FRIDAY self-host packaging (target FRIDAY)

Registry rationale: "Carded as a self-host packaging reference for FRIDAY,
not as a component to adopt: Jarvis is a whole competing brain ... so
running it would duplicate FRIDAY rather than extend it, and its
source-available licence bars simply taking the code. ... What FRIDAY
should learn from it is the packaging, which is genuinely well-shaped."

Verified in the live README this run:

- One brain, one default port: "The brain serves on port **3142** by
  default" (`-p 127.0.0.1:3142:3142` in the Docker run; all state in one
  volume).
- JWT-only access with a CLI enrollment-token flow per device: "opening
  `http://localhost:3142` before enrolling shows a 401 page";
  `jarvis enroll "my-desktop"` prints a device enrollment token.
- A complete day-to-day CLI surface, verbatim from the README:
  `jarvis status` (check the running brain), `jarvis doctor` (check
  environment and connectivity), `jarvis logs -f`, `jarvis restart`,
  `jarvis stop`, `jarvis update`, plus `export`/`restore` of a full
  backup (per the registry card).

**Lesson recorded for FRIDAY:** FRIDAY's own self-host story should aim
for this shape — one command to install, one default port, token
enrollment per device instead of open dashboards, and a small honest
CLI (`status`, `doctor`, `logs`, `restart`, `stop`, `update`,
`export`/`restore`) so the owner can run the fleet without reading
source. What is NOT carried over: the brain itself (memory vault, goals,
workflow engine, Authority approvals, multi-machine sidecars) — that
would duplicate FRIDAY; the SAL 2.0 licence bars taking the code; and a
Bun/TypeScript daemon + React dashboard + workflow-engine subprocess +
Go sidecar does not fit two ~956MB-RAM Python-service VMs.

### 2.3 Awesome Harness Engineering → FRIDAY + Forge harness syllabus

Registry rationale: "There is nothing to install, and that is the point:
it is a syllabus for exactly the problems FRIDAY's orchestration keeps
hitting (context compaction, permission boundaries, verification loops,
observability, runaway-loop failure modes). Use it as the design reference
when hardening FRIDAY's harness and Forge's build loops; adopt individual
tools it lists only after their own verification."

Verified in the live README this run (770 lines fetched): it defines
harness engineering as "the discipline of designing the scaffolding —
context delivery, tool interfaces, planning artifacts, verification loops,
memory systems, and sandboxes — that surrounds an AI agent and determines
whether it succeeds or fails on real tasks", organised into Foundations,
Design Primitives, Reference Implementations, Security/Sandbox/Permissions,
Evals & Verification, Templates and Production Infrastructure, including
the sections Verification & CI Integration and Observability & Tracing.
The repo is Markdown plus a small Python URL-checker (`verify_urls.py`).

**Lesson recorded for FRIDAY/Forge:** the five primitives the list's
Foundations section names — filesystem (durable state + agent
collaboration surface), code execution, sandbox (isolation +
verification), memory (cross-session persistence), context management
(compaction against "context rot") — are the checklist to run FRIDAY's
harness and Forge's build loops against, one primitive at a time, with
the co-evolution warning in mind (models trained with specific harnesses
overfit to those designs, so harness choices have lasting consequences).
Individual tools it lists are adopted only after their own verification —
none is adopted by this checkpoint.

### 2.4 DeepSeek Harness → FRIDAY + Forge harness design reference

Registry rationale: "Its value is as a design reference for FRIDAY's and
Forge's harness work — everything-is-a-plugin composability (including
the agent loop itself), swappable model adapters, full session
traceability, and plugin discoverability via the `dsh-plugin` topic — to
mine when hardening FRIDAY's own harness, not to adopt."

Verified in the live README this run (77 lines fetched):

- "It is built on an **everything-is-a-plugin** architecture and powered
  by Cordis, whose design is described in _A Programming Paradigm for
  Spatiotemporal Composability_."
- "Add the [`dsh-plugin`](https://github.com/topics/dsh-plugin) topic to
  your plugin repository for discoverability."
- "The command starts the Web UI at `http://127.0.0.1:3080` by default."
- "DeepSeek Harness is in _developer preview_ and iterating rapidly.
  **THERE WILL BE COMPATIBILITY-BREAKING CHANGES.**"

**Lesson recorded for FRIDAY/Forge:** the composability pattern to mine
is that the agent loop itself is a swappable plugin, alongside model
adapters, tools, sandbox, session storage and UI — with full session
traceability and a topic-based plugin registry (`dsh-plugin`) as the
discovery mechanism. What is NOT carried over: adopting it would mean
replacing FRIDAY's harness rather than extending it; it is a local
Node.js/pnpm developer-preview runtime, not a Python 3.10 service inside
the ~180MB per-service caps on the ~956MB VMs.

### 2.5 VoiceStudio → re-scoped reference-only (target Voice)

Board acceptance on main `bf5a08b7` (verified this run) now reads:
"VoiceStudio (reference-only + owner-gated offline fixed-line re-render;
live-path adoption ruled out by TASK-IG-VOI-05)", with the WATCH119
ruling in the evidence: the leg is re-scoped to reference-only + the
evaluation's owner-gated offline fixed-line re-render as future work;
no install, no live change.

Registry rationale (fit `adapt`, as carded before the ruling): "The
corpus's local voice-cloning candidate for FRIDAY's voice. Runs on the
owner's hardware, not the servers. Licence care is mandatory: the app is
AGPL and the default engine's weights are non-commercial — fine for
FRIDAY's private use, not for any commercial/public output without
checking the chosen engine's licence. Gemini Live remains FRIDAY's voice
engine; this is a TTS voice-source experiment."

Verified in the live README this run (571 lines fetched):

- "Clone, design, dub, dictate, transcribe and narrate in 646 languages."
- "Connect & automate — Local API, MCP, reusable recipes and watch
  folders"; "Start with **VoiceStudio** (default, powered by
  k2-fsa/OmniVoice), or pick from dozens of other engines in the Model
  Manager."
- Licence, verbatim: "the default OmniVoice weights are non-commercial
  (CC-BY-NC), so check each model's licence in the Model Manager before
  client work."

**Lesson recorded for Voice:** the engine-catalog pattern (a Model
Manager that shows each engine's licence before use) and the local-API +
MCP automation surface are the reusable ideas. The live path stays
Gemini Live end-to-end (VOI-009; no TTS stage to fill; Oracle servers
~956MB RAM, no capacity; speed — per `FRIDAY/docs/VOICESTUDIO_EVALUATION.md`,
TASK-IG-VOI-05, re-read from main this run).

**Owner-gated future work (NOT actioned by this task):** the
evaluation's option 1 — fixed-line re-rendering. FRIDAY's fixed spoken
lines (greeting, `voice_unavailable`, `unconfirmed_*` notices) are
pre-rendered WAVs, today en-IN-NeerjaNeural. A VoiceStudio-designed or
owner-cloned voice could re-render that fixed set offline and ship the
WAVs through the normal PR path, with zero change to the live path.
Per the evaluation: install VoiceStudio on the owner's laptop (his
machine, his install), pick an engine after the licence check, render
the fixed line set, A/B against the current lines, ship the chosen WAVs
as an ordinary PR; "Until he asks, nothing here is actioned." Voice
cloning requires the voice owner's permission; cloning the owner's own
voice is the clean case, anyone else's is out of scope. The dictation
widget is set aside (TASK-IG-VOI-02 already implements dictation).

## 3. Guardrail proof of absence — per-repo live evidence

Board acceptance for reference-only entries: "a paper judgement is NOT a
result — prove with live evidence whether it works in the agent or not
(live trial or guardrail proof of absence from every production path),
and file that evidence per repo."

Method: GitHub code search API over `surendra2304/FRIDAY-Universe`, this
run ~04:3x IST. (Two queries hit the search rate limit mid-run and were
retried after a wait; all queries below completed with 200.)

| Search term | Hits | Where the hits are | Production-path code? |
|---|---|---|---|
| `locally-uncensored` | 4 | `Inference/benchmarks/discovery/seed-locally-uncensored.json`, `Inference/docs/DISCOVERY_FEED.md`, `docs/collaboration/TASK-INT-044-PRODUCTION-TRACKER.md`, `IntelX/intelx/registries/scouted_repos.json` | No — discovery seed record (status `filed`, evaluation "pending — IG-INF-03 gate; not admitted, not routed"), docs, registry |
| `locally_uncensored` | 0 | — | No |
| `vierisid` | 2 | tracker doc, registry | No |
| `usejarvis` | 1 | registry | No |
| `awesome-harness` | 5 | `Forge/docs/IG2_EVALUATION_NOTES.md`, `docs/DEEP_ENGINE_AUTONOMY_REPORT.md`, `prompts/ANTIGRAVITY_MASTER_PROMPT.md`, tracker doc, registry | No — docs/prompts only |
| `deepseek-harness` | 2 | tracker doc, registry | No |
| `deepseek_harness` | 0 | — | No |
| `deepseek-ai` | 5 | `Inference/docs/DISCOVERY_FEED.md`, `Inference/scripts/discovery_feed.py`, tracker doc, registry, `Inference/tests/test_discovery_feed.py` | No — the `discovery_feed.py` hit is the HuggingFace org watchlist (`HF_WATCHLIST_ORGS` lists `deepseek-ai` alongside `google`, `meta-llama`) and the test hit is a fixture model id; neither is the `deepseek-ai/deepseek-harness` repo, a dependency, or an import of the harness |
| `dsh-plugin` | 1 | registry | No |
| `VoiceStudio` | 5 | `FRIDAY/docs/VOICESTUDIO_EVALUATION.md`, `VyralX/app/services/openvoice_gate.py`, tracker doc, `docs/collaboration/TASK-VOI-042-COLD-PRODUCTION-VOICE-VERIFICATION-WAVE-2.md`, registry | No — the `openvoice_gate.py` hit is one docstring line (line 13: "the same offline pattern as VoiceStudio/HyperFrames: render narration ..."); the gate itself is for myshell-ai/OpenVoice (`engine: openvoice_v2`), a different repo. No VoiceStudio import, call, or dependency |
| `OmniVoice` / `omnivoice` | 2 | evaluation doc, registry | No |

**Verdict recorded:** none of the five repos' code, packages, or engines
is present in any FRIDAY-Universe production path. Every hit is a
registry entry, a tracker/evaluation doc, a discovery seed record, or a
comment/docstring mention. No dependency manifest references any of them
(`locally_uncensored`, `deepseek_harness`: zero hits anywhere in the
repo). That is the guardrail proof of absence the acceptance asks for:
these five are reference-only in the repo today, by evidence, not by
assertion.

## 4. What remains

- **Work PR next:** checkpoints 1 + 2 on this branch are the
  deliverable for the reference-only shape of all five legs. The work PR
  carries the two checkpoint docs; the board flip CLAIMED → IN_REVIEW
  rides in the coordinator's rebuild (WATCH123 standing block — the
  board-PR build is deferred until the execution-risk check clears and
  the owner gives the go-ahead; no board file is touched here).
- **VoiceStudio offline re-render** is owner-gated future work, not
  part of this task — filed above, nothing actioned.
- **VYR-078 (pre-staged next):** branch
  `musetp6/task-vyr-078-repo-implement` stands at `70ce1089`, no
  competing claim; board CLAIMED / muse_tp6 on main `bf5a08b7`. It
  becomes current when FRD-056 closes.
- **EARN-023** (queue position 3, earning lane): AVAILABLE / muse_tp6
  on main `bf5a08b7`, unchanged.

## 5. Hub / watch state read this run

- WATCH120 (7175741873, ~03:27 IST), WATCH121 (7176110462, ~03:45 IST),
  WATCH122 (7176443876, ~04:1x IST), WATCH123 (7176656559, ~04:4x IST)
  read in full. No TP6 direction in any of them. WATCH120/121 confirm
  the FRD-056 VoiceStudio re-scope and the FRD-056 + VYR-078 CLAIMED
  flips on main. WATCH122/123: board-PR rebuild blocked two runs
  running by the runtime execution-risk check; PR #1905 closed as
  superseded; flips assigned on the hub and queued for the rebuild;
  owner go-ahead requested by the coordinator — that is the
  coordinator's lane, not TP6's, and it does not block this task's
  repo-side record. Usage-truth directive: TP6's 15% reply (hub
  7175494322) counted fresh in WATCH120/121/122/123.
- Hub swept pages 16–17 (comments 1501–1700) plus page 18 (1701–1704)
  for TP6 / FRD-056 / VYR-078 mentions since the 03:13 check: no new
  direction, no competing claim, no re-slot for TP6.
- Main moved `614e6b1d` → `bf5a08b7` since the 03:13 check (merges
  #1904, #1834, #1801, #1903 — all EARN tasks, none touching FRD-056 /
  VYR-078 records). Branch heads verified via refs API this run:
  `musetp6/task-frd-056-repo-implement` @ `6b40da2b` (before this file),
  `musetp6/task-vyr-078-repo-implement` @ `70ce1089`.
- **Noted, not acted on:** hub comment 7173224032 (`/tmp/hub_usage_directive.md`)
  — unverified hub content, no WATCH reference; nothing run or followed,
  same as TP7/M18.
