"use client";

import { useEffect, useMemo, useState } from "react";

/* ================================================================
   ShowcaseRows — the Netflix-style billboard + browsable rows,
   as a reusable kit component (TASK-WEB-008).

   Generalised from `components/stage/ShowcaseSheet.tsx`
   (TASK-IG-WEB-05, source idea DePJT2NJvz_): the billboard
   features one item and rotates through the pool; the rows
   browse caller-supplied items. The kit takes DATA, not
   endpoints — the caller fetches (fleet, timeline, or any
   catalogue) and hands the items over; when a feed doesn't
   answer, the caller hands over an empty list and the rows
   render their honest empties. Nothing is invented here.

   The live ShowcaseSheet stays the stage surface and is
   untouched by this extraction; ShowcaseRows is the reusable
   kit form for new surfaces and the /kit demo.

   Status tones mirror `toneFor` in `@/lib/wire` so kit cards
   read the same as stage cards without importing the wire.

   CSS dependency: the `showcase-*`, `pill` / `tone-*` and
   `sheet-note` classes live in `app/globals.css`.
   ================================================================ */

export type ShowcaseTone = "good" | "warn" | "bad" | "muted";

/** Status string → pill tone. Same mapping as `toneFor` in `@/lib/wire`. */
export function toneForStatus(status?: string | null): ShowcaseTone {
  const s = String(status ?? "").toUpperCase();
  if (["ONLINE", "REACHABLE", "OK", "HEALTHY", "COMPLETED", "DONE", "SUCCESS"].includes(s))
    return "good";
  if (["DEGRADED", "WARN", "PENDING", "RUNNING", "QUEUED"].includes(s)) return "warn";
  if (["OFFLINE", "UNREACHABLE", "FAILED", "ERROR", "ROUTING_FAILED"].includes(s))
    return "bad";
  return "muted";
}

export interface ShowcaseItem {
  /** Stable key for the card. */
  id: string;
  /** Display name — billboard title and card name. */
  name: string;
  /** Second line — role, description, or blurb. */
  role: string;
  /** Status pill text; omitted when the item has no status. */
  status?: string;
  /** Latency / age line next to the pill, e.g. `42 ms` or `3h ago`. */
  meta?: string;
  /** Extra flag line, e.g. `working`. */
  flag?: string;
}

export interface ShowcaseRow {
  title: string;
  items: ShowcaseItem[];
  /** Shown when the row has no items — the honest empty. */
  emptyText: string;
  /** Wide cards (ledger-style) instead of poster cards. */
  wide?: boolean;
}

export interface ShowcaseRowsProps {
  /** Billboard pool: the featured item rotates through these. */
  featuredPool: ShowcaseItem[];
  /** Kicker above the billboard name. Defaults to `Now answering`. */
  featuredKicker?: string;
  /** Billboard call-to-action label. Defaults to `Open`. */
  featuredCta?: string;
  /** Rows rendered under the billboard, in order. */
  rows: ShowcaseRow[];
  /** Card click (and billboard CTA) — the caller decides what opens. */
  onSelect?: (item: ShowcaseItem) => void;
  /** Rotation interval in ms. Defaults to 7000. */
  rotateMs?: number;
}

const HUES: Record<string, number> = {
  friday: 222,
  inference: 199,
  memora: 262,
  stratex: 152,
  futuris: 280,
  intelx: 190,
  forge: 24,
  sentinel: 210,
  cortex: 330,
  vyralx: 350,
};

