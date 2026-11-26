# TASK-VYR-079 — Checkpoint 1: repo-side scoping (2026-11-24 ~23:25 IST)

**Task:** TASK-VYR-079 — REPO-IMPLEMENT: VyralX repos — OpenFilm (adapt),
Nextwork AI Video Editor cooked (adapt), OpenVoice (adapt), LongCat-Video
(reject), MoneyPrinterTurbo (adapt) — target VyralX, wave 1. P1.

**Claim:** hub #1483 comment 7139812148; branch
`musetp2/task-vyr-079-repo-implement-wave1` from main `6e3fe049`.
Board verified first-hand this run: AVAILABLE / owner null / P1, no blockers.
No claim PR — claim is the hub comment + branch, per WORKER_PROMPT §3.
Board flip rides in the work PR.

**State:** implemented (scoping) / tested (registry read first-hand) /
merged NO / deployed n/a / production-verified NO.

## 1. The five repos — identified from the in-repo registry

Source: `IntelX/intelx/registries/scouted_repos.json` (102 verified cards;
read first-hand this run). No repo was identified from a web search — all
five come from the registry, with the URLs below copied verbatim from it.

| Repo (board name) | Registry slug | Fit | Licence |
|---|---|---|---|
| OpenFilm | `openfilm/openfilm` | adapt | MIT |
| Nextwork AI Video Editor cooked | `nextwork-projects/ai-video-editor-cooked` | adapt | MIT |
| OpenVoice (MyShell / MIT) | `myshell-ai/OpenVoice` | adapt | MIT |
| LongCat-Video + Avatar 1.5 (Meituan) | `meituan-longcat/LongCat-Video` | reject | MIT |
| MoneyPrinterTurbo | `harry0703/MoneyPrinterTurbo` | adapt | MIT |

- **OpenFilm** — open-source AI video agent: a coding agent writes a film as
  plain web pages (`film.html`, tracks cut from pages/footage/stills/sound,
  each shot a `frame(t)` function) and renders to MP4 via headless Chromium +
  FFmpeg. Ships Studio, a local browser editor with a real timeline.
  Constraint (registry): rendering is headless-Chromium work — too heavy to
  run inside a ~180 MB service on the ~956 MB fleet VMs; run renders on the
  owner's machine or post-ARM, with VyralX orchestrating.
- **Nextwork AI Video Editor cooked** — a Claude Code plugin (also Codex,
  Cursor, Gemini CLI, Copilot) that edits a talking-head video in the style
  of a liked creator: raw clip + 3–6 reference videos sharing one format; it
  measures cut speed, zooms, captions, cards, graphics and sound into a
  saved, reusable style, then cuts retakes/false starts/pauses.
  Constraint: built around Claude Code; README states a Claude account with
  a paid plan or an API key is needed to drive it.
- **OpenVoice** — instant voice-cloning audio foundation model (MIT/MyShell):
  extracts tone colour from a short reference clip and applies it to speech
  in multiple languages/accents, zero-shot cross-lingual cloning. V2 adds
  MeloTTS. Constraint: PyTorch model with separately downloaded checkpoints
  — cannot run on the fleet; run on the owner's hardware.
- **LongCat-Video** — Meituan 13.6B-parameter foundational video model
  (text/image-to-video, continuation); Avatar 1.5 turns audio (+ text, +
  optional reference image) into lip-synced talking-character video.
  Reject on hardware alone: needs a datacentre-class GPU (40 GB card in
  independent testing) and multi-GB weights; the fleet is two ~956 MB-RAM
  VMs with no GPU, and the free-only rule rules out renting GPU generation
  as a default.
- **MoneyPrinterTurbo** — one-stop AI short-video generator: topic/keyword
  → LLM script (Gemini, DeepSeek, Qwen, Groq, OpenRouter, local Ollama) →
  stock footage (Pexels/Pixabay/Coverr or local media) → voiceover
  (Microsoft Edge TTS built in — free, no API key) → burned-in subtitles.
  Closest off-the-shelf match to what VyralX's autopilot already does.
  Constraint: requires Python 3.11+ while the fleet runs Python 3.10.

## 2. VyralX tree (main `6e3fe049`, first-hand)

- 420 tree entries under `VyralX/`; `VyralX/app/` 180 entries:
  `agents/`, `api/`, `data/` (incl. `thumbnail_templates/`), `services/`.
- `VyralX/tests/` 114 entries.

## 3. Existing in-repo touchpoints (already on main — adapt starts here, not from zero)

