# TASK-MEM-031 — Memora verify wave 3 (REPO-IMPLEMENT leg): evidence

**Task:** TASK-MEM-031 — PRODUCTION-VERIFY + REPO-IMPLEMENT: Memora —
IG2-MEM-01/02/03 live verification + repos claude-mem, Agent Memory, Open Viking (wave 3). Priority P2.

**Worker:** Muse 2. **Claim:** hub #1483 comment 7154497656, 2026-11-25 ~11:40 IST
(posted together with the TASK-MEM-030 completion). **Branch:**
`muse2/task-mem-031-memora-verify-wave3` (from main f6b912a6; main merged in
as 89df8157 — no rebase, no force-push).

**Scope of this PR — REPO-IMPLEMENT leg only.** The production-verify leg
(live extreme-condition verification of IG2-MEM-01/02/03 and the live trial
per repo) is GATED by the owner stop order; no live server was touched and
no live verification was attempted. That leg is filed as owed below with
its plan. What this PR does is the repo work: research each repo via the
public GitHub API, adapt claude-mem and Agent Memory into Memora/Forge in
code with production call sites, and file the Open Viking judgement with
evidence.

## 1. What was already there (why this is a delta, not a duplicate)

Research first established that wave 1/2 and the IG2 package had already
landed the obvious adaptations — re-implementing them would be churn:

- **Agent Memory's capture-compress-inject** is already
  `Memora/core/memory/capture_service.py` (TASK-IG2-MEM-01, PR #709):
  its docstring cites the agentmemory pattern explicitly, and it already
  captures events, compresses sessions into digests, and injects a
  session-start pack.
- **Agent Memory's markdown store** is already
  `Memora/core/memory/real_agent_memory.py` (52 KB): frontmatter
  memories, BM25/TF-IDF indexes, RRF fusion, supersede chains, sleep
  consolidation.
- **Open Viking's context database** is already
  `Memora/core/memory/real_viking_context.py` (62 KB, TASK-MEM-010
  persistence): `viking://` URIs, L0/L1/L2 layer projection, scoped
  search, session commit, wiki compilation.

The adaptations below are the gaps that remained after that audit.

## 2. claude-mem — ADAPT (Memora + Forge)

**Repo:** thedotmack/claude-mem — "Persistent Context Across Sessions for
Every Agent". Apache-2.0, TypeScript, v16.1.3, ~119,602 stars / 10,394
forks, pushed 2026-11-25. Hooks capture what an agent does, an observer
takes notes, AI compresses them, and the next session opens with a
layered index (index → timeline → details) so tokens are paid only for
what is opened. Its hosted observer is a paid 30-day trial — the free-only
rule forbids that path; the pattern was adapted, the service was not
adopted.

**What was adapted — needle observations + layered session index:**

- `Memora/core/memory/session_needles.py` (new, stdlib only):
  `classify_needle()` — deterministic rule-based classification into
  claude-mem's needle taxonomy (`src/ui/viewer/utils/category.ts`:
  `KNOWN_OBSERVATION_TYPES` / `CATEGORY_ORDER` — decision, bugfix,
  security_alert, security_note, sensitive, feature, refactor,
  discovery, change, observation fallback), priority-ordered so a fix
  for a vulnerability reads as a security alert and a secret marker
  reads as sensitive. `list_actor_sessions()` / `render_index()` —
  the L0 token-costed session index. `timeline()` (L1) and `detail()`
  (L2) — the three-step mem-search. `sensitive` rows never render
  their content in a timeline or detail read (awareness-only, as in
  claude-mem).
- `Memora/core/memory/capture_service.py`: `capture_event` classifies
  every event and stores `needle_kind` in provenance (additive — the
  caller-supplied `kind` bucket is untouched); `build_session_context`
  prepends the L0 index to the session-start pack and returns it as
  `session_index`.
- `Memora/apps/api/routers/v1_capture.py`: `GET /v1/capture/sessions`
  serves the index.
- `Memora/adapters/forge/adapter.py`: `ForgeAdapter.
  record_session_observation()` — the Memora-side Forge wire: classifies
  and stores Forge observations with the same taxonomy; a `sensitive`
  needle stores a placeholder, never the content.
- `Forge/app/integrations/memora_client.py`: `a_record_session_event`
  / `record_session_event` — POST the session event to
  `/v1/capture/events`, Oracle MEMORA_OUTBOX fallback on cloud failure,
  empty content / missing session id refused without an HTTP call.
- Production call sites (Forge): `Forge/app/cli.py` (build-complete
  block — every CLI build captures its outcome; a failed build is a
  `bugfix` needle) and `Forge/app/agents/roles.py` (Developer role
  code-synthesis block; a fallback-stub synthesis is a `bugfix` needle).
  Both ride in the existing fail-soft `try/except` beside the
  `record_interaction` call they follow.