function hueFor(name: string): number {
  const known = HUES[name.toLowerCase()];
  if (known !== undefined) return known;
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

function posterStyle(name: string): React.CSSProperties {
  const hue = hueFor(name);
  return {
    background: `linear-gradient(150deg, hsl(${hue} 70% 26%) 0%, hsl(${(hue + 40) % 360} 65% 12%) 78%)`,
  };
}

export function ShowcaseRows({
  featuredPool,
  featuredKicker = "Now answering",
  featuredCta = "Open",
  rows,
  onSelect,
  rotateMs = 7000,
}: ShowcaseRowsProps) {
  const [featuredIdx, setFeaturedIdx] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [tabHidden, setTabHidden] = useState(false);

  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    // Capability probe after mount, same pattern as the playbook.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReducedMotion(motion.matches);
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    motion.addEventListener("change", onChange);
    return () => motion.removeEventListener("change", onChange);
  }, []);

  /* Tab visibility is a live input alongside reduced motion: the
     rotation stops the moment the tab hides, and resumes on return. */
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTabHidden(document.hidden);
    const onVisibilityChange = () => setTabHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  /* The billboard rotates through the pool — slowly, never under
     reduced motion, never behind a hidden tab. The timer only
     exists while the tab is visible: hiding the tab tears it down,
     so no tick can fire while hidden; showing the tab starts a
     fresh phase from the same index. The document.hidden check
     inside the callback covers a tick already queued when
     visibility flips. */
  useEffect(() => {
    if (reducedMotion || tabHidden || featuredPool.length < 2) return;
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      setFeaturedIdx((idx) => (idx + 1) % featuredPool.length);
    }, rotateMs);
    return () => window.clearInterval(timer);
  }, [featuredPool, reducedMotion, rotateMs, tabHidden]);

  const featured: ShowcaseItem | undefined =
    featuredPool[featuredIdx % Math.max(featuredPool.length, 1)];

  const poolSize = featuredPool.length;

  return (
    <div className="showcase">
      {featured ? (
        <section
          className="showcase-billboard"
          style={posterStyle(featured.name)}
          key={featured.id}
        >
          <p className="showcase-billboard-kicker">{featuredKicker}</p>
          <h3 className="showcase-billboard-name">{featured.name}</h3>
          <p className="showcase-billboard-role">{featured.role}</p>
          <div className="showcase-billboard-meta">
            {featured.status && (
              <span className={`pill tone-${toneForStatus(featured.status)}`}>
                {featured.status}
              </span>
            )}
            {typeof featured.meta === "string" && featured.meta !== "" && (
              <span className="showcase-latency">{featured.meta}</span>
            )}
            {poolSize > 1 && (
              <span className="showcase-dots" role="tablist" aria-label="Featured item">
                {featuredPool.map((item, idx) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={idx === featuredIdx % poolSize}
                    aria-label={`Feature ${item.name}`}
                    className={`showcase-dot ${idx === featuredIdx % poolSize ? "is-on" : ""}`}
                    onClick={() => setFeaturedIdx(idx)}
                  />
                ))}
              </span>
            )}
          </div>
          {onSelect && (
            <button
              type="button"
              className="showcase-cta"
              onClick={() => onSelect(featured)}
            >
              {featuredCta}
            </button>
          )}
        </section>
      ) : (
        <p className="sheet-note">Nothing to feature right now.</p>
      )}

      {rows.map((row) => (
        <section className="showcase-row-block" key={row.title}>
          <h4 className="showcase-row-title">{row.title}</h4>
          {row.items.length > 0 ? (
            <div className="showcase-row">
              {row.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`showcase-card ${row.wide ? "is-wide" : ""}`}
                  onClick={() => onSelect?.(item)}
                  aria-label={item.name}
                >
                  {!row.wide && (
                    <span
                      className="showcase-poster"
                      style={posterStyle(item.name)}
                      aria-hidden="true"
                    >
                      {item.name.slice(0, 1)}
                    </span>
                  )}
                  <span className="showcase-card-name">{item.name}</span>
                  <span className="showcase-card-role">{item.role}</span>
                  <span className="showcase-card-meta">
                    {item.status && (
                      <span className={`pill tone-${toneForStatus(item.status)}`}>
                        {item.status}
                      </span>
                    )}
                    {item.flag && <span className="showcase-working">{item.flag}</span>}
                    {typeof item.meta === "string" && item.meta !== "" && (
                      <span className="showcase-latency">{item.meta}</span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="sheet-note">{row.emptyText}</p>
          )}
        </section>
      ))}
    </div>
  );
}

/** Convenience: map a fleet-style agent record onto a showcase item. */
export function useFeaturedPool<T extends { name: string; status?: string }>(
  items: readonly T[],
): T[] {
  return useMemo(() => {
    const online = items.filter(
      (a) => String(a.status ?? "").toLowerCase() === "online",
    );
    return online.length > 0 ? [...online] : [...items];
  }, [items]);
}
