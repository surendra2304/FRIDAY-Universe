# TASK-WEB-006 — PRODUCTION-VERIFY — 2026-11-25 ~18:52 IST — Muse TP9

Claim: hub #1483 comment 7163567360.
Branch: musetp9/task-web-006, from main f216e1b.
Task: PRODUCTION-VERIFY website corpus items IG2-WEB-04, IG2-WEB-05, IG2-WEB-06, IG2-WEB-07
(live extreme-condition verification, wave 2, P1).

## Verdict: 0 of 4 verified live

| Item | Verdict | One line |
|---|---|---|
| IG2-WEB-04 sector heatmap | NOT VERIFIED | No heatmap anywhere on the live dashboard; the page is unstyled and its JS never runs — `/static/*` assets 404 at the site root while `/stratex/static/*` serves |
| IG2-WEB-05 Ctrl-K palette | NOT VERIFIED | Ctrl-K and the "Jump to" button both do nothing; no palette element ever appears in the DOM |
| IG2-WEB-06 persisted layouts | NOT VERIFIED | Widgets cannot be dragged at all (drag only selects text); no drag handles, no Reveal UI, nothing to persist |
| IG2-WEB-07 glass start page | NOT VERIFIED | `/start` renders a glass page, but it has no widget-toggle control; the served page does not match the GlassStartPage component on main |

Failure injection (acceptance: a failure case per item): the live system
supplied its own failure — the Stratex backend never answers and the
dashboard's assets 404 (see Root cause). No deliberate outage was staged;
none is needed while the production path itself is down.

## Live target and method

Live-leg target is the public production site
`https://friday-universe.duckdns.org` (public ingress per bridge
`get_system_info`, Oracle Server 2, 2026-11-25). All legs ran in a real
browser as a visitor, no sign-in, no service restarted, deployed or
changed. Two browser runs: main verification 18:52–18:55 IST
(browser-task 64590f3b, ~35 s+ of waiting across two loads of
`/stratex/`), plus a follow-up probe of the heatmap API paths and
`/start` (browser-task 46de5700, result below).

Scope limits, stated plainly:

- Viewport: the browser tooling provided no viewport resize/emulation,
  so every observation is desktop (1919x998). The mobile viewport
  (~390x844) was NOT tested; it is owed on re-verification.
- HTTP status: the browser exposes no network/devtools log, so data-call
  statuses are stated from observation (page behaviour), not from a log.
  Where a numeric status is quoted below it comes from a direct fetch
  of that exact URL, which returns the upstream status.
- The text fetcher returns 404 for `/start` while the live browser
  renders it — a fetcher artifact for a client-side route, not a
  contradiction of the render. The live browser is the authority for
  what renders.

Code position, verified first-hand on main via the GitHub API: all four
items' code IS on main — `Stratex/static/index.html` (sha 4d3f064e)
contains the `#sector-heatmap-grid` section and the Markets view,
`heatmap.js` (c178e056) fetches `/api/v1/market/sector-heatmap`,
`command-palette.js` (0079f60c) wires Ctrl/Cmd-K and the "Jump to"
button, `layout.js` (04cb7f05) drags panels by heading and persists to
localStorage key `stratex.dashboard.layout.v1`, and
`FRIDAY/ui/components/GlassStartPage.tsx` has a settings strip with
widget toggles (`toggleWidget`, `enabledWidgets`). The failure is in
serving, not in the merged code.

## Root cause (live evidence)

The Stratex dashboard HTML is served at `/stratex/`, but every asset it
references is root-relative, and the root paths 404:

- `https://friday-universe.duckdns.org/static/style.css` — **404**
  (checked twice, with and without `?v=9.0.2`).
- `https://friday-universe.duckdns.org/stratex/static/style.css` —
  **200**, the real 778-line stylesheet.
- `https://friday-universe.duckdns.org/api/v1/market/sector-heatmap` —
  serves the FRIDAY SPA HTML in a real browser (see probe below), not
  sector JSON; the text fetcher reported 404 for the same URL.

`index.html` on main references `/static/style.css?v=9.0.2`,
`/static/app.js?v=9.0.2`, `/static/heatmap.js?v=1.0.0`,
`/static/command-palette.js?v=1.0.0`, `/static/layout.js?v=1.0.0` —
all root-relative. The gateway serves the Stratex app under `/stratex/`
but does not map `/static/*` (or `/api/*`) to it. So the browser gets
the HTML skeleton and nothing else: no CSS, no JS, no data. That one
routing defect explains IG2-WEB-04, -05 and -06 together — none of the
three can even start.

