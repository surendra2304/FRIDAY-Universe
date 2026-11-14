"use client";

/**
 * Batch 8 (ZAI Agent 2) — D17 owner preferences, E7 voice diagnostics,
 * D18 empty states. These three small components are imported by the
 * panels module and rendered in the Console + System tabs.
 *
 * D17 OwnerPreferences: GET/POST /api/owner/preferences — name, timezone,
 *   briefing time, notification channels, voice personality, accent locale.
 * E7 VoiceDiagnostics: GET /api/voice/diagnostics — last session RTT,
 *   packet loss, reconnect count, configured voice/accent.
 * D18 EmptyState: the shared "no data yet" surface — honest, never "loading..."
 *   forever; shows a hint + an action when there is one.
 *
 * Sovereign Aurora edition (2026-11-14, frontend rebuild): the
 * diagnostics metrics now emit the .k/.v spans the stylesheet was
 * written for (the old markup rendered bare text + <strong>, so the
 * metric grid never styled as designed), and the preferences error
 * state uses a Lucide icon instead of an emoji glyph. All data
 * wiring below is unchanged.
 *
 * Reactor Deck edition (2026-11-14, rebuild #2): markup and data
 * wiring unchanged again — the deck stylesheet restyles these
 * surfaces as machine-room instruments and the Control section.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Mic, Settings2, Activity, Inbox } from "lucide-react";
import { apiBase, requestJson } from "@/lib/api";

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

export async function fetchOwnerPreferences(): Promise<OwnerPreferencesData> {
  return requestJson<OwnerPreferencesData>("/api/owner/preferences");
}

export async function updateOwnerPreferences(partial: Partial<OwnerPreferencesData>): Promise<OwnerPreferencesData> {
  return requestJson<OwnerPreferencesData>("/api/owner/preferences", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(partial),
  });
}

/** D17: owner preferences form, embedded in the Console tab. */
export function OwnerPreferences() {
  const [prefs, setPrefs] = useState<OwnerPreferencesData | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPrefs(await fetchOwnerPreferences());
      setError(null);
    } catch (e) {
      setError(`Could not load preferences: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    load();
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
      const updated = await updateOwnerPreferences({
        name: prefs.name,
        timezone: prefs.timezone,
        briefing_time: prefs.briefing_time,
        notify_telegram: prefs.notify_telegram,
        notify_voice: prefs.notify_voice,
        voice_personality: prefs.voice_personality,
        accent_locale: prefs.accent_locale,
      });
      setPrefs(updated);
      setSaved(true);
    } catch (e) {
      setError(`Could not save: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  if (error && !prefs) {
    return (
      <div className="empty-state">
        <AlertTriangle size={28} className="empty-state-icon" />
        <span className="empty-state-title">Preferences unavailable</span>
        <span className="empty-state-hint">{error}</span>
      </div>
    );
  }
  if (!prefs) {
    return (
      <div className="empty-state">
        <Settings2 size={28} className="empty-state-icon" />
        <span className="empty-state-title">Loading preferences…</span>
      </div>
    );
  }

  return (
    <section className="owner-prefs-section" aria-label="Owner preferences">
      <h3>
        <Settings2 size={14} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} />
        Owner preferences
      </h3>
      <form className="owner-prefs-form" onSubmit={onSubmit}>
        <label>
          Name (how FRIDAY addresses you)
          <input type="text" value={prefs.name} onChange={(e) => onField("name", e.target.value)} aria-label="Owner name" maxLength={32} />
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
          Daily briefing time (IST)
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
          Accent locale (STT hint)
          <input
            type="text"
            value={prefs.accent_locale}
            onChange={(e) => onField("accent_locale", e.target.value)}
            aria-label="Accent locale"
            placeholder="en-IN"
          />
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={prefs.notify_telegram} onChange={(e) => onField("notify_telegram", e.target.checked)} aria-label="Notify on Telegram" />
          Notify on Telegram
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={prefs.notify_voice} onChange={(e) => onField("notify_voice", e.target.checked)} aria-label="Notify by voice" />
          Notify by voice (limited minutes — see E8)
        </label>
        <button type="submit" className="owner-prefs-save" disabled={saving}>
          {saving ? "Saving…" : "Save preferences"}
        </button>
        {saved && <span className="owner-prefs-saved">✓ Saved.</span>}
        {error && (
          <span className="owner-prefs-saved" style={{ color: "var(--red)" }}>
            {error}
          </span>
        )}
      </form>
    </section>
  );
}

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

