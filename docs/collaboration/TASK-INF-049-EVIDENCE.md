# TASK-INF-049 — Inference: close the INF-048 G-gaps

## Claim

- Claimed by Muse 7 on hub #2045, comment 7231568529 (2026-11-28 01:18:11Z).
- Branch: `muse7/task-inf-049-g-gaps`.
- Board record verified on main `d7602c74`: TASK-INF-049, P1, owner muse_7.
- Acceptance: (1) alias failover 6/6 passes on the live router; cut-second variation measured; pinning test + thinking trace filed. (2) Evidence filed as this file.

## Method (same construction as INF-048/INF-029/INF-019, so results are comparable)

- Prompt: the exact INF-019 probe A construction — code-review over 400 identical `def add` helpers, 35,214 chars; Gemini's own count 13,519 prompt tokens on every served direct trial. Model requested: `gemini-flash-latest`, `max_tokens=200`, `temperature=0`.
- Harness: `/tmp/inf049_measure_harness.py` on Oracle Server 1 (INF-048 harness adapted: 6 direct trials, 1 compressed trial, 3 gateway explicit-60s trials, longer content capture). Run as a separate process in the live Inference environment (`PYTHONPATH=/opt/friday_universe/Inference`, venv312, cwd `/opt/friday_universe/Inference`); the running service was never touched, restarted, or reconfigured. Run window: 2026-11-28 06:55–06:56 IST.
- Live settings read by the harness from the service's own config: `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` → primary slice `min(60 x 0.6, 15) = 15.0 s`. Unchanged.

## Live service state (verified first-hand, before and after the run)

- Live Inference on FRIDAY-Server: `Inference.service` active (running) since Thu 2026-11-26 06:43:04 UTC, Main PID 58827 — identical before and after the run. `/health` 200 via the S1 tunnel (inference v2.0.0, providers groq/cerebras/openrouter/gemini/nvidia, 19 active specialist agents), observed 2026-11-28T01:23:45Z and again 01:27:05Z.
- Key pools unchanged before/after (counts only; no key value read, printed, logged, or stored): gemini 15/15/0, groq 15/15/0, openrouter 15/15/0, nvidia 2/2/0, others 0 (total/active/quarantined). Failover log 0 → 2 events (the two gateway deadline cuts only).

## G1 — alias failover: 6/6

Every one of the 6 direct trials logged "Gemini model gemini-flash-latest experienced 503 high demand; failing over to gemini-3.6-flash" and was served as `gemini-3.6-flash`:

| Trial | Elapsed | Upstream latency | Served model | Finish | Prompt tokens | Completion tokens |
|-------|---------|------------------|--------------|--------|---------------|-------------------|
| 1 | 5.88 s | 1.89 s | gemini-3.6-flash | STOP | 13,519 | 70 |
| 2 | 7.00 s | 2.00 s | gemini-3.6-flash | STOP | 13,519 | 48 |
| 3 | 9.11 s | 1.31 s | gemini-3.6-flash | STOP | 13,519 | 47 |
| 4 | 5.68 s | 1.70 s | gemini-3.6-flash | STOP | 13,519 | 47 |
| 5 | 3.70 s | 1.59 s | gemini-3.6-flash | STOP | 13,519 | 44 |
| 6 | 3.40 s | 2.00 s | gemini-3.6-flash | STOP | 13,519 | 44 |

- **Alias failover count: 6/6** (acceptance met). Alias resolution is still not pinned: the `-latest` alias 503s on every trial and the in-adapter failover serves 3.6-flash. Combined with INF-048 (6/6 incl. compressed) and INF-029 (5/5), the alias has failed over on every measured direct trial to date.
- Note the speed contrast with INF-048 two hours earlier (median 53.10 s, 0/5 inside the 15 s slice): this run's upstream latencies were 1.31–2.00 s and all 6 elapsed times were inside 15 s. Gemini's latency on this prompt shape varies by more than an order of magnitude between windows; no mechanism is claimed for the difference.

## G2 — cut-second variation: 15.2 s, 15.0 s, and one no-cut primary serve

Three gateway-path trials, explicit 60 s budget:

| Trial | Elapsed | Served | Cut second (fallback provenance) |
|-------|---------|--------|----------------------------------|
| 1 | 22.10 s | openrouter / nvidia/nemotron-3.5-lightning:free | "Request deadline exceeded for provider 'gemini' after 15.2s" |
| 2 | 17.10 s | openrouter / nvidia/nemotron-3.5-lightning:free | "Request deadline exceeded for provider 'gemini' after 15.0s" |
| 3 | 10.20 s | gemini / gemini-3.6-flash | no deadline cut — primary served inside the slice (alias failover in-adapter; 12,719 prompt tokens on the compressed prompt) |

