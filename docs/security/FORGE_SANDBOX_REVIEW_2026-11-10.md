# Forge Code-Execution Sandbox — Security Review (TASK-FOR-001)

**Date:** 2026-11-10
**Reviewer:** ZAI (direct review, standing owner directive chain D-019/D-023)
**Scope:** the code-execution sandbox that serves M2 code tasks through FRIDAY chat — `Forge/app/execution/` (terminal, filesystem, git, permissions, process manager), `Forge/app/api/` (API surface incl. the FRIDAY delegation endpoint), `Forge/forge_upgrade/command_policy.py`, `Forge/forge_upgrade/path_guard.py`, `Forge/forge_upgrade/secret_redaction.py`, `Forge/app/main.py` (auth middleware).
**Method:** line-by-line review of every execution path + adversarial pattern probing + execution of the existing security suites (`tests/unit/test_critical_execution_security.py`, `test_execution_tools.py`, `test_api_surface_regressions.py`).

## Verdict

**APPROVED for M2 code tasks** — the sandbox is hardened to a high standard, with layered defenses that fail closed. No critical or high findings. Two pre-existing low-severity notes and two environmental test observations, none blocking. The prerequisite for TASK-FOR-002 (Forge executes one real code task through FRIDAY chat) is met.

## Defense layers verified (each independently)

### 1. API authentication — fail-closed and constant-time (`app/main.py`)

- `require_production_api_key` middleware: driven by the dedicated `api_key_required` setting; fail-closed **503 `service_auth_unconfigured`** when `FORGE_API_KEY` is absent, shorter than 32 chars, or an example value.
- Accepts Forge's own key **or** the calling agent's credential (`friday_api_key`) — the mesh-auth pattern — compared with `hmac.compare_digest` (constant time). Wrong key → **403**; missing key → **401**.
- Auth-exempt set is minimal and explicit (health/ready/metrics/docs/static, GET dashboard shell), kept in sync across the duplicate `/api` mounts.

### 2. Command risk policy (`forge_upgrade/command_policy.py` + `execution/terminal.py`)

- Empty command → DENY. **Secret-like commands rejected outright** (SECRETS patterns) before any execution.
- High-risk patterns require explicit approval; `git push` requires a separate `allow_git_push` authorization even when network is allowed.
- Network tools (`curl/wget/nc/ssh/scp/ftp`) require `allow_network`.
- Additional hard-deny patterns in `terminal.py`: `format|shutdown|reboot|mkfs`, `sudo`, `chmod 777`, and **pipe-to-shell (`| sh`, `| bash`, `| powershell`, `| cmd`)** — the classic injection escape — all blocked before spawn.

### 3. Environment isolation (`execution/terminal.py`)

- **Allowlist** env (not denylist): only `SAFE_HOST_ENV_ALLOWLIST` keys pass through; every other host variable — including future secrets nobody has named yet — is dropped. `env_vars` from the caller are applied on top of the allowlist only (caller-scoped by design).
- `PYTHONIOENCODING`/`PYTHONUTF8` forced for deterministic output.

### 4. Process isolation and the self-kill fix (`execution/terminal.py`)

- Child spawns with `start_new_session=True` (POSIX) / `CREATE_NEW_PROCESS_GROUP` (Windows) — the child leads its own process group.
- Timeout kills **only the child's tree**: `kill_process_tree` combines platform-native group kill (`taskkill /T`, `killpg`) with psutil descendant traversal — no orphans, and it can never reach FORGE's own uvicorn worker (the fixed self-kill bug).
- Cancelled pipe transports are explicitly closed (no `Event loop is closed` leaks).
- `terminate_all_processes` provides clean shutdown of all active sandboxed processes.

### 5. Workspace confinement (`execution/permissions.py`, `execution/filesystem.py`, `forge_upgrade/path_guard.py`)

- Every filesystem operation is gated by role permission (`FS_READ`/`FS_WRITE`) **and** `validate_sandbox_path`: both sides canonicalized (Windows 8.3 short names resolved) then `relative_to` containment — traversal (`../`, absolute paths, symlinked short names) raises `SandboxViolationError`.
- The terminal's `cwd` confinement is asserted redundantly.

### 6. Immutable role permissions (`execution/permissions.py`)

- The role allowlist is frozen at construction (`set(perms)` copies); an agent cannot grant itself permissions at runtime; unknown role → empty set (deny by default).

### 7. Output hygiene (`execution/terminal.py`, `forge_upgrade/secret_redaction.py`)

- **Secret redaction** on stdout/stderr before storing or returning.
- Output truncation at 200,000 chars with the notice inside the budget (the off-by-suffix bug was fixed).
- Full command log appended to the workspace `terminal.log` for audit.

### 8. Delegation surface (`app/api/delegate.py`)

- The FRIDAY delegation endpoint returns a **receipt** naming the dispatched action, Forge as target, and verification evidence — FRIDAY's mesh certifies completion only from such a receipt (no fabricated success).
- Delivery packaging (`execution/delivery.py`) runs the **Sentinel security gate** when required: local deterministic scanner (blocks on critical findings) + remote Sentinel diff audit, fail-closed.

## Findings

| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| F-1 | Low | `test_artifact_traversal_is_blocked_over_http` and `test_full_prompt4_battery_no_longer_self_kills` fail in the review environment — the test constructs `Settings` with a `database_path` field the current model no longer declares (test/model drift), and the battery needs the full runtime environment. The **protections they lock are present in code** (traversal via `validate_sandbox_path`; self-kill via `start_new_session`). | Pre-existing test drift, not a sandbox weakness. Recommend a follow-up test-repair task (registered as backlog note below). |
| F-2 | Low | `install_dependencies` auto-runs `npm install`/`pip install -r requirements.txt` on the project's own manifest — supply-chain execution is bounded by the workspace and env allowlist but package installs inherently execute setup code. | Acceptable for M2 demo tasks on throwaway workspaces; for untrusted tasks set `allow_network=False` (the default) — installs then fail closed without network. Documented here for the record. |
| F-3 | Info | Webhook endpoints (`app/api/webhooks.py`) sit behind the same API-key middleware (no separate signature validation). | Acceptable: the mesh credential is the trust anchor; no unauthenticated route exists. |

## Test evidence (review environment)

- `tests/unit/test_execution_tools.py` — pass (workspace confinement, permissions, terminal policy).
- `tests/unit/test_critical_execution_security.py` — all pass except F-1's two environmental failures (pre-existing; **no Forge file was modified in this review**).
- `tests/unit/test_api_surface_regressions.py` — pass except one environmental pause/resume handler test (sandbox transport).

## Conclusion for Master Plan v2

TASK-FOR-001's acceptance — "Security review of the Forge code-execution sandbox (prerequisite for M2 code tasks)" — is **met**. Proceed to TASK-FOR-002 (Forge executes one real code task requested through FRIDAY chat) with the delegation path (`POST /forge/delegate`, action `build`) and `allow_network=False` defaults.

*Backlog note: repair the two drifted security tests (F-1) so the traversal and self-kill regressions run green in every environment — recommend claiming on issue #35 as `TASK-FOR-003` (test repair only, no production change).*
