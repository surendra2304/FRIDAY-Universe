# TASK-REL-045 — Universe-wide parameter inventory & tuning table

**Crew:** muse_ai · **Date:** 2026-11-15 · **Claim:** issue #35 comment 6892549916
**Mandate:** owner's directive 2026-11-15 — the coordinator sets the *best* value for every
consequential setting across all 10 agents, including settings the owner himself chose,
based on evidence, not defaults or habit.

## Method and scope rules

- **Inventory source:** live reads on both servers on 2026-11-15 (each agent's `.env`,
  systemd unit files, and deployed code), taken read-only through the bridge. Secret-named
  variables were recorded by name only; no key material appears anywhere in this document.
- **Evidence source:** the current audit/benchmark waves — FRD-003, TASK-INF-004
  (Inference latency/cost profile), INF-005, INF-003-W5, MEM-002, VOI-008/009, TASK-OBS-003
  (fleet honesty sweep), FUT-004/005, INT-003, COR-002, SEN-002, REL-010/032/039/043/044.
- **This task changed NO live setting.** Verdicts:
  - **KEEP** — measured evidence supports the current value.
  - **TUNE** — measured evidence supports one specific better value, stated exactly.
    The coordinator approves; a per-agent follow-up crew implements and verifies.
  - **UNKNOWN** — no measurement exists yet. The exact measurement that would settle it
    is named. **No UNKNOWN parameter is guess-tuned.**
- **Out of scope:** all Stratex *trading* parameters (owned by FWD-006/RISK-001) —
  recorded in the appendix for reference only. Voice-worker internals are evidence-only
  until VOI-009 merges (file-collision rule); one already-decided item is recorded as such.

## Fleet-wide (systemd, both hosts)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| MemoryMax — FRIDAY | 200M | UNKNOWN | Measurement: 7-day OOM-kill + restart count and memory.pressure from the S1 journal (SEN-003 corpus). If OOM kills > 0, follow-up evaluates 220M against host headroom. | Working set measured at the cap (199.9M/200M, 2026-11-14); no OOM-kill count exists yet in any wave. |
| MemoryMax — all other agents | 180M (S1: Inference/Memora/Stratex/Futuris/IntelX/Forge), 200M (Cortex/Sentinel), 250M (VyralX), 350M (VyralX-Daemon) | KEEP | — | TASK-OBS-003 live sweep 2026-11-15: all 10 agents responsive inside caps; no wave reports a memory-cap failure outside FRIDAY/voice, both handled separately. |
| Restart policy | Restart=always, RestartSec=5, TimeoutStopSec=10 (uniform) | KEEP | — | No restart-storm or flapping evidence in any 2026-11-15 wave. |
| fleet-health-watcher.service | inactive (dead) on BOTH hosts | UNKNOWN | Measurement: journal diagnosis of why it died on each host; TASK-OBS-003's manual scorecard is the stopgap until then. | `systemctl` read 2026-11-15 (this sweep) on Server 1 and Server 2. |

## FRIDAY (Server 1, :10000)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Chat request ceiling | 300 s (`api/server.py`: `future.result(timeout=300)`) | KEEP | — | Backend contract the website is built on; FRD-003 journal sample shows completed LLM turns at 8.6–24.5 s — the ceiling is not the constraint, turn latency is. |
| LLM confidence gate (`/v1/friday/ask`) | 0.70 (`llm/ai_universe_provider.py`: `min_confidence=0.70`) | KEEP | — | REL-044 live probe: a capped 35-word answer at confidence 0.55 was correctly rejected by this gate; escalation was redesigned around it rather than weakening it. |
| Escalation depth `FRIDAY_LLM_ESCALATION_DEPTH` | 3 (code default; not set in .env) | UNKNOWN | Measurement: REL-044's production escalation logs over ~2 weeks — trigger/depth distribution vs turn outcomes. | REL-044 shipped 2026-11-15; no production distribution exists yet. |
| Proactive watcher interval `FRIDAY_WATCHER_INTERVAL_SECONDS` | 120 s (enabled) | UNKNOWN | Measurement: PRO-001 event log — alert latency attributable to the 120 s poll, plus watcher CPU share on the 956 MB host. | No wave has measured watcher cost/benefit; FRD-003 recorded host load ≈5 during probes, so cadence cost is worth measuring before touching. |
| Own-pool routing (provider/models) | provider=gemini, chat gemini-3.6-flash; Groq text failover openai/gpt-oss-120b; OpenRouter meta-llama/llama-3.3-70b-instruct | KEEP | — | REL-010 pool-exhaustion failover production-verified; REL-039 tool-discipline fix; owner's architecture (Gemini voice / Groq text). |
| `FRIDAY_UNIVERSE_API_URL` | `http://localhost:8000` — nothing listens on :8000 on either host | UNKNOWN | Measurement: grep the deployed tree for readers of this variable + journal scan for :8000 connection errors. If a live path reads it, it is a latent dead endpoint; if unread, follow-up removes it as config hygiene. | .env read + service/port inventory, this sweep, 2026-11-15. |

