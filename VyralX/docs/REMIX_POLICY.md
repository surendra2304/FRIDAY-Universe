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
- **Straight re-uploads of anything**, however licensed, without the full
  transformative edit below.

## 3. Content lanes (coordinator steering, 2026-11-15)

1. **Priority 1 — money/finance explainers** with original commentary (the
   *Money in 40 seconds* scripts): PD/CC business, market, city and
   technology footage. The flagship lane.
2. **Priority 2 — space & science spectacle** with narration: NASA/ESA and
   other public-domain footage. Zero copyright risk, evergreen, shareable.

## 4. Transformative edit spec — every remix, no exceptions

A remix stays inside YouTube's reused-content policy only if it adds
significant original value. Every video from this flow must have **all** of:

1. **An original script** written for this video (the *Money in 40 seconds*
   scripts are the first five), not the source's own words.
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
- [ ] Attribution in the description: author, licence, source URL
- [ ] Format is not an excluded lane (no anime/gameplay compilations or straight re-uploads)
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
