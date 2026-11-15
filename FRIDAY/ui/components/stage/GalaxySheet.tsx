"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Counter from "../reactbits/Counter";
import {
  ageLabel,
  clockTime,
  fetchMemories,
  oneLine,
  type MemoryBrowserSnapshot,
  type MemoryEntry,
} from "@/lib/wire";

/* ================================================================
   The Memory Galaxy, summoned (TASK-IG-WEB-03).

   Source idea (IG reference corpus, DfJ8UlUApUN): FRIDAY's
   memories rendered as an explorable starfield — "a universe
   of you" — with search and a voice orb docked in the room
   (the stage's halo stays live underneath this layer, as
   always).

   The stars are real: GET /api/memory/browser returns the most
   recent ACTIVE memories in the live Memora store, each with
   an importance tier and score. Tier sets the colour (pinned
   gold, normal violet, trivial dim cyan), score sets the size,
   and the centre node is the owner — "You".

   Honesty note, also shown in the layer: the threads between
   stars join memories that share a category, or sit nearest
   in the layout when they have none. The endpoint does not
   expose Memora's own relationship edges, so no count of
   "connections" is invented — the threads are a reading aid,
   not a claim about the store's graph.

   The sky is one canvas, drawn in 2D: like the halo, this
   room never depends on a GPU. It turns very slowly; under
   reduced motion it holds still.
   ================================================================ */

const TIER_COLORS: Record<string, string> = {
  pinned: "#fbbf24",
  normal: "#a855f7",
  trivial: "#38bdf8",
  other: "#8ea0c9",
};

