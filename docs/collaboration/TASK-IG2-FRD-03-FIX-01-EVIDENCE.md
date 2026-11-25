# TASK-IG2-FRD-03-FIX-01 — EVIDENCE — 2026-11-25 ~19:43 IST — Muse 15

Claim: hub #1483 comment 7163894360 (~19:01 IST), re-slotted from the pool
per WATCH099 (FRD-043 hold stands) / WATCH100 queue
FRD-043 -> FRD-054 (MERGED) -> FIX-01.
Branch: muse15/task-ig2-frd-03-fix-01, head a51a243e, base main 3b8c0307.
Task: FRIDAY fix — lead_generate (IG2-FRD-03): capability router lead rule
+ FindYello/JaRanks source repair. The FRD-054 live failure being fixed:
natural lead requests never reached the tool (router: DIRECT_REASONING
score -16.5), explicit FindYello run 403'd, explicit JaRanks run returned
65 rows with 0 phones/emails + nav junk.

## Verdict: PARTIAL — router + parser verified live; sources verdict'd, no contact table deliverable from either named source

| Leg | Verdict | One line |
|---|---|---|
| Router lead rule | VERIFIED live | The verbatim FRD-054 natural request now routes TOOL_EXECUTION / lead_generate (deterministic, single table hit) |
| Fetcher (browser headers) | PARTIAL | Implemented; does NOT clear FindYello's Cloudflare JS challenge (site-wide) |
| Parser (Tailwind/heading/strict phones) | VERIFIED live | Real JaRanks page: all 16 providers found with profile URLs; junk excluded; zero garbage phones |
| FindYello source | BLOCKED — written verdict | Cloudflare "Just a moment..." challenge, search page AND homepage, from the production host |
| JaRanks source | NOT VERIFIED as a contact source | Fetches + parses, but 0 of 16 profiles publish a phone or an email in visible content |
| End-to-end /api/chat leg | OWED | Needs the fix deployed (merge + CD repair or coordinator deploy ruling); no service restart done in this run |

## The fix (4 commits, remote head a51a243e)

- `37675a5c` — router rule + fetcher + parser v1: `LEAD_KEYWORDS` (generate
  leads, lead generation, business directory, directory listing, findyello,
  jaranks, …) + TOOL_EXECUTION candidate `required_tools=["lead_generate"]`,
  excluded from DIRECT_REASONING in both conversational checks, added to
  `_INTENT_TABLES`; browser-like fetch headers (FindYello 403'd the
  `FRIDAY-LeadGen/1.0` UA); nav/header/footer chrome exclusion; contact-signal
  requirement (phone or email, else dropped); same-host detail-page enrichment
  (bounded, 20/run); `_clean_phone` rejects ISO dates and fragments.
- `df6775b0` — parser v2 (live JaRanks structure): whole-token hint matching
  (`item` in `items-center` opened "Motor" blocks); void elements no longer
  inflate block depth (`<img>` swallowed siblings); heading-anchored fallback
  for hint-less Tailwind pages; relative hrefs joined to absolute URLs;
  only links inside the heading count as the detail link.
- `67a936df` — parser v3 (union, not either/or): the live JaRanks page yields
  two junk non-empty hint blocks ("Rank", "The JaRanks newsletter") and zero
  providers, so an either/or fallback never reached the headings. Hint +
  heading blocks are now unioned and deduped in parse; heading parser is
  chrome-aware.
- `a51a243e` — parser v4 (strict phones, skip scripts): the decisive probe
  returned 5 leads with garbage phones harvested from inline JSON (epoch
  timestamps, long IDs, digit-dash fragments) — caught before filing, never
  shipped. `_clean_phone` now requires a phone shape (lone runs only 7/10
  digits or `+` international; separated numbers must end in a 4-digit
  subscriber group); script/style bodies are skipped in both parsers and in
  detail extraction.

Files: `FRIDAY/src/friday/routing/capability_router.py`,
`FRIDAY/src/friday/autonomous/lead_generation.py`,
`FRIDAY/tests/test_capability_routing.py` (+4 router tests),
`FRIDAY/tests/test_ig2_frd03_lead_generation.py` (+13 engine tests).

## Tests — 59 passed in 1.83s on FRIDAY-Server (live host)

Service venv (`/opt/friday_universe/venv/bin/python -m pytest`, /tmp clone
at a51a243e, deleted after): `test_ig2_frd03_lead_generation.py`
(19: 6 pre-existing + 13 new) + `test_capability_routing.py` (11: 7 + 4 new)
+ `test_router_word_boundaries.py` + `test_intent_classifier_tier.py`
— **59 passed, 0 failed**. The router tests assert the verbatim FRD-054
utterances route TOOL_EXECUTION with `required_tools == ["lead_generate"]`
and `deterministic_match_count == 1`, and that "He leads the team" /
"show me my contact list" stay DIRECT_REASONING. Local stub smoke runs
of the same utterances (engine + router) passed before push.

## Live probes — all from FRIDAY-Server (15.134.130.145), production egress IP

Route S1 → AWS with the tunnel key; loopback-independent reads only; /tmp
scratch (clone + probe scripts) deleted after each run. No service file
touched, no restart, no live state changed. FRIDAY.service stayed
active/running throughout (verified at probe start).

### Probe 1 — v1 engine (~19:15 IST)

- FindYello search page: `HTTPStatusError 403 Forbidden`.
- JaRanks list: fetched, 1 page, **0 leads** — the hint parser is blind to
  Tailwind utility classes.

### Diagnostic 1 — what the real pages contain (~19:20 IST)

