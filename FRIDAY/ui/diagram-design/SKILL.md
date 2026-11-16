---
name: diagram-design
description: Create branded architecture, flowchart, sequence, state machine, ER/data model, timeline, quadrant, pyramid/funnel, Sankey, deployment, dependency-graph and 40+ other diagram types as self-contained HTML files with inline SVG — editorial quality, no build step, no JavaScript, no external images.
license: MIT
metadata:
  version: "2.6"
  adopted-from: "cathrynlavery/diagram-design (MIT) — see README.md in this folder"
  friday-profile: "halo (pre-customized style guide — the §0 gate is satisfied for FRIDAY work)"
---

# Diagram Design — FRIDAY adoption (TASK-IG2-WEB-01)

Create diagrams as self-contained HTML files with inline SVG and an editorial
design system. Fifty visual types upstream; semantic patterns describe
behavior, type references describe layout.

> **Adoption note.** This is the FRIDAY adoption of Cathryn Lavery's
> `diagram-design` skill (MIT, `LICENSE` in this folder). The core skill —
> philosophy, selection guide, anti-patterns, connector rules, complexity
> budget, taste gate — is adopted here with the style guide pre-customized to
> FRIDAY's Halo tokens (§5), which satisfies the upstream first-run style-guide
> gate for FRIDAY work. The upstream per-type reference library
> (`references/type-*.md`, ~60 files) and the example gallery (`assets/`) are
> NOT vendored; load them from the upstream repo when a diagram needs a type
> reference: https://github.com/cathrynlavery/diagram-design

---

## 0. First-time setup — style guide gate (FRIDAY: pre-satisfied)

Upstream, before a first diagram in a new project you must verify the style
guide has been customized and ask the user if it is still the shipped default
(paper `#f5f5f5`, ink `#2d3142`, accent `#bf4520`). **For FRIDAY Universe this
gate is already satisfied**: §5 below carries the FRIDAY Halo profile. Only
ask when producing a diagram for a *different* brand than FRIDAY.

## 1. Philosophy

**The highest-quality move is usually deletion.**

- Every node represents a distinct idea. Two nodes that always travel together are one node.
- Every connection carries information. If the relationship is obvious from layout, remove the line.
- The accent is **editorial, not a flag.** 1–2 focal nodes per diagram. Using it on 5 nodes erases the signal.
- The schematic isn't done when everything is added. It's done when nothing can be removed.

**Target density: 4/10.** Enough to be technically complete. Not so dense it
needs a guide. Above 9 nodes, it's probably two diagrams.

## 2. When to use

Use for any of the visual types in §3 when a reader will learn more from a
visual than from prose, a table, or a bulleted list.

**Don't use for:** quick unicode diagrams; lists of things (table or bullets);
attribute-only before/after (table — topology changes get an Architecture
delta); one-shape "diagrams" (just write the sentence).

Before drawing, ask: *Would the reader learn more from this than from a
well-written paragraph?* If no, don't draw.

## 3. Selection: semantic pattern, then visual type

When behavior, state, enforcement, or risk carries the meaning, first choose
one semantic pattern, then choose the nearest visual type for layout.

| Behavioral trigger | Semantic pattern → nearest type |
|---|---|
| Fan-in, queue depth, finite capacity, bottleneck | **Fan-in queue / bottleneck** → Data flow |
| Repeated Question / Input / Governance / Output slots across stages | **Stage framework with semantic slots** → Process |
| Conversation or loose input becomes a structured durable artifact | **Unstructured input → structured artifact** → Data flow |
| Two rule traces need pass/fail/skipped/not-reached and first divergence | **Paired policy-evaluation traces** → Flowchart |
| Trust boundaries plus permitted/forbidden ingress or deploy paths | **Secure paved road** → Architecture |
| Controls grouped by where they are enforced | **Governance / control catalog** → Layer stack |
| Defenses compensate for prior gaps and residual risk propagates | **Compensating security layers** → Layer stack |
| Hierarchical, ID-addressable decomposition needing per-block I/O | **Traceable block decomposition** → Tree |
| One subject progresses through phases, waits, retries, cancellation | **Lifecycle phase map** → State Machine |

### Visual-type guide (50 upstream)

