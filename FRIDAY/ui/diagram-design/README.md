# diagram-design — FRIDAY adoption (TASK-IG2-WEB-01)

**Source:** https://github.com/cathrynlavery/diagram-design by Cathryn Lavery
**License:** MIT — verbatim license in [`LICENSE`](LICENSE) in this folder.
**Spec card:** `~/workspace/ig-references/repos/diagram-design.md` (fit: **adopt**)
**Where it lives:** `FRIDAY/ui/diagram-design/` — website/docs tooling for
Website-UI and Forge (consumer). It is a loadable skill file-set: zero runtime
cost, nothing to host, no build step, no dependency added to the website.

## What was adopted

| File | What it is |
|---|---|
| `SKILL.md` | The skill itself: philosophy, semantic-pattern + visual-type selection (50 types), universal anti-patterns, the six mandatory connector rules, 4px-grid layout, complexity budget (≤9 nodes, ≤12 arrows, ≤2 accents), the pre-output taste gate, variants and import rules — with the style guide **pre-customized to FRIDAY's Halo tokens** (upstream §0 gate satisfied for FRIDAY work). |
| `LICENSE` | Upstream MIT license, verbatim. |
| `examples/friday-fleet-architecture.html` | A worked example produced *with* the skill: the 10-agent fleet as a minimal-dark Architecture diagram — one self-contained HTML file, inline SVG, no JavaScript. Use it as the starting template for new diagrams. |

## What was deliberately NOT vendored

The upstream per-type reference library (`references/`, ~60 files) and the
example gallery (`assets/`, ~150 HTML files). Vendoring them would add
megabytes of rarely-loaded reference material to this repo; the adopted
`SKILL.md` links to the upstream repo, and an agent loads the one type
reference it needs from there when drawing. If a future diagram series needs
a type reference repeatedly, vendor just that file into `references/` here
with its upstream path noted.

## How to use

1. Load `SKILL.md` when a task needs a published diagram (architecture,
   explainer, docs hero) for the website or docs.
2. Pick the semantic pattern, then the visual type; state the plan before drawing.
3. Draw on the 4px grid with hairline borders and no shadows; accent on at
   most 2 elements; run the §9 taste gate before shipping.
4. For diagrams that live in Git and change every sprint, keep using Mermaid —
   it diffs better (upstream's own caveat). Diagram Design is for published
   diagrams.
