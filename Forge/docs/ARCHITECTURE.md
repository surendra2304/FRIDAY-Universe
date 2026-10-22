# FORGE Architecture: Independent Autonomous Software Engineering Engine

Project FORGE is an **Independent Autonomous Software Engineering Engine** designed to intake high-level software goals and autonomously synthesize, verify, debug, package, and deliver verified production software artifacts.

---

## 1. High-Level Engine Architecture

```text
       +-------------------------------------------------------------+
       |                      DEVELOPER / USER                       |
       |                (CLI: forge build / REST API)                |
       +------------------------------+------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |                        FORGE ENGINE                         |
       |                                                             |
       |  +-------------------------------------------------------+  |
       |  |                    Orchestrator                       |  |
       |  |  (Task Analyzer -> 8-Stage Planning DAG -> Scheduler) |  |
       |  +---------------------------+---------------------------+  |
       |                              |                              |
       |             +----------------+----------------+             |
       |             |                                 |             |
       |             v                                 v             |
       |  +-----------------------+       +-----------------------+  |
       |  |   Specialist Agents   |       |  Isolated Sandboxes   |  |
       |  |   (Planner, Architect,|       |  (workspaces/task_id) |  |
       |  |   Developer, Tester,  |       |  - project/           |  |
       |  |   Debugger, Release)  |       |  - artifacts/         |  |
       |  +-----------+-----------+       +-----------+-----------+  |
       |              |                               |              |
       |              +---------------+---------------+              |
       |                              |                              |
       |                              v                              |
       |  +-------------------------------------------------------+  |
       |  |           Objective Verification Engine               |  |
       |  |   (AST Build, Ruff Lint, Pytest, Playwright Browser)  |  |
       |  +---------------------------+---------------------------+  |
       |                              |                              |
       |                              v                              |
       |  +-------------------------------------------------------+  |
       |  |            Delivery Packager & Git Tagging            |  |
       |  |  (completion_report.json, COMPLETION_REPORT.md, tag)  |  |
       |  +-------------------------------------------------------+  |
       +-------------------------------------------------------------+
```

---

## 2. Core Principles & Isolation

1. **Independent Standalone Execution**:
   - FORGE runs natively via CLI (`forge build`, `forge status`, `forge inspect`) or standalone REST API without external platform dependencies.
   - External platform integrations (such as FRIDAY / Jarvis or external swarm adapters) are explicitly deferred until FORGE achieves mature standalone product readiness.
2. **Evidence Over Model Confidence**:
   - Software correctness is established through objective runtime verification (AST syntax verification, Ruff linting, Pytest execution, and Playwright browser checks), not LLM self-reporting.
3. **Workspace Sandbox Isolation**:
   - All code generation, process execution, and git operations are confined to `workspaces/task_<id>/`.
4. **Self-Healing Anti-Loop Controls**:
   - `RecoveryEngine` performs root-cause analysis, deduplicates patches using SHA256 hashes, and caps retries to 3 per failure class to prevent infinite repair loops.
5. **Durable Task Lifecycle & Parallel DAG Waves**:
   - Tasks progress through 8 formal lifecycle states (`PENDING`, `READY`, `RUNNING`, `BLOCKED`, `FAILED`, `VERIFYING`, `COMPLETED`, `CANCELLED`).
   - Independent DAG nodes run concurrently in parallel waves via `asyncio.gather`.
