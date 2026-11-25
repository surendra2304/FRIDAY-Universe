# TASK-INT-045 — First Squawk free feed route: verdict NO FREE ROUTE

- **Task:** IntelX: find a viable free feed route for First Squawk and activate it in `headline_watch.py`.
- **Acceptance:** First Squawk items flow through the headline watch, **or** a verified no-free-route verdict is recorded and the source is dispositioned.
- **Outcome: no-free-route verdict (implemented + tested).** No First Squawk items flow — there is no keyless, free, public route that carries them. The source stays registered inactive in `headline_watch.py` with the dated verdict as its `unavailable_reason` (`FIRST_SQUAWK_NO_FREE_ROUTE`).
- **Worker:** Muse 10. **Claim:** hub #1483 comment 7152682884, 2026-11-25 ~09:43 IST, on assignment in coordinator watch075 (comment 7152477568). PR #1771 carries claim + work (single PR: claim commit 01fd12a6 + work commit).
- **Board:** TASK-INT-045 CLAIMED → IN_REVIEW, owner muse_10. This PR also carries the six owed MERGED flips from watch075 (INT-017 #1621, FRD-037 #1407, REL-088 #1604, SEN-023 #1646, CTX-008 #1760, VYR-070 #1711 — all six re-verified merged via the PR API this run).

## Probes (all first-hand, 2026-11-25 ~09:45–10:00 IST)

| # | Candidate route | Probe | Result |
|---|---|---|---|
| 1 | firstsquawk.com RSS/Atom feed | Homepage fetch (HTTP 200, 14 KB); searched HTML for rss/atom/feed links | **None.** No feed link anywhere on the site. |
| 2 | `firstsquawk.com/feed`, `/rss.xml` | Direct fetch | **404** both. |
| 3 | `firstsquawk.com/blog/feed/` (WordPress RSS) | Followed 301 → `firstsquawk.com/blog/feed/`, HTTP 200 `application/rss+xml` | **Dead.** Valid RSS 2.0 but `lastBuildDate` 2019-03-28, single item "Hello world!" — a never-used install, not a headline wire. |
| 4 | Site "News → Real-Time" page | Homepage nav: the News dropdown links only to `/blog` | **Dead end** — same dead blog (route 3). No live headline page exists. |
| 5 | Site headlines for non-members | Homepage copy: "All the major headlines we broadcast are published on our website … a valuable resource for all of our members" | **Paid.** Products are Audio News $200, Text Headlines $150, Newsletter $100/mo. No free tier, no free trial page. |
| 6 | Official Telegram channel | `t.me/s/firstsquawk` → redirects to `t.me/firstsquawk`, a contact/user page, no posts | **No channel.** `@firstsquawk` is a contact account, not a public channel. |
| 7 | Telegram lookalike `@firstsquaw` | `t.me/s/firstsquaw` → channel page | **Impersonator.** Page itself labels it "First Squawk [ FAKE ]", 3,784 subscribers. Rejected — piping it would put impersonated content in the watch. |
| 8 | X mirror: nitter.net | `nitter.net/FirstSquawk`, HTTP 200 | **Offline.** Page states "nitter.net is offline." |
| 9 | X mirror: xcancel.com | `xcancel.com/FirstSquawk` | **HTTP 451** (unavailable for legal reasons). |
| 10 | X mirror: twstalker.com | `twstalker.com/FirstSquawk` | **Unreachable** (connection failed). |
| 11 | X API for @FirstSquawk | Known from the module's standing rule + X's pricing: no keyless read | **Paid-only.** The account itself is live and posts (~277 posts/day per Xanguard, updated 2026-11-25), but reading it needs paid X API credentials, which are not configured. |
| 12 | Third-party mirror bot (Xanguard) | `xanguard.tech/track/firstsquawk/` — free plan tracks 1 X account into Telegram | **Not a server route.** Needs a Telegram bot setup and user account; the watch cannot drive it keylessly. Noted, not adopted. |

## Disposition

- `first_squawk_x` stays in `DEFAULT_SOURCES` as `kind="x_account"`, `handle="FirstSquawk"`, `active=False`, with `FIRST_SQUAWK_NO_FREE_ROUTE` as the reason. The watch reports it as unavailable; it never yields headlines and nothing is fabricated.
- **Re-probe trigger:** only if First Squawk publishes a public feed (RSS/Atom, public Telegram channel, or other keyless endpoint). Then flip the source to that route with a live fetch as proof.
- No credentials, no paid services, no new dependencies introduced.

## Change set (this PR)

- `IntelX/intelx/ingestion/headline_watch.py` — `FIRST_SQUAWK_NO_FREE_ROUTE` verdict constant; `first_squawk_x` uses it.
- `IntelX/tests/test_ig_intelx_wiring_feeds.py` — verdict test (date, task id, every checked route named) + inactive-source poll test.
- `.github/workflows/friday-universe-ci.yml` — the wiring test file added to the IntelX tier-1 list: it was previously collected by **no** CI job (same uncollected-test failure mode as FUT-030 / PR-936).
- `docs/collaboration/TASK-INT-045.md` — this evidence doc.
- `docs/collaboration/WORK_BOARD.yaml` — INT-045 → IN_REVIEW (pr 1771); six owed MERGED flips (see top).

## Tests (local, IntelX venv from `IntelX/requirements.txt` + pytest + pytest-asyncio + aiosqlite)

- `IntelX/tests/test_ig_intelx_wiring_feeds.py` — **all pass** (run: `python -m pytest -q tests/test_ig_intelx_wiring_feeds.py`, working dir `IntelX`).
- IntelX tier-1 CI list (`tests/test_intelx_health_contract.py tests/test_health.py tests/test_healthz_liveness.py` + the wiring file) — run locally before filing; CI verdict pending on PR #1771.

## States

- implemented: YES (verdict in code + disposition + evidence doc)
- tested: YES (new tests pass locally; CI pending)
- merged: NO — awaiting Muse's merge; I never merge my own PR
- deployed: NO
- production-verified: NO (no live leg exists — there is no free route to verify live; the verdict itself is the verified outcome)

— Muse 10
