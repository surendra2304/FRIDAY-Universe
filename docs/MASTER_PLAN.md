# FRIDAY Universe: Master Plan v2 (Claude)

Replaces v1. v1 was written before most of the code was read and is superseded.

## How to read this plan
- VERIFIED: checked in source, git history, CI logs, or on the live servers during this review.
- OBSERVED: seen in one place (a log line, a config value, a grep count) but not traced end to end.
- GAP: not yet read. Nothing in this plan should be implemented in a GAP area until it is read.
- No secret values appear here. Secret names only.

## Coverage of this review
- Repository: 5,288 tracked files, about 1.1 million lines of Python.
- Read in full: the sniper workflows and retry script, the deploy, mirror and validation workflows, AGENTS.yaml, the two open PRs, CI logs for the failing PRs.
- Read in part, with targeted searches: the FRIDAY orchestrator (server.py command router, fleet_client, universe_orchestrator, dispatch bus), Stratex's exchange selection, the Caddy routes, systemd unit definitions on both servers.
- Not read yet (GAP): the bodies of the Inference, Memora, Futuris, IntelX, Forge, Cortex, Sentinel and VyralX agents; FRIDAY's 3,089-line server.py beyond routing; the tests (89 files at top level plus per-agent suites); database schemas; Server 2 unit bodies beyond ExecStart; the mesh and inter-agent auth code.
- The plan is therefore complete for infrastructure, deploy, routing and safety. It is not yet complete for the per-agent internals. Phase 1 closes that gap.

## 0. Security actions (Surendra)
1. Rotate every provider key that appeared in public commit 46034a4. Done per owner.
2. History rewrite: removes leaked strings from all commits on main. Pending owner confirmation. Rotation is the real fix; the rewrite stops copying from history. Force-push invalidates open PR bases and ChatGPT branches.
3. Bridge exposure (VERIFIED): Caddy on Server 1 routes /bridge, /mcp and /messages to Server 2 port 8011. The bridge exposes run_shell (passwordless sudo on both servers) and github_write_file with no authentication. Owner accepted the risk. Recommendation stands: add a shared-secret header check.
4. OCI secrets for the sniper (Surendra): not present in the repo and not recoverable from the servers. See section 1.

## 1. Oracle sniper and ARM server
- VERIFIED: root cause of no allocation is Oracle capacity in ap-hyderabad-1 ("Capacity full" across all four shapes over 287 attempts), not authentication.
- VERIFIED and FIXED in code: scheduled runs cancelled active 6h runs (cancel-in-progress true with shared concurrency). Now false, with a skip guard. Retry cycle 15s, 429 backoff 45s.
- VERIFIED and MOVED: sniper workflows now live at repo root (.github/workflows) so GitHub runs them. Commit dd1ff29.
- BLOCKED: the four OCI secrets (OCI_USER_OCID, OCI_KEY_CONTENT, OCI_FINGERPRINT, OCI_TENANCY_OCID) and the _2 variants for worker 2 are missing from the main repo. CREDENTIALS.md does not contain them (it lists the names only). None of the servers has an OCI config or API key. They must come from the OCI console (user OCID, tenancy OCID, API key fingerprint, and the private API key PEM generated for the user). The workflow also needs OCI_REGION only if not ap-hyderabad-1.
- Note: the retry script hardcodes one availability domain and one subnet. If Hyderabad has more than one AD, the script never tries the others.

## 2. Infrastructure (VERIFIED)
- Server 1 (140.245.208.100 / 10.0.0.121): 956 MB RAM. Runs FRIDAY, FRIDAY-Voice, Inference, Memora, Stratex, Stratex-Daemon, Futuris, IntelX, Forge, Caddy.
- Server 2 (140.245.243.168 / 10.0.0.120): 956 MB RAM. Runs Sentinel, Cortex, VyralX (+ daemon, autopilot), friday-bridge, Docker.
- Memory limits (VERIFIED from systemd MemoryMax): FRIDAY 200M, Stratex-Daemon 300M, most others 180M. FRIDAY-Voice has NO limit (infinity). On a 956 MB host this is the most likely cause of swap pressure and an OOM risk. Fix first: set a MemoryMax on FRIDAY-Voice.
- Restart policy: all services Restart=always. A crash loop will spin without alerting.
- Caddy (VERIFIED): public routes for friday, inference, memora, stratex, futuris, intelx, forge (Server 1), and bridge, vyralx, sentinel, cortex (Server 2). Ports in AGENTS.yaml and DEPLOYMENT_GUIDE.md now match Caddy.

## 3. FRIDAY orchestrator (the central agent) (VERIFIED)
FRIDAY must route and assign tasks to the other agents. Current state:
- It does route. Two real paths exist:
  a. Command path: `_dispatch_command` in api/server.py maps commands to `fleet_client.ask_*` for each peer.
  b. Directive path: `fleet_client.dispatch_directive` picks a peer by keyword.
  c. Typed path: `fleet_client.dispatch_task` posts a TaskEnvelope to a peer's /v1/task/execute.
