"use client";

import { CSSProperties, ReactNode, useCallback, useEffect, useRef, useState } from "react";

/* ============================================================
   FRIDAY effects kit — "Living Universe" edition (2026-11-13,
   ZAI Agent 1). Owner directive: the dashboard must be attractive
   and dynamic — floating elements, aurora, particles, glass and
   motion (the reactbits aesthetic) — WITHOUT losing information
   density or the working features. This edition reinstates every
   layer that the Obsidian Console retired, engineered so that:

   - everything is GPU-friendly (transform/opacity/blur only);
   - every layer pauses when the tab is hidden;
   - prefers-reduced-motion collapses all of it to static renders;
   - no layer ever intercepts pointer events over content.

   Layers: AuroraBackground (CSS blobs) · ParticleField (canvas
   starfield with pointer parallax) · FloatingOrbs (glass drift) ·
   Orbital (satellite rings around the voice orb) · Parallax ·
   Magnetic · SpotlightCard · ScrambleText · CountUp · Reveal.
   ============================================================ */

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ---------------- ambient: aurora ---------------- */

/** Drifting aurora blobs — pure CSS keyframes, zero JS cost. */
export function AuroraBackground() {
  return (
    <div className="aurora" aria-hidden="true">
      <span className="aurora-blob a1" />
      <span className="aurora-blob a2" />
      <span className="aurora-blob a3" />
      <span className="aurora-blob a4" />
      <div className="aurora-vignette" />
    </div>
  );
}

/* ---------------- ambient: starfield ---------------- */

/**
 * Canvas starfield with three parallax depth layers that lean with
 * the pointer. ~130 stars, one rAF loop that parks itself when the
 * tab hides; collapses to a static scatter under reduced motion.
 */
export function ParticleField({ density = 130 }: { density?: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = prefersReducedMotion();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;

    type Star = { x: number; y: number; r: number; depth: number; tw: number; phase: number };
    let stars: Star[] = [];
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

    const resize = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(40, Math.round((density * width * height) / (1280 * 720)));
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: 0.4 + Math.random() * 1.5,
        depth: 0.25 + Math.random() * 0.75,
        tw: 0.4 + Math.random() * 2.2,
        phase: Math.random() * Math.PI * 2,
      }));
    };

    let raf = 0;
    let last = 0;
    let running = true;

    const draw = (now: number) => {
      if (!running) return;
      raf = requestAnimationFrame(draw);
      if (now - last < 33) return; // ~30fps is plenty for stars
      last = now;
      pointer.x += (pointer.tx - pointer.x) * 0.06;
      pointer.y += (pointer.ty - pointer.y) * 0.06;
      ctx.clearRect(0, 0, width, height);
      for (const s of stars) {
        const twinkle = reduced ? 0.75 : 0.55 + 0.45 * Math.sin(now / 1000 / s.tw + s.phase);
        const px = s.x + pointer.x * s.depth * 26;
        const py = s.y + pointer.y * s.depth * 26;
        ctx.globalAlpha = Math.min(1, twinkle * (0.35 + s.depth * 0.6));
        ctx.fillStyle = s.depth > 0.8 ? "#cfe4ff" : s.depth > 0.5 ? "#9db8ff" : "#6d7fa8";
        ctx.beginPath();
        ctx.arc(px, py, s.r * (0.7 + s.depth * 0.6), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    };

    const onPointer = (e: PointerEvent) => {
      pointer.tx = (e.clientX / window.innerWidth - 0.5) * 2;
      pointer.ty = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        if (!running) {
          running = true;
          raf = requestAnimationFrame(draw);
        }
      } else {
        running = false;
        cancelAnimationFrame(raf);
      }
    };

    resize();
    if (reduced) {
      // static scatter, no loop, no pointer listener
      last = -1e9;
      draw(0);
      cancelAnimationFrame(raf);
      running = false;
    } else {
      raf = requestAnimationFrame(draw);
      window.addEventListener("pointermove", onPointer, { passive: true });
    }
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [density]);

  return <canvas ref={canvasRef} className="starfield" aria-hidden="true" />;
}

/* ---------------- ambient: floating glass orbs ---------------- */

/** Slow-drifting translucent glass orbs behind the hero zones. */
export function FloatingOrbs() {
  return (
    <div className="floating-orbs" aria-hidden="true">
      <span className="fo fo1" />
      <span className="fo fo2" />
      <span className="fo fo3" />
    </div>
  );
}

/* ---------------- orbital satellite rings ---------------- */

export interface OrbitalAgent {
  id: string;
  name?: string;
  status?: string;
}

/**
 * Satellite ring around the voice orb. When `agents` is provided the
 * satellites are REAL fleet members (position + status color + tooltip
 * from live probe data — never decorative claims); otherwise a neutral
 * decorative ring. Two counter-rotating rings, GPU transforms only.
 */
