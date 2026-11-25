# TASK-CTX-008 — Budget gate into production: repo-side evidence

**Task:** Cortex: wire the per-agent budget gate into production (caller, durable
store, breach alerts). **Worker:** Muse 10. **Claim:** hub #1483 comment
7149146388, 2026-11-25 ~06:35 IST, per coordinator watch 7148827655.
**Branch:** `muse10/task-ctx-008-budget-gate`, base main `33625090`.
**Work PR:** (number filled on open).

All code findings below were verified first-hand on main `33625090` (local
clone, board 22,327 lines).

## Repo-side findings

### F1 — Caller leg: the envelope executor is the dispatch path, and it charges
- `Cortex/apps/api/src/cortex_api/friday_router.py` (~line 930):
  `process_task_envelope` calls `agent_budget_ledger.record_usage("Cortex",
  tokens=0, tasks=1)` for every non-exempt, non-dry-run envelope and raises
  HTTP 429 on breach. The code comment states the engines are deterministic
  governed operations, so `tokens=0` on this path is deliberate; token usage
  is reported through `POST /api/v1/cortex/budgets/usage`.
- Pinned by `Cortex/tests/unit/test_ig2_cor_agent_budgets_wiring.py`
  (gap-1 tests: charge, 429 deny, CRITICAL override, exemptions).

### F2 — Token reporting: the surface exists, is mounted, and had no caller
- `POST /api/v1/cortex/budgets/usage` exists in
  `Cortex/apps/api/src/cortex_api/agent_budgets.py` (router, `UsageRequest`:
  agent/tokens/tasks/critical) and is mounted in `main.py:311` behind
  `require_cortex_route_access`.
- Repo-wide grep: **no production code anywhere calls that endpoint** (only
  the module itself, `friday_router.py`'s comment, and tests).
- Cortex has **no LLM-backed caller to wire**: `cognitive_planner.py` and
  `competitive_intelligence.py` contain zero references to httpx/requests/
  llm/Inference/OpenAI/Gemini — they are deterministic heuristics (consistent
  with the repo AGENTS.md caveats). There is nothing in-repo that produces
  tokens to report, so the token leg cannot be wired from an in-repo caller.
- **New test (this PR):**
  `test_router_post_usage_reports_tokens_and_enforces_token_budget` in
  `Cortex/tests/unit/test_ig2_cor_agent_budgets.py` proves the seam through
  the mounted router: POST 600 tokens → 200 with `tokens_used` 600 /
  `tokens_remaining` 400; POST 500 more → 429 (token budget 1,000);
  GET snapshot shows `tokens_used` 600 and `paused` true; exactly one
  `Cortex` alert recorded. Local run: **42 passed (41 baseline + 1 new),
  0.84s**, venv with the Cortex API requirements.

### F3 — Durable store: DB default is code, pinned by tests
- `_build_production_ledger()` (`agent_budgets.py`) defaults to
  `DatabaseBudgetStore` (PR #770); `CORTEX_AGENT_BUDGET_STORE=memory` is the
  escape hatch. COR-012 NullPool fix keeps saves off the wrong loop.
- Pinned by `test_ig2_cor_agent_budgets_wiring.py` gap-2 tests (DB round-trip
  + restart restore) and `test_ig2_cor_agent_budgets_production_default.py`.

### F4 — Breach alerts: webhook sink, exactly-one pinned
- `WebhookBreachAlertSink` posts to `SELF_HEALING_ESCALATION_WEBHOOK`
  (Telegram sendMessage URLs translated via
  `cortex_core.resilience.telegram_delivery_payload`; channel redacted in
  persisted records). Pinned by the wiring gap-3 tests (exactly one alert,
  sink failure never breaks the gate, live HTTP capture test).

## Live legs — gated, not yet proven
- **G-live-1:** live Cortex actually running the PR #770 / COR-012 code:
  `GET /api/v1/cortex/budgets` must show `store: {backend: database,
  durable: true}` on the running service (Cortex 8009, server 2).
- **G-live-2:** `SELF_HEALING_ESCALATION_WEBHOOK` configured on live Cortex
  and resolving to Telegram via Sentinel (the owner channel).
- **G-live-3:** usage survives a real Cortex restart; a real dispatch is
  budget-checked and a forced breach produces exactly one owner alert.
- All three need live access and are **gated on the owner stop order
  (~16:42 IST 2026-11-24, still in force per the latest coordinator watch
  7149764574, which carries no lift)** and Muse's clearance. No live move
  was made in this PR. Clearance requested on hub #1483 (see checkpoint 1).

## Status
- implemented: YES (repo-side: token-reporting seam test; no code change was
  needed — the wiring already exists) / tested: YES (42/42 local, see above)
  / merged: NO / deployed: NO / production-verified: NO (live legs gated)

— Muse 10
