# Project FORGE — Autonomous Self-Improvement & Delivery Reference

Project FORGE incorporates autonomous self-improvement, continuous template evolution, pipeline optimizations, and flexible delivery automation while remaining a pure, consumer-agnostic engineering engine.

---

## 1. Self-Improvement Engine (`app/improvement/`)

FORGE monitors its historical execution telemetry to detect failure clusters, discover recurring defects, and formulate actionable improvement proposals.

### Failure Pattern Analysis (Rolling 7-Day Window)
Failed tasks are clustered into distinct categories:
- **`missing_dependencies`**: Missing package imports or unsatisfied dependencies.
- **`syntax_errors`**: AST syntax and indentation regressions.
- **`verification_failures`**: Unit/integration test assertion failures.
- **`fallback_stub_issues`**: Low-confidence synthesis fallback detections.
- **`security_violations`**: Forbidden patterns (`eval()`, hardcoded secrets).

### Safety Governance Rule
> [!IMPORTANT]
> All self-improvement actions are strictly generated as **proposals**. No self-modifying code changes are automatically executed without human/admin approval:
> - `GET /api/improvement/report` — View active analysis and proposals.
> - `POST /api/improvement/apply/{proposal_id}` — Human-approved proposal execution.

---

## 2. Continuous Template Evolution (`app/improvement/template_evolution.py`)

- **Template Mining**: Tracks the verification success rates of various code patterns (e.g. CSS Grid vs. Flexbox, SQLite vs. in-memory CRUD).
- **A/B Testing**: When requirements allow multiple valid architectures, candidate variants are evaluated and the winning pattern is promoted based on pass rate and historical reliability.

---

## 3. Build Pipeline Optimization (`app/core/pipeline_optimizer.py`)

- **Parallel File Synthesis**: Synthesizes independent project files concurrently using semaphore throttling.
- **Synthesis & Verification Caching**: In-memory LRU cache with TTL for identical prompts and unchanged file verifications.
- **Incremental Builds**: Compares file manifests against previous iterations to regenerate only modified assets.
- **Pre-Synthesis Cost Estimation**: Predicts required AI-Universe queries and token expenditure prior to task execution.

---

## 4. Multi-Project Management & Workspace Retention (`app/core/multi_project.py`)

- **Priority Queue**: `urgent` > `high` > `normal`.
- **Preemption**: Urgent tasks preempt normal tasks after safe checkpointing.
- **Workspace Lifecycle Retention**:
  - Completed builds are retained for 7 days before archiving.
  - Failed sandboxes are purged after 24 hours.

---

## 5. Automated GitHub Delivery (`app/integrations/github_delivery.py`)

On completion, FORGE can optionally deliver software to GitHub:
- Auto-creates a remote repository (`forge-{task_id}`).
- Synchronizes sandbox assets to the default branch.
- Publishes tagged releases with release notes.

---

## 6. Web Dashboard (`app/dashboard/`)

An interactive dashboard is served at `http://localhost:8000/dashboard`:
- Live 8-stage progress tracker and playback.
- Auto-scrolling live log viewer.
- Verification results breakdown.
- Deliverable artifacts download list.

---

## 7. Automated Documentation Generator (`app/delivery/docs_generator.py`)

- Generates clean, production-grade `README.md` files including overview, requirements, architecture, CLI/API usage guides, and testing instructions.
- Evaluates codebase comment quality and density.
