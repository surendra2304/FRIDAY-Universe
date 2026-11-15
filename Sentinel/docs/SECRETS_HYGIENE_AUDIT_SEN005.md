# Secrets-Hygiene Audit — TASK-SEN-005 (Round 2)

**Date:** 2026-11-15 · **Auditor:** Muse crew (`muse_ai`), finisher run after the original crew died on a transport failure · **Scope:** the public repo (current tree + git history) and the deployed trees on both Oracle servers, read-only.

**Reporting rule (followed throughout):** counts, locations and severities only. No secret value was printed, copied, or stored by this audit — including in this document. Matches were triaged using structure only (length, character diversity, dummy-marker presence, hash-equality against known test-fixture strings computed in-process, and context lines with every credential-shaped span masked before display).

**Headline verdict:** No confirmed real secret exists in the repository tree or its history. The fleet's designated secret stores are correctly permissioned and git-ignored almost everywhere — with four concrete exceptions (F-1…F-4), the most serious being a GitHub token persisted in plaintext inside Forge build logs on Server 1 (F-1).

---

## 1. Repository — current tree (main `b34e2d34`, 5,915 tracked files)

*Currency note:* main advanced to `51c67317` while this audit was being shipped (3 merges: REL-044 code, WEB-002 and VYR-004 board updates). The 6 changed files were re-scanned with the same 9 classes at the new head — **zero hits** — so every verdict below holds at `51c67317` as well.

Strong-pattern scan (9 classes). File counts include every hit; the triage column is the audit's classification after structural review.

| Pattern class | Files | Triage |
|---|---|---|
| Google API key shape | 9 | All test fixtures (secret-scanner / scrubber test suites) |
| OpenAI-style `sk-` | 36 | 30 test files; 3 scanner-tooling/config files; 3 collaboration docs — see note (a) |
| GitHub token shape | 5 | All test fixtures |
| AWS access-key shape | 16 | 14 test files; 1 scanner-guard script (pattern definitions + the canonical public example key); 1 GitGuardian config (allowlisted test dummy, hash-verified) |
| Private-key block header | 6 | 4 test files; 1 scanner-guard script (pattern literal); 1 notes file — prose mention only, no key block (no END marker, no body) |
| JWT shape | 3 | All test fixtures |
| Slack token shape | 0 | — |
| Stripe live-key shape | 2 | Both Cortex test files |
| Generic `name = "literal"` assignment | 96 | 94 test files; 2 production files — see F-5, F-6 |

**(a) The collaboration-doc `sk-` hits are false positives.** All 32 matches in `docs/collaboration/WORK_BOARD.yaml` (29), `ACTIVITY_LOG.md` (2) and `HANDOFFS.md` (1) are the substring `sk-` inside branch names (`claude/task-…`), verified on masked context. They are not credentials.

**Sensitive-named tracked files: 11 of 5,915** — nine `.env.example` templates, `.github/workflows/sync-credentials.yml` (references GitHub `secrets.*` context; zero embedded values), and `Stratex/oanda_demo/credentials.py` (reads environment variables only; zero pattern matches). **No `.env`, `CREDENTIALS.md`, `*.pem`, `*.key`, `id_rsa`, or token file is tracked.**

Remaining repo items:

- `Inference/notes/WORKQUEUE.md` — its one key-shaped string is byte-identical (hash-equality) to a known test-fixture dummy. Not a secret.
- `Memora/scripts/run_e2e_system_test.py` — one key-shaped string used as adversarial test content (a labelled fake "credential leak" payload for the scanner). Not a secret.
- `Forge/app/providers/anthropic.py` — two dummy-marked placeholder key strings in production code (F-6).
- `scripts/rotate_gateway_secret.py` — one hardcoded literal assigned to a secret variable; not fixture-matched (F-5, unresolved).

## 2. Repository — git history (1,121 commits reachable, 2026-10-24 → 2026-11-15)

- Sensitive-named paths that ever existed in the window: **the same 11** as the current tree. Nothing was committed and later deleted.
- Commits whose diffs touch each pattern class: Google-shape 5, `sk-` 43 (37 of them are `WORK_BOARD.yaml` churn — the branch-name false positives above), GitHub-shape 5, AWS-shape 6, private-key header 6, JWT 5, Stripe 5, generic assignment 8.
- Every file that appears in history is in the same fixture / tooling / docs set as the current tree. **No file containing a confirmed real secret was found anywhere in the scanned history.**

## 3. Deployed fleet — secret stores and permissions

Designated stores verified on both servers: per-agent `.env` files, the root `.env`, and the credentials dossier(s). All are **git-ignored** in the deployed checkouts on both servers (`git check-ignore` confirmed for every probed path), and `git ls-files` shows only the same two clean tracked lookalikes as the repo.

Permissions: every live `.env` and dossier is mode `600` (owner `ubuntu`) **except F-2 and F-3 below**.

Variable-name inventory (names only) confirmed the intended layout still holds: keys live in the server env files and the dossier; the `THIRD_PARTY_*` auxiliary set in `Inference/.env` remains separately named from the primary pools (never merged). One structural observation is recorded as F-7.

