import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { AxisScore } from "@/lib/api";
import { C, pretty, tooltip, zToPct } from "./theme";

export function ArchetypeRadar({ axes }: { axes: AxisScore[] }) {
  if (!axes?.length) return null;
  const data = axes.map((a) => ({
    axis: pretty(a.axis),
    Player: Math.round(zToPct(a.player)),
    Archetype: Math.round(zToPct(a.archetype)),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke={C.border} />
        <PolarAngleAxis
          dataKey="axis"
          tick={{ fontSize: 11, fill: C.muted }}
        />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Radar
          name="Archetype avg"
          dataKey="Archetype"
          stroke={C.muted}
          fill={C.muted}
          fillOpacity={0.12}
          isAnimationActive={false}
        />
        <Radar
          name="Player"
          dataKey="Player"
          stroke={C.fg}
          fill={C.fg}
          fillOpacity={0.32}
          isAnimationActive={false}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: C.muted }}
          iconType="plainline"
        />
        <Tooltip
          {...tooltip}
          formatter={(v) => [`${v} pctl`, ""]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