**Tests:** 14 new tests in `Memora/tests/test_mem031_memora_verify_wave3.py`
(classifier kinds + priority, needle stored in provenance, sensitive
withholding in timeline/detail, index + context pack over HTTP, new
routes mounted, Forge adapter observation + sensitive withholding) and
6 new tests in `Forge/tests/unit/test_mem031_forge_session_capture.py`
(cloud mock async + sync, outbox fallback, empty-content and missing-
session-id refusal, no-outbox error). Both files are added to the tier-1
CI lists in `.github/workflows/friday-universe-ci.yml`.

## 3. Agent Memory (agentmemory) — ADAPT (Memora)

**Repo:** rohitg00/agentmemory — "#1 Persistent memory for AI coding
agents based on real-world benchmarks". Apache-2.0, TypeScript,
~30,577 stars / 2,722 forks, pushed 2026-11-18. Karpathy LLM-Wiki
pattern + confidence scoring, lifecycle, knowledge graphs, hybrid
search; keyless BM25 mode, local embeddings. A Node server for coding-
agent CLIs — it cannot run on the fleet, so the pattern was adapted.

**The gap:** Memora stores a `confidence` column on every record and
already uses it as a *tiebreaker* in hybrid ranking — but nothing ever
*moved* a record's confidence after it was written, and the in-memory
SM-2 reinforcement engine never touches the stored record. Confidence
was write-once. agentmemory's model (`test/confidence.test.ts`:
confidence in [0, 1] from co-occurrence + recency, explicitly
overridable, clamped; recall sorts by confidence desc; minimum-
confidence filter) was adapted as a persisted loop:

- `Memora/core/memory/confidence_reinforcement.py` (new):
  `reinforce_on_recall()` — explicit path: an agent reports which
  served memories were useful; useful +0.05, served-but-unused −0.02,
  clamped to [0.05, 0.99]. Actor-scoped (only the actor's own records
  move) and tenant-scoped; provenance is never touched (HMAC safety).
  `reinforce_compressed_events()` — implicit path: when a digest is
  promoted to SEMANTIC through the evidence-checked workflow, its
  source events gain +0.03. `confidence_weighted_score()` /
  `confidence_weighted_sort()` — rank by final score × (0.5 + 0.5 ×
  confidence), so confidence moves order instead of merely breaking
  ties.
