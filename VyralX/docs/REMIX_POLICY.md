# VyralX Remix Policy — sourcing, transformative edit spec, compliance checklist

TASK-VYR-004 · Owner direction 2026-11-15: build videos out of other people's
videos (less editing, real footage), after generated-image videos were
rejected. This document is the governing policy for that flow; the code is
`app/services/remix_flow.py`, driven by `scripts/run_remix_flow.py`.

**The rule of thumb: the borrowed video is the evidence, not the product.
The channel's commentary is the product.**

## 1. Sourcing policy — what may be used

Only material the channel may lawfully and safely reuse:

| Source class | Status |
|---|---|
| Creative Commons **CC0 / Public Domain** | ✅ allowed |
| **CC BY** | ✅ allowed, with attribution |
| **CC BY-SA** | ✅ allowed, with attribution; share-alike obligation noted in the provenance record |
| Owner's own uploads | ✅ allowed |
| **CC BY-NC** (any NC variant) | ❌ forbidden — NonCommercial licences bar use on a monetised channel |
| **CC BY-ND** (any ND variant) | ❌ forbidden — NoDerivatives licences bar remixes outright |
| Anything with no licence metadata / all rights reserved | ❌ forbidden |

### Provenance is mandatory

Every evaluated source gets a **provenance record** in the append-only
registry (`data/remix_provenance.jsonl`): source page URL, media URL,
author, licence name + URL, licence class, the allow/reject decision with
its reason, and the retrieval date. **No provenance record = not a
candidate**, and the produce step enforces this in code
(`ProvenanceRecord.require_candidate`).

### Where discovery runs

Keyless sources only, until the owner supplies a valid YouTube Data API key:

- **Wikimedia Commons** — API search with per-file licence metadata.
- **Internet Archive** — advanced search + per-item `licenseurl`.
- **NASA image/video library** — U.S. Government works are public domain.

YouTube's own Creative Commons search exists, but the Data API route needs
a valid `YOUTUBE_DATA_API_KEY` — the deployed key is invalid and
CREDENTIALS.md contains none (TASK-VYR-003, live-tested). When the owner
supplies one, a YouTube-CC adapter joins this list under the same
provenance rules. **Pexels is unavailable-by-design** (the owner reports it
has stopped issuing API keys) and is not a source for this flow.

## 2. Excluded formats — never source these

- **Anime compilations (Naruto etc.)** — aggressively Content-ID'd, and
  compilations are expressly named in YouTube's reused-content policy as
  monetisation-ineligible. Strike risk on top.
- **Straight gameplay re-uploads** — the same reused-content category.
  Gameplay is survivable only inside heavy original criticism / review /
  ranking commentary, and even then it is claim-prone (revenue may go to
  the rights holder). That format is **out of scope for this flow** and
  needs a separate coordinator decision before anyone builds it.
- **Sports, Bollywood and movie compilations** — same claim/strike profile
  as anime: rights holders police them aggressively and compilations are
  the reused-content policy's named example.
- **Financial advice** — YouTube policy makes AI-persona financial
  guidance / investment tips non-monetisable, and SEBI bars unregistered
  specific advice in India. Money content exists in this flow only as
  storytelling (Lane 4 below), never as advice.
- **Straight re-uploads of anything**, however licensed, without the full
  transformative edit below.

## 3. Content lanes (researched ranking, coordinator 2026-11-15)

Ranked from a sourced research pass (YouTube's own policy pages +
creator-economy data: AIR / vidIQ / upGrowth):

1. **Lane 1 — space & science facts/mysteries** over NASA/NOAA and other
   public-domain footage. Narration IS the format; evergreen; English /
   global audience. Recipe: 40–60s, 1–2/day, extreme-fact hook in the
   first 0–3s, 3 escalating narrated facts, payoff + loop ending; mix
   one-fact, Top-5 and mission-story formats. (Education/science also
   carries the highest measured long-form median RPM, $10.22.)
