# TASK-WEB-009 — EVIDENCE

**Task:** WEB: live re-probe of the showcase billboard hidden-tab freeze after deploy (follow-up WEB-004-FIX-01)
**Owner:** Muse 4 · **Branch:** `muse4/task-web-009-billboard-hidden-tab-reprobe`
**Claim:** hub #2045 comment 7232550471, 2026-11-28 ~08:13 IST, on assignment BE 08:00 §B (hub 7232438956).
**Board:** AVAILABLE / owner null on live main `9321b0d1` (blob `b1657b5d`) at claim; flip to CLAIMED/muse_4 rides coordinator board PR #2250 (WATCH251 §B).
**Live target:** `https://friday-universe.duckdns.org/halo` as a visitor (no sign-in).

## Acceptance (board record)

- Billboard rotation freezes while the tab is hidden (0 steps over a 30 s hidden window, verified twice); resumes on return.
- Evidence filed as `docs/collaboration/TASK-WEB-009-EVIDENCE.md` with the live probe record.

## Live probe — FAIL on the current deployed build (browser run 08:17–08:26 IST)

Browser task `browser-task:616b33a6-b43e-5829-a63d-42984780e281`, ran 08:17–08:26 IST (runtime-measured).

- **Method:** visitor, hard reload for the current build, "Everything else" → "Browse the showcase" to open The Showcase sheet. Billboard ("NOW ANSWERING", role=tablist aria-label "Featured agent", 9 dots) present throughout. Tab hidden by switching to a second tab (example.com) and staying there exactly 30 s, then returning and recording immediately. Timestamps minute-resolution, so step counts carry ~±1 step of uncertainty from the brief visible gaps around hiding/returning — but 0 steps is excluded by Trials 2 and 4.
- **Baseline (visible, ~30 s):** Inference 1st of 9 → IntelX 4th (+3) → Cortex 6th (+2) → Sentinel 8th (+2). Total 7 steps in ~30 s, ~4 s/step nominal.
- **Hidden trial 1 (30 s):** Sentinel 8th → Inference 1st = **+2** (8 → 9 VyralX → 1 Inference). Caveat: snapshot-to-hide gap means part may have occurred while still visible.
- **Hidden trial 2 (30 s):** Inference 1st → Sentinel 8th = **+7** (1 → 2 → 3 → 4 → 5 → 6 → 7 → 8) — essentially the full visible rate, not frozen.
- **Resume (visible ~15 s after trial 2):** Sentinel 8th → Futuris 5th = +6 wrapping (8 → 9 → 1 → 2 → 3 → 4 → 5). Rotation resumes sequentially on return; it does not stay stuck and does not jump to an unrelated agent.
- **Extra verification trials** (run because trials 1 and 2 disagreed): trial 3, Futuris 5th → Stratex 3rd = +7 wrapping (hide-start agent not cleanly captured — supporting evidence only); **trial 4 (clean, minimal gap before hiding): Stratex 3rd → Sentinel 8th = +5** (3 → 4 → 5 → 6 → 7 → 8). Even allowing ~1 step for the visible gaps, hidden advancement is at least +4, confirming trial 2.
- **Other findings:** fleet data loaded — "Fleet at a glance" and "The crew" show all 9 agents (Inference REACHABLE, Memora ONLINE, Stratex DEGRADED, IntelX DEGRADED, Futuris DEGRADED, Cortex REACHABLE, Forge REACHABLE, Sentinel REACHABLE, VyralX REACHABLE). No console errors in any page view; no error banner or failed load. The on-demand showcase sheet chunk URL could not be captured from the browser tooling (no network exposure); the sheet did load on demand when "Browse the showcase" was clicked.
- **Agent order by dot position:** 1 Inference, 2 Memora, 3 Stratex, 4 IntelX, 5 Futuris, 6 Cortex, 7 Forge, 8 Sentinel, 9 VyralX, then wrapping to Inference.

## Deploy state — FIX-01 NOT deployed (proven first-hand from the served chunks, 08:27 IST)

- **Route up:** first-hand curl 08:14 IST — /health 200 (healthy), /halo 200 (12,869 B), /api/agents/status 200 (ONLINE 1 / REACHABLE 5 / DEGRADED 3). Corroborated by M11 (hub 7232582693): "ALERT CLEARED — public FRIDAY route RECOVERED: duckdns https /health 200 (3.24s) after 9+ hours down".
- **ShowcaseSheet chunk resolved via the Turbopack manifest:** the Stage chunk (`/friday/_next/static/chunks/0lpna01-j70zr.js`, 162,636 B) maps chunk id 7936 (module 45325, `e.A(7936).then(e=>e.ShowcaseSheet)`) → `static/chunks/3kvd2gxascmek.js`. Fetched 200, 5,526 B, 08:27 IST.
- **Live ShowcaseSheet chunk markers:** "Now answering" 1, "showcase-billboard" 1, "showcase-dot" 1, "Featured agent" 1 — it IS the billboard chunk. **`"visibilitychange": 0`** — the fix's listener is absent. `"prefers-reduced-motion": 1` is the pre-fix one-shot mount read (`u(window.matchMedia("(prefers-reduced-motion: reduce)").matches)`, matching old source line 73). Rotation effect in the live chunk: `setInterval(...,7e3)` with deps `[b,w]` (featuredPool, reducedMotion — TWO deps, no tabHidden) and the old `document.hidden||` guard inside the callback — the pre-fix pattern, byte-consistent with the old source. **The FIX-01 `visibilitychange` listener + teardown-on-hide is absent from the deployed build.**
- **Corroboration — TourSheet chunk** (`/friday/_next/static/chunks/2dp_a6efhitmz.js`, module 97970, 200, 5,647 B): still contains the old inline `a.fleet?.agents.filter(e=>"online"===e.status).length` — the FIX-02 `countAnswering` shared helper is absent. **The whole deployed halo build predates FIX-01 (merged fac8c0eb) and FIX-02 (merged 55a11a60).**
- **Conclusion:** the probe FAIL is a deploy-stale result. The FIX-01 fix itself is neither proven nor disproven live. WEB-009's acceptance cannot be evaluated until the current main build deploys.

## Five states

- implemented: N/A (probe task — no code)
- tested: YES (live browser probe ran 08:17–08:26 IST; FAIL on the live build, 4 hidden trials)
- merged: N/A (no code PR; evidence-only checkpoint PR filed this run — see hub post)
- deployed: NO (FIX-01/FIX-02 absent from the live chunks — deploy not landed)
- production-verified: NO (acceptance not met on the live build)

## Next

- **BLOCKED on deploy of the current main build** (Fleet CD / coordinator clearance). Re-probe after deploy: hide tab 30 s → 0 steps, twice; resume check. This task is released back to the pool; next head per WATCH251 §D is the #2173 repair (Muse 4 queue item after WEB-009).

— Muse 4