Architecture · Architecture delta · IT current-state · Flowchart · Sequence ·
State machine · ER / data model · Steps · Timeline · Swimlane · Quadrant ·
Radar / Spider · Polar chart · Loop / flywheel · Nested · Tree · Org chart ·
Layer stack · Exploded axonometric · Axonometric plan · Venn · Pyramid /
funnel · Bar · Waterfall · Treemap / marimekko · Heatmap · Line (slopegraph,
ridgeline, streamgraph, bump) · Gantt · Scatter (bubble, beeswarm, box plot) ·
High-level · Process · Medallion · Data flow · DP integration · DP security
matrix · Sankey · Fishbone · Wardley map · Kanban · User journey · Service
blueprint · Deployment · Dependency graph (arc diagram) · UML class · Story
map · Database schema · SBGN · Requirement traceability · Event modeling ·
Unit grid.

Rules of thumb:

- If a 3-column table communicates the same thing, pick the table.
- If two types seem useful, pick the dominant axis; a semantic pattern may add behavior-specific primitives, not a second layout grammar.
- If you're past the complexity budget (§7), split into an overview + detail.

**Always load the chosen type reference from the upstream repo before
drawing.** Before rendering, state the plan in one short message: the chosen
visual type (and semantic pattern, if routed), the size preset, and anything
the complexity budget will force out.

## 4. Universal anti-patterns

These mark "AI slop" schematics of any type:

| Anti-pattern | Why it fails |
|---|---|
| Dark mode + cyan/purple glow | Looks "technical" without design decisions |
| JetBrains Mono as blanket "dev" font | Mono is for *technical* content — ports, commands, URLs |
| Identical boxes for every node | Erases hierarchy |
| Legend floating inside the diagram area | Collides with nodes |
| Arrow labels with no masking rect | Bleeds through the line |
| Vertical `writing-mode` text on arrows | Unreadable |
| 3 equal-width summary cards as default | Generic grid — vary widths |
| Shadow on any element | Shadows are out. Borders are in. |
| `rounded-2xl` on boxes | Max radius 6–10px or none |
| Accent on every "important" node | Accent is 1–2 editorial accents, not a signaling system |
| Reproducing Mermaid's renderer layout | Imports automatic spacing instead of an editorial layout |
| Any breach of the six §6 connector rules | Automatic fail |

## 5. Design system — FRIDAY Halo profile (the customized style guide)

Semantic roles; resolve every role against this table before emitting.

| Role | FRIDAY Halo value | Purpose |
|---|---|---|
| `paper` | `#030409` (site `--void`) | Page bg (minimal-dark variant, FRIDAY default) |
| `paper-2` | `#0a0e1d` | Container bg |
| `ink` | `#eef1ff` (site `--ink`) | Primary text / stroke |
| `muted` | `#8b93b8` (site `--dim`) | Secondary text, default arrows, sublabels |
| `soft` | `#5b6284` (site `--faint`) | Tertiary text |
| `rule` | `rgba(148,163,255,.18)` | Hairline borders (1px) |
| `rule-solid` | `rgba(148,163,255,.35)` | Strong borders |
| `accent` | `#8f9bff` (Halo indigo light) | 1–2 focal elements per diagram ONLY |
| `accent-tint` | `rgba(99,102,241,.16)` | Focal fill wash |
| `link` | `#7dd3fc` | HTTP/API calls, external arrows |

For light/print output (minimal-light variant), invert on the same hue family:
paper `#f6f7fc`, paper-2 `#ffffff`, ink `#23264a`, muted `#5b6284`,
rule `rgba(35,38,74,.16)`, accent `#4f46e5`, link `#0369a1`.

**Focal rule:** `accent` goes on 1–2 elements max. Everything else is `ink` /
`muted` / `soft`.

**Typography (FRIDAY mapping of the upstream system):** the upstream skill
uses Instrument Serif titles + Geist; FRIDAY's site type system substitutes
its own families — Space Grotesk 600 for node names and the diagram title,
Manrope for prose/callouts, JetBrains Mono **only** for technical sublabels,
eyebrows and arrow labels (ports, commands, URLs — the upstream "never
JetBrains Mono" rule targets its blanket use as a dev aesthetic; FRIDAY's
design system already restricts it to machine readouts, which is the same
intent).

## 6. Core SVG primitives + mandatory connector rules

