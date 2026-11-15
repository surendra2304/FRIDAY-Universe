# VyralX packaging system — remix era (TASK-VYR-005)

Packaging decides whether a finished remix gets clicked and kept: the
**title**, the **thumbnail text**, and the **hook** in the first
seconds. This system replaces the autopilot formula autopsied in
`docs/AUTOPSY_29_UNLISTED.md` — one interchangeable sensational title
for every video, a frame-grab thumbnail, no hook design, and no gate
between a render and an upload.

Code: `app/services/packaging.py` (pure, deterministic, no network).
Tests: `tests/test_vyr005_packaging.py`.

## 1. Content lanes

From the 2026-11-15 niche research (YouTube's own policy pages +
AIR/vidIQ/upGrowth RPM and view data); lanes 1–3 owner-confirmed.

| # | Lane | Sources | Why |
|---|------|---------|-----|
| 1 | `space_science` — Space & science facts | NASA/NOAA/ESA public domain, Wikimedia Commons | Zero copyright risk; education/science carries the highest measured long-form RPM; evergreen and shareable |
| 2 | `history_dyk` — History / did-you-know | Archive + Wikimedia public domain; Indian history & GK included | PD sources, curiosity-driven, global + Indian appeal |
| 3 | `tech_ai` — Tech & AI explainers | Own screen recordings first; clips only with provenance | Highest safe Shorts RPM tier; footage we create ourselves carries no claim risk |
| 4 | `money_stories` — Money stories (guarded) | PD/CC footage; VyralX-drawn charts | Stories about money (rise/fall/scams) only. **Advice is banned**: YouTube bars financial-advice content from AI personas and SEBI bars unregistered advice in India. Advice terms in a title/hook/script are a hard lint fail |

Explicitly out: anime compilations and raw gameplay re-uploads
(aggressive Content ID; named in YouTube's reused-content policy as
monetisation-ineligible), sports highlights, movie/TV compilations.

Publish in English for a global audience: Shorts revenue is allocated
per viewer country (researched figures: US ≈ $0.328/1k views vs India
≈ $0.008/1k), so packaging language targets the global feed.

## 2. Title system

Templates live in `packaging.LANES[lane]["title_templates"]`; a title
is rendered from a template with concrete slots, then must pass
`lint_title`:

* ≤ 60 characters (the feed truncates beyond it);
* ≤ 2 emoji;
* a **concrete anchor** — a number, a question, or a named subject.
  Mood-only titles ("His Reaction Says Everything") are the old era's
  defect: interchangeable across any video;
* no banned terms — globally: source-framing carry-overs
  ("Repurposed:"), engagement begging; per lane: e.g. fabricated-hype
  terms in `tech_ai`, all advice language in `money_stories`.

## 3. Thumbnail-text system

Thumbnail text is a shout, not a sentence (`lint_thumbnail_text`):

* ≤ 4 words, ≤ 24 characters;
* must **not** repeat the title's opening words — thumbnail and title
  are two different hooks for the same click;
* numbers and scale words travel well in lanes 1–2 ("100 SUNS",
  "2,000 YEARS OLD"); a question travels in lane 2 ("WHO BURIED IT?").

(Shorts also surface in feeds where the first frame *is* the
thumbnail — pick the frame at the hook moment, not a random grab.)

## 4. Hook framework (first ~2–3 seconds)

Every video opens with a hook line built from its lane's archetypes
(`build_hook`) and checked by `score_hook`:

* ≤ 12 words — speakable inside the first seconds;
* at least one **curiosity device**: a number, a question, a
  negation/secret, or a second-person address;
* the hook is a promise the video's first beat immediately starts
  paying off — the TASK-VYR-003 pipeline retimes segments to the
  voiceover beats, so the hook beat is a real, measured segment, not
  an estimate.

Archetypes per lane (examples):

* `space_science`: `scale_shock` ("Meet the largest black hole — 4
  million suns in one point."), `you_are_looking_at`, `the_shot`.
* `history_dyk`: `buried_fact` ("They didn't teach you this: …"),
  `on_this_day`, `the_photo`.
* `tech_ai`: `just_happened`, `the_test`, `nobody_talking`.
* `money_stories`: `the_fall`, `the_scam`, `the_turn`.

## 5. Pre-publish checklist

`prepublish_checklist(candidate)` returns every gate's verdict; a
candidate is publishable only if **all** gates pass, and a missing
measurement is a **failed** gate, never a skipped one (the autopsy's
central lesson: `VIDEO_METRICS` sat empty for 46 videos).

| Gate | Source | Rule |
|------|--------|------|
| `provenance_record_complete` | TASK-VYR-004 | source URL, author, licence, retrieval date all recorded |
| `license_allowed` | TASK-VYR-004 | licence is a recognised PD/CC/owner-owned licence — the old blanket "operator policy" string **fails** |
| `original_commentary_present` | TASK-VYR-004 / reused-content policy | script ≥ 40 words and voiceover present — commentary is the product |
| `sync_beats_retimed` | TASK-VYR-003 | max per-beat \|segment − voiceover\| ≤ 0.25s (proof render: 0.00s) |
| `sync_caption_mean` | TASK-VYR-003 | caption mean \|offset\| ≤ 0.15s (proof: 0.025s) |
| `sync_caption_max` | TASK-VYR-003 | caption max \|offset\| ≤ 0.50s (proof: 0.413s) |
| `sync_narration_coverage` | TASK-VYR-003 | narration covers ≥ 98% of runtime (broken era: 73.6%) |
| `duration_under_claim_block` | YouTube policy | if the material could be claimed, keep the Short < 60s (claimed Shorts ≥ 60s get blocked) |
| `packaging_title` | this system | `lint_title` passes for the lane |
| `packaging_thumbnail_text` | this system | `lint_thumbnail_text` passes |
| `packaging_hook` | this system | `score_hook` passes |

## 6. Measurement contract (so the next autopsy isn't blind)

Per published video, the pipeline must record — in the tables that
already exist — the publish job id, YouTube video id, lane, title,
hook archetype used, and the sync measurements from the checklist;
and once YouTube API access exists (owner re-auth + valid Data API
key), a metrics job must populate `VIDEO_METRICS` (views, likes,
comments) on a schedule. Selection must record its reasoning too:
source query, source video id, and score — the three fields that sat
empty for all 46 autopilot projects.
