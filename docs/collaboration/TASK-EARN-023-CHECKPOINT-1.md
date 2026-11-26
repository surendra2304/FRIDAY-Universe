# TASK-EARN-023 — CHECKPOINT 1 (scoping)

- Worker: Muse TP6 — 2026-11-26 ~08:2x IST
- Branch: `musetp6/task-earn-023-swiggy-builders-club` @ main `5b703635`
- Hub claim: 7181154926
- Task: EARN — Swiggy Builders Club option (corpus reel DYg_b2ZTK70, @lavin_creator)

## Board verified first-hand (main `5b703635`, raw board fetch)

- TASK-EARN-023 AVAILABLE / muse_tp6 / P3 / branch null / pr null.
- Acceptance: deliverable is a one-page prototype concept (e.g. a FRIDAY voice
  food-ordering / auto-restock agent on the Swiggy MCP) plus the full
  application answers, drafted under `earning/`.
- OWNER ONE-TIME: submit the application form himself (his details, his call).
  First-money path is indirect and unproven — this task buys an option on the
  programme, it does not promise income. If Swiggy declines or never replies,
  close the task with that verdict recorded.

## Programme verified first-hand (live public page, 2026-11-26 ~08:19 IST)

- `https://mcp.swiggy.com/builders` loads publicly: Swiggy Builders Club, MCP
  platform for developers/startups/enterprises. 4 MCP servers (Food,
  Instamart, Dineout, Scenes), 62 API tools. Contact: builders@swiggy.in.
- Path to prod, per the live page: (1) start building on localhost, NO
  APPROVAL, prototype against real tool schemas, free; (2) apply for prod
  access — tell Swiggy who you are, what you built, share a demo; (3) quick
  review of use case + security setup; (4) go live — OAuth redirect details
  allowlisted; (5) send a demo (standout projects get featured; Swiggy hires
  from the programme).
- Note: the April 2026 launch announcement cited 3 MCP servers / 18+ API
  tools at launch; the live page today says 4 servers / 62 tools — the
  programme has grown since. Live-page figures used.
- Root `https://mcp.swiggy.com` returns auth-required JSON
  (`{"error": "invalid_token", "error_description": "Authentication required"}`)
  to unauthenticated visitors (live browser read 2026-11-26 ~08:18 IST) — the
  MCP endpoint itself is gated; the public programme + application route is
  `/builders`. No sign-in attempted, no form filled.

## Repo state

- `earning/` on main: no EARN-023 file yet. Existing pattern is one doc per
  task under `earning/` (EARN-002 … EARN-031 packs).
- Corpus reel DYg_b2ZTK70: cited by coordinator evidence (re-audit sweep);
  not re-verified first-hand this run — the programme itself is verified live
  above, which is what the deliverable depends on.

## Guardrails

- Free only; no credentials in repo or chat; no application submitted by TP6
  (owner one-time); no income promised.

## Next

- Checkpoint 2: draft the one-page prototype concept + the full application
  answers under `earning/`.
