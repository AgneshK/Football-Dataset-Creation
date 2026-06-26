import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { AgentRow } from "@/lib/api";
import { C, eurM, tooltip } from "./theme";

interface Pt {
  x: number;
  y: number;
  name: string;
  ratio: number;
  squad: string;
}

function PointTip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div style={tooltip.contentStyle}>
      <div style={{ fontWeight: 600 }}>{p.name}</div>
      <div style={{ color: "var(--muted-foreground)", fontSize: 11 }}>{p.squad}</div>
      <div style={{ marginTop: 4 }}>
        actual €{p.x.toFixed(1)}M · predicted €{p.y.toFixed(1)}M ·{" "}
        <b>{p.ratio}×</b>
      </div>
    </div>
  );
}

export function ValueScatter({ rows }: { rows: AgentRow[] }) {
  const data: Pt[] = rows
    .filter((r) => r.actual_value_eur != null && r.predicted_value_eur != null)
    .map((r) => ({
      x: eurM(r.actual_value_eur),
      y: eurM(r.predicted_value_eur),
      name: r.player,
      ratio: r.ratio ?? 0,
      squad: r.squad,
    }));
  if (!data.length) return null;
  const max = Math.ceil(Math.max(...data.flatMap((d) => [d.x, d.y])) * 1.1);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ left: 4, right: 12, top: 8, bottom: 16 }}>
        <CartesianGrid stroke={C.border} strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="x"
          domain={[0, max]}
          name="actual"
          tick={{ fontSize: 11, fill: C.muted }}
          tickLine={false}
          axisLine={{ stroke: C.border }}
          label={{ value: "Actual €M", position: "insideBottom", offset: -8, fill: C.muted, fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          domain={[0, max]}
          name="predicted"
          tick={{ fontSize: 11, fill: C.muted }}
          tickLine={false}
          axisLine={{ stroke: C.border }}
          label={{ value: "Predicted €M", angle: -90, position: "insideLeft", fill: C.muted, fontSize: 11 }}
        />
        <ZAxis range={[60, 60]} />
        {/* fair-value line: points above it are priced below the model */}
        <ReferenceLine
          segment={[{ x: 0, y: 0 }, { x: max, y: max }]}
          stroke={C.muted}
          strokeDasharray="4 4"
        />
        <Tooltip content={<PointTip />} />
        <Scatter data={data} fill={C.pos} fillOpacity={0.85} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