## FRIDAY-Voice worker (Server 1) — evidence-only until VOI-009 merges

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Warm pool `num_idle_processes` / executor | 1 / THREAD (+ prewarm hook) | KEEP | — | VOI-008 implemented and production-verified this (was 0): greetings 22.16/15.78/4.69 s vs 25.6 s baseline; a PROCESS executor (~150–250 MB) cannot fit the host, THREAD can. |
| MemoryMax / MemoryHigh | 300M / 250M | KEEP | — | VOI-008 measured peak 242 MB — inside the hard cap with deliberate headroom; soft limit correctly below hard limit. |
| Owner-memory recall budget on the greeting path | 7.0 s (`asyncio.wait_for(..., timeout=7.0)`, on the critical path) | TUNE | **Decouple recall from the greeting path** — greet first, recall asynchronously. Implementation sequenced *after* VOI-009 merges (same worker file). | VOI-008 decomposition of the 25.6 s greeting: recall leg ≤7 s is the largest single remaining on-path leg; post-fix greetings still 15.8–22.2 s on an idle host and 47.4 s under load when recall hit its timeout. Owner's acceptance criterion is speed-first. Coordinator decision already taken under the 2026-11-15 autonomy mandate; recorded here as the tuning decision. |
| Voice brain / delegation budget | 60 s | UNKNOWN | Measurement: FRD-005 acceptance harness per-turn latencies after VOI-009 lands. | VOI-008 follow-up: delegations timed out at ~60 s under load while Stratex `/health` answered in 0.088 s — the defect was the delegation path (VOI-006 single-flight fix), not the budget's size. No evidence indicts 60 s itself. |