Probe result — browser-task 46de5700, 18:57 IST (13:27 UTC), real
browser, read-only:

- `https://friday-universe.duckdns.org/api/v1/market/sector-heatmap`
  (the root path `heatmap.js` fetches): loads the FRIDAY web app SPA
  HTML instead of JSON — main heading "FRIDAY", subtitle "ULTRON
  COMMAND · TASK-WEB-003". The dashboard's data fetch gets HTML, so
  `heatmap.js` can never render tiles. (The text fetcher reported 404
  for this same URL; the live browser renders the SPA. The operative
  fact is identical either way: no JSON reaches the dashboard.)
- `https://friday-universe.duckdns.org/stratex/api/v1/market/sector-heatmap`
  (the prefixed path): renders as raw JSON —
  `{"as_of":"2026-11-25T13:27:22.708557+00:00","sectors":[{"change_pct":null,...,"sector":"Technology"},...],"source":"stooq (free daily quotes)"}`.
  The endpoint works under the prefix, BUT every sector and member in
  the body has `"change_pct":null` and `"members_available":0`. The
  Stooq data source currently yields zero priced members, so even with
  routing fixed the heatmap would render all-"unavailable" tiles until
  quotes flow. By design `heatmap.js` never invents a number — an
  unpriced sector is a neutral tile.
- `/start` re-check: renders the FRIDAY/ULTRON COMMAND page (heading
  "FRIDAY", subtitle "ULTRON COMMAND · TASK-WEB-003"). Word search of
  the full page text: "Settings" NOT found, "Weather" NOT found,
  "To-do" NOT found; "Notes" only as "Notes / Description" in
  conversation-history text below the dashboard, "Map" only inside
  the word "sitemap", "Search" only in conversation-history text —
  none as a widget label. No settings strip, no widget toggle control,
  no switches or checkboxes that hide/show a widget. Only controls:
  VOICE / TEXT buttons, message textbox + Send, and CONTROL buttons
  "WAKE WORD OFF", "START THE LINE", "WRITE INSTEAD".

## IG2-WEB-04 — NOT VERIFIED (heatmap never renders)

- URL: `https://friday-universe.duckdns.org/stratex/`, HTML served,
  skeleton in a few seconds.
- What rendered: a completely UNSTYLED page (plain serif text, blue
  links, no layout/CSS) stuck in loading states — "ENGINE · Connecting
  · Waiting for service data", "Loading service state / Waiting for
  health endpoint", all metric cards "— / Waiting for account data",
  "Equity trajectory — No timeline loaded", "Engine status — Checking
  health / No response yet", "Paper experiment — Waiting for experiment
  status", "Open positions — Loading position records…", footer "No
  successful sync yet".
- No sector heatmap exists anywhere on the page: a text search for
  "heatmap" returned nothing, the "Markets" nav button did nothing (no
  navigation, no view change), scrolling the full Overview found no
  heatmap section. The `#sector-heatmap-grid` section exists in the
  main-branch HTML but its module (`heatmap.js`) never loads live.
- Failure case: waited 10 s then a further 25 s, reloaded once, clicked
  Markets, scrolled — still no data and no heatmap after ~35 s+.
- Corroboration: the `/start` page's Core Modules panel listed
  "Stratex DEGRADED" (also IntelX and Futuris DEGRADED).

## IG2-WEB-05 — NOT VERIFIED (palette never opens)

- URL: same `/stratex/`.
- Ctrl-K: nothing — no palette, dialog, search input or command list
  appeared, and the DOM gained no palette element.
- Failure case: clicked the on-page "Jump to Ctrl K" button ("Command
  palette (Ctrl-K)") — again nothing after a 5 s wait. Escape pressed
  after Ctrl-K and after reload — nothing opened, nothing closed.
- Choosing a command could not be tested: no palette ever opened and
  no commands were ever listed. Consistent with the root cause — the
  page's JavaScript does not run at all (unstyled page, dead nav
  buttons).

## IG2-WEB-06 — NOT VERIFIED (no drag, nothing to persist)

- URL: same `/stratex/`.
- Dragged the "Engine status" widget heading onto the "Paper experiment"
  heading: the drag only selected/highlighted text; widget order did
  not change. There are no drag handles, layout/edit controls, or any
  "Reveal" UI — a text search for "Reveal" returned nothing, so the
  Reveal surfaces are NOT visible.
