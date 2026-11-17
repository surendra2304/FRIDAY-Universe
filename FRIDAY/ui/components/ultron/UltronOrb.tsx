"use client";

import type { VoicePhase } from "../VoiceCall";

/* ================================================================
   The ULTRON orb — the centre of the command dashboard.

   The visual is the owner's picked design candidate (the ULTRON
   reel dashboard): a red/orange wireframe globe with rotating arc
   gauges, a tick ring and a breathing core, drawn as inline SVG —
   no WebGL, no assets, nothing to load. It is a button, exactly
   like the Halo it replaces: tapping it while the line rests
   starts the voice call (the stage owns that rule; this component
   only reports the tap).

   The phase is information, not decoration: the orb carries
   data-phase and the stylesheet speeds the spin and brightens
   the glow as the conversation moves (speaking fastest/brightest,
   down nearly still). Under prefers-reduced-motion the CSS
   stills every rotation.
   ================================================================ */

export function UltronOrb({ phase, onTap }: { phase: VoicePhase; onTap?: () => void }) {
  return (
    <button
      type="button"
      className="ultron-orb"
      data-phase={phase}
      onClick={onTap}
      aria-label={
        phase === "resting" || phase === "down"
          ? "Start a voice call with FRIDAY"
          : phase === "opening"
            ? "Voice call is connecting"
            : "Voice call in progress — use End the line to close it"
      }
    >
      <span className="ultron-orb-glow" aria-hidden="true" />
      <svg className="ultron-orb-svg" viewBox="0 0 440 440" aria-hidden="true">
        <defs>
          <radialGradient id="ultronCoreGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffe9c4" />
            <stop offset="22%" stopColor="#ffab54" />
            <stop offset="48%" stopColor="#ff5a22" stopOpacity=".85" />
            <stop offset="75%" stopColor="#e82e10" stopOpacity=".35" />
            <stop offset="100%" stopColor="#ff3b1f" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="ultronWire" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffb287" />
            <stop offset=".5" stopColor="#ff6a26" />
            <stop offset="1" stopColor="#ff3b1f" />
          </linearGradient>
        </defs>

        {/* tick ring */}
        <circle cx="220" cy="220" r="203" fill="none" stroke="#ff5a2a" strokeWidth="9" strokeDasharray="2 11.75" opacity=".38" />
        <circle cx="220" cy="220" r="196" fill="none" stroke="#2a3440" strokeWidth="1" />

        {/* rotating arc gauges */}
        <g className="ultron-spin-a">
          <circle cx="220" cy="220" r="182" fill="none" stroke="#ff4a1f" strokeWidth="5" strokeLinecap="round" strokeDasharray="210 934" opacity=".95" />
          <circle cx="220" cy="220" r="182" fill="none" stroke="#ffa53c" strokeWidth="5" strokeLinecap="round" strokeDasharray="70 1074" strokeDashoffset="-420" opacity=".8" />
        </g>
        <g className="ultron-spin-b">
          <circle cx="220" cy="220" r="166" fill="none" stroke="#ff6a26" strokeWidth="1.6" strokeDasharray="3 9" opacity=".6" />
          <circle cx="220" cy="220" r="166" fill="none" stroke="#ff3b1f" strokeWidth="3.5" strokeLinecap="round" strokeDasharray="120 924" strokeDashoffset="-300" opacity=".85" />
        </g>

        {/* wireframe globe */}
        <g className="ultron-breathe">
          <circle cx="220" cy="220" r="140" fill="url(#ultronCoreGlow)" opacity=".34" />
          <g className="ultron-spin-c" opacity=".92">
            <g transform="rotate(-16 220 220)" stroke="url(#ultronWire)" fill="none" strokeWidth="1.4">
              <circle cx="220" cy="220" r="140" />
              <ellipse cx="220" cy="220" rx="52" ry="140" />
              <ellipse cx="220" cy="220" rx="98" ry="140" />
              <ellipse cx="220" cy="152" rx="118" ry="24" />
              <ellipse cx="220" cy="288" rx="118" ry="24" />
              <ellipse cx="220" cy="220" rx="140" ry="34" />
              <ellipse cx="220" cy="98" rx="82" ry="15" />
              <ellipse cx="220" cy="342" rx="82" ry="15" />
            </g>
          </g>
          <ellipse cx="220" cy="220" rx="17" ry="88" fill="url(#ultronCoreGlow)" opacity=".85" />
          <circle cx="220" cy="220" r="34" fill="url(#ultronCoreGlow)" />
          <circle cx="220" cy="220" r="7" fill="#fff6e6" />
          <circle className="ultron-node" cx="150" cy="140" r="3.4" fill="#ffd9a8" />
          <circle className="ultron-node" cx="298" cy="168" r="2.8" fill="#ffb287" style={{ animationDelay: ".6s" }} />
          <circle className="ultron-node" cx="262" cy="308" r="3.2" fill="#ffd9a8" style={{ animationDelay: "1.2s" }} />
          <circle className="ultron-node" cx="142" cy="272" r="2.6" fill="#ff8a4c" style={{ animationDelay: "1.7s" }} />
          <circle className="ultron-node" cx="220" cy="82" r="2.6" fill="#ffe9c4" style={{ animationDelay: ".3s" }} />
        </g>
        <circle cx="220" cy="220" r="140" fill="none" stroke="#ff7a3c" strokeWidth="1.6" opacity=".85" />
      </svg>
      <span className="ultron-orb-hint" aria-hidden="true">
        {phase === "resting" ? "tap to talk" : phase === "down" ? "tap to retry" : ""}
      </span>
    </button>
  );
}