function hashOf(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

interface Star {
  memory: MemoryEntry;
  angle: number;
  radiusFrac: number;
  size: number;
  x: number;
  y: number;
}

export function GalaxySheet() {
  const [snap, setSnap] = useState<MemoryBrowserSnapshot | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<MemoryEntry | null>(null);
  const [hoverText, setHoverText] = useState("");

  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const starsRef = useRef<Star[]>([]);
  const angleRef = useRef(0);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchMemories();
        if (!cancelled) setSnap(data);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const memories = useMemo(() => snap?.memories ?? [], [snap]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    return new Set(memories.filter((m) => m.text.toLowerCase().includes(q)).map((m) => m.id));
  }, [memories, query]);

  /* Deterministic layout: a golden-angle spiral seeded by each
     memory's id, so the sky is the same sky on every visit. */
  const layout = useCallback(
    (width: number, height: number): Star[] => {
      const cx = width / 2;
      const cy = height / 2;
      const maxR = Math.min(width, height) * 0.46;
      return memories.map((memory, i) => {
        const frac = Math.sqrt((i + 0.5) / Math.max(memories.length, 1));
        const angle = i * 2.39996 + hashOf(memory.id || memory.text) * 0.6;
        const radiusFrac = 0.12 + frac * 0.88;
        const r = radiusFrac * maxR;
        return {
          memory,
          angle,
          radiusFrac,
          size: 1.6 + Math.max(0, Math.min(1, memory.score)) * 3.2,
          x: cx + Math.cos(angle + angleRef.current) * r,
          y: cy + Math.sin(angle + angleRef.current) * r,
        };
      });
    },
    [memories],
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = wrap.clientWidth;
    const height = Math.max(300, Math.min(500, Math.round(width * 0.62)));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const stars = layout(width, height);
    starsRef.current = stars;

    /* Threads: same-category nearest neighbour, else nearest
       neighbour overall. A reading aid — see the header note. */
    ctx.lineWidth = 1;
    for (let i = 0; i < stars.length; i++) {
      let best: Star | null = null;
      let bestDist = Infinity;
      let bestSame: Star | null = null;
      let bestSameDist = Infinity;
      for (let j = 0; j < stars.length; j++) {
        if (i === j) continue;
        const dx = stars[i].x - stars[j].x;
        const dy = stars[i].y - stars[j].y;
        const dist = dx * dx + dy * dy;
        if (dist < bestDist) {
          bestDist = dist;
          best = stars[j];
        }
        if (
          stars[i].memory.category &&
          stars[i].memory.category === stars[j].memory.category &&
          dist < bestSameDist
        ) {
          bestSameDist = dist;
          bestSame = stars[j];
        }
      }
      const target = bestSame ?? best;
      if (!target) continue;
      const dimmed =
        matches !== null &&
        !(matches.has(stars[i].memory.id) && matches.has(target.memory.id));
      ctx.strokeStyle = dimmed ? "rgba(120, 135, 180, 0.05)" : "rgba(120, 135, 180, 0.16)";
      ctx.beginPath();
      ctx.moveTo(stars[i].x, stars[i].y);
      ctx.lineTo(target.x, target.y);
      ctx.stroke();
    }

    /* Stars. */
    for (const star of stars) {
      const color = TIER_COLORS[star.memory.tier] ?? TIER_COLORS.other;
      const isMatch = matches === null || matches.has(star.memory.id);
      const isSelected = selected?.id === star.memory.id;
      ctx.globalAlpha = isMatch ? 0.95 : 0.13;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.size * (isSelected ? 1.5 : 1), 0, Math.PI * 2);
      ctx.fill();
      if (star.memory.tier === "pinned" || isSelected) {
        ctx.globalAlpha = isMatch ? 0.5 : 0.1;
        ctx.strokeStyle = color;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.size * 2.1, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    /* The centre: you. */
    const cx = width / 2;
    const cy = height / 2;
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 30);
    glow.addColorStop(0, "rgba(233, 237, 251, 0.9)");
    glow.addColorStop(0.35, "rgba(99, 102, 241, 0.45)");
    glow.addColorStop(1, "rgba(99, 102, 241, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, 30, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#e9edfb";
    ctx.font = "600 11px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("YOU", cx, cy + 26);
  }, [layout, matches, selected]);

  useEffect(() => {
    draw();
    const wrap = wrapRef.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [draw]);

  /* The sky turns, very slowly — and stops for reduced motion,
     a hidden tab, or an unmounted layer. */
  useEffect(() => {
    if (reducedMotion || memories.length === 0) return;
    let raf = 0;
    let last = 0;
    const tick = (now: number) => {
      if (!document.hidden && now - last > 66) {
        last = now;
        angleRef.current += 0.0016;
        draw();
      }
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [draw, memories.length, reducedMotion]);

  const pick = (event: React.MouseEvent<HTMLCanvasElement>, commit: boolean) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let nearest: Star | null = null;
    let nearestDist = Infinity;
    for (const star of starsRef.current) {
      const dx = star.x - x;
      const dy = star.y - y;
      const dist = dx * dx + dy * dy;
      if (dist < nearestDist) {
        nearestDist = dist;
        nearest = star;
      }
    }
    if (nearest && nearestDist <= 22 * 22) {
      setHoverText(oneLine(nearest.memory.text, 90));
      if (commit) setSelected(nearest.memory);
    } else {
      setHoverText("");
      if (commit) setSelected(null);
    }
  };

  const tiers = snap?.summary?.tiers ?? {};
  const unreachable = snap?.status === "unreachable";

  return (
    <div className="galaxy">
      <p className="sheet-summary">
        {snap && !unreachable ? (
          <>
            <Counter value={snap.count ?? memories.length} fontSize={20} /> memories in the sky
            {snap.summary?.active_goals ? <> · {snap.summary.active_goals} active goals</> : null}
            <> · {tiers.pinned ?? 0} pinned</>
          </>
        ) : unreachable || failed ? (
          "Memora didn't answer this time — no sky is invented in its place."
        ) : (
          "Asking Memora what it holds…"
        )}
      </p>

      {snap && !unreachable && memories.length > 0 && (
        <>
          <label className="galaxy-search">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search the sky…"
              aria-label="Search memories"
            />
            {matches !== null && (
              <span className="galaxy-match-count">
                {matches.size} of {memories.length} lit
              </span>
            )}
          </label>

          <div className="galaxy-canvas-wrap" ref={wrapRef}>
            <canvas
              ref={canvasRef}
              className="galaxy-canvas"
              role="img"
              aria-label={`Memory galaxy: ${memories.length} memories`}
              onMouseMove={(e) => pick(e, false)}
              onMouseLeave={() => setHoverText("")}
              onClick={(e) => pick(e, true)}
            />
          </div>
          <p className="galaxy-readout" aria-live="polite">
            {hoverText || "Hover a star — click to read the memory whole."}
          </p>

          <div className="galaxy-legend" aria-hidden="true">
            <span>
              <i className="galaxy-dot" style={{ background: TIER_COLORS.pinned }} /> pinned
            </span>
            <span>
              <i className="galaxy-dot" style={{ background: TIER_COLORS.normal }} /> normal
            </span>
            <span>
              <i className="galaxy-dot" style={{ background: TIER_COLORS.trivial }} /> trivial
            </span>
            <span>
              <i className="galaxy-dot" style={{ background: TIER_COLORS.other }} /> other
            </span>
          </div>

          {selected && (
            <article className="galaxy-detail">
              <div className="galaxy-detail-top">
                <span className="pill" style={{ color: TIER_COLORS[selected.tier] ?? TIER_COLORS.other }}>
                  {selected.tier}
                </span>
                {selected.active_goal && <span className="pill tone-warn">active goal</span>}
                {selected.category && <span className="galaxy-detail-cat">{selected.category}</span>}
                <time className="chronicle-time">
                  {clockTime(selected.created_at)} · {ageLabel(selected.created_at)} ago
                </time>
              </div>
              <p className="galaxy-detail-text">{selected.text}</p>
              <p className="galaxy-detail-score">
                importance <b>{selected.score.toFixed(2)}</b>
              </p>
            </article>
          )}

          <p className="sheet-note galaxy-note">
            Threads join memories that share a category, or sit nearest in the layout. The memory
            store&apos;s own relationship edges are not exposed by its browser endpoint, so none
            are invented here — the threads are a reading aid, not a map of the graph.
          </p>
        </>
      )}

      {snap && !unreachable && memories.length === 0 && (
        <p className="sheet-note">The store answered, and it is holding nothing active right now.</p>
      )}
    </div>
  );
}
