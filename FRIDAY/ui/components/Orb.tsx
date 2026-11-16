"use client";

/* TASK-IG2-WEB-03 — Orb: the ULTRON orb visual, adapted as an optional
   FRIDAY website component (spec card ultron-by-sagar-builds.md, MIT).

   Scope, exactly as the card bounds it: ONLY the orb user interface.
   The creator's voice agent and device-control layer are proprietary and
   are NOT in the source repo and NOT attempted here — this component has
   no voice, no controls and no data of its own. It is a visual surface
   whose animation state is driven from outside.

   What was adapted from the source (a Next.js + Three.js holographic orb):
   the visual vocabulary — layered wireframe shells around a spiral core,
   orbiting debris and dust particles, scan rings, pointer parallax.
   What was deliberately changed: the source's Three.js/WebGL stack and
   post-processing (bloom, chromatic aberration) are NOT adopted. The
   FRIDAY website's bundle discipline (the live stage lazy-loads even its
   own voice machinery) cannot carry a 3D engine for a decorative surface,
   so the orb is re-implemented in dependency-free Canvas 2D at a fraction
   of the weight, in the Halo palette. MediaPipe gesture control from the
   source is also not adopted (it needs webcam access the website does not
   ask for); pointer parallax covers the interactive part.

   State model: the orb renders FRIDAY's real voice phases — the same
   VoicePhase union VoiceCall reports (resting / opening / listening /
   thinking / speaking / down) — plus an optional 0..1 level for live
   audio reactivity. Wire it as <Orb phase={phase} level={level} /> next
   to a VoiceCall. Mounted (IG implementation wave, 2026-11-16):
   components/stage/OrbSheet.tsx summons it over the live stage, driven
   by the stage's real voice phase. It remains a summoned layer, not
   the stage's face — the Halo design is untouched.

   Accessibility: prefers-reduced-motion renders one static frame and no
   animation loop (repo design rule). The canvas is aria-hidden decoration;
   the phase is exposed to assistive tech via the visually-hidden label. */

import { useEffect, useRef } from "react";
import type { VoicePhase } from "./VoiceCall";

export interface OrbProps {
  phase: VoicePhase;
  /** Live audio level 0..1 (e.g. from a LiveKit track). Default 0. */
  level?: number;
  /** Canvas CSS size in px. Default 340 (the Halo size on the live stage). */
  size?: number;
}

interface PhaseLook {
  /** Core rotation speed multiplier. */
  spin: number;
  /** Breathing (radius pulse) amplitude 0..1. */
  breath: number;
  /** Shell colour. */
  shell: string;
  /** Core colour. */
  core: string;
}

const LOOKS: Record<VoicePhase, PhaseLook> = {
  resting: { spin: 0.25, breath: 0.02, shell: "148, 163, 255", core: "99, 102, 241" },
  opening: { spin: 0.8, breath: 0.05, shell: "148, 163, 255", core: "56, 189, 248" },
  listening: { spin: 0.5, breath: 0.06, shell: "125, 211, 252", core: "56, 189, 248" },
  thinking: { spin: 1.6, breath: 0.03, shell: "168, 85, 247", core: "168, 85, 247" },
  speaking: { spin: 0.9, breath: 0.1, shell: "148, 163, 255", core: "47, 230, 189" },
  down: { spin: 0.05, breath: 0.005, shell: "251, 113, 133", core: "251, 113, 133" },
};

const PARTICLE_COUNT = 72;
const DEBRIS_COUNT = 22;

