import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AgentRow } from "@/lib/api";
import { C, tooltip } from "./theme";

export function SimilarityBars({ rows }: { rows: AgentRow[] }) {
  const data = rows.slice(0, 10).map((r) => ({
    name: r.player,
    similarity: r.similarity ?? 0,
    squad: r.squad,
    value: r.market_value_eur,
  }));
  if (!data.length) return null;

  return (
    <ResponsiveContainer width="100%" height={Math.max(150, data.length * 34)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ left: 6, right: 40, top: 4, bottom: 4 }}
        barCategoryGap={6}
      >
        <XAxis type="number" domain={[0, 1]} hide />
        <YAxis
          type="category"
          dataKey="name"
          width={128}
          tick={{ fontSize: 12, fill: C.muted }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          {...tooltip}
          cursor={{ fill: "var(--muted)", opacity: 0.35 }}
          formatter={(v) => [Number(v).toFixed(3), "similarity"]}
        />
        <Bar dataKey="similarity" radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {data.map((d, i) => (
            <Cell key={i} fill={C.fg} fillOpacity={0.55 + 0.45 * d.similarity} />
          ))}
          <LabelList
            dataKey="similarity"
            position="right"
            formatter={(v) => Number(v).toFixed(2)}
            style={{ fill: C.muted, fontSize: 11, fontFamily: "var(--font-mono)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
