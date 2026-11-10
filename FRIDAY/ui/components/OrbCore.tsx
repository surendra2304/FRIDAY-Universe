"use client";

export type OrbState = "idle" | "connecting" | "listening" | "thinking" | "speaking";

const STATE_LABELS: Record<OrbState, string> = {
  idle: "Standing by",
  connecting: "Opening the line",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

/**
 * The FRIDAY core orb — the console centerpiece.
 * Pure geometry: no pictogram glyphs inside the core (owner directive
 * 2026-11-11: drop the ear / waveform / letter icons). State is expressed
 * only through color, ring motion and the equalizer arcs at the base —
 * calm at rest, alive in a call.
 */
export function OrbCore({ state = "idle", showLabel = true }: { state?: OrbState; showLabel?: boolean }) {
  return (
    <div className="orb" data-state={state} role="img" aria-label={`FRIDAY — ${STATE_LABELS[state]}`}>
      <div className="orb-glow" aria-hidden="true" />
      <div className="orb-ring r1" aria-hidden="true" />
      <div className="orb-ring r2" aria-hidden="true" />
      <div className="orb-ring r3" aria-hidden="true" />
      <div className="orb-core">
        <span className="orb-pulse" aria-hidden="true" />
        <span className="orb-eq" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
          <i />
        </span>
      </div>
      <span className="orb-halo" aria-hidden="true" />
      <span className="orb-halo h2" aria-hidden="true" />
      {showLabel && <span className="orb-label">{STATE_LABELS[state]}</span>}
    </div>
  );
}
