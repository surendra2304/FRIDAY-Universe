"use client";

import { CSSProperties, ReactNode, useEffect, useRef, useState } from "react";

/* ============================================================
   FRIDAY effects kit — React-Bits-style dynamic components.
   Every effect is mobile-safe: compositor-only animations,
   adaptive counts, pauses when offscreen or tab-hidden, and
   full prefers-reduced-motion compliance.
   ============================================================ */

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ---------- Aurora background (pure CSS, GPU transforms) ---------- */
export function AuroraBackground() {
  return (
    <>
      <div className="aurora" aria-hidden="true">
        <div className="aurora-blob b1" />
        <div className="aurora-blob b2" />
        <div className="aurora-blob b3" />
      </div>
      <div className="noise" aria-hidden="true" />
      <div className="grid-overlay" aria-hidden="true" />
    </>
  );
}

/* ---------- Floating glass orbs (pure CSS drift, reduced-motion safe) ---------- */
export function FloatingOrbs() {
  return (
    <div className="float-orbs" aria-hidden="true">
      <span className="float-orb o1" />
      <span className="float-orb o2" />
      <span className="float-orb o3" />
      <span className="float-orb o4" />
      <span className="float-orb o5" />
    </div>
  );
}

/* ---------- Particle field (canvas, adaptive + self-pausing) ---------- */
type Particle = { x: number; y: number; vx: number; vy: number; r: number; c: string; a: number };

export function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const realCtx = canvas.getContext("2d");
    if (!realCtx) return;

    const reduced = prefersReducedMotion();
    let width = 0;
    let height = 0;
    let dpr = 1;
    let particles: Particle[] = [];
    let raf = 0;
    let running = true;
    const mouse = { x: -9999, y: -9999 };
    const palette = ["133,240,191", "112,212,232", "185,166,255"];

    function resize() {
      if (!canvas) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      realCtx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      // Adaptive count: phones get a light field, desktops a richer one.
      const target = Math.round(Math.min(110, Math.max(26, (width * height) / 22000)));
      particles = Array.from({ length: target }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: 0.7 + Math.random() * 1.6,
        c: palette[Math.floor(Math.random() * palette.length)],
        a: 0.25 + Math.random() * 0.45,
      }));
    }

    function frame() {
      if (!running) return;
      const ctx2 = realCtx!;
      ctx2.clearRect(0, 0, width, height);
      const linkDist = width < 720 ? 88 : 110;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        // Gentle mouse attraction on fine-pointer devices only.
        if (mouse.x > -999) {
          const dx = mouse.x - p.x;
          const dy = mouse.y - p.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < 32400 && d2 > 1) {
            const f = 0.012 / Math.sqrt(d2);
            p.vx += dx * f;
            p.vy += dy * f;
          }
        }
        p.x += p.vx;
        p.y += p.vy;
        p.vx *= 0.995;
        p.vy *= 0.995;
        if (p.x < -20) p.x = width + 20;
        if (p.x > width + 20) p.x = -20;
        if (p.y < -20) p.y = height + 20;
        if (p.y > height + 20) p.y = -20;
        ctx2.beginPath();
        ctx2.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx2.fillStyle = `rgba(${p.c},${p.a})`;
        ctx2.fill();
        if (i % 2 === 0) continue; // halve link work on mobile-class devices
        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < linkDist * linkDist) {
            const alpha = (1 - Math.sqrt(d2) / linkDist) * 0.14;
            ctx2.strokeStyle = `rgba(133,240,191,${alpha})`;
            ctx2.lineWidth = 1;
            ctx2.beginPath();
            ctx2.moveTo(p.x, p.y);
            ctx2.lineTo(q.x, q.y);
            ctx2.stroke();
          }
        }
      }
      raf = requestAnimationFrame(frame);
    }

    function start() {
      if (reduced) return;
      if (!running) {
        running = true;
        raf = requestAnimationFrame(frame);
      }
    }
    function stop() {
      running = false;
      cancelAnimationFrame(raf);
    }

    function onVisibility() {
      if (document.hidden) stop();
      else if (inView) start();
    }

    function onMouse(event: PointerEvent) {
      if (event.pointerType !== "mouse") return;
      mouse.x = event.clientX;
      mouse.y = event.clientY;
    }
    function onMouseLeave() {
      mouse.x = -9999;
      mouse.y = -9999;
    }

    let inView = true;
    const io = new IntersectionObserver(
      (entries) => {
        inView = entries[0]?.isIntersecting ?? true;
        if (inView && !document.hidden) start();
        else stop();
      },
      { threshold: 0 },
    );
    io.observe(canvas);

    resize();
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pointermove", onMouse, { passive: true });
    window.addEventListener("pointerleave", onMouseLeave);
    if (!reduced) start();

    return () => {
      stop();
      io.disconnect();
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pointermove", onMouse);
      window.removeEventListener("pointerleave", onMouseLeave);
    };
  }, []);

  if (typeof window !== "undefined" && prefersReducedMotion()) return null;
  return <canvas id="particles" ref={canvasRef} aria-hidden="true" />;
}

