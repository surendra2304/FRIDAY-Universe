"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";

/* ================================================================
   The scroll-driven motion layer — UI KIT form (TASK-WEB-008).

   Moved verbatim from `components/stage/motion.tsx`
   (TASK-IG-WEB-01), which now re-exports this module: the live
   stage keeps importing from `./motion` and sees zero behaviour
   change; the kit is the single implementation from here on.

   Source idea (IG reference corpus, Website-UI roll-up,
   DcOGDRgkhj6): a GSAP ScrollTrigger-style animation system —
   scroll progress, pinned/scrubbed sections, parallax, reveals —
   as a motion layer for Halo.

   It is rebuilt on the stack Halo already has, not on a new
   library: IntersectionObserver for reveals, rAF-throttled
   scroll reads for progress and parallax, and CSS transform /
   opacity for everything that moves. Halo ships zero animation
   dependencies and its small core bundle is a WEB-002 value;
   every pattern in the house animation playbook (scroll reveal,
   scroll progress, pin + scrub, parallax ≤ 3 layers) is natively
   expressible this way, and the Forge console precedent is
   IO-based. Nothing here animates layout properties.

   Reduced motion is a hard rule, not a nicety: under
   `prefers-reduced-motion: reduce`, reveals land instantly
   (CSS), parallax never engages, and the progress hairline is
   the only scroll-linked element left — it carries information,
   not decoration.

   CSS dependency: the classes `reveal` / `is-in`,
   `sheet-progress`, `parallax` live in `app/globals.css` and
   must stay loaded wherever the kit is used.
   ================================================================ */

/** Live `prefers-reduced-motion` state for this device. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    // Capability probe after mount, same pattern as Halo.tsx.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReduced(motion.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    motion.addEventListener("change", onChange);
    return () => motion.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/* ---------------------------------------------------------------
   Reveal — content rises into view as it enters the scrollport.
   The ScrollTrigger "top 80%" start, expressed with an
   IntersectionObserver root margin. Once revealed, it stays
   revealed (these are reading surfaces, not a showreel).
   --------------------------------------------------------------- */
export function Reveal({
  children,
  delay = 0,
  className = "",
  style,
}: {
  children: ReactNode;
  /** Stagger offset in ms, capped by the caller for long lists. */
  delay?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      el.classList.add("is-in");
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            el.classList.add("is-in");
            io.disconnect();
          }
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.05 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`reveal ${className}`}
      style={{ transitionDelay: delay ? `${delay}ms` : undefined, ...style }}
    >
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------
   ScrollProgress — the hairline at a sheet's throat that fills
   as its body scrolls. It writes the transform directly to the
   DOM node (rAF-throttled) so scrolling never re-renders React.
   When the body has nothing to scroll, the bar hides itself.
   --------------------------------------------------------------- */
export function ScrollProgress({
  scrollerRef,
}: {
  scrollerRef: RefObject<HTMLElement | null>;
}) {
  const barRef = useRef<HTMLDivElement | null>(null);
  const fillRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const scroller = scrollerRef.current;
    const bar = barRef.current;
    const fill = fillRef.current;
    if (!scroller || !bar || !fill) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const max = scroller.scrollHeight - scroller.clientHeight;
      if (max <= 4) {
        bar.style.opacity = "0";
        return;
      }
      bar.style.opacity = "1";
      const fraction = Math.min(1, Math.max(0, scroller.scrollTop / max));
      fill.style.transform = `scaleX(${fraction.toFixed(4)})`;
    };
    const onScroll = () => {
      if (!raf) raf = window.requestAnimationFrame(update);
    };
    update();
    scroller.addEventListener("scroll", onScroll, { passive: true });
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onScroll) : null;
    ro?.observe(scroller);
    return () => {
      scroller.removeEventListener("scroll", onScroll);
      ro?.disconnect();
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, [scrollerRef]);

  return (
    <div ref={barRef} className="sheet-progress" aria-hidden="true">
      <span ref={fillRef} />
    </div>
  );
}

/* ---------------------------------------------------------------
   Parallax — a layer that drifts against the scroll at a
   fraction of the scroll speed (the pin + scrub pattern's
   gentler sibling). `speed` is the fraction of the element's
   distance-from-centre to counter-translate; keep it small
   (≤ 0.12) and never stack more than three layers (playbook).
   Finds its own scrolling ancestor; never engages under
   reduced motion or when no scroller exists.
   --------------------------------------------------------------- */
function findScroller(el: HTMLElement): HTMLElement | null {
  let node: HTMLElement | null = el.parentElement;
  while (node) {
    const overflowY = window.getComputedStyle(node).overflowY;
    if (overflowY === "auto" || overflowY === "scroll") return node;
    node = node.parentElement;
  }
  return null;
}

export function Parallax({
  children,
  speed = 0.08,
  className = "",
}: {
  children: ReactNode;
  speed?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || reduced) return;
    const scroller = findScroller(el);
    if (!scroller) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const sRect = scroller.getBoundingClientRect();
      const eRect = el.getBoundingClientRect();
      const centreDelta =
        eRect.top + eRect.height / 2 - (sRect.top + sRect.height / 2);
      const shift = Math.max(-48, Math.min(48, -centreDelta * speed));
      el.style.transform = `translate3d(0, ${shift.toFixed(1)}px, 0)`;
    };
    const onScroll = () => {
      if (!raf) raf = window.requestAnimationFrame(update);
    };
    update();
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      scroller.removeEventListener("scroll", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
      el.style.transform = "";
    };
  }, [reduced, speed]);

  return (
    <div ref={ref} className={`parallax ${className}`}>
      {children}
    </div>
  );
}
