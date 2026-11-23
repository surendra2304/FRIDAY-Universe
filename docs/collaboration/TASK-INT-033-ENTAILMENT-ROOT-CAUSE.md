# TASK-INT-033 — synthesis_entailment_unverified: root cause + fix

**Worker:** Muse 9. **Claim:** issue #1483 comment 7102901933, 2026-11-23 ~19:12 IST, on coordinator assignment in watch12 (comment 7102801241) filing INT-033 → muse_9 (lag-hunt re-slot; board PR #1504, not yet merged at claim time). **Branch:** `muse9/task-int-033`. **Base:** main ecc401a.

**Status:** implemented YES / tested YES (local, see §5) / merged NO / deployed NO / production-verified NO — the fix is code + tests in the work PR; deployment to live IntelX (S2) and the live re-probe need coordinator clearance after merge (see §6).

## 1. The blocker as observed

Every live research run on 2026-11-22 → 2026-11-23 is DEGRADED with
`synthesis_error.reason: synthesis_entailment_unverified` (11/11 runs;
INF-026 deploy evidence 2/2, INT-023 interim evidence 11/11). Synthesis
transport is healthy — the draft reaches Inference and returns HTTP 200 —
but IntelX's entailment screen rejects the draft and the run falls back
to unsynthesised raw findings. INT-020 run 3 (Muse 7) waits on a green
synthesis.

## 2. Root cause — three tokenisation defects, not missing support

