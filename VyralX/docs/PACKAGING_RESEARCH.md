# VyralX packaging research — what actually earns the click and the first 3 seconds (TASK-VYR-008)

Companion to `docs/PACKAGING.md` (TASK-VYR-005, the rules) and
`app/services/packaging_generator.py` (TASK-VYR-008, the generator that
applies this research). Researched 2026-11-15 from public sources only;
every scoring rule in the generator cites a rule id (R1–R10) defined here.

## The honest starting point

VyralX has **no packaging performance data of its own**. The TASK-VYR-005
autopsy of the 46 autopilot videos (29 uploaded unlisted, 17 failed on a
dead OAuth credential) found `VIDEO_METRICS = 0 rows` and no selection
signal recorded for any video (`trend_score 0.0`, empty trend fields).
So this research is the channel's starting prior, not a fit to its own
history — and the old era's packaging is the anti-pattern throughout:
one interchangeable formula (sensational scene description + emoji +
`#Shorts`) regardless of content, with the source creator's framing
carried over. Everything below is aimed at global-English audiences in
the three owner-confirmed lanes: **space & science**, **history /
did-you-know**, **tech & AI explainers** (plus the guarded money-stories
lane: stories only, never advice).

A second structural fact shapes everything: in the Shorts *feed* the
video autoplays — the first frame and first spoken line do the
thumbnail's job. Titles and thumbnail text earn their clicks in
**search, the channel page, and suggested surfaces**, and they decide
whether search ever learns what the video is about. Packaging is
therefore a three-part system — title, thumbnail text, first-frame
hook — and the generator scores all three as one unit.

## Findings → rules

| Rule | Finding | Evidence (public) |
|---|---|---|
| R1 | Top Shorts titles average **~49 characters**; low performers run ~30% longer. Only ~40–60 chars display in the feed; hard cap 60 in our lint. | SubSub, *YouTube Titles That Get Clicks*: 120,703 videos (70,191 Shorts) |
| R2 | **57% of top-performing Shorts titles use 1–2 emoji; only 17% of low performers do.** Emoji are visual anchors in a scrolling feed — for Shorts only; long-form shows the opposite. | SubSub, same study |
| R3 | **Front-load the subject/search phrase.** A Short that names a real query compounds search views for months; hiding the topic for mystery (TikTok-style) underperforms on Shorts because search never learns the topic. | Webeyez Shorts CTR guide; Viibeo faceless-Shorts guide |
| R4 | **Every title needs a concrete anchor** — a number, a year, a named subject. Interchangeable mood titles were the autopsy era's norm and its defect. | TASK-VYR-005 autopsy; miraflow curiosity-gap guidance |
| R5 | **Question-form titles underperform for Shorts** (they belong in the spoken hook, not the title). The generator applies a small −3 flag, not a ban. | SubSub Shorts formula ("avoid questions") |
| R6 | A **superlative with no anchor is clickbait risk**: if the first 2 seconds don't pay the thumbnail/title promise, retention dies and distribution is punished. Unanchored superlatives score −4. | x20 network analysis, 18,000 Shorts (Q1 2026) |
| R7 | Thumbnail text: **3 words maximum**, large bold sans, **yellow/white on dark** won the most tests; low contrast performs ~40% worse in suggested; focal subject in the **top two-thirds** (faces there earned +29% CTR from search). Custom thumbnails beat auto first-frames (3.2× search/suggested traffic in their network test). | x20 network analysis, 18,000 Shorts |
| R8 | **~50–60% of all drop-off happens in the first 3 seconds**; viewers decide in ~1 second; average swipe at ~5.8s; an immediate hook in the first 2s retains ~19% more viewers. The hook must be speakable in ~2–3s (≤12 words, per VYR-005). | vidIQ research via Virvid; YouTube Blog Shorts deep dive (Hoyos/Sherman, Jan 2025); Zebracat stats |
| R9 | Hook *type* matters, measured: **in-media-res 85%** 3-second retention, **result-first 78%**, **problem-statement 74%**, no hook **62%** (50-video controlled test). Distribution band: **VVSA 70–90%** = strong push, <60% = collapse (3.3B-Shorts study). | AllIn1Panel 180-day storytelling study; Paddy Galloway study via Virvid |
| R10 | **Promise alignment**: title/thumbnail must match the first 2 seconds of the video, and the curiosity loop opened at the start must be paid off at the end — a gap that disappoints trains the feed to stop showing you to that viewer. | x20 network analysis; Kompozy Shorts optimisation guide |

## Lane notes

