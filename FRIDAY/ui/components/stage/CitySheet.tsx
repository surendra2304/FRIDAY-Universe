"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchFleet,
  fetchLive,
  oneLine,
  toneFor,
  type AgentsLiveSnapshot,
  type FleetSnapshot,
} from "@/lib/wire";

/* ================================================================
   The City, summoned (TASK-IG-WEB-07).

   Source idea (IG reference corpus, Dc8xeYzoOLh): a
   city-metaphor structure — the site's sections as explorable
   places in a stylised city.

   Here the places are the crew: ten districts in a night
   skyline, one per agent, FRIDAY Plaza at the centre. The
   city is lit by real data — a district's windows glow warm
   when the fleet endpoint says its agent is online, a beacon
   burns while the live endpoint says it is working, and if
   neither answers the whole city renders dark and says so.
   No district is ever shown lit on invented data.

   Clicking a district flies the camera to it (a viewBox
   tween; instant under reduced motion) and opens its panel.
   The panel's button hands off to the real Fleet layer.
   ================================================================ */

type RoomKind = "fleet" | "chronicle" | "pulse";

interface District {
  id: string; // agent id, lowercase
  name: string;
  place: string;
  x: number;
  w: number;
  h: number;
  crown?: "orb" | "spire" | "dome" | "beacon" | "chimney";
}

const GROUND_Y = 430;
const VIEW_W = 760;
const VIEW_H = 470;

const DISTRICTS: District[] = [
  { id: "inference", name: "Inference", place: "The Gate", x: 18, w: 56, h: 120 },
  { id: "vyralx", name: "VyralX", place: "The Studios", x: 84, w: 60, h: 150 },
  { id: "memora", name: "Memora", place: "The Library", x: 154, w: 64, h: 172 },
  { id: "stratex", name: "Stratex", place: "The Heights", x: 228, w: 58, h: 212 },
  { id: "forge", name: "Forge", place: "The Works", x: 296, w: 62, h: 142, crown: "chimney" },
  { id: "friday", name: "FRIDAY", place: "The Plaza", x: 368, w: 78, h: 252, crown: "orb" },
  { id: "futuris", name: "Futuris", place: "The Spire", x: 456, w: 54, h: 232, crown: "spire" },
  { id: "intelx", name: "IntelX", place: "The Observatory", x: 520, w: 64, h: 162, crown: "dome" },
  { id: "cortex", name: "Cortex", place: "The Hall", x: 594, w: 62, h: 186 },
  { id: "sentinel", name: "Sentinel", place: "The Watchtower", x: 666, w: 58, h: 242, crown: "beacon" },
];

/* Deterministic per-building window pattern (same windows on
   every visit), lit count scaled by nothing but the seed —
   whether they glow at all is the fleet's say-so. */
function seeded(seedText: string): () => number {
  let h = 2166136261;
  for (let i = 0; i < seedText.length; i++) {
    h ^= seedText.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967295;
  };
}

function windowsFor(district: District): Array<{ x: number; y: number; lit: boolean }> {
  const rand = seeded(district.id);
  const cols = Math.max(3, Math.floor(district.w / 13));
  const rows = Math.max(4, Math.floor(district.h / 17));
  const windows: Array<{ x: number; y: number; lit: boolean }> = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      windows.push({
        x: district.x + 8 + c * ((district.w - 14) / Math.max(cols - 1, 1)),
        y: GROUND_Y - district.h + 14 + r * ((district.h - 26) / Math.max(rows - 1, 1)),
        lit: rand() > 0.42,
      });
    }
  }
  return windows;
}

type ViewBox = [number, number, number, number];
const FULL_VIEW: ViewBox = [0, 0, VIEW_W, VIEW_H];

