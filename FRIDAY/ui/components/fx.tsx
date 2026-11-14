"use client";

import { useId } from "react";

/* Small shared helpers for the Arc edition: a reduced-motion
   check and a dependency-free sparkline. Nothing else — this
   design gets its richness from light and composition, not
   from an effects library. */

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Tiny area sparkline for the Machine view's server readouts. */
export function Sparkline({
  values,
  color,
  width = 132,
  height = 40,
}: {
  values: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  const gid = useId().replace(/[^a-zA-Z0-9]/g, "");
  if (values.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${100 - ((v - min) / span) * 88}`);
  const d = `M${pts.join(" L")}`;
  const area = `${d} L100,100 L0,100 Z`;
  const last = pts[pts.length - 1].split(",");
  return (
    <svg width={width} height={height} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={`fx-spark-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.32" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#fx-spark-${gid})`} stroke="none" />
      <path d={d} fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r={3} fill={color} />
    </svg>
  );
}
