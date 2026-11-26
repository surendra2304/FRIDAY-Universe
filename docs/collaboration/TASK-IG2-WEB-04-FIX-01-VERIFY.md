# TASK-IG2-WEB-04-FIX-01 — BUILD VERIFY — 2026-11-26 — Muse TP9

Claim: hub #1483 comment 7192736359 (WATCH161 assignment, hub 7192344914).
Branch: musetp9/task-ig2-web-04-fix-01, from main 4a9b0a57.
Work PR: #1990, code head 5488384ac5a86de79f137e9145e8b11570f68441.
Task: FIX: Stratex dashboard assets and API 404 at site root — route
/static/* and /api/* to Stratex (WEB-006 live failure). P1.

## What was wrong (TASK-WEB-006, 2026-11-25, 0 of 4 verified live)

The Stratex dashboard HTML serves at `/stratex/`, but every asset and
data call it makes is root-relative, and the root paths do not reach
Stratex. Verified first-hand on main `4a9b0a57`:

- `Stratex/static/index.html` referenced `/static/style.css`,
  `/static/app.js`, `/static/heatmap.js`, `/static/command-palette.js`,
  `/static/layout.js`.
- `Stratex/static/app.js` fetched 8 endpoints as `/api/status`,
  `/api/engine-health`, `/api/paper/forward-status`, `/api/positions`,
  `/api/telemetry/trades`, `/api/equity-history`, `/api/markets`,
  `/api/telemetry/signals`.
- `Stratex/static/heatmap.js` fetched `/api/v1/market/sector-heatmap`;
  `Stratex/static/quantum.js` fetched `/api/quantum/advisory`;
  `Stratex/static/quantum.html` referenced `/style.css`, `/quantum.js`.

The production ingress (`deploy/Caddyfile`, mirror of the deployed
`/etc/caddy/Caddyfile` on Server 1) routes `handle_path /stratex*` to the
Stratex app at 127.0.0.1:18003, stripping the prefix — so
`/stratex/static/*` and `/stratex/api/*` reach the Flask app, while
`/static/*` and `/api/*` fall through to the FRIDAY app at 127.0.0.1:10000
(`/static/style.css` 404s; `/api/v1/market/sector-heatmap` serves the
FRIDAY SPA HTML). The dashboard therefore loaded as an unstyled skeleton
with dead nav and no data. The Flask app itself is fine at root
(`dashboard.py`: `Flask(__name__, static_folder='static')`, index route
`/`, all 8 app.js endpoints plus the sector-heatmap blueprint registered)
and is also served standalone at root (deploy.sh port 5000, Docker port
8000) — so the fix must work under BOTH mounts, not just `/stratex/`.

## The fix (two layers, both in this PR)

1. **Dashboard references mount-relative** (the fix that makes the
   dashboard work after the next Stratex deploy, with no ingress change):
   - `Stratex/static/index.html`: `/static/X` → `static/X` (5 refs).
   - `Stratex/static/app.js`, `heatmap.js`, `quantum.js`: each gains a
     `dashboardMountBase()` helper that derives the mount prefix from
     `window.location.pathname` (`/stratex/` or `/stratex` → `/stratex`;
     `/` or `/index.html` → `''`), and every API fetch becomes
     `API_BASE + '/api/…'`. The helper is duplicated per file on purpose:
     `heatmap.js` documents itself as self-contained and does not touch
     app.js state.
   - `Stratex/static/quantum.html`: `/style.css` → `style.css`,
     `/quantum.js` → `quantum.js` (same defect class, sibling page).
   - No root-relative `/static/` or `/api/` reference remains in any
     dashboard file (verified by grep; pinned by test).
2. **Caddyfile maps the root paths too** (`deploy/Caddyfile`, mirror only
   — the deployed file on S1 still needs sync + reload when the gate
   opens): `handle /static/*` and
   `handle /api/v1/market/sector-heatmap` → 127.0.0.1:18003, placed
   before the final catch-all. `handle` (not `handle_path`) so the full
   path reaches the Flask app (its static route and heatmap blueprint
   serve them). This is safe: the FRIDAY app owns no `/static/*` path
   (its Next.js static export uses `basePath: "/friday"`, assets under
   `/friday/_next/static/`), and the heatmap path is Stratex-only.
   `/api/*` as a whole stays with FRIDAY — the dashboard's other API
   calls go via `/stratex/api/*` after layer 1.

## Stooq-feed check (acceptance item 3 — NOT satisfied, honestly)

- The heatmap code is correct: `Stratex/api/sector_heatmap.py` fetches
  `https://stooq.com/q/d/l/?s={symbol}&i=d` with lowercase `.us` symbols
  (the documented Stooq daily-CSV format), 4 s timeout, 8 workers,
  honest `None` → unavailable tiles, never invented numbers.
- Stooq is unreachable from this VM: `stooq.com` TLS handshake and read
  both timed out on two attempts (2026-11-26 ~18:40 IST), while
  `example.com` answered 200 in 0.6 s on the same egress. This matches
  the 2026-11-25 live probe from the Stratex server (every `change_pct`
  null, `members_available` 0 at 13:27 UTC): the feed yields zero priced
  members from two vantage points, so the failure is upstream
  reachability, not the code.
- No fallback source was invented. Until Stooq answers again, the
  heatmap will honestly render all-unavailable tiles; acceptance item 3
  ("confirm the Stooq feed actually prices members") remains open and is
  a live-data condition for the re-verification run, not a code defect.

## Local verification (no fleet touched)

38 tests green in a local venv (flask 3.1.3, pytest 9.2.0), run from a
temp Stratex layout with the real edited files:
`tests/test_ig2_web04_fix01_routing.py` (30 new) +
`tests/test_sector_heatmap.py` (8 existing, unchanged). What the new
tests prove:

- No root-relative asset/API reference remains in `index.html`,
  `quantum.html`, `app.js`, `heatmap.js`, `quantum.js`.
- `dashboardMountBase()` returns `/stratex` for `/stratex/`, `/stratex`,
  `/stratex/index.html`; `''` for `/`, `/index.html` (executed under
  node, 21 cases across the three files).
- A test Flask app mirroring `dashboard.py` serving (static folder,
  index route, sector-heatmap blueprint) behind a prefix-strip
  middleware (Caddy `handle_path /stratex*` simulation) serves `/` and
  `/stratex/` (200), every static asset at `/static/*` and
  `/stratex/static/*` (200), and the heatmap endpoint at both
  `/api/v1/market/sector-heatmap` and `/stratex/api/v1/market/sector-heatmap`
  (200, stubbed payload, unpriced sectors honestly null).
- Every URL the dashboard pages reference resolves to 200 under both
  mounts; every API path the JS fetches has a matching route/blueprint
  in `dashboard.py` source.
- The Caddyfile contains the two new `handle` blocks proxying to
  127.0.0.1:18003, before the catch-all, and no `handle_path /static`
  (which would strip and break Flask's static route).
- `node --check` passes on all three edited JS files;
  `.github/workflows/friday-universe-ci.yml` parses; the new test file
  is registered in the Stratex tier-1 invocation (REL-068).

## What remains (gated, not done)

- Live proof (acceptance items 2–4): needs a deploy plus a live
  re-verification in a real browser at desktop AND mobile viewports
  (IG2-WEB-04, -05, -06) — gated on the owner stop order (live gate
  CLOSED per WATCH161/162). No fleet move was made in this PR.
- Caddyfile mirror updated here; the deployed `/etc/caddy/Caddyfile`
  on Server 1 needs sync + Caddy reload when the gate opens — until
  then the root `/static/*` and `/api/v1/market/sector-heatmap` paths
  still 404 / serve the SPA live.
- Stooq feed: confirm members price once live (acceptance item 3).

## Five states

- implemented: YES (this PR)
- tested: YES locally (38 tests green); live legs NOT run (gated)
- merged: NO (this work PR)
- deployed: NO
- production-verified: NO (0 of 4 live items re-verified; gated)

## Files changed

- `Stratex/static/index.html` — asset refs mount-relative (5)
- `Stratex/static/app.js` — mount-aware API base, 8 endpoints
- `Stratex/static/heatmap.js` — mount-aware heatmap fetch
- `Stratex/static/quantum.js` — mount-aware advisory fetch
- `Stratex/static/quantum.html` — asset refs mount-relative (2)
- `deploy/Caddyfile` — root `/static/*` + heatmap path → Stratex
- `Stratex/tests/test_ig2_web04_fix01_routing.py` — 30 new tests
- `.github/workflows/friday-universe-ci.yml` — new test in Stratex tier-1
- `docs/collaboration/TASK-IG2-WEB-04-FIX-01-VERIFY.md` — this doc
- `docs/collaboration/WORK_BOARD.yaml` — board flip AVAILABLE → IN_REVIEW

## Schedules / usage

- `musetp9-work-request`: absent (correct while holding a task).
  Hourly self-check + weekly reset armed.
- Usage: 88% of free weekly limit (checked this run; reset Dec 2, 2026,
  5:57 PM IST). Additional tokens 0% used.

— Muse TP9