* **Space & science** — the subject supplies the spectacle; nobody
  expects a face (69% of channels in the niche are faceless, TubeMind
  niche data, 2026-11-15). Winning title patterns measured in-niche:
  superlatives with a real anchor ("most powerful", 8.8× avg lift),
  "where did" framings (2.8×). Scale comparisons are the native hook
  ("On Venus, a day lasts longer than a year"). Accuracy is the
  moat: this audience corrects wrong numbers in the comments within
  minutes — the generator never invents a fact (missing slots degrade
  the score, they are never filled by fabrication).
* **History / did-you-know** — the native devices are the buried fact
  ("they didn't teach you this"), the dated anchor ("on this day in
  {year}"), and the story arc in one line (rise/fall in the title, the
  turn withheld for the payoff). Date/year anchors score under R4 and
  double as search terms under R3.
* **Tech & AI** — breakout titles in adjacent niches are test-shaped:
  a named tool + one job + a measured outcome ("I Tested {tool}…",
  "{tool} vs {rival}"). Fabricated benchmarks are a hard fail in this
  lane (VYR-005 banned terms: "100x", "destroyed", "kills", "dead") —
  the claim in the title must be the claim the video actually shows
  (R6/R10), and our own screen recordings are the provenance-safe
  visual source.

## What the generator does with this

`packaging_generator.generate_variants(video)` takes the video's real
facts (subject, payoff fact for the title, spoken hook fact, plus
optional question/scale/story slots) and returns exactly **three
variants** — `fact_first`, `curiosity_gap`, `scale_or_story` — each a
title + thumbnail text + first-frame hook, scored 0–100
(title 40 + thumbnail 25 + hook 35) with a per-component breakdown
citing rule ids, and gated by the VYR-005 hard lints (composed when
`packaging.py` is importable, mirrored otherwise). Scores are
**research priors, not predicted CTR** — the channel will only earn
real packaging data once uploads resume and a metrics job exists
(VYR-005 follow-up). Until then, the recommended variant is simply the
one the published evidence favours, and the other two are the A/B
alternates the research says are worth testing.

### Worked samples (generator output, 2026-11-15)

* **Space — Venus** → recommended `curiosity_gap` (76): "Why Does Venus
  Spin Backwards?" / SPINNING BACKWARDS / "Venus spins the wrong way.
  Nobody knows why." — beats `fact_first` (68) and `scale_or_story`
  (67) on hook type + curiosity device, despite the R5 question-title
  flag.
* **History — Titanic** → recommended `scale_or_story` (79): "The Night
  the Unsinkable Ship Sank in 1912" / UNSINKABLE? IT SANK / "They
  called it unsinkable. It sank in 1912." (hook 35/35, in-media-res).
* **Tech — AI exam** → recommended `fact_first` (80): "This AI Just
  Passed a Real Medical Exam ⚡" / IT PASSED / "This AI just passed a
  real medical exam."

## Sources

* SubSub — *YouTube Titles That Get Clicks: Data From 120,703 Videos* — https://www.subsub.io/blog/youtube-title-formulas-that-work
* x20 — *Why YouTube Shorts Thumbnails Matter in 2026* (18,000-Shorts network analysis) — https://blog.x20.online/why-youtube-shorts-thumbnails-matter-2026/
* Webeyez — *YouTube Shorts Click-Through Rate Optimization* — https://webeyez.com/insights/guides/youtube-shorts-click-through-rate-guide
* Virvid — *How to Get Views on YouTube Shorts in 2026* (vidIQ/Zebracat/Galloway figures) — https://virvid.ai/blog/how-to-get-views-youtube-shorts-2026-algorithm-secrets
* Virvid — *The First 3 Seconds: Hook Structures That Stop Scroll* — https://virvid.ai/blog/first-3-seconds-hook-faceless-shorts-2026
* Teleprompter — *How to Go Viral on YouTube Shorts* (YouTube Blog Hoyos/Sherman deep dive) — https://www.teleprompter.com/blog/how-to-go-viral-on-youtube-shorts
* Kompozy — *YouTube Shorts optimization tips (2026)* — https://kompozy.io/how-to/youtube-shorts-optimization-tips
* AllIn1Panel — *How Storytelling in YouTube Shorts Impacts Views* (180-day study) — https://allin1panel.com/i-tested-storytelling-in-shorts/
* Viibeo — *Faceless YouTube Shorts: The Viral Growth Guide (2026)* — https://www.viibeo.com/blog/faceless-youtube-shorts-viral-growth-2026
* TubeMind — *Space & Science YouTube niche 2026* — https://tubemind.io/advanced/niches/space-science
* ShortFast — *Faceless Space Channel playbook* — https://www.shortfast.com/niches/space
* Internal: TASK-VYR-005 autopsy (`docs/AUTOPSY_29_UNLISTED.md`) and the 2026-11-15 niche research (AIR/vidIQ/upGrowth data; owner-confirmed lanes).
