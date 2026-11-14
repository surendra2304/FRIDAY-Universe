# QA Loop State — shared by the scheduled runs (consolidated 2026-11-14)

> This file is the handoff memory between runs. Scheduled tasks reset per owner
> ask (2026-11-14 ~17:45 IST): daily QA Loop cron 530005 DELETED; the single
> scheduled task is now cron 530116 'FRIDAY DNS Guard — 30-min self-heal'
> (fixed_rate 1800 s; runs scripts/dns_guard.py --auto-fix-domain
> friday-universe; lean payload, 1-line replies). SWEEP+CHAOS is unarmed until
> the owner re-arms it. A run that ends without updating this file is a FAILED
> run.

## LAST_RUN
- 2026-11-14 ~17:15 IST manual SWEEP-style session (ZAI Agent 1): dns_guard
  typo-domain false-alarm root-caused + fixed (commit 4a55148, suite 13/13);
  OANDA demo calm (99,833.00 USD, 0 open trades); no chaos surface consumed
  (rotation stays at 2 = voice). Cron consolidated: job 528192 deleted
  (quota-stalled), job 530005 armed (daily 09:00 IST).
- 2026-11-13 17:30 IST CHAOS run (surface 1: chat-brain), commit 20dbfc1
- battery 11/11 green; regression suites: api-command/origin/fleet 64, persona/router 65

## IN_PROGRESS (must be finished or cleanly reverted FIRST, before any new work)
- TASK-STRATEX-OANDA-001 — OANDA demo trading live (cron job 528111 runs the validated
  portfolio_v2 D1 engine hourly). Open question: 2026-11-13 16:57 IST all 6 trades closed
  via TRADE_CLOSE market orders not originating from this loop — identify key holder
  (likely manual close in OANDA web UI) before treating it as a defect.
- TASK-WF-015 — United owner-workflow acceptance and real shared-memory/research lifecycle.

## FINDINGS_QUEUE (severity | repro | discovered by | status)
- CRITICAL | dns_guard --name default + both dns-fix.yml job FQDNs were
  misspelled 'friday-universe.duckns.org' (missing 'd'); the typo-domain serves
  a wildcard catch-all with the same Linode trio, so every default run
  monitored the WRONG domain: false drift alerts to the owner + the workflow's
  verify/TLS steps never checked the real record. Real record proven healthy
  (all 8 authoritative NS + Google/Cloudflare DoH -> 140.245.208.100).
  FIXED commit 4a55148 (DEFAULT_NAME/DEFAULT_EXPECTED constants, typo fixes,
  2 regression pins, suite 13/13) | SWEEP | DONE
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
- 2026-11-14 ~17:45 IST (ZAI Agent 1): owner reset all scheduled tasks: cron 530005
  (daily SWEEP+CHAOS) deleted; ONE job armed instead — 530116 'FRIDAY DNS Guard —
  30-min self-heal' (fixed_rate 1800 s). Guard command validated live before
  arming (OK -> 140.245.208.100, exit 0). QUOTA CAUTION: gateway warns 'estimated
  48 daily executions exceeds limit 3, excess triggers will be ignored' — on the
  current plan only ~3 runs/day actually fire (same failure mode as old 528192);
  full 30-min cadence needs a plan upgrade (owner-side). OANDA portfolio cron
  remains NOT re-armed (unchanged, needs explicit owner approval).
- 2026-11-14 ~17:15 IST (ZAI Agent 1): (a) The afternoon "DNS re-drift" was a
  FALSE ALARM — watchdog typo-domain bug (see FINDINGS_QUEUE); the real record
  is healthy on all 8 authoritative nameservers and Google/Cloudflare DoH
  (TTL 60s). The 12:10 IST "zone left the zone" narrative was very likely the
  same artifact (dns_guard default mode could only ever report drift); the
  Nov-13 outage itself was real (owner impact). Owner received a Telegram
  correction. Website-surface runs: still recheck public DNS first, but with
  the fixed guard the readings are now trustworthy. (b) Scheduled tasks reset
  per owner ask: quota-stalled 30-min cron 528192 ("cron_trigger quota exceeded
  for plan free" since 2026-11-13 17:30 IST) deleted; consolidated job 530005
  runs daily 09:00 IST — SWEEP+CHAOS in one run, ~30 triggers/month to live
  within the free-plan quota. If the plan is upgraded, split back into
  SWEEP/CHAOS at higher cadence. (c) OANDA portfolio engine cron 528111 NOT
  re-armed: open pricing defect (TASK-STRATEX-PORTFOLIO-002: batch fallback
  returns one stale price for the basket, tp=0.00000) + open external-close
  question (TASK-STRATEX-OANDA-001); needs explicit owner approval. (d) Repo
  left on clean main (was checked out on zai/TASK-STRATEX-PORTFOLIO-002 with
  local main 1 behind); collaborators shipped PRs #100-#136 during the stall —
  always fetch+rebase before committing. Known untracked sandbox skeletons at
  repo root (__init__.py, agents/) are ignored leftovers, not work in flight.
- 2026-11-14 ~11:45 IST: agent-scheduler cron triggers are quota-stalled ("cron_trigger quota exceeded for plan free") — no SWEEP/CHAOS runs have fired since 2026-11-13 17:30 IST. Rotation resumes at surface 2 (voice) when triggers return. Owner informed; options: thinner schedule vs plan upgrade. [Superseded 17:15 IST: resolved via job consolidation, see above.]
- 2026-11-14 ~12:10 IST: DuckDNS token secured (owner-supplied) — GitHub secret DUCKDNS_TOKEN set, vault copies updated, dns_guard section-parse bug fixed+pinned (suite 11/11). BUT friday-universe is currently OUT of the DuckDNS zone (wildcard catch-all served for it, identical to nonexistent names; update API returns OK but does not republish the zone entry). RECOVERED ~07:05 UTC / 12:35 IST: public DNS again serves a single A record 140.245.208.100 (zone entry back — owner dashboard action and/or the token-carrying dns-fix run republished it; exact trigger unconfirmed). dns-fix.yml (30-min) + dns_guard are armed to hold it there; dns-fix Server-1 job now pins the ingress IP (egress ipify report-only). If the catch-all returns: owner re-adds friday-universe in the duckdns.org dashboard (1 min) and the loop holds it from there. Website-surface testing: recheck public DNS first — one zone flap was observed today.
