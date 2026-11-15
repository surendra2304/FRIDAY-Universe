# IG Reference Notes — FRIDAY lane (TASK-IG-FRD-011)

Notes from the owner's Instagram reference corpus (2026-11-15) for the
items that are **benchmarks and patterns, not features to build**. Kept
so future crews do not re-litigate them. Companion implementation
tasks: TASK-IG-FRD-001…010.

## 1. "All my employees are agents" — org pattern (item `DanLpQ2KdzV`)

**Corpus classification: already implemented.** Verification against
the architecture as it actually stands (AGENTS.yaml v3.0.0, read
2026-11-15):

| Reel's org chart | FRIDAY Universe equivalent |
|---|---|
| One human owner, final say | The owner; agents act under his standing rules |
| A chief-of-staff agent routing work | **FRIDAY** (10000) — orchestration, dispatch bus, mission queue |
| Specialist "employees" with their own domains | **Inference** 8001 (models), **Memora** 8002 (memory), **Stratex** 8003 (trading), **Futuris** 8004 (forecasting), **IntelX** 8005 (research/OSINT), **Forge** 8006 (code), **Sentinel** 8008 (security/ops), **Cortex** 8009 (decisions/CRM), **VyralX** 8010 (content) |
| Employees that hand work to each other | Peer dispatch + the mesh (FRIDAY routes; specialists also call each other through the gateway) |
| Work tracked on a board | docs/collaboration/WORK_BOARD.yaml + issue #35 coordination |

What the reel adds structurally: **nothing**. The pattern is the
project's founding architecture. The honest gaps are not structural —
they are depth gaps inside individual agents (tracked by their own
task lanes), not a missing org layer. **Do not rebuild an "agent
employees" layer on top of this.**

## 2. Peer Jarvis demo (item `DaMk3NWxVop`) — benchmark, no discrete feature

The reel demonstrates a peer Jarvis-style assistant end-to-end. It
contains no separable feature the corpus could name; its value is as
an experience benchmark. The bars worth holding FRIDAY to, and the
workstream that owns each:

- **Time-to-first-response in voice** — the demo answers immediately;
  FRIDAY's voice is judged on speed first (owner criterion 2026-11-15;
  VOI lane / voice acceptance harness).
- **Follow-through without re-prompting** — the demo's assistant
  completes multi-step asks in one thread; FRIDAY's equivalents are
  the goal-loop engine (TASK-IG-FRD-001) and persistent follow-up
  tracking (TASK-IG-FRD-002).
- **Visible state** — the demo shows what the assistant is doing;
  FRIDAY's surface for this is the website (owner's design pick from
  the stored candidates) plus the activity/announcement streams.

No task is created from this item; it is cited by the lanes above as
their acceptance reference.

## 3. Reference-only repositories (verdicts from the repo pass — binding)

These were deep-read during the corpus repo pass
(~/workspace/ig-references/repos/). Verdict for each: **reference
only** — FRIDAY already implements the pattern; do not adopt or
integrate the code.

- **hermes-agent** — persistent self-improving agent loop with memory
  and skills. FRIDAY's equivalents: the agent loop + mission queue,
  Memora-backed memory, the skill registry, and now the goal-loop
  engine (TASK-IG-FRD-001). Read for loop-design ideas only.
- **herald-os** — voice-first ambient assistant surface. FRIDAY's
  equivalents: the Gemini Live voice worker + the Halo website's
  voice-first home. Read for interaction patterns only.
- **openclaw** — multi-channel personal-agent gateway (many messaging
  surfaces into one agent). FRIDAY's equivalents: the API server +
  companion websocket + phone/laptop bridges. Read for channel
  patterns only.

## 4. Related pattern sources already actioned elsewhere in this lane

- **Project NOMAD** (offline-first) — verdict *adapt*; miniature built
  as TASK-IG-FRD-007 (full stack waits for the ARM server).
- **Manus Cue** (delegated errands; closed-source, pattern only) —
  framework built as TASK-IG-FRD-004 with hard approval gates.