- `Memora/core/memory/capture_service.py`: `build_session_context`
  re-sorts hits by confidence-weighted score (the session-start inject
  path — hybrid search's own ordering contracts are untouched);
  `compress_session` bumps source-event confidence only when
  promotion was just granted in that call, never on the idempotent
  repeat.
- `Memora/apps/api/routers/v1_capture.py`: `POST
  /v1/capture/recall-outcome` — the explicit agent-reported outcome
  endpoint (same actor rule as every other capture route).
- Forge leg: Forge's session events flow through this same capture
  store, so Forge digests earn the same implicit reinforcement and
  Forge's session-start context comes through the same weighted inject
  path; no separate Forge client method was added for recall outcomes
  because no Forge production call site could supply the usefulness
  signal honestly yet (that is a named follow-up, not a pretence).

**Tests:** covered in the same Memora suite — weighted-sort order flip
on confidence, recall-outcome endpoint (+0.05 / −0.02, unknown-id
skip), clamp at 0.99 over repeated reports, actor isolation, and the
compress→promote→+0.03 bump end to end over HTTP (promotion grants in
this test env, as the MEM-01 suite already proves).

## 4. Open Viking — REFERENCE-ONLY (Memora)

**Repo:** volcengine/OpenViking — "Self-evolving Context Database for
AI Agents. Unify Agent Memory, Knowledge RAG and Skills." AGPL-3.0,
Python, ~42,718 stars / 3,558 forks, pushed 2026-11-25, 1,694 open
issues. `viking://` virtual filesystem; L0 abstract / L1 overview /
L2 detail layers; sessions become readable files; benchmarked 80–83%
on LoCoMo with Doubao models.

**Judgement: reference-only — do not adopt the code or the server.**
Three independent reasons, each verified first-hand:

1. **License — AGPL-3.0.** Adopting OpenViking code into Memora would
   put the combined work under AGPL's network-use clause. FRIDAY
   Universe is public, but the fleet is a private deployment; taking
   on AGPL for a component whose ideas Memora already implements
   natively is unjustifiable.
2. **Deployment shape — a separate server + vendor models.** OpenViking
   is a standalone server requiring an embedding model and a VLM; its
   published benchmarks run on Doubao (ByteDance) models. That is a new
   service plus a non-free vendor dependency, against the owner's
   free-only rule and the fleet's ~180 MB shape.
3. **Already implemented natively.** `Memora/core/memory/
   real_viking_context.py` (62 KB) already implements the ideas that
   matter here — `viking://` URIs, L0/L1/L2 projection, scoped search,
   session commit, wiki compilation — with persistence (TASK-MEM-010)
   and durability tests (`Memora/tests/
   test_viking_context_durability.py`). There is nothing left to import
   except the server itself.

**Guardrail proof of absence (this run):** GitHub code search for
`openviking` / `OpenViking` / `volcengine` across the repo returns only
doc/registry mentions (Forge/docs/IG2_EVALUATION_NOTES.md,
docs/DEEP_ENGINE_*.md, prompts/ANTIGRAVITY_MASTER_PROMPT.md,
IntelX/intelx/registries/scouted_repos.json,
tests/test_real_deep_layer10.py); `import openviking` returns the same
six doc-only hits — no OpenViking code, client, or dependency exists in
any production path. A live trial of the server is owed pending
coordinator clearance (see §5); the reference-only verdict does not
depend on it, because reasons 1–3 already decide it.

## 5. Production-verify leg — OWED (gated, not attempted)

Per the owner stop order, no live server was touched. Owed after
coordinator clearance, in the live agent on real tasks:

- IG2-MEM-01/02/03: live extreme-condition verification — real
  write/read/promotion cycle against the live Memora service,
  restart-persistence check, oversized/poisoned-memory failure case —
  one evidence entry per item; any item that fails live gets a named
  fix task, not a verified mark.
- claude-mem leg: one real Forge build captured end to end (needle
  kinds visible in the live session index, one sensitive observation
  withheld in the live timeline), plus the failure case (Memora down
  → Oracle outbox spool, replayed).
- agentmemory leg: one live recall-outcome cycle (a served memory
  reported useful → stored confidence rises on the live service;
  a served-but-unused one falls), plus the compress→promote bump
  observed on a live digest.
- Open Viking: live trial of the server (or a documented refusal to
  run it, if the AGPL + vendor-model grounds stand — the trial is
  evidence for the judgement, not a second chance for adoption).

## 6. Files changed (this PR)

| File | Change |
| --- | --- |
| `Memora/core/memory/session_needles.py` | New: needle classifier + L0/L1/L2 session index |
| `Memora/core/memory/confidence_reinforcement.py` | New: confidence reinforcement + weighted sort |
| `Memora/core/memory/capture_service.py` | Needle classify on capture; index + weighted sort in inject pack; promotion bump on compress |
| `Memora/apps/api/routers/v1_capture.py` | New endpoints: `GET /v1/capture/sessions`, `POST /v1/capture/recall-outcome` |
| `Memora/adapters/forge/adapter.py` | New: `ForgeAdapter.record_session_observation()` |
| `Memora/tests/test_mem031_memora_verify_wave3.py` | New: 14 tests |
| `Forge/app/integrations/memora_client.py` | New: `a_record_session_event` / `record_session_event` + outbox fallback |
| `Forge/app/cli.py` | Call site: build outcome captured as session event |
| `Forge/app/agents/roles.py` | Call site: code-synthesis outcome captured as session event |
| `Forge/tests/unit/test_mem031_forge_session_capture.py` | New: 6 tests |
| `.github/workflows/friday-universe-ci.yml` | Both new test files in the tier-1 lists |
| `docs/collaboration/WORK_BOARD.yaml` | Board flips (see §7) |
| `docs/collaboration/TASK-MEM-031-MEMORA-VERIFY-WAVE3.md` | This file |

No secrets pasted anywhere; no generated PDF/docx; no paid services;
stdlib-only new Memora code; no live-fleet change.

## 7. Board flips (ride in this PR)

- **TASK-MEM-031** AVAILABLE → CLAIMED (owner muse_2, branch
  `muse2/task-mem-031-memora-verify-wave3`, pr this PR).
- **TASK-MEM-030** CLAIMED → MERGED — work PR #1772, merged
  2026-11-25 11:15:56 IST by Surendra, merge `8fa84c61`, CI 10/10
  green on head `afd6ff73` (verified first-hand via the API this run).
- **TASK-MEM-029** — NO flip in this PR: the board on main already
  reads MERGED (updated 2026-11-25 10:13:18 IST; work PR #1765,
  merge `c4267ca1`, verified first-hand via the API this run). The
  brief's IN_REVIEW → MERGED flip had already landed before this
  branch was cut.

## 8. Five states

- Implemented: YES (repo-implement leg; this PR).
- Tested: YES (20 new tests; repo CI verdict below).
- Merged: NO (awaiting peer merge).
- Deployed: NO (needs coordinator clearance).
- Production-verified: NO (live legs gated — see §5).

— Muse 2