export function Orbital({
  children,
  agents,
  className,
  radius,
  duration = 44,
  count,
}: {
  children?: ReactNode;
  agents?: OrbitalAgent[];
  className?: string;
  radius?: number;
  duration?: number;
  count?: number;
}) {
  void count; void radius; // sizing is CSS-driven for responsiveness
  const tone = (s?: string) => {
    const v = String(s ?? "").toUpperCase();
    if (["ONLINE", "REACHABLE", "OK", "HEALTHY"].includes(v)) return "good";
    if (["DEGRADED", "WARN", "PENDING"].includes(v)) return "warn";
    if (["OFFLINE", "UNREACHABLE", "FAILED", "ERROR"].includes(v)) return "bad";
    return "muted";
  };
  const list = agents && agents.length > 0 ? agents.slice(0, 10) : [];
  const outer = list.slice(0, Math.ceil(list.length / 2));
  const inner = list.slice(Math.ceil(list.length / 2));
  const ringStyle = (i: number, total: number, offset = 0): CSSProperties => ({
    ["--a" as string]: `${(360 / Math.max(total, 1)) * i + offset}deg`,
  });

  return (
    <div className={`orbital-wrap${className ? ` ${className}` : ""}`} style={{ ["--spin" as string]: `${duration}s` }}>
      <div className="orbital-ring" aria-hidden={list.length ? undefined : "true"}>
        {outer.length
          ? outer.map((a, i) => (
              <span key={a.id} className={`sat t-${tone(a.status)}`} style={ringStyle(i, outer.length)} title={`${a.name ?? a.id} · ${String(a.status ?? "").toLowerCase()}`} />
            ))
          : Array.from({ length: 5 }, (_, i) => <span key={i} className="sat t-deco" style={ringStyle(i, 5)} />)}
      </div>
      <div className="orbital-ring rev" aria-hidden={list.length ? undefined : "true"}>
        {/* offset 45°: keeps the bottom-center slot free for the state pill */}
        {inner.length
          ? inner.map((a, i) => (
              <span key={a.id} className={`sat t-${tone(a.status)}`} style={ringStyle(i, inner.length, 45)} title={`${a.name ?? a.id} · ${String(a.status ?? "").toLowerCase()}`} />
            ))
          : Array.from({ length: 4 }, (_, i) => <span key={i} className="sat t-deco" style={ringStyle(i, 4, 45)} />)}
      </div>
      {children}
    </div>
  );
}

/* ---------------- interaction: parallax ---------------- */

/** Pointer parallax wrapper. Depth 0..1; disabled for touch and reduced motion. */
export function Parallax({
  children,
  depth = 0.35,
  className,
}: {
  children: ReactNode;
  depth?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (prefersReducedMotion() || !window.matchMedia("(pointer: fine)").matches) return;
    let raf = 0;
    let cx = 0;
    let cy = 0;
    let tx = 0;
    let ty = 0;
    const onMove = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect();
      const midX = rect.left + rect.width / 2;
      const midY = rect.top + rect.height / 2;
      tx = ((e.clientX - midX) / Math.max(rect.width / 2, 1)) * 10 * depth;
      ty = ((e.clientY - midY) / Math.max(rect.height / 2, 1)) * 8 * depth;
    };
    const tick = () => {
      raf = requestAnimationFrame(tick);
      cx += (tx - cx) * 0.08;
      cy += (ty - cy) * 0.08;
      el.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      el.style.transform = "";
    };
  }, [depth]);
  return (
    <div ref={ref} className={`parallax${className ? ` ${className}` : ""}`} style={{ willChange: "transform" }}>
      {children}
    </div>
  );
}

/* ---------------- interaction: magnetic ---------------- */

/** Buttons drift toward the cursor a few px and spring back on leave. */
export function Magnetic({ children, strength = 6 }: { children: ReactNode; strength?: number }) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const onMove = useCallback(
    (e: React.PointerEvent<HTMLSpanElement>) => {
      const el = ref.current;
      if (!el || prefersReducedMotion()) return;
      const rect = el.getBoundingClientRect();
      const dx = (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2 || 1);
      const dy = (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2 || 1);
      el.style.transform = `translate3d(${(dx * strength).toFixed(2)}px, ${(dy * strength * 0.7).toFixed(2)}px, 0)`;
    },
    [strength],
  );
  const reset = useCallback(() => {
    const el = ref.current;
    if (el) el.style.transform = "";
  }, []);
  return (
    <span
      ref={ref}
      className="magnetic"
      onPointerMove={onMove}
      onPointerLeave={reset}
      style={{ display: "inline-flex" }}
    >
      {children}
    </span>
  );
}

/* ---------------- interaction: spotlight ---------------- */

/** Glass card with a cursor-following radial highlight. */
export function SpotlightCard({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const onMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    el.style.setProperty("--my", `${e.clientY - rect.top}px`);
  }, []);
  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      className={className ? `${className} spotlight` : "spotlight"}
      style={style}
    >
      {children}
    </div>
  );
}

/* ---------------- text: scramble ---------------- */

const SCRAMBLE_CHARS = "ABCDEFGHKMNPRSTUVXYZ#%*+<>/\\";

/** Text scrambles in once on mount (and on text change). Static under reduced motion. */
export function ScrambleText({ text, speed = 35, className }: { text: string; speed?: number; className?: string }) {
  const [shown, setShown] = useState(text);
  useEffect(() => {
    if (prefersReducedMotion()) {
      setShown(text);
      return;
    }
    let frame = 0;
    let timer = 0;
    const total = Math.max(text.length, 1);
    const settleAt = (i: number) => Math.floor((i / total) * (total * 2));
    const step = () => {
      frame += 1;
      let out = "";
      let pending = false;
      for (let i = 0; i < total; i++) {
        if (text[i] === " ") {
          out += " ";
          continue;
        }
        if (frame >= settleAt(i) + 3) out += text[i];
        else {
          out += SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
          pending = true;
        }
      }
      setShown(out);
      if (pending) timer = window.setTimeout(step, speed);
    };
    step();
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  return <span className={`scramble${className ? ` ${className}` : ""}`}>{shown}</span>;
}

/* ---------------- numbers: count up ---------------- */

export function CountUp({ value, duration = 900, suffix }: {
  value: number;
  duration?: number;
  suffix?: string;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const reduced = prefersReducedMotion();
    if (reduced) {
      setShown(value);
      return;
    }
    let raf = 0;
    const total = Math.min(Math.max(duration, 200), 1200);
    const start = performance.now();
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

/* ---------------- layout: reveal ---------------- */

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
