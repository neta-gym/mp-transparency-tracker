"use client";

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { getScoreColor } from "@/lib/colors";
import type { ScoreBreakdown } from "@/lib/types";
import { SCORE_COMPONENTS } from "@/lib/types";

interface ScoreRadarProps {
  breakdown: ScoreBreakdown;
  compositeScore: number;
}

export function ScoreRadar({ breakdown, compositeScore }: ScoreRadarProps) {
  const color = getScoreColor(compositeScore);

  const data = SCORE_COMPONENTS.map((comp) => ({
    subject: `${comp.label} (${Math.round(comp.weight * 100)}%)`,
    value: breakdown[comp.key],
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
        <PolarGrid stroke="#1E293B" strokeWidth={2} />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: "#1E293B", fontSize: 12, fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif" }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={{ fill: "#94A3B8", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.5}
          strokeWidth={3}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#FFFFFF",
            border: "3px solid #1E293B",
            borderRadius: "0px",
            color: "#0F172A",
            boxShadow: "3px 3px 0 0 #CBD5E1",
            fontFamily: "'JetBrains Mono', monospace",
          }}
          formatter={(value: number) => [`${value.toFixed(1)}`, "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
