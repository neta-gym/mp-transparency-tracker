import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#FAFAFA",
        surface: "#FFFFFF",
        ink: "#1E293B",
        card: "#FFFFFF",
        "card-hover": "#FEF3C7",
        border: "#1E293B",
        "text-primary": "#0F172A",
        "text-secondary": "#475569",
        "text-muted": "#94A3B8",
        primary: "#FF3D00",
        secondary: "#00D1FF",
        accent: "#B6FF00",
        highlight: "#FEF9C3",
        info: "#7C4DFF",
        success: "#00C853",
        warning: "#FFAB00",
        danger: "#FF1744",
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
        sans: ['"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      borderWidth: {
        3: "3px",
        4: "4px",
        5: "5px",
      },
      boxShadow: {
        "brutal-sm": "2px 2px 0 0 #CBD5E1",
        brutal: "3px 3px 0 0 #CBD5E1",
        "brutal-lg": "4px 4px 0 0 #CBD5E1",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
