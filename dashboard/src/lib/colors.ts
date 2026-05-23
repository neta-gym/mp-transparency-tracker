import { scaleLinear } from "d3-scale";

// Continuous score → color scale (0-100)
const scoreColorScale = scaleLinear<string>()
  .domain([0, 20, 40, 60, 80, 100])
  .range([
    "#FF1744", // danger — Critical
    "#FF3D00", // primary — Poor
    "#FFAB00", // warning — Average
    "#00C853", // success — Good
    "#059669", // emerald — Excellent
    "#047857", // emerald-700
  ])
  .clamp(true);

export function getScoreColor(score: number): string {
  return scoreColorScale(score);
}

export function getScoreLabel(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 60) return "Good";
  if (score >= 40) return "Average";
  if (score >= 20) return "Poor";
  return "Critical";
}

// No-data color (visible on near-white)
export const NO_DATA_COLOR = "#E2E8F0";

// Party colors (darkened for white-card readability)
const PARTY_COLORS: Record<string, string> = {
  BJP: "#FF6B00",
  INC: "#0066CC",
  AAP: "#0044AA",
  TMC: "#008800",
  DMK: "#CC0000",
  SP: "#CC2200",
  BSP: "#1565C0",
  JDU: "#2E7D32",
  YSRCP: "#0052CC",
  TDP: "#C8A600",
  BJD: "#006600",
  SHS: "#E67E00",
  NCP: "#0000AA",
  RJD: "#1B6E1B",
  CPI: "#CC0000",
  CPIM: "#CC0000",
};

export function getPartyColor(party: string): string {
  const upper = party.toUpperCase().replace(/[^A-Z]/g, "");
  return PARTY_COLORS[upper] ?? "#6B6B6B";
}

// Returns "#FFF" or "#111" based on luminance of the party color
export function getPartyTextColor(party: string): string {
  const hex = getPartyColor(party);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? "#111111" : "#FFFFFF";
}

// Evidence grade colors
const GRADE_COLORS: Record<string, string> = {
  A: "#059669", // emerald
  B: "#00C853", // success green
  C: "#E6A800", // darker amber
  D: "#FF3D00", // primary orange
  E: "#FF1744", // danger red
};

export function getGradeColor(grade: string): string {
  return GRADE_COLORS[grade.toUpperCase()] ?? "#6B6B6B";
}

// Confidence level
export function getConfidenceLevel(
  confidence: number
): "High" | "Medium" | "Low" {
  if (confidence >= 0.7) return "High";
  if (confidence >= 0.4) return "Medium";
  return "Low";
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.7) return "#059669";
  if (confidence >= 0.4) return "#E6A800";
  return "#FF1744";
}