Live probe, 2026-11-23 ~19:12 IST (read-only; one live Inference
completion through the service's own gateway; no writes, no restart).
The archived run `lr_6d6a7103193348adb29bd4e8` (query "latest AI model
releases", 2026-11-23 09:00:29 IST) was read back from the IntelX
archive, its 5 sources re-fetched (all HTTP 200), the source documents
rebuilt exactly as `collect_live_brief` builds them, and the real
gateway (`qwen/qwen3.8-27b`) asked to synthesise from them. The draft
came back with all three quotes verbatim-verified — and still degraded.
Per-finding `statement_support` results on the real draft:

| Finding | Statement (abridged) | Quote gate | Entailment | Failing reason |
|---|---|---|---|---|
| 0 | "…include GLM-5.4 from Z.ai and Gemini 4 Neon from Google." | pass | FAIL | `unsupported_entity:Google.` |
| 1 | "Anthropic released Claude Fable 5.2 and Claude Mythos 5.2 on November 9, 2026." | pass | pass | supported |
| 2 | "OpenAI released GPT-6.2 Astra and GPT-6.2 Sol on November 17, 2026." | pass | FAIL | `unsupported_entity:GPT-6.2` |

The three defects, all inside `statement_support`
(`IntelX/intelx/api/grounded_live_research.py`):

1. **Trailing sentence punctuation is glued to the entity token.**
   `_WORD_RE = [A-Za-z][A-Za-z0-9&.'-]*` swallows the sentence-final
   period, so the statement-final entity is checked as `"Google."`.
   The source — concatenated calendar-table cells — contains no literal
   `"Google."` substring, so the check fails. The period is
   punctuation, not part of the entity.
2. **Unicode punctuation is not normalised.** The source page spells
   model names with a U+2011 non-breaking hyphen (`GPT‑6.2`); the model
   writes an ASCII hyphen (`GPT-6.2`). The byte-exact substring check
   treats them as different entities.
3. **The coverage leg requires exact token-vocabulary membership while
   the source text is concatenated table cells.** The extractor joins
   table cells without spaces (`GLM-5.4Z.aiGeneral`,
   `NeonGoogleGeneral`), so the source vocabulary holds glued tokens
   that never equal the statement's clean words. On the captured draft,
   finding 0 scored 5/10 under the old coverage rule (missing `latest`,
   `include`, `glm-5.4`, `neon`, `google.`) — every one of those words
   is present in the source as a substring. The entity leg already uses
   substring containment; the coverage leg did not.

**Amplifier:** the gate is whole-draft fail-closed — one finding failing
any leg degrades the entire draft. With 3 findings per draft and
hyphenated model names endemic to this topic (`GPT-6.2`, `GLM-5.4`,
`Claude Opus 4.7`), at least one artifact failure per draft is the
normal case, which is why the failure is systematic (11/11) rather
than flaky.

**Correction to an earlier claim:** the INT-023 interim evidence says
the failure happens "because the findings are single-source". That is
wrong as a mechanism. Probe A showed the 5 documents form no
near-duplicate clusters (each is its own cluster), and
`statement_support` never consults the single-source flag at all:
`single_source: True` is a per-finding property by construction (each
finding cites exactly one source). Single-source is a separate
corroboration concern, not the cause of this failure.

## 3. The fix

`IntelX/intelx/api/grounded_live_research.py`, `statement_support`
only — no threshold, prompt, budget or gate-semantics change:

- Normalise unicode punctuation (dashes U+2010–U+2014/U+2212, curly
  quotes, non-breaking spaces) to ASCII on **both** sides before any
  comparison.
- Strip trailing sentence punctuation (`.-'`) from entity tokens
  before the substring check (and run the sentence-furniture check on
  the stripped token).
- Coverage leg: content-word containment by substring against the
  normalised source text, instead of exact token-vocabulary
  membership. The 0.80 threshold and the content-word definition
  (length ≥ 4, not a stopword) are unchanged.

**Why this cannot weaken the gate:** each change is a strictly
false-negative repair. Normalisation is applied identically to both
sides (substring relations are preserved under a per-character map);
stripping only shortens the needle (if `"Google."` was a substring,
`"Google"` is too); substring containment is a superset of token
membership. No previously-passing statement can newly fail. Invented
numbers, invented entities and Bruker-style absent content still fail
— the existing rejection tests pin that (see §5).

Verified against the captured live draft (probe D, same documents,
same supplied slices): finding 0 `unsupported_entity:Google.` →
`supported` (coverage 9/10 — `latest` is the only miss, the calendar's
first 6000 chars carry no `latest` substring); finding 1 stays
`supported`; finding 2 `unsupported_entity:GPT-6.2` → `supported`
(coverage 6/6). The whole captured draft passes all three legs, so the
same draft returns SUCCESS instead of DEGRADED.

## 4. What changed

- `IntelX/intelx/api/grounded_live_research.py` — `_normalize_text`
  helper + `statement_support` comparison fixes (see §3).
- `IntelX/tests/test_int005_verification_pass.py` — 4 regression
  tests: sentence-final entity, U+2011 hyphen entity, glued-table
  coverage, and the exact captured live draft end-to-end through
  `synthesize_grounded` (all three probe-B statements and quotes,
  verbatim). No new test file, so no contracts-workflow change is owed.

## 5. Tests (local, this run)

- `IntelX/tests/test_int005_verification_pass.py`: **13/13 pass**
  (9 baseline + 4 new). Before/after proof: the 4 new tests **fail on
  the pre-fix code** (verified via `git stash`: 4 failed) and pass with
  the fix.
- `IntelX/tests/test_int009_verification_gaps.py`: **14/14 pass**.
- Neighbour suites touching the same modules
  (`test_int011_canonical_projection.py`,
  `test_owner_briefing.py`, `test_rel038_intelx_honesty_persistence.py`,
  `test_source_diversity.py`): **42/42 pass**.
- Root suites `tests/test_grounded_research_synthesis.py`,
  `tests/test_grounded_live_research.py`,
  `tests/test_live_research_task_contract.py`: **17 failed / 32
  passed, identical failure sets on clean main and with the fix**
  (verified by diffing the sorted FAILED lists). Pre-existing local
  environment failure, not caused by this change: under the root
  `tests/conftest.py` path order, `routers` resolves to
  `Memora/apps/api/routers` (which has no `universal_crawler`) instead
  of `IntelX/routers`, so any test transitively importing
  `intelx.api.router` dies with `ModuleNotFoundError`. Not fixed here
  — it is shared test infrastructure, out of this task's scope; filed
  below as a follow-up for the coordinator's pool.
- Live code check: the S2 deployed `grounded_live_research.py` and
  `live_research_task.py` are byte-identical to main (sha256 match),
  and the deployed file carries the 14,000-char INF-026 budget — the
  probe results apply to the live code.

## 6. What remains (not in this PR)

- **Work PR review + merge** (coordinator / peer).
- **Deploy to live IntelX (S2) + live re-probe** — needs Muse's
  clearance on the hub before any deploy, per standing orders. The
  re-probe is a fresh `research_live` run on the same query through
  the live path; SUCCESS (synthesised brief) is the production
  verification, and it unblocks INT-020 run 3 (Muse 7). The deploy
  itself is a restart of IntelX.service with the merged checkout; no
  config or env change.
- **Follow-up (new, for the coordinator's pool):** root-test
  `routers` shadowing — `tests/conftest.py` inserts `Memora/apps/api`
  ahead of `IntelX`, so `import routers` resolves to Memora's package
  and root contract tests importing `intelx.api.router` fail locally
  (and, by the same conftest, wherever that path order applies).
  Candidate fix: insert `IntelX` ahead of the Memora entries, or make
  the IntelX router import absolute. Not attempted here: shared test
  infrastructure, needs a coordinator decision.
- **Queue:** per the board record as filed in #1504, Muse 9's queue is
  INT-023 → REL-086 → INT-033 — i.e. REL-086 is listed ahead of
  INT-033. INT-033 was taken first because watch12 filed it as the
  lag-hunt re-slot (Muse 3 held it from 16:25 IST with no claim or
  branch after the 17:35 and 17:50 demands) and it unblocks INT-020's
  blocked head lane; this ordering is stated here so the coordinator
  can redirect if REL-086-first was intended. REL-086 is next for
  Muse 9 after INT-033 either way.

## 7. Evidence index

- Claim: issue #1483 comment 7102901933.
- Probes (read-only, S2, service venv python): probe A (archive +
  rebuild + clustering), probe B (real draft capture + failing legs),
  probe C (candidate fix, partial — finding 0 still failed on
  coverage), probe D (full fix — all 3 findings pass). Probe scripts:
  `~/workspace/friday-bridge/int033_probe_{a,b,c,d}.py` (kept in the
  local workspace, not the repo).
- Live archive run: `lr_6d6a7103193348adb29bd4e8`, DEGRADED,
  `synthesis_entailment_unverified`, 5 sources / 15 findings.
- Local test runs: §5 (venv `~/workspace/tmp/muse9_int033_venv`,
  `PYTHONPATH=IntelX`, pytest).

— Muse 9
