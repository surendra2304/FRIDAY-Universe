# TASK-VYR-076 — Adapt designs: Podcastfy + OpenMontage (repo-side work, 2026-11-25 ~03:00 IST)

REPO-IMPLEMENT: VyralX repos, wave 1, P1. Branch work only — NO PR yet (owner
order 7143628341 rule 1: one work PR per task, opened when DONE or genuinely
BLOCKED). Live legs HELD under the owner stop order; this file is the repo-side
design leg. Verifier (watch057): Muse 5 — starts when the work PR opens.

## §1 Upstream reads — verified first-hand (shallow clones, read-only)

| Repo | Upstream HEAD | What was read |
|---|---|---|
| souzatharsis/podcastfy | `053b54a0917e35edb2808049499292361ccaae7b` | README.md (194 lines), pyproject.toml, requirements.txt, podcastfy/config.yaml, podcastfy/conversation_config.yaml, usage/config.md, podcastfy/tts/providers/ (edge, elevenlabs, gemini, geminimulti, openai) |
| calesthio/OpenMontage | `2e003e65fa99a0f329478a2c1cdcf26bc481933a` | README.md (776 lines), config.yaml, requirements.txt, pipeline_defs/*.yaml (13 pipelines), docs/PROVIDERS.md, skills/ layout (core, creative, meta, pipelines + INDEX.md) |

No upstream code copied into this repo. Designs below borrow patterns and
interfaces only. Licence care: Podcastfy Apache-2.0; OpenMontage AGPL-3.0 —
any future code reuse stays internal and licence-noted; nothing built from it
is distributed.

## §2 Design A — Podcastfy → VyralX audio / repurposing lane (batch job)

### Borrowed pipeline (upstream shape, verified)

1. **Content extraction** — `content_parser`: website (via `r.jina.ai`),
   YouTube (transcript), PDF, or a user-supplied topic.
2. **Transcript → dialogue** — `content_generator`, default
   `gemini-2.5-flash` (max 8192 output tokens); Langfuse-hosted prompt
   templates with pinned commits: `podcastfy_multimodal_cleanmarkup`
   (`b2365f11`), longform (`acfdbc91`), cleaner (`8c110a0b`), rewriter
   (`8ee296fb`).
3. **Dialogue shaping** — `conversation_config.yaml`: two hosts
   (main summarizer + questioner/clarifier), structure Introduction → Main
   Content Summary → Conclusion, engagement techniques (rhetorical questions,
   anecdotes, analogies, humor), longform max 8 chunks, min 600 chars/chunk.
4. **Text → speech** — `text_to_speech` provider switch (see §2.1).

### §2.1 Free-path correction — upstream-verified, changes the registry picture

The registry says the "Gemini-only (`geminimulti`) TTS, one Gemini key" path
is free. Upstream `usage/config.md` proves it is **allowlist-gated**: Google
multi-speaker voices are only available to allowlisted projects, requesting
access needs a paid Google Cloud support subscription and a support case, and
an unallowlisted project fails at runtime with
`RuntimeError: Failed to generate audio: 403 Multi-speaker voices are only
available to allowlisted projects`. So:

- **Free-now path:** Gemini transcript (fleet Gemini key, free tier) +
  **Edge TTS** (`edge-tts`, no key, free) — the only no-key TTS provider in
  the repo. Local-LLM transcript is the zero-key alternative (see
  `usage/local_llm.md`, not yet read).
- **Trial-only path:** `geminimulti` — attempt only to record the 403 (or a
  pass if the fleet key happens to be allowlisted); do NOT build on it.
- **Excluded (paid):** default OpenAI TTS (`tts-1-hd`, voices echo/shimmer)
  and ElevenLabs (`eleven_multilingual_v2`, voices Chris/Jessica).

### §2.2 Why not adopt as-is (confirmed blockers)

- Python `^3.11` (pyproject + every requirements marker `>=3.11, <4.0`);
  fleet is Python 3.10 — cannot import as-is on the fleet.
- FFmpeg required plus heavy deps (`google-cloud-aiplatform`, etc.); the
  audio workload will not fit a ~180 MB service cap on ~956 MB VMs.
- **Shape: batch job, not a resident service.** One-shot process on
  VyralX-Server (or post-ARM / off-fleet) per source item: in = source
  URL/topic + conversation config; out = transcript + MP3, filed in a
  `data/transcripts` + `data/audio` layout (or VyralX's equivalent). No
  change to VyralX's publish path: output stays UNLISTED, loop OFF.

### §2.3 Live-trial plan (HELD — needs Muse clearance)

- **Pass case:** one real 2–5 min two-host audio from a real source
  (article or video), Edge TTS, transcript + audio filed as evidence.
- **Failure cases (at least one filed):** empty/missing source URL
  (extractor failure); YouTube transcript unavailable; `geminimulti` 403
  (allowlist proof); FFmpeg missing on the trial host; a chunk under the
  600-char minimum. Each failure must show the error, not a silent pass.

## §3 Design B — OpenMontage → VyralX production-system patterns (borrow, don't install)

### Borrowed patterns (file-level, verified)

- **Pipeline manifest shape** (`pipeline_defs/*.yaml`): name, version,
  description, orchestration (`mode: executive-producer`, stage-director
  skill), `budget_default_usd`, `max_revisions_per_stage`,
  `max_send_backs`, `max_wall_time_minutes`, `required_skills` per stage,
  and per-stage `checkpoint_required: true` +
  `human_approval_default: true` + `review_focus` + `success_criteria`.
  Template: `podcast-repurpose.yaml` v2.0 (budget $1.00, 3 revisions/stage,
  3 send-backs, 12-min wall time; 8 stage-director skills + `meta/reviewer`
  + `meta/checkpoint-protocol`).
- **Stage-director split:** idea / script / scene / asset / edit / compose /
  publish directors, each producing a schema-valid artifact consumed by the
  next stage. VyralX adopts the split and the artifact handoffs, not the
  skill files themselves.
- **Budget governance** (`config.yaml`): `mode: observe | warn | cap`,
  `total_usd: 10.00`, `reserve_pct: 0.10` (holdback for retries/cleanup),
  `single_action_approval_usd: 0.50`,
  `require_approval_for_new_paid_tool: true`. VyralX adopts the same fields
  on its render jobs, with `mode: cap` (FREE-only rule: a job that would
  spend is refused, not warned).
- **Scored provider selection** (`docs/PROVIDERS.md` table): every provider
  carries a price and a free tier; the $0 rows are Piper (offline TTS — no
  key, no network), local video gen ($0 + GPU: WAN/Hunyuan/CogVideo/LTX),
  and Google TTS free tiers (1M Standard + 1M WaveNet + 1M Neural2 chars/mo,
  independently). VyralX's provider choice copies the scoring table, with
  paid rows excluded by the cap above.
- **Retrieval-first montage** (`documentary-montage.yaml` v1.0): semantic
  corpus from Pexels / Archive.org (Prelinger) / NASA / Wikimedia Commons /
  Unsplash, CLIP-based retrieval into slot descriptions, music sync, uniform
  color grade. Two of its rules map directly onto VyralX's machine-QA:
  **music plan is MANDATORY** (silent only on explicit opt-out) and **end-tag
  plan is MANDATORY** — a missing-BGM render must FAIL the gate, never pass
  silent.
- **Storyboard approval gate** (Backlot concept: a living storyboard board
  server, FastAPI/uvicorn): in VyralX terms, a manifest-approval checkpoint
  before any render job runs; renders held unlisted.

### Not adopted (confirmed)

- Full stack: Node.js 22.23.4+ (README line 180), Remotion / HyperFrames
  headless rendering, optional Blender, GPU-only local video generation —
  far exceeds ~956 MB VMs and ~180 MB/service caps.
- Core Python deps are light (pyyaml, pydantic, jsonschema, Pillow, numpy,
  requests + FastAPI Backlot), but the render path is what breaks the fleet
  budget, not the manifest layer. Borrow the manifest/gate layer only; run
  any real OpenMontage-style render off-fleet or post-ARM.

### Quality gates for VyralX (from this design)

- **Pre-render:** source present; BGM present-or-explicit-opt-out; captions
  single-track check; watermark scan.
- **Post-render:** duration sane; audio present; caption-duplication check.
  These cover exactly the board's machine-QA bad inputs: missing BGM,
  doubled captions, watermark.

### Live-trial plan (HELD — needs Muse clearance)

- **Pass case:** one real end-to-end render on VyralX-Server driven by a
  borrowed manifest (idea → script → scene → assets → edit → compose) with
  the §3 gates applied and the gate log filed.
- **Failure case:** a missing-BGM input must be refused/failed by the
  pre-render gate with the refusal logged — proving the gate fires, not
  that rendering merely works.

## §4 Reference-only / reject — live-trial designs (guardrail proof)

Per the board acceptance a paper judgement is NOT a result. Where no trial is
possible, the evidence is a **scripted guardrail proof of absence** from every
VyralX production path (dependency lists + import/call search, filed as
evidence — not an assertion):

| Repo | Design |
|---|---|
| Social Media Research Skills (reference-only) | No trial: the only data layer is the paid ScrapeCreators API (100 free lifetime credits, then pay-as-you-go) — breaks FREE-only. Guardrail proof of absence + the 13 skill workflow designs read as reference for hook/competitor jobs. |
| OpenCreator (reference-only) | No trial: desktop-first Codex-CLI workspace, paid third-party model APIs. Guardrail proof of absence; reference pattern only (transcribe → translate subtitles → dub → portrait render). |
| FLUX.2 (reject) | No trial: hardware + licence. Guardrail proof — no FLUX weights/API on the fleet (no GPU, no 8 GB VRAM, no H100; only 4B weights Apache-2.0, 9B/[dev] non-commercial). |
| ACE-Step 1.5 (reject) | No trial: hardware alone (smallest ~4.7 GB weights, needs VRAM). Guardrail proof — no ACE weights on the fleet. |

## §5 What remains (live legs HELD)

- VyralX-Server is live (coordinator watch058 probe: `VyralX.service`
  running, port 8010 answers 200) — the server is NOT the blocker. The only
  gate is Muse's clearance under the owner stop order (requested in
  checkpoint 1, hub 7143189048; no ruling through watch058).
- When clearance lands: run Design A trial + Design B trial + §4 guardrail
  checks, then open the SINGLE work PR (rule 1) with the live evidence;
  board flip rides in that PR (rule 4). Verifier Muse 5 starts then.
- If clearance is refused: the task is genuinely BLOCKED — open the single
  work PR with these designs + the refusal as the block evidence.

## §6 VyralX grounding — repo AGENTS.md, read first-hand 2026-11-25

The designs above map onto VyralX modules that already exist (not hypothetical
ones). VyralX: port 8010, server 2, Python FastAPI; shared fleet venv Python
3.10.12 — confirming the Podcastfy ^3.11 blocker at fleet level.

- `workflow_manager.py` — content workflow orchestration **with approval
  gates**. This is where the OpenMontage storyboard-approval gate and the
  per-stage `human_approval_default` land: no new gate framework, extend the
  existing one with the manifest checkpoint (§3).
- `app/services/real_media_routes.py` — unified multi-modal `/growth-pack`
  already orchestrating ClaudeAds, TopRank, OpenHiggsfield, **Hyperframes**,
  DiagramDesign. OpenMontage's HyperFrames composer is therefore not a new
  dependency — the borrowed manifest/compose pattern plugs into an existing
  Hyperframes route.
- `content_accessibility_enhancer.py` — accessibility improvements with
  auto-captioning. The caption single-track check and the doubled-captions
  QA case belong here.
- **FFmpeg rendering, stock-footage assembly and YouTube OAuth upload are
  real** (AGENTS.md caveats) — so the documentary-montage retrieval-first
  pattern has a real assembly path on VyralX. **The upload daemon creates
  private drafts** — "renders held unlisted" is already the daemon's
  behaviour, not a new control to build.
- **Trial-design constraint:** analytics dashboards, localization reports,
  influencer ROI and monetization scores are hash/keyword heuristics, **not
  measured platform data**. The board's metrics-sync leg must therefore use
  measured platform data from the real channel, never the heuristic
  dashboards, or the sync proves nothing.

## §7 States (reported separately)

- implemented: NO — no component runs in VyralX's live path yet.
- tested: NO — no live trial run yet.
- merged: NO — no work PR open (checkpoint-1 PR #1708 merged pre-rules).
- deployed: NO.
- production-verified: NO.
- Usage: 42% of free weekly limit (checked this run; reset Nov 29 02:27 IST;
  additional tokens 0%). Under the Wed 20:00 IST 50% bar — next task scope
  doubles per rule 6 unless usage rises.
- INT-023 final compilation (due 2026-11-27) remains mine but BLOCKED
  (INT-032 timer uninstalled; IntelX has no running home) — unchanged.

— Muse 9
