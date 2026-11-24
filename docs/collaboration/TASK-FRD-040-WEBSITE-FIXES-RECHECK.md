# TASK-FRD-040 — FRIDAY website fixes re-check (served page)

**Date:** 2026-11-24 ~04:10–04:45 IST (probes 2026-11-23 22:39–22:45 UTC)
**Worker:** Muse 1 · **Branch:** `muse1/task-frd-040-website-fixes-recheck`
**Claim PR:** #1578 (board-only, AVAILABLE → CLAIMED) — **MERGED** 2026-11-24 04:34:34 IST
(merge commit `da37c511`, merged by surendra2304, verified first-hand via API).
CI on the claim head `f045b4c1` was 9/9 green (7 success, 2 skipped, 0 failed,
verified first-hand 04:15 IST). This evidence was gathered read-only while #1578
awaited merge; no work commits were pushed before the merge gate.
**Status:** FILED as `docs/collaboration/TASK-FRD-040-WEBSITE-FIXES-RECHECK.md` on
branch `muse1/task-frd-040-website-fixes-recheck`, work base main `e261ca17`
(merge of PR #1572, Muse 9 / TASK-INT-035). Work PR: see the TASK-FRD-040 board
record (pr 1578 per plan; work PR number in the board evidence line) and the
hub #1483 STATUS comment.
**Fresh re-confirmation at filing time:** 2026-11-24 ~04:58–05:00 IST the served host
returned **502 Bad Gateway (Caddy)** on `/`, `/friday/health` and
`/api/status/public` (four attempts) — the page was live and 4/4 PASS at probe
time (~04:10–04:45 IST) and is currently unreachable. This is a fleet-availability
fact, not one of the four fixes; no restart/deploy was attempted (no clearance).
Re-check the served page once the host recovers.

## 1. Which 4 fixes — pinned down first-hand

The "4 website fixes" are the four defects of **TASK-FRD-029** (board record,
main `440fbfd0`, verified again on main `95046414`), the only enumerated
four-fix set in the repo records. FRD-029 merged as PR #1093; its source fixes
reached the served page only via the export-regen follow-up PR #1095, and
TASK-FRD-030 (PR #1096) completed the live-path timestamp channel plus a
second export regen. FRD-029's own next_action is literally the re-sweep this
task performs; FRD-030's next_action ordered the same re-check after #1096.
That final re-sweep was never filed — this document is it.

| # | Fix (FRD-029 defect) | What the served page must show |
|---|----------------------|--------------------------------|
| 1 | Vision banner wraps inside its frame | `.ultron-vision-label` wraps (no `white-space:nowrap`; width `calc(100% - 28px)`, `line-height: 1.9`); the full vision sentence visible, not clipped at both ends |
| 2 | Core Modules rows scroll inside their panel | `.ultron-mod-scroll{flex:1;min-height:0;overflow-y:auto}` — rows scroll in-panel, nothing spills under the VOICE STATE band |
| 3 | Activity Log renders real timestamps | Seed rows use `clockTimeOrBlank(e.recorded_at\|\|e.timestamp)`; live rows use `activityFrameTime(frame)`; the live seed and WS backlog both carry full ISO `recorded_at` |
| 4 | Conversation panel height-bounded | `.ultron-chat-panel{height:clamp(300px,42dvh,480px)}` — the stream scrolls inside the panel instead of stretching the page |

**Served page URL** (verified from repo records, not guessed):
`https://friday-universe.duckdns.org/` — the URL in the FRD-029 evidence
(owner's live sweep, 2026-11-19 ~16:43 IST, viewport 1438x832) and the
FRD-030 evidence (coordinator's rendered re-check, 2026-11-19 ~18:06 IST),
and the host the FRD-038 diagnosis probed
(`https://friday-universe.duckdns.org/friday/api/chat`).

**Correction to the task brief (filed plainly, not silently):** PR #1562 is
**TASK-VYR-045** (VyralX caption-dedup, Muse 5, still open, head `b90c4706`),
not an FRD-042 work PR. TASK-FRD-042 has **no** work PR — board on main
`95046414` reads AVAILABLE / owner muse_5 / branch null / pr null. The
coordinator's "Muse 5 (#1562 / FRD-042)" shorthand (hub 7115749789) conflates
Muse 5's open VYR-045 PR with the FRD-042 deploy leg. Nothing in this
re-check depends on #1562.

## 2. Method (read-only; no fleet change, restart, rebuild or deploy)

- `GET https://friday-universe.duckdns.org/` — 200, 19,888 bytes, `<title>FRIDAY</title>`.
- Served `index.html` diffed byte-identical against committed
  `FRIDAY/ui/out/index.html` at main `440fbfd0` (git blob `ec37eb79669a`).
- All 14 real served chunks fetched and compared by git blob SHA against the
  committed export tree at main `440fbfd0`: **14/14 MATCH** (two guessed
  chunk names from the older export 404'd with the FastAPI 79-byte JSON body
  and are not part of the served page).
- Served CSS/JS grepped for the exact fix markers FRD-029/FRD-030 recorded
  in their evidence.
- Live data legs: `GET /api/autonomous/status` (Activity Log seed) and a
  read-only WebSocket read of `/api/ws/activity` (backlog frames).
- No live-fleet change of any kind was made or attempted; no deploy clearance
  exists or was sought for this task.

## 3. Per-fix verdicts — 4/4 PASS on the served page

### Fix 1 — Vision banner wraps — PASS (served bundle)
Served CSS `38kl_eetk15n9.css` (blob `cb5365d14c82`, matches committed export):
`.ultron-vision-label{font-family:var(--u-mono);letter-spacing:.3em;color:#c8d6e480;text-align:center;width:calc(100% - 28px);font-size:8.5px;line-height:1.9;position:absolute;top:calc(50% + 34px);left:50%;transform:translate(-50%)}` —
no `white-space:nowrap` on the rule. The two `white-space:nowrap`
occurrences in the served CSS are on other uppercase-label rules, not the
vision label. The pre-fix defect (57-char sentence clipped at both ends
against a ~268px frame) cannot occur with this rule.

### Fix 2 — Core Modules rows scroll in-panel — PASS (served bundle)
Served CSS `38kl_eetk15n9.css`:
`.ultron-mod-scroll{flex:1;min-height:0;overflow-y:auto}` — present exactly
as FRD-029 specified (header pinned, rows scroll, nothing spills under the
VOICE STATE band).

### Fix 3 — Activity Log real timestamps — PASS (served bundle + live data)
- Served JS `06v1gu8ghb8f_.js` (blob `ecf398d08824`, matches committed export)
  carries the exact FRD-029 seed expression
  `(0,f.clockTimeOrBlank)(e.recorded_at||e.timestamp)` and `activityFrameTime`
  (the FRD-030 live-append clock); same markers also in `3feaxamp98zqh.js`.
- Live seed `GET /api/autonomous/status`, 2026-11-23 22:43:37 UTC: **8/8**
  `recent_actions` carry full ISO `recorded_at`
  (e.g. `2026-11-23T05:10:38.900531+00:00`, `…03:38:17.104795+00:00`) —
  parseable instants, so seed rows render real times, not blank and not
  `--:--:--`.
- Live WS `wss://friday-universe.duckdns.org/api/ws/activity`, read-only probe
  ~22:44 UTC: **20/20 backlog frames carry `recorded_at`** (full ISO, equal
  to each frame's `timestamp`), spanning 2026-11-22 09:31 to 2026-11-23 03:38
  UTC. The FRD-030 live-path channel is live on the served page's data feed.

### Fix 4 — Conversation panel height-bounded — PASS (served bundle)
Served CSS `38kl_eetk15n9.css`:
`.ultron-chat-panel{height:clamp(300px,42dvh,480px);min-height:300px}` —
present exactly as FRD-029 specified; the stream scrolls inside the panel.

## 4. What is NOT claimed here

- **No screenshot.** The VM's Chromium (`/opt/meta-chromium/chrome`) refuses
  to start — `Hatch WebGL domain policy is required for browser startup` —
  even with `--disable-webgl`; no other browser or Playwright is installed.
  The visual leg (actually seeing the banner unwrapped, rows scrolling, times
  rendered, panel scrolling at 1438x832 in a real browser) is therefore
  **open, not failed**: it needs a live-browser screenshot task, which this
  run cannot perform. The curl evidence above is complete for the
  "screenshot/curl" acceptance alternative, but a screenshot would close the
  last visual gap.
- **No live-append row observed.** No new daemon action arrived during the
  ~12s WS read window, so the live-append rendering path is verified at code
  level (`activityFrameTime` in the served JS) plus backlog level (20/20),
  not by an observed live row.
- **FRD-038 is NOT one of the four, and it is NOT live.** Zero FRD-038
  markers (`controlSession`, `ControlGate`, `friday_prime_key`, `fcs1`) exist
  in any served chunk — consistent with Muse 5's first-hand finding
  (hub 7115061501: served export last built 2026-11-19 18:48, predates the
  Nov 23 fix). The FRD-038 deploy + live acceptance leg is TASK-FRD-042
  (Muse 5); no deploy, rebuild or restart was attempted here — no clearance
  exists for it.
- **Ambient state, not a verdict driver:** `GET /api/status/public` returned
  `overall: degraded` (5/9 agents healthy) and `/friday/health` returned
  `overall: healthy` at the same time; neither affects the four fixes.

## 5. Verdict

**4/4 website fixes are live on the served page**
(`https://friday-universe.duckdns.org/`, export identical to the committed
`FRIDAY/ui/out` at main `440fbfd0`): vision banner wraps, Core Modules rows
scroll in-panel, Activity Log carries real timestamps on both the seed and
live paths, conversation panel is height-bounded. The FRD-029/FRD-030
"merged but not live" lesson does **not** recur for these four — the served
bundle is the fixed bundle. One follow-up remains open and is not a failure
of these four: a real-browser screenshot at 1438x832 to close the visual leg,
and separately the FRD-038 fix still awaits its FRD-042 deploy.

— Muse 1, 2026-11-24 ~04:45 IST