- `VyralX/app/services/openvoice_gate.py` (129 lines) — OpenVoice gate.
- `VyralX/app/services/mpt_lane.py` (714 lines) — MoneyPrinterTurbo lane.
- `VyralX/app/agents/real_money_printer.py` (357 lines).
- `VyralX/app/services/film_pipeline.py` (155 lines) — render pipeline
  (OpenFilm / HyperFrames pattern neighbour).
- `VyralX/app/services/short_video_assembly.py` (220 lines) — assembly
  (Nextwork measured-style neighbour).
- Tests: `VyralX/tests/test_ig2_vyr07_openvoice_gate.py`,
  `VyralX/tests/test_ig2_vyr_mpt_lane.py`,
  `VyralX/tests/test_ig2_vyr05_film_pipeline.py`,
  `VyralX/tests/test_ig2_vyr08_short_video_assembly.py`.

## 4. Plan (per repo, in board order)

1. **OpenFilm (adapt):** read the existing film pipeline + HyperFrames
   usage; prove the HTML-as-video pattern runs in VyralX's live path with
   one real end-to-end use incl. a failure case (e.g. missing footage /
   bad `frame(t)`), with the heavy render leg run where the registry says
   it can run — never claimed as fleet-run if it is not.
2. **Nextwork cooked (adapt):** extract the measured-style workflow into a
   reusable style profile applied to VyralX footage with staged human
   approval; prove one real end-to-end use incl. a failure case; record the
   Claude-account constraint honestly — no paid path is used or promised.
3. **OpenVoice (adapt):** drive the existing `openvoice_gate.py` through
   one real end-to-end use (reference clip → cloned narrator voice on a
   real short) incl. a failure case; record where inference actually ran.
4. **LongCat-Video (reject):** live evidence, not a paper judgement —
   trial or guardrail proof of absence from every VyralX production path,
   plus the hardware bound stated with the numbers above.
5. **MoneyPrinterTurbo (adapt):** drive `mpt_lane.py` /
   `real_money_printer.py` through one real end-to-end use (topic →
   script → voice → stock footage → captioned short) incl. a failure
   case; record the Python 3.11 vs fleet 3.10 bound honestly.

Each repo gets its evidence filed per repo; adapt entries must run in
VyralX's live production path.

## 5. Live-leg gates (stated, not assumed)

- Owner stop order (~16:42 IST 2026-11-24) still in force for moves.
  Read-only legs proceed per the 21:57 coordinator ruling.
- Live leg = a real end-to-end render/discovery cycle on VyralX-Server
  with real source videos + machine-QA under bad inputs (missing BGM,
  doubled captions, watermark) + metrics-sync against the real channel.
  Loop stays OFF, uploader paused, renders held unlisted.
- VyralX-Server route to be verified first-hand before any live leg; no
  live move without clearance. My bridge access was confirmed at
  onboarding (FRIDAY-Cloud-Engineering-Bridge v1.30.0).

## 6. Next step

Checkpoint 2: read the five touchpoint files + the registry cards in full,
then run the first adapt leg (OpenFilm pattern against `film_pipeline.py`)
repo-side, with tests.

— Muse TP2

# Checkpoint 2: OpenFilm adapt leg (2026-11-26 ~07:4x IST)

**Stall repaired:** checkpoint 1 stood ~32h with no checkpoint 2 and no
work PR — flagged by this hourly self-check (usage 4%, free allowance
remaining) and repaired by implementing the first adapt leg in this run.

**State:** implemented (OpenFilm leg) / tested (10/10 pytest, see below) /
merged NO / deployed n/a / production-verified NO.

## What was built

- `VyralX/app/services/openfilm_adapter.py` (new, stdlib only, Python
  3.10) — `validate_openfilm_film()` (OpenFilm-pattern conformance:
  well-formed `frame(t)` from the supported closed set, footage/stills
  assets resolved through the caller's `asset_exists` — a missing asset
  FAILS the film, never claimed present without a check; unchecked
  assets are reported as warnings, not passes; content, shot kinds,
  duration sums, Shorts cap re-checked) and `adapt_openfilm_film()`
  (end-to-end leg: build → render `film.html` → validate → render gate;
  a validation failure returns `status="failed"` and issues NO render
  command). Rendering stays gated off-fleet via `film_pipeline.render_gate`.
- `VyralX/tests/test_vyr079_openfilm_adapter.py` (new, 6 tests) — happy
  path end-to-end (3 shots, 15.0s, 2 assets resolved, render refused on
  fleet / allowed on owner machine); missing-footage failure names the
  asset and shot; bad `frame(t)` (unknown name, malformed, empty) fails
  with the shot named; content-less shot and unknown kind fail;
  unchecked assets warn; Shorts cap still enforced.

## Evidence (first-hand this run)

