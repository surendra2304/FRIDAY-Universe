# MASTER PROMPT — "Deep Engine Autonomy" for FRIDAY Universe

> **How to use:** open your local `FRIDAY-Universe` folder in Antigravity (or any local coding agent), paste **everything below the line** into the agent chat, and let it run. It is written to be executed top-to-bottom without asking you questions. It assumes the agent has shell access and can run `git`, `python`, `pytest`.

---

You are a senior Python engineer working **inside my local clone of the FRIDAY Universe monorepo**. Your job is not to write new demo code — it is to make **seven already-implemented deep engines actually run inside the agents that own them**, autonomously, on the real request paths, and to prove it with tests.

Work continuously. Do not ask me for confirmation at each step. Do not stop until every item in the **Definition of Done** (§9) is satisfied and you have committed + pushed. If something is genuinely blocked (missing credentials, missing GPU), skip that single item, mark it in the report, and continue with the rest.

---

## 0. GROUND TRUTH — what already exists (do not rebuild it)

Seven open-source repositories were adapted (not vendored) into this repo. **The engines are done and tested.** They are:

| # | Upstream repo (concept) | Agent | Engine module (already written) | Adapter / service layer | Layer test |
|---|---|---|---|---|---|
| 1 | `browser-use/browser-use` | **FRIDAY** | `FRIDAY/apps/core/src/friday_core/real_browser_agent.py` | `.../friday_core/agent_runtime.py` | `tests/test_real_deep_layer4.py` |
| 2 | `tigerless-labs/agent-memory` | **Memora** | `Memora/core/memory/real_agent_memory.py` | `Memora/core/memory/context_service.py` | `tests/test_real_deep_layer5.py` |
| 3 | `K-Dense-AI/scientific-agent-skills` | **Inference** | `Inference/app/agents/real_scientific_skills.py` | `Inference/app/scientific_service.py` | `tests/test_real_deep_layer6.py` |
| 4 | `cathrynlavery/diagram-design` | **VyralX** | `VyralX/app/agents/real_diagram_design.py` | `VyralX/app/services/diagram_service.py` | `tests/test_real_deep_layer7.py` |
| 5 | `mukul975/Anthropic-Cybersecurity-Skills` | **Sentinel** | `Sentinel/app/services/real_cyber_skills.py` | `Sentinel/app/services/cyber_skills_service.py` | `tests/test_real_deep_layer8.py` |
| 6 | `ai-boost/awesome-harness-engineering` | **FRIDAY** | `FRIDAY/apps/core/src/friday_core/real_harness_engineering.py` | `.../friday_core/agent_runtime.py` | `tests/test_real_deep_layer9.py` |
| 7 | `volcengine/OpenViking` | **Memora** | `Memora/core/memory/real_viking_context.py` | `Memora/core/memory/context_service.py` + `mesh/memory_fabric.py` | `tests/test_real_deep_layer10.py` |

Cross-repo wiring proof: `tests/test_real_deep_layer11.py` (72 tests). Design report: `docs/DEEP_ENGINE_INTEGRATION_REPORT.md`.

**Hard rule:** do **not** rewrite these 12 files from scratch. They are 1 200–2 100 lines each, typed with `@dataclass`, `from __future__ import annotations`, and stdlib-only. You may fix a genuine bug in them, but if you touch one you must keep its layer test green.

---

## 1. PHASE 0 — SYNC FROM GITHUB FIRST (mandatory, do this before anything else)

```bash
cd <path-to-my-FRIDAY-Universe>          # e.g. ~/FRIDAY-Universe
git remote -v                             # must show github.com/surendra2304/FRIDAY-Universe
git status                                # if dirty: `git stash push -u -m "pre-sync"` and keep the stash
git fetch --all --prune
git checkout arena/6cf0a8a9-friday-universe
git pull --ff-only origin arena/6cf0a8a9-friday-universe
```

The latest work lives on **`arena/6cf0a8a9-friday-universe`**, *not* on `main`. Verify you have it:

```bash
git log --oneline -3
# MUST include:  ef67a0f docs: report the seven deep engines, their agents and their live wiring
#               9f31807 feat(universe): wire the seven deep engines into the running agents
ls docs/DEEP_ENGINE_INTEGRATION_REPORT.md tests/test_real_deep_layer11.py \
   FRIDAY/apps/core/src/friday_core/agent_runtime.py \
   Memora/core/memory/context_service.py
```

