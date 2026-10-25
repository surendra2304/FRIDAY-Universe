# Stratex Design System

## Visual Direction

**Stratex is a high-frequency trading operations desk.** The design language is:
- **Dark, precise, data-dense** — every pixel carries information.
- **Lime-on-charcoal signal identity** — the `#b4f46b` accent marks active state, profit, and primary actions.
- **Terminal-adjacent typography** — DM Mono for numbers, Manrope for readability.
- **Restrained motion** — animations support comprehension, never decorate.

### Brand Personality
- **Confident, not flashy.** Numbers speak; chrome stays quiet.
- **Operational, not marketing.** The dashboard is a workspace, not a landing page.
- **Precision-first.** Monospaced figures, tabular alignment, zero ambiguity.

## Design Tokens

### Colors
| Token | Value | Usage |
|-------|-------|-------|
| `--canvas` | `#090b0f` | Page background |
| `--surface` | `#101319` | Card/panel background |
| `--surface-raised` | `#151a22` | Elevated surfaces |
| `--surface-soft` | `#1a2029` | Hover/secondary surfaces |
| `--line` | `rgba(212,225,239,.085)` | Borders |
| `--line-strong` | `rgba(212,225,239,.15)` | Strong borders |
| `--ink` | `#edf2f6` | Primary text |
| `--ink-soft` | `#a5b0ba` | Secondary text |
| `--ink-dim` | `#717c87` | Muted text |
| `--lime` | `#b4f46b` | Primary accent (profit/active) |
| `--mint` | `#7ee0b5` | Success/online |
| `--red` | `#ff7c86` | Loss/error |
| `--amber` | `#f2c679` | Warning/stale |
| `--violet` | `#b7a7ff` | Paper/simulation |

### Typography
- **Display/Headings:** Manrope, weights 700-800, letter-spacing -0.055em
- **Body:** Manrope, weight 400-500, size 13px
- **Numbers/Data:** DM Mono, weights 400-500, tabular-nums
- **Labels/Eyebrows:** DM Mono, 9px, uppercase, letter-spacing 0.13em

### Spacing
- **Base unit:** 4px
- **Panel padding:** 18px 19px (desktop), 14px 12px (mobile)
- **Card gap:** 11-12px
- **Section gap:** 15-23px

### Layout Grid
- **Sidebar:** 238px (desktop), 210px (1280px), full-width sticky (900px)
- **Content max-width:** 1600px, centered
- **Metric grid:** 5 columns (desktop), 3 (1280px), 2 (640px)
- **Overview grid:** 1.65fr / 0.95fr (desktop), single column (900px)

### Motion Tokens
| Token | Duration | Easing | Usage |
|-------|----------|--------|-------|
| `--fast` | 0.18s | ease | Hover, micro-interactions |
| `--normal` | 0.28s | ease | Page transitions, panel reveals |
| `--slow` | 0.5s | cubic-bezier(.16,1,.3,1) | Scroll-triggered reveals |
| `--spring` | 0.4s | cubic-bezier(.34,1.56,.64,1) | Button press, modal |

## Component Standards

### Panels
- Border: `1px solid var(--line)`
- Background: `linear-gradient(145deg, rgba(20,24,31,.94), rgba(15,18,24,.97))`
- Radius: 11px
- Shadow: `0 10px 28px rgba(0,0,0,.1)`
- Padding: 18px 19px

### Metric Cards
- Border: `1px solid var(--line)`
- Background: `linear-gradient(145deg, rgba(22,27,35,.97), rgba(15,18,24,.98))`
- Radius: 10px
- Primary card: lime-tinted border and background

### Buttons
- **Primary:** Lime background `rgba(180,244,107,.08)`, lime border, lime text
- **Secondary:** Transparent, `--line` border, `--ink-soft` text
- **Hover:** Increase border opacity and background
- **Focus-visible:** `2px solid var(--lime)` outline, offset 3px

### Tables
- Header: `8px DM Mono`, uppercase, letter-spacing 0.07em, `--ink-dim`
- Body: `9px DM Mono`, `#c0c8ce`
- Row hover: `rgba(255,255,255,.018)`
- Border: `rgba(212,225,239,.055)` between rows

### Status Indicators
- **Online/Success:** `--mint` dot with glow
- **Warning/Stale:** `--amber` dot with glow
- **Error:** `--red` dot with glow
- **Loading:** CSS spinner with lime accent

## Accessibility

- **Reduced motion:** All animations reduce to 0.01ms via `@media (prefers-reduced-motion: reduce)`
- **Focus states:** Visible lime outline on all interactive elements
- **Semantic HTML:** `<nav>`, `<main>`, `<section>`, `<article>`, `<header>`, `<footer>`, `<table>`
- **ARIA:** `aria-label`, `aria-live`, `aria-hidden`, `role` attributes on dynamic content
- **Contrast:** All text meets WCAG AA (4.5:1) against backgrounds

## Responsive Breakpoints
| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Desktop | >1280px | Full sidebar, 5-col metrics |
| Tablet | 901-1280px | Narrower sidebar, 3-col metrics |
| Mobile | ≤900px | Sticky top nav, single column |
| Small mobile | ≤640px | Compact metrics, wrapped header |

## Image Guidelines
- **No stock photos** in operational dashboards
- **Icons:** Unicode glyphs or inline SVG, `--ink-dim` default
- **Charts:** SVG-based, lime accent line, gradient fill
- **Avatars/Logos:** Not used in data dashboards

## Anti-Patterns (Do NOT Use)
- Glassmorphism on data panels (reduces readability)
- Giant hero headlines in dashboards
- Excessive 3D in trading interfaces
- Bright gradient backgrounds behind tables
- Animation that delays data display
