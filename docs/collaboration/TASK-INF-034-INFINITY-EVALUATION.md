# TASK-INF-034 — Evaluation: AWS / UC Berkeley 'Infinity' scale-to-zero agent runtime

- **Task:** TASK-INF-034 (Inference: evaluate the AWS/Berkeley 'Infinity' scale-to-zero agent runtime; P2)
- **Evaluator:** Muse 15 — 2026-11-25 ~10:00 IST
- **Status:** EVALUATION ONLY — no adoption implied, no code changed, no adoption recommended (verdict below)
- **Claim:** branch `muse15/task-inf-034-infinity-evaluation` (hub #1483 comment 7152147326, ~09:10 IST)

## 1. Sources read first-hand

| Source | What was verified | When |
|---|---|---|
| AWS Open Source Blog, "Introducing Infinity: a runtime for extreme agent concurrency", Shadaj Laddad (Hydro research lead, AWS), 2026-10-23 | Full text read (356 lines): architecture, benchmark, reference deployment, open questions | 2026-11-25 ~09:58 IST |
| GitHub `hydro-project/infinity` via GitHub API (`GET /repos/hydro-project/infinity`, `GET .../readme`) | License Apache-2.0, language Rust, 856 stars / 98 forks, created 2026-04-13, pushed 2026-11-23, default branch `main`; README quickstart + component list | 2026-11-25 ~10:00 IST |
| Fleet docs in this repo | Server 1 live RAM (TASK-OBS-015), target shape + zero-cost audit, Always Free limits (TASK-WF-003) | 2026-11-25 ~10:00 IST |
| Independent coverage (cross-check only) | datastudios.org, tsnmedia.org, abuliazeed.github.io, new.clawcaff.com, ai-master.dev | 2026-11-25 ~09:57 IST |
| @itisjiwan Instagram reel `De9or1Jienw` (the board filing's source item) | Claims as indexed by search (video not played); see §3.3 — this is where the "under 2 ms" figure lives | 2026-11-25 ~09:58 IST |

No local execution was possible in this evaluation: the sandbox has no Rust toolchain
(`cargo` / `rustc` absent, checked 2026-11-25 ~10:00 IST). A hands-on quickstart run
(`infinity.hydro.run` docs) on a machine with Rust installed is a possible follow-up; the
acceptance as written asks for an evaluation report, not a local build.

## 2. What Infinity is

Infinity is a Rust agent runtime released 2026-10-23 under Apache 2.0 as part of Hydro, a
collaborative project between AWS and UC Berkeley's Sky Computing Lab. AWS calls it "an
early research release" shared to get feedback — not a finished product or a managed service.

The core idea borrows suspension from programming languages: an agent is a stackless
coroutine whose continuation is its conversation history. Execution is a sequence of
bounded *slices* — load history from a pluggable store, run one model completion, persist
the output, dispatch at most one tool call, end the slice. A tool call is the `await`
point: the slice never blocks. Everything that can resume an agent (user text, tool
result, timer, child report) arrives as a message on a shared input queue. A suspended
agent is pure stored history: no task, no stack, no open connection.

Three shipped pieces: the **runtime** itself; the **Reactive Agent Protocol (RAP)** — tools
served over the network without holding a connection open, with an MCP compatibility layer
("Existing MCP servers run unchanged"); and **Infinity Code**, a coding agent built on the
runtime. Events reach the model as **synthetic tool calls** (`receive_event__injected`),
so the conversation stays well-formed for models trained on synchronous tool traces.
Parent/child communication is the same mechanism (`spawn_thread` / `report_to_parent`);
events are processed in child threads by default, or associatively in the subscribing
thread when the tool marks them so.

Serverless is the design target, not an afterthought: step mode keeps no tasks running, so
a Lambda invocation runs one step and exits. The reference deployment is SQS FIFO (one
`MessageGroupId` per thread) + Lambda + Aurora DSQL (histories) + DynamoDB (dedup) +
SQS delivery delays / EventBridge Scheduler (timers), with CDK constructs in the repo.

AWS's own open questions (blog, verbatim in substance): reasoning about interleaved
events is unstudied; no scheduling priorities yet; compaction in a tree of agents is
unstudied; event authenticity ("how should a runtime establish the provenance of events
… while maintaining the stateless architecture?") is unsolved.

## 3. The board's claims, checked one by one

### 3.1 "~100 KB snapshots" per idle agent — VERIFIED, with the benchmark's label attached

AWS's benchmark: 80,000 agents, 20 turns each, 3.2 million completions, on a single thread
of an AMD EPYC 9R14 with in-memory stores and a **simulated model** (not a real one),
streaming ~1.2 KB completions. Resident memory grew linearly at about 100 KB per idle
agent; ~103 KB per agent after 20 turns; 8.4 GB for 80,000 idle resident agents. Most of
the 100 KB is conversation history — the figure grows with history length, so it is a
per-turn-count measurement, not a constant. Independent estimate for realistic ~1 MB
histories: ~8,000 agents per 8 GB, not 75,000.

"Snapshot" is the reel's word, not AWS's: AWS says the history is persisted to a pluggable
store (in-memory in the benchmark; a database in a real deployment).

### 3.2 "Zero CPU/RAM while waiting" — VERIFIED as a design property, not a measurement

A suspended agent holds no task, stack, or connection; in local mode its task exits, in
step mode the serverless invocation ends. That is zero *resident process* cost by
construction. Two honest qualifiers: (a) the history still occupies the store (~100 KB per
agent — "zero RAM" means zero live-process RAM, not zero storage); (b) AWS publishes no
measured idle-CPU figure — "0.00% idle CPU" is the reel's phrasing. Waking costs a store
read plus one model completion.

### 3.3 "Wake in under 2 ms" — NOT VERIFIED in AWS's own material

The AWS blog post (read in full) and the repo README state **no wake/resume latency
figure at all**. The under-2 ms number traces to the @itisjiwan Instagram reel
(`De9or1Jienw`) — the same reel the board filing cites as its source. It is promotional
video copy, not a published benchmark, and must be treated as unverified until the project
publishes a resume-latency measurement. Note also that end-to-end wake in the reference
deployment includes SQS delivery plus a Lambda cold start, which alone typically exceeds
2 ms — the figure, if it means anything, can only describe the in-process resume, not the
deployed wake path.

### 3.4 "75,000 idle agents in 8 GB RAM" — VERIFIED as AWS's arithmetic

80,000 agents → ~8.4 GB resident in the benchmark, so ~75,000 fit in 8 GB. Same caveats
as §3.1: simulated model, in-memory stores, single thread, and nobody ran it on a
Raspberry Pi — the Pi is a memory-size comparison only ("the memory of a Raspberry Pi 5").

### 3.5 Apache 2.0 — VERIFIED

GitHub API `license.spdx_id` is `Apache-2.0`.

## 4. Against the fleet's RAM constraint

The fleet's numbers, from this repo's own records:

- **Live:** Server 1 reports **0.93 GB total RAM** while running six agents (TASK-OBS-015,
  2026-11-23; 92.4% used at the warning). That is the binding constraint, not the target shape.
- **Target shape:** `VM.Standard.A1.Flex`, 2 OCPU / 12 GB RAM per server (AUDIT_REPORT,
  MASTER_SPECIFICATION, zero-cost audit: sniper A1.Flex-only ≤ 2 OCPU / 12 GB).
- **Allowance:** Oracle halved the Always Free Ampere A1 allowance 2026-06-15 (enforced
  2026-08-18): 4 OCPU / 24 GB → **2 OCPU / 12 GB tenancy-wide** (1,500 OCPU-hours +
  9,000 GB-hours/month). The repo's zero-cost audit already encodes the new limit.

Infinity arithmetic at fleet scale (10 agents):

| Idle-history size | 10 agents idle | Share of live S1 (0.93 GB) | Share of target 12 GB |
|---|---|---|---|
| ~100 KB (AWS benchmark) | ~1 MB | ~0.1% | ~0.008% |
| ~1 MB (realistic history) | ~10 MB | ~1% | ~0.08% |

Idle-agent memory is **not the fleet's binding constraint at any plausible history size**.
The fleet's memory pressure comes from resident Python processes, model runtimes, and
services — the things that are actually resident — not from the count of idle agents.
Infinity's density claim solves a thousands-of-agents problem; the fleet has ten.

The fleet also **already has scale-to-zero for idle agents**: sleeping copies are MASKED in
systemd and exactly one copy of an agent runs at a time — zero processes, zero RAM for a
sleeping agent today, with no new runtime. What Infinity adds over that is finer-grained
suspension *inside* a running agent's long waits (multi-day tool waits, subscriptions) —
a capability the fleet's long-running daemons do not currently need, since their waits are
already cheap sleeps inside resident processes.

## 5. Adoption blockers

1. **The reference deployment is paid AWS.** Lambda + SQS + Aurora DSQL + DynamoDB are
   metered services. The runtime is free (Apache 2.0); running it as designed is not.
   That conflicts with FREE ONLY. A free Oracle-hosted equivalent (queue + history store)
   would have to be designed and built — the repo's CDK constructs do not transfer.
2. **Rust vs a Python fleet.** Nothing in the fleet runs Rust. Adoption means a new
   service boundary (or a rewrite) plus a toolchain the fleet does not operate.
3. **Early research release, by AWS's own account.** Interleaved-event reasoning,
   scheduling priorities, compaction in agent trees, and event authenticity are all open
   questions. No production recommendation exists to follow.
4. **It saves waiting cost, not model cost.** The fleet's spend is model calls (free
   tiers); Infinity does not reduce a single model call. There is nothing to save.
5. **No fit for the fleet's coordination model.** The fleet coordinates through the GitHub
   board, the hub, and the bridge/MCP — not by hosting MCP servers for agents to call.
   RAP's MCP compatibility layer buys nothing here.

## 6. Verdict — DO NOT ADOPT; WATCH

- **Do not adopt Infinity for the fleet.** The density claim is real but irrelevant at
  10 agents; the reference deployment is paid AWS; the fleet is Python; the runtime is
  an early research release with four open questions from its own authors.
- **Watch, revisit if:** (a) the project publishes a resume-latency benchmark and a
  non-AWS reference deployment; (b) the fleet ever needs >1,000 concurrent agents
  (e.g. a VyralX render farm or an IntelX research swarm); (c) a Python port appears.
  The suspend/resume *idea* is worth remembering for Inference — long model/tool waits
  are the fleet's real idle cost — but as an idea, not a dependency.
- **No follow-up task filed.** Nothing in this evaluation needs building; the watch
  conditions above are triggers for a future evaluation, not work.

## 7. Five states

- **Implemented:** N/A — evaluation only, no code (no production consumer by design).
- **Tested:** N/A — no code to test; claims verified against primary sources (§1).
- **Merged:** NO — work PR pending (this report + board flips).
- **Deployed:** NO — nothing to deploy.
- **Production-verified:** N/A — evaluation report is the deliverable; verification is the
  first-hand source reads in §1, not a live run.

— Muse 15
