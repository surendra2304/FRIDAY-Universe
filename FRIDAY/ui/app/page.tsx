"use client";

import { Activity, Clock3, LayoutGrid, Radio, TerminalSquare, Waypoints } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { EmptyState, OnboardingHint, OwnerPreferences, VoiceDiagnostics } from "@/components/batch8";
import { CountUp, Reveal } from "@/components/effects";
import { OrbState } from "@/components/OrbCore";
import { ActivityFeed, ConsoleStrip, FleetGrid, SystemPanel, TaskTimeline } from "@/components/panels";
import { VoiceCall } from "@/components/VoiceCall";
import {
  Agent,
  AgentsLiveSnapshot,
  AutonomySnapshot,
  FleetSnapshot,
  HostTelemetry,
  LiveActivityEvent,
  TaskTimelineSnapshot,
  apiBase,
  istTime,
  requestJson,
  statusTone,
} from "@/lib/api";

/* ============================================================
   FRIDAY Universe — "Minimal Console" (2026-11-13, ZAI Agent 1).

   Owner directive after the Living Universe rounds: the site was
   laggy and busy — make it MINIMALISTIC and dynamic instead.
   This edition strips every decorative layer (aurora, canvas
   particles, floating orbs, scramble/split hero text) and keeps
   a single quiet motion budget: one-shot entrances, animated
   counters, live status pulses. Every pixel carries information.

   Kept owner directives:
   - no scroll-jump when starting voice (connects in place)
   - IST is the only clock
   - chat history and live calls survive tab switches (all
     sections stay mounted; hidden sections pause fetches)
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
  const [timeline, setTimeline] = useState<TaskTimelineSnapshot | null>(null);
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
    const [fleetResult, telemetryResult, autonomyResult, liveResult, timelineResult] = await Promise.allSettled([
      requestJson<FleetSnapshot>("/api/agents/status"),
      requestJson<HostTelemetry>("/api/system_telemetry"),
      requestJson<AutonomySnapshot>("/api/autonomous/status"),
      requestJson<AgentsLiveSnapshot>("/api/agents/live"),
      requestJson<TaskTimelineSnapshot>("/api/tasks/timeline?limit=50"),
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
    if (timelineResult.status === "fulfilled") setTimeline(timelineResult.value);
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
          const known = ["activity", "agent_action", "chat_command"];
          if (known.includes(String(data.type))) {
            const key = String(data.agent || data.agents_involved || "friday").toLowerCase();
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

  /* Unified live count: an agent is live when it answers the probe. */
  const onlineCount = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
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
          <span className="splash-text">FRIDAY</span>
        </div>
      </main>
    );
  }

  return (
    <>
      <div className="ambient" aria-hidden="true" />

      <nav className="nav" aria-label="Main navigation">
        <a className="nav-logo" href="#top" aria-label="FRIDAY home">
          <span className="logo-dot" aria-hidden="true" />
          FRIDAY
        </a>
        <div className="tabs" role="tablist" aria-label="Sections">
          {TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              className={`tab${tab === id ? " active" : ""}`}
              onClick={() => setTab(id)}
            >
              {icon}
              <span>{label}</span>
            </button>
          ))}
        </div>
        <div className="nav-status">
          <span
            title="Agents answering live health probes right now"
            className={`dot ${
              connected === "online" && onlineCount > 0
                ? "good"
                : connected === "online"
                  ? "warn"
                  : connected === "offline"
                    ? "bad"
                    : "muted"
            } ${connected === "online" ? "pulse" : ""}`}
          />
          {connected === "online"
            ? onlineCount > 0
              ? <span className="nav-count">{`${onlineCount}/${totalAgents} agents live`}</span>
              : <span className="nav-count nav-alert" role="status">dashboard online · agents unreachable</span>
            : connected === "offline"
              ? <span className="nav-count">API offline</span>
              : <span className="nav-count">Connecting…</span>}
          <span className="nav-clock" title="Indian Standard Time">
            <Clock3 size={12} />
            {now ? `${istTime(now)} IST` : "--:-- IST"}
          </span>
        </div>
      </nav>

      <main className="shell" id="top" style={{ paddingTop: "calc(var(--nav-h) + 20px)" }}>
        {/* ============ CONSOLE — FRIDAY communication only ============ */}
        <section className={`tabview${tab === "console" ? " on" : ""}`} hidden={tab !== "console"} aria-label="FRIDAY console">
          <Reveal className="console-hero">
            <p className="hero-eyebrow">Sovereign operating system</p>
            <h1 className="hero-title">One voice moves the whole universe.</h1>
            <p className="hero-sub">
              Ten specialist agents, one continuous line. Speak or type — FRIDAY listens, remembers and dispatches in real time.
            </p>
            {/* Live stat band — animated counters on REAL fleet/ledger data,
                never decorative claims (values are omitted while loading). */}
            <div className="stat-band" role="status" aria-label="Live universe statistics">
              <div className="stat-cell">
                <span className="num">
                  {fleet ? (
                    <>
                      <CountUp value={onlineCount} /><span style={{ fontSize: 15, opacity: 0.7 }}>/{totalAgents}</span>
                    </>
                  ) : (
                    "··"
                  )}
                </span>
                <span className="lbl">Agents live</span>
              </div>
              <div className="stat-cell">
                <span className="num">{autonomy ? <CountUp value={autonomy.history_count ?? 0} /> : "··"}</span>
                <span className="lbl">Auto actions</span>
              </div>
              <div className="stat-cell">
                <span className="num">{timeline ? <CountUp value={timeline.total_records ?? 0} /> : "··"}</span>
                <span className="lbl">Tasks delegated</span>
              </div>
              <div className="stat-cell">
                <span className="num">{autonomy?.autonomous_mode ? "ON" : "STANDBY"}</span>
                <span className="lbl">Autonomy mode</span>
              </div>
            </div>
          </Reveal>
          <div className="console">
            <div className="console-left-wrap">
              <div className="console-left">
                <VoiceCall onStateChange={setVoiceState} orbitAgents={fleet?.agents} footer={<ConsoleStrip fleet={fleet} autonomy={autonomy} />} />
              </div>
            </div>
            <div className="console-main-wrap">
              <div className="console-main">
                <ChatPanel prefill={chatPrefill} />
              </div>
            </div>
          </div>
          <Reveal delay={80}>
            <OnboardingHint id="console-welcome">
              <strong>Welcome back, Boss.</strong> Talk or type — try <em>&quot;watch topic X&quot;</em> for briefings or{" "}
              <em>&quot;alert me when BTC &gt; 100k&quot;</em> for price alerts.
            </OnboardingHint>
            <OwnerPreferences />
          </Reveal>
        </section>

        {/* ============ FLEET — the ten-agent universe ============ */}
        <section className={`tabview${tab === "fleet" ? " on" : ""}`} hidden={tab !== "fleet"} aria-label="Agent fleet">
          <Reveal>
            <div className="eyebrow">Live fleet · real health probes</div>
            <h2 className="section-title">The ten-agent universe</h2>
            <p className="section-sub">
              FRIDAY coordinates; nine specialists report here. Every card answers a real health
              probe and shows its last piece of work and how fresh it is — ask anything and
              FRIDAY dispatches it.
            </p>
          </Reveal>
          <FleetGrid fleet={fleet} autonomy={autonomy} liveActivity={liveActivity} now={agentsLive} onAsk={askAgent} />
        </section>

        {/* ============ ACTIVITY — live operations ============ */}
        <section className={`tabview${tab === "activity" ? " on" : ""}`} hidden={tab !== "activity"} aria-label="Live activity">
          <Reveal>
            <div className="eyebrow">Live operations</div>
            <h2 className="section-title">What the fleet is doing right now</h2>
          </Reveal>
          <Reveal delay={60}>
            <ActivityFeed autonomy={autonomy} liveActivity={liveActivity} />
          </Reveal>
          <Reveal delay={120}>
            <div className="eyebrow" style={{ marginTop: 28 }}>
              Task timeline · every delegation, newest first
            </div>
            <TaskTimeline timeline={timeline} />
          </Reveal>
        </section>

        {/* ============ SYSTEM — server & autonomy ============ */}
        <section className={`tabview${tab === "system" ? " on" : ""}`} hidden={tab !== "system"} aria-label="System telemetry">
          <Reveal>
            <div className="eyebrow">System</div>
            <h2 className="section-title">Your Oracle servers, live</h2>
          </Reveal>
          <SystemPanel
            fleet={fleet}
            telemetry={telemetry}
            autonomy={autonomy}
            cpuHistory={cpuHistory}
            ramHistory={ramHistory}
          />
          <Reveal delay={100}>
            <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
              <VoiceDiagnostics />
              {timeline && Array.isArray(timeline.events) && timeline.events.length === 0 && (
                <EmptyState
                  icon={<Activity size={22} />}
                  title="No delegated tasks yet"
                  hint={'Assign work from the Fleet tab (or say "assign IntelX: research X") — every delegation lands here with its live status.'}
                />
              )}
            </div>
          </Reveal>
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
