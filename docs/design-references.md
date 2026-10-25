# Design References

## Studied Sources

### 1. Stratex Operations Desk (Internal)
- **URL:** `Stratex/static/index.html`
- **What was learned:** Dark theme, monospace data, lime accent system works well for trading dashboards. The 5-column metric grid and panel-based layout are effective for dense data.
- **Pattern adapted:** Metric card grid, panel layout, sidebar navigation
- **Implemented in:** `Stratex/static/style.css` (already present), `Forge/app/dashboard/routes.py` (upgrade)

### 2. Forge Engineering Console (Internal)
- **URL:** `Forge/app/dashboard/routes.py`
- **What was learned:** Read-only dashboards need clear health indicators, task lists with state badges, and tab-based detail views. The paper-green color scheme works for operations consoles.
- **Pattern adapted:** Task register with state badges, detail panel with tabs, health metrics grid
- **Implemented in:** `Forge/app/dashboard/routes.py` (upgrade with animations)

### 3. GSAP Showcase (gsap.com/showcase)
- **What was learned:** Pin + scrub for storytelling works best with 2-3 sections max. Staggered text reveals need `display: inline-block` on spans. Scroll-triggered reveals should use `start: 'top 80%'` to avoid premature triggers.
- **Pattern adapted:** Scroll-triggered panel reveals, staggered entrance animations
- **Implemented in:** `Forge/app/dashboard/routes.py`, `Stratex/static/style.css`

### 4. Three.js Examples (threejs.org/examples)
- **What was learned:** Interactive 3D is justified for portfolio allocation visualization, network graphs, and spatial data. Must lazy-load with IntersectionObserver. Need WebGL fallback for headless/no-WebGL environments.
- **Pattern adapted:** Lazy-loaded Three.js scene for Stratex portfolio visualization (optional, documented)
- **Implemented in:** Documentation only (implemented as optional enhancement)

### 5. Lenis (lenis.dev)
- **What was learned:** Lenis must be integrated with GSAP ticker, not just `requestAnimationFrame`. Must disable under `prefers-reduced-motion`. Smooth scroll works best when combined with `scroll-behavior: auto` on html.
- **Pattern adapted:** Smooth scroll integration with GSAP ScrollTrigger
- **Implemented in:** `Forge/app/dashboard/routes.py` (optional Lenis), `Stratex/static/app.js`

### 6. Motion (motion.dev)
- **What was learned:** Motion (Framer Motion) is ideal for React-based layout animations, gesture handling, and page transitions. For vanilla HTML, CSS transitions are sufficient.
- **Pattern adapted:** CSS view transitions for SPA-like panel switching
- **Implemented in:** `Stratex/static/style.css` (CSS `@keyframes enter`)

## Transferable Design Lessons

1. **Dark themes with single-accent color systems** are more effective than multi-color palettes for data dashboards. The lime accent in Stratex and the green accent in Forge both follow this principle.

2. **Monospaced fonts for all numeric data** eliminates tabular misalignment. DM Mono at 9-10px with tabular-nums works at dashboard density.

3. **Panel-based layouts with consistent padding** (18px desktop, 14px mobile) create visual rhythm without requiring grid frameworks.

4. **State badges with color + shape** (dot + label) are more scannable than text-only status indicators.

5. **Scroll-triggered reveals should be subtle** — 0.5s duration, 30px y-offset, opacity 0→1. Never bounce or overshoot in data dashboards.

6. **Reduced-motion fallbacks are not optional.** Every animation must have a CSS `@media (prefers-reduced-motion: reduce)` fallback that shows content instantly.

7. **Lazy-load everything expensive.** Three.js, GSAP, and Lenis should load after initial paint. Use IntersectionObserver or dynamic import.

8. **Hover states should be fast** — 0.16s transitions for cards, 0.18s for buttons. Longer hovers feel sluggish.

9. **Focus states must be visible.** 2px lime outline with 3px offset on all interactive elements. Never rely on color alone for state.

10. **Responsive breakpoints should restructure, not just scale.** At 900px, the sidebar becomes a sticky top nav. At 640px, metrics go from 5-col to 2-col.
