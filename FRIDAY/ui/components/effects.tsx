"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

/* ============================================================
   FRIDAY effects kit — "Reactor Deck" edition (2026-11-14,
   rebuild #2).

   Deliberately smaller than the Aurora kit: the deck's richness
   comes from composition and light, not effect density. What
   remains is load-bearing:
   - Reveal   — one-shot entrance rise (sections of the deck)
   - CountUp  — vitals ribbon numerals tween on real data
   - Orbital  — the live agent satellite ring around the reactor
                core (rendered by VoiceCall; informative, one
                slow compositor rotation)
   Every motion is transform/opacity only, terminates or runs
   as a single compositor loop, and collapses under
   prefers-reduced-motion.
   ============================================================ */

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
