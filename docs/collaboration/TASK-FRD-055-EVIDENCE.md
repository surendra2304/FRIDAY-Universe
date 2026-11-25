# TASK-FRD-055 — Evidence: FRIDAY repos wave 2 (Muse 8, 2026-11-25 ~23:30 IST)

- **Task:** REPO-IMPLEMENT: FRIDAY repos wave 2 — Hermes Agent, Herald OS, OpenClaw (reference-only); Project NOMAD, Agentic Inbox (adapt). Target FRIDAY. P1.
- **Claim:** hub #1483 comment 7167454965 (2026-11-25 ~21:26 IST). Branch `muse8/task-frd-055`.
- **Board:** AVAILABLE / owner muse_8 / branch null / pr null on main `3efe8b04` (verified first-hand this run, board 23,107 lines, saved `~/workspace/muse8/selfcheck/board_main_2316.yaml`). Board flip AVAILABLE → IN_REVIEW rides in the work PR (rule 4).
- **Source citation on the board is stale:** the board evidence cites PRODUCTION-VERIFICATION-PROGRAMME.md sections A/B/C — that file does NOT exist on main (full recursive tree search, twice: main `0eeaa43a` and main `439dfe9`). Actual source is `IntelX/intelx/registries/scouted_repos.json` (102 entries); all 5 repos present with fits matching the board.

## 1. Upstream repos — read first-hand this run (GitHub API, 2026-11-25 ~23:20 IST)

| Repo | Licence | Language | Last push | State |
|---|---|---|---|---|
| NousResearch/hermes-agent | MIT | Python | 2026-11-25T17:20:33Z | Active; README confirms built-in learning loop — creates skills from experience, improves them in use, persists knowledge, searches past conversations, builds a model of the user across sessions |
| iamlukethedev/Herald-OS | MIT | TypeScript | 2026-10-29T11:00:08Z | Alpha; README confirms agent-native OS, Hermes as interface, every mutating action through a permission system |
| openclaw/openclaw | MIT | TypeScript | 2026-11-25T17:48:27Z | Active; README confirms Gateway control plane, 20+ channels, `.agents/skills` structure |
| Crosstalk-Solutions/project-nomad | Apache-2.0 | TypeScript | 2026-11-24T23:02:59Z | Active; README confirms offline-first server, ~5 GB disk / <1 GB RAM base, Kiwix/Kolibri/ProtoMaps, Ollama + Qdrant RAG |
| cloudflare/agentic-inbox | Apache-2.0 | TypeScript | 2026-04-23T21:04:17Z | **Unmaintained ~7 months** (last code push 2026-04-23; repo `updated_at` is metadata activity only). README confirms Workers / Durable Objects / R2 + Agents SDK email agent |

Full API responses saved: `~/workspace/muse8/frd-055/upstream_reads.json`. One gap: the tree API returned an empty top-level listing for hermes-agent (repo ~1.55 GB; structure unverified from the API) — its README + description are verified; structure to be confirmed from a direct clone if a trial needs it. All licences are MIT/Apache-2.0 — free-only OK, no paid service involved.

## 2. Repo-side dispositions — verified first-hand on main `3efe8b04` (not taken on trust)

The five repos' dispositions were already recorded by prior merged work. I re-verified each on current main this run instead of citing the tracker blind:

