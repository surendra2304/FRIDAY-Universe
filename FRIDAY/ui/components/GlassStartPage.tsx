"use client";

/* TASK-IG2-WEB-07 — GlassStartPage: a glass-style browser start-page
   dashboard in the GNTD pattern (GNTD: Glass New Tab Dashboard, free
   Chrome new-tab extension; IG sweep crew-13, shortcode DX7B57RM491,
   cluster #11). Glass panels float over a custom photo or gradient
   background; Search, To-do, Weather, Music, Notes and Map widgets
   are each toggleable from the settings strip, and every choice —
   toggles, background, city, to-dos, notes — persists in
   localStorage via lib/glassWidgets.ts.

   Mounted (IG implementation wave, 2026-11-16): app/start/page.tsx
   renders it at the /start route, exactly the standalone start-page
   mounting this component was built for. It is not part of the live
   Halo stage at / and changes no existing surface. All state logic lives in
   lib/glassWidgets.ts (unit-tested with plain node); this file is
   rendering + the two free, key-less data feeds the widgets need:
   Open-Meteo for weather and OpenStreetMap/Nominatim for the map.
   A failed feed renders an explicit unavailable state — the widgets
   never invent weather or places.

   Styling is inline and reads the Halo CSS variables from
   app/globals.css, so the component carries no stylesheet of its
   own. The glass itself is backdrop-filter blur over the chosen
   background. Motion is a single opacity fade on mount; nothing
   loops, so prefers-reduced-motion needs no extra handling. */

import { useEffect, useRef, useState, type CSSProperties } from "react";
import {
  addTodo,
  buildMapEmbedUrl,
  buildMapSearchUrl,
  buildSearchUrl,
  clearDoneTodos,
  clockParts,
  DEFAULT_SETTINGS,
  enabledWidgets,
  GRADIENT_PRESETS,
  loadNotes,
  loadSettings,
  loadTodos,
  removeTodo,
  saveNotes,
  saveSettings,
  saveTodos,
  toggleTodo,
  toggleWidget,
  weatherCodeLabel,
  WIDGET_CATALOGUE,
  type StartPageSettings,
  type TodoItem,
  type WidgetId,
} from "@/lib/glassWidgets";

const mono = "var(--font-mono)";
const display = "var(--font-display)";

const glassPanel: CSSProperties = {
  background: "rgba(10, 14, 29, 0.55)",
  backdropFilter: "blur(18px) saturate(160%)",
  WebkitBackdropFilter: "blur(18px) saturate(160%)",
  border: "1px solid var(--hair)",
  borderRadius: 18,
  padding: 18,
  color: "var(--ink)",
  boxShadow: "0 18px 50px rgba(0, 0, 0, 0.35)",
};

const widgetTitle: CSSProperties = {
  fontFamily: display,
  fontSize: 13,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: "var(--dim)",
  margin: "0 0 12px",
};

const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  background: "rgba(3, 4, 9, 0.55)",
  border: "1px solid var(--hair)",
  borderRadius: 10,
  color: "var(--ink)",
  padding: "9px 12px",
  fontSize: 14,
  outline: "none",
};

const buttonStyle: CSSProperties = {
  background: "rgba(56, 189, 248, 0.16)",
  border: "1px solid var(--hair)",
  borderRadius: 10,
  color: "var(--ink)",
  padding: "8px 14px",
  fontSize: 13,
  cursor: "pointer",
  whiteSpace: "nowrap",
};

type WeatherState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; place: string; tempC: number; code: number; windKmh: number }
  | { status: "error"; message: string };

type MapState = { lat: number; lon: number; label: string; searched: boolean };

const DEFAULT_MAP: MapState = { lat: 17.385, lon: 78.4867, label: "Hyderabad (default)", searched: false };
const DEFAULT_STREAM = "https://ice1.somafm.com/groovesalad-128-mp3";