- PROBLEM 1 (VERIFIED, fake success): `UniverseOrchestrator.execute_universe_goal` does not dispatch when no simulation API is configured. It returns a fixed message with metrics `real_agents: 8` and status "dispatched" without calling any peer. Any caller treating this as a real dispatch receives a false result. Fix: remove the fabricated synthesis, or make it call the fleet and report real per-agent results.
- PROBLEM 2 (VERIFIED, misrouting): keyword routing is substring matching. "decode this base64" routes to Forge (matches "code"). "trader-proof" routes to Stratex (matches "trade"). "cashback" routes to Stratex (matches "cash"). "webpage" routes to Cortex (matches "web"). Fix: replace substring matching with explicit intent classification, with the routing table tested.
- PROBLEM 3 (VERIFIED, missing endpoints): dispatch_task sends TaskEnvelopes to /v1/task/execute. Forge and Sentinel have no such route. Sending a typed task to them returns 404 and falls through. Fix: implement the endpoint on those agents, or do not route typed tasks to them.
- PROBLEM 4 (VERIFIED): every peer call is a separate HTTP request with no shared result model. Failures are reported per call but there is no task-level status, retry or assignment record. Required for "assign tasks and track them": a task table with ID, owner agent, status and result.
- Requirement mapping (owner said FRIDAY should do everything he says, assign tasks, and option c = both "run the fleet itself" and "route requests"): the routing exists; the assignment/tracking layer and the autonomous fleet control loop are not verified. GAP: read the autonomous controller and fleet supervision code before claiming autonomy.

## 4. Stratex (VERIFIED)
- Exchange mode is chosen by the BINANCE_TESTNET environment variable. The code default is "true" (testnet). The effective value on the running services could not be read from here. Owner states demo account; confirm the variable is true on both Stratex units.
- Stratex contains MT5 and cTrader code as well as Binance Futures. Confirm which adapters are enabled in the running config.
- Live-order gating is by that variable only. Recommendation: add an explicit ALLOW_LIVE_TRADING=false guard that must be set by hand, so a single env change cannot turn on mainnet.

## 5. Deploy and CI (VERIFIED)
- deploy-monorepo.yml deploys on every push to main, and runs `git reset --hard origin/main` on both servers. Uncommitted server changes are lost on every deploy.
- mirror-subrepos.yml force-pushes agent folders to standalone repos. Edit the monorepo only.
- CI (VERIFIED, red): PR #19 and PR #20 both fail on the VyralX/Futuris `app` package collision (`No module named app.services.autonomous_orchestrator`). Main was red before these PRs. Fix CI before any feature merge.
- Workflow files at root are the only ones GitHub runs. Keep the sniper workflows at root.

## 6. Bridge
- bridge/ is untracked and ignored by PR #19/#20 proposals. The ignore rule for bridge/** would prevent the bridge source from ever being committed. Narrow it.
- Add auth, remove any hardcoded token from source, and document every tool it exposes.
- run_shell is the largest single risk in the system. Restrict its allowed commands or add an audit log before the bridge is used by anything other than the owner.

## 7. Repo hygiene
- AGENTS.yaml is the intended roster source. Other roster and port documents must be generated from it or deleted.
- Remove untracked backups on Server 2 (.deploy-backups/, Cortex *.bak-*).
- Multiple overlapping handoff and audit documents exist in docs/. Consolidate into docs/handoff.md and docs/archive.

## 8. Per-agent GAPS (must be read before those agents are changed)
Each agent needs: entrypoint, routes, state store, external calls, tests, failure modes.
- FRIDAY: server.py (3,089 lines), agent/, planning/, ecosystem/, autonomous/, tools/.
- Inference: LLM provider routing, key pools (names only), fallbacks.
- Memora: memory schema, Oracle usage, vector store.
- Stratex: testnet_engine, autonomy, stratex_agents, risk gates, Telegram.
- Futuris: forecasting, Oracle DSN handling (CI relies on a DATABASE_URL shape).
- IntelX: research and evidence pipeline, libSQL usage.
- Forge: code generation and execution sandbox. Security review required (runs code).
- Cortex: CRM and website operations, Mumbai notes.
- Sentinel: security policy and audit log.
- VyralX: video pipeline, autopilot, daemon (Server 2).
- FRIDAY-Voice: LiveKit worker (no memory limit; see section 2).

## 9. Roadmap
- Phase 0 (owner): OCI secrets into the main repo; confirm history rewrite; confirm BINANCE_TESTNET=true on Stratex units.
- Phase 1 (read-only, Claude): finish per-agent GAPS above. Output: docs/ARCHITECTURE_AS_BUILT.md, with file references for every claim.
- Phase 2 (Claude): CI fix (VyralX/Futuris collision), FRIDAY-Voice memory limit, bridge auth and narrowed ignore rules, remove fake dispatch success in universe_orchestrator.
- Phase 3 (ChatGPT): FRIDAY routing rewrite (intent classification, task records, endpoints on Forge and Sentinel) with tests.
- Phase 4: ARM server placement once a sniper claims an instance.
- Phase 5: per-agent hardening, monitoring, backups, rollback.

## 10. Working agreement
- One owner per task, recorded in docs/handoff.md. Only the owner edits those paths.
- One branch and one PR per task. CI must pass before merge. Reviewer comments on the PR and says "Reviewed by X, merged by X".
- Never reset --hard a server while another task has uncommitted work there.
- Secrets never go into git, comments, logs or documents.
