"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

/* ============================================================
   FRIDAY effects kit — "Sovereign Aurora" edition (2026-11-14).

   The owner's verdict on the stripped-down Minimal Console was
   "worst of its kind — rebuild it with dynamic effects, floating
   elements, React-Bits-style components." This kit delivers that
   richness under the performance lessons of the Living Universe
   era (which WAS laggy): every effect here is transform/opacity
   only, one-shot or a single compositor loop, with NO canvas,
   NO per-letter timers on live data, and a hard reduced-motion
   opt-out everywhere.

   Kit: Reveal (entrance) · CountUp (numbers) · TextReveal (hero
   word stagger) · Tilt (pointer-tracked card tilt + glare) ·
   Magnetic (primary-action pull) · Orbital (live agent ring
   around the voice orb — informative, one rotation).
   ============================================================ */

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function finePointer(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(pointer: fine)").matches;
}

/* ---------------- entrance ---------------- */

/** One-shot fade-and-rise on mount. No observer, no loop. */
export function Reveal({
  children,
  delay = 0,
  className,
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "article" | "section";
}) {
  const Tag = as as "div";
  return (
    <Tag className={`reveal${className ? ` ${className}` : ""}`} style={{ animationDelay: `${delay}ms` }}>
      {children}
    </Tag>
  );
}

/* ---------------- numbers ---------------- */

/** Tween a number up on mount/change; terminates when done. */
export function CountUp({ value, duration = 700, suffix }: { value: number; duration?: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return (
    <>
      {display.toLocaleString()}
      {suffix}
    </>
  );
}

/* ---------------- hero text ---------------- */

/**
 * React-Bits-style split reveal for the hero line: each word rises
 * out of an overflow mask with a spring stagger, once, on mount.
 * Words are real spans (screen readers read the intact line via
 * aria-label on the parent — callers pass plain text only).
 */
export function TextReveal({
  text,
  className,
  delay = 0,
  stagger = 55,
}: {
  text: string;
  className?: string;
  delay?: number;
  stagger?: number;
}) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <span className={`wrev${className ? ` ${className}` : ""}`} role="text" aria-label={text}>
      {words.map((word, i) => (
        <span className="wrev-mask" key={i} aria-hidden="true">
          <span className="wrev-word" style={{ animationDelay: `${delay + i * stagger}ms` }}>
            {word}
          </span>
        </span>
      ))}
    </span>
  );
}

/* ---------------- tilt cards ---------------- */

/**
 * Pointer-tracked 3D tilt + glare for fleet cards. rAF-throttled,
 * max ~4.5°, transform-only. Inert on touch pointers and under
 * reduced motion (renders a plain wrapper).
 */
export function Tilt({
  children,
  className,
  max = 4.5,
}: {
  children: ReactNode;
  className?: string;
  max?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef(0);

  function onMove(event: React.PointerEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el || prefersReducedMotion() || !finePointer()) return;
    const rect = el.getBoundingClientRect();
    const px = (event.clientX - rect.left) / Math.max(rect.width, 1);
    const py = (event.clientY - rect.top) / Math.max(rect.height, 1);
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      el.style.setProperty("--tilt-x", `${((0.5 - py) * max).toFixed(2)}deg`);
      el.style.setProperty("--tilt-y", `${((px - 0.5) * max).toFixed(2)}deg`);
      el.style.setProperty("--glare-x", `${(px * 100).toFixed(1)}%`);
      el.style.setProperty("--glare-y", `${(py * 100).toFixed(1)}%`);
      el.classList.add("tilting");
    });
  }

  function onLeave() {
    const el = ref.current;
    if (!el) return;
    cancelAnimationFrame(rafRef.current);
    el.classList.remove("tilting");
    el.style.setProperty("--tilt-x", "0deg");
    el.style.setProperty("--tilt-y", "0deg");
  }

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  return (
    <div ref={ref} className={`tilt${className ? ` ${className}` : ""}`} onPointerMove={onMove} onPointerLeave={onLeave}>
      {children}
    </div>
  );
}

/* ---------------- magnetic actions ---------------- */

/**
 * Subtle magnetic pull for the primary action in a panel (the
 * voice button, the send button). The element leans a few px
 * toward the pointer; springs back on leave via CSS transition.
 * Inert on touch / reduced motion.
 */
export function Magnetic({
  children,
  className,
  strength = 5,
}: {
  children: ReactNode;
  className?: string;
  strength?: number;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);

  function onMove(event: React.PointerEvent<HTMLSpanElement>) {
    const el = ref.current;
    if (!el || prefersReducedMotion() || !finePointer()) return;
    const rect = el.getBoundingClientRect();
    const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2);
    el.style.transform = `translate(${(dx / Math.max(rect.width, 1)) * strength}px, ${(dy / Math.max(rect.height, 1)) * strength}px)`;
  }

  function onLeave() {
    const el = ref.current;
    if (el) el.style.transform = "";
  }

  return (
    <span ref={ref} className={`magnetic${className ? ` ${className}` : ""}`} onPointerMove={onMove} onPointerLeave={onLeave}>
      {children}
    </span>
  );
}

/* ---------------- voice orb ring ---------------- */

/** Live fleet as a quiet satellite ring around the voice orb.
 *  Pure CSS rotation (one compositor loop, no JS), real agent colors. */
export function Orbital({
  agents,
  duration = 60,
  children,
}: {
  agents?: Array<{ id: string; status?: string }>;
  duration?: number;
  children: ReactNode;
}) {
  const sats = (agents ?? []).slice(0, 10);
  return (
    <div className="orbital" style={{ "--orbital-period": `${duration}s` } as React.CSSProperties}>
      {sats.length > 0 && (
        <div className="orbital-ring" aria-hidden="true">
          {sats.map((a, i) => {
            const angle = (i / Math.max(sats.length, 1)) * 360;
            return (
              <span
                key={a.id}
                className={`orbital-sat tone-${a.status?.toLowerCase() === "online" ? "good" : "muted"}`}
                style={{ transform: `rotate(${angle}deg) translateY(calc(var(--orbital-r) * -1))` }}
                title={a.id}
              />
            );
          })}
        </div>
      )}
      <div className="orbital-core">{children}</div>
    </div>
  );
}
