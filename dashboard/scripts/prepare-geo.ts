/**
 * GeoJSON Preparation Script
 *
 * Downloads India state boundaries and parliamentary constituency boundaries
 * from open-source repositories, simplifies them, and saves to public/geo/.
 *
 * Usage: npx tsx scripts/prepare-geo.ts
 */

import fs from "fs";
import path from "path";

const OUT_DIR = path.join(__dirname, "..", "public", "geo");
const PC_DIR = path.join(OUT_DIR, "pc");

// India state boundaries (DataMeet / geohacker)
const INDIA_STATES_URL =
  "https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson";

// All-India parliamentary constituency boundaries (DataMeet 2019 simplified)
const ALL_INDIA_PC_URL =
  "https://raw.githubusercontent.com/datameet/maps/master/parliamentary-constituencies/india_pc_2019_simplified.geojson";

// State name → slug mapping for filtering constituency GeoJSON
const STATE_NAME_TO_SLUG: Record<string, string> = {
  DELHI: "delhi",
  "NCT OF DELHI": "delhi",
  MAHARASHTRA: "maharashtra",
  "UTTAR PRADESH": "uttar-pradesh",
  KARNATAKA: "karnataka",
  "TAMIL NADU": "tamil-nadu",
  "WEST BENGAL": "west-bengal",
  BIHAR: "bihar",
  RAJASTHAN: "rajasthan",
  "ANDHRA PRADESH": "andhra-pradesh",
  TELANGANA: "telangana",
  GUJARAT: "gujarat",
  "MADHYA PRADESH": "madhya-pradesh",
  KERALA: "kerala",
  ODISHA: "odisha",
  ORISSA: "odisha",
  ASSAM: "assam",
  JHARKHAND: "jharkhand",
  PUNJAB: "punjab",
  CHHATTISGARH: "chhattisgarh",
  HARYANA: "haryana",
  UTTARAKHAND: "uttarakhand",
  "HIMACHAL PRADESH": "himachal-pradesh",
  "JAMMU & KASHMIR": "jammu-and-kashmir",
  "JAMMU AND KASHMIR": "jammu-and-kashmir",
  GOA: "goa",
  TRIPURA: "tripura",
  MEGHALAYA: "meghalaya",
  MANIPUR: "manipur",
  NAGALAND: "nagaland",
  MIZORAM: "mizoram",
  "ARUNACHAL PRADESH": "arunachal-pradesh",
  SIKKIM: "sikkim",
  PUDUCHERRY: "puducherry",
  CHANDIGARH: "chandigarh",
  "ANDAMAN & NICOBAR ISLANDS": "andaman-and-nicobar-islands",
  "ANDAMAN & NICOBAR": "andaman-and-nicobar-islands",
  "ANDAMAN AND NICOBAR ISLANDS": "andaman-and-nicobar-islands",
  "DADRA & NAGAR HAVELI AND DAMAN & DIU": "dadra-and-nagar-haveli-and-daman-and-diu",
  "DAMAN & DIU": "dadra-and-nagar-haveli-and-daman-and-diu",
  "DADRA & NAGAR HAVELI": "dadra-and-nagar-haveli-and-daman-and-diu",
  "DADRA AND NAGAR HAVELI": "dadra-and-nagar-haveli-and-daman-and-diu",
  LAKSHADWEEP: "lakshadweep",
  LADAKH: "ladakh",
};

// Extract constituency boundaries for every state/UT tracked by the dashboard.
// If this falls out of sync, state pages show an infinite "Loading constituency map..."
// and log a JSON parse error because /geo/pc/{state}.json returns the static 404 page.
const STATES_TO_EXTRACT = Object.values(STATE_NAME_TO_SLUG).filter(
  (slug, index, all) => all.indexOf(slug) === index
);

interface GeoJSONFeature {
  type: "Feature";
  properties: Record<string, unknown>;
  geometry: {
    type: string;
    coordinates: unknown[];
  };
}