export function Orb({ phase, level = 0, size = 340 }: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef({ phase, level });
  stateRef.current = { phase, level };
  const pointerRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    // Deterministic particle fields (stable across frames and phases).
    const particles = Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
      angle: (i / PARTICLE_COUNT) * Math.PI * 2 + (i % 7) * 0.13,
      radius: 0.62 + ((i * 37) % 40) / 100,
      speed: 0.1 + ((i * 53) % 30) / 100,
      size: 1 + ((i * 29) % 3) * 0.6,
    }));
    const debris = Array.from({ length: DEBRIS_COUNT }, (_, i) => ({
      angle: (i / DEBRIS_COUNT) * Math.PI * 2 + (i % 5) * 0.31,
      radius: 1.04 + ((i * 41) % 24) / 100,
      speed: 0.05 + ((i * 17) % 20) / 100,
      size: 1.4 + ((i * 23) % 4) * 0.7,
    }));

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let start = performance.now();

    const draw = (now: number) => {
      const t = (now - start) / 1000;
      const { phase: currentPhase, level: currentLevel } = stateRef.current;
      const look = LOOKS[currentPhase];
      const cx = size / 2 + pointerRef.current.x * 8;
      const cy = size / 2 + pointerRef.current.y * 8;
      const baseR = size * 0.31;
      const pulse = 1 + Math.sin(t * 1.6) * look.breath + currentLevel * 0.12;
      const R = baseR * pulse;

      ctx.clearRect(0, 0, size, size);

      // Scan rings.
      for (let ring = 0; ring < 2; ring += 1) {
        const rr = R * (1.18 + ring * 0.14 + Math.sin(t * 0.7 + ring) * 0.012);
        ctx.beginPath();
        ctx.ellipse(cx, cy, rr, rr * 0.36, -0.42 + pointerRef.current.x * 0.1, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${look.shell}, ${0.16 - ring * 0.05})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Layered wireframe shells: tilted ellipses rotating at phase speed.
      for (let shellIdx = 0; shellIdx < 3; shellIdx += 1) {
        const rot = t * 0.35 * look.spin * (shellIdx % 2 === 0 ? 1 : -1) + shellIdx * (Math.PI / 3);
        ctx.beginPath();
        ctx.ellipse(cx, cy, R, R * (0.38 + shellIdx * 0.2), rot, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${look.shell}, ${0.34 - shellIdx * 0.08})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Spiral core.
      ctx.beginPath();
      const turns = 3.5;
      const steps = 90;
      for (let s = 0; s <= steps; s += 1) {
        const p = s / steps;
        const a = p * Math.PI * 2 * turns + t * 1.1 * look.spin;
        const rr = p * R * 0.52;
        const x = cx + Math.cos(a) * rr;
        const y = cy + Math.sin(a) * rr * 0.82;
        if (s === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${look.core}, 0.85)`;
      ctx.lineWidth = 1.4;
      ctx.stroke();

      // Bright heart.
      const heart = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.3);
      heart.addColorStop(0, `rgba(${look.core}, ${0.5 + currentLevel * 0.3})`);
      heart.addColorStop(1, `rgba(${look.core}, 0)`);
      ctx.fillStyle = heart;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 0.3, 0, Math.PI * 2);
      ctx.fill();

      // Dust particles hugging the shell.
      for (const p of particles) {
        const a = p.angle + t * p.speed * look.spin;
        const x = cx + Math.cos(a) * R * p.radius * pulse;
        const y = cy + Math.sin(a) * R * p.radius * pulse * 0.86;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${look.shell}, 0.5)`;
        ctx.fill();
      }

      // Orbiting debris, slightly outside the shell.
      for (const d of debris) {
        const a = d.angle + t * d.speed * (0.6 + look.spin * 0.4);
        const x = cx + Math.cos(a) * R * d.radius;
        const y = cy + Math.sin(a) * R * d.radius * 0.8;
        ctx.beginPath();
        ctx.arc(x, y, d.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${look.shell}, 0.75)`;
        ctx.fill();
      }

      if (!reduced) raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    if (reduced) {
      // One static frame at a composed angle; no loop.
      start = performance.now() - 2400;
      draw(performance.now());
    }

    const onPointer = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointerRef.current = {
        x: ((event.clientX - rect.left) / rect.width - 0.5) * 2,
        y: ((event.clientY - rect.top) / rect.height - 0.5) * 2,
      };
    };
    canvas.addEventListener("pointermove", onPointer);
    return () => {
      cancelAnimationFrame(raf);
      canvas.removeEventListener("pointermove", onPointer);
    };
  }, [size]);

  return (
    <div style={{ width: size, height: size, position: "relative" }}>
      <canvas ref={canvasRef} style={{ width: size, height: size, display: "block" }} aria-hidden="true" />
      <span
        style={{
          position: "absolute",
          width: 1,
          height: 1,
          overflow: "hidden",
          clip: "rect(0 0 0 0)",
          whiteSpace: "nowrap",
        }}
        role="status"
      >
        FRIDAY is {phase}
      </span>
    </div>
  );
}
