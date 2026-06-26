import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { C, eurM } from "./theme";
import { Badge } from "@/components/ui/badge";

const VERDICT_VARIANT = {
  undervalued: "positive",
  overvalued: "negative",
  fair: "muted",
  unknown: "muted",
} as const;

export function ValueCompare({
  actual,
  predicted,
  verdict,
  ratio,
}: {
  actual: number | null | undefined;
  predicted: number | null | undefined;
  verdict?: string | null;
  ratio?: number | null;
}) {
  const data = [
    { name: "Actual", v: eurM(actual), kind: "actual" },
    { name: "Predicted", v: eurM(predicted), kind: "pred" },
  ];
  const predColor =
    verdict === "undervalued" ? C.pos : verdict === "overvalued" ? C.neg : C.fg;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          Market value vs model
        </span>
        {verdict && (
          <Badge
            variant={VERDICT_VARIANT[(verdict as keyof typeof VERDICT_VARIANT)] ?? "muted"}
            className="capitalize"
          >
            {verdict}
            {ratio ? ` · ${ratio}×` : ""}
          </Badge>
        )}
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={72}
            tick={{ fontSize: 12, fill: C.muted }}
            tickLine={false}
            axisLine={false}
          />
          <Bar dataKey="v" radius={[0, 5, 5, 0]} barSize={26} isAnimationActive={false}>
            <Cell fill={C.muted} fillOpacity={0.5} />
            <Cell fill={predColor} />
            <LabelList
              dataKey="v"
              position="right"
              formatter={(v) => `€${Number(v).toFixed(0)}M`}
              style={{ fill: C.muted, fontSize: 11, fontFamily: "var(--font-mono)" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
