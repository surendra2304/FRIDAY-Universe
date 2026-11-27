# TASK-VYR-076 — Live trial evidence (2026-11-26)

REPO-IMPLEMENT: VyralX repos, wave 1, P1. This document records the live
leg: the two IG2 adapt modules (`audio_content.py`, `pipeline_orchestration.py`)
exercised on VyralX-Server, the fleet-side weights check, the §8.3 guardrail
re-verification, and the wiring decision. Design context:
`TASK-VYR-076-ADAPT-DESIGNS.md` (§2.3, §3, §5, §8.2, §8.3).

Authority: FOLLOW-UP DIRECTIVE (Muse, Head Manager, 2026-11-26) — full
`run_shell` through the Bridge; live legs previously held on clearance are
unblocked. The owner stop order on server MOVES stands (none attempted);
live-money actions remain owner-only (none attempted). Nothing was
published; all outputs are unlisted/on-host only.

## §1 Route and host verification

- Route: Server 2 (`friday-universe-vnic-2`, bridge host) →
  `ssh -i ~/.ssh/Oracle-Cloud-x-AWS-Key ubuntu@13.211.162.71`.
  Candidates from the credentials-file hostname tokens were probed by
  hostname/service: `13.211.162.71` = **VyralX-Server** (hostname
  `ip-172-26-12-48`); `32.236.185.237` = IntelX-Server; `13.211.78.20` =
  Stratex-Server; `15.134.130.145` = FRIDAY-Server.
- On VyralX-Server: `VyralX.service` **active**; `127.0.0.1:8010/health`
  → **200**.
- Modules present and **byte-identical to main** (`df4e261b`):
  - `VyralX/app/services/audio_content.py` — 7,913 bytes,
    sha256 `26eb005aefcc14d350da1bb0448ce512485253bebd5a878a6e4fd1dcbba34ca6`
  - `VyralX/app/services/pipeline_orchestration.py` — 9,245 bytes,
    sha256 `2fa28757addbfca98d0e29da35d41a418eee04d4d1b0e6542d6d0d2b15bc1459`
- Both import cleanly with the service venv Python **3.10.22**:
  `ig2-vyr01-1` / `ig2-vyr02-1`. `edge-tts` **7.3.1** in the venv;
  `ffmpeg` **6.1.1** on the host.
- The host carries a deployed copy, not a git checkout (`git rev-parse`
  fails there); the version record is the hash equality above.

## §2 Design A trial — `audio_content.py` (Podcastfy pattern)

Real source: Wikipedia "James Webb Space Telescope" plain-text extract
(63,618 chars, fetched on the host via the Wikipedia action API).
Lane `space_science`, mode `short`, provider `edge`
(voices `en-US-AriaNeural` / `en-US-GuyNeural`). The module built the
dialogue script + TTS segment plan; Edge TTS rendered each segment with
the service venv; ffmpeg stitched one MP3. `publish: false`,
`privacy_if_published: unlisted` throughout.

Four runs (the module behaved identically in all four; only my source
sentence selection changed):

| Run | Source words (4 sentences) | Estimated | Actual (ffprobe) | Verdict |
|---|---|---|---|---|
| v1 | 219 (78/51/40/50) | 1.84 min | 111.984 s (1.87 min) | below the 2–5 min window |
| v2 | 456 (78/72/73/233) | 3.42 min | 268.152 s (4.47 min) | in window, but the 233-word "sentence" was the article's External-links list — degenerate chunk |
| v3 | 78 (1 sentence) | 0.75 min | 44.52 s | prose filter too strict (my selection bug) |
| **v4** | **279 (78/56/72/73)** | **2.24 min** | **154.92 s (2.58 min)** | **pass case: in window, clean prose** |

v4 pass-case record (companions in `vyr076-live-trial/`):

- 10 dialogue turns (host_b intro/prompts, host_a source sentences, outro);
  transcript filed (`design_a_transcript.txt`).
- 10/10 TTS segments rendered; ffmpeg concat rc 0.
- Episode: `/opt/friday_universe/VyralX/data/vyr076_live_trial/design_a_v4/episode.mp3`
  on VyralX-Server — 929,757 bytes, 154.92 s,
  sha256 `841e5ac954d40f9b905a15800817ca9c92eba59dff297f7af205f88e24bfd137`.
  The MP3 is filed on the live host (path + hash above, re-checkable by
  the verifier); transcript, manifest and logs are filed in this repo.
- Manifest filed (`design_a_manifest.json`): `execution: batch_offline`,
  `resident_service: false`, `paid_services_used: false`.

Failure cases (each shows its error; `design_a_failure_log.json`):

- Empty source → `AudioContentError: source_text produced no sentences`
- Paid provider → `AudioContentError: TTS provider 'openai' is paid; free paths only ('edge', 'gemini')`
- Finance-advice source → `AudioContentError: dialogue blocked by finance-advice screen: [{'pattern': 'direct recommendation to the viewer', 'matched_text': 'You should buy'}, {'pattern': 'promised returns', 'matched_text': 'guaranteed returns'}]`

## §3 Design B trial — `pipeline_orchestration.py` (OpenMontage pattern)

One real manifest run: pipeline `explainer_short`, lane `space_science`,
topic "James Webb Space Telescope". All 9 stages completed
(`research → script → storyboard → assets → voice → compose → quality →
approval → publish_plan`), `final_state: complete`, `publish: false`.
Companions: `design_b_run_manifest.json`, `design_b_gate_log.json`.

