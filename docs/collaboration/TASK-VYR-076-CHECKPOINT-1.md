# TASK-VYR-076 — Checkpoint 1: claim repair + scoping (2026-11-24 ~23:44 IST)

REPO-IMPLEMENT: VyralX repos — Social Media Research Skills (reference-only),
OpenCreator (reference-only), FLUX.2 (reject), ACE-Step 1.5 (reject), Podcastfy
(adapt), OpenMontage (adapt). Target VyralX, wave 1, P1.

## §1 Claim repair — what the 22:54 run left owed

The 22:54 IST work-request run claimed VYR-076 (hub #1483 comment 7139313127,
branch `muse9/task-vyr-076` created from main `3a2009b8`) but its exec result
failed a safety check, so it took no further action: no checkpoint doc, no board
edit, no work PR. This checkpoint repairs that gap.

Re-verified first-hand this run (2026-11-24 ~23:44 IST):

- Board on fresh main `28efad19` (blob `fa92f85e`, 21,025 lines): VYR-076 still
  AVAILABLE, owner null, branch null, pr null, P1. No competing claim.
- Hub #1483 tail scan (pages 185–194, comments 7139192691–7140221277): no
  competing VYR-076 claim, no instruction addressed to Muse 9. Claim comment
  7139313127 stands as the claim of record. Neighbours: VYR-075 Muse 7,
  VYR-077 Muse TP3 (checkpoints 1–5 filed), VYR-079 Muse TP2.
- Branch `muse9/task-vyr-076` rebased onto current main `28efad19`
  (fast-forward; zero local commits at claim time). Board flip
  AVAILABLE → CLAIMED rides in this work PR, per standing orders.

## §2 Registry evidence — the six repos (read first-hand)

Source: `IntelX/intelx/registries/scouted_repos.json`
(schema `intelx.scouted_repos/v1`, 102 entries, generated from 102 verified
spec cards via `IntelX/scripts/generate_scouted_repos.py`; fit counts:
adapt 40, reference-only 46, adopt 6, reject 10). All six entries target
VyralX, source video `DelZub4u74G`.

| Repo | Fit | Why (registry `fit_rationale`, condensed) |
|---|---|---|
| ScrapeCreators/social-media-research-skills | reference-only | 13 agent skills for social research (outlier posts, transcripts, competitor/ad teardown); workflow designs match VyralX's hook/competitor job. Cannot adopt: only data layer is the paid ScrapeCreators API (100 free lifetime credits, then pay-as-you-go) — breaks the FREE-only rule. |
| krillinai/OpenCreator | reference-only | All-in-one creator workspace; proven chain transcribe → translate subtitles → dub → portrait render is the reference pattern. Cannot adopt: desktop-first Codex-CLI workspace, not a headless service for a ~956 MB VM; image/video generation depends on paid third-party model APIs. |
| black-forest-labs/flux2 | reject | Hardware + licence. [klein] 4B needs ~8 GB VRAM; [dev] 32B needs H100-class. Fleet has no GPU, ~956 MB RAM, Python 3.10 (repo needs 3.12/CUDA). Only 4B weights are Apache-2.0; 9B/[dev] are non-commercial; hosted API is paid. |
| ace-step/ACE-Step-1.5 | reject | Hardware alone (clean MIT licence). Smallest config ~4.7 GB weights, needs <4 GB VRAM at best; XL 4B needs ≥12 GB VRAM. Fleet: no GPU, ~956 MB RAM, Python 3.10 (repo needs 3.11–3.12). |
| souzatharsis/podcastfy | adapt | Transcript → dialogue → TTS fits a VyralX audio/repurposing lane (article/video in, podcast-style audio out). Free paths exist: Gemini-only (`geminimulti` TTS, one Gemini key) and no-API-keys (local LLM + Edge TTS). Blockers as-is: needs Python 3.11+ (fleet 3.10); FFmpeg/audio workload will not fit a ~180 MB service cap — borrow the pipeline, run as a batch job, not a resident fleet service. Default OpenAI TTS is paid — do not use. |
| calesthio/OpenMontage | adapt | Strongest production-system pattern for VyralX: pipeline manifests, stage-director skills, scored provider selection, pre/post-render quality gates, budget governance, storyboard approval gate. Zero-API-key path is real (offline Piper TTS, Archive.org/NASA/Wikimedia footage, Remotion/HyperFrames + FFmpeg). Not adoptable as-is: full stack (Node 22+, Remotion/headless rendering, optional Blender) far exceeds ~956 MB VMs; local video generation is GPU-only. AGPL-3.0 care if anything built from it is ever distributed. |

## §3 What "implemented" requires — and what is HELD

Per the board acceptance, a paper judgement is NOT a result:

- Adapt (Podcastfy, OpenMontage): the adapted component must run in VyralX's
  live production path, proven by one real end-to-end use filed as evidence
  incl. a failure case.
- Reference-only / reject (other four): live trial, or guardrail proof of
  absence from every production path, filed per repo.
- Plus a real end-to-end render/discovery cycle on VyralX-Server with real
  source videos + machine-QA under bad inputs (missing BGM, doubled captions,
  watermark) + metrics-sync against the real channel. Loop stays OFF, uploader
  paused, renders held unlisted.

HELD — owner stop order (2026-11-24 17:26 IST, partial lift for key
architecture work, bridge work, Inference move only): all other server moves
FROZEN. The VyralX-Server render/discovery cycle is a live server move and is
HELD. Live-trial clearance requested from Muse in this run's hub status post.
Also flagged: the yt-dlp/EJS break (VYR-056) may gate the render leg, and the
VyralX-Server route is not yet granted to Muse 9 — to be requested via Muse.

## §4 Plan

- Checkpoint 2: upstream repo reads (public clones, read-only) + adapt designs
  for Podcastfy (Gemini-only TTS lane, batch-job shape) and OpenMontage
  (manifests / gates / budget governance borrowed into VyralX's pipeline);
  reference/reject live-trial designs (guardrail proof where no trial is
  possible). No live moves.
- Checkpoint 3+: live trials once Muse grants clearance under the stop order;
  render/discovery cycle on VyralX-Server with machine-QA under bad inputs.
- INT-023 final compilation (due 2026-11-27) remains mine but BLOCKED
  (INT-032 timer uninstalled; IntelX has no running home) — unchanged.

## §5 States (reported separately, per the implementation standard)

- implemented: NO — no component runs in VyralX's live path yet.
- tested: NO — no live trial run yet.
- merged: NO — this work PR not yet merged (peer merge only; never own PR).
- deployed: NO.
- production-verified: NO.
- Usage: 41% of free weekly limit (checked this run via `subscription-status
  status`; reset Nov 29, 2:27 AM IST; additional tokens 0% used).
  Not nearly exhausted — no wrap-up, no schedule changes.

— Muse 9
