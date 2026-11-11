"use client";

import { Clock3, Globe2, LayoutGrid, Radio, TerminalSquare, Waypoints } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { AuroraBackground, CountUp, FloatingOrbs, Magnetic, Orbital, Parallax, ParticleField, Reveal, ScrambleText } from "@/components/effects";
import { OrbState } from "@/components/OrbCore";
import { ActivityFeed, ConsoleStrip, FleetGrid, SystemPanel } from "@/components/panels";
import { VoiceCall } from "@/components/VoiceCall";
import {
  Agent,
  AgentsLiveSnapshot,
  AutonomySnapshot,
  FleetSnapshot,
  HostTelemetry,
  LiveActivityEvent,
  apiBase,
  istTime,
  requestJson,
} from "@/lib/api";

/* ============================================================
   FRIDAY Universe — sectioned command center.

   Owner directives honored here (2026-11-11 IST):
   - The Dashboard (Console) is FRIDAY communication ONLY — voice
     and chat side by side, fits the viewport, nothing scrolls.
   - Fleet / Activity / System live in their own sections.
   - No scroll-jump when starting voice (it connects in place).
   - IST is the only clock shown.
   - Chat history and any live call survive tab switches (all
     sections stay mounted; hidden sections pause their fetches).
   ============================================================ */

type Tab = "console" | "fleet" | "activity" | "system";

const TABS: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
  { id: "console", label: "Console", icon: <Radio size={14} /> },
  { id: "fleet", label: "Fleet", icon: <LayoutGrid size={14} /> },
  { id: "activity", label: "Activity", icon: <Waypoints size={14} /> },
  { id: "system", label: "System", icon: <TerminalSquare size={14} /> },
];

