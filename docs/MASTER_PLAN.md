# FRIDAY Universe: Master Plan (v1, written by Claude)

Status legend: VERIFIED = checked in code, git or on the live servers. GAP = not yet read; must be read before Phase 2 work.
Secrets: this document contains no secret values. Any credential mentioned is named, never printed.

## 0. Do this first (security, owner: Surendra)
1. Rotate every provider key that was ever committed. VERIFIED: public commit 46034a4 (2026-10-23) contains 8 distinct Google-API-key-shaped strings and 9 Groq/OpenRouter/GitHub token-shaped strings. Eight Google-key strings are still present at HEAD, mostly in test files. Rotate: Google Gemini pool, Groq pool, OpenRouter, any other provider in those files. Then scrub HEAD. Rewriting public history (git filter-repo + force push) is destructive, so it needs your explicit yes.
2. Treat the repo as public. CREDENTIALS.md exists only on Server 2 disk (untracked, 0 commits in history). Keep it off git. Move its contents into a secrets store or the server environment file, then delete the copy in the repo.
3. The FRIDAY bridge is reachable publicly. VERIFIED: Caddy on Server 1 routes /bridge*, /mcp* and /messages* to 10.0.0.120:8011. The bridge now has run_shell (passwordless sudo on both servers) and github_write_file, and they have no authentication. You said you accept this risk. I still recommend a shared-secret header check, because the exposure is the single most powerful thing in the system.
4. Hard-coded GitHub token: bridge/server.py had a fallback token in source. Confirm it was removed and that the old PAT is revoked (you say it is).

## 1. Sniper / ARM server (owner: Claude)
- VERIFIED root cause of "never got the server": not auth. Run 42463163919 made 287 attempts over 5.5h, all "Capacity full" in ap-hyderabad-1, with 429 throttling. Two causes of waste: concurrency cancelled runs, and 42s+ sleeps.
- DONE (monorepo a50b9c6, mirrored to standalone): cancel-in-progress false; scheduled runs skip when a sniper is active; retry cycle 15s; 429 backoff 45s. Worker 2 has the same change.
- Expected limit: Oracle capacity. If Hyderabad stays full, no script speed helps. Check run logs after the next scheduled hour.
- Open: when the instance is claimed, the script never promotes it to production, by design. Decide later.

## 2. Infrastructure (VERIFIED on live servers)
- Server 1 (140.245.208.100, 10.0.0.121): 956 MB RAM, ~46% used, swap in use. Runs FRIDAY, FRIDAY-Voice, Inference, Memora, Stratex, Stratex-Daemon, Futuris, IntelX, Forge, Caddy. Public ingress.
- Server 2 (140.245.243.168, 10.0.0.120): 956 MB RAM. Runs Cortex, Sentinel, VyralX (+daemon/autopilot), Bridge (8011), Docker/Dokploy.
- Memory is the binding constraint. Plan: move the lightest-coupled agent to the ARM box once claimed. Do not move Stratex or the trading engines without a test window.
- Caddy routes are listed in /etc/caddy/Caddyfile on Server 1. Keep the table in sync with AGENTS.yaml.

## 3. Stratex (VERIFIED: two engine families)
- Binance Futures engines exist (Stratex/testnet_engine, Stratex/autonomy, Binance adapter tests).
- MT5 engine also exists: Stratex/autonomy/mt5_autonomous_engine.py. Stratex-Daemon.service runs an IC Markets cTrader engine plus Telegram.
- Correction: an earlier note said Stratex was Binance-only. It is multi-venue. Confirm which venues are live before touching trading code. Treat all execution code as high risk: test on testnet/demo first.

## 4. Deploy and CI (VERIFIED)
- deploy-monorepo.yml deploys on every push to main, and its SSH step runs `git reset --hard origin/main` on both servers. Uncommitted server edits are lost. Only commit-and-push changes survive.
- mirror-subrepos.yml force-pushes each agent folder to its standalone repo. Edits made only in a standalone repo are overwritten. Always edit the monorepo.
- Two CI systems are red on main (earlier observation, re-verify). Fix CI before adding features.
- Known breakage: run_workspace_test calls venv/bin/pytest, which is not installed on Server 2. Fix: install pytest into the venv or use `python -m pytest`.

## 5. Bridge hygiene (owner: Claude)
- bridge/ is untracked and not git-ignored. Add it to .gitignore or commit it deliberately (it holds the connector code, so commit only after auth is added and secrets are removed).
- git_commit uses `git add -u`, so new files are not committed. Use github_write_file or run_shell git add for new files.
- bridge/test_bridge_recon.py is a blank placeholder. Delete it.

## 6. Repo hygiene (owner: Claude)
- Untracked clutter on Server 2: .deploy-backups/, Cortex/*.bak-* files, bridge/. Move backups out of the repo or git-ignore them.
- Duplicate roster sources: AGENTS.md, AGENTS.yaml, docs/REPOSITORY_REGISTRY.md, docs/FRIDAY_UNIVERSE_MASTER_SPECIFICATION.md. Pick AGENTS.yaml as the single source of truth and generate the rest from it.
- Multiple handoff files (docs/FRIDAY_Universe_Engineering_Handoff.md and others). Create docs/handoff.md with the TASK-ID protocol from the directive and retire the rest into docs/archive.

## 7. GAPS (not yet read in full; required before Phase 2)
- Per-agent code for: FRIDAY (orchestrator), Inference, Memora, Futuris, IntelX, Forge, Cortex, Sentinel, VyralX, Stratex (engines and risk gates), FRIDAY-Voice.
- Database layer: which agents use Oracle, which use libSQL, Mumbai-region notes, Dokploy Postgres.
- Systemd unit files on both servers (ExecStart, env files, restart policy, memory limits).
- Test coverage per agent and which tests currently fail.
- Mesh/inter-agent auth between services.
Claude will read these in Phase 1 before proposing code changes to any of them.

## 8. Roadmap
Phase 0 (now): section 0 security rotation (owner: Surendra). Then section 4 CI fix (Claude).
Phase 1 (read-only): complete section 7 gaps. Output: docs/ARCHITECTURE_AS_BUILT.md, verified not inferred.
Phase 2: bridge auth + hygiene (section 5), repo hygiene (section 6), memory reduction on Server 1.
Phase 3: ARM server promotion and agent placement, once the sniper claims an instance.
Phase 4: per-agent upgrades, one agent per branch and PR, with tests.
Phase 5: production hardening: monitoring, backups, rollback procedure.

## 9. Working agreement between Claude and ChatGPT
- Each task has one owner, recorded in docs/handoff.md. Only the owner edits that path.
- One branch per task. CI must pass before merge to main. Merge to main is the deploy, so keep merges small.
- The other AI reviews by reading the handoff entry and running tests, not by pushing to the same files.
- Never run reset --hard on a server while another task has uncommitted work there.
