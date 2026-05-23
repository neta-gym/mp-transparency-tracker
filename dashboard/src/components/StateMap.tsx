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
import { useMapTooltip } from "@/hooks/useMapTooltip";
import { MapTooltip } from "./MapTooltip";
import type { LeaderboardEntry } from "@/lib/types";

type GeoJSONLike = {
  features?: Array<{
    geometry?: { coordinates?: unknown };
  }>;
};

interface StateMapProps {
  stateSlug: string;
  entries: LeaderboardEntry[];
}

function normalizeConstituencyName(name: string): string {
  const normalized = name
    .toLowerCase()
    .replace(/parliamentary constituency/gi, "")
    .replace(/[^a-z0-9 ]/g, "")
    .trim()
    .replace(/\s+/g, " ");

  // Canonicalize known naming variants between leaderboard + GeoJSON
  const constituencyAliases: Record<string, string> = {
    haridwar: "hardwar",
  };

  return constituencyAliases[normalized] ?? normalized;
}

function findEntryForConstituency(
  pcName: string,
  entries: LeaderboardEntry[]
): LeaderboardEntry | undefined {
  const normalized = normalizeConstituencyName(pcName);

  // Exact match
  const exact = entries.find(
    (e) => normalizeConstituencyName(e.constituency) === normalized
  );
  if (exact) return exact;

  // Token overlap: if all tokens in one are contained in the other
  const tokens = normalized.split(" ");
  return entries.find((e) => {
    const entryTokens = normalizeConstituencyName(e.constituency).split(" ");
    return (
      tokens.every((t) => entryTokens.includes(t)) ||
      entryTokens.every((t) => tokens.includes(t))
    );
  });
}

function entryToSlug(entry: LeaderboardEntry): string {
  return entry.mp_name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function collectCoordinatePairs(coords: unknown, out: [number, number][]) {
  if (!Array.isArray(coords)) return;
  if (
    coords.length >= 2 &&
    typeof coords[0] === "number" &&
    typeof coords[1] === "number"
  ) {
    out.push([coords[0], coords[1]]);
    return;
  }
  coords.forEach((child) => collectCoordinatePairs(child, out));
}

function getProjectionConfig(geoData: unknown) {
  const points: [number, number][] = [];
  const features = (geoData as GeoJSONLike).features ?? [];
  features.forEach((feature) =>
    collectCoordinatePairs(feature.geometry?.coordinates, points)
  );

  if (points.length === 0) {
    return { scale: 30000, center: [77.1, 28.63] as [number, number] };
  }

  const lons = points.map(([lon]) => lon);
  const lats = points.map(([, lat]) => lat);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const lonSpan = Math.max(maxLon - minLon, 0.15);
  const latSpan = Math.max(maxLat - minLat, 0.15);
  const center: [number, number] = [(minLon + maxLon) / 2, (minLat + maxLat) / 2];

  // Approximate a Mercator fit-to-box scale. The clamp keeps tiny UTs visible
  // without making them overflow the 500x500 viewport.
  const rawScale = Math.min(
    470 / (lonSpan * 0.0174533),
    470 / (latSpan * 0.0174533)
  );
  const scale = Math.max(2500, Math.min(55000, rawScale));
  return { scale, center };
}

export function StateMap({ stateSlug, entries }: StateMapProps) {
  const router = useRouter();
  const { tooltip, showTooltip, moveTooltip, hideTooltip } = useMapTooltip();
  const [geoData, setGeoData] = useState<unknown>(null);

  useEffect(() => {
    fetch(`/geo/pc/${stateSlug}.json`)
      .then((r) => r.json())
      .then(setGeoData)
      .catch(console.error);
  }, [stateSlug]);

  if (!geoData) {
    return (
      <div className="flex items-center justify-center h-[500px] text-text-muted font-mono uppercase tracking-widest">
        Loading constituency map...
      </div>
    );
  }

  const projectionConfig = getProjectionConfig(geoData);

  return (
    <div className="relative">
      <ComposableMap
        projection="geoMercator"
        projectionConfig={projectionConfig}
        width={500}
        height={500}
        style={{ width: "100%", height: "auto" }}
      >
        <ZoomableGroup>
          <Geographies geography={geoData}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const pcName = String(
                  geo.properties.PC_NAME ||
                  geo.properties.pc_name ||
                  geo.properties.CONSTITUENCY ||
                  ""
                );
                const entry = findEntryForConstituency(pcName, entries);
                const fillColor = entry
                  ? getScoreColor(entry.composite_score)
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
                        fill: entry ? "#FEF3C7" : "#E2E8F0",
                        cursor: entry ? "pointer" : "default",
                        strokeWidth: 3,
                        stroke: "#1E293B",
                      },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={(event) => {
                      showTooltip(event, {
                        title: entry?.mp_name || pcName,
                        score: entry?.composite_score ?? null,
                        subtitle: entry
                          ? `${entry.constituency} · ${entry.party}`
                          : pcName,
                      });
                    }}
                    onMouseMove={moveTooltip}
                    onMouseLeave={hideTooltip}
                    onClick={() => {
                      if (entry) {
                        router.push(
                          `/state/${stateSlug}/mp/${entryToSlug(entry)}`
                        );
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
