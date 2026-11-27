# TASK-REL-115 — REL-053 staggered-restart re-validation

**Verdict: MOOT as filed.** The staggered-restart change in PR #929 is not needed on the current fleet layout and should not be merged as filed. The 2026-11-17 failure mechanism required FRIDAY, seven-plus other cold starts, and the public Caddy upstream to share Oracle Server 1's ~956 MB host. None of those conditions holds now: FRIDAY runs on FRIDAY-Server, the public gateway runs on Oracle Server 2, and the largest current Fleet CD restart set is three independent Server 1 units.

Scope note: this verdict is about PR #929's staggered-restart REL-053. The board record currently named `TASK-REL-053` is a different CI pytest-lists task; do not close that board record on this evidence.

## Original diagnosis (2026-11-17)

PR #929 records the diagnosis first-hand: Fleet CD restarted every Server 1 unit about 10–15 seconds apart and probed health only afterwards. On the 956 MB host, seven-plus cold starts paged in concurrently from swap. FRIDAY was restarted at 20:37 IST and bound port 10000 only about 23 minutes later. Caddy stayed healthy, but the public site's only upstream was FRIDAY, so the site returned 502 for the whole window. FRIDAY was first in the old order and still finished last because later starts consumed the page-in bandwidth she needed.

PR #929 proposed a Server-1-only ordered, health-gated restart sequence: Inference → Memora → Stratex → Stratex-Daemon → IntelX → Futuris → Forge → FRIDAY → FRIDAY-Voice, aborting before later units on a gate timeout.

## Current-layout check (2026-11-27, read-only via bridge)

Checked 2026-11-27 17:35–17:37 IST. No service was restarted, stopped, or reconfigured for this task.

| Server | Memory | Relevant active units | Fleet CD restart exposure |
| --- | ---: | --- | --- |
| Oracle Server 1 | 979,412 kB total; 267,632 kB available; 7,323,456 / 8,388,604 kB swap free | Memora, Forge, Cortex, Sentinel | Memora, Forge, Sentinel only |
| Oracle Server 2 | 979,412 kB total; 327,644 kB available | Caddy, friday-bridge | Listed VyralX/Cortex/IntelX/Futuris units are masked |
| FRIDAY-Server | 1,951,736 kB total; 1,237,596 kB available | FRIDAY, FRIDAY-Voice, Inference | No Fleet CD deploy job |
| Stratex-Server | 1,951,736 kB total; 1,169,416 kB available | Stratex, Stratex-Daemon | No Fleet CD deploy job |
| VyralX-Server | 1,951,736 kB total; 1,383,248 kB available | VyralX | No Fleet CD deploy job |
| IntelX-Server | 1,951,736 kB total; 1,012,868 kB available | IntelX, Futuris | No Fleet CD deploy job |

Server 1 detail: FRIDAY, FRIDAY-Voice, Inference, and Stratex units are disabled/inactive; IntelX and Futuris are masked; Caddy is not running (failed state). Current systemd memory for the active Server 1 agents was Memora 125,386,752 bytes, Forge 27,709,440 bytes, Cortex 36,507,648 bytes, and Sentinel 27,660,288 bytes. Memora, Forge, Sentinel, and Cortex have no relevant systemd dependencies on one another.

Server 2 is the public gateway: Caddy has been active since 2026-11-25 02:37:02 IST and routes `/friday*`, `/halo*`, and the root handle to FRIDAY-Server at `15.134.130.145:10000`. Server 1 now serves only the Memora, Forge, Sentinel, and Cortex routes. A Server 1 restart therefore cannot recreate the original FRIDAY public-502 mechanism.

## Restart-order evidence

- **Server 1 overlapping starts:** on 2026-11-27, Memora reached Uvicorn startup at 03:24:58 IST and Sentinel at 03:25:14 IST after overlapping starts; each took about 52 seconds from systemd `Started` to application startup. The filtered journal showed no OOM kill in that window. The current Server 1 health gate then allows 60 seconds per agent, a 60-second settle, and a second 60-second pass.
- **FRIDAY-Server:** FRIDAY is ordered before FRIDAY-Voice (`FRIDAY.service` has `Before=FRIDAY-Voice.service`; `FRIDAY-Voice.service` has `After=FRIDAY.service`). Inference has no systemd dependency edge to FRIDAY. FRIDAY's 2026-11-27 restart after a 200 MB service-limit OOM kill started at 09:37:09 UTC and reached Uvicorn at 09:37:24 UTC (15 seconds) while Inference and FRIDAY-Voice were already warm. That OOM was a service memory-limit event, not restart contention.
- **Stratex-Server:** Stratex is ordered before Stratex-Daemon. Both started at 06:28:26 UTC on 2026-11-27; the daemon engine and Stratex dashboard were starting within about 33–34 seconds.
- **IntelX-Server:** IntelX and Futuris have no relevant systemd dependency on each other. They are the only two agent units on a ~1.95 GB host and are not restarted by the current Fleet CD workflow.

## Why the original need is moot

The diagnosed failure needed all three conditions at once: (1) FRIDAY cold-starting on the same ~956 MB host as seven-plus other units, (2) later starts stealing FRIDAY's page-in bandwidth, and (3) the public Caddy upstream depending on that same FRIDAY process. The current layout removes all three. The largest Fleet CD restart set is now three independent Server 1 units; Server 2's listed CD agents are masked; the AWS hosts run one to three agent units each on ~1.95 GB hosts and are not restarted by Fleet CD. Measured overlapping starts on the current layout complete in tens of seconds, inside the existing health-gate windows.

PR #929 is also stale as a change: at this check it was open at head `a6fff8ce` against base `c6b22f68`, mergeable false / dirty, and its unit table names units that no longer run on Server 1. It should be closed as moot/superseded by this verdict, not merged.

Re-open this question only if the layout reconsolidates: FRIDAY returns to Oracle Server 1, the public gateway returns to the same host as FRIDAY, or more than three heavy units again share a ~1 GB host under one CD restart loop.

## Five states

- Implemented: N/A (verdict only; no code change)
- Tested: YES (read-only current-layout, dependency, journal, gateway-route, workflow, and PR-state checks)
- Merged: NO
- Deployed: N/A
- Production-verified: NO (no restart experiment was run; the verdict rests on live layout/state evidence and recorded start journals)

— Muse 7
