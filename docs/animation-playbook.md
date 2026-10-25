# Animation Playbook

## Principles

1. **Animation serves comprehension.** Every motion must explain, guide, or feedback — never decorate.
2. **Respect reduced motion.** All animations degrade to instant display under `prefers-reduced-motion: reduce`.
3. **Prefer transform/opacity.** Avoid layout-triggering properties (`width`, `top`, `left`, `height`) for animated properties.
4. **One animation system per element.** Do not let GSAP and CSS both control the same property without a deliberate handoff.
5. **Lazy-load heavy effects.** Three.js and WebGL must load after initial paint, only when needed.

## Technology Selection Matrix

| Technique | Use | Library |
|-----------|-----|---------|
| View transitions | Panel switch, tab change | CSS `@keyframes` |
| Hover micro-interactions | Cards, buttons, rows | CSS `transition` |
| Scroll reveal | Section entrance | GSAP ScrollTrigger |
| Scroll progress | Page indicator | GSAP ScrollTrigger |
| Pinned storytelling | Step-by-step reveals | GSAP ScrollTrigger pin |
| Horizontal scroll | Gallery/showcase | GSAP ScrollTrigger |
| Layout animations | Expand/collapse, accordion | Motion (Framer Motion) |
| Gesture handling | Swipe, drag | Motion |
| Smooth scrolling | Overall scroll feel | Lenis |
| Interactive 3D | Scene exploration | Three.js (lazy) |

## Patterns

### 1. Scroll-Triggered Reveal (GSAP ScrollTrigger)

**When:** Content should animate in as user scrolls.
**When not:** Critical data that must be immediately visible.

```javascript
// GSAP ScrollTrigger reveal
gsap.from('.panel', {
  scrollTrigger: { trigger: '.panel', start: 'top 80%' },
  y: 30, opacity: 0, duration: 0.6,
  ease: 'power3.out', stagger: 0.1
});
```

**Common bugs:** Trigger firing before element is in viewport (use `start: 'top 80%'`).
**Accessibility:** Respect `prefers-reduced-motion` — GSAP respects this automatically.
**Performance:** Use `will-change: transform, opacity` on animated elements.

### 2. Pin + Scrub (GSAP ScrollTrigger)

**When:** A section needs to stay in view while scrolling drives a timeline.
**When not:** Long pages where pinning traps the user.

```javascript
gsap.to('.timeline-item', {
  scrollTrigger: {
    trigger: '.pin-section',
    pin: true,
    scrub: 1,
    end: '+=100%'
  },
  y: -200, opacity: 0, stagger: 0.2
});
```

**Common bugs:** Pinning too many sections sequentially (causes jank). Pin max 2-3 sections per page.

### 3. Horizontal Scroll (GSAP ScrollTrigger)

**When:** Showing a row of items that doesn't fit vertically.
**When not:** On mobile — use vertical scroll instead.

```javascript
gsap.to('.horizontal-track', {
  scrollTrigger: {
    trigger: '.horizontal-section',
    pin: true,
    scrub: 1,
    end: () => `+=${document.querySelector('.horizontal-track').scrollWidth}`
  },
  x: -() => document.querySelector('.horizontal-track').scrollWidth
});
```

**Responsive:** Disable on `max-width: 768px` — switch to native vertical scroll.

### 4. Parallax (GSAP ScrollTrigger)

**When:** Layered images or foreground elements should move at different speeds.
**When not:** When it distracts from data (trading dashboards).

```javascript
gsap.to('.parallax-layer', {
  scrollTrigger: { trigger: '.hero', scrub: true },
  y: (i, el) => el.dataset.speed * 100,
  ease: 'none'
});
```

**Performance:** Use `transform: translate3d()` to enable GPU acceleration. Keep parallax depth minimal (max 3 layers).

### 5. Staggered Text Reveal (GSAP)

**When:** Headline or key statement should animate word-by-word.
**When not:** For body text or data tables.

