# QA Loop State — shared by the two hourly scheduled runs

> This file is the handoff memory between runs. SWEEP (hourly :00) repairs the fleet.
> CHAOS (hourly :30) tests like a hostile human and ships one upgrade.
> A run that ends without updating this file is a FAILED run.

## LAST_RUN
- 2026-11-13 17:30 IST CHAOS run (surface 1: chat-brain), commit 20dbfc1
- battery 11/11 green; regression suites: api-command/origin/fleet 64, persona/router 65

## IN_PROGRESS (must be finished or cleanly reverted FIRST, before any new work)
- TASK-STRATEX-OANDA-001 — OANDA demo trading live (cron job 528111 runs the validated
  portfolio_v2 D1 engine hourly). Open question: 2026-11-13 16:57 IST all 6 trades closed
  via TRADE_CLOSE market orders not originating from this loop — identify key holder
  (likely manual close in OANDA web UI) before treating it as a defect.
- TASK-WF-015 — United owner-workflow acceptance and real shared-memory/research lifecycle.

## FINDINGS_QUEUE (severity | repro | discovered by | status)
- MEDIUM | 2026-11-13 16:57 IST: trades 57-77 flattened externally 2 min after open,
  -42.47 USD realized; not SL/TP, not this loop. Confirm = owner manual close. | SWEEP | OPEN
- CRITICAL | datetime in command-result metadata crashed raw json.dumps on every
  502/refusal branch -> empty 500. FIXED commit 20dbfc1 (_json_safe), pinned in
  test_json_safe_converts_datetimes_not_evidence | CHAOS | DONE
- HIGH | "Open a live OANDA position ..." swallowed by launcher fast path (2 sites),
  answered "no application called '...'". FIXED commit 20dbfc1 (trading-intent guard),
  pinned | CHAOS | DONE
- HIGH | /api/chat shipped honest failure replies as 502; dashboard discarded the words
  and faked "I lost the link". FIXED commit 20dbfc1 (rewrap readable reply as 200;
  403/500 untouched) | CHAOS | DONE
- (sweep runs append here; fixed items move to DONE with commit hash)

## UPGRADE_BACKLOG (CHAOS run implements exactly ONE per run, smallest-first)
1. TASK-WF-009 — Isolate generated-project tests, preserve Python code fences (BLOCKED board item).
2. TASK-WF-008 — Preserve released goal-specific code during repair + embedded unittest exec.
3. TASK-WF-007 — Goal-specific real model code + valid generated tests through Forge/Inference.
4. Owner standing asks: site performance polish (minimal dynamic design), chat reply brevity,
   agent autonomy depth (screen-read / app-open), voice robustness.
   (chat-surface honesty slice of item 4 shipped in commit 20dbfc1; the rest remains)

## CHAOS_ROTATION (one surface per CHAOS run, cycle top to bottom)
1. chat-brain (rapid-fire, long/unicode/malformed input, secret-siphon prompts, live-money refusal)
2. voice (call start, mid-call interrupt, drop-reconnect, timeout)
3. fleet-dispatch (real task through FRIDAY to a specialist; kill+restart one service; breaker check)
4. website (load timing, mobile viewport, asset 404s, JS console errors)
5. stratex-oanda (quotes fresh, bad-order rejection, SL/TP on every open trade, breaker states)
6. security (unauthenticated /bridge and /api probes must be fail-closed per D-023; no secrets in responses)
(next surface = 2)

## DONE
- 2026-11-13 17:30 IST CHAOS run 1 (chat-brain): commit 20dbfc1 — chat chaos battery
  (11 tests) + JSON-safe failure branches + trading-intent launcher guard + /api/chat
  honest-reply contract. Zero regressions (129 related tests green).

## OPS NOTES (environment facts the next run must know)
- 2026-11-14 ~11:45 IST: agent-scheduler cron triggers are quota-stalled ("cron_trigger quota exceeded for plan free") — no SWEEP/CHAOS runs have fired since 2026-11-13 17:30 IST. Rotation resumes at surface 2 (voice) when triggers return. Owner informed; options: thinner schedule vs plan upgrade.
- 2026-11-14 ~12:10 IST: DuckDNS token secured (owner-supplied) — GitHub secret DUCKDNS_TOKEN set, vault copies updated, dns_guard section-parse bug fixed+pinned (suite 11/11). BUT friday-universe is currently OUT of the DuckDNS zone (wildcard catch-all served for it, identical to nonexistent names; update API returns OK but does not republish the zone entry). Owner dashboard action pending. dns-fix.yml (30-min) + dns_guard are armed and will hold the record at 140.245.208.100 the moment the zone entry exists; dns-fix Server-1 job now pins the ingress IP (egress ipify report-only). Website surface testing while the domain is on the catch-all will fail from the public internet — verify via direct IP or after the owner restores the zone entry.