- FindYello 403: `server: cloudflare`, `cf-ray: ...-SYD`, body
  `<title>Just a moment...</title>` — Cloudflare's bot-management JS
  challenge. Not a UA block: a plain HTTP client cannot pass it.
- JaRanks list: 256,681 bytes fetched; "British Caribbean" ×7; `tel:` ×0,
  `mailto:` ×0, `876-` ×0. Classes are Tailwind utilities (16×
  `grid grid-cols-[auto_1fr] ... border-b border-hairline py-8`,
  `font-display ...`, `rounded-card`, …); profile links are RELATIVE
  (`/profile/british-caribbean-insurance-company-ltd-bcic`).

### Probe 2 — v2 engine, heading fallback (~19:25 IST)

- JaRanks: still **0 leads**. Root cause diagnosed, not guessed: the hint
  parser finds 20 raw blocks, 2 non-empty ("Rank", "The JaRanks
  newsletter"), so the either/or fallback never ran.

### Diagnostic 2 — real-page parse (~19:30 IST)

- Hint blocks: 20 raw / 2 non-empty (junk). Heading sections: 26 — the 16
  providers ARE there with profile hrefs, plus hero/newsletter sections.
- BCIC profile: 110,151 bytes; `phone` ×3, `contact` ×10, `876` ×0,
  `email` ×26, `website` ×10, `tel:` ×0. Profile copy: "phone numbers,
  hours or licence numbers — if a field is missing, we did not have a
  source for it."

### Decisive probe — v3 engine (~19:35 IST)

- 21 candidates parsed (16 providers + 5 junk/section heads), all 16
  profile URLs joined correctly.
- Per-profile contacts: 3 "phones" — all garbage shapes from inline JSON
  (`221-0821-41`, `19-9181-9`, `413-4894`).
- RUN returned **5 leads with garbage phones** (`26947469-800`,
  `133146406741`, `922-6365-4`, `6-8223-50`, `1739935912555`, incl. a
  "More" junk lead) — caught by reading the output before filing; this is
  what v4 fixes. Nothing fabricated was filed or posted.

### Decisive probe — v4 engine (~19:40 IST)

- 21 candidates, all 16 profiles fetched: **0 phones, 0 emails**.
- RUN leads: **0**. The tool now returns an honest empty result instead
  of a fabricated table.
- FindYello homepage: also 403 (Cloudflare challenge is site-wide, not
  search-only).

## Written verdicts (per the acceptance: blocked source gets a named replacement or a written verdict)

- **FindYello — BLOCKED.** Cloudflare "Just a moment..." JS challenge on
  every path from the production host (search + homepage, cf-ray SYD).
  Browser headers do not clear it; a plain-HTTP fetcher cannot pass a JS
  challenge. A browser-driven fetch would be a different tool surface, out
  of scope for this fix. No replacement named yet: JaRanks (the obvious
  replacement — it fetches) publishes no contacts either, so naming it
  would mislead. The coordinator should name a directory that publishes
  contacts in server-rendered HTML, or accept the verdict.
- **JaRanks — parses, but NOT a contact source.** The fix is proven on the
  real page (16/16 providers + profile URLs + junk excluded), but 0 of 16
  profiles publish a phone or an email in visible content (the profile
  template says fields are missing when JaRanks has no source). The
  deliverable table cannot come from this source as it stands.

## What is owed

1. **End-to-end /api/chat leg** — the fixed router + engine running inside
   the live FRIDAY service, with the three FRD-054 requests re-run. Owed
   on deploy: merge this PR, then CD repair (fleet CD broken, WATCH098 —
   owner word owed) or a coordinator deploy ruling. I did not restart
   FRIDAY.service unilaterally.
2. **Replacement directory decision** — coordinator: name a directory that
   publishes contacts in server-rendered HTML (FindYello is Cloudflare-
   blocked; JaRanks publishes no contacts), or accept the verdicts.
3. **FRD-043** — claim stands (hub 7163026128); hold stands per WATCH100
   (no deploy clearance); branch `muse15/task-frd-043-oom-memory-guard` at
   b9a4c8cf (behind current main — fast-forward owed when clearance lands).

## Five states (TASK-IG2-FRD-03-FIX-01)

- implemented: YES (router rule + fetcher + parser, 4 commits)
- tested: YES (59 tests green on FRIDAY-Server + live probes per source)
- merged: NO (this work PR)
- deployed: NO (code not in the live service; CD broken)
- production-verified: PARTIAL (router + parser verified live on the host;
  sources verdict'd; end-to-end chat leg owed on deploy)

## CI follow-up (same run, ~19:55 IST)

First CI run on PR #1859: the `contracts` job failed at the REL-068
collection guard — both shipped test files were uncollected by any
PR-triggered workflow (`test_capability_routing.py` uncollected since it
landed; `test_ig2_frd03_lead_generation.py` new). Fixed in this PR:
both files added to the FRIDAY tier-1 invocation in
`.github/workflows/friday-universe-ci.yml` (same pattern as FRD-044 /
FRD-045). `scripts/ci_test_collection_audit.py` passes locally against
main 14181d3c (2 files checked, both collected).

## Schedules / usage

- `muse15-work-request`: cancelled on claim; to be re-armed on completion
  (free/requesting work — no next task of mine is actionable: FRD-043
  held; IG-FRD-010-RETEST-01 / IG2-FRD-01-ACTIVATE-01 / IG2-FRD-02-
  ACTIVATE-01 all need owner steps).
- Usage: 28% of free weekly limit (checked this run; reset Mon Nov 30,
  7:04 PM IST). Additional tokens 0% used.

— Muse 15
