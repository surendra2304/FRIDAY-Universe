"use client";

import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  Database,
  Eye,
  Globe2,
  HardDrive,
  Layers,
  LineChart,
  MessageSquareText,
  Network,
  ShieldCheck,
  Terminal,
  TrendingUp,
} from "lucide-react";
import {
  Agent,
  AgentsLiveSnapshot,
  AutonomySnapshot,
  FleetSnapshot,
  LiveActivityEvent,
  cleanDirective,
  freshness,
  statusTone,
} from "@/lib/api";

/* ============================================================
   The Crew — the nine specialists behind FRIDAY, one tile each.

   Every tile is a live probe, not a poster: reachability and
   latency come from the fleet snapshot, "working on" from the
   unified task ledger, and "last finished" from the live
   activity socket with the autonomy ledger as its fallback.
   Freshness is always printed next to the claim, so a stale
   reading can never dress itself up as live work.

   Boilerplate stripping is kept from the old console: raw
   "owner-approved task" wrappers never reach the screen — the
   human intent does (cleanDirective).
   ============================================================ */

const CREW_ORDER = ["stratex", "inference", "cortex", "forge", "intelx", "vyralx", "memora", "futuris", "sentinel"] as const;

const CREW_ICONS: Record<string, React.ReactNode> = {
  stratex: <TrendingUp size={17} />,
  inference: <Network size={17} />,
  cortex: <Database size={17} />,
  forge: <Terminal size={17} />,
  intelx: <Eye size={17} />,
  vyralx: <Layers size={17} />,
  memora: <HardDrive size={17} />,
  futuris: <LineChart size={17} />,
  sentinel: <ShieldCheck size={17} />,
};

const CREW_CRAFT: Record<string, string> = {
  stratex: "Trading & portfolios",
  inference: "The model gateway",
  cortex: "Web & client operations",
  forge: "Builds the software",
  intelx: "Research & threat watch",
  vyralx: "Video & content",
  memora: "Long-term memory",
  futuris: "Forecasts & scenarios",
  sentinel: "Security watch",
};

function CrewSkeleton() {
  return (
    <div className="crew-grid" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div className="tile skel" key={i} style={{ animationDelay: `${i * 90}ms` }}>
          <div className="skel-line w40" />
          <div className="skel-line w70" />
          <div className="skel-line w55" />
          <div className="skel-line w80" />
        </div>
      ))}
    </div>
  );
}

export function Crew({
  fleet,
  autonomy,
  liveActivity,
  now,
  onAsk,
}: {
  fleet: FleetSnapshot | null;
  autonomy: AutonomySnapshot | null;
  liveActivity: Record<string, LiveActivityEvent>;
  now?: AgentsLiveSnapshot | null;
  onAsk: (agent: Agent) => void;
}) {
  const agents = fleet?.agents ?? [];
  const nowById = new Map((now?.agents ?? []).map((a) => [a.id, a] as const));
  const sorted = [...agents].sort((a, b) => {
    const ai = CREW_ORDER.indexOf(a.id as (typeof CREW_ORDER)[number]);
    const bi = CREW_ORDER.indexOf(b.id as (typeof CREW_ORDER)[number]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  if (!fleet) return <CrewSkeleton />;

  if (sorted.length === 0) {
    return (
      <div className="blank">
        <Globe2 size={22} />
        <p>Nobody has reported in yet. The probe runs again every 30 seconds.</p>
      </div>
    );
  }

  return (
    <div className="crew-grid">
      {sorted.map((agent) => {
        const live = liveActivity[agent.id];
        const ledger = nowById.get(agent.id);
        const working = ledger?.in_flight
          ? {
              task_id: ledger.in_flight.task_id,
              description: cleanDirective(ledger.in_flight.description, 120),
              status: ledger.in_flight.status,
              at: ledger.in_flight.since,
            }
          : null;
        const record = live
          ? {
              directive: cleanDirective(live.directive || `${live.action ?? "activity"} ${live.target ?? ""}`.trim()),
              result: cleanDirective(live.result, 120),
              success: Boolean(live.success),
              at: live.timestamp,
            }
          : (() => {
              const a = autonomy?.agent_activity?.[agent.id];
              if (!a) return null;
              return {
                directive: cleanDirective(a.directive),
                result: cleanDirective(a.result, 120),
                success: Boolean(a.success),
                at: a.recorded_at ?? a.timestamp,
              };
            })();
        const isActive = autonomy?.active_agent?.toLowerCase() === agent.id || Boolean(working);
        const tone = statusTone(agent.status);
        return (
          <article key={agent.id} className={`tile tone-${tone}${isActive ? " active" : ""}`}>
            <div className="tile-top">
              <span className={`tile-badge tone-${tone}`}>{CREW_ICONS[agent.id] ?? <Database size={17} />}</span>
              <span className={`pill ${tone}`}>{agent.status.toLowerCase()}</span>
            </div>
            <h3 className="tile-name">
              {agent.name}
              {isActive && <span className="dot good pulse" aria-label="working now" />}
            </h3>
            <p className="tile-craft">{CREW_CRAFT[agent.id] ?? agent.role ?? "Specialist"}</p>
            <p className="tile-meta">
              <span>{typeof agent.latency_ms === "number" ? `${Math.round(agent.latency_ms)} ms away` : "latency unknown"}</span>
              <span>
                {working
                  ? `on it for ${freshness(working.at) || working.status}`
                  : record?.at
                    ? freshness(record.at)
                      ? `last moved ${freshness(record.at)} ago`
                      : "moved just now"
                    : `probed ${freshness(agent.last_checked) || "just now"}`}
              </span>
            </p>
            {working && (
              <p className="tile-work now">
                <strong>Working on:</strong> {working.description}
                <span className="work-bar" aria-hidden="true" />
              </p>
            )}
            <p className="tile-work">
              {record?.directive ? (
                <>
                  <strong>Last finished:</strong> {record.directive}
                </>
              ) : working ? (
                <>
                  {working.task_id} — {working.status}
                </>
              ) : (
                <>Standing by for your word.</>
              )}
            </p>
            {record?.result && (
              <p className={`tile-result ${record.success ? "good" : "bad"}`}>
                {record.success ? (
                  <CheckCircle2 size={13} aria-hidden="true" />
                ) : (
                  <Activity size={13} aria-hidden="true" />
                )}
                <span>{record.result}</span>
              </p>
            )}
            <div className="tile-actions">
              <button type="button" className="ghost-btn" onClick={() => onAsk(agent)}>
                <MessageSquareText size={13} /> Direct a task
              </button>
              <a
                className="ghost-btn"
                href={`https://friday-universe.duckdns.org/${agent.id}`}
                target="_blank"
                rel="noreferrer"
              >
                Its own console <ArrowUpRight size={12} />
              </a>
            </div>
          </article>
        );
      })}
    </div>
  );
}
