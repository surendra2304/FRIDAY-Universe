"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Cpu, Gauge, Mic, Settings2, Wifi, Zap } from "lucide-react";
import {
  AutonomySnapshot,
  FleetSnapshot,
  HostTelemetry,
  requestJson,
  statusTone,
} from "@/lib/api";
import { Sparkline } from "./fx";

/* ============================================================
   Under the hood — the machinery, measured honestly.

   Server instruments read GET /api/system_telemetry; the crew
   count reads the same fleet snapshot as the Crew view; the
   voice card reports the LAST call's measured line quality
   from GET /api/voice/diagnostics — a call that never happened
   reads as "no call yet", never as invented good numbers; the
   settings form reads and writes /api/owner/preferences.
   ============================================================ */

export function Instruments({
  telemetry,
  fleet,
  autonomy,
  cpuHistory,
  ramHistory,
}: {
  telemetry: HostTelemetry | null;
  fleet: FleetSnapshot | null;
  autonomy: AutonomySnapshot | null;
  cpuHistory: number[];
  ramHistory: number[];
}) {
  const answering = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
  const total = fleet?.agent_count ?? fleet?.agents?.length ?? 0;
  const cpuOk = telemetry?.status === "ok" && typeof telemetry.cpu_percent === "number";
  const ramOk = telemetry?.status === "ok" && typeof telemetry.ram_percent === "number";

  return (
    <div className="instruments">
      <article className="gauge-card">
        <div className="gauge-head">
          <span className="gauge-label">
            <Cpu size={13} /> Processor · Server 1
          </span>
          <span className={`pill ${cpuOk ? "good" : "muted"}`}>{cpuOk ? "live" : "no reading"}</span>
        </div>
        <div className="gauge-value">{cpuOk ? `${Math.round(telemetry!.cpu_percent!)}%` : "—"}</div>
        <div className="gauge-foot">
          <span>
            {telemetry?.cpu_cores ?? "—"} cores · Oracle free tier
          </span>
          <Sparkline values={cpuHistory} color="#57e6ff" />
        </div>
      </article>

      <article className="gauge-card">
        <div className="gauge-head">
          <span className="gauge-label">
            <Gauge size={13} /> Memory · Server 1
          </span>
          <span className={`pill ${telemetry?.status === "ok" ? "good" : "muted"}`}>
            {telemetry?.status === "ok" ? "live" : "no reading"}
          </span>
        </div>
        <div className="gauge-value">{ramOk ? `${Math.round(telemetry!.ram_percent!)}%` : "—"}</div>
        <div className="gauge-foot">
          <span>
            {telemetry?.ram_used_gb ?? "—"} of {telemetry?.ram_total_gb ?? "—"} GB in use
          </span>
          <Sparkline values={ramHistory} color="#8ef4ff" />
        </div>
      </article>

      <article className="gauge-card">
        <div className="gauge-head">
          <span className="gauge-label">
            <Wifi size={13} /> Crew answering
          </span>
          <span className={`pill ${statusTone(fleet?.status)}`}>{fleet?.status ?? "unknown"}</span>
        </div>
        <div className="gauge-value">
          {answering}
          <small> / {total}</small>
        </div>
        <div className="gauge-foot">
          <span>agents returning a health reading right now</span>
        </div>
      </article>

      <article className="gauge-card">
        <div className="gauge-head">
          <span className="gauge-label">
            <Zap size={13} /> Acting on its own
          </span>
          <span className={`pill ${autonomy?.autonomous_mode ? "good" : "muted"}`}>
            {autonomy?.autonomous_mode ? "running" : "manual"}
          </span>
        </div>
        <div className="gauge-value">{autonomy?.history_count ?? 0}</div>
        <div className="gauge-foot">
          <span>autonomous actions on record</span>
          <span className="gauge-accent">{autonomy?.active_agent ? `busy: ${autonomy.active_agent}` : "standing by"}</span>
        </div>
      </article>
    </div>
  );
}

/* ---------------- voice line diagnostics ---------------- */

export interface VoiceDiagnosticsData {
  last_session: {
    session_id: string;
    started_at: string;
    ended_at: string;
    duration_sec: number;
    rtt_ms: number | null;
    packet_loss_pct: number | null;
    reconnect_count: number;
    quality: string;
  };
  configured: {
    voice_personality: string;
    accent_locale: string;
    notify_voice: boolean;
  };
  note?: string;
}

