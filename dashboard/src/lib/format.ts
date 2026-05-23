/** Format a number in Indian currency notation (Crore/Lakh) */
export function formatINR(amount: number | null | undefined): string {
  if (amount == null) return "N/A";

  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";

  if (abs >= 1e7) {
    const crore = abs / 1e7;
    return `${sign}\u20B9${crore.toFixed(2)} Cr`;
  }
  if (abs >= 1e5) {
    const lakh = abs / 1e5;
    return `${sign}\u20B9${lakh.toFixed(2)} L`;
  }
  if (abs >= 1e3) {
    return `${sign}\u20B9${(abs / 1e3).toFixed(1)}K`;
  }
  return `${sign}\u20B9${abs.toLocaleString("en-IN")}`;
}

/** Format a value that is already in crores (e.g., MPLADS fund data from eSAKSHI) */
export function formatCrore(amount: number | null | undefined): string {
  if (amount == null) return "N/A";
  return `\u20B9${amount.toFixed(2)} Cr`;
}

/** Format percentage */
export function formatPercent(
  value: number | null | undefined,
  decimals = 1
): string {
  if (value == null) return "N/A";
  return `${value.toFixed(decimals)}%`;
}

/** Format confidence as percentage */
export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Format a score with one decimal */
export function formatScore(score: number): string {
  return score.toFixed(1);
}

/** Format a date string */
export function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/** Format growth ratio as percentage */
export function formatGrowth(ratio: number | null | undefined): string {
  if (ratio == null) return "N/A";
  const pct = ratio * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}
