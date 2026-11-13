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

/** Drifting aurora blobs + sky ribbon — pure CSS keyframes, zero JS cost. */
export function AuroraBackground() {
  return (
    <div className="aurora" aria-hidden="true">
      <span className="aurora-ribbon" />
      <span className="aurora-blob a1" />
      <span className="aurora-blob a2" />
      <span className="aurora-blob a3" />
      <span className="aurora-blob a4" />
      <span className="aurora-blob a5" />
      <div className="aurora-vignette" />
    </div>
  );
}

/* ---------------- ambient: starfield ---------------- */

/**
 * Living plexus starfield (react-bits aesthetic, 2026-11-13 owner directive
 * round 2): drifting particles linked by constellation lines when they pass
 * close, three parallax depth layers leaning with the pointer, twinkle, and
 * an occasional shooting star. Canvas, one rAF loop parked when the tab
 * hides; collapses to a static scatter under reduced motion. Line links are
 * O(n²) but n is capped (~110) and the loop runs at ~30fps.
 */
export function ParticleField({
  density = 110,
  linkDistance = 130,
}: {
  density?: number;
  linkDistance?: number;
}) {
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

    type Star = {
      x: number; y: number;
      vx: number; vy: number;
      r: number; depth: number;
      tw: number; phase: number;
      hue: string;
    };
    let stars: Star[] = [];
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    const HUES = ["#cdb4ff", "#8be9ff", "#f2f5ff", "#ffd9a0"];

    const resize = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(36, Math.round((density * width * height) / (1280 * 720)));
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.14,
        vy: (Math.random() - 0.5) * 0.14,
        r: 0.5 + Math.random() * 1.7,
        depth: 0.25 + Math.random() * 0.75,
        tw: 0.4 + Math.random() * 2.2,
        phase: Math.random() * Math.PI * 2,
        hue: HUES[Math.floor(Math.random() * HUES.length)],
      }));
    };

    let raf = 0;
    let last = 0;
    let running = true;
    let shooting: { x: number; y: number; vx: number; vy: number; life: number } | null = null;
    let nextShoot = 4000 + Math.random() * 8000;

    const draw = (now: number) => {
      if (!running) return;
      raf = requestAnimationFrame(draw);
      if (now - last < 33) return; // ~30fps is plenty for stars
      const dt = Math.min((now - last) / 1000, 0.12);
      last = now;
      pointer.x += (pointer.tx - pointer.x) * 0.06;
      pointer.y += (pointer.ty - pointer.y) * 0.06;
      ctx.clearRect(0, 0, width, height);

      // constellation links first (under the dots)
      if (!reduced) {
        ctx.lineWidth = 0.7;
        for (let i = 0; i < stars.length; i++) {
          const a = stars[i];
          for (let j = i + 1; j < stars.length; j++) {
            const b = stars[j];
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const d2 = dx * dx + dy * dy;
            if (d2 > linkDistance * linkDistance) continue;
            const alpha = (1 - Math.sqrt(d2) / linkDistance) * 0.26;
            ctx.strokeStyle = `rgba(150, 160, 255, ${alpha.toFixed(3)})`;
            ctx.beginPath();
            ctx.moveTo(a.x + pointer.x * a.depth * 26, a.y + pointer.y * a.depth * 26);
            ctx.lineTo(b.x + pointer.x * b.depth * 26, b.y + pointer.y * b.depth * 26);
            ctx.stroke();
          }
        }
      }

      for (const s of stars) {
        if (!reduced) {
          s.x += s.vx * dt * 60;
          s.y += s.vy * dt * 60;
          if (s.x < -8) s.x = width + 8; else if (s.x > width + 8) s.x = -8;
          if (s.y < -8) s.y = height + 8; else if (s.y > height + 8) s.y = -8;
        }
        const twinkle = reduced ? 0.75 : 0.55 + 0.45 * Math.sin(now / 1000 / s.tw + s.phase);
        const px = s.x + pointer.x * s.depth * 26;
        const py = s.y + pointer.y * s.depth * 26;
        ctx.globalAlpha = Math.min(1, twinkle * (0.35 + s.depth * 0.6));
        ctx.fillStyle = s.hue;
        ctx.beginPath();
        ctx.arc(px, py, s.r * (0.7 + s.depth * 0.6), 0, Math.PI * 2);
        ctx.fill();
        if (s.depth > 0.85) { // glow halo on the brightest layer
          ctx.globalAlpha = Math.min(0.28, twinkle * 0.22);
          ctx.beginPath();
          ctx.arc(px, py, s.r * 3.2, 0, Math.PI * 2);
          ctx.fillStyle = s.hue;
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;

      // occasional shooting star
      if (!reduced) {
        nextShoot -= 33;
        if (!shooting && nextShoot <= 0) {
          nextShoot = 6000 + Math.random() * 10000;
          shooting = {
            x: Math.random() * width * 0.7 + width * 0.15,
            y: Math.random() * height * 0.3,
            vx: -(5 + Math.random() * 3),
            vy: 2.2 + Math.random() * 1.4,
            life: 1,
          };
        }
        if (shooting) {
          shooting.x += shooting.vx;
          shooting.y += shooting.vy;
          shooting.life -= 0.02;
          const t = Math.max(0, shooting.life);
          const grad = ctx.createLinearGradient(
            shooting.x, shooting.y,
            shooting.x - shooting.vx * 12, shooting.y - shooting.vy * 12,
          );
          grad.addColorStop(0, `rgba(220, 230, 255, ${(0.85 * t).toFixed(3)})`);
          grad.addColorStop(1, "rgba(220, 230, 255, 0)");
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          ctx.moveTo(shooting.x, shooting.y);
          ctx.lineTo(shooting.x - shooting.vx * 12, shooting.y - shooting.vy * 12);
          ctx.stroke();
          if (shooting.life <= 0 || shooting.x < -80 || shooting.y > height + 80) shooting = null;
        }
      }
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
  }, [density, linkDistance]);

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

/* ---------------- text: split entrance ---------------- */

/**
 * SplitText (react-bits style): each word rises out of a blur with a slight
 * stagger. Pure CSS animation driven by a per-word inline delay; static
 * (no animation) under reduced motion. `gradient` paints each word with its
 * own animated gradient — deliberately NOT a clipped parent span, because
 * `background-clip: text` on a parent breaks (renders invisible) when the
 * child words carry their own filter/transform animation layers.
 */
export function SplitText({
  text,
  className,
  delay = 0,
  step = 70,
  gradient = false,
}: {
  text: string;
  className?: string;
  delay?: number;
  step?: number;
  gradient?: boolean;
}) {
  const words = text.split(" ");
  return (
    <span className={`split-text${className ? ` ${className}` : ""}`} aria-label={text} role="text">
      {words.map((word, i) => (
        <span
          key={`${word}-${i}`}
          className={`split-word${gradient ? " grad-word" : ""}`}
          style={{ animationDelay: `${delay + i * step}ms` }}
          aria-hidden="true"
        >
          {word}
          {i < words.length - 1 ? "\u00A0" : ""}
        </span>
      ))}
    </span>
  );
}

/* ---------------- text: gradient shimmer ---------------- */

/**
 * GradientText (react-bits style): an animated violet→cyan→amber gradient
 * that slowly sweeps through the text. Falls back to a static gradient
 * under reduced motion.
 */
export function GradientText({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <span className={`grad-text shimmer${className ? ` ${className}` : ""}`}>{children}</span>;
}

/* ---------------- interaction: click spark ---------------- */

type Spark = { x: number; y: number; vx: number; vy: number; life: number; color: string };

/**
 * ClickSpark (react-bits style): a burst of tiny sparks flies out from the
 * pointer on every click, rendered on a small overlay canvas. Used on the
 * primary voice CTA. Reduced motion renders no sparks.
 */
export function ClickSpark({ children }: { children: ReactNode }) {
  const hostRef = useRef<HTMLSpanElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  /* sparks live in a ref so the click handler and the rAF loop share one list */
  const sparksRef = useRef<Spark[]>([]);

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    if (!host || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let raf = 0;
    const resize = () => {
      const rect = host.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;
      ctx.clearRect(0, 0, w, h);
      const sparks = sparksRef.current;
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.x += s.vx;
        s.y += s.vy;
        s.vy += 0.06;
        s.life -= 0.033;
        if (s.life <= 0) {
          sparks.splice(i, 1);
          continue;
        }
        ctx.globalAlpha = Math.min(1, Math.max(0, s.life));
        ctx.fillStyle = s.color;
        ctx.fillRect(s.x, s.y, 2.2, 2.2);
      }
      ctx.globalAlpha = 1;
    };
    resize();
    raf = requestAnimationFrame(tick);
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  const onClick = (e: React.MouseEvent<HTMLSpanElement>) => {
    const host = hostRef.current;
    if (!host || prefersReducedMotion()) return;
    const rect = host.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const colors = ["#7c5cff", "#22d3ee", "#ffc65c", "#ffffff"];
    const fresh: Spark[] = Array.from({ length: 14 }, (_, i) => {
      const angle = (Math.PI * 2 * i) / 14 + Math.random() * 0.4;
      const speed = 1.6 + Math.random() * 2.4;
      return {
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 0.8,
        life: 0.85 + Math.random() * 0.3,
        color: colors[i % colors.length],
      };
    });
    sparksRef.current = [...sparksRef.current, ...fresh];
  };

  return (
    <span ref={hostRef} className="click-spark" onClick={onClick}>
      <canvas ref={canvasRef} className="click-spark-canvas" aria-hidden="true" />
      {children}
    </span>
  );
}

/* ---------------- interaction: tilt ---------------- */

/**
 * Tilt (react-bits style): subtle 3D perspective tilt following the cursor.
 * Disabled on touch and reduced motion; resets smoothly on leave.
 */
export function Tilt({
  children,
  max = 7,
  className,
}: {
  children: ReactNode;
  max?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const onMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const el = ref.current;
      if (!el || prefersReducedMotion() || e.pointerType === "touch") return;
      const rect = el.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      el.style.transform = `perspective(900px) rotateX(${(-py * max).toFixed(2)}deg) rotateY(${(px * max).toFixed(2)}deg) translateZ(0)`;
    },
    [max],
  );
  const reset = useCallback(() => {
    const el = ref.current;
    if (el) el.style.transform = "";
  }, []);
  return (
    <div ref={ref} className={`tilt${className ? ` ${className}` : ""}`} onPointerMove={onMove} onPointerLeave={reset}>
      {children}
    </div>
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