- **Provider scoring ($0 default budget):** `edge_tts_free` selected;
  `paid_cloud_tts` ineligible ("cost $0.40 exceeds budget $0.00");
  `local_gpu_video_gen` ineligible ("requires GPU (fleet has none)").
  Paid-only candidate list refused:
  `OrchestrationError: no eligible provider within budget $0.00: [...]`
- **Storyboard approval gate:** advancing without approval refused —
  `OrchestrationError: storyboard approval gate: a human must approve the storyboard before production stages run`
  — run state unchanged; with `approved=True` the run proceeded.
- **Quality gate refusal:** bad artifact (75 s > 59 s cap, no captions,
  no provenance) refused —
  `OrchestrationError: quality gate failed: {'passed': False, 'checks': {'duration_within_cap': False, 'captions_present': False, 'provenance_present': False}, 'pipeline': 'explainer_short'}`
  — run state unchanged; a passing artifact then completed the stage
  with its gate record stored on the run.
- **Finance-advice script gate:** `passed: false`,
  `no_finance_advice: false` for prescriptive-advice text.
- **Missing-BGM probe — honest finding:** an otherwise-passing video
  artifact with `has_bgm: false` **PASSED** the gate
  (`passed: true`; checks run: `duration_within_cap`,
  `captions_present`, `provenance_present`). The gate as coded in
  `pipeline_orchestration.evaluate_quality_gate` has **no BGM check** —
  the §3 design rule ("a missing-BGM render must FAIL the gate") is not
  implemented in the IG2 gate. Filed as a wiring-decision gap (§6), not
  dressed up as a pass.
- Render stages `voice`/`compose` are `off_fleet` by design: the state
  machine advanced them; **no render was attempted** on the resident
  service. What ran on-fleet is exactly: planning, scoring, gating,
  approval — the manifest layer.

## §4 Fleet-side weights check (FLUX.2 / ACE-Step corroboration)

On VyralX-Server: `find /opt/friday_universe -iname "*.safetensors" -o
-iname "*flux*" -o -iname "*ace-step*" -o -iname "*acestep*"` → **zero
hits**. No FLUX or ACE-Step weights/binaries on the VyralX host,
corroborating the repo-side guardrail (§5) for this host.

## §5 Guardrail re-verification vs main `df4e261b`

§8.3 method repeated verbatim (`git grep`, same patterns):

| Pattern | Scope | Result |
|---|---|---|
| `scrapecreators`, `social.media.research` | VyralX prod paths excl. tests | 0 files |
| `opencreator`, `codex-cli` | VyralX prod paths excl. tests | 0 files |
| `flux\.2` | whole repo | 3 files: registry, checkpoint-1 doc, board |
| `FLUX2` | whole repo | 4 files: registry, IG test name-list, INT-044 tracker, checkpoint-1 doc |
| `flux-2`, `flux_2`, `acestep` | whole repo | 0 files |
| `ace-step` | whole repo | 5 files: registry, IG test name-list, INT-044 tracker, checkpoint-1 doc, board |
| `podcastfy`, `montage` | VyralX `pyproject.toml` / `requirements.lock` | 0 hits |
| IG2 module imports | whole repo | only the two IG2 test files |

**§8.3 stands unchanged.** Zero VyralX production hits for all four
reference-only/reject repos; zero Python imports of the IG2 modules from
any production file (the two known prose mentions —
`channel_strategy.json`, `SCENE_ASSEMBLY_EVALUATION.md` — unchanged).

## §6 Wiring decision (recorded, not silently taken)

What was exercised: both modules, standalone, on the live VyralX host,
against the deployed byte-identical copies, with real source material,
real TTS, real gates, and filed failure cases.

What remains unwired: everything. Neither module is reachable from any
VyralX route or the live app (zero production imports, §5). Wiring them
into a live route is a separate decision for the coordinator — **not
done here**, and no production route was touched.

Findings for that decision:

1. **Missing-BGM check absent** from `evaluate_quality_gate` (§3). Any
   wiring that relies on the §3 gates must add the BGM check (and the
   captions single-track / watermark checks, which are likewise not in
   this gate) before the gate can be trusted for machine-QA.
2. **Dialogue is a deterministic template** (source sentences chunked
   into alternating turns). An LLM rewrite pass is a batch-runner
   concern upstream of the module, per its own docstring.
3. **Short-mode duration sensitivity:** short mode uses exactly 4 source
   sentences (10-turn cap), so the 2-minute floor depends on source
   sentence length — v1 missed it at 219 source words; v4 cleared it at
   279. A production runner should select/verify source length.
4. **No new dependencies:** both modules run on the fleet's Python 3.10;
   `edge-tts` is already a VyralX dependency. The batch/offline shape
   (manifest → off-resident execution) matches the ~180 MB service cap.

## §7 Five states (honest, per the implementation standard)

- **implemented:** the IG2 modules were implemented on main before this
  task (TASK-IG2-VYR-01/02 pattern ports). This task added the designs,
  the guardrail proof, and live evidence — no new production code.
- **tested:** YES — live trials on VyralX-Server (§2, §3) with pass and
  failure cases filed; guardrail re-verified (§5); weights check (§4).
- **merged:** NO — this PR.
- **deployed:** the modules are present on VyralX-Server byte-identical
  to main (verified, §1) — a pre-existing deployment; trial artifacts
  are on the host. No service was changed or restarted by this task.
- **production-verified:** NO — the modules remain unwired (§6); they do
  not run in VyralX's live production path. Production verification
  requires the wiring decision plus a real end-to-end use through the
  live path, which is the coordinator's call.

— Muse 9
