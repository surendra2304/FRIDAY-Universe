# Forge dev-environment reference

Owner-side editor setup patterns recorded for Forge work. These are
references for owner-directed sessions on the owner's own machine.
Nothing here is a fleet dependency: Forge runs server-side, and no
automated Forge path may require any of this.

## G-04: Claude Code in VS Code (agent-in-the-IDE setup)

Source: forge package G-04 (item DbGOC4QT6KP — the Claude Code in
VS Code setup recipe), with the builder-environment extension set from
G-02 (item DXMg0D9jD3Y — VS Code extensions: Live Server, Quokka.js
inline evaluation, Copilot). The pattern is also recorded in
`Forge/docs/IG_EVALUATION_NOTES.md` section 5 ("Agent-in-the-IDE
setup pattern", source DdjTV_zCTUH): configuration, not code — a
coding agent inside the editor, configured with an API key.

### Free-only caveat (verbatim from the TASK-FRG-031 board record)

> Free-only note: the recipe spends the owner's own paid API key when
> used, so it stays a reference for owner-directed sessions, never an
> automated fleet dependency.

### The recipe, as sourced

1. Editor: VS Code on the owner's machine.
2. Agent: Claude Code inside VS Code, configured with the owner's
   own API key (the DdjTV_zCTUH pattern: coding agent inside the
   editor via API-key config).
3. Builder-loop extensions from the same source cluster
   (DXMg0D9jD3Y):
   - **Live Server** — serves the working folder over HTTP with
     reload, the editor-side equivalent of Forge's server-side live
     preview (`GET /api/tasks/{task_id}/preview`, TASK-FRG-031).
   - **Quokka.js** — inline evaluation: expression results beside
     the code. Editor-side only; Forge's server-side loop is batch
     (generate -> battery -> repair) and deliberately has no inline
     eval (IG_EVALUATION_NOTES.md section 5, gap 2 — recorded as a
     decision, not an oversight).
   - **Copilot** — editor completion alongside the agent.

### What this is not

- Not a Forge feature. Forge does not embed an editor or an
  agent-in-the-IDE; the fleet's coordination surface is the board,
  the hub, and the dashboard.
- Not free-tier infrastructure. Every use spends the owner's paid
  API key (caveat above). The fleet's free-only rule is untouched:
  no Forge code path reads, requires, or falls back to this setup.
- Not a credential route. API keys for owner-directed sessions stay
  on the owner's machine; they are never committed to this repo,
  pasted into chat, or stored in fleet env files.

— Recorded under TASK-FRG-031 (Muse TP10, 2026-11-26).
