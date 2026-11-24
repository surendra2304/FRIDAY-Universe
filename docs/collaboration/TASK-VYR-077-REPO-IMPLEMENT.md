# TASK-VYR-077 — REPO-IMPLEMENT: VyralX repos (wave 1) — Checkpoint 1 (repo-side scoping)

- Task: TASK-VYR-077, P1, REPO-IMPLEMENT VyralX repos, wave 1.
- Claim: hub issue #1483 comment 7139661577 (2026-11-24 ~23:15 IST). Branch `musetp3/task-vyr-077-repo-implement-wave1` from main `6e3fe049`.
- Board verified first-hand this run: main `6e3fe049`, TASK-VYR-077 AVAILABLE / owner null / P1, branch null, pr null. No competing claim on the hub through the latest read (938 comments). Pool order: Wave 1 Stratex fully spoken for (coordinator watch 22:17 IST); VYR-077 is the first free Wave 1 VyralX task (VYR-070 M10, VYR-071 M5 pre-staged, VYR-072 M14, VYR-073 M14 pre-staged, VYR-074 M4, VYR-075 M7, VYR-076 M9).
- State: implemented NO, tested NO, merged NO, deployed NO, production-verified NO. Checkpoint 1 only: scoping.

## Scope (board record)

- Adapt: Short Video Factory, AI YouTube Shorts Generator.
- Reference-only: Social Media Agent / LangChain, Lemo-Opuscar, MG Styles 15, Claude Animation Base.
- Target: VyralX.
- Acceptance: adapt entries must run in VyralX's live production path, proven by one real end-to-end use incl. a failure case; reference-only entries need live evidence (trial or guardrail proof of absence from every production path), filed per repo. Live leg: real end-to-end render/discovery cycle on VyralX-Server with real source videos + machine-QA under bad inputs (missing BGM, doubled captions, watermark) + metrics-sync against the real channel; loop stays OFF, uploader paused, renders held unlisted.

## VyralX structure (verified from live main tree, 6e3fe049)

- VyralX has 436 tree entries; top level: `app/`, `docs/`, `scripts/`, `tests/`.
- `VyralX/app/` has 188 entries. Entry points: `app/main.py`, `app/config.py`, `app/database.py`, `app/media_store.py`.
- Render / caption / audio services relevant to the two adapt repos: `app/services/captions.py`, `app/services/audio_mixer.py`, `app/services/film_pipeline.py`, `app/services/full_pipeline_engine.py`, `app/services/discovery.py`, `app/services/generated_footage.py`, `app/services/format_clone.py`, `app/services/format_templates.py`.
- Docs: `VyralX/README.md` (12,354 bytes), `VyralX/docs/ARCHITECTURE.md`, `VyralX/docs/OPERATIONS.md`, `VyralX/docs/BGM_SHELF.md`.
- No code has been changed yet. No adapt component has been wired into any production path yet.

## Repo scouting (in progress)

- The six scouted repo names come from the board record only; no source URLs were in the board record, and no URLs are claimed here.
- Scouting is running in parallel (public GitHub search, authenticated as surendra2304, plus web search as fallback): exact owner/name, license, stars, key components, and whether the core runs without paid keys, per repo. Results will be filed here as Checkpoint 2, with only URLs returned by the search tools — no invented URLs.
- Reference-only judgements will not be paper-only: each needs a live trial or a guardrail proof of absence from every production path, filed per repo.

## Live leg — BLOCKED (bridge pending)

- The VyralX-Server live leg cannot run yet: the Oracle bridge link is still pending via secure entry flow (asked Surendra 2026-11-24 ~23:16 IST; GitHub PAT is already connected and verified, so it was not asked for again). No bridge, no fleet shell, no CREDENTIALS.md read.
- Loop stays OFF, uploader paused, renders held unlisted, per the task. No deploys without Muse clearance.
- Repo-side work proceeds first: scouting, adapt design against the services above, local trial with no paid keys where possible. The live end-to-end leg and machine-QA under bad inputs will be posted as blocked until the bridge arrives — not assumed.

## Usage

- 0% of free weekly limit (checked this run; reset Mon Nov 30, 3:03 PM IST). Additional tokens 0% used.

— Muse TP3
