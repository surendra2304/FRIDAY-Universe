# IG wave-2 Forge evaluation notes (TASK-IG2-FRG-09)

Package G-08..G-12 of the full re-watch (ig-fullwatch/packages/forge.md):
the agent-infrastructure repos and platforms the owner's corpus
pointed at Forge. Method, per the task: every named item was verified
against the actual project (public repo/platform pages, read
2026-11-16) before any verdict — items from the reels were
**named-unverified** until then. Verdicts are Forge-scoped: a
"reference-only" here means *not a Forge build input*, with the
owning lane named where one exists. Companion builds from the same
package: TASK-IG2-FRG-07 (the real one-prompt flow) and
TASK-IG2-FRG-08 (the Claudex Loop).

## 1. G-08 — the seven-repo list (Dc3pMkakrid, @duncanrogoff)

The reel's links sit behind the creator's community page, so the
identities below are the frame/subtitle names resolved against
GitHub — each one confirmed as a real, matching project.

### 1.1 Browser Use — browser-use/browser-use — REFERENCE-ONLY
Verified: MIT, ~117k stars, Python; v1.0 (Nov 2026) rewrote the agent
onto raw Chrome DevTools Protocol with a persistent REPL. Forge does
not drive browsers — it generates code; the fleet's browser surface
is FRIDAY's `real_browser_agent`. Adoption as a dependency is also
blocked today on a hard fact: Browser Use requires Python 3.11+ and
the fleet runs 3.10 (the same blocker holding PR #347). Pattern
(task-level browser agent, REPL over CDP) is FRIDAY-lane reference.

### 1.2 agentmemory — rohitg00/agentmemory — REFERENCE-ONLY
Verified: Apache-2.0, TypeScript, ~30k stars; a persistent-memory
MCP server for coding CLIs (Claude Code, Codex, Cursor, …) that
captures sessions and makes decisions searchable. Memory is Memora's
remit — the fleet has exactly one memory agent by design, and a
second memory server contradicts it. The transferable pattern
(session capture → searchable decisions) is the same one the
claude-mem note (§3.3) already records for the Forge↔Memora seam.

### 1.3 Scientific Agent Skills — K-Dense-AI/scientific-agent-skills — REFERENCE-ONLY
Verified: MIT; 177 skills at verification time (the reel's frame
said 163 — the count has since grown), 100+ scientific databases,
following the open Agent Skills standard (SKILL.md packages). The
content domain is scientific research, not code generation — nothing
for Forge to build from. The *format* is the note worth keeping:
skills as portable standard packages. Forge's `SkillRegistry` is the
same idea in fleet-internal form; if cross-tool skill portability is
ever wanted, the agentskills.io format is the candidate standard.

### 1.4 Diagram Design — cathrynlavery/diagram-design — REFERENCE-ONLY (already in-fleet)
Verified: MIT; a Claude Code skill producing editorial diagrams as
one self-contained HTML+SVG file. That exact pattern already lives
in the fleet — VyralX's `diagram_service.py` renders diagrams as
self-contained HTML+SVG. Nothing for Forge.

### 1.5 Anthropic Cybersecurity Skills — mukul975/Anthropic-Cybersecurity-Skills — REFERENCE-ONLY (Sentinel's lane)
Verified: Apache-2.0; a **community project, not Anthropic PBC**
despite the name (the repo disclaims affiliation itself); 754 skills
at v1.0 growing to 818, each mapped across MITRE ATT&CK, NIST CSF,
MITRE ATLAS, D3FEND, NIST AI RMF and MITRE F3. The framework-mapped
skill-pack pattern is already implemented in-fleet by Sentinel's
`cyber_skills_service` (ATT&CK / NIST CSF 2.0 / D3FEND / ATLAS / F3),
and Forge's own `sec.*` registry skills follow the same data shape.
Two cautions recorded: the library includes offensive/dual-use
techniques (its own README restricts it to authorized use), so
wholesale content import is rejected; and ownership of any future
content adoption is Sentinel's, not Forge's.

### 1.6 Awesome Harness Engineering — ai-boost/awesome-harness-engineering — REFERENCE-ONLY (gap closed)
Verified: a curated list (~5k stars), organised by problem —
context delivery, tool design/MCP, planning artifacts, permissions
and sandboxing, memory, verification and evals, agent-loop structure.
The Forge baseline (B10) flagged that this list had *no Forge
evaluation anywhere*; this section is that evaluation. Cross-check:
every category has a counterpart somewhere in the fleet today — on
the Forge side, harness patterns (`app/harness/ecc_patterns.py`,
`app/harness/workflow.py`), planning (`app/planning/plan_to_ship.py`),
verification (`app/verification/` battery + review passes + the
Claudex Loop of TASK-IG2-FRG-08) and execution sandboxing
(`app/execution/`); the memory category's counterpart is Memora —
memory is Memora's remit by design, not Forge's (see §1.7). No
pattern family in the list is missing from the fleet. It stays on
the reference shelf as the external cross-check catalog for future
harness work.

### 1.7 OpenViking — volcengine/OpenViking — REFERENCE-ONLY (Memora's lane)
Verified: AGPL-3.0; a context database storing memory, resources and
skills as a browsable `viking://` virtual filesystem with tiered
(L0 abstract / L1 overview / L2 detail) loading. Memora's context
layer already mirrors this pattern (`viking://` URIs, L0/L1/L2).
Pattern-only is also the license-safe route: AGPL-3.0 would attach
to any direct adoption, which is a decision for the owner, not an
implementer — and unnecessary, since the pattern is already in use.

### 1.8 affaan-m/ECC — ALREADY IMPLEMENTED
Named in this task alongside G-08: the ECC harness patterns were
adopted in wave 2 — PR #734 shipped `Forge/app/harness/ecc_patterns.py`.
No further work.

## 2. G-09 — JCode (Da5fhPriu3n) — REFERENCE-ONLY
Identity per the wave-1 repo card: 1jehuang/jcode (Forge evaluation
notes, TASK-IG-FRG-08 §1). The full-watch frame names (multi-agent
terminal harness, swarm mode, 31k stars claimed) are consistent with
that identity. The wave-1 ruling stands and the full watch changes
nothing material: Forge *is* the fleet's build harness; adopting a
second terminal harness duplicates it. Its working patterns —
Kanban-style board, worktree isolation, PR queue — are already fleet
practice. Reference-only.

## 3. G-10 — Claude Code plugins (DdPncBxAQoz)

### 3.1 OmniRoute — NOT FORGE'S ITEM
A local multi-provider model gateway (the frame's 9Router detail).
Provider routing is Inference's remit; the inference package (I-12)
owns the detail. Forge takes no position.

### 3.2 Karpathy Skill — multica-ai/andrej-karpathy-skills — ALREADY IMPLEMENTED
Wave-2 PR #674 (TASK-IG2-FRG-01).

### 3.3 Graphify — Graphify-Labs/graphify — ALREADY IMPLEMENTED
Wave-2 PR #676 (TASK-IG2-FRG-02). The claude-mem plugin named in the
same family (thedotmack/claude-mem): pattern owned by Memora; the
Forge consumer half (query Memora at build start) is documented in
the wave-1 notes §6 and remains unbuilt — recorded here again as a
named follow-up, deliberately not folded into this task.

## 4. G-11 — MausBot aggregator (DeZ-JEFNTpR) — REJECT as a Forge component
Verified identity: milind-soni/OpenMausBot (Apache-2.0, active — 563
commits per a third-party roundup read 2026-11-16); the item's
mausbot.com / Hermes / OpenClaw framing matches a desktop agent
shell with messaging front doors. Consistent with the baseline
(A9/B1) verdict: it is a consumer product surface, not build
infrastructure. The fleet's equivalent surface is FRIDAY itself.
Nothing to adopt into Forge.

## 5. G-12 — Swiggy Builders Club (DYg_b2ZTK70) — REFERENCE-ONLY (external platform)
Verified real: Swiggy's official MCP platform
(mcp.swiggy.com/builders), announced April 2026 — 3 MCP servers
(Food, Instamart, Dineout) and 18+ API tools at launch (the builders
page now lists a fourth server, Scenes, and 62 tools), OAuth 2.1 +
PKCE, free localhost prototyping, production access
application-gated. This is an external commerce platform, not agent
infrastructure: a future FRIDAY consumer integration would involve
real-money ordering and is an owner decision, outside Forge's remit
and outside this task. The pattern note is genuinely good and
already fleet practice: per-domain MCP servers, OAuth+PKCE, and
localhost-first development mirror the fleet's own MCP bridge
discipline.

## Summary

| Item | Verdict |
|---|---|
| Browser Use | reference-only (FRIDAY lane; Python 3.11+ blocks adoption) |
| agentmemory | reference-only (Memora's remit) |
| Scientific Agent Skills | reference-only (format noted) |
| Diagram Design | reference-only (pattern already in VyralX) |
| Anthropic Cybersecurity Skills | reference-only (Sentinel's lane; dual-use caution) |
| Awesome Harness Engineering | reference-only (cross-checked; no missing family) |
| OpenViking | reference-only (pattern already in Memora; AGPL caution) |
| affaan-m/ECC | already implemented (PR #734) |
| JCode | reference-only (wave-1 ruling stands) |
| OmniRoute | inference lane's item (I-12) |
| Karpathy Skill / Graphify | already implemented (PRs #674 / #676) |
| MausBot | reject as a Forge component |
| Swiggy Builders Club | reference-only (external platform; owner-decision territory) |

No G-08..G-12 item produced a Forge code adoption in this task: the
build outcomes of the package are FRG-07 and FRG-08. That is the
honest result of verifying before adopting — most of the list was
already in the fleet under another lane's ownership, and the rest
does not fit Forge's remit.