export function CitySheet({ onSummon }: { onSummon: (kind: RoomKind) => void }) {
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [live, setLive] = useState<AgentsLiveSnapshot | null>(null);
  const [selected, setSelected] = useState<District | null>(null);
  const [view, setView] = useState<ViewBox>(FULL_VIEW);
  const [reducedMotion, setReducedMotion] = useState(false);
  const tweenRef = useRef(0);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let cancelled = false;
    (async () => {
      try {
        const snap = await fetchFleet();
        if (!cancelled) setFleet(snap);
      } catch {
        /* the city renders dark and says so */
      }
      try {
        const snap = await fetchLive();
        if (!cancelled) setLive(snap);
      } catch {
        /* beacons simply stay unlit */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const fleetById = useMemo(
    () => new Map((fleet?.agents ?? []).map((a) => [a.name.toLowerCase(), a])),
    [fleet],
  );
  const liveById = useMemo(
    () => new Map((live?.agents ?? []).map((a) => [a.id.toLowerCase(), a])),
    [live],
  );
  const windowsById = useMemo(() => new Map(DISTRICTS.map((d) => [d.id, windowsFor(d)])), []);

  const flyTo = useCallback(
    (target: ViewBox) => {
      window.cancelAnimationFrame(tweenRef.current);
      if (reducedMotion) {
        setView(target);
        return;
      }
      const from = view;
      const started = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - started) / 480);
        const eased = 1 - Math.pow(1 - t, 3);
        setView([
          from[0] + (target[0] - from[0]) * eased,
          from[1] + (target[1] - from[1]) * eased,
          from[2] + (target[2] - from[2]) * eased,
          from[3] + (target[3] - from[3]) * eased,
        ]);
        if (t < 1) tweenRef.current = window.requestAnimationFrame(step);
      };
      tweenRef.current = window.requestAnimationFrame(step);
    },
    [reducedMotion, view],
  );

  useEffect(() => () => window.cancelAnimationFrame(tweenRef.current), []);

  const visit = (district: District) => {
    setSelected(district);
    const cx = district.x + district.w / 2;
    const cy = GROUND_Y - district.h / 2;
    const w = 250;
    const h = w * (VIEW_H / VIEW_W);
    flyTo([
      Math.max(0, Math.min(VIEW_W - w, cx - w / 2)),
      Math.max(0, Math.min(VIEW_H - h, cy - h / 2)),
      w,
      h,
    ]);
  };

  const reset = () => {
    setSelected(null);
    flyTo(FULL_VIEW);
  };

  const selectedAgent = selected ? fleetById.get(selected.id) : undefined;
  const selectedLive = selected ? liveById.get(selected.id) : undefined;
  const onlineCount = fleet?.agents.filter((a) => a.status === "online").length;

  return (
    <div className="city">
      <p className="sheet-summary">
        {fleet ? (
          <>
            <b>{onlineCount ?? 0} of {fleet.agents.length}</b>&nbsp;districts are lit tonight
          </>
        ) : (
          "Asking the fleet which districts are lit…"
        )}
      </p>

      <div className="city-frame">
        <svg
          className="city-svg"
          viewBox={view.map((n) => n.toFixed(1)).join(" ")}
          role="img"
          aria-label="A night skyline of the ten agents as city districts"
        >
          <defs>
            <linearGradient id="city-sky" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#070b1d" />
              <stop offset="70%" stopColor="#0a0e1d" />
              <stop offset="100%" stopColor="#101736" />
            </linearGradient>
            <radialGradient id="city-orb" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#e9edfb" />
              <stop offset="45%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect x={-400} y={-200} width={VIEW_W + 800} height={VIEW_H + 400} fill="url(#city-sky)" />
          <circle cx={668} cy={52} r={13} fill="#e9edfb" opacity={0.75} />
          <circle cx={664} cy={49} r={11} fill="#0a0e1d" opacity={0.55} />

          {DISTRICTS.map((district) => {
            const agent = fleetById.get(district.id);
            const online = agent?.status === "online";
            const working = Boolean(liveById.get(district.id)?.in_flight);
            const top = GROUND_Y - district.h;
            const isSelected = selected?.id === district.id;
            return (
              <g
                key={district.id}
                className="city-district"
                onClick={() => visit(district)}
                role="button"
                aria-label={`Visit ${district.name}, ${district.place}`}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    visit(district);
                  }
                }}
              >
                {district.crown === "chimney" && (
                  <rect x={district.x + district.w - 18} y={top - 16} width={8} height={18} fill="#131a33" />
                )}
                {district.crown === "spire" && (
                  <polygon
                    points={`${district.x + district.w / 2},${top - 26} ${district.x + 8},${top + 2} ${district.x + district.w - 8},${top + 2}`}
                    fill="#131a33"
                  />
                )}
                {district.crown === "dome" && (
                  <path
                    d={`M ${district.x + 8} ${top + 2} A ${district.w / 2 - 8} ${district.w / 2 - 8} 0 0 1 ${district.x + district.w - 8} ${top + 2} Z`}
                    fill="#131a33"
                  />
                )}
                <rect
                  x={district.x}
                  y={top}
                  width={district.w}
                  height={district.h}
                  rx={3}
                  className={`city-building ${isSelected ? "is-selected" : ""}`}
                />
                {(windowsById.get(district.id) ?? []).map((win, idx) => (
                  <rect
                    key={idx}
                    x={win.x}
                    y={win.y}
                    width={5.5}
                    height={7.5}
                    rx={1}
                    fill={online && win.lit ? "#ffd9a0" : "#1c2547"}
                    opacity={online && win.lit ? 0.92 : 0.8}
                  />
                ))}
                {district.crown === "orb" && (
                  <>
                    <circle cx={district.x + district.w / 2} cy={top - 16} r={17} fill="url(#city-orb)" opacity={online ? 0.95 : 0.35} />
                    <circle cx={district.x + district.w / 2} cy={top - 16} r={5.5} fill="#e9edfb" opacity={online ? 1 : 0.4} />
                  </>
                )}
                {(district.crown === "beacon" || working) && (
                  <circle
                    cx={district.x + district.w / 2}
                    cy={top - (district.crown === "beacon" ? 10 : 6)}
                    r={3.4}
                    fill={working ? "#fbbf24" : online ? "#2fe6bd" : "#1c2547"}
                    className={working && !reducedMotion ? "city-beacon" : ""}
                  />
                )}
                <text x={district.x + district.w / 2} y={GROUND_Y + 18} className="city-label">
                  {district.name}
                </text>
                <text x={district.x + district.w / 2} y={GROUND_Y + 31} className="city-sublabel">
                  {district.place}
                </text>
              </g>
            );
          })}
          <rect x={-400} y={GROUND_Y + 36} width={VIEW_W + 800} height={3} fill="#1c2547" />
        </svg>
      </div>

      <div className="city-panel">
        {selected ? (
          <>
            <div className="city-panel-main">
              <p className="city-panel-place">
                {selected.place} · {selected.name}
              </p>
              {selectedAgent ? (
                <>
                  <p className="city-panel-role">{selectedAgent.role}</p>
                  <div className="city-panel-meta">
                    <span className={`pill tone-${toneFor(selectedAgent.status)}`}>{selectedAgent.status}</span>
                    {typeof selectedAgent.latency_ms === "number" && (
                      <span className="city-panel-latency">{selectedAgent.latency_ms} ms</span>
                    )}
                    {selectedLive?.in_flight ? (
                      <span className="city-panel-task">at work: {oneLine(selectedLive.in_flight.description, 90)}</span>
                    ) : selectedLive?.last_outcome ? (
                      <span className="city-panel-task">last: {oneLine(selectedLive.last_outcome.description, 90)}</span>
                    ) : null}
                  </div>
                </>
              ) : (
                <p className="city-panel-role">
                  {fleet ? "The fleet didn't list this district." : "The fleet hasn't answered yet."}
                </p>
              )}
            </div>
            <div className="city-panel-actions">
              <button type="button" className="city-btn" onClick={() => onSummon("fleet")}>
                Open in the Fleet
              </button>
              <button type="button" className="city-btn is-ghost" onClick={reset}>
                Whole city
              </button>
            </div>
          </>
        ) : (
          <p className="sheet-note city-hint">
            {fleet
              ? "Click a district to fly to it. Lit windows mean the agent is answering; an amber beacon means it is at work this minute."
              : "The fleet didn't answer, so the city is dark tonight — no district is shown lit on invented data. The districts are still visitable."}
          </p>
        )}
      </div>
    </div>
  );
}
