"use client";

import { useEffect, useState } from "react";
import Orb from "../reactbits/Orb";
import type { VoicePhase } from "../VoiceCall";

/* ================================================================
   The halo — the living light at the centre of the room.

   The visual engine is React Bits' Orb (WebGL2 fluid shader),
   driven entirely by state: hue, speed and intensity follow the
   conversation's phase, so the light is information, not decor.
     resting   slow indigo breath
     opening   brightening, gathering speed
     listening cyan, attentive
     thinking  violet, fast churn
     speaking  teal, intensified
     down      ember red, nearly still

   Not every device gets the shader. Reduced-motion settings, a
   missing WebGL2 context, or a low-power device all fall back to
   a pure-CSS halo that carries the same phase colours at a
   fraction of the cost — the room never depends on a GPU.
   ================================================================ */

const PHASE_LOOK: Record<VoicePhase, { hue: number; speed: number; intensity: number; force: boolean }> = {
  resting: { hue: 0, speed: 0.35, intensity: 0.55, force: false },
  opening: { hue: 10, speed: 0.9, intensity: 0.9, force: false },
  listening: { hue: -14, speed: 0.55, intensity: 0.8, force: false },
  thinking: { hue: 58, speed: 1.5, intensity: 1.0, force: false },
  speaking: { hue: -58, speed: 0.85, intensity: 1.25, force: true },
  down: { hue: 142, speed: 0.25, intensity: 0.4, force: false },
};

const BASE_COLORS = ["#38bdf8", "#6366f1", "#a855f7"];

function webgl2Available(): boolean {
  try {
    const probe = document.createElement("canvas");
    const gl = probe.getContext("webgl2");
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

function lowPowerDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const cores = navigator.hardwareConcurrency ?? 8;
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  return cores <= 2 || memory <= 2;
}

export function Halo({ phase, onTap }: { phase: VoicePhase; onTap?: () => void }) {
  const [shaderOk, setShaderOk] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    /* Capability probe: WebGL2 support, device power class and
       the owner's motion preference only exist after mount, so
       this state is set from the effect by design. */
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReducedMotion(motion.matches);
    setShaderOk(webgl2Available() && !lowPowerDevice());
    const onMotion = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    motion.addEventListener("change", onMotion);
    const onVisibility = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      motion.removeEventListener("change", onMotion);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const look = PHASE_LOOK[phase];
  const useShader = shaderOk && !reducedMotion;

  return (
    <button
      type="button"
      className="halo"
      data-phase={phase}
      onClick={onTap}
      aria-label={
        phase === "resting" || phase === "down"
          ? "Start a voice call with FRIDAY"
          : phase === "opening"
            ? "Voice call is connecting"
            : "Voice call in progress — tap End the line below to close it"
      }
    >
      {useShader ? (
        <Orb
          colors={BASE_COLORS}
          hue={look.hue}
          speed={look.speed}
          hoverIntensity={look.intensity}
          forceHoverState={look.force}
          rotateOnHover={false}
          followCursor={false}
          clickPulse={false}
          dpr={Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 1.75)}
          paused={hidden}
        />
      ) : (
        <span className="halo-fallback" aria-hidden="true">
          <span className="halo-fallback-core" />
          <span className="halo-fallback-ring" />
        </span>
      )}
      <span className="halo-hint" aria-hidden="true">
        {phase === "resting" ? "tap to talk" : phase === "down" ? "tap to retry" : ""}
      </span>
    </button>
  );
}
