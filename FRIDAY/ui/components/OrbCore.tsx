"use client";

import { AudioLines, Ear, Loader2, Radio, Sparkles } from "lucide-react";

export type OrbState = "idle" | "connecting" | "listening" | "thinking" | "speaking";

const STATE_LABELS: Record<OrbState, string> = {
  idle: "FRIDAY standing by",
  connecting: "Establishing neural link",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

function stateGlyph(state: OrbState) {
  const size = 54;
  const sw = { strokeWidth: 1.8 };
  switch (state) {
    case "listening":
      return <Ear size={size} {...sw} className="orb-glyph" />;
    case "thinking":
      return <Sparkles size={size} {...sw} className="orb-glyph" />;
    case "connecting":
      return <Loader2 size={size} {...sw} className="orb-glyph spin" />;
    case "speaking":
      return <Radio size={size} {...sw} className="orb-glyph" />;
    default:
      return <AudioLines size={size} {...sw} className="orb-glyph" />;
  }
}

/**
 * The FRIDAY core orb — the hero centerpiece.
 * Pure CSS/SVG animation layers (GPU-composited, no per-frame JS),
 * state-reactive colors: idle cyan, listening mint, thinking amber,
 * speaking violet.
 */
export function OrbCore({ state = "idle", showLabel = true }: { state?: OrbState; showLabel?: boolean }) {
  return (
    <div className="orb" data-state={state} role="img" aria-label={STATE_LABELS[state]}>
      <div className="orb-glow" aria-hidden="true" />
      <div className="orb-ring r1" aria-hidden="true" />
      <div className="orb-ring r2" aria-hidden="true" />
      <div className="orb-ring r3" aria-hidden="true" />
      <div className="orb-core">{stateGlyph(state)}</div>
      <span className="orb-halo" aria-hidden="true" />
      <span className="orb-halo h2" aria-hidden="true" />
      {showLabel && <span className="orb-label">{STATE_LABELS[state]}</span>}
    </div>
  );
}