/* ---------- Scramble / decrypt text ---------- */
const SCRAMBLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*+<>/";

export function ScrambleText({
  text,
  className,
  speed = 34,
  once = true,
  style,
}: {
  text: string;
  className?: string;
  speed?: number;
  once?: boolean;
  style?: CSSProperties;
}) {
  const [display, setDisplay] = useState(text);
  const ref = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplay(text);
      return;
    }
    let frame = 0;
    let interval: ReturnType<typeof setInterval> | undefined;
    const queue = text.split("").map((_, i) => ({ start: i * 2 + 4, end: i * 2 + 12 }));

    function run() {
      frame = 0;
      interval = setInterval(() => {
        let out = "";
        let done = 0;
        for (let i = 0; i < text.length; i++) {
          const ch = text[i];
          if (ch === " ") { out += " "; done++; continue; }
          const q = queue[i];
          if (frame >= q.end) { out += ch; done++; }
          else if (frame >= q.start) { out += SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)]; }
          else { out += ch; done++; }
        }
        setDisplay(out);
        frame++;
        if (done === text.length && interval) clearInterval(interval);
      }, speed);
    }

    if (once) {
      run();
      return () => { if (interval) clearInterval(interval); };
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          run();
          if (!once) io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => { io.disconnect(); if (interval) clearInterval(interval); };
  }, [text, speed, once]);

  return (
    <span ref={ref} className={`scramble ${className ?? ""}`} style={style}>
      {display}
    </span>
  );
}

/* ---------- Scroll reveal ---------- */
export function Reveal({
  children,
  delay = 0,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "article" | "header";
}) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (prefersReducedMotion()) {
      el.classList.add("revealed");
      return;
    }
    el.style.setProperty("--reveal-delay", `${delay}ms`);
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          el.classList.add("revealed");
          io.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [delay]);

  return (
    <Tag
      ref={ref as never}
      className={`reveal ${className ?? ""}`}
    >
      {children}
    </Tag>
  );
}

/* ---------- Magnetic button (fine pointers only) ---------- */
export function Magnetic({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLSpanElement | null>(null);

  function onMove(event: React.PointerEvent) {
    const el = ref.current;
    if (!el || event.pointerType !== "mouse") return;
    const rect = el.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = event.clientY - rect.top - rect.height / 2;
    el.style.transform = `translate(${x * 0.16}px, ${y * 0.22}px)`;
  }
  function onLeave() {
    const el = ref.current;
    if (!el) return;
    el.style.transform = "translate(0px, 0px)";
  }

  return (
    <span
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{ display: "inline-flex", transition: "transform 0.32s cubic-bezier(0.22,1,0.36,1)", willChange: "transform" }}
    >
      {children}
    </span>
  );
}

/* ---------- Spotlight card ---------- */
export function SpotlightCard({
  children,
  className,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  function onMove(event: React.PointerEvent) {
    const el = ref.current;
    if (!el || event.pointerType !== "mouse") return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${event.clientX - rect.left}px`);
    el.style.setProperty("--my", `${event.clientY - rect.top}px`);
  }

  return (
    <div ref={ref} onPointerMove={onMove} onClick={onClick} className={`spotlight ${className ?? ""}`}>
      {children}
    </div>
  );
}

/* ---------- Count-up number ---------- */
export function CountUp({ value, duration = 900, suffix }: { value: number; duration?: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);

  useEffect(() => {
    const from = prev.current;
    const to = value;
    prev.current = value;
    if (from === to) { setDisplay(to); return; }
    if (prefersReducedMotion()) { setDisplay(to); return; }
    const start = performance.now();
    let raf = 0;
    function tick(now: number) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return (
    <>
      {display}
      {suffix ? <small>{suffix}</small> : null}
    </>
  );
}