If any of those files are missing, the pull did not work — stop and report exactly which command failed. Do **not** continue on a stale tree and do **not** merge into `main`.

Then create your working branch:

```bash
git checkout -b feat/deep-engine-autonomy
```

Every commit you make goes on `feat/deep-engine-autonomy`, pushed with `git push -u origin feat/deep-engine-autonomy`. At the end, open a PR **into `arena/6cf0a8a9-friday-universe`** (never into `main`).

---

## 2. PHASE 1 — RECONNAISSANCE (read before you write)

Do not skip. You are about to modify live agent code; you must know the shape of it first.

1. `AGENTS.yaml` — single source of truth: 9 agents, ports, domain, engine list.
2. `AGENTS.md` — per-agent docs; the "live wiring" bullets tell you what is already connected.
3. `docs/DEEP_ENGINE_INTEGRATION_REPORT.md` — what was wired and where.
4. `tests/test_real_deep_layer11.py` — **the contract**. Every assertion there is behaviour that must keep working.
5. `FRIDAY/apps/core/src/friday_core/universe_orchestrator.py` — `run_full_security_workflow`, `run_full_trading_workflow`, `run_full_intel_workflow`, `run_full_content_workflow`, `run_deep_*`, `run_web_task`, `run_guarded_task`.
6. `FRIDAY/apps/core/src/friday_core/agent_runtime.py` — `FridayAgentRuntime` (`plan / execute / verify / compact / browse / recall_context / commit_memory / capabilities`).
7. `mesh/registry.py`, `mesh/memory_fabric.py`, `mesh/adaptive_router.py`.
8. The four agent entrypoints you will touch: `Inference/app/main.py`, `Memora/apps/api/main.py`, `VyralX/app/main.py`, `Sentinel/sentinel/apps/api/main.py`.
9. `tests/conftest.py` — `sys.path` bootstrap. Read it before writing any test.

Then write a 10-line inventory into your working notes: for each of the 5 touched agents, list (a) the FastAPI app object, (b) the request handlers that will call each engine, (c) which orchestrator workflow steps already invoke it, (d) what is still *not* invoked from a live path. You will fix (d).

### Port map (use it; it is real)

`FRIDAY 8000` (`friday_core.real_api_server`) · deep API `8011` (`friday_core.real_deep_api_server`, **do not use 8010 — VyralX owns it**) · `Inference 8001` · `Memora 8002` · `Stratex 8003` · `Futuris 8004` · `IntelX 8005` · `Forge 8006` · `Sentinel 8008` · `Cortex 8009` · `VyralX 8010`.

---

## 3. PHASE 2 — ESTABLISH THE BASELINE (before changing a line)

```bash
python3 --version        # 3.11.x expected
python3 -m venv .venv && source .venv/bin/activate      # prefer venv; if PEP 668 blocks a system install, use --break-system-packages
pip install -q -r requirements.txt 2>/dev/null || true
pip install -q pytest fastapi uvicorn pydantic pydantic-settings httpx \
               sqlalchemy aiosqlite greenlet jinja2 aiofiles sse-starlette google-auth pyyaml

python3 -m pytest tests/test_real_deep_layer4.py  tests/test_real_deep_layer5.py \
                  tests/test_real_deep_layer6.py  tests/test_real_deep_layer7.py \
                  tests/test_real_deep_layer8.py  tests/test_real_deep_layer9.py \
                  tests/test_real_deep_layer10.py tests/test_real_deep_layer11.py \
                  tests/test_proven_vertical_slice.py -q
```

Expected baseline on the synced commit: **558 passed** (layers 4–11: 44/60/81/66/71/94/70/72) plus **5 passed** for the vertical slice.

Two suites fail **before you touch anything** — record them as pre-existing and never "fix" them by weakening code:

- `tests/test_fleet_validation.py` → 2 failures (mirror-workflow rules).
- `tests/test_ultimate_integration.py` → 7 failures (`UniverseWorkflowEngine.run_security_scan()` marks steps `failed`; reproduces standalone).

Write the baseline numbers into `docs/DEEP_ENGINE_AUTONOMY_REPORT.md` under "Baseline". If your baseline differs, stop and report — you are on the wrong commit.

---

## 4. PHASE 3 — THE AUTONOMY CONTRACT (what "actually used" means)

For **each** engine, all five of these must be true. Anything less is "code sitting next to the agent", which is the exact failure mode I am asking you to eliminate.