export function GlassStartPage() {
  const [settings, setSettings] = useState<StartPageSettings>(DEFAULT_SETTINGS);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [notes, setNotes] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [now, setNow] = useState(() => new Date());

  const [searchQuery, setSearchQuery] = useState("");
  const [todoDraft, setTodoDraft] = useState("");
  const [cityDraft, setCityDraft] = useState(DEFAULT_SETTINGS.city);
  const [weather, setWeather] = useState<WeatherState>({ status: "idle" });
  const [map, setMap] = useState<MapState>(DEFAULT_MAP);
  const [mapQuery, setMapQuery] = useState("");
  const [mapError, setMapError] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState(DEFAULT_STREAM);
  const [playing, setPlaying] = useState(false);
  const [musicError, setMusicError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  /* Load persisted state once (client-only; SSR renders defaults). */
  useEffect(() => {
    const loaded = loadSettings(window.localStorage);
    setSettings(loaded);
    setCityDraft(loaded.city);
    setTodos(loadTodos(window.localStorage));
    setNotes(loadNotes(window.localStorage));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) saveSettings(window.localStorage, settings);
  }, [hydrated, settings]);
  useEffect(() => {
    if (hydrated) saveTodos(window.localStorage, todos);
  }, [hydrated, todos]);
  useEffect(() => {
    if (hydrated) saveNotes(window.localStorage, notes);
  }, [hydrated, notes]);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 20_000);
    return () => clearInterval(timer);
  }, []);

  /* Weather for the configured city, from Open-Meteo (free, no key).
     Any failure lands in the error state with the reason — no fallback
     numbers are ever fabricated. */
  useEffect(() => {
    if (!settings.enabled.weather || !hydrated) return;
    let cancelled = false;
    setWeather({ status: "loading" });
    (async () => {
      try {
        const geoRes = await fetch(
          `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(settings.city)}&count=1`,
        );
        if (!geoRes.ok) throw new Error(`geocoding HTTP ${geoRes.status}`);
        const geo = (await geoRes.json()) as {
          results?: { latitude: number; longitude: number; name: string; country?: string }[];
        };
        const place = geo.results?.[0];
        if (!place) throw new Error(`no match for "${settings.city}"`);
        const wxRes = await fetch(
          `https://api.open-meteo.com/v1/forecast?latitude=${place.latitude}&longitude=${place.longitude}&current=temperature_2m,weather_code,wind_speed_10m`,
        );
        if (!wxRes.ok) throw new Error(`forecast HTTP ${wxRes.status}`);
        const wx = (await wxRes.json()) as {
          current?: { temperature_2m: number; weather_code: number; wind_speed_10m: number };
        };
        if (!wx.current) throw new Error("forecast carried no current conditions");
        if (!cancelled) {
          setWeather({
            status: "ok",
            place: place.country ? `${place.name}, ${place.country}` : place.name,
            tempC: wx.current.temperature_2m,
            code: wx.current.weather_code,
            windKmh: wx.current.wind_speed_10m,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setWeather({
            status: "error",
            message: err instanceof Error ? err.message : "weather lookup failed",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [settings.city, settings.enabled.weather, hydrated]);

  const clock = clockParts(now);
  const visible = enabledWidgets(settings);

  const runSearch = () => {
    const url = buildSearchUrl(searchQuery);
    if (url) window.open(url, "_blank", "noopener");
  };

  const applyCity = () => {
    const city = cityDraft.trim();
    if (city) setSettings((s) => ({ ...s, city }));
  };

  const searchMap = async () => {
    const query = mapQuery.trim();
    if (!query) return;
    setMapError(null);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const hits = (await res.json()) as { lat: string; lon: string; display_name: string }[];
      const hit = hits[0];
      if (!hit) {
        setMapError(`No place found for "${query}".`);
        return;
      }
      setMap({ lat: Number(hit.lat), lon: Number(hit.lon), label: hit.display_name, searched: true });
    } catch (err) {
      setMapError(err instanceof Error ? `Map search failed: ${err.message}` : "Map search failed.");
    }
  };

  const toggleMusic = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    setMusicError(null);
    if (playing) {
      audio.pause();
      setPlaying(false);
      return;
    }
    try {
      await audio.play();
      setPlaying(true);
    } catch {
      setMusicError("The stream would not play — check the URL or try again.");
      setPlaying(false);
    }
  };

  return (
    <main
      aria-label="FRIDAY glass start page"
      style={{ position: "relative", minHeight: "100vh", overflow: "hidden", fontFamily: "var(--font-body)" }}
    >
      {/* Background: chosen gradient, or the user's photo under a dark veil. */}
      {settings.background.kind === "image" ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={settings.background.value}
            alt=""
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
          />
          <div style={{ position: "absolute", inset: 0, background: "rgba(3, 4, 9, 0.45)" }} />
        </>
      ) : (
        <div style={{ position: "absolute", inset: 0, background: settings.background.value }} />
      )}

      <div
        style={{
          position: "relative",
          maxWidth: 1060,
          margin: "0 auto",
          padding: "42px 20px 56px",
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <header style={{ textAlign: "center", color: "var(--ink)", textShadow: "0 2px 18px rgba(0,0,0,0.6)" }}>
          <div style={{ fontFamily: mono, fontSize: 64, fontWeight: 600, lineHeight: 1 }}>{clock.time}</div>
          <div style={{ fontFamily: display, fontSize: 16, color: "var(--dim)", marginTop: 6 }}>{clock.day}</div>
        </header>

        {/* Settings strip: widget toggles + background + city. */}
        <section aria-label="Start page settings" style={{ ...glassPanel, padding: "12px 16px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 18px", alignItems: "center" }}>
            {WIDGET_CATALOGUE.map((w) => (
              <label key={w.id} style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: 13, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={settings.enabled[w.id]}
                  onChange={() => setSettings((s) => toggleWidget(s, w.id as WidgetId))}
                />
                {w.title}
              </label>
            ))}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
            <select
              aria-label="Background gradient"
              value={GRADIENT_PRESETS.find((p) => p.css === settings.background.value)?.id ?? "custom"}
              onChange={(e) => {
                const preset = GRADIENT_PRESETS.find((p) => p.id === e.target.value);
                if (preset) setSettings((s) => ({ ...s, background: { kind: "gradient", value: preset.css } }));
              }}
              style={{ ...inputStyle, width: "auto" }}
            >
              {GRADIENT_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
              {settings.background.kind === "image" && <option value="custom">Photo background</option>}
            </select>
            <input
              aria-label="Photo background URL"
              placeholder="…or paste a photo URL for the background"
              defaultValue={settings.background.kind === "image" ? settings.background.value : ""}
              onBlur={(e) => {
                const url = e.target.value.trim();
                if (url) setSettings((s) => ({ ...s, background: { kind: "image", value: url } }));
              }}
              style={{ ...inputStyle, flex: "1 1 260px", width: "auto" }}
            />
            <input
              aria-label="Weather city"
              value={cityDraft}
              onChange={(e) => setCityDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyCity()}
              placeholder="Weather city"
              style={{ ...inputStyle, flex: "0 1 170px", width: "auto" }}
            />
            <button type="button" style={buttonStyle} onClick={applyCity}>
              Set city
            </button>
          </div>
        </section>

        {visible.length === 0 && (
          <p style={{ ...glassPanel, textAlign: "center", color: "var(--dim)" }}>
            Every widget is off. Turn one back on in the settings strip above — this page is yours to arrange.
          </p>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))",
            gap: 18,
            alignItems: "start",
          }}
        >
          {settings.enabled.search && (
            <section aria-label="Search" style={{ ...glassPanel, gridColumn: "1 / -1" }}>
              <h2 style={widgetTitle}>Search</h2>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  aria-label="Search the web"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && runSearch()}
                  placeholder="Search the web…"
                  style={inputStyle}
                />
                <button type="button" style={buttonStyle} onClick={runSearch}>
                  Search
                </button>
              </div>
            </section>
          )}

          {settings.enabled.todo && (
            <section aria-label="To-do" style={glassPanel}>
              <h2 style={widgetTitle}>To-do</h2>
              <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
                <input
                  aria-label="New to-do"
                  value={todoDraft}
                  onChange={(e) => setTodoDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      setTodos((t) => addTodo(t, todoDraft, `todo-${Date.now()}`, Date.now()));
                      setTodoDraft("");
                    }
                  }}
                  placeholder="Add a task…"
                  style={inputStyle}
                />
                <button
                  type="button"
                  style={buttonStyle}
                  onClick={() => {
                    setTodos((t) => addTodo(t, todoDraft, `todo-${Date.now()}`, Date.now()));
                    setTodoDraft("");
                  }}
                >
                  Add
                </button>
              </div>
              {todos.length === 0 ? (
                <p style={{ color: "var(--faint)", fontSize: 14, margin: 0 }}>Nothing on the list yet.</p>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                  {todos.map((item) => (
                    <li key={item.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
                      <input
                        type="checkbox"
                        checked={item.done}
                        onChange={() => setTodos((t) => toggleTodo(t, item.id))}
                        aria-label={`Mark "${item.text}" ${item.done ? "not done" : "done"}`}
                      />
                      <span style={{ flex: 1, textDecoration: item.done ? "line-through" : "none", color: item.done ? "var(--faint)" : "var(--ink)" }}>
                        {item.text}
                      </span>
                      <button
                        type="button"
                        aria-label={`Remove "${item.text}"`}
                        onClick={() => setTodos((t) => removeTodo(t, item.id))}
                        style={{ ...buttonStyle, padding: "4px 10px" }}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {todos.some((t) => t.done) && (
                <button type="button" style={{ ...buttonStyle, marginTop: 12 }} onClick={() => setTodos((t) => clearDoneTodos(t))}>
                  Clear done
                </button>
              )}
            </section>
          )}

          {settings.enabled.weather && (
            <section aria-label="Weather" style={glassPanel}>
              <h2 style={widgetTitle}>Weather</h2>
              {weather.status === "idle" || weather.status === "loading" ? (
                <p style={{ color: "var(--dim)", fontSize: 14, margin: 0 }}>Loading live weather for {settings.city}…</p>
              ) : weather.status === "error" ? (
                <p style={{ color: "var(--bad)", fontSize: 14, margin: 0 }}>
                  Weather unavailable ({weather.message}). Check the city name or your connection.
                </p>
              ) : (
                <div>
                  <div style={{ fontFamily: mono, fontSize: 40 }}>{Math.round(weather.tempC)}°C</div>
                  <div style={{ fontSize: 15, marginTop: 4 }}>{weatherCodeLabel(weather.code)}</div>
                  <div style={{ fontSize: 13, color: "var(--dim)", marginTop: 6 }}>
                    {weather.place} · wind {Math.round(weather.windKmh)} km/h · Open-Meteo
                  </div>
                </div>
              )}
            </section>
          )}

          {settings.enabled.music && (
            <section aria-label="Music" style={glassPanel}>
              <h2 style={widgetTitle}>Music</h2>
              <audio
                ref={audioRef}
                src={streamUrl}
                preload="none"
                onError={() => {
                  setPlaying(false);
                  setMusicError("That stream could not be loaded.");
                }}
              />
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <button type="button" style={buttonStyle} onClick={toggleMusic} aria-label={playing ? "Pause music" : "Play music"}>
                  {playing ? "❚❚ Pause" : "▶ Play"}
                </button>
                <span style={{ fontSize: 13, color: "var(--dim)" }}>
                  {playing ? "Playing live stream" : "Preset: SomaFM Groove Salad"}
                </span>
              </div>
              <input
                aria-label="Stream URL"
                value={streamUrl}
                onChange={(e) => {
                  setStreamUrl(e.target.value);
                  setPlaying(false);
                }}
                placeholder="Audio stream URL"
                style={{ ...inputStyle, marginTop: 12 }}
              />
              {musicError && (
                <p style={{ color: "var(--bad)", fontSize: 13, margin: "10px 0 0" }}>{musicError}</p>
              )}
            </section>
          )}

          {settings.enabled.notes && (
            <section aria-label="Notes" style={glassPanel}>
              <h2 style={widgetTitle}>Notes</h2>
              <textarea
                aria-label="Notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Scratch something down — it stays on this device."
                rows={7}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "var(--font-body)" }}
              />
            </section>
          )}

          {settings.enabled.map && (
            <section aria-label="Map" style={glassPanel}>
              <h2 style={widgetTitle}>Map</h2>
              <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
                <input
                  aria-label="Find a place"
                  value={mapQuery}
                  onChange={(e) => setMapQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void searchMap()}
                  placeholder="Find a place…"
                  style={inputStyle}
                />
                <button type="button" style={buttonStyle} onClick={() => void searchMap()}>
                  Go
                </button>
              </div>
              <iframe
                title={`Map — ${map.label}`}
                src={buildMapEmbedUrl(map.lat, map.lon)}
                style={{ width: "100%", height: 220, border: 0, borderRadius: 12 }}
                loading="lazy"
              />
              <div style={{ fontSize: 12, color: "var(--dim)", marginTop: 8 }}>
                {map.label}
                {buildMapSearchUrl(map.label) && (
                  <>
                    {" · "}
                    <a href={buildMapSearchUrl(map.label) ?? undefined} target="_blank" rel="noreferrer" style={{ color: "var(--glow-a)" }}>
                      Open in OpenStreetMap
                    </a>
                  </>
                )}
              </div>
              {mapError && (
                <p style={{ color: "var(--bad)", fontSize: 13, margin: "8px 0 0" }}>{mapError}</p>
              )}
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
