"use client";

import { CSSProperties, ReactNode, useEffect, useRef, useState } from "react";

/* ============================================================
   FRIDAY effects kit — REDESIGNED 2026-11-13 (ZAI Agent 2).

   The owner rejected the previous theme, and the VLM review named
   the cause: decorative screensaver layers (aurora blobs, particle
   canvas, floating orbs, parallax, magnetic hover) that made the
   dashboard feel like a template and drowned the content. All of
   those are now retired — every export keeps its original call
   signature so callers stay source-compatible, but each renders
   at most a plain wrapper or a static string:

     AuroraBackground / FloatingOrbs / ParticleField / Orbital → null
     Parallax / Magnetic / SpotlightCard                  → plain wrappers
     ScrambleText / CountUp                              → static text
     Reveal                                              → kept (subtle fade)

   What remains is the ONLY motion the new design wants: a quiet
   fade-in for sections and the voice orb's state animation.
   ============================================================ */

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ---------- retired ambient layers ---------- */

export function AuroraBackground() {
  return null;
}

export function FloatingOrbs() {
  return null;
}

export function ParticleField() {
  return null;
}

export function Orbital({ className, count, radius, duration }: {
  className?: string; count?: number; radius?: number; duration?: number;
}) {
  void className; void count; void radius; void duration;
  return null;
}

/* ---------- retired interactions → plain wrappers ---------- */

export function Parallax({
  children,
  depth,
  className,
}: {
  children: ReactNode;
  depth?: number;
  className?: string;
}) {
  void depth;
  return <div className={className}>{children}</div>;
}

export function Magnetic({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function SpotlightCard({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={className ? `${className} spotlight` : "spotlight"} style={style}>
      {children}
    </div>
  );
}

/* ---------- retired text effects → static renders ---------- */

export function ScrambleText({ text, speed }: { text: string; speed?: number }) {
  void speed;
  return <span className="scramble">{text}</span>;
}

export function CountUp({ value, duration = 900, suffix }: {
  value: number;
  duration?: number;
  suffix?: string;
}) {
  void duration;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    // one quick ease to the final number; reduced-motion users see it instantly
    const reduced = prefersReducedMotion();
    if (reduced) {
      setShown(value);
      return;
    }
    let frame = 0;
    const total = Math.min(Math.max(duration, 200), 1200);
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min((now - start) / total, 1);
      setShown(Math.round(value * (1 - Math.pow(1 - t, 3))));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <span>
      {shown.toLocaleString()}
      {suffix ?? ""}
    </span>
  );
}

/* ---------- kept: subtle section entrance ---------- */

export function Reveal({
  children,
  delay = 0,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.06 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={ref as React.Ref<HTMLDivElement>}
      className={`reveal${visible ? " on" : ""}${className ? ` ${className}` : ""}`}
      style={visible ? { animationDelay: `${delay}ms` } : { opacity: 0 }}
    >
      {children}
    </Tag>
  );
}