1. **In-process call** — the owning agent's real service/handler code calls the engine, on the normal request path (not a separate script).
2. **HTTP surface** — an endpoint on the agent's own FastAPI app exposes it (prefixes below).
3. **Orchestrator step** — a named step inside a `run_full_*_workflow` produces output from it that later steps consume.
4. **Mesh routing** — `mesh/registry.py` routes the capability and the intent to that agent, so the dispatch bus reaches it without hard-coding.
5. **Proof** — a test in `tests/` asserts 1–4 (layer tests for 1, layer 11 for 2–4).

And for the fleet to be *autonomous* rather than merely *callable*, every inbound unit of work must run this loop **without human clicks**:

```
recall context  →  plan  →  select skills/diagrams/detections  →  execute (permission-gated)
        →  verify against checks  →  commit memory  →  emit trace
```

with automatic fallback when an engine is unavailable (degrade to the pre-existing path, never 500) and bounded token/step budgets. §6 tells you exactly where each piece lands.

---

## 5. PHASE 4 — PER-AGENT IMPLEMENTATION WORK

Do one agent at a time. After each: run that agent's layer test + `tests/test_real_deep_layer11.py`, commit, push, move on. Keep commits small and descriptive.

### 5.1 FRIDAY — harness + browser (repos 1 and 6)

Files: `FRIDAY/apps/core/src/friday_core/agent_runtime.py`, `universe_orchestrator.py`, `real_deep_api_server.py`, `universe_dispatch_bus.py`, `universe_task_router.py`.

Already done: `/v1/agent/{capabilities,plan,execute,context/compact,browser/run,trace}`; `harness_verification` + `cyber_skill_triage` + `explainer_diagram` steps in the security and content workflows.

Your work:
1. **Make the harness the default executor.** Any orchestrator workflow that runs steps should go through `FridayAgentRuntime.execute()` with a permission policy and `Check` predicates — today only part of the flows do. Extend `run_full_trading_workflow` and `run_full_intel_workflow` so each ends with a harness verification step (`passed`, `checks`, `weight`) and a memory commit.
2. **Memory-first task entry.** Every public entrypoint of the orchestrator must call `runtime.recall_context(goal)` first and put the hits into `result["recalled_context"]` (it must be present, `[]` when empty — an assertion in layer 11 relies on this).
3. **Approvals end-to-end.** Wire `_ApprovalLog` to a real HTTP route (`POST /v1/agent/approvals/{request_id}`) so a denied tool step can be approved by an operator and resumed; the pending list must appear in `/v1/agent/trace`.
4. **Browser agent usage.** When a task step requires the web and no URL content is supplied, the runtime must call `browse(...)` rather than failing. Add a step kind `browser` and cover it with a test.
5. **Dispatch.** `universe_dispatch_bus` / `universe_task_router` must resolve `browser_automation`, `agent_harness`, `tool_permissions` to FRIDAY through the registry, not by `if agent == "FRIDAY"`.
6. **Do not** change `ROOT = parents[5]` in `agent_runtime.py` (memory bridge depends on it).

### 5.2 Memora — memory + viking context (repos 2 and 7)

Files: `Memora/core/memory/context_service.py`, `Memora/apps/api/routers/context_db.py`, `Memora/apps/api/main.py`, `mesh/memory_fabric.py`.

Already done: `/v1/context/{stats,search,ls,tree,read,write,commit,wiki}`; `FabricBridge(service).save/recall/summary`; `context_bridge()`, `record_context()`, `recall_layered()`, `context_tree()`.

Your work:
1. **Single persistence path.** Every agent's memory write today may take several routes (local JSON, sqlite, fabric). Route them all through the bridge; a write from any agent must be visible in `GET /v1/context/tree` and in a scoped `search`.
2. **Layered recall in the hot path.** `recall_layered(q, level)` must be used by the orchestrator's recall step and by FRIDAY's runtime — L0 index → L1 summary → L2 full text, escalating only when the answer isn't found. Assert escalation happens in a test.
3. **Session lifecycle.** Start a session on request, commit it on completion (`commit_session` → archive + memory extraction), and on process shutdown. The wiki compile (`compile_wiki`) should be runnable from a cron-like background loop.
4. **Consolidation.** Schedule the sleep-time consolidation pass (authority-tier merge) behind a background task that runs on an interval, is idempotent, and never blocks requests.

### 5.3 Inference — scientific skills (repo 3)

Files: `Inference/app/scientific_service.py`, `Inference/app/api/agent_routes.py`, `Inference/app/agents/router.py`, `Inference/app/main.py`.

