# TASK-FRD-055 — CHECKPOINT 1: scope verified, repo-side material mapped (Muse 8, 2026-11-25 ~22:20 IST)

- **Task:** REPO-IMPLEMENT: FRIDAY repos wave 2 — Hermes Agent, Herald OS, OpenClaw (reference-only); Project NOMAD, Agentic Inbox (adapt). Target FRIDAY. P1.
- **Claim:** hub #1483 comment 7167454965 (2026-11-25 ~21:26 IST). Branch `muse8/task-frd-055` from main `0eeaa43a` (ref verified via git-refs API). Board record verified AVAILABLE / owner muse_8 / branch null / pr null on main `0eeaa43a` before claiming; re-verified AVAILABLE / owner muse_8 on current main `439dfe9` this run (board blob read first-hand from a fresh clone, 23,0xx lines). No competing claim. Board flip AVAILABLE → CLAIMED rides in the work PR (rule 4, WATCH105 precedent).
- **Queue:** FRD-055 (head, CLAIMED) → EARN-026.
- **Stall repaired this run:** the scope draft was written locally at ~21:29 IST (claim run) but never committed — branch `muse8/task-frd-055` still sat at base `0eeaa43a` with zero commits 51 minutes after the claim. This checkpoint commits that scope to the branch so progress is real and visible.

## Source material — verified first-hand

- **PRODUCTION-VERIFICATION-PROGRAMME.md does NOT exist on main.** Full recursive tree search of main `439dfe9` (this run) finds no such file under any path; the claim run found the same on main `0eeaa43a`. The board evidence cites it as the source (sections A/B/C) — that citation is stale or the doc lives outside the repo. Do NOT cite it as read until located.
- **Actual source:** `IntelX/intelx/registries/scouted_repos.json` — 102 entries, verified first-hand this run on main `439dfe9`. All 5 repos present with fits matching the board (5/5). Full entries saved in the claim run's local `scout_entries.json`.

## The five repos

1. **Hermes Agent** — NousResearch/hermes-agent, MIT, Python. Self-improving self-hosted personal agent; skill-learning loop + agent-curated persistent memory + cross-session recall. Target FRIDAY / Memora. Fit reference-only: FRIDAY already implements the pattern; mine the skill-learning loop + memory design for Memora/FRIDAY, don't adopt the platform.
2. **Herald OS** — iamlukethedev/Herald-OS, MIT, TypeScript. Agent-native OS layer, Hermes as interface, permission-gated actions, alpha 0.1. Target FRIDAY. Fit reference-only: alpha, do not adopt; takeaway is permission-gated mission UX + morning-briefing flow; FRIDAY already has both — compare details.
3. **OpenClaw** — openclaw/openclaw, MIT, TypeScript. Personal AI assistant, local Gateway control plane, 20+ channels, swappable models. Target FRIDAY. Fit reference-only: competing platform, would replace FRIDAY; lesson is the channel-gateway control-plane pattern (FRIDAY's bridge/mesh plays this role).
4. **Project NOMAD** — Crosstalk-Solutions/project-nomad, Apache-2.0, TypeScript/Node + Docker. Offline-first knowledge/education server (Kiwix, Kolibri, ProtoMaps, Ollama + Qdrant RAG). Target FRIDAY. Fit adapt: pattern source for FRIDAY's offline-first fallback mode (local LLM + local knowledge store); full Docker stack too heavy for current servers — adopt the pattern in miniature now, fuller version post-ARM (Qdrant already in FRIDAY's post-ARM plan).
5. **Agentic Inbox** — cloudflare/agentic-inbox, Apache-2.0, TypeScript. Self-hosted AI email client on Cloudflare Workers/Durable Objects/R2; classify → summarise → draft, human approval before send. Target FRIDAY. Fit adapt: the Workers stack cannot come to the fleet (hard-wired to Cloudflare, unmaintained since Apr 2026); adopt the workflow pattern in FRIDAY onto existing Gmail access — exactly the triage behaviour the owner wants from his inbox.

## Acceptance — what counts as done

- Adopt/adapt entries (NOMAD, Agentic Inbox): the adapted component must run in FRIDAY's live production path, proven by one real end-to-end use filed as evidence incl. a failure case.
- Reference-only entries (Hermes, Herald OS, OpenClaw): a paper judgement is NOT a result — prove with live evidence whether it works in the agent or not (live trial or guardrail proof of absence from every production path), file that evidence per repo.
- Plus: real owner-style request executed end-to-end through the live FRIDAY service on FRIDAY-Server + failure injection (a downstream agent down) + latency measured per item.

## Live-leg blocker — stated up front

The live legs depend on the owner stop order / fleet CD state (fleet CD broken; Server 2 disk 92% and climbing, cleanup needs owner word — WATCH107, 2026-11-25 ~22:07 IST). Repo-side work proceeds first: read the 5 upstream repos, draft the per-repo trial/guardrail evidence. Live legs are assessed, not assumed — if blocked, reported plainly (STR-047 wiring-leg pattern), not claimed done.

## Next steps

1. Read each upstream repo (public GitHub) — structure, the specific pattern named in fit_rationale, licence compatibility (all MIT/Apache-2.0, free-only OK).
2. Draft evidence doc `docs/collaboration/TASK-FRD-055-EVIDENCE.md` skeleton: one section per repo (trial design or guardrail proof), plus the live end-to-end request plan.
3. Assess live legs vs stop order; report blockers on the hub if live work is gated.
4. Work PR (no checkpoint PRs per coordinator rule): scope/evidence + board flip AVAILABLE → IN_REVIEW (then MERGED flip after merge, STR-051 precedent).

— Muse 8
