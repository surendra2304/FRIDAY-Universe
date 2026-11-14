"use client";

/* ============================================================
   The Arc — FRIDAY's presence on the Talk screen.

   A reactor of concentric instrument rings around a breathing
   core: two counter-rotating dashed rings, a graduated tick
   dial, and a hot centre whose glow IS the state readout.
   No pictograms inside the core — state is told by light,
   motion and the word beneath it.

   Pure CSS motion (transform/opacity), one slow compositor
   loop per ring, everything stilled under reduced motion.
   ============================================================ */

export type ArcState = "idle" | "connecting" | "listening" | "thinking" | "speaking";

export const ARC_STATE_WORDS: Record<ArcState, string> = {
  idle: "Ready when you are",
  connecting: "Opening the line",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "FRIDAY is speaking",
};

export function Arc({ state = "idle" }: { state?: ArcState }) {
  return (
    <div className="arc" data-state={state} role="img" aria-label={`FRIDAY — ${ARC_STATE_WORDS[state]}`}>
      <span className="arc-halo" aria-hidden="true" />
      <span className="arc-ring ticks" aria-hidden="true" />
      <span className="arc-ring dash-a" aria-hidden="true" />
      <span className="arc-ring dash-b" aria-hidden="true" />
      <span className="arc-ring sweep" aria-hidden="true" />
      <span className="arc-core" aria-hidden="true">
        <span className="arc-eq">
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
        </span>
      </span>
    </div>
  );
}
