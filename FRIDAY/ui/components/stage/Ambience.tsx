"use client";

import { useEffect, useRef, useState } from "react";

/* ================================================================
   The ambient sky (TASK-IG-WEB-04).

   Source idea (IG reference corpus, DaLGg9yMmn6): an animated,
   interactive background layer for the dashboard.

   A field of slow motes drifting behind the room, in Halo's
   own indigo / sky / violet / teal, leaning a few pixels
   toward the pointer by depth. It lives inside the stage's
   existing .stage-ambience layer, above the phase-reactive
   CSS gradients and below everything else.

   It is OFF by default — Halo's current home is the live
   design and its look does not change uninvited. The veil
   carries the toggle; the choice persists in localStorage.

   Same discipline as the halo itself: DPR capped, the loop
   pauses while the tab is hidden, and on reduced-motion or
   low-power hardware the component renders nothing at all —
   the CSS ambience underneath remains the whole story.
   ================================================================ */

const COLORS: Array<[number, number, number]> = [
  [56, 189, 248], // sky
  [99, 102, 241], // indigo
  [168, 85, 247], // violet
  [47, 230, 189], // teal
];

interface Mote {
  x: number; // 0..1 of width
  y: number; // 0..1 of height
  depth: number; // 0.3..1 — size, brightness, parallax reach
  vx: number;
  vy: number;
  phase: number;
  speed: number;
  color: [number, number, number];
}

function makeMotes(count: number): Mote[] {
  const motes: Mote[] = [];
  for (let i = 0; i < count; i++) {
    motes.push({
      x: Math.random(),
      y: Math.random(),
      depth: 0.3 + Math.random() * 0.7,
      vx: (Math.random() - 0.5) * 0.00006,
      vy: -(0.00002 + Math.random() * 0.00005),
      phase: Math.random() * Math.PI * 2,
      speed: 0.4 + Math.random() * 0.8,
      color: COLORS[i % COLORS.length],
    });
  }
  return motes;
}

export function Ambience() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  /* Probed after mount, like the halo's own capability checks:
     nothing renders until the machine says it can afford it. */
  const [capable, setCapable] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cores = navigator.hardwareConcurrency ?? 4;
    const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!reduced && cores > 2 && memory > 2) setCapable(true);
  }, []);

  useEffect(() => {
    if (!capable) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let motes: Mote[] = [];
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      width = parent.clientWidth;
      height = parent.clientHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(28, Math.min(90, Math.round((width * height) / 24000)));
      if (motes.length === 0) motes = makeMotes(count);
    };
    resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    if (ro && canvas.parentElement) ro.observe(canvas.parentElement);

    const onPointer = (event: PointerEvent) => {
      pointer.tx = (event.clientX / Math.max(window.innerWidth, 1)) * 2 - 1;
      pointer.ty = (event.clientY / Math.max(window.innerHeight, 1)) * 2 - 1;
    };
    window.addEventListener("pointermove", onPointer, { passive: true });

    let raf = 0;
    const tick = (now: number) => {
      raf = window.requestAnimationFrame(tick);
      if (document.hidden || width === 0) return;
      pointer.x += (pointer.tx - pointer.x) * 0.03;
      pointer.y += (pointer.ty - pointer.y) * 0.03;
      ctx.clearRect(0, 0, width, height);
      const t = now / 1000;
      for (const mote of motes) {
        mote.x += mote.vx;
        mote.y += mote.vy;
        if (mote.y < -0.02) {
          mote.y = 1.02;
          mote.x = Math.random();
        }
        if (mote.x < -0.02) mote.x = 1.02;
        if (mote.x > 1.02) mote.x = -0.02;
        const px = mote.x * width + pointer.x * mote.depth * 14;
        const py = mote.y * height + pointer.y * mote.depth * 10;
        const twinkle = 0.65 + 0.35 * Math.sin(t * mote.speed + mote.phase);
        const alpha = 0.3 * mote.depth * twinkle;
        const [r, g, b] = mote.color;
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(px, py, 0.7 + mote.depth * 1.5, 0, Math.PI * 2);
        ctx.fill();
      }
    };
    raf = window.requestAnimationFrame(tick);

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onPointer);
      ro?.disconnect();
    };
  }, [capable]);

  if (!capable) return null;
  return <canvas ref={canvasRef} className="ambience-canvas" aria-hidden="true" />;
}
