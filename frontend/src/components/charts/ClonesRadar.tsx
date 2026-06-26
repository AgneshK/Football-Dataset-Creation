import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { RadarData } from "@/lib/api";
import { C, pretty, tooltip, zToPct } from "./theme";

const MATCH_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)"];

export function ClonesRadar({ radar }: { radar: RadarData }) {
  const { axes, series } = radar;
  if (!axes?.length || series?.length < 2) return null;

  // one row per axis; one numeric key per player (percentile of the z-score)
  const data = axes.map((ax, i) => {
    const row: Record<string, number | string> = { axis: pretty(ax) };
    for (const s of series) row[s.player] = Math.round(zToPct(s.values[i] ?? 0));
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={360}>
      <RadarChart data={data} outerRadius="68%" margin={{ top: 8, bottom: 8 }}>
        <PolarGrid stroke={C.border} />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: C.muted }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        {series.map((s, i) => {
          const color = s.target ? C.fg : MATCH_COLORS[(i - 1) % MATCH_COLORS.length];
          return (
            <Radar
              key={s.player}
              name={s.player + (s.target ? " (target)" : "")}
              dataKey={s.player}
              stroke={color}
              fill={color}
              fillOpacity={s.target ? 0.3 : 0.08}
              strokeWidth={s.target ? 2.5 : 1.5}
              isAnimationActive={false}
            />
          );
        })}
        <Legend
          wrapperStyle={{ fontSize: 11, color: C.muted, paddingTop: 6 }}
          iconType="plainline"
        />
        <Tooltip {...tooltip} formatter={(v) => [`${v} pctl`, ""]} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