2. **Lane 2 — history & 'did you know' facts**, including Indian history /
   GK, over archive / Wikimedia / public-domain footage. Recipe: 45–70s,
   1/day, rotating Top-5 countdown / story / one-fact formats. Per-file
   licence checks are mandatory, and the script must be original synthesis
   — reading Wikipedia aloud is a named YPP ban.
3. **Lane 3 — tech & AI explainers** over the channel's OWN screen
   recordings plus short launch/demo clips used for critical review.
   Recipe: 40–60s, weekdays, result-first hook, demo + verdict.
4. **Lane 4 — money content as STORIES only** (rise/fall, scams —
   storytelling), never advice (see §2). The five *Money in 40 seconds*
   scripts may be used only where they are pure education/story, and each
   must be re-checked against the advice line before any use — prescriptive
   trading guidance ("keep leverage low", "practise on demo first") does
   not pass. (Finance Shorts also had the lowest median views — 32K — in
   an 869-Short Indian sample, which is why this lane is last.)

**Audience rule:** publish in English for a global audience. Shorts
revenue is allocated per viewer country — AIR 2025 measured US Shorts RPM
at $0.328/1k vs India at $0.008/1k (~41×), so India-only traffic cannot
carry the channel's income target.

## 4. Transformative edit spec — every remix, no exceptions

A remix stays inside YouTube's reused-content policy only if it adds
significant original value. Every video from this flow must have **all** of:

1. **An original script** written for this video, not the source's own
   words — and never a reading of a Wikipedia article (a named YPP ban).
2. **Original voice-over commentary** as the primary audio (channel voice,
   per-beat synthesis). A source that already has narration is skipped —
   two voices never overlap.
3. **A re-cut structure**: the source is split into scene beats that are
   retimed to the commentary (speed / freeze-pad / trim), never a straight
   re-upload of the original edit.
4. **Captions from the finished audio** (faster-whisper word timestamps
   aligned to the script — the TASK-VYR-003 path), never estimated timings.
5. **On-screen additions** from the channel renderer: vertical 1080×1920
   reframing, colour grade, burned captions.
6. **Attribution in the description**: source title, author, licence name
   + URL, and the source page URL (`build_remix_metadata` generates it).

## 5. Per-video compliance checklist

`remix_flow.compliance_checklist` evaluates this list for every render and
stores the result in the review-queue entry:

- [ ] Source is CC / public-domain / owner-owned, with a provenance record on file
- [ ] Licence permits derivatives and commercial use (no NC, no ND)
- [ ] Original script + original voice-over commentary is the primary audio (source audition passed: no source narration)
- [ ] Source re-cut into scene beats retimed to the commentary (not a straight re-upload)
- [ ] Captions aligned to the finished audio (Whisper word timestamps)
- [ ] Runtime under 60 seconds — a claimed Short over 1 minute is BLOCKED, not just claimed
- [ ] Attribution in the description: author, licence, source URL
- [ ] Format is not an excluded lane (no anime/gameplay/sports/Bollywood/movie compilations, no finance advice, no straight re-uploads)
- [ ] Language and targeting: English, global audience (India-only Shorts traffic pays ~41× less)
- [ ] Declared format recorded — structure varies across the declared formats (one-fact / Top-5 / story / countdown); template-identical mass volume risks 'inauthentic content' demonetisation
- [ ] Held for owner review — this flow never uploads

## 6. Review queue — nothing uploads from this flow

Renders land in `data/remix_review_queue.jsonl` with status
`pending_review` (plus a `pending_approval` publish job when produced with
`--with-db`). Uploading additionally requires the YouTube OAuth credential,
which is currently **dead** (`invalid_grant` — TASK-VYR-003); uploads are
impossible until the owner re-auths.

## 7. What this flow still needs from the owner

1. **A valid YouTube Data API v3 key** — unlocks YouTube-CC discovery at
   scale (the keyless sources above work without it).
2. **YouTube OAuth re-auth** — required before anything can upload again;
   publishing the OAuth consent screen out of Testing status prevents the
   7-day refresh-token expiry that killed the current credential.

Everything else — discovery, provenance, download, remix, render, review
queue — works without him.
