"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ScoreSnapshot } from "@/lib/trends";

interface TrendChartProps {
  data: ScoreSnapshot[];
  mpName: string;
}

const SCORE_COLORS = {
  score: "#1E293B",
  mplads: "#2563EB",
  assets: "#059669",
  criminal: "#DC2626",
  attendance: "#D97706",
  participation: "#7C3AED",
};

export function TrendChart({ data, mpName }: TrendChartProps) {
  if (data.length < 2) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Score Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ddd" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
              />
              <Tooltip
                contentStyle={{
                  border: "2px solid #1E293B",
                  backgroundColor: "#FAFAFA",
                  fontFamily: "JetBrains Mono",
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, fontFamily: "Space Grotesk" }} />
              <Line
                type="monotone"
                dataKey="score"
                name="Composite"
                stroke={SCORE_COLORS.score}
                strokeWidth={3}
                dot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="mplads"
                name="MPLADS"
                stroke={SCORE_COLORS.mplads}
                strokeWidth={1}
                strokeDasharray="5 5"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="criminal"
                name="Criminal"
                stroke={SCORE_COLORS.criminal}
                strokeWidth={1}
                strokeDasharray="5 5"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-text-muted text-center mt-2">
          Score evolution for {mpName} over time
        </p>
      </CardContent>
    </Card>
  );
}