- This run's cut seconds: **15.2 s and 15.0 s** against the 15.0 s slice (+0.2 s, +0.0 s).
- Historical series: INF-019 14.7 s x2, LLM-003 14.7 s, INF-029 15.0 s, INF-048 13.1 s, INF-049 15.2 s / 15.0 s. Observed range across all runs: 13.1–15.2 s around the 15.0 s slice. The variation is real but small; in every cut case the fallback ladder served the request end-to-end inside the 60 s budget. No mechanism is claimed for the sub-second-to-2 s spread.
- Trials 1–2 cut despite the fast direct trials minutes earlier on the same prompt: the gateway path compresses the prompt and rotates keys (the direct compressed trial below 429'd), so gateway primary behaviour is not identical to the single-key direct path. Trial 3 shows the gateway primary serving inside the slice when it completes. Facts only; the deadline decision (KEEP 60.0/0.6/15.0) is unchanged by this run.

## G3 — thinking trace: confirmed again, both fallback trials

Both nemotron fallback serves returned a thinking trace and hit the 200-token cap:

- Trial 1: 720 chars, `finish_reason=length`, 200 completion tokens. Content opens: "Here's a thinking process:\n\n1.  **Analyze User Input:**\n   - User provides a Python module `utils.py` with 400 function definitions (helper 0 to helper 399)..."
- Trial 2: 722 chars, `finish_reason=length`, 200 completion tokens. Content opens: "Here's a thinking process:\n\n1.  **Analyze User Input:**\n   - The user provided a Python module `utils.py` with 400 function definitions (helper 0 to helper 399)..."

The trace consumes the whole 200-token budget before a final answer line (same observation as INF-029 G3 / INF-048 G3). Observation, not a defect claimed here.

## G4 — compression: no new completion sample (429)

The compressed prompt was 32,814 chars / 12,620 estimated tokens (same -7% shrink as INF-048), but the direct compressed trial failed in 0.20 s with "Gemini API rate limit exceeded across rotated keys (HTTP 429)" — no completion sample this run. G4 therefore stands as recorded: 23.52 s (INF-029) vs 50.01 s (INF-048), one sample each, compression does not reliably rescue the deadline.

## G5 — defaults-pinning test: added and CI-collected

- Test: `test_routing_deadline_defaults_are_pinned` in `Inference/tests/test_provider_gateway_deadlines.py`. It pins the shipped field defaults — `REQUEST_TIMEOUT` 60.0, `PRIMARY_ATTEMPT_FRACTION` 0.6, `PRIMARY_ATTEMPT_MAX_SECONDS` 15.0 — and the derived primary slice `min(60.0 * 0.6, 15.0) = 15.0 s`, so a silent default change fails CI instead of quietly moving the deadline the INF-029/047/048 measurements justify.
- Collection (verified first-hand on current main before the change): `scripts/ci_test_collection_audit.py --full` listed `Inference/tests/test_provider_gateway_deadlines.py` as UNCOLLECTED — the INF-048 G5 state, still true after REL-068 completed (the guard is diff-scoped; it does not retro-collect files). This PR adds the file to the Inference tier-1 invocation in `.github/workflows/friday-universe-ci.yml` (the INF-045 pattern), after which the audit no longer lists it as uncollected and `scripts/tier1_collection_gate.py` passes (21/21).
- Local run (CI-style venv from `Inference/requirements.txt` + pytest + pytest-asyncio + aiosqlite): `tests/test_provider_gateway_deadlines.py` 11 passed (7 parametrized deadline-validation + 3 deadline-behaviour + 1 pinning); full Inference tier-1 set 65 passed, 0 failed.

## G6 — daemon-reload warning: still present, flag-only

Re-checked on FRIDAY-Server 2026-11-28 ~01:24Z: `NeedDaemonReload=yes`; "Warning: The unit file, source configuration file or drop-ins of Inference.service changed on disk." The service is running fine (PID 58827, since 2026-11-26 06:43:04 UTC, `/health` 200). No reload or restart was performed — flagged for the coordinator, unchanged from INF-048 G6.

## Reproduction

Harness (kept on Server 1): `PYTHONPATH=/opt/friday_universe/Inference /opt/friday_universe/venv312/bin/python /tmp/inf049_measure_harness.py` from `/opt/friday_universe/Inference`. S1 artefacts: `/tmp/inf049_measure_harness.py`, `/tmp/inf049_measure.json`, `/tmp/inf049_measure.log`.

## States

- **implemented:** YES — live measurement run (G1/G2/G3/G4/G6) plus the defaults-pinning test and its CI wiring (G5). No routing, deadline, or service behaviour change.
- **tested:** YES — live measurement (6 direct + 1 compressed + 3 gateway) against the live FRIDAY-Server router; pinning test green locally (11/11 file, 65/65 tier-1 set).
- **merged:** NO — work PR open this run, awaiting Muse.
- **deployed:** NO — nothing to deploy (measurement + test/CI only; the live service was not touched).
- **production-verified:** YES for the measurement legs — the numbers above are production evidence from the live router. The pinning leg is verified repo-side (test green + collection audit clean); its CI run is on the work PR.

— Muse 7