- **Hermes (reference-only) — pattern-mined, implementation exists.** `Memora/core/memory/skill_learning_service.py` (TASK-IG2-MEM-02, `PATTERN_TAG = "hermes-skill-learning-loop"`) + `Memora/core/memory/user_model_service.py` (TASK-IG2-MEM-03, `PATTERN_TAG = "hermes-user-model"`) — both read first-hand; headers state the Hermes transferable assets explicitly. No upstream Hermes code vendored. INT-044 tracker row 7: DISPOSITION CONFIRMED (main 98b1ce8d).
- **Herald OS (reference-only) — no implementation, reference only.** Full-repo grep for `herald` on main finds hits only in the registry, the INT-044 tracker, and `FRIDAY/docs/IG_REFERENCE_NOTES.md` — no implementation, no adoption. INT-044 tracker row 8: DISPOSITION CONFIRMED.
- **OpenClaw (reference-only) — pattern-mined, implementation exists.** `FRIDAY/src/friday/proactive/whatsapp_gateway.py` (TASK-IG2-FRD-02, "OpenClaw pattern") + `FRIDAY/src/friday/api/server.py` — headers read first-hand. The competing platform is not adopted; no upstream code vendored. INT-044 tracker row 9: DISPOSITION CONFIRMED.
- **NOMAD (adapt) — repo-side IMPLEMENTED.** `Memora/core/memory/offline_pack.py` + `Memora/core/memory/nomad_pack/manifest.json` + `corpus.jsonl` (TASK-MEM-032, Muse 2, merged) + `Memora/tests/test_mem032_nomad_offline_pack.py` + `FRIDAY/tests/test_ig_frd_007_offline_fallback.py`. Manifest read first-hand: 16 entries, SHA-256 pinned, "packaging pattern only; no NOMAD code, content, or services are vendored". INT-044 tracker row 12: REPO-SIDE IMPLEMENTED (main a0a9f1ba). LIVE production-verified: NOT YET.
- **Agentic Inbox (adapt) — repo-side IMPLEMENTED.** `FRIDAY/src/friday/tools/builtin/agentic_inbox_tools.py` + `FRIDAY/tests/test_agentic_inbox.py` + `Cortex/apps/api/src/cortex_api/real_agentic_inbox.py` + `tests/test_real_batch4a.py`. Test header read first-hand: deterministic classification, extractive summaries, drafts pending-only, single send path, unconfigured mailbox reports `not_configured`. INT-044 tracker row 49: REPO-SIDE IMPLEMENTED (main a0a9f1ba). LIVE production-verified: NOT YET.

**Not conflated:** `hermes-parser` / `hermes-estree` in `Sentinel/apps/dashboard/package-lock.json` is Meta's Hermes JavaScript parser (npm) — unrelated to NousResearch Hermes Agent. It is not a Hermes Agent dependency.

**FRD-053 (Muse 1, 2026-11-25 ~17:20 IST) already live-probed two of these legs** (`docs/collaboration/TASK-FRD-053-PRODUCTION-VERIFY.md`, read first-hand): IG2-FRD-01 agentic inbox NOT VERIFIED (triage executes live, fails honestly in ~2–5 ms; no mailbox configured on FRIDAY-Server); IG2-FRD-02 WhatsApp gateway NOT VERIFIED (route exists, designed 404 while unconfigured; owner Meta setup owed). Failure injection NOT RUN — held, needs owner clearance. Live target settled: FRIDAY-Server, NOT S1 (S1 FRIDAY.service retired by design).

## 3. Verdict — repo-side substantially complete; live legs are what FRD-055 still owes

- **No new implementation is needed for the repo-side legs.** The pattern-mining (Hermes, OpenClaw) and the adaptations (NOMAD, Agentic Inbox) already exist on main as merged, tested work, and the reference-only hold (Herald OS) is confirmed by absence. Re-implementing them would add noise, not value. This evidence doc is FRD-055's own consolidated record of those dispositions, verified first-hand.
- **What FRD-055 still owes — the live legs, all of them:**
  - Adapt entries (NOMAD, Agentic Inbox): the adapted component running in FRIDAY's live production path, proven by one real end-to-end use filed as evidence incl. a failure case.
  - Reference-only entries (Hermes, Herald OS, OpenClaw): LIVE evidence per repo — a live trial or guardrail proof of absence from every production path. The greps in §2 are repo-side evidence, not live evidence; they do not satisfy this acceptance line on their own.
  - Plus: a real owner-style request executed end-to-end through the live FRIDAY service on FRIDAY-Server + failure injection (a downstream agent down) + latency measured per item.

## 4. Live legs — BLOCKED, stated plainly

- Owner stop order still in force (WATCH109, hub #1483 comment 7169671316, 2026-11-25 ~23:03 IST: deploy clearance for IG-INF-01-FIX-01 NOT granted).
- Fleet CD broken; Server 2 disk 94% and climbing (cleanup needs owner word) — carried, not mine.
- Failure injection on the live voice companion needs owner clearance (FRD-053 established this; WATCH093 held it).
- No live probe was run this run. No live leg is claimed done. When clearance comes, the live legs run against FRIDAY-Server with latency measured per item; until then they stay owed, not claimed.

## 5. Route to close

Work PR (no checkpoint PRs per coordinator rule): this evidence doc + checkpoint docs + board flip AVAILABLE → IN_REVIEW, then MERGED flip after the live legs are proven or the coordinator rules on the blocked live legs (STR-047 wiring-leg precedent: a held live leg can be follow-up work for a new task rather than blocking the MERGED flip — coordinator's call, not mine).

— Muse 8, 2026-11-25 ~23:30 IST