interface GeoJSON {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

async function downloadJSON(url: string): Promise<unknown> {
  console.log(`  Downloading: ${url}`);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status}`);
  }
  return response.json();
}

/**
 * Reduce coordinate precision to shrink file size.
 * precision=100 → 2 decimal places (~1.1km accuracy), good for state-level
 * precision=1000 → 3 decimal places (~110m accuracy), good for constituency-level
 */
function reduceCoordinatePrecision(coords: unknown, precision: number): unknown {
  if (typeof coords === "number") {
    return Math.round(coords * precision) / precision;
  }
  if (Array.isArray(coords)) {
    return coords.map((c) => reduceCoordinatePrecision(c, precision));
  }
  return coords;
}

/**
 * Downsample polygon coordinates by keeping every Nth point.
 * Preserves first and last point to keep polygons closed.
 */
function downsampleCoords(coords: unknown, keepEveryN: number): unknown {
  if (!Array.isArray(coords)) return coords;
  if (coords.length === 0) return coords;

  // If first element is a number, this is a coordinate pair — don't downsample
  if (typeof coords[0] === "number") return coords;

  // If first element is an array of numbers, this is a ring of coordinates
  if (Array.isArray(coords[0]) && typeof coords[0][0] === "number") {
    if (coords.length <= 4) return coords; // Minimum polygon
    const sampled = coords.filter(
      (_, i) => i === 0 || i === coords.length - 1 || i % keepEveryN === 0
    );
    return sampled;
  }

  // Otherwise recurse
  return coords.map((c) => downsampleCoords(c, keepEveryN));
}

function simplifyGeoJSON(
  geojson: GeoJSON,
  precision: number,
  downsample: number = 1
): GeoJSON {
  return {
    type: "FeatureCollection",
    features: geojson.features.map((f) => {
      let coords = f.geometry.coordinates;
      if (downsample > 1) {
        coords = downsampleCoords(coords, downsample) as unknown[];
      }
      coords = reduceCoordinatePrecision(coords, precision) as unknown[];
      return {
        ...f,
        geometry: { ...f.geometry, coordinates: coords },
      };
    }),
  };
}

async function prepareIndiaStates() {
  console.log("\n=== Preparing India state boundaries ===");

  try {
    const geojson = (await downloadJSON(INDIA_STATES_URL)) as GeoJSON;
    console.log(`  Downloaded ${geojson.features.length} state features`);

    // Aggressively simplify: 2 decimal places + keep every 5th point
    const simplified = simplifyGeoJSON(geojson, 100, 5);

    // Keep only essential properties
    simplified.features = simplified.features.map((f) => ({
      ...f,
      properties: {
        NAME_1: f.properties.NAME_1 || f.properties.name || f.properties.ST_NM,
        ST_CODE: f.properties.ST_CODE || f.properties.state_code,
      },
    }));

    const outPath = path.join(OUT_DIR, "india-states.json");
    fs.writeFileSync(outPath, JSON.stringify(simplified));
    const sizeKB = (fs.statSync(outPath).size / 1024).toFixed(1);
    console.log(`  Saved: ${outPath} (${sizeKB} KB)`);
  } catch (error) {
    console.error("  Failed to download India states GeoJSON:", error);
    console.log("  Creating placeholder india-states.json...");
    const placeholder: GeoJSON = { type: "FeatureCollection", features: [] };
    fs.writeFileSync(
      path.join(OUT_DIR, "india-states.json"),
      JSON.stringify(placeholder)
    );
  }
}

async function prepareConstituencies() {
  console.log("\n=== Preparing constituency boundaries ===");
  console.log("  Downloading all-India constituency GeoJSON...");

  let allIndia: GeoJSON;
  try {
    allIndia = (await downloadJSON(ALL_INDIA_PC_URL)) as GeoJSON;
    console.log(
      `  Downloaded ${allIndia.features.length} total constituency features`
    );
  } catch (error) {
    console.error("  Failed to download all-India PC GeoJSON:", error);
    console.log("  Will use placeholders for all states.");
    // Create placeholders for requested states
    for (const stateSlug of STATES_TO_EXTRACT) {
      if (stateSlug === "delhi") {
        const placeholder = createDelhiPlaceholder();
        const outPath = path.join(PC_DIR, `${stateSlug}.json`);
        fs.writeFileSync(outPath, JSON.stringify(placeholder));
        console.log(`  Created Delhi placeholder with 7 constituencies`);
      }
    }
    return;
  }

  // Group features by state
  const byState = new Map<string, GeoJSONFeature[]>();
  for (const feature of allIndia.features) {
    const stName =
      ((feature.properties.st_name as string) ||
        (feature.properties.ST_NAME as string) ||
        "")
        .toUpperCase()
        .trim();
    const pcName =
      ((feature.properties.pc_name as string) ||
        (feature.properties.PC_NAME as string) ||
        "")
        .toUpperCase()
        .trim();
    const slug =
      stName === "JAMMU & KASHMIR" && pcName === "LADAKH"
        ? "ladakh"
        : STATE_NAME_TO_SLUG[stName];
    if (slug) {
      if (!byState.has(slug)) byState.set(slug, []);
      byState.get(slug)!.push(feature);
    }
  }

  console.log(`  Found constituencies for ${byState.size} states`);

  for (const stateSlug of STATES_TO_EXTRACT) {
    const features = byState.get(stateSlug);
    if (!features || features.length === 0) {
      console.log(
        `  WARNING: No constituency features found for ${stateSlug}`
      );
      if (stateSlug === "delhi") {
        const placeholder = createDelhiPlaceholder();
        const outPath = path.join(PC_DIR, `${stateSlug}.json`);
        fs.writeFileSync(outPath, JSON.stringify(placeholder));
        console.log(`  Created Delhi placeholder with 7 constituencies`);
      }
      continue;
    }

    // Build state GeoJSON with simplified coordinates
    const stateGeo: GeoJSON = {
      type: "FeatureCollection",
      features: features.map((f) => ({
        ...f,
        properties: {
          PC_NAME:
            (f.properties.pc_name as string) ||
            (f.properties.PC_NAME as string) ||
            "",
          ST_NAME: stateSlug,
        },
        geometry: {
          ...f.geometry,
          coordinates: reduceCoordinatePrecision(
            f.geometry.coordinates,
            10000
          ) as unknown[],
        },
      })),
    };

    const outPath = path.join(PC_DIR, `${stateSlug}.json`);
    fs.writeFileSync(outPath, JSON.stringify(stateGeo));
    const sizeKB = (fs.statSync(outPath).size / 1024).toFixed(1);

    const names = stateGeo.features.map((f) => f.properties.PC_NAME);
    console.log(
      `  ${stateSlug}: ${features.length} constituencies (${sizeKB} KB)`
    );
    console.log(`    Names: ${names.join(", ")}`);
  }
}

function createDelhiPlaceholder(): GeoJSON {
  const constituencies = [
    { name: "Chandni Chowk", cx: 77.23, cy: 28.66 },
    { name: "North East Delhi", cx: 77.3, cy: 28.7 },
    { name: "East Delhi", cx: 77.32, cy: 28.63 },
    { name: "New Delhi", cx: 77.21, cy: 28.61 },
    { name: "North West Delhi", cx: 77.1, cy: 28.72 },
    { name: "West Delhi", cx: 77.05, cy: 28.63 },
    { name: "South Delhi", cx: 77.22, cy: 28.52 },
  ];

  const d = 0.04;

  return {
    type: "FeatureCollection",
    features: constituencies.map((c) => ({
      type: "Feature" as const,
      properties: { PC_NAME: c.name, ST_NAME: "delhi" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [c.cx - d, c.cy - d],
            [c.cx + d, c.cy - d],
            [c.cx + d, c.cy + d],
            [c.cx - d, c.cy + d],
            [c.cx - d, c.cy - d],
          ],
        ],
      },
    })),
  };
}

async function main() {
  console.log("MP Transparency Dashboard — GeoJSON Preparation");
  console.log("================================================");

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.mkdirSync(PC_DIR, { recursive: true });

  await prepareIndiaStates();
  await prepareConstituencies();

  console.log("\n=== Done ===");
  console.log(`Output directory: ${OUT_DIR}`);
}

main().catch(console.error);
