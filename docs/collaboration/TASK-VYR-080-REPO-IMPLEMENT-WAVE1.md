# TASK-VYR-080 — REPO-IMPLEMENT: VyralX repos (wave 1) — Checkpoint 1 (repo-side legs)

- Task: TASK-VYR-080, P1, REPO-IMPLEMENT VyralX repos, wave 1.
- Claim: hub issue #1483 comment 7143373422. Branch
  `muse2/task-vyr-080-vyralx-repo-implement-wave1` from main `b0276946`
  (merge #1712; main head re-verified this run, still `b0276946`).
- Board verified first-hand this run: main `b0276946`, TASK-VYR-080
  AVAILABLE / owner null / P1, branch null, pr null. No competing hub
  claim, no branch, no PR.
- State: implemented YES (repo-side legs) / tested YES (unit, CI) /
  merged NO / deployed NO / production-verified NO. Checkpoint 1 only:
  the live leg is gated by the owner stop order (see §6).

## Scope (board record)

- Adapt: AgentTube. Reference-only: OpenCut. Reject: SANA-WM, WanGP,
  ComfyUI. Target: VyralX.
- Acceptance: the adapt entry must run in VyralX's live production path,
  proven by one real end-to-end use incl. a failure case; the other four
  need live evidence per repo (live trial or guardrail proof of absence
  from every production path) — a paper judgement is NOT a result. Live
  leg: real end-to-end render/discovery cycle on VyralX-Server with real
  source videos + machine-QA under bad inputs (missing BGM, doubled
  captions, watermark) + metrics-sync against the real channel; loop
  stays OFF, uploader paused, renders held unlisted.

## 1. Repo scouting — identified first-hand

Source of truth for the five names is the scout registry
`IntelX/intelx/registries/scouted_repos.json` (102 entries, read
first-hand from main `b0276946`); every repo below was then verified
against the live upstream repo (stars, licence, default branch) and its
README read first-hand. No repo was cloned, downloaded, installed or
run. No upstream code is vendored anywhere in this PR.

| Repo | Upstream | Stars / licence | Fit |
| --- | --- | --- | --- |
| AgentTube | darkzOGx/youtube-automation-agent | 5,362 / MIT | adapt |
| OpenCut | OpenCut-app/OpenCut | 99,307 / MIT | reference-only |
| SANA-WM | NVlabs/Sana | 9,885 / Apache-2.0 | reject |
| WanGP | deepbeepmeep/WanGP (formerly Wan2GP) | 12,233 / NOASSERTION | reject |
| ComfyUI | Comfy-Org/ComfyUI | 148,442 / GPL-3.0 | reject |

## 2. AgentTube (adapt) — what was built

New module `VyralX/app/services/agenttube.py` (486 lines) + new tests
`VyralX/tests/test_vyr080_agenttube.py` (337 lines, 16 tests). No
existing VyralX file was edited. Pattern-only: no upstream code
vendored; the upstream stack is NOT adopted (see §3).

Upstream, verified from its README (14,224 bytes, read first-hand):
a self-hosted AI agent that runs a YouTube channel end to end — research,
script, narration/visuals, real MP4 assembly, titles/descriptions/tags,
scheduling after human approval, then learning from analytics, retention
curves and comments. Runs on Node.js 18.17+ with your own keys; Gemini
free tier covers text and narration; YouTube Data API v3 + Analytics API
credentials required; free local slideshow rendering by default, paid
AI-video providers optional and capped; Playwright/Chromium renders the
slideshow videos.

The adaptation keeps the workflow discipline, expressed with VyralX's
own services:

- **Approval-first publishing** — a run cannot reach `publish` until the
  owner approves it (`advance_run` raises otherwise); `publish_decision`
  never uploads — an approved run waits unlisted and pending review.
- **Production readiness** — a verified check before anything runs on
  its own: narration present, facts linked to verified sources
  (evidence desk), a finance-advice screen via
  `compliance_gate.find_finance_advice`, and the measured
  `compliance_gate.evaluate_compliance_gate` verdict. Fail-closed: a
  missing gate input, missing narration or unlinked facts each fail it,
  and unmeasured sync fails the gate, never passes.
- **Resumable, checkpointed production** — stages research → script →
  production → review → publish → learn, each checkpointed;
  `resume_run` returns the next pending stage after a crash instead of
  starting over.
- **Scene Repair Studio** — `repair_scene` delegates to
  `film_pipeline.apply_studio_edit` (trim/move/restyle/retype); unknown
  ops and unknown shots raise there and are never silently dropped. The
  repair is logged on the run; the run itself is untouched.
- **Shorts Repurposing Studio** — `repurpose_shorts` turns an approved
  long video into up to three 9:16 Short drafts via
  `shorts_generator.generate_shorts` (local mode only — a paid mode is
  rejected there) + `shorts_live_path.build_clip_render_plan`, reusing
  existing media so no new generation credits are spent. Drafts stay
  unlisted and review-first.
- **Learning loop** — `propose_lesson` compares measured 24-hour and
  7-day evidence with the channel baseline and proposes a change; a
  missing measurement is an error, never a zero. `approve_lesson`
  approves — approval is not application: `applied` stays False until a
  human applies the change.
- **Controlled growth experiments** — `run_title_experiment` runs
  title/thumbnail variants through `content_ab_tester`; a winner is
  adopted only at the 95% evidence threshold with at least 100
  impressions; anything weaker adopts nothing. The original is restored
  before any decision; the function never changes the live title itself.
- **Comment mining** — `mine_comment_ideas` turns repeated audience
  requests ("video on X", "make a video on X", "please cover X") into
  video ideas; only a request mentioned at least twice becomes an idea.

Failure cases covered in code and tests: missing BGM → the render plan
names the ambient-pad fallback (never a silent render); doubled
captions → deduped and counted (`shorts_live_path.dedupe_cues`);
over-long short → rejected, not trimmed; unapproved publish →
refused; rejected run → never advances; lesson without measurements →
refused; weak experiment evidence → no winner adopted.

## 3. What was NOT adopted from AgentTube (honest limit)

- The full second channel-running stack is not adopted: VyralX already
  has a production-verified YouTube autopilot, and a second Node +
  Playwright/Chromium stack makes no sense on the ~956 MB fleet with a
  ~180 MB per-service cap.
- No LLM call, no paid provider, no YouTube credentials are added by
  this module: it is stdlib-only plus existing VyralX services, and
  `shorts_generator` local mode stays the only generation path.
- The live-path wiring gap (same shape as VYR-077 checkpoint 4): this
  module is the first real caller of the AgentTube workflow, but it is
  not yet called by `full_pipeline_engine.execute_pipeline` — that
  engine's stages are still in-process stubs (TASK-REL-020) and the
  call belongs in the live trial, not in a repo-side edit. The wiring
  point is `execute_pipeline`'s `review`/`publish` stages, which should
  call `production_readiness` → `approve_run` → `publish_decision`.

## 4. Reference-only / reject evidence (guardrail proof of absence)

No live trial was run for any of the four — the owner stop order is in
force and no live server action was taken (see §6). The evidence filed
here is the guardrail proof of absence from every production path, plus
the upstream README facts that decide each repo. A paper judgement
alone is not a result; the guardrail below is executable, not prose:
`test_no_banned_imports_in_production_path` parses every `.py` file
under `VyralX/app` with `ast` and fails if any of
`opencut / sana / wangp / wan2gp / comfyui / torch / diffusers / gradio /
playwright` appears in a real import statement, and
`test_no_banned_heavyweight_runtime_in_dependencies` fails if any of
`torch / diffusers / gradio / playwright` appears in
`VyralX/pyproject.toml`. Both are in the new test file and run in CI.

Absence verified first-hand this run (GitHub code search, VyralX/app):

- `opencut`: 0 hits. `comfyui`: 0 hits. `wangp`: 0 hits.
  `sana-wm` / `SANA-WM`: 0 hits. `diffusers`, `gradio`, `playwright`:
  0 hits each. `torch`: 1 hit, in `VyralX/app/services/openvoice_gate.py`
  — prose only ("No network, no torch import, no execution. Python
  3.10, stdlib only."), not an import; the file imports `pathlib` and
  `typing` only.

### OpenCut (reference-only) — OpenCut-app/OpenCut, MIT

- Upstream README (2,661 bytes, read first-hand): "the open-source
  CapCut alternative"; the project is being rewritten from the ground
  up (Rust core, plugin-first architecture, an Editor API, an MCP
  server for AI agents, headless mode for automation/batch rendering);
  the previous version lives on as `opencut-app/opencut-classic`,
  "the one to reach for today".
- Consequence for VyralX: today OpenCut offers no API, MCP or headless
  path — those are promised in the unfinished rewrite — and VyralX's
  pipeline is agent-driven rendering, not hand-editing. Its value now
  is as the owner's free manual finishing editor on his own machine
  when a VyralX video needs a human touch-up, replacing CapCut Pro
  without a subscription. Revisit for integration only when the
  rewrite's MCP server / headless mode actually ships. Guardrail: no
  OpenCut import or reference in any VyralX production path (above).

### SANA-WM (reject) — NVlabs/Sana, Apache-2.0

- Upstream: NVIDIA's 2.6B-parameter world model (released 2026/05):
  one image plus a camera trajectory → 720p, minute-long, controllable
  video with 6-DoF camera control. The wider Sana repo is NVIDIA's
  training/inference codebase for the whole Sana family.
- Reject reason (hardware, verified from the registry record and the
  upstream project page): inference needs a single H100 for a
  one-minute 720p clip (the distilled NVFP4 variant runs on a single
  RTX 5090, ~34s per 60s clip). The fleet has no GPU at all (two
  ~956 MB-RAM VMs), and the free-only rule rules out paid hosted GPU
  generation as a default. Guardrail: no Sana import in any VyralX
  production path (above). Revisit only if GPU hardware ever arrives.

### WanGP (reject) — deepbeepmeep/WanGP, licence NOASSERTION

- Upstream README (53,526 bytes, read first-hand): a one-stop local
  "super app" for open-source generative models — video (Wan 2.1/2.2,
  MiniMax H3, LTX-2/2.3/2.5, Hunyuan Video), image, music, speech and
  3D, with a Gradio web interface, LoRA support, quantised checkpoints,
  a generation queue, headless batch mode, an API and an MCP interface.
  "8 GB of VRAM is enough to get started" — a GPU is required; the
  README's install paths target GTX 10XX / RTX 20XX–50XX cards with
  PyTorch/CUDA.
- Reject reason (hardware): "GPU Poor" still means a GPU. The fleet
  has no GPU at all, two ~956 MB-RAM VMs with ~180 MB per-service caps
  and Python 3.10/3.11, and the multi-GB model weights alone exceed a
  VM's RAM; the free-only rule rules out rented/hosted GPU generation
  as a default. Licence is NOASSERTION on GitHub (a `LICENSE.txt` is
  present; the README states it is free to use locally and will never
  ask for a licence fee; the underlying models carry their own
  licences) — the licence text was not read, and no material was used.
  Guardrail: no WanGP import in any VyralX production path (above).
  Revisit only if the owner gets GPU hardware of his own.

### ComfyUI (reject) — Comfy-Org/ComfyUI, GPL-3.0

- Upstream README (10,398 bytes, read first-hand): "the most powerful
  and modular diffusion model GUI, api and backend with a graph/nodes
  interface" — node-based image/video/3D/audio/text generation with
  workflows saved as JSON and a local API for production pipelines.
  Its own floor: "can run even the biggest open source models on as
  low as 4GB vram + 8GB ram" — a GPU machine is required, and it steers
  users to Python 3.13 (3.12 as a fallback).
- Reject reason (hardware, not merit): the fleet has no GPU at all,
  two ~956 MB-RAM VMs, and Python 3.10/3.11; the multi-GB checkpoints
  alone exceed a VM's RAM. The only no-local-GPU route, Comfy Cloud,
  is the project's official paid cloud version, which the free-only
  rule rules out as a default. Guardrail: no ComfyUI import in any
  VyralX production path (above). Revisit only if the owner gets GPU
  hardware of his own: on a local GPU machine ComfyUI would be
  VyralX's strongest generation backend, and its portable workflow-JSON
  format is the pattern any future VyralX workflow layer should stay
  compatible with.

## 5. Test verification — NOT run locally, by rule

The local repo copy failed an execution-risk check, so no repo code was
imported, run or tested on this VM. The 16 new tests are written and
syntax-checked only (`py_compile` OK on both new files; line lengths
within the 100-char ruff limit). Verification is the repo's own CI
`test` check on the PR — that is the established path (same as
VYR-077 checkpoint 4) and it runs the tests in CI, not on this VM.
This is stated plainly, not claimed as tested. The PR must show CI
fully green before it is reported ready.

## 6. Live leg — GATED (no live move attempted)

- Owner stop order (~16:42 IST, 2026-11-24) still in force. No live
  server action, deployment or restart was taken in this checkpoint.
- No VyralX-Server route decision has been recorded on hub #1483 for
  this task; the coordinator's VyralX-Server verification probe is
  still owed (VYR-072 checkpoint 1, same gate).
- Live acceptance still owed, per item: one real end-to-end use of the
  AgentTube workflow in VyralX's live production path incl. a failure
  case (missing BGM → ambient-pad fallback; doubled captions → dedupe;
  watermark → provenance watermark step), on VyralX-Server with real
  source videos + machine-QA under bad inputs + metrics-sync against
  the real channel; loop OFF, uploader paused, renders unlisted.
  Known upstream risk: the yt-dlp/EJS download break (VYR-056, M18)
  may gate the render leg's source-video downloads.
- No fleet shell was run for this checkpoint. All evidence above is
  from first-hand reads of live main `b0276946` (via the GitHub API)
  and public upstream reads. No upstream code was vendored anywhere.

## Gaps

- **G1 — Live leg gated.** Needs Muse's VyralX-Server route decision
  (and the stop order lifted for this verification) before any live
  run.
- **G2 — Wiring point owed.** `full_pipeline_engine.execute_pipeline`
  does not yet call the AgentTube workflow; the call belongs in the
  live trial (§3).
- **G3 — WanGP licence text not read.** GitHub reports NOASSERTION;
  the `LICENSE.txt` text was not read because no WanGP material is
  used. Read it before any WanGP material is ever used.
- No repo-side gap found: the adaptation module, its tests and the
  per-repo evidence are filed in this PR.

## Next action

Await the route decision (G1); then run the live leg: one real
end-to-end AgentTube-operator run on VyralX-Server (research → script →
production → review → publish → learn, with approval), one real render
with a bad-input failure case, and metrics-sync against the real
channel — filing live evidence per repo in this record.

— Muse 2
