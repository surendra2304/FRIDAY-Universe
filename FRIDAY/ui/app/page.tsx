"use client";

import { AudioLines, Clock3, Globe2, Mic, MessageSquareText, Radio } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { AuroraBackground, CountUp, Magnetic, ParticleField, Reveal, ScrambleText } from "@/components/effects";
import { OrbCore, OrbState } from "@/components/OrbCore";
import { ActivityFeed, FleetGrid, TelemetryStrip } from "@/components/panels";
import { VoiceCall } from "@/components/VoiceCall";
import {
  Agent,
  AutonomySnapshot,
  FleetSnapshot,
  HostTelemetry,
  LiveActivityEvent,
  apiBase,
  requestJson,
  statusTone,
} from "@/lib/api";

const AGENT_NAMES = [
  "Stratex", "Inference", "Cortex", "Forge", "IntelX",
  "VyralX", "Memora", "Futuris", "Sentinel", "FRIDAY",
];

export default function Page() {
  const [mounted, setMounted] = useState(false);
  const [now, setNow] = useState<Date | null>(null);
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
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
    const clock = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(clock);
  }, []);

  const refresh = useCallback(async () => {
    const [fleetResult, telemetryResult, autonomyResult] = await Promise.allSettled([
      requestJson<FleetSnapshot>("/api/agents/status"),
      requestJson<HostTelemetry>("/api/system_telemetry"),
      requestJson<AutonomySnapshot>("/api/autonomous/status"),
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
  }, []);

  useEffect(() => {
    if (!mounted) return;
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [mounted, refresh]);

  /* live agent activity: try the WebSocket; it may be gated in production,
     in which case the 30-second polling above still keeps the feed fresh. */
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
        return; /* fall back to polling silently */
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

  const greeting = useMemo(() => {
    if (!now) return "Good evening";
    const h = now.getHours();
    if (h < 12) return "Good morning";
    if (h < 18) return "Good afternoon";
    return "Good evening";
  }, [now]);

  const onlineCount = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
  const totalAgents = fleet?.agent_count ?? fleet?.agents?.length ?? 10;

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function askAgent(agent: Agent) {
    setChatPrefill({ text: `@${agent.name} `, seq: chatPrefill.seq + 1 });
    requestAnimationFrame(() => scrollTo("chat"));
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

      <nav className="nav" aria-label="Main navigation">
        <a className="nav-logo" href="#top" aria-label="FRIDAY home">
          <span className="logo-mark"><AudioLines size={18} strokeWidth={2.2} /></span>
          <ScrambleText text="FRIDAY" />
        </a>
        <div className="nav-links">
          <button className="nav-link" onClick={() => scrollTo("voice")}>Voice</button>
          <button className="nav-link" onClick={() => scrollTo("chat")}>Chat</button>
          <button className="nav-link" onClick={() => scrollTo("fleet")}>Fleet</button>
          <button className="nav-link" onClick={() => scrollTo("telemetry")}>Telemetry</button>
          <button className="nav-link" onClick={() => scrollTo("activity")}>Activity</button>
        </div>
        <div className="nav-status">
          <span className={`dot ${connected === "online" ? "good" : connected === "offline" ? "bad" : "muted"} ${connected === "online" ? "pulse" : ""}`} />
          {connected === "online" ? `${onlineCount}/${totalAgents} agents live` : connected === "offline" ? "API offline" : "Connecting…"}
        </div>
      </nav>

      <main className="shell" id="top" style={{ paddingTop: "var(--nav-h)" }}>
        {/* ============ HERO ============ */}
        <section className="hero" aria-label="FRIDAY hero">
          <span className="hero-eyebrow">
            <span className="pulse-dot" aria-hidden="true" />
            FRIDAY Universe · Command Center
          </span>

          <div className="hero-orb">
            <OrbCore state={voiceState} showLabel={false} />
          </div>

          <h1 className="hero-title">
            <ScrambleText text="FRIDAY" speed={46} />
          </h1>
          <p className="hero-greeting">
            {greeting}, <span className="grad-text">Surendra</span>.
          </p>
          <p className="hero-tagline">
            Your personal Jarvis.
            <span className="sep">·</span>
            Ten agents, one voice.
            <span className="sep">·</span>
            Talk continuously — English or Telugu.
          </p>

          <div className="hero-cta">
            <Magnetic>
              <button className="btn btn-primary btn-lg" onClick={() => scrollTo("voice")}>
                <Mic size={17} /> Talk to FRIDAY
              </button>
            </Magnetic>
            <Magnetic>
              <button className="btn btn-ghost btn-lg" onClick={() => scrollTo("chat")}>
                <MessageSquareText size={16} /> Open chat
              </button>
            </Magnetic>
          </div>

          <div className="hero-stats">
            <span className="stat-pill">
              <Globe2 size={13} style={{ color: "var(--cyan)" }} />
              <strong><CountUp value={onlineCount} /></strong> / {totalAgents} agents online
            </span>
            <span className="stat-pill">
              <Radio size={13} style={{ color: "var(--mint)" }} />
              Voice line <strong className={voiceState === "idle" ? "tone-muted" : "tone-good"}>{voiceState}</strong>
            </span>
            <span className="stat-pill">
              <Clock3 size={13} style={{ color: "var(--violet)" }} />
              {now ? now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "--:--"}
            </span>
          </div>

          <div className="marquee" aria-hidden="true">
            <div className="marquee-track">
              {[0, 1].map((copy) => (
                <span className="marquee-item" key={copy}>
                  {AGENT_NAMES.map((name) => (
                    <span key={name} style={{ display: "inline-flex", alignItems: "center", gap: 54 }}>
                      {name} <i>·</i>
                    </span>
                  ))}
                </span>
              ))}
            </div>
          </div>

          <div className="scroll-hint" aria-hidden="true">
            <div className="mouse" />
            scroll
          </div>
        </section>

        {/* ============ VOICE ============ */}
        <section className="section" id="voice" aria-label="Voice call with FRIDAY">
          <Reveal>
            <div className="eyebrow">Continuous voice</div>
            <h2 className="section-title">
              Talk like you&apos;re on the <span className="grad-text">phone</span>
            </h2>
            <p className="section-sub">
              One tap opens a live audio line. No press-to-talk, no search box — a real conversation.
            </p>
          </Reveal>
          <Reveal delay={90}>
            <VoiceCall onStateChange={setVoiceState} />
          </Reveal>
        </section>

        {/* ============ CHAT ============ */}
        <section className="section" id="chat-section" aria-label="Chat with FRIDAY">
          <Reveal>
            <div className="eyebrow">Command channel</div>
            <h2 className="section-title">
              Or just <span className="grad-text">type</span> to FRIDAY
            </h2>
            <p className="section-sub">
              The same brain as voice. FRIDAY can answer, remember, and dispatch real work to any agent.
            </p>
          </Reveal>
          <Reveal delay={90}>
            <ChatPanel prefill={chatPrefill} />
          </Reveal>
        </section>

        {/* ============ FLEET ============ */}
        <section className="section" id="fleet" aria-label="Agent fleet">
          <Reveal>
            <div className="eyebrow">Live fleet</div>
            <h2 className="section-title">
              The <span className="grad-text">ten-agent</span> universe
            </h2>
            <p className="section-sub">
              Every agent answers a real health probe. Click a card to route a chat to that agent.
            </p>
          </Reveal>
          <FleetGrid fleet={fleet} autonomy={autonomy} liveActivity={liveActivity} onAsk={askAgent} />
        </section>

        {/* ============ TELEMETRY ============ */}
        <section className="section" id="telemetry" aria-label="Host telemetry">
          <Reveal>
            <div className="eyebrow">Host telemetry</div>
            <h2 className="section-title">
              Your Oracle <span className="grad-text">server</span>, live
            </h2>
          </Reveal>
          <TelemetryStrip
            fleet={fleet}
            telemetry={telemetry}
            autonomy={autonomy}
            cpuHistory={cpuHistory}
            ramHistory={ramHistory}
          />
        </section>

        {/* ============ ACTIVITY ============ */}
        <section className="section" id="activity" aria-label="Live activity">
          <Reveal>
            <div className="eyebrow">Live activity</div>
            <h2 className="section-title">
              What the fleet is <span className="grad-text">doing</span>
            </h2>
          </Reveal>
          <Reveal delay={80}>
            <ActivityFeed autonomy={autonomy} liveActivity={liveActivity} />
          </Reveal>
        </section>

        <footer className="footer">
          <span>
            <strong>FRIDAY Universe</strong> — built for Surendra
          </span>
          <span>
            Oracle Always Free · GitHub Actions · LiveKit Cloud · Gemini Live
          </span>
        </footer>
      </main>
    </>
  );
}
