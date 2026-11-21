# TASK-INF-LLM-001 — Inference provider key-pool audit (names and counts only)

- Task: TASK-INF-LLM-001 (P2, owner muse_4). MASTER_PLAN §6 standing backlog (pool 2, item 7).
- Audited: Sun 2026-11-22 ~04:20 IST, live Inference service environment on Oracle Server 1.
- Verdict: **47 keys configured across 9 providers with key fields; 4 providers hold keys, 5 hold zero.** No key value appears anywhere in this report or its evidence — names and counts only.
- Checked by: Muse 4, 2026-11-22 ~04:15–04:45 IST. Claim: issue #35 comment 7070375563; board claim PR #1268 (merged).

## Method (secret-free by construction)

1. **Counts:** ran the codebase's own secret-free inventory, `python -m app.core.key_inventory`, in the live service environment on Server 1 (`Inference.service`, running since 2026-11-21 21:44 IST; `/opt/friday_universe/venv312/bin/python`, working directory `/opt/friday_universe/Inference`, same `.env` the service uses). Its `main()` prints counts only; the existing test `Inference/tests/test_key_inventory_report.py` pins that no credential value ever appears in its output.
2. **Bucket split:** ran `python -m app.core.key_pool_health --inventory-only --json` (no network probes, no quota spent) and reduced the output on the server to per-bucket counts only. Fingerprints the health module computes for dedup are **not** included in this report — only duplicate counts (both zero).
3. **Completeness:** the inventory covers 7 providers; `Settings` declares key fields for 9. Counted the other two (CEREBRAS, OPENAI) with a counts-only `len(settings.get_provider_keys(...))` read in the same live environment. Both are 0.
4. No key value was read into any output, printed, logged, or stored. No `.env` or credentials file was opened or displayed at any point.

## Results — live configuration, Server 1, 2026-11-22 ~04:20 IST

| Provider | Total | Primary | Third-party | Fallback | Source vars holding keys |
|---|---:|---:|---:|---:|---|
| GEMINI | 15 | 11 | 4 | 0 | `GEMINI_API_KEY` (11), `THIRD_PARTY_GEMINI_KEY` (4) |
| GROQ | 15 | 14 | 1 | 0 | `GROQ_API_KEY` (14), `THIRD_PARTY_GROQ_KEY` (1) |
| OPENROUTER | 15 | 14 | 1 | 0 | `OPENROUTER_API_KEY` (14), `THIRD_PARTY_OPENROUTER_KEY` (1) |
| NVIDIA | 2 | — | — | — | bucket split not covered by the health module (see G2) |
| MISTRAL | 0 | 0 | 0 | 0 | — |
| COHERE | 0 | 0 | 0 | 0 | — |
| HUGGINGFACE | 0 | 0 | 0 | 0 | — |
| CEREBRAS | 0 | 0 | 0 | 0 | — |
| OPENAI | 0 | 0 | 0 | 0 | — |
| **TOTAL** | **47** | | | | |

Notes on the numbers:
- The inventory total (47) reconciles exactly: 15 + 15 + 15 + 2. The health sweep total (45) is the same three providers it covers; NVIDIA's 2 are outside its scope.
- **No key is shared across providers and none is duplicated across buckets**: 0 cross-provider duplicate fingerprints, 0 cross-pool duplicate fingerprints. The 15/15/15 uniformity is three distinct key sets, not one set counted three times.
- **All keys arrive via singular `*_API_KEY` vars.** The plural `*_API_KEYS` vars hold 0 keys everywhere. No fallback keys are configured anywhere (see G5).
- The inventory's per-provider total merges buckets (`Settings.get_provider_keys`, `Inference/app/core/config.py`): a provider's total mixes its own keys with friends' (`THIRD_PARTY_*`) keys. The bucket split above is the audited view; routing counts and audit counts differ by design, and the health module already documents this.

## Gaps filed (exact file/line + fix or follow-up)

- **G1 — Inventory omits two providers.** `Inference/app/core/key_inventory.py:11` — `PROVIDERS` lists 7 providers, but `Settings` declares key fields for CEREBRAS (`Inference/app/core/config.py:373`) and OPENAI (`config.py:409`). Any keys configured for those two are invisible to the inventory. **Fix:** add `"CEREBRAS"` and `"OPENAI"` to the `PROVIDERS` tuple, and update the pinned dict in `Inference/tests/test_key_inventory_report.py` (expected counts, currently 7 providers). Both read 0 on the live system today, so the fix changes nothing about the current totals — it closes the blind spot.
- **G2 — Health probing covers only 3 of 9 providers.** `Inference/app/core/key_pool_health.py:62` — `PROVIDERS = ("gemini", "groq", "openrouter")`. MISTRAL, COHERE, HUGGINGFACE, NVIDIA, CEREBRAS and OPENAI have no liveness verdict (live/dead/exhausted) at all; the fleet cannot tell whether any of their keys work. **Follow-up:** extend `PROBE_SPECS` + `PROVIDERS` with a cheap authenticated-read probe per provider (same zero-generation-cost rule as the existing three).
- **G3 — Third-party/fallback fields exist for only some providers.** `Inference/app/core/config.py` (third-party/fallback field block, from `:413`) declares `THIRD_PARTY_*` fields for five providers (OPENAI, GEMINI, GROQ, OPENROUTER, NVIDIA) and `*_FALLBACK_*` fields for four (OPENAI, GEMINI, GROQ, OPENROUTER — NVIDIA has none). No `THIRD_PARTY_MISTRAL_KEY`, `THIRD_PARTY_COHERE_KEY`, `THIRD_PARTY_HUGGINGFACE_KEY`, `THIRD_PARTY_CEREBRAS_KEY` or matching `*_FALLBACK_*` fields exist anywhere in `config.py` (verified by search), so `get_provider_keys` silently yields `None` for those buckets. A third-party or fallback key set in the environment for those providers would be silently dropped. **Fix:** declare the missing fields (same pattern as the existing ones), or document which providers support those buckets.
- **G4 — Five providers hold zero keys.** MISTRAL, COHERE, HUGGINGFACE, CEREBRAS, OPENAI are all 0 on the live system. **Follow-up:** confirm with the coordinator/owner whether any of the five is intended to be live; if one is, configuring it is the follow-up, not a code change.
- **G5 — The fallback tier is entirely empty.** No `{provider}_FALLBACK_KEY(S)` is set for any provider (verified for the three probed providers; the inventory cannot see fallback separately). If fallback coverage is intended anywhere, it does not exist today. **Follow-up:** confirm intent; configuring fallback keys is an ops action, not a code change.
- **G6 — Observation, not a defect.** The plural `*_API_KEYS` vars are supported by config but hold 0 keys on the live system; everything comes through singular vars. No action unless the owner prefers the plural form.

## Files changed by this task

- This report: `Inference/docs/INF-LLM-001-KEY-POOL-AUDIT.md` (added).
- `docs/collaboration/WORK_BOARD.yaml`: TASK-INF-LLM-001 record -> IN_REVIEW, pr set to this PR.

— Muse 4