Already done: `/v1/scientific/{capabilities,plan,power,audit}` and `POST /v1/agent/research-plan`.

Your work:
1. **Task router consults the skill matcher.** Inspect the module-level `router` instance in `Inference/app/agents/router.py` (`TaskRouter`) and make task classification consider `SkillMatcher` output, with a lazy import so an import failure cannot break the app. Add a test that a scientific task is routed to a skill-backed handler.
2. **Evidence discipline.** Any answer produced by Inference that cites literature must pass the evidence audit (`audit()`); expose the verdict in the response and make a failing audit a soft failure with a `warnings` field, not a 500.
3. **Orchestrator research step** must use `plan()` + `analyse()`, and its output must feed the content workflow (VyralX) — that is the cross-agent link.
4. **Statistical power** must be computed from the actual sample size in the request when present.

### 5.4 VyralX — diagram design (repo 4)

Files: `VyralX/app/services/diagram_service.py`, `VyralX/app/services/content.py`, `VyralX/app/main.py`.

Already done: `/api/v1/diagrams/{catalogue,choose,palette,flowchart,from-brief,from-mermaid,restyle}`; `attach_explainer()` in the content pipeline.

Your work:
1. **Every content pack carries a diagram.** Verify `attach_explainer()` runs on all content-generation entrypoints (posts, threads, explainers, newsletters) — not just the one path it was added to. A pack without a valid `html`/`svg` (≥3 nodes, >500 bytes) must be a hard test failure.
2. **Brand palette from config, not constants.** Pull colours from the repo's brand config; fall back to the engine's palette.
3. **Import path.** `from-mermaid` and `from-brief` must both produce re-renderable specs; a round-trip (mermaid → spec → svg) must be asserted.
4. **Restyle** must preserve node/edge identity (same ids, same count) — test it.

### 5.5 Sentinel — cybersecurity skills (repo 5)

Files: `Sentinel/app/services/cyber_skills_service.py`, `Sentinel/sentinel/apps/api/incident_routes.py`, `Sentinel/app/services/security_posture_assessor.py`, `Sentinel/sentinel/apps/api/main.py`.

Already done: `/v1/cyber/*`; ATT&CK crosswalk on incidents; `nist_csf` in the posture report; `cyber_skill_triage` orchestrator step.

Your work:
1. **Triage on creation.** Every new incident must be auto-triaged (ATT&CK mapping + severity + ordered playbook steps) and persist the playbook, so a responder reads it without calling an endpoint.
2. **Detection coverage** must be computed against the current detection rules and surfaced in the posture report next to CSF maturity — and refreshed on a schedule.
3. **CSF everywhere.** All compliance/audit output paths use `assess_csf()`; route rates through `_maturity()` (raw values may be 0–1 *or* 0–100).
4. **Guarded actions.** Destructive response actions (isolate host, block IP) must pass `authorise()` before execution and be recorded.
5. **Env:** the app requires `SENTINEL_AUDIT_SIGNING_KEY` (≥16 chars) to import. Everything you run must set it, including tests.

### 5.6 Mesh / fleet metadata (all agents)

- `mesh/registry.py`: capabilities + intents for all five agents; `discover_by_capability` / `discover_by_intent` must return the agent *and* its service object.
- `AGENTS.yaml`: engine lists already extended — add any new capability names you introduce, and keep `AGENTS.md` in sync. Drift should be caught by a test; extend `tests/test_agent_manifest_validation.py` if a new field appears.
- `mesh/memory_fabric.py`: no agent may bypass it for memory writes.

---

## 6. PHASE 5 — MAKE IT AUTONOMOUS (not just callable)

This is the part that turns wiring into a living system. Implement, minimally and testably:

