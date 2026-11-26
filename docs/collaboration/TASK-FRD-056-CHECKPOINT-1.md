# TASK-FRD-056 — Checkpoint 1 (scoping) — Muse TP6 — 2026-11-26 ~02:13 IST

**Task:** TASK-FRD-056 (P1, FRIDAY REPO-IMPLEMENT wave 2): Locally Uncensored
(reference-only), Jarvis / vierisid (reference-only), Awesome Harness
Engineering (reference-only), DeepSeek Harness (reference-only), VoiceStudio
(adapt, target Voice).
**Claim:** hub 7172627840 (~01:10 IST). **Branch:**
`musetp6/task-frd-056-repo-implement` @ `70ce1089` (main at claim).
**Board on main `8abf3a94`:** AVAILABLE / owner muse_tp6 / branch null / pr null
(owner flipped by board PR #1893, merge `0bb1010ba`; CLAIMED flip + branch
ride in the work PR, per the WATCH117 note for VYR-078).
**Usage:** 15% of free weekly limit, reset Mon Nov 30 1:48 PM IST.
**Method this run:** read-only scoping via the GitHub API (scout registry,
in-repo evaluation, upstream repo checks). No repo code executed, no
server touched, no live leg attempted — owner stop order still in force.

## 1. Source of truth verified

`IntelX/intelx/registries/scouted_repos.json` on main: 102 entries,
generated from the `~/workspace/ig-references/repos/` spec cards
(wave 1 verified 2026-11-15; waves 2 + 2b verified 2026-11-16),
fit counts adapt 40 / reference-only 46 / adopt 6 / reject 10.
All five FRD-056 entries below are quoted from that registry, not
from memory.

## 2. The five legs — upstream verified live this run

All five repos exist, public, not archived (GitHub API, 2026-11-26 ~02:10 IST):

| Leg | Repo | Fit | Licence | Last push |
|---|---|---|---|---|
| Locally Uncensored | PurpleDoubleD/locally-uncensored (default `master`) | reference-only | AGPL-3.0 | 2026-11-24 |
| Jarvis | vierisid/jarvis (default `main`) | reference-only | Source-available (Jarvis SAL 2.0, RSALv2-based — NOT OSI) | 2026-11-25 |
| Awesome Harness Engineering | ai-boost/awesome-harness-engineering (default `main`) | reference-only | Other (NOASSERTION; LICENSE file present) | 2026-11-25 |
| DeepSeek Harness | deepseek-ai/deepseek-harness (default `master`) | reference-only | MIT | 2026-11-22 |
| VoiceStudio | debpalash/VoiceStudio (default `main`) | adapt → Voice | AGPL-3.0 app; default OmniVoice weights CC-BY-NC | 2026-11-25 |

## 3. Reference-only legs — what "implement" means here

No code adoption for these four; the deliverable is the applicable
patterns/lessons recorded in a FRIDAY-side record (checkpoint 2), each
traced to the registry's fit rationale:

- **Locally Uncensored** (target FRIDAY): UX patterns only — zero-config
  install, a model manager that honestly marks what fits the hardware,
  chat/create/code in one window — mapped onto the owner's laptop/phone
  client ambitions. The app itself does not fit the fleet (desktop
  local-model studio; media needs a real GPU; AGPL-3.0 would encumber
  copied code; "uncensored" is not a FRIDAY requirement).
- **Jarvis / vierisid** (target FRIDAY): self-host packaging reference
  only — one-command self-host, single default port 3142, JWT-only access
  with CLI enrollment-token flow per device, day-to-day CLI surface
  (`status`, `doctor`, `logs`, `restart`, `stop`, `autostart`, `update`,
  `export`/`restore`). Jarvis is a whole competing brain (memory vault,
  goals, workflow engine, Authority approvals); running it would duplicate
  FRIDAY, and its source-available licence bars taking the code.
- **Awesome Harness Engineering** (targets FRIDAY, Forge): a syllabus,
  not software (curated Markdown + URL-checker). Design reference for
  context compaction, permission boundaries, verification loops,
  observability, runaway-loop failure modes. Individual tools it lists
  are adopted only after their own verification.
- **DeepSeek Harness** (targets FRIDAY, Forge): design reference only —
  everything-is-a-plugin composability (including the agent loop itself),
  swappable model adapters, full session traceability, plugin
  discoverability via the `dsh-plugin` topic. Adopting it would mean
  replacing FRIDAY's harness, not extending it; it is also a local
  Node.js/pnpm developer-preview runtime, not a Python 3.10 service
  inside the ~180MB per-service caps on the ~956MB VMs, and its README
  promises compatibility-breaking changes.

## 4. VoiceStudio leg — CONFLICT, decision owed to Muse

The board acceptance says "VoiceStudio (adapt, target Voice)" and the
general acceptance requires an adapted component to run in the target
agent's live production path, proven by one real end-to-end use filed
as evidence incl. a failure case.

That leg as written conflicts with an evaluation already in the repo:
`FRIDAY/docs/VOICESTUDIO_EVALUATION.md` (TASK-IG-VOI-05) rules **do NOT
adopt into FRIDAY's live voice path**, on three grounds:

1. There is no TTS stage to fill — since TASK-VOI-009 FRIDAY's live
   voice is Gemini Live end-to-end (realtime model hears and speaks
   natively; provider contract `gemini-realtime` only). A TTS engine
   could only enter by rebuilding voice as STT → LLM → TTS, the
   pipeline shape the owner's live test #2 rejected and his standing
   rule bans (Gemini is the only AI for voice).
2. It cannot run where FRIDAY runs — desktop app driving
   inference-class local models; the Oracle servers have ~956MB RAM
   each and already rely on swap.
3. Speed — the owner's criterion is speed first (greeting ≤8s, simple
   turns 4–6s); a laptop hop plus local inference latency regresses it.

The scout card itself agrees: "Gemini Live remains FRIDAY's voice
engine; this is a TTS voice-source experiment." Licence care is
mandatory in any case: AGPL-3.0 app, default OmniVoice weights
CC-BY-NC (non-commercial — fine for private use, not for published
VyralX output or business deployment without a commercially-licensed
engine), and cloning requires the voice owner's permission.

**Decision owed (Muse):** re-scope the VoiceStudio leg to reference-only
plus the evaluation's one legitimate offline use — owner-gated re-render
of FRIDAY's fixed spoken lines (greeting, `voice_unavailable`,
`unconfirmed_*`) with a VoiceStudio-designed or owner-cloned voice,
shipped as WAVs through the normal PR path, zero live-path change —
or drop the leg. **No live adapt work started; none will start until
ruled.** If the re-scope is approved, the offline re-render itself
still needs the owner to choose a voice and judge it by ear.

## 5. Blockers and gates (unchanged)

- Owner stop order (2026-11-24 ~16:42 IST) still in force: no server
  moves, no deploy, no live-leg run until clearance. Production
  verification for any adapted component is therefore gated, same as
  every other FRD task.
- VoiceStudio live adapt: blocked on the Muse ruling in §4, not just
  on deploy clearance.
- Execution-risk flag (from the STR-086 run) stands: no repo code
  executed locally this run; scoping stayed read-only via API.

## 6. Next step

Checkpoint 2: the recorded-lessons document for the four
reference-only legs (patterns + where each maps in FRIDAY/Forge),
plus whatever the VoiceStudio ruling permits. Work PR carries the
board AVAILABLE → CLAIMED flip with the true branch.

— Muse TP6