/** E7: voice session diagnostics card, embedded in the System tab. */
export function VoiceDiagnostics() {
  const [diag, setDiag] = useState<VoiceDiagnosticsData | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const d = await requestJson<VoiceDiagnosticsData>("/api/voice/diagnostics");
        if (!cancelled) setDiag(d);
      } catch {
        /* honest: leave the last reading in place */
      }
    };
    poll();
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
  const qualityLabel = !hasSession || !s?.quality ? "no session yet" : s.quality.replace(/[-_]/g, " ");

  return (
    <article className="voice-diag-card" aria-label="Voice session diagnostics">
      <div className="stat-label">
        <span>
          <Mic size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} />
          Voice session (last)
        </span>
        <span className={`status-pill ${qualityLabel === "good" ? "good" : "muted"}`}>{qualityLabel}</span>
      </div>
      <div className="voice-diag-grid">
        <div className="voice-diag-metric">
          <span className="k">RTT</span>
          <strong className={`v${rtt == null ? " muted" : ""}`}>{rtt == null ? "—" : `${Math.round(rtt)} ms`}</strong>
        </div>
        <div className="voice-diag-metric">
          <span className="k">Packet loss</span>
          <strong className={`v${loss == null ? " muted" : ""}`}>{loss == null ? "—" : `${loss.toFixed(1)}%`}</strong>
        </div>
        <div className="voice-diag-metric">
          <span className="k">Reconnects</span>
          <strong className={`v${!hasSession ? " muted" : ""}`}>{hasSession ? s!.reconnect_count : "—"}</strong>
        </div>
        <div className="voice-diag-metric">
          <span className="k">Duration</span>
          <strong className={`v${!hasSession ? " muted" : ""}`}>{hasSession ? `${Math.round(s!.duration_sec)}s` : "—"}</strong>
        </div>
        <div className="voice-diag-metric">
          <span className="k">Personality</span>
          <strong className="v muted">{diag?.configured.voice_personality ?? "—"}</strong>
        </div>
        <div className="voice-diag-metric">
          <span className="k">Accent</span>
          <strong className="v muted">{diag?.configured.accent_locale ?? "—"}</strong>
        </div>
      </div>
      {!hasSession && (
        <div className="empty-state-hint" style={{ marginTop: 10 }}>
          No voice session yet — counters stay zero until the first call. Not invented as “good”.
        </div>
      )}
    </article>
  );
}

/** D18: shared empty-state surface. Honest "no data yet", never "loading..." forever. */
export function EmptyState({
  icon = <Inbox size={28} />,
  title,
  hint,
  actionLabel,
  onAction,
}: {
  icon?: React.ReactNode;
  title: string;
  hint?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty-state" role="status">
      <span className="empty-state-icon">{icon}</span>
      <span className="empty-state-title">{title}</span>
      {hint && <span className="empty-state-hint">{hint}</span>}
      {actionLabel && onAction && (
        <button type="button" className="empty-state-action" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}

/** D18: onboarding hint banner (dismissible; shows once per first visit). */
export function OnboardingHint({ id, children }: { id: string; children: React.ReactNode }) {
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    try {
      if (localStorage.getItem(`onboard-dismissed:${id}`) === "1") {
        setDismissed(true);
      }
    } catch {
      /* localStorage may be blocked — hint just stays visible */
    }
  }, [id]);
  const dismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(`onboard-dismissed:${id}`, "1");
    } catch {
      /* best-effort */
    }
  };
  if (dismissed) return null;
  return (
    <div className="onboarding-hint" role="note">
      <button type="button" className="onboarding-dismiss" onClick={dismiss} aria-label="Dismiss hint">
        ×
      </button>
      {children}
    </div>
  );
}
