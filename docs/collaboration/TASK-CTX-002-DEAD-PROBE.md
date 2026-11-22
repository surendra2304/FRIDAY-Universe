# TASK-CTX-002 — Cortex dead ai-universe probe: evidence

Task: fix or remove the dead `ai_universe` health probe
(`INFERENCE_BASE_URL` / `AI_UNIVERSE_BASE_URL` unset in production) +
file 48h fires-vs-messages evidence.

- Assignment: coordinator POOL 8 (issue #35 comment 7077110975, ~14:52 IST).
- Claim: issue #35 comment 7079118491 (~17:57 IST). Branch `muse9/task-ctx-002`.
- Work: implementation by subagent (survey + code + tests); verified first-hand
  by Muse 9 (diff read in full, tests re-run, live logs + live target probed
  from Server 2). The subagent errored (output cap) before reporting; the
  work it left was reviewed line by line, black reformatting of untouched
  lines was reverted, one ruff import-order error was fixed, and the remaining
  verification was done by Muse 9 directly.

## 1. The defect (before)

`Cortex/apps/api/src/cortex_api/self_healing.py::probe_ai_universe` only
resolved the configured host's DNS (`loop.getaddrinfo`). With
`INFERENCE_BASE_URL` and `AI_UNIVERSE_BASE_URL` both unset — the production
state — it returned `ProbeResult.UNCONFIGURED` every cycle. The supervisor
(`Cortex/packages/core/src/cortex_core/resilience.py::run_cycle`) records no
circuit outcome for UNCONFIGURED, never repairs, never escalates: the probe
observed nothing at all. Suppressed noise, not health. (The PR #1054 dedupe
fix, proven live as 71 fires / 1 message per the board record, only throttled
the symptom.)

## 2. Live 48h evidence (before the fix)

Source: `journalctl -u Cortex.service --since "48 hours ago"` on Server 2
(Cortex runs there), read 2026-11-22 ~18:00 IST. Window covers
Nov 20 18:31:54 → Nov 22 ~18:0x IST, 1,858 lines.

- `ai_universe` lines in 48h: **5**, all identical — the standing
  configuration notice, one per process start (different PIDs):
  - Nov 20 21:34:18 (pid 561987), Nov 20 23:47:20 (pid 563317),
    Nov 20 23:58:31 (pid 563591), Nov 21 00:47:56 (pid 565184),
    Nov 22 12:16:58 (pid 584499, 20 s after the 12:16:38 service start).
  - Text: `self-healing: subsystem ai_universe is not configured; treating
    as a standing configuration notice (no repair, no escalation)`.
- `telegram` lines in 48h: **0**. `escalat` lines: **5** — the same 5 notice
  lines (they contain "(no repair, no escalation)").
- Fires: **~5,760 derived, not counted.** The loop ticks every 30 s
  (`self_healing_interval_seconds` default 30, `self_healing.py:199`;
  sleep in `resilience.py:599`), so ~5,760 probe executions ran in 48h.
  The loop logs nothing per cycle, so the exact count is unobservable from
  logs — the 5 notice lines are the only trace, and no repair, escalation
  or delivery line exists for `ai_universe` anywhere in the window.
- Production env: `/opt/friday_universe/Cortex/.env` contains **0**
  occurrences of `INFERENCE_BASE_URL=` and **0** of `AI_UNIVERSE_BASE_URL=`
  (presence counts only; values not read). `SELF_HEALING_ESCALATION_WEBHOOK`
  is present (1 occurrence) — a channel is configured, but the probe gave it
  nothing to deliver.
- Service state: `Cortex.service` active since Nov 22 12:16:38 IST
  (restarted ~5h45m before this check). Deployed checkout
  `/opt/friday_universe` HEAD `c373615`; deployed `self_healing.py` still
  contains `getaddrinfo` — the old probe is what is running live.
- `GET /v1/friday/self_healing` was **not** queried: it returns HTTP 401
  without `X-Friday-Api-Key`, and the key was not read or used. The
  in-process delivery/suppressed counters are therefore unverified live
  (gap G3 below).

Conclusion for the 48h window: fires ~5,760 (derived) vs Telegram messages
**0** — at the designed ratio only in the trivial sense that an
unconfigured probe can never fire a real alert. The probe contributed no
health signal in 48h.

## 3. The fix (after)

`probe_ai_universe` now performs `GET {base}/health` and reports HEALTHY
only on HTTP 200 from a gateway that says it is healthy:

- Base URL precedence: `INFERENCE_BASE_URL` > `AI_UNIVERSE_BASE_URL`
  (legacy migration fallback) > fleet default
  `http://10.0.0.121:8001` (Inference on Server 1, port 8001 — the verified
  production layout, `AGENTS.md` "Verified Production Deployment"; Cortex
  on Server 2 reaches Server 1 over the private network, not via the public
  Caddy/DuckDNS ingress).
- 5.0 s timeout (`PROBE_TIMEOUT_SECONDS`); `trust_env=False`, mirroring
  `EscalationNotifier` — ambient proxy env must not intercept the probe.
- Tri-state (TASK-COR-014) kept: a set-but-unparseable URL (no host) is
  UNCONFIGURED; any transport failure, non-200, or a 200 body whose
  `status` is not `"healthy"` is UNHEALTHY; a 200 with no `status` field or
  a non-JSON body is HEALTHY (liveness only).
- Repair path unchanged: `repair_ai_universe` still only re-installs the
  deterministic fallback and never claims success.
- `Cortex/.env.example` documents that an unset URL now probes the fleet
  default instead of reporting unconfigured.

The fix was chosen over removal: the probe now checks the real dependency
(Inference is the gateway Cortex deliberations depend on), so it carries a
real signal instead of a standing notice.

## 4. The target is real (verified live)

Inference's `GET /health` (`Inference/app/health.py::basic_health`,
mounted at the app root, `Inference/app/main.py:322`) returns
`{"status": "healthy", "service": "inference", ...}` with HTTP 200.

