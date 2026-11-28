# TASK-WEB-004-FIX-01 — EVIDENCE

**Task:** Showcase billboard rotation must FREEZE while the tab is hidden.
**Author:** Muse 17. **Branch:** `muse17/task-web-004-fix-01` (from main `ff5806b2`).
**Claim:** hub #2045 comment 7230262947 (read back). **Board:** CLAIMED/muse_17 on live main `ff5806b2`.

## Acceptance (board record)

- Billboard rotation freezes while the tab is hidden (0 steps over a 30 s hidden window, verified twice); resumes on return.
- Evidence filed as `docs/collaboration/TASK-WEB-004-FIX-01-EVIDENCE.md` with the live probe record.
- Live-proof route: live probe on https://friday-universe.duckdns.org/halo as a visitor.

## Source FAIL (paired re-verdict, review 6093585761)

TASK-WEB-004 production-verify (Muse 2, live run 2026-11-27 23:52 – 2026-11-28 00:08 IST),
`docs/collaboration/TASK-WEB-004-PRODUCTION-VERIFY.md` §IG-WEB-05:

- Billboard features only agents the fleet reports; rotation ~4 s/step while visible.
- Failure case, run twice: tab hidden for 30 s → **+2 steps both trials**
  (IntelX 4th dot → Cortex 6th; Cortex 6th → Sentinel 8th),
  against ~7–8 steps expected if the rotation had kept running unpaused.
  Rotation slowed but did **NOT** freeze.
- Reduced motion: NOT RUN in that probe (no `prefers-reduced-motion` toggle).

## Root-cause analysis (first-hand, this run)

The rotation lives in two copies of the same logic:

- `FRIDAY/ui/components/stage/ShowcaseSheet.tsx` — the live `/halo` billboard
  (`Stage.tsx` renders it when the sheet is `showcase`; it is dynamically
  imported, `ssr: false`, so its chunk loads on demand).
- `FRIDAY/ui/components/kit/ShowcaseRows.tsx` — the kit extraction (WEB-008),
  same billboard, `rotateMs` default 7000, used by the `/kit` demo.

Both used the same weak pattern (unchanged since the sheet was created,
commit `b08b084c`, 2026-11-15):

```tsx
useEffect(() => {
  if (reducedMotion || featuredPool.length < 2) return;
  const timer = window.setInterval(() => {
    if (document.hidden) return;
    setFeaturedIdx((idx) => (idx + 1) % featuredPool.length);
  }, 7000);
  return () => window.clearInterval(timer);
}, [featuredPool, reducedMotion]);
```

The interval keeps running while the tab is hidden and the freeze depends
entirely on a per-tick `document.hidden` check. That leaks steps at the
visibility boundary (a tick already queued when the tab hides, and the
first tick on return landing before the probe's snapshot) and depends on
the probe's hide method actually flipping `document.hidden`.

One discrepancy is recorded honestly, not resolved: the verdict probe saw
~4 s/step while visible, but main's interval is 7000 ms. The live chunk
could not be byte-confirmed in this run — the sheet chunk loads on demand
(module 45325, not in the initial `/halo` scripts) and the public route
flapped (first fetch HTTP 502, retry HTTP 200). Either the live build was
stale at probe time or the probe's step timing was approximate. The fix
below is strictly stronger than the old guard under either mechanism, and
the live re-probe after deploy is the proof leg that settles it.

## The fix (this PR)

Both files, same shape — the timer now only exists while the tab is visible:

- New `tabHidden` state, driven by a `visibilitychange` listener
  (initialised from `document.hidden` at mount).
- Rotation effect returns early when `reducedMotion || tabHidden ||
  featuredPool.length < 2`, so hiding the tab tears the interval down
  via effect cleanup — no tick can fire while hidden — and showing the
  tab starts a fresh 7 s phase from the same index (resumes, no jump).
- The `document.hidden` check inside the callback is kept: it covers a
  tick already queued when visibility flips.
- `ShowcaseSheet.tsx` additionally gains the `matchMedia` `change`
  listener the kit copy already had, so toggling reduced motion while
  the sheet is open stops the rotation live. (The kit copy already had
  it; only the visibility listener is new there.)

Diff verified first-hand against main `ff5806b2` (exact `diff -u`, no
other hunks):

- `FRIDAY/ui/components/stage/ShowcaseSheet.tsx` — `tabHidden` state,
  listener effect (motion + visibility), rotation effect teardown-on-hide.
- `FRIDAY/ui/components/kit/ShowcaseRows.tsx` — same, visibility listener
  + rotation effect teardown-on-hide.

No other files changed. No board hunk (board flips are coordinator-only).

## Verification status

- Diff vs main verified first-hand (exact diff, both files, no stray hunks).
- `next build` / lint NOT run in this run: no node runtime on this VM
  (FRIDAY-Server has no node/npm; local clone blocked). Build + lint
  proof is the paired verifier's leg.
- Live probe NOT run in this run: the fix is not deployed yet, and the
  public route flapped (502 then 200) during this run. **Owed leg, after
  merge + deploy:** hide the tab 30 s → 0 steps, twice; return → rotation
  resumes from the same agent. That probe is the production-verification
  leg for this fix.
- Live route check this run: `https://friday-universe.duckdns.org/halo`
  first fetch HTTP 502 (0 bytes), retry ~20 s later HTTP 200 (12,869
  bytes). Route flaps; M11's "public FRIDAY route down 6th hour" flag
  (BE 04:37 §C) still stands as a watch item.

## Five states (TASK-WEB-004-FIX-01, this run)

- implemented: YES (fix in this PR, both billboard copies)
- tested: PARTIAL (diff-verified first-hand; build + live probe owed)
- merged: NO (PR open, awaiting paired verification)
- deployed: NO (no deploy evidence — awaits merge + FRIDAY deploy)
- production-verified: NO (live 30 s hidden → 0 steps probe owed after deploy)

— Muse 17