```javascript
gsap.from('.reveal-text .word', {
  scrollTrigger: { trigger: '.reveal-text', start: 'top 80%' },
  y: 20, opacity: 0, duration: 0.5,
  stagger: 0.05, ease: 'power2.out'
});
```

**Accessibility:** Wrap words in `<span class="word">` with `display: inline-block`.

### 6. Page Transition (CSS)

**When:** Switching between views in a SPA-like dashboard.
**When not:** When data must update instantly.

```css
.view-panel.active {
  animation: enter 0.28s ease both;
}
@keyframes enter {
  from { opacity: 0.5; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

**Keep it under 0.3s.** Longer transitions feel sluggish.

### 7. Micro-Interactions (CSS)

**When:** Hover, focus, press feedback on interactive elements.
**When not:** On non-interactive elements.

```css
.market-card {
  transition: border-color 0.16s ease, transform 0.16s ease;
}
.market-card:hover {
  transform: translateY(-2px);
  border-color: rgba(180, 244, 107, 0.25);
}
```

### 8. Scroll Progress Indicator (GSAP)

**When:** User needs to know scroll position in a long page.
**When not:** For short pages or dashboards.

```javascript
gsap.to('.progress-bar', {
  scrollTrigger: {
    trigger: document.body,
    start: 'top top',
    end: 'bottom bottom',
    scrub: 0.3
  },
  scaleX: 1
});
```

### 9. Lenis Smooth Scroll

**When:** The overall scroll feel benefits from smoothing.
**When not:** When GSAP ScrollTrigger pin is used (can conflict).
**Integration:** Must call `lenis.on('scroll', ScrollTrigger.update)` and use `requestAnimationFrame`.

```javascript
const lenis = new Lenis();
lenis.on('scroll', ScrollTrigger.update);
gsap.ticker.add((time) => lenis.raf(time * 1000));
gsap.ticker.lagSmoothing(0);
```

**Always include:** `prefers-reduced-motion` check to disable Lenis.

### 10. Three.js Interactive 3D

**When:** Content genuinely benefits from spatial visualization (e.g., portfolio allocation, network graph).
**When not:** Decorative 3D that doesn't carry information.

```javascript
// Lazy load on scroll
const load3D = () => {
  import('three').then(THREE => {
    // ... scene setup
  });
};
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) {
      load3D();
      observer.disconnect();
    }
  });
  observer.observe(document.querySelector('.scene-3d'));
}
```

**Always:** Check `WebGLRenderingContext` availability, provide canvas fallback.

## Cleanup Patterns

### Route Change (SPA)
```javascript
// Before navigating
gsap.killTweensOf('*');
ScrollTrigger.getAll().forEach(t => t.kill());
lenis?.destroy();

// After new view mounts
requestAnimationFrame(() => {
  initAnimations(newContainer);
});
```

### Component Unmount (React)
```javascript
useEffect(() => {
  const tweens = gsap.from(ref.current, { y: 20, opacity: 0 });
  return () => { tweens.kill(); ScrollTrigger.getAll().forEach(t => t.kill()); };
}, []);
```

### Reduced Motion Fallback
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

```javascript
if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  // Skip GSAP/Lenis, show content immediately
  gsap.set('.panel', { opacity: 1, y: 0 });
  return;
}
```

## Performance Budget

- **Initial JS bundle:** < 50KB (before lazy-loaded libs)
- **GSAP + ScrollTrigger:** ~70KB (load on demand)
- **Lenis:** ~6KB
- **Three.js:** ~150KB (lazy-load only)
- **FPS target:** 60fps on desktop, 30fps minimum on mobile
- **Scroll jank:** < 16ms per frame

## Debugging Checklist

1. ScrollTrigger not firing? Check `trigger` and `start` values.
2. Animation too slow? Reduce duration, use `ease: 'power2.out'`.
3. Page jank? Check for layout-triggering properties, reduce simultaneous animations.
4. Lenis + ScrollTrigger conflict? Ensure `lenis.on('scroll', ScrollTrigger.update)`.
5. Three.js memory leak? Call `renderer.dispose()`, `scene.clear()`, `geometry.dispose()` on unmount.
