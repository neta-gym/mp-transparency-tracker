// All Indian states and UTs with slugs and display names

export interface StateInfo {
  slug: string;
  displayName: string;
  geoJsonName: string; // Name as it appears in GeoJSON features
}

export const STATES: StateInfo[] = [
  { slug: "andaman-and-nicobar-islands", displayName: "Andaman & Nicobar Islands", geoJsonName: "Andaman & Nicobar Island" },
  { slug: "andhra-pradesh", displayName: "Andhra Pradesh", geoJsonName: "Andhra Pradesh" },
  { slug: "arunachal-pradesh", displayName: "Arunachal Pradesh", geoJsonName: "Arunachal Pradesh" },
  { slug: "assam", displayName: "Assam", geoJsonName: "Assam" },
  { slug: "bihar", displayName: "Bihar", geoJsonName: "Bihar" },
  { slug: "chandigarh", displayName: "Chandigarh", geoJsonName: "Chandigarh" },
  { slug: "chhattisgarh", displayName: "Chhattisgarh", geoJsonName: "Chhattisgarh" },
  { slug: "dadra-and-nagar-haveli-and-daman-and-diu", displayName: "Dadra & Nagar Haveli and Daman & Diu", geoJsonName: "Daman & Diu" },
  { slug: "delhi", displayName: "Delhi", geoJsonName: "NCT of Delhi" },
  { slug: "goa", displayName: "Goa", geoJsonName: "Goa" },
  { slug: "gujarat", displayName: "Gujarat", geoJsonName: "Gujarat" },
  { slug: "haryana", displayName: "Haryana", geoJsonName: "Haryana" },
  { slug: "himachal-pradesh", displayName: "Himachal Pradesh", geoJsonName: "Himachal Pradesh" },
  { slug: "jammu-and-kashmir", displayName: "Jammu & Kashmir", geoJsonName: "Jammu & Kashmir" },
  { slug: "jharkhand", displayName: "Jharkhand", geoJsonName: "Jharkhand" },
  { slug: "karnataka", displayName: "Karnataka", geoJsonName: "Karnataka" },
  { slug: "kerala", displayName: "Kerala", geoJsonName: "Kerala" },
  { slug: "ladakh", displayName: "Ladakh", geoJsonName: "Ladakh" },
  { slug: "lakshadweep", displayName: "Lakshadweep", geoJsonName: "Lakshadweep" },
  { slug: "madhya-pradesh", displayName: "Madhya Pradesh", geoJsonName: "Madhya Pradesh" },
  { slug: "maharashtra", displayName: "Maharashtra", geoJsonName: "Maharashtra" },
  { slug: "manipur", displayName: "Manipur", geoJsonName: "Manipur" },
  { slug: "meghalaya", displayName: "Meghalaya", geoJsonName: "Meghalaya" },
  { slug: "mizoram", displayName: "Mizoram", geoJsonName: "Mizoram" },
  { slug: "nagaland", displayName: "Nagaland", geoJsonName: "Nagaland" },
  // india-states.json uses legacy spellings for these two state names
  { slug: "odisha", displayName: "Odisha", geoJsonName: "Orissa" },
  { slug: "puducherry", displayName: "Puducherry", geoJsonName: "Puducherry" },
  { slug: "punjab", displayName: "Punjab", geoJsonName: "Punjab" },
  { slug: "rajasthan", displayName: "Rajasthan", geoJsonName: "Rajasthan" },
  { slug: "sikkim", displayName: "Sikkim", geoJsonName: "Sikkim" },
  { slug: "tamil-nadu", displayName: "Tamil Nadu", geoJsonName: "Tamil Nadu" },
  { slug: "telangana", displayName: "Telangana", geoJsonName: "Telangana" },
  { slug: "tripura", displayName: "Tripura", geoJsonName: "Tripura" },
  { slug: "uttar-pradesh", displayName: "Uttar Pradesh", geoJsonName: "Uttar Pradesh" },
  { slug: "uttarakhand", displayName: "Uttarakhand", geoJsonName: "Uttaranchal" },
  { slug: "west-bengal", displayName: "West Bengal", geoJsonName: "West Bengal" },
];

// Lookup maps
export const STATE_BY_SLUG = new Map(STATES.map((s) => [s.slug, s]));
export const STATE_BY_GEO_NAME = new Map(
  STATES.map((s) => [s.geoJsonName.toLowerCase(), s])
);

export function getStateBySlug(slug: string): StateInfo | undefined {
  return STATE_BY_SLUG.get(slug);
}

export function getStateSlugFromGeoName(geoName: string): string | undefined {
  return STATE_BY_GEO_NAME.get(geoName.toLowerCase())?.slug;
}
