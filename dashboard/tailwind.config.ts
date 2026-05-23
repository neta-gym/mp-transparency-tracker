import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#F8FAFC",
        surface: "#FFFFFF",
        ink: "#0F172A",
        card: "#FFFFFF",
        "card-hover": "#F8FAFC",
        border: "#E2E8F0",
        "text-primary": "#0F172A",
        "text-secondary": "#475569",
        "text-muted": "#64748B",
        primary: "#4F46E5",
        secondary: "#0EA5E9",
        accent: "#22C55E",
        highlight: "#EEF2FF",
        info: "#6366F1",
        success: "#16A34A",
        warning: "#D97706",
        danger: "#DC2626",
        "score-critical": "#FF1744",
        "score-poor": "#FF3D00",
        "score-average": "#FFAB00",
        "score-good": "#00C853",
        "score-excellent": "#059669",
        "party-bjp": "#FF6B00",
        "party-inc": "#0066CC",
        "party-aap": "#0044AA",
        "party-tmc": "#008800",
        "party-dmk": "#CC0000",
        "party-sp": "#CC2200",
        "party-bsp": "#1565C0",
        "party-other": "#6B6B6B",
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      borderWidth: {
        3: "3px",
        4: "4px",
        5: "5px",
      },
      boxShadow: {
        "brutal-sm": "0 1px 2px 0 rgba(15, 23, 42, 0.06), 0 1px 1px 0 rgba(15, 23, 42, 0.04)",
        brutal: "0 8px 24px -12px rgba(15, 23, 42, 0.22)",
        "brutal-lg": "0 12px 30px -14px rgba(15, 23, 42, 0.28)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