- After a reload the widget order was exactly the original fixed
  server-rendered order (Equity trajectory → Engine status → Paper
  experiment → Open positions) — but that proves nothing about
  persistence, because no rearrangement ever took effect to persist.
  The layout did not "reset"; it simply never changed. Nothing to
  restore; the original order is intact.
- All widgets stayed in loading/empty states throughout ("Loading…",
  "No response yet", "Waiting for experiment status").

## IG2-WEB-07 — NOT VERIFIED (glass page renders, toggles do not exist)

- URL: `https://friday-universe.duckdns.org/start`, page served, styled
  glass render within a few seconds, reload reproduced it.
- What rendered: a dark "ULTRON COMMAND" glass start page with a live
  ticking clock (18:54 Wed 25 Nov 2026, matching real time), an orange
  wireframe orb ("STANDING BY"), and panels: System Diagnostics, Core
  Modules (10 units), FRIDAY core, Fleet Link, Vision — Live Feed,
  Activity Log, Conversation, Control, plus VOICE/TEXT buttons and a
  message box.
- Load behaviour: data is slow/flaky — on first load, after some
  seconds, Fleet Link showed 6/9 agents online, mean latency 1160 ms;
  immediately after a reload it showed only "Telemetry unreachable —
  no figures shown rather than invented ones", "Fleet unreachable —
  module states unknown, not guessed", "Agents online 0/—". The first
  load briefly showed a stale clock (07:16:48, Tuesday 24 Nov 2026)
  before the live time took over.
- Toggle test: NO widget toggle exists to test. A full-DOM text search
  for "widget" returned nothing; no switches, checkboxes or customize
  controls; scrolling the whole page revealed none. The only
  toggle-like controls are "WAKE WORD OFF", "START THE LINE" and
  "WRITE INSTEAD" — none hides/shows a widget.
- Mismatch note: the served page does not match the GlassStartPage
  component on main, whose description is "search, weather, to-dos,
  notes and a map, on one calm page" with a settings strip of widget
  toggles. The probe (task 46de5700, 18:57 IST) confirms it: `/start`
  serves the FRIDAY stage subtitled "ULTRON COMMAND · TASK-WEB-003",
  with no Settings, Weather or To-do anywhere on the page. Either the
  deployed checkout predates the `/start` mount (PR #720, merged
  2026-11-16) or `/start` serves a different component in production.

## Follow-ups named (filed as board records in this PR)

- **TASK-IG2-WEB-04-FIX-01** — Fix Stratex dashboard asset/API routing
  so the live page actually loads: map `/static/*` and `/api/*` to the
  Stratex app (or make the dashboard's references prefix-relative),
  confirm `/static/style.css`, `/static/app.js`, `/static/heatmap.js`,
  `/static/command-palette.js`, `/static/layout.js` and
  `/api/v1/market/sector-heatmap` all answer 200 live, confirm the
  Stooq feed actually prices members (as of 2026-11-25 13:27 UTC every
  `change_pct` was null and `members_available` 0 — an all-unavailable
  heatmap is honest but not a verification), then re-verify
  IG2-WEB-04, IG2-WEB-05 and IG2-WEB-06 in a real browser (desktop +
  mobile viewport). No code fix in the four items is indicated; the
  defect is serving/routing plus the quotes feed.
- **TASK-IG2-WEB-07-FIX-01** — Make `/start` serve the GlassStartPage
  component (or correct the mount if it already should): confirm the
  deployed checkout includes the `/start` wiring, then re-verify live
  that the settings strip with widget toggles exists and that toggling
  a widget off and on hides/shows it, desktop + mobile viewport.

## Five states (TASK-WEB-006)

- implemented: YES (all four items' code merged on main)
- tested: PARTIAL (live browser legs run for all four items; mobile
  viewport and throttled slow-network legs NOT run — owed on
  re-verification)
- merged: NO (this work PR)
- deployed: PARTIAL (Stratex HTML serves but its assets 404;
  `/start` serves a page, but not the GlassStartPage toggles)
- production-verified: NO (0 of 4)

## Schedules / usage

- `musetp9-work-request`: cancelled on claim (correct while holding a
  task). Hourly self-check + weekly reset armed.
- Usage: 2% of free weekly limit (checked this run; reset Dec 2, 2026,
  5:57 PM IST). Additional tokens 0% used.

— Muse TP9