- **Arrows:** `muted` by default, `accent` for the headline path, `link` for HTTP/API and external calls, dashed `5,4` for optional, passive, return, or async. Draw arrows before boxes so lines sit behind nodes.
- **Node box:** an opaque paper mask rect, then the styled box at `rx=6`, a rectangular type tag at `rx=2` (not a pill), the name in Space Grotesk 600, and a mono sublabel.

### Mandatory connector rules (non-negotiable; §9 checks each one)

1. **Orthogonal only.** Connectors between off-axis nodes are rounded right-angle elbows at `r=8` (`r=6` minimum in tight layouts); a straight `<line>` only when both ends share x or y. Diagonals fail.
2. **Label gap.** Every arrow label (14 characters max, all caps, centered on its segment) sits on an opaque mask with a visible 6 to 10px gap from its stroke, beside vertical segments, never on the line.
3. **No overlaps.** No shared or stacked strokes: offset parallel routes by 12px or more, and use the bridge/hop at a single crossing.
4. **Fan attach points.** Connectors on one box edge each get their own point at `L * k / (N + 1)`, 12px or more apart (8px on very small boxes).
5. **No transit behind a non-endpoint box.** Reroute. Only when the box is geometrically unavoidable: dashed stroke (`4,3`), label at the visible end, no marker on the intervening box.
6. **Mask before node.** A label mask must not overlap a node drawn after it; badge masks fully inside a node and masks over earlier zones are fine.

## 7. Layout & spacing

Structural geometry sits on a **4px grid**: node origins, widths, heights,
gaps, and padding divide by 4. Type sizes follow the role ramp, not the grid.

### Complexity budget (per diagram)

| Limit | Rule |
|---|---|
| Max nodes | 9 |
| Max arrows / transitions | 12 |
| Max accent elements | 2 |
| Max annotation callouts | 2 |

If you exceed, split into two diagrams (overview + detail).

## 8. Summary card pattern

Don't use 3 identical generic cards. Vary the treatment: column widths such as
`1.1fr 1fr 0.9fr`, a paper-2 background with a 1px hairline border and 6px
radius, no `box-shadow`.

## 9. Pre-output checklist (taste gate)

Run before producing any diagram.

**Type fit:** right visual type (§3)? Semantic pattern chosen first if
behavior matters? Stated type/pattern/preset/cuts before drawing? Would a
table or paragraph do the same job (if yes — don't draw)?

**Remove test:** can I remove any node / merge any two nodes / remove any
arrow / remove any label (color or shape already signals it)?

**Signal:** accent on ≤2 elements? Legend covers every type used — and nothing
extra? Within the §7 complexity budget?

**Technical:** `<svg>` has `role="img"` and `aria-labelledby` resolving to its
`<title>` and `<desc>` (IDs prefixed per diagram, `<title>` first child)?
Arrows drawn before boxes? §6 rules 1–6 all hold? Every arrow label has an
opaque `fill="{paper}"` rect behind it? Legend is a horizontal bottom strip,
not floating? No vertical `writing-mode` text? `viewBox` expanded ~60px for
the legend strip? `min-width` equals the viewBox width and the SVG sits in a
local `overflow-x: auto` wrapper? Node geometry on the 4px grid?

**Typography:** names in Space Grotesk, technical sublabels in mono only,
no mono as a blanket font?

## 10. Templates & variants

Every diagram ships as one self-contained HTML file in up to three variants:

| Variant | When to use |
|---|---|
| **Minimal light** | Screenshot-ready, print, docs on light backgrounds |
| **Minimal dark** (FRIDAY default) | The FRIDAY website, slides, dark posts |
| **Full editorial** | Long-form posts where the diagram is the hero |

To create a new diagram: start from `examples/friday-fleet-architecture.html`
in this folder (a worked minimal-dark Architecture diagram), replace the
eyebrow, title and SVG body, load the upstream type reference for any other
type, then run the §9 taste gate. Output is a single HTML file: inline SVG,
no JavaScript, no external images; export to SVG/PNG by screenshotting or by
extracting the `<svg>` element.

## 11. Importing an existing diagram

Mermaid / draw.io / Excalidraw / PlantUML sources are **redrawn** editorially
— never reproduce the source renderer's automatic layout. Keep a fidelity
ledger (nodes/edges/labels dropped or merged, and why) and report it beside
the deliverable. Note the upstream caveat: for diagrams that live in Git and
change every sprint, Mermaid still diffs better — use Diagram Design for
published diagrams.