export default function Page() {
  const [mounted, setMounted] = useState(false);
  const [tab, setTab] = useState<Tab>("console");
  const [now, setNow] = useState<Date | null>(null);
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [agentsLive, setAgentsLive] = useState<AgentsLiveSnapshot | null>(null);
  const [telemetry, setTelemetry] = useState<HostTelemetry | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomySnapshot | null>(null);
  const [liveActivity, setLiveActivity] = useState<Record<string, LiveActivityEvent>>({});
  const [connected, setConnected] = useState<"checking" | "online" | "offline">("checking");
  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [ramHistory, setRamHistory] = useState<number[]>([]);
  const [voiceState, setVoiceState] = useState<OrbState>("idle");
  const [chatPrefill, setChatPrefill] = useState<{ text: string; seq: number }>({ text: "", seq: 0 });

  useEffect(() => {
    setMounted(true);
    setNow(new Date());
    const clock = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(clock);
  }, []);

  const refresh = useCallback(async () => {
    const [fleetResult, telemetryResult, autonomyResult, liveResult] = await Promise.allSettled([
      requestJson<FleetSnapshot>("/api/agents/status"),
      requestJson<HostTelemetry>("/api/system_telemetry"),
      requestJson<AutonomySnapshot>("/api/autonomous/status"),
      requestJson<AgentsLiveSnapshot>("/api/agents/live"),
    ]);
    if (fleetResult.status === "fulfilled") {
      setFleet(fleetResult.value);
      setConnected("online");
    } else {
      setConnected("offline");
    }
    if (telemetryResult.status === "fulfilled") {
      const data = telemetryResult.value;
      setTelemetry(data);
      if (data.status === "ok" && typeof data.cpu_percent === "number") {
        setCpuHistory((current) => [...current, data.cpu_percent!].slice(-40));
      }
      if (data.status === "ok" && typeof data.ram_percent === "number") {
        setRamHistory((current) => [...current, data.ram_percent!].slice(-40));
      }
    } else {
      setTelemetry(null);
    }
    if (autonomyResult.status === "fulfilled") setAutonomy(autonomyResult.value);
    if (liveResult.status === "fulfilled") setAgentsLive(liveResult.value);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [mounted, refresh]);

  /* live agent activity over the keyless origin-gated WebSocket; polling
     above keeps everything fresh if the socket is unavailable. */
  useEffect(() => {
    if (!mounted) return;
    let socket: WebSocket | null = null;
    let retry: number | null = null;
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      try {
        socket = new WebSocket(`${apiBase().replace(/^http/, "ws")}/api/ws/activity`);
      } catch {
        return;
      }
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(String(event.data)) as LiveActivityEvent;
          if (data.type === "activity" && data.agent) {
            const key = String(data.agent).toLowerCase();
            setLiveActivity((current) => ({ ...current, [key]: data }));
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (!cancelled && retry === null) {
          retry = window.setTimeout(() => {
            retry = null;
            connect();
          }, 10_000);
        }
      };
      socket.onerror = () => {
        try { socket?.close(); } catch { /* ignore */ }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (retry !== null) window.clearTimeout(retry);
      try { socket?.close(); } catch { /* ignore */ }
    };
  }, [mounted]);

  const onlineCount = fleet?.agents?.filter((a) => a.status?.toUpperCase() === "ONLINE").length ?? 0;
  const totalAgents = fleet?.agent_count ?? fleet?.agents?.length ?? 10;

  function askAgent(agent: Agent) {
    setChatPrefill({ text: `@${agent.name} `, seq: chatPrefill.seq + 1 });
    setTab("console");
  }

  if (!mounted) {
    return (
      <main className="splash" role="status" aria-label="Loading FRIDAY">
        <div className="splash-inner">
          <div className="splash-ring" />
          <span className="splash-text">
            <ScrambleText text="FRIDAY" speed={60} />
          </span>
        </div>
      </main>
    );
  }

  return (
    <>
      <AuroraBackground />
      <ParticleField />
      <FloatingOrbs />

      <nav className="nav" aria-label="Main navigation">
        <a className="nav-logo" href="#top" aria-label="FRIDAY home">
          <span className="logo-dot" aria-hidden="true" />
          <ScrambleText text="FRIDAY" />
        </a>
        <div className="tabs" role="tablist" aria-label="Sections">
          {TABS.map(({ id, label, icon }) => (
            <Magnetic key={id}>
              <button
                role="tab"
                aria-selected={tab === id}
                className={`tab${tab === id ? " active" : ""}`}
                onClick={() => setTab(id)}
              >
                {icon}
                <span>{label}</span>
              </button>
            </Magnetic>
          ))}
        </div>
        <div className="nav-status">
          <span className={`dot ${connected === "online" ? "good" : connected === "offline" ? "bad" : "muted"} ${connected === "online" ? "pulse" : ""}`} />
          {connected === "online" ? `${onlineCount}/${totalAgents} live` : connected === "offline" ? "API offline" : "Connecting…"}
          <span className="nav-clock" title="Indian Standard Time">
            <Clock3 size={12} />
            {now ? `${istTime(now)} IST` : "--:-- IST"}
          </span>
        </div>
      </nav>

      <main className="shell" id="top" style={{ paddingTop: "var(--nav-h)" }}>
        {/* ============ CONSOLE — FRIDAY communication only ============ */}
        <section className={`tabview${tab === "console" ? " on" : ""}`} hidden={tab !== "console"} aria-label="FRIDAY console">
          <div className="console">
            <Parallax depth={6} className="console-left-wrap">
              <div className="console-left">
                <Orbital className="console-orbital" count={9} radius={128} duration={46} />
                <VoiceCall onStateChange={setVoiceState} footer={<ConsoleStrip fleet={fleet} autonomy={autonomy} />} />
              </div>
            </Parallax>
            <Parallax depth={2} className="console-main-wrap">
              <div className="console-main">
                <ChatPanel prefill={chatPrefill} />
              </div>
            </Parallax>
          </div>
        </section>

        {/* ============ FLEET — the ten-agent universe ============ */}
        <section className={`tabview${tab === "fleet" ? " on" : ""}`} hidden={tab !== "fleet"} aria-label="Agent fleet">
          <Reveal>
            <div className="eyebrow">
              <Globe2 size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
              Live fleet · what every agent is doing
            </div>
            <h2 className="section-title">
              The <span className="grad-text">ten-agent</span> universe
            </h2>
            <p className="section-sub">
              Every agent answers a real health probe. Cards show each agent&apos;s last piece of work and how fresh it is —
              assign or ask anything and FRIDAY dispatches it.
            </p>
          </Reveal>
          <FleetGrid fleet={fleet} autonomy={autonomy} liveActivity={liveActivity} now={agentsLive} onAsk={askAgent} />
        </section>

        {/* ============ ACTIVITY — live operations ============ */}
        <section className={`tabview${tab === "activity" ? " on" : ""}`} hidden={tab !== "activity"} aria-label="Live activity">
          <Reveal>
            <div className="eyebrow">Live operations</div>
            <h2 className="section-title">
              What the fleet is <span className="grad-text">doing</span> right now
            </h2>
          </Reveal>
          <Reveal delay={80}>
            <ActivityFeed autonomy={autonomy} liveActivity={liveActivity} />
          </Reveal>
        </section>

        {/* ============ SYSTEM — server & autonomy ============ */}
        <section className={`tabview${tab === "system" ? " on" : ""}`} hidden={tab !== "system"} aria-label="System telemetry">
          <Reveal>
            <div className="eyebrow">System</div>
            <h2 className="section-title">
              Your Oracle <span className="grad-text">servers</span>, live
            </h2>
          </Reveal>
          <SystemPanel
            fleet={fleet}
            telemetry={telemetry}
            autonomy={autonomy}
            cpuHistory={cpuHistory}
            ramHistory={ramHistory}
          />
        </section>

        <footer className="footer">
          <span>
            <strong>FRIDAY Universe</strong> — built for Surendra
          </span>
          <span>Oracle Always Free · GitHub Actions · LiveKit · IST everywhere</span>
        </footer>
      </main>
    </>
  );
}
