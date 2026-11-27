# TASK-FRG-030 — CHECKPOINT 1 (scoping) — Muse 11 — 2026-11-25 ~14:05 IST

## Status
- **Task:** TASK-FRG-030 — Forge: Gradio instant-UI delivery layer for one-prompt internal tools (P2)
- **Board:** AVAILABLE / owner null on main `a0a9f1ba` (claim flip rides in the work PR, owner order 7143628341 rule 4). Hub claim filed 13:48 IST as comment 7157018365; branch `muse11/task-frg-030-gradio-ui` @ `a0a9f1ba`.
- **Done (board):** one real internal tool shipped with a working Gradio UI and used by another agent.

## 1. Forge one-prompt remit — baseline (verified first-hand on main a0a9f1ba)
- The one-prompt remit is REAL, not a stub. Two layers exist:
  - **Template scaffold** — `Forge/app/templates/ig_templates.py`: `ONE_PROMPT_AGENT`
    (`"one-prompt-agent"`, "One-prompt agent scaffold"): one plain-language prompt becomes a
    configured single-file agent (tool registry, system prompt from the owner's description,
    model calls routed through FRIDAY's Inference gateway). Manifest: `agent.py`, `tools.py`,
    `requirements.txt` (httpx only), `README.md` (prompt stored verbatim).
  - **Real flow** — `Forge/app/templates/agent_creation.py` (28,697 B, TASK-IG2-FRG-07):
    `create_agent(prompt, output_root)` — prompt in -> agent project on disk -> real checks run
    -> registered in `created_agents.json`. Deterministic file rendering (same prompt ->
    byte-identical files). Supervisor correction C-1 on the Forge baseline (A12) is what made
    this real; before it the item was a template scaffold only.
- **Delivery today is CLI / API only.** Forge's surface is `Forge/app/cli.py`,
  `Forge/app/main.py` (FastAPI, mesh `http://forge:8000`, gateway `/forge/*`), the 10-check
  verification battery, and sandboxed workspaces. `Forge/app/delivery/` holds one file
  (`docs_generator.py`) — no UI delivery layer of any kind.
- Forge README positions Forge as the autonomous code-synthesis + sandbox + self-repair
  engine (FastAPI service + CLI). Nothing in it promises an interactive UI.

## 2. The Gradio gap (verified first-hand)
- **No Gradio anywhere in Forge code.** Code search `gradio` across the repo: 7 hits, zero in
  `Forge/` — the hits are VyralX/docs, `VyralX/app/services/agenttube.py` (where `gradio` is
  in `BANNED_IMPORTS`, i.e. explicitly forbidden), `IntelX/.../scouted_repos.json`, and
  collaboration docs. Gradio exists in this monorepo only as a named idea, never as a runtime.
- **No Streamlit in Forge either** (4 repo hits, none in `Forge/`). Board acceptance is
  accurate: "neither Gradio nor Streamlit exists in Forge code (Streamlit is named only as an
  absent layer)."
- **No Gradio in any requirements file:** `Forge/requirements.txt` (15 pins: fastapi, uvicorn,
  pydantic, sqlalchemy, httpx, redis, openai, anthropic, …) carries no UI framework.
- Consequence: the delivery layer is a from-zero addition — new dependency (`gradio`, free,
  PyPI), new module, new tests. No existing UI code to extend or migrate.

## 3. Candidate internal tool (chosen)
**Board task lookup** — a one-prompt-built internal tool that answers the question every
worker asks all day: "what is the state of task X / what is free in lane Y?"
- Inputs: task id (textbox), status filter (dropdown), owner filter (dropdown), max rows
  (slider) — the sliders/inputs/live-outputs shape the acceptance names.
- Output: matching board records (id, title, status, owner, branch, pr) read live from
  `docs/collaboration/WORK_BOARD.yaml` on main, plus the queue depth for the requester.
- Why this tool: (a) real — workers read the board every run; (b) small — one read-only
  lookup over a file the team already owns, no new service, no secrets; (c) provably used —
  another agent can run a lookup and the lookup itself is the evidence; (d) it exercises the
  layer exactly as specified (instant interactive UI where a full app is overkill).
- Alternatives considered and set aside: Memora cursor-health viewer (too narrow, one
  consumer); hub-watch digest (duplicates what the coordinator already posts); a Gradio
  front-end on the one-prompt flow itself (kept as the layer's demo surface, not the
  proof tool — the proof tool must be a tool, not a demo of the layer).

## 4. Build plan (checkpoint 2)
1. **Layer** — `Forge/app/delivery/gradio_layer.py`: thin wrapper that turns a
   one-prompt-built tool (function + declared inputs/outputs) into a `gr.Interface` and
   launches it; `gradio` added to `Forge/requirements.txt` (free, PyPI, no paid tier).
   The layer also fronts the one-prompt flow itself (`create_agent` via prompt textbox +
   template dropdown) as its demo surface.
2. **Tool** — the board task lookup, built through the one-prompt flow (template
   `one-prompt-agent`), given its Gradio UI through the layer.
3. **Proof** — run the UI live (local launch + screenshot/log), and get one other agent to
   run a real lookup against it; record who used it, when, and what it returned. That use
   is the Done evidence.
4. **Rule (recorded, rides in the work PR):** Gradio when the tool is single-purpose,
   internal-only, no auth / multi-user state / persistent DB, and the UI is under a day of
   work; a full app when it is multi-user, public-facing, needs auth or persistent state,
   or needs a custom frontend. Free-only: no paid Gradio tier, no hosted share link that
   costs anything.
5. **Board flip** — FRG-030 CLAIMED -> MERGED (or IN_PROGRESS per the work PR) rides in the
   single work PR with this doc, per owner order 7143628341 rule 1 (one work PR when DONE
   or genuinely BLOCKED; no checkpoint PRs).

## 5. Blockers / holds
- None on the repo-side legs. Live legs (a shared/public Gradio launch, if the using agent
  needs one) are subject to the owner stop order on server moves — the proof run is local
  first; any hosted leg needs coordinator/owner clearance, requested in the completion post
  if it becomes necessary.
- No live state re-probed this run (repo-side scoping only); last verified live state
  13:13 IST self-check: FRIDAY /health 200 healthy, both Oracle servers ONLINE, Memora 401
  fix holds (PID 3747325).

## 6. Queue
- FRG-030 (head) -> FRG-021 (owner muse_11 on board, watch085 flip). Depth 2.

— Muse 11
