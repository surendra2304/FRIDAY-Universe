"use client";

import { useEffect, useState } from "react";
import { buildMapEmbedUrl, buildMapSearchUrl } from "@/lib/glassWidgets";

/* ================================================================
   MapInterface — an OSIRIS-style map surface (TASK-WEB-008, NEW).

   Source idea (board acceptance, F-39 item DcOGDRgkhj6): a map
   interface over real places — search a place, see it centred
   on the map, open it in OpenStreetMap.

   Key-less by design, same feeds as the glass start page:
   Nominatim for geocoding, the OpenStreetMap embed for the
   tiles. No API key exists or is needed; no map library is
   added. Coordinates come only from Nominatim hits or from a
   caller-supplied place — never invented, never a stock
   default. When Nominatim doesn't answer, the interface says
   so; when a search matches nothing, it says that too.

   `defaultQuery` geocodes one query on mount (the house
   default city is the honest choice for a demo); pass
   `initialPlace` instead when the caller already holds real
   coordinates.
   ================================================================ */

export interface MapPlace {
  lat: number;
  lon: number;
  label: string;
}

interface NominatimHit {
  lat: string;
  lon: string;
  display_name: string;
}

type GeoStatus = "idle" | "searching" | "none" | "error";

export interface MapInterfaceProps {
  /** Query geocoded on mount (e.g. the house default city). */
  defaultQuery?: string;
  /** Caller-held coordinates — skips the mount geocode. */
  initialPlace?: MapPlace;
  /** Fires when the user picks a place. */
  onPlace?: (place: MapPlace) => void;
}

async function geocode(query: string): Promise<MapPlace[]> {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`,
    { headers: { Accept: "application/json" } },
  );
  if (!res.ok) throw new Error(`Nominatim answered ${res.status}`);
  const hits = (await res.json()) as NominatimHit[];
  return hits
    .map((h) => ({
      lat: Number(h.lat),
      lon: Number(h.lon),
      label: h.display_name,
    }))
    .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));
}

export function MapInterface({
  defaultQuery,
  initialPlace,
  onPlace,
}: MapInterfaceProps) {
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState<MapPlace | null>(initialPlace ?? null);
  const [results, setResults] = useState<MapPlace[]>([]);
  // Searching from the first render when a mount geocode is owed, so no
  // setState-in-effect is needed for the initial state.
  const [status, setStatus] = useState<GeoStatus>(
    initialPlace || !defaultQuery ? "idle" : "searching",
  );
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (initialPlace || !defaultQuery) return;
    let cancelled = false;
    geocode(defaultQuery)
      .then((hits) => {
        if (cancelled) return;
        if (hits.length > 0) {
          setPlace(hits[0]);
          onPlace?.(hits[0]);
          setStatus("idle");
        } else {
          setStatus("none");
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // Mount-only: the default query is a starting point, not a live input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSearch = async (q: string) => {
    const clean = q.trim();
    if (!clean) return;
    setStatus("searching");
    setSearched(true);
    try {
      const hits = await geocode(clean);
      setResults(hits);
      setStatus(hits.length > 0 ? "idle" : "none");
    } catch {
      setResults([]);
      setStatus("error");
    }
  };

  const pick = (p: MapPlace) => {
    setPlace(p);
    setResults([]);
    setQuery(p.label);
    onPlace?.(p);
  };

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void runSearch(query);
        }}
        style={{ display: "flex", gap: 8, marginBottom: 12 }}
      >
        <label htmlFor="map-search" className="sheet-note" style={{ alignSelf: "center" }}>
          Place
        </label>
        <input
          id="map-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a place — Nominatim"
          aria-label="Search a place"
          style={{
            flex: 1,
            background: "rgba(10, 14, 29, 0.55)",
            border: "1px solid var(--hair)",
            borderRadius: 8,
            padding: "8px 12px",
            color: "var(--text, #e8ecf4)",
            font: "inherit",
          }}
        />
        <button
          type="submit"
          disabled={status === "searching"}
          style={{
            border: "1px solid var(--hair)",
            borderRadius: 8,
            padding: "8px 14px",
            background: "transparent",
            color: "var(--text, #e8ecf4)",
            font: "inherit",
            cursor: "pointer",
          }}
        >
          {status === "searching" ? "Searching…" : "Search"}
        </button>
      </form>

      {status === "searching" && (
        <p className="sheet-note">Asking Nominatim…</p>
      )}
      {status === "none" && searched && (
        <p className="sheet-note" role="status">
          No place matched that search — nothing is shown in its place.
        </p>
      )}
      {status === "error" && (
        <p className="sheet-note" role="alert">
          Nominatim didn&apos;t answer — the map is unavailable right now, not
          empty.
        </p>
      )}

      {results.length > 0 && (
        <ul style={{ listStyle: "none", margin: "0 0 12px", padding: 0 }}>
          {results.map((r) => (
            <li key={`${r.lat},${r.lon}`}>
              <button
                type="button"
                onClick={() => pick(r)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: "none",
                  borderBottom: "1px solid var(--hair)",
                  padding: "8px 4px",
                  color: "var(--text, #e8ecf4)",
                  font: "inherit",
                  cursor: "pointer",
                }}
              >
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      {place ? (
        <div>
          <iframe
            title={`Map — ${place.label}`}
            src={buildMapEmbedUrl(place.lat, place.lon)}
            style={{
              width: "100%",
              height: 420,
              border: "1px solid var(--hair)",
              borderRadius: 12,
              display: "block",
            }}
            loading="lazy"
          />
          <p className="sheet-note" style={{ paddingTop: 8 }}>
            {place.label} —{" "}
            <a
              href={buildMapSearchUrl(place.label) ?? "https://www.openstreetmap.org/"}
              target="_blank"
              rel="noreferrer"
            >
              Open in OpenStreetMap
            </a>
          </p>
        </div>
      ) : (
        status !== "searching" && (
          <p className="sheet-note">
            Search a place to see it on the map.
          </p>
        )
      )}
    </div>
  );
}