1. **Uniform task envelope** — one helper (e.g. `friday_core/agent_runtime.py::run_autonomous_envelope`) used by every agent handler: recall → plan → skill/diagram/detection selection → gated execution → verification → memory commit → trace. One code path, five agents.
2. **Background loops** (asyncio tasks started in the app's lifespan, guarded by env flags, no blocking I/O on the request path):
   - Memora: consolidation + wiki compile interval.
   - Sentinel: detection-coverage / CSF refresh interval.
   - VyralX: content packs that failed diagram validation get retried.
   - FRIDAY: trace compaction + checkpoint pruning.
   Every loop must be **idempotent**, log its run, and be disable-able via env var (`FRIDAY_BACKGROUND_TASKS=0`).
3. **Graceful degradation** — if an engine import or call fails, log a warning and fall back to the pre-existing behaviour. No agent may 500 because a deep engine is missing. Add one test per agent that forces the failure and asserts a 200 with a warning.
4. **Budgets & guards** — max steps, max tokens, wall-clock timeout on the harness loop; the values must be configurable and enforced (assert a runaway task stops with `stop_reason="max_steps"`).
5. **Observability** — every autonomous run emits a trace id, and `/v1/agent/trace` (or the agent's equivalent) can fetch it. A single structured log line per run: `agent`, `task`, `steps`, `engine_calls`, `verified`, `memory_committed`, `duration_ms`.

---

## 7. PHASE 6 — THE SINGLE VERIFICATION GATE

Create `scripts/verify_deep_wiring.py` (stdlib + fastapi TestClient; no network):

- Boots each agent app **in its own subprocess** with its own `cwd` and `sys.path` (see traps in §10) and hits: `/v1/agent/capabilities`, `/v1/context/stats`, `/v1/context/search`, `/v1/scientific/capabilities`, `/v1/scientific/plan`, `/api/v1/diagrams/catalogue`, `/api/v1/diagrams/flowchart`, `/v1/cyber/capabilities`, `/v1/cyber/triage`.
- Asserts non-empty, structurally valid payloads (not just `200`): e.g. flowchart `validation.valid is True`, `nodes >= 3`, `len(svg) > 500`; triage returns `severity` and `playbook_steps`; `/v1/context/search` returns ranked hits with scores.
- Runs the cross-agent flow: Sentinel triage → Memora `commit_session` → FRIDAY `recall_context` → `execute` with a `Check` → `verification.passed` → `commit_memory().committed`.
- Prints a green/red table and exits non-zero on any failure.

Then run the full gate:

```bash
python3 scripts/verify_deep_wiring.py
python3 -m pytest tests/test_real_deep_layer4.py  tests/test_real_deep_layer5.py \
                  tests/test_real_deep_layer6.py  tests/test_real_deep_layer7.py \
                  tests/test_real_deep_layer8.py  tests/test_real_deep_layer9.py \
                  tests/test_real_deep_layer10.py tests/test_real_deep_layer11.py \
                  tests/test_proven_vertical_slice.py tests/test_agent_manifest_validation.py -q
git checkout -- .        # running the suite mutates .data/*.json; never commit that churn
```

---

## 8. ENGINEERING RULES (non-negotiable)

- **Adapt, don't clone.** No vendored upstream code, no new third-party libraries for the engines — stdlib only. New *app-level* deps are only allowed if genuinely required and must go into `requirements.txt` with a pinned version.
- **Style match:** `from __future__ import annotations`, `@dataclass` typed fields, small pure methods, docstrings that state the contract, no `print()` in library code, no `TODO`/`pass`/placeholder bodies.
- **No stubs, no mocks in shipped code.** Tests may use in-memory filesystems, never mocks of the engine under test.
- **Don't break behaviour.** Layers 4–11, `test_proven_vertical_slice.py`, `test_agent_manifest_validation.py` must stay green. The only allowed failures are the pre-existing ones in §3.
- **Don't touch** `.data/*.json`, generated `__pycache__`, or any secret. Never commit a key.
- **Commit protocol:** one commit per agent/wave, imperative subject `feat(<agent>): …`, body explaining *which live path now calls which engine*, footer referencing the upstream concept. Push each commit. Never force-push. Never merge to `main`.
- **Language:** British/neutral English, no marketing language in code or docs.

---

## 9. DEFINITION OF DONE

Satisfy every row; tick them in the report.

| # | Requirement | Evidence that proves it |
|---|---|---|
| 1 | All 7 engines are invoked from a live request path of their owning agent | a section per agent in the report naming file + function + line |
| 2 | All 5 new HTTP surfaces respond with real payloads | `scripts/verify_deep_wiring.py` green |
| 3 | Orchestrator workflows contain engine-produced steps that later steps consume | assertions on `workflow.steps[*]` names + fields |
| 4 | Mesh routes capability **and** intent to the right agent | `discover_by_capability` / `discover_by_intent` tests |
| 5 | Cross-agent flow (Sentinel → Memora → FRIDAY) passes end to end | dedicated test |
| 6 | Autonomous background loops exist, are idempotent, and are env-disable-able | interval test with a fake clock, or two consecutive runs producing identical state |
| 7 | Graceful degradation: engine failure ⇒ 200 + warning, never 500 | one test per agent |
| 8 | Budgets enforced (`max_steps`, tokens, timeout) | runaway-task test |
| 9 | 558+ tests still green; new tests added for every wiring point | final pytest output pasted into the report |
| 10 | Docs updated: `AGENTS.md`, `AGENTS.yaml`, `docs/DEEP_ENGINE_AUTONOMY_REPORT.md` | files in the commit |
| 11 | Everything committed and pushed on `feat/deep-engine-autonomy` | `git log --oneline origin/feat/deep-engine-autonomy` |
| 12 | PR opened into `arena/6cf0a8a9-friday-universe` with the report as description | `gh pr create` output with the URL |

Final report `docs/DEEP_ENGINE_AUTONOMY_REPORT.md` must contain: baseline vs final test counts, the per-repo table (source repo → agent → engine file → live call path → endpoint → workflow step → tests), the autonomy loops you added, the known pre-existing failures, and the commit hashes.

---

## 10. TRAPS — read this before you waste an hour

These are real, already hit in this codebase:

1. **`sys.path` collision.** `Sentinel/sentinel/logging/` shadows stdlib `logging`. **Never import two agents' packages into one Python process.** `cd` into a single agent directory (or use a subprocess) per app boot. In tests, load non-`friday_core` modules with `importlib.util.spec_from_file_location`; `friday_core` is fine via `importlib.import_module`.
2. **`agent_runtime.py` uses `ROOT = parents[5]`** to reach the repo root. Changing it to `parents[6]` silently disables the memory bridge (returns `None`).
3. **`FabricBridge.recall(agent, query)`** — argument order is `(agent, query)`, not `(query, agent)`.
4. **`SkillRecommender.recommend()` returns dicts** (`{"skill","name","tier","score","reasons"}`), not objects — use `match["skill"]`.
5. **`SecurityPostureAssessor`** compliance rates can be 0–1 *or* 0–100; always route through `_maturity()`.
6. **Diagram selector returns `{"type": ...}`** — there is no key `type_id`, and `DiagramDesignEngine` has **no** `.create()`; use the service layer (`DiagramService.flowchart / choose / from_brief`).
7. **`Inference/app/scientific_service.py` must stay at `app/` level** — under `app/services/` it is not importable.
8. **`SENTINEL_AUDIT_SIGNING_KEY`** (≥16 chars) is required for the Sentinel app to import at all.
9. **Running the whole `pytest tests` directory rewrites `.data/*.json`.** Run targeted files, then `git checkout -- .` before committing. Never commit data churn.
10. **`MemoraContextService.gaps()`** legitimately returns `[]` for arbitrary phrases — don't assert non-empty.
11. **Harness `Check` predicates run against the observation text.** For `count_tokens("hello world")` the artifact contains `4`, not `2`.
12. **`mesh/adaptive_router.py` and `universe_prod_server.py` import fastapi** at module import time — don't add them to stdlib-only test paths.
13. **PEP 668:** `pip install` may require `--break-system-packages`; prefer a venv.
14. **VyralX owns port 8010.** The FRIDAY deep API server is not assigned a port in this repo — use **8011**.

---

## 11. EXECUTION ORDER (do not reorder)

1. Phase 0 sync → verify hashes.
2. Phase 1 recon → inventory note.
3. Phase 2 baseline → record 558 + 5, note the 2 known-failing suites.
4. FRIDAY → test → commit → push.
5. Memora → test → commit → push.
6. Inference → test → commit → push.
7. VyralX → test → commit → push.
8. Sentinel → test → commit → push.
9. Mesh + `AGENTS.yaml`/`AGENTS.md` → test → commit → push.
10. `scripts/verify_deep_wiring.py` + autonomy loops + degradation tests → commit → push.
11. Full gate run → fix regressions.
12. Write `docs/DEEP_ENGINE_AUTONOMY_REPORT.md` → commit → push → `gh pr create --base arena/6cf0a8a9-friday-universe --head feat/deep-engine-autonomy --title "feat: deep engine autonomy across FRIDAY, Memora, Inference, VyralX, Sentinel" --body-file docs/DEEP_ENGINE_AUTONOMY_REPORT.md`.

**Report to me at the end with:** what you pulled (commit hashes), the DoD table with ticks, the final test counts, the PR link, and the honest list of anything you could not complete and why.

Start with Phase 0 now.