- `pytest tests/test_vyr079_openfilm_adapter.py
  tests/test_ig2_vyr05_film_pipeline.py` — **10 passed** (6 new + 4
  existing), Python 3.12.3, pytest 9.2.0 (installed `--user` for this
  run; the repo CI runs the same suite). `py_compile` clean.
- Registry card re-read first-hand: `openfilm/openfilm`, MIT, fit adapt
  (`IntelX/intelx/registries/scouted_repos.json`, 102 entries).
- Branch `musetp2/task-vyr-079-repo-implement-wave1`, base `6e3fe049`;
  behind origin/main ~741 commits at commit time (main drift, rebase
  owed before merge — coordinator route). Board on origin/main:
  CLAIMED, owner muse_tp2, pr null (work PR filed this run; board `pr`
  field rides with the coordinator board rebuild, not hand-edited from
  a stale base).

## Next step

Checkpoint 3: Nextwork cooked leg — measured-style profile against
`short_video_assembly.py`, repo-side, with tests (brief §4.2).

— Muse TP2

# Checkpoint 3: Nextwork cooked adapt leg (2026-11-26 ~12:3x IST)

**Stall repaired:** checkpoint 2 (`42c8b4bb`, 07:28 IST) stood ~5h with
no checkpoint 3 and no new commits — flagged by this hourly self-check
(usage 5%, free allowance remaining) and repaired by implementing the
second adapt leg in this run. Same yardstick the team applies to
others (Muse 4 DB-012, TP11 VYR-081 flagged at ~2h zero commits).

**State:** implemented (OpenFilm + Nextwork legs) / tested (16/16
pytest, see below) / merged NO / deployed n/a / production-verified NO.

## What was built

- `VyralX/app/services/nextwork_style.py` (new, stdlib only, Python
  3.10) — `measure_style()` (3–6 same-format references averaged into
  a reusable style profile: cut speed, mean shot length, zooms, caption
  style, cards, graphics density, sound bed; fewer than 3 / more than 6
  / mismatched formats / out-of-range measurements FAIL, never
  silently averaged), `cut_transcript()` (retakes, false starts and
  pauses dropped with reasons named; kept speech re-cut into shots at
  the style's mean shot length; an all-junk transcript FAILS),
  `build_staged_plan()` / `approve_stage()` (cut → look → render,
  in order only — out-of-order approval is an error), `render_gate()` /
  `render_command()` (Remotion rendering ~1.5 GB install stays gated
  off-fleet; a command is issued only when all three stages are
  approved AND the host is the owner machine). Paid-path honesty: the
  Claude-account constraint is recorded on every style
  (`claude_code.required_upstream` True, `used_here` False,
  `paid_services_used` False) — no Claude Code/plugin step runs, no
  key is taken, no paid path is promised.
- `VyralX/tests/test_vyr079_nextwork_style.py` (new, 6 tests) — happy
  path end-to-end (3 refs → 12.0 cuts/min, 4.0s mean shot, 18s kept
  speech re-cut into 5 shots, 7s dropped, stages unapproved, no
  render); reference bounds (2 / 7 refs, mixed formats, bad caption
  style, zero cut speed); missing raw clip fails, unchecked asset
  warns; all-junk transcript fails, unknown segment kind fails;
  stages approve in order only; render gated until approved and
  off-fleet (fleet refused, owner machine gets the `remotion render`
  command).

## Evidence (first-hand this run)

- `pytest tests/test_vyr079_nextwork_style.py
  tests/test_vyr079_openfilm_adapter.py
  tests/test_ig2_vyr05_film_pipeline.py` — **16 passed** (6 new + 6
  OpenFilm + 4 existing), Python 3.12.3, pytest 9.2.0 (fresh venv in
  /tmp for this run — the `--user` pytest from checkpoint 2 is no
  longer importable on this VM; the repo CI runs the same suite).
  `py_compile` clean.
- Registry card re-read first-hand:
  `nextwork-projects/ai-video-editor-cooked`, MIT, fit adapt
  (`IntelX/intelx/registries/scouted_repos.json`, 102 entries).
- Branch `musetp2/task-vyr-079-repo-implement-wave1`, base `6e3fe049`;
  behind origin/main ~830 commits at commit time (main drift, rebase
  owed before merge — coordinator route; no rebase demand names this
  branch in WATCH113–144). Board on origin/main: CLAIMED, owner
  muse_tp2, pr null (work PR #1787 open, updated by this push; board
  `pr` field rides with the coordinator board rebuild, not hand-edited
  from a stale base).

## Next step

Checkpoint 4: OpenVoice adapt leg — drive the existing
`openvoice_gate.py` through one real end-to-end use (brief §4.3).

— Muse TP2
