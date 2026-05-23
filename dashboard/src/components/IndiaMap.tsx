"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from "react-simple-maps";
import { getScoreColor, NO_DATA_COLOR } from "@/lib/colors";
import { publicPath } from "@/lib/paths";
import { useMapTooltip } from "@/hooks/useMapTooltip";
import { MapTooltip } from "./MapTooltip";
import type { StateManifest } from "@/lib/types";

interface IndiaMapProps {
  states: StateManifest[];
}

// Build lookup: geoJsonName (lowercase) → StateManifest
function buildStateLookup(states: StateManifest[]) {
  const map = new Map<string, StateManifest>();
  // We need to match GeoJSON feature names to our state slugs
  // The GeoJSON uses NAME_1 property with various name formats
  const NAME_OVERRIDES: Record<string, string> = {
    "nct of delhi": "delhi",
    "andaman & nicobar island": "andaman-and-nicobar-islands",
    "andaman & nicobar islands": "andaman-and-nicobar-islands",
    "daman & diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "dadra & nagar haveli": "dadra-and-nagar-haveli-and-daman-and-diu",
    "jammu & kashmir": "jammu-and-kashmir",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
  };

  for (const s of states) {
    // Map by slug
    map.set(s.slug, s);
    // Map by display name (normalized)
    map.set(s.displayName.toLowerCase(), s);
  }

  return { map, NAME_OVERRIDES };
}

function getStateForFeature(
  featureName: string,
  lookup: ReturnType<typeof buildStateLookup>,
  states: StateManifest[]
): StateManifest | undefined {
  const normalized = featureName.toLowerCase().trim();

  // Check overrides first
  const overrideSlug = lookup.NAME_OVERRIDES[normalized];
  if (overrideSlug) {
    return states.find((s) => s.slug === overrideSlug);
  }

  // Direct match on display name
  const byName = lookup.map.get(normalized);
  if (byName) return byName;

  // Try slug-style match
  const slugified = normalized.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const bySlug = lookup.map.get(slugified);
  if (bySlug) return bySlug;

  // Fuzzy: check if any state display name contains or is contained
  return states.find(
    (s) =>
      s.displayName.toLowerCase().includes(normalized) ||
      normalized.includes(s.displayName.toLowerCase())
  );
}

export function IndiaMap({ states }: IndiaMapProps) {
  const router = useRouter();
  const { tooltip, showTooltip, moveTooltip, hideTooltip } = useMapTooltip();
  const [geoData, setGeoData] = useState<unknown>(null);

  useEffect(() => {
    fetch(publicPath("/geo/india-states.json"))
      .then((r) => r.json())
      .then(setGeoData)
      .catch(console.error);
  }, []);

  const lookup = buildStateLookup(states);

  if (!geoData) {
    return (
      <div className="flex items-center justify-center h-[600px] text-text-muted font-mono uppercase tracking-widest">
        Loading map...
      </div>
    );
  }

  return (
    <div className="relative">
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{
          scale: 1000,
          center: [82, 22],
        }}
        width={600}
        height={700}
        style={{ width: "100%", height: "auto" }}
      >
        <ZoomableGroup>
          <Geographies geography={geoData}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const name = String(
                  geo.properties.NAME_1 ||
                  geo.properties.name ||
                  geo.properties.ST_NM ||
                  ""
                );
                const state = getStateForFeature(name, lookup, states);
                const fillColor =
                  state?.hasData && state.avgScore != null
                    ? getScoreColor(state.avgScore)
                    : NO_DATA_COLOR;

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={fillColor}
                    stroke="#1E293B"
                    strokeWidth={2}
                    style={{
                      default: { outline: "none" },
                      hover: {
                        outline: "none",
                        fill: state?.hasData ? "#FEF3C7" : "#E2E8F0",
                        cursor: state?.hasData ? "pointer" : "default",
                        strokeWidth: 3,
                        stroke: "#1E293B",
                      },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={(event) => {
                      showTooltip(event, {
                        title: state?.displayName || name,
                        score: state?.avgScore ?? null,
                        subtitle: state?.hasData
                          ? `${state.mpCount} MPs`
                          : "No data yet",
                      });
                    }}
                    onMouseMove={moveTooltip}
                    onMouseLeave={hideTooltip}
                    onClick={() => {
                      if (state?.hasData) {
                        router.push(`/state/${state.slug}`);
                      }
                    }}
                  />
                );
              })
            }
          </Geographies>
        </ZoomableGroup>
      </ComposableMap>
      <MapTooltip {...tooltip} />
    </div>
  );
}
