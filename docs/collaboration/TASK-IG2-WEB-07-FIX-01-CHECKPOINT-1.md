# TASK-IG2-WEB-07-FIX-01 — CHECKPOINT 1 — 2026-11-26 ~22:30 IST — Muse 10

Claim: hub #1483 comment 7194954328. Branch
`muse10/task-ig2-web-07-fix-01-glass-start-page` (recreated from main
`4cf9c897` after the post-merge branch deletion — GitHub ref 404, normal).
Claim PR #1995 merged 21:43 IST (merge `8c94e146`, CI 9/9). Base main
`4cf9c897`.

## Verdict: stall repaired — checkpoint 1 filed. Root cause found, fix implemented (repo-side). Live proof still owed.

Scope: `/start` must serve the GlassStartPage component (search, weather,
to-dos, notes, map, plus its settings strip of widget toggles); live proof
in a real browser at desktop AND mobile viewport sizes; toggle a widget off
and on live.

## Live state, verified this run

- Real browser, 22:16 IST, desktop 1919x998 (browser-task 0697167f):
  `https://friday-universe.duckdns.org/start` AND
  `/friday/start` both render the ULTRON COMMAND stage (title FRIDAY,
  "ULTRON COMMAND · TASK-WEB-003", orb, "TAP TO TALK", "START THE LINE").
  No search box, weather, to-dos, notes, map, or settings strip with
  widget toggles on either URL. No 502, no sign-in. The WEB-006 failure
  reproduces exactly.
- Deployed build on Server 1 DOES contain the glass page:
  `/opt/friday_universe/FRIDAY/ui/out/start/index.html` exists with title
  "FRIDAY — Start". This is not a stale-build problem.
- `/friday/health` via the public ingress answers 200 healthy
  (observed 22:19 IST): platform `Linux-7.0.0-1014-aws-x86_64`, Python
  3.10.22, Oracle `SELECT 1 FROM DUAL` OK, 41811.3 MB free.

## Root cause (code, verified first-hand)

The root static mount in `FRIDAY/src/friday/api/server.py` is
`_APIAwareStaticFiles(html=False)`. With `html=False`, Starlette never
resolves a directory path: `/start` maps to the directory
`out/start/`, so the mount raises 404 and the except-404 branch hands the
browser the root shell (`_index_html()` — the ULTRON stage) with a 404
status. Caddy strips the `/friday` prefix (`handle_path /friday*`), so
`/friday/start` reaches FastAPI as `/start` and hits the same miss —
which is why the `html=True` `/friday` mount never rescues it in
production. Confirmed against the installed Starlette
(`staticfiles.py`, `lookup_path`/`get_response`): directory + `html=False`
→ 404; absolute paths rejected; directory confinement via commonpath.

## Fix (this PR)

In `_APIAwareStaticFiles.get_response`, on a 404 miss, try
`<path>/index.html` through StaticFiles itself (same resolution and
confinement) before the shell/JSON fallback. `/start` now serves
`out/start/index.html` (200). Unknown paths still fall through: browsers
get the shell, API clients get the JSON envelope — the 2026-11-12
behaviour is preserved. Generic: covers any future export route
directory, not just `/start`. No Caddy change. No change to the `/`
route, `/dashboard`, or any API route. `+16` lines, one file.

## Gated / owed — stated plainly

- Live re-verification (desktop + mobile + toggle test) is owed. It needs
  this fix deployed to the serving host with that host's FRIDAY up. Not
  attempted: server moves are frozen under the owner stop order.
- Serving-host anomaly found this run: Server 1 `FRIDAY.service` is
  inactive (dead) and disabled, Caddy is failed (`Result=timeout`), and
  nothing listens on S1:10000/443 — yet the public site answers live.
  `duckdns` resolves to `140.245.243.168` (Server 2 public IP) from S1,
  but Server 2 has nothing on 10000/443/8011 either, while `/friday/health`
  reports an AWS kernel. The live site is served from a host not yet
  identified; the deployment target for this fix needs a coordinator
  ruling. Flagged, not assumed.
- No new test file in this checkpoint: a focused mount test is owed.
  Local test runs were not possible in this run, so CI on this PR is the
  verification for this checkpoint.
- Branch note: the Server 2 bridge-workspace checkout sits on this branch
  at `410f0738` (`get_system_info`), not on main. Flagged; no change made
  to it.

## Files

- `FRIDAY/src/friday/api/server.py` (+16, the mount fix)
- `docs/collaboration/TASK-IG2-WEB-07-FIX-01-CHECKPOINT-1.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (record flip CLAIMED → IN_REVIEW,
  pr set, second commit)

## State

- Implemented: mount fix + this evidence doc + board flip (this work PR).
- Tested: CI on this PR head (pending at filing; see PR checks).
- Merged / deployed / production-verified: owed. Live proof gated as
  above.
- Usage: 61% (last verified 19:06 IST; reset Nov 28 02:03 IST).

— Muse 10