Live probe from Server 2, 2026-11-22 ~18:33 IST
(`curl http://10.0.0.121:8001/health` — the exact call the new probe makes):
HTTP 200, `{"status": "healthy", "service": "inference", "agent":
"Inference", "evidence_class": "process_liveness", "active_specialist_agents":
19, "version": "2.0.0"}`. The fleet-default target answers exactly as the
probe expects.

## 5. Tests (run locally, 2026-11-22 ~18:0x IST)

Venv `/tmp/ctx002-venv`, Cortex deps installed from `Cortex/pyproject.toml`:

- `tests/unit/test_cor014_unconfigured_probe.py`: **23 passed**. New tests
  pin the HTTP contract: fleet default used when both URLs unset (healthy
  and down cases), URL precedence, legacy fallback, unreachable/timeout/
  non-200/degraded-body → UNHEALTHY, 200 without `status` / non-JSON →
  HEALTHY, 5.0 s timeout + `trust_env=False`, end-to-end through the
  supervisor (healthy pass; down escalates once the repair budget is
  exhausted).
- `test_f1_self_healing_probe_async_http` in both
  `tests/unit/test_e2e_tier1.py` and `tests/e2e/test_e2e_tier1.py`:
  **2 passed** (mocked `httpx.AsyncClient`, asserts the exact
  `GET {base}/health` URL).
- The two tier-1 files together: **151 passed, 19 failed. The 19 failures
  are pre-existing**: the identical failure set (same 19 test IDs) was
  reproduced on the stashed base (`git stash`, re-run, `git stash pop`) —
  shared-client lifecycle, Memora adapter, peer-transport backoff, plan
  payload, README/env-table checks; scratch-env gaps, not caused by this
  change. (Same pattern as the PR #1330 CI repro: proxy-env/module gaps.)
- `ruff check` on all four changed Python files: **clean** (one import-order
  error found by Muse 9 in review — stdlib `urllib.parse` before third-party
  `httpx` — fixed).
- No new test file was added, so no contracts-workflow file-list change was
  needed. Base files were not black-clean and CI enforces neither black nor
  ruff on Cortex; the touched files were left in their original style except
  the new test helpers in `test_cor014_unconfigured_probe.py`, which are
  black-formatted.

## 6. Gaps and honest bounds

- **G1 — /health is liveness only.** Inference's `/health` docstring says
  "Report process liveness only; no dependency readiness is implied" — a
  degraded Inference still answers 200 healthy (the same REL-004 finding:
  9 of 10 agents return 200 while degraded). The probe is truthful about
  `/health`, not a readiness verdict. A `/ready`-based probe is a possible
  follow-up, not done here.
- **G2 — 48h fires are derived, not counted.** The loop logs nothing per
  cycle; ~5,760 is 48h × the 30 s tick. The observable facts are the 5
  notice lines and the absence of any repair/escalation/delivery line.
- **G3 — live supervisor state not queried.** `/v1/friday/self_healing`
  needs `X-Friday-Api-Key` (401 without it); the key was not read or used.
  In-process delivery/suppressed counters are unverified live.
- **G4 — not yet deployed.** The running Cortex still has the old probe
  (deployed HEAD `c373615` contains `getaddrinfo`). This PR is code-only;
  the behaviour change lands after merge + a coordinator-cleared Cortex
  restart/redeploy. The first 48h of the NEW probe's fires-vs-messages is
  the follow-up evidence owed after deploy.
- **G5 — 19 pre-existing tier-1 failures** (see §5), identical on base.

## Files

- `Cortex/apps/api/src/cortex_api/self_healing.py` — probe rewrite + docs.
- `Cortex/.env.example` — behaviour documented (3 comment lines).
- `Cortex/tests/unit/test_cor014_unconfigured_probe.py` — HTTP contract tests.
- `Cortex/tests/unit/test_e2e_tier1.py`, `Cortex/tests/e2e/test_e2e_tier1.py`
  — F1.2 probe test updated DNS → HTTP.
- `docs/collaboration/TASK-CTX-002-DEAD-PROBE.md` — this file.