## Inference (Server 1, :8001)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Groq-rung prompt-size guard, unified/agent-role path | **Absent** (the chat/completions path has REL-043's long-context guard; the unified path does not) | TUNE | **Route prompts > 7,000 tokens away from Groq rungs** on every path (mirror the REL-043 guard). | TASK-INF-004 journal analysis: ≥6 deterministic HTTP 413s in one hour — prompts of 9,876–11,207 tokens against Groq's 8,000 TPM free-tier cap. A guard threshold of 7,000 leaves response headroom under the cap. |
| NVIDIA rung in the fallback ladder | Enabled, with a configured function id that 404s on both accounts | TUNE | **Disable the rung** (skip in ladder) until a probe-verified model id exists (INF-003-W5-style metadata probe). | TASK-INF-004: 8 nvidia ladder entries in one hour, ≥7 of them HTTP 404 "function id not found" — every hit burns ladder time on a rung that cannot answer. |
| OpenRouter discovery cache | TTL 300 s, **per provider instance** — the gateway builds a fresh instance per fallback attempt, so the cache can never hit in production | TUNE | **TTL stays 300 s; scope becomes module-level shared** (keyed by base_url, single-flight, successes only). Implemented in TASK-INF-004's PR, awaiting coordinator merge. | TASK-INF-004: catalogue fetch is 850,791 bytes, 0.59–1.10 s from Server 1, paid on *every* fallback (≈14–25 s/hour of critical path at the measured failure rate). Isolated harness, before/after: 10 fallbacks = 8.10 s → 0.85 s discovery wall time, same model selected. |
| Total request budget / primary fraction | ~60 s total, primary fraction 0.6 (measured from the timeout signature: Gemini primaries time out at exactly ~36 s) | UNKNOWN | Measurement: A/B primary fraction 0.6 vs 0.4 on the local staging fleet (TASK-REL-046 harness) — p95 latency + success rate per arm. | TASK-INF-004 `/metrics` window: p50 0.402 s, p95 29.9 s, p99 48.4 s — the tail is failure cascades governed by this budget split, but no comparative measurement exists. |
| Verified catalogue + best-suitable selection | 7 verified-live model ids; REL-043 suitability policy | KEEP | — | REL-043 VERIFIED (PRs #278/#291 merged, deployed, fingerprint-verified, live probes incl. retired-id containment). |
| Key-pool composition | Gemini 11 + Groq 14 + OpenRouter 14 primary; third-party 4/1/1 kept separate | KEEP | — | INF-003-W5 live sweep 2026-11-15: 45/45 keys accepted, 0 dead, 0 exhausted (acceptance probe ≠ remaining generation quota — INF-007 owns quota accounting). |
| Internal cache TTLs | dedup/idempotency 300 s; token-optimizer 3,600 s default (per-domain table); telemetry cache 86,400 s / 5,000 entries; market-data 5–10 s | UNKNOWN | Measurement: INF-006's caching/staleness audit — any surface where a TTL serves an answer the owner would consider stale. | Values inventoried from deployed code this sweep; no wave has measured staleness harm. The response-cache L1 itself is proven working (INF-004: repeat hits at 0.01–0.19 s). |

## Memora (Server 1, :8002)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| `ENVIRONMENT` / `APP_ENV` | `development` / `development` (while `MEMORA_ENV=production`) | TUNE | **`production` / `production`**, matching `MEMORA_ENV` and every other agent. The follow-up crew must re-run the MEM-005 auth matrix immediately after the flip and report any behaviour change. | This sweep's .env read: Memora is the only production service whose generic env flags say "development". MEM-005's code audit showed Memora's auth production check reads these flags (`MEMORA_ENV` *or* `ENVIRONMENT`) — mixed flags are a latent fail-open surface in any code path that reads only `ENVIRONMENT`. |
| `DEFAULT_CONFIDENCE_THRESHOLD` | 0.75 (.env and `core/config.py`) | UNKNOWN | Measurement: MEM-002 probe set swept at 0.65 / 0.75 / 0.85 — fresh-fact rank vs noise admissions per value. | No wave has varied this threshold; MEM-002's benchmark gives the instrument to do it. |
| Lexical candidate window | `min(max(limit×100, 500), 5000)` → 500 at FRIDAY's production limit=5 | UNKNOWN | Measurement: MEM-002 benchmark on its 600-decoy corpus at window 500 vs 2,000 — recall position + search latency. | MEM-002 proved the *ordering* starved fresh facts at this window and fixed the ordering; whether the window's *size* also binds is unmeasured. |
| Memory decay / freshness | decay_rate_per_day 0.02; reranker freshness half-life 60 d | UNKNOWN | Measurement: MEM-006's planted-fact ageing test (plant → age → recall) against both constants. | Values inventoried from deployed code; no ageing measurement exists. |
| `REDIS_URL` | `disabled` | KEEP | — | Owner decision: Redis/Qdrant provision after the ARM server exists. REL-013/024 show the Oracle-native path performing (fresh-fact positions 54/100 → 4/4/3 after fixes). |
| `VECTOR_DIMENSION` | 1536 | UNKNOWN | Measurement: one-line check — stored embedding dimensions in the production store vs this constant and the embedding model's output dimension. | Inventoried this sweep; semantic search demonstrably works (REL-013/024), so this is a consistency check, not a suspected defect. |

## Futuris (Server 1, :8004)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Forecast refresh / ingest cadence | refresh 60 min, ingest 15 min, horizon 24 h, nightly backtest 02:00 | KEEP | — | FUT-005: stored forecasts are stale from 2026-11-14 because refresh *honestly skips* while the statsforecast backend is absent (post-ARM owner decision) — cadence is not the binding constraint, the missing producer is. |
| Prediction-interval level | 0.95 in the scheduler's outcome path; 0.90 nominal in TASK-FUT-004's evaluation protocol | UNKNOWN | Measurement: FUT-004's completed synthesis + FUT-008 — reconcile to a single level and verify empirical coverage ≈ nominal on scorable series. | FUT-004 harness fragments show empirical coverage of nominal-90% intervals ranging 0.4–1.0 across horizon steps on the scorable heuristic series (the crew errored before publishing its synthesis). Two different levels in two live surfaces is itself the finding. |
| `LLM_PROVIDER` | `none` | KEEP | — | REL-018 fail-closed provenance design; FUT-005 verified market forecasts are 503-or-live and name their real producer (`heuristic:telemetry_vol_rule@v2`). |

## IntelX (Server 1, :8005)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Inference call timeout (`ai_universe_provider.py`) | 45.0 s | TUNE | **60 s** — align with the Inference gateway's own ~60 s request budget. | TASK-INF-004 measured the gateway's p99 at 48.4 s: IntelX currently abandons calls at 45 s that the gateway would have answered inside its own budget. |
| Source caps | 30 (web form) / 25 (research agent) / 20 (synthesis) | UNKNOWN | Measurement: INT-003's D1 source-diversity / D2 primary-ratio scores read against these caps + INT-004's diversity audit — if scores saturate below the caps they are inert; if synthesis starves, raise the synthesis cap first. | INT-003's rubric and runs exist; nobody has yet read them against the caps. The effective cap today is the synthesis layer's 20. |
| `LLM_MODEL` (via Inference) | `llama-3.3-70b-versatile` | UNKNOWN | Measurement: check the id against REL-043's verified catalogue (7 ids). If absent, the follow-up repoints to the catalogue's research-class pick (REL-044 chose `openai/gpt-oss-120b` for research on live probes). | REL-043's containment PR (#291) exists because non-catalogue ids get substituted behind selection; whether this id is in the catalogue has not been checked. The identical value in VyralX's .env is settled by the same check (see VyralX). |
| `MOCK_MODE` / `INTELX_MOCK_MODE` | false / false | KEEP | — | IntelX's research output is real and measured (REL-016/021, INT-003) — the correct contrast to Cortex below. |

## Forge (Server 1, :8006)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| `MODEL_TEMPERATURE` | 0.2 | KEEP | — | REL-028's first end-to-end successful build (verification battery 11/11, 69 pytest) and FRG-003's acceptance battery both ran at 0.2; no failure in any Forge report is attributed to temperature. |
| Self-repair attempt cap / build timeout | Code defaults, not env-exposed (exact values not extracted by this sweep) | UNKNOWN | Measurement: FRG-005's convergence distribution (attempts-to-converge per planted defect class) → set the cap at p95 + 1; extraction of the current defaults is part of the same follow-up. | FRG-005 is measuring exactly this distribution now; tuning before it lands would be guessing. |
| Fallback model ids | `OPENAI_DEFAULT_MODEL=gpt-4o`, `ANTHROPIC_DEFAULT_MODEL=claude-3-5-sonnet-20241022`, with `DEFAULT_PROVIDER=direct` | UNKNOWN | Measurement: grep FRG-003/FRG-004 build logs for the provider/model that actually served. If the Anthropic id is ever selected, it is a retired-era id and will fail at call time — repoint or remove in the follow-up. | REL-032 established the fleet precedent: retired model ids presented as live were a real defect class in Inference's catalogue. Whether Forge's fallbacks are reachable is unmeasured. |


## Sentinel (Server 2, :8008)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| `SENTINEL_BLOCK_ON_MEDIUM_CVES` | false | KEEP | — | SEN-002: the fleet's dependency backlog is carried as report + fix PRs (18 CVEs sat behind Sentinel's own exact pins alone). Blocking deploys on *medium* findings would freeze the fleet's fix pipeline; no incident is traced to this setting. |
| `SENTINEL_AUTO_KILL_SWITCH_ENABLED` | false | KEEP | — | SEN-001 production-verified the veto path when invoked deliberately (planted AWS key → VETO). An automatic kill on a shared 956 MB host, with no false-positive measurement, would be the riskier setting. |
| Anomaly z-score threshold (`real_security_engine.detect`) | 3.0 | UNKNOWN | Measurement: SEN-003's 7-day log corpus — count anomaly fires and hand-label a sample for false-positive rate. | No fire-rate or FP measurement exists in any wave. |
| Threat-intel severity cutoffs | score >15 critical / >10 high / >5 medium; CVSS ≥7.0 treated as high | UNKNOWN | Measurement: same SEN-003 corpus — distribution of scores assigned vs the cutoffs (bunching at a boundary would indict it). | Inventoried from deployed code; unmeasured. |

## Cortex (Server 2, :8009)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Decision missing-score default (`decision_recommendation_system.py`) | **0.5**, silently, for any score cell the caller didn't supply (`.get(crit_id, 0.5)`, two call sites; the same 0.5 default seeds `risk_score`/`return_projection`) | TUNE | **No silent default: reject an incomplete score matrix (HTTP 422).** A decision may not be computed from invented cells. | COR-002 controlled live probe #1: a 2×2 matrix with only 1 of 4 cells supplied returned a confident recommendation (confidence 0.5833) in which 75% of the inputs were this default, with no basis recorded in the output. |
| `MOCK_MODE` (integrations layer) | `true` in .env; the integrations package default is also `"true"` when unset | UNKNOWN | Measurement: COR-003's decision-log audit + one live probe of an integration-backed surface — do fixture responses reach owner-facing output? Several integration credentials exist by name in .env, so if surfaces serve fixtures, this flips to TUNE → `false` with per-integration verification. | COR-002 verified the *decision* surfaces run real logic; the CRM/integration clients (SendGrid/Twilio/HubSpot class) are governed by this separate flag and were not probed. |
| `REDIS_URL` | `redis://localhost:6379/0` — no Redis is provisioned (post-ARM owner decision) and nothing in the fleet inventory listens on 6379 | UNKNOWN | Measurement: check for a 6379 listener on Server 2 + count Redis connection errors in the Cortex journal. If the event stream silently drops, the follow-up either points Cortex at the same explicit `disabled` convention Memora uses or wires its Oracle-backed path. | .env read + service inventory, this sweep; Memora's honest `REDIS_URL=disabled` is the contrasting convention. |

## VyralX (Server 2, :8010 + VyralX-Daemon)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| `MAX_CONCURRENT_RENDERS` / `RENDER_MAX_CPU_THREADS` | 1 / 1 | KEEP | — | Host reality: 956 MB RAM shared with Sentinel/Cortex/bridge, daemon MemoryMax 350M. VYR-003's proof render succeeded at these values; raising concurrency risks OOM-ing neighbours for unmeasured gain. |
| `MAX_RENDER_SECONDS` | 14,400 s (4 h) for videos that are 15–60 s long | UNKNOWN | Measurement: render-duration distribution from the production RENDER_JOBS table (46 renders in VYR-005's autopsy corpus) → set the cap at ~3× p99. A stuck render at the current cap monopolises the single render slot for 4 h × up to 3 attempts. | VYR-005 autopsy data exists; nobody has computed the distribution. |
| `RENDER_MAX_MEMORY_MB` | 512 — larger than VyralX-Daemon's MemoryMax (350M) | UNKNOWN | Measurement: read the consuming code path (ffmpeg limit vs supervisor budget) + cgroup OOM events during the largest renders. If the budget governs a subprocess, align to ≤320 MB so the cgroup doesn't kill the daemon first. | Arithmetic from this sweep's inventory (512 > 350); which mechanism the value drives is unverified, so no value is decided yet. |
| `AUTONOMOUS_PUBLISH_PRIVACY` | `unlisted` | KEEP | — | The owner's own deliberate setting, verified in the deployed config by VYR-003. Recorded so no follow-up crew "tunes" it. |
| `INFERENCE_MODEL` | `llama-3.3-70b-versatile` | UNKNOWN | Settled by the same catalogue check as IntelX's `LLM_MODEL` (one measurement, two rows). | See IntelX. |
| Viral discovery thresholds | `viral_min_source_views` 250,000; source length 8–58 s | UNKNOWN | Measurement: VYR-004's lane source-finder yield at this view floor vs a lowered one, per lane. | The 58 s cap is consistent with the <60 s claimed-content rule (KEEP that bound). The 250k-view floor belongs to the retired re-upload design: VYR-005's autopsy found `trend_score=0.0` on all 46 autopilot videos — no selection signal was ever recorded — and the new lanes (space/history/tech, public-domain sources) may not carry view signals at all. |
| Worker queue: poll / heartbeat / max attempts | 2 s / 90 s / 3 | KEEP | — | The queue demonstrably drained in production (46 renders produced, VYR-005); no stall or duplicate-processing evidence in any wave. |
| Per-stage AI timeouts | Inference 60 s; vision 90 s; ElevenLabs 120 s; Inference-TTS 180 s; caption alignment 90 s | UNKNOWN | Measurement: per-stage duration logs from the VYR-004 pipeline's first proof videos — set each timeout at ~2× its stage p95 instead of today's round numbers. | Inventoried from `app/config.py` + .env; a serial worst case sums to ~9 minutes of pure waiting per video, unmeasured stage by stage. |

## Website (Caddy + FRIDAY UI, Server 1)

| Parameter | Current | Verdict | Decided value / measurement | Evidence |
|---|---|---|---|---|
| Proxy timeouts (Caddyfile) | No explicit timeouts — Caddy defaults; the effective ceiling is the app's 300 s | KEEP | — | The 300 s app-side ceiling (FRIDAY section) is the documented contract every website rebuild must preserve; no wave reports proxy-side truncation. |
| `fleet-health-watcher` driving site/fleet status | Service dead (see fleet section) | UNKNOWN | Covered by the fleet row's journal diagnosis. | TASK-OBS-003's scorecard was produced manually; the watcher that should automate it is not running. |

## Appendix — Stratex (OUT OF SCOPE for tuning; recorded 2026-11-15, owned by FWD-006/RISK-001)

Values as read from the live `.env` today, for the record only — several are already
superseded by the coordinator's decided package (per-trade 0.1% of *venue* equity, 2% heat
cap per strategy, 5% DD kill marking to market on scan cadence) and FWD-002's ground-truth
read (live risk is denominated on composite equity; no heat cap exists yet):
`SCAN_INTERVAL_SECONDS=15`, `STRATEX_RISK_PER_TRADE_PCT=0.01`, `STRATEX_MAX_POSITION_PCT=0.10`,
`STRATEX_MAX_POSITIONS=30` (per venue and total), `STRATEX_MAX_DAILY_LOSS_PCT=0.03`,
`STRATEX_MIN_CONFIDENCE=0.55`, `STRATEX_MIN_RR=1.5`, `STRATEX_MIN/MAX_STOP_PCT=0.001/0.15`,
`STRATEX_SYMBOL_COOLDOWN_SEC=900`, `STRATEX_MAX_ENTRIES_PER_CYCLE=3`,
`STRATEX_FEE_ROUNDTRIP=0.0008`, `BINANCE_LEVERAGE=3`, `TESTNET_ONLY=TRUE`.
One non-trading observation is referred to RISK-001 with this table: Stratex's `.env` also
carries `ENVIRONMENT=development` / `APP_ENV=development` in production — the same flag
incoherence as Memora's row, in the agent where fail-closed matters most.

## Summary

- **Rows:** 53 parameters inventoried across 12 sections (54 table rows; the website
  health-watcher row is a cross-reference to the fleet row).
- **KEEP: 20** — evidence supports the current value.
- **TUNE: 7** — Inference Groq prompt guard (>7,000 tokens), Inference NVIDIA rung (disable),
  Inference OpenRouter cache scope (300 s, module-level; implemented in TASK-INF-004's PR),
  Memora env flags (→ production), IntelX Inference timeout (45 s → 60 s),
  Cortex missing-score default (0.5 → reject), FRIDAY-Voice greeting recall (decouple;
  implementation after VOI-009 merges).
- **UNKNOWN: 26** — each with its settling measurement named, mapped to an existing crew
  wherever one exists (INF-006, MEM-002/006, FRD-005, COR-003, SEN-003, FUT-004/008,
  INT-003/004, FRG-005, PRO-001, REL-046 staging) so the measurements actually happen.
- **Nothing was guess-tuned, and no live setting was changed by this task.**

### Recommended follow-up batches (for the coordinator to dispatch after approving this table)

1. **Inference batch** — land TASK-INF-004's PR (cache scope), add the Groq prompt guard and
   the NVIDIA-rung disable in the same follow-up PR; verify against INF-004's journal method.
2. **Memora batch** — env-flag flip + MEM-005 auth-matrix re-run in one maintenance action.
3. **IntelX one-liner** — timeout 45 → 60 s with the next IntelX PR; catalogue check for
   `llama-3.3-70b-versatile` settles the IntelX + VyralX model rows together.
4. **Cortex batch** — 422-on-incomplete-matrix with COR-003's provenance work.
5. **Voice** — the recall decoupling, first voice-worker change after VOI-009 merges.