## 4. Deployed fleet — content sweep (outside the designated stores)

Server-side pattern sweep over log files and notes/data directories (the deployed checkouts' code content is the repo content already scanned in §1):

- **Server 1:** 93 log files swept. **5 hit files**, all Forge build-workspace terminal logs from 2026-11-12 — see F-1. Notes/data sweep: only the two already-triaged repo files (`Forge/notes/raw-findings.md`, `Inference/notes/WORKQUEUE.md`).
- **Server 2:** 1 log file swept, **0 hits**. Notes/data sweep: the same two triaged repo files only.

## 5. Findings register

| ID | Severity | Finding |
|---|---|---|
| F-1 | **HIGH** | **GitHub token in plaintext in Forge build logs (Server 1).** 5 files — `Forge/workspaces/task*/logs/terminal.log` (workspaces 1812112026175500, 1912112026181927, 0612112026152234, 1112112026162526, 0312112026145003; all 2026-11-12) — each contain a logged `git remote set-url` command with a GitHub token embedded as the `x-access-token` in the remote URL (masked-context verified; 1 match per file). Forge logs shell commands verbatim, so any credential carried in a command line is persisted. The token must be treated as exposed: revoke/rotate it, purge or redact these logs, and add credential redaction to Forge's terminal logging. |
| F-2 | **MEDIUM** | **OAuth client secret + token files world-readable (Server 2).** `VyralX/data/credentials/` is mode `775`, and both files inside — `client_secrets.json` (404 B) and `token.json` (850 B) — are mode `664`, readable by any local account/process. Recommend `700` on the directory and `600` on both files. |
| F-3 | **LOW** | **Group-readable `.env` copy (Server 1).** `VyralX/.env` in Server 1's deployed tree is mode `664`; every other live `.env` on both servers is `600`. Recommend `600`. |
| F-4 | **LOW** | **Env-backup sprawl.** 27 `.env.bak*` copies of live env files across the fleet (17 on Server 1, 10 on Server 2), all mode `600`. Each is a full stale credential set that stays valid until the underlying keys rotate. Recommend a retention limit (e.g. newest 2 per env file) and secure deletion of the rest. |
| F-5 | **LOW (unresolved)** | **Hardcoded literal in a rotation utility (repo).** `scripts/rotate_gateway_secret.py` line 18 assigns an 18-character literal to a secret variable. It matches no known test fixture, so this audit cannot clear it without reading the value (out of scope by the reporting rule). Recommend the coordinator verify it is a placeholder and move it to an environment variable either way. |
| F-6 | **LOW** | **Placeholder key strings in production surfaces (repo).** `Forge/app/providers/anthropic.py` (2 dummy-marked key-shaped placeholders in a production provider file) and `Cortex/apps/api/src/cortex_api/landing_page.py` (a placeholder `data-api-key` attribute in demo markup). Both are dummy-marked, i.e. intentionally fake — but placeholders in production files invite copy-paste of real values. Recommend replacing with environment references / obviously-invalid markers. |
| F-7 | **INFO** | **Mesh-wide key distribution.** Variable-name inventories show every agent's `.env` holds every peer agent's API key (plus, on some agents, third-party service keys). This is the mesh's working design, but it means one agent's env file compromise exposes all peer keys. Cross-reference: TASK-MEM-005 examined the same layout from the memory-access angle. Recorded for the coordinator's remediation decision; no change made by this audit. |
| F-8 | **INFO** | **Split credential dossiers.** Server 2 holds both `CREDENTIALS.md` (16,951 B) and `credentials.md` (1,298 B); Server 1 holds only `credentials.md` (1,264 B) — all mode `600`, all git-ignored. Divergent copies risk stale records being trusted. Recommend one canonical dossier per fleet with the other removed or reduced to a pointer. |

## 6. What was verified clean

- No `.env`, dossier, private-key, or token file is tracked in the repo, in the tree or in 1,121 commits of history.
- All designated secret stores are git-ignored in both deployed checkouts.
- All live secret stores are mode `600` except F-2/F-3.
- The credentials-sync workflow embeds zero secret values (context references only); `Stratex/oanda_demo/credentials.py` reads env only.
- Server 2 logs and both servers' notes/data directories contain no un-triaged pattern hits.
- The `THIRD_PARTY_*` auxiliary key set remains separately named in `Inference/.env`.

## 7. Method and limits

- Repo scan: `git grep` (file lists only) + `git log -G` (paths/counts only) over 9 pattern classes at main `b34e2d34`; the local mirror is shallow, so the history window is the 1,121 commits reachable in it (2026-10-24 → 2026-11-15) — history before 2026-10-24 was not scanned.
- Triage never displayed a matched value: length/character-diversity statistics, dummy-marker tests, in-process hash-equality against 29 distinct test-fixture strings, and masked-context lines.
- Fleet probes were read-only bridge `run_shell` batches (listings, `stat`, `check-ignore`, variable-name listings, pattern file-lists and per-class counts). The generic-assignment class was not swept server-side (too broad for log data); the strong classes were.
- No cleanup or permission change was performed by this audit; remediation is for follow-up tasks under the coordinator.