export function VoiceLineCard() {
  const [diag, setDiag] = useState<VoiceDiagnosticsData | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const d = await requestJson<VoiceDiagnosticsData>("/api/voice/diagnostics");
        if (!cancelled) setDiag(d);
      } catch {
        /* honest: keep the last reading rather than blanking it */
      }
    };
    void poll();
    const id = setInterval(poll, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const s = diag?.last_session;
  const hasSession = !!(s && s.session_id);
  const rtt = s?.rtt_ms;
  const loss = s?.packet_loss_pct;
  const qualityLabel = !hasSession || !s?.quality ? "no call yet" : s.quality.replace(/[-_]/g, " ");

  return (
    <article className="voice-card" aria-label="Voice line diagnostics">
      <div className="gauge-head">
        <span className="gauge-label">
          <Mic size={13} /> Your last call, measured
        </span>
        <span className={`pill ${qualityLabel === "good" ? "good" : "muted"}`}>{qualityLabel}</span>
      </div>
      <div className="voice-grid">
        <div className="voice-metric">
          <span className="k">Round trip</span>
          <strong className={`v${rtt == null ? " muted" : ""}`}>{rtt == null ? "—" : `${Math.round(rtt)} ms`}</strong>
        </div>
        <div className="voice-metric">
          <span className="k">Sound lost</span>
          <strong className={`v${loss == null ? " muted" : ""}`}>{loss == null ? "—" : `${loss.toFixed(1)}%`}</strong>
        </div>
        <div className="voice-metric">
          <span className="k">Reconnected</span>
          <strong className={`v${!hasSession ? " muted" : ""}`}>{hasSession ? s!.reconnect_count : "—"}</strong>
        </div>
        <div className="voice-metric">
          <span className="k">Went on for</span>
          <strong className={`v${!hasSession ? " muted" : ""}`}>{hasSession ? `${Math.round(s!.duration_sec)}s` : "—"}</strong>
        </div>
        <div className="voice-metric">
          <span className="k">Personality</span>
          <strong className="v muted">{diag?.configured.voice_personality ?? "—"}</strong>
        </div>
        <div className="voice-metric">
          <span className="k">Listening accent</span>
          <strong className="v muted">{diag?.configured.accent_locale ?? "—"}</strong>
        </div>
      </div>
      {!hasSession && (
        <p className="voice-none">No call on record yet — these stay blank until the first one ends. Nothing here is estimated.</p>
      )}
    </article>
  );
}

/* ---------------- owner settings ---------------- */

export interface OwnerPreferencesData {
  owner_id: string;
  name: string;
  timezone: string;
  briefing_time: string;
  notify_telegram: boolean;
  notify_voice: boolean;
  voice_personality: string;
  accent_locale: string;
}

export function OwnerSettings() {
  const [prefs, setPrefs] = useState<OwnerPreferencesData | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPrefs(await requestJson<OwnerPreferencesData>("/api/owner/preferences"));
      setError(null);
    } catch (e) {
      setError(`Couldn't load your settings: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onField = (key: keyof OwnerPreferencesData, value: string | boolean) => {
    setPrefs((p) => (p ? { ...p, [key]: value } : p));
    setSaved(false);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prefs) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await requestJson<OwnerPreferencesData>("/api/owner/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: prefs.name,
          timezone: prefs.timezone,
          briefing_time: prefs.briefing_time,
          notify_telegram: prefs.notify_telegram,
          notify_voice: prefs.notify_voice,
          voice_personality: prefs.voice_personality,
          accent_locale: prefs.accent_locale,
        }),
      });
      setPrefs(updated);
      setSaved(true);
    } catch (err) {
      setError(`Couldn't save: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  if (error && !prefs) {
    return (
      <div className="blank">
        <AlertTriangle size={26} />
        <p className="blank-title">Settings unavailable</p>
        <p>{error}</p>
      </div>
    );
  }
  if (!prefs) {
    return (
      <div className="blank">
        <Settings2 size={26} />
        <p>Reading your settings…</p>
      </div>
    );
  }

  return (
    <section className="settings" aria-label="Your settings">
      <form className="settings-form" onSubmit={onSubmit}>
        <label>
          Your name, as FRIDAY should use it
          <input type="text" value={prefs.name} onChange={(e) => onField("name", e.target.value)} aria-label="Your name" maxLength={32} />
        </label>
        <label>
          Timezone
          <input
            type="text"
            value={prefs.timezone}
            onChange={(e) => onField("timezone", e.target.value)}
            aria-label="Timezone (IANA)"
            placeholder="Asia/Kolkata"
          />
        </label>
        <label>
          Morning briefing at (IST)
          <input type="time" value={prefs.briefing_time} onChange={(e) => onField("briefing_time", e.target.value)} aria-label="Briefing time" />
        </label>
        <label>
          Voice personality
          <input
            type="text"
            value={prefs.voice_personality}
            onChange={(e) => onField("voice_personality", e.target.value)}
            aria-label="Voice personality"
            placeholder="assistant"
          />
        </label>
        <label>
          Accent FRIDAY listens for
          <input
            type="text"
            value={prefs.accent_locale}
            onChange={(e) => onField("accent_locale", e.target.value)}
            aria-label="Accent locale"
            placeholder="en-IN"
          />
        </label>
        <label className="check-row">
          <input type="checkbox" checked={prefs.notify_telegram} onChange={(e) => onField("notify_telegram", e.target.checked)} aria-label="Notify on Telegram" />
          Reach me on Telegram
        </label>
        <label className="check-row">
          <input type="checkbox" checked={prefs.notify_voice} onChange={(e) => onField("notify_voice", e.target.checked)} aria-label="Notify by voice" />
          Reach me by voice (minutes are limited)
        </label>
        <button type="submit" className="save-btn" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
        {saved && <span className="saved-note">Saved.</span>}
        {error && <span className="saved-note bad">{error}</span>}
      </form>
    </section>
  );
}
