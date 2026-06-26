import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatResult } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SimilarityBars } from "@/components/charts/SimilarityBars";
import { ClonesRadar } from "@/components/charts/ClonesRadar";
import { ValueScatter } from "@/components/charts/ValueScatter";
import { ValueCompare } from "@/components/charts/ValueCompare";
import { ArchetypeRadar } from "@/components/charts/ArchetypeRadar";
import { formatEuro } from "@/lib/utils";

const ROLE_ORDER = ["GK", "DF", "MF", "FW"];

function SquadLineup({ result }: { result: ChatResult }) {
  const lineup = (result.lineup ?? []).filter((s) => s.player);
  const byRole = ROLE_ORDER.map((role) => ({
    role,
    players: lineup.filter((s) => s.role === role),
  })).filter((g) => g.players.length);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {result.formation && (
          <Badge variant="outline" className="font-mono">
            {result.formation}
          </Badge>
        )}
        {result.total_value_eur != null && (
          <span className="text-muted-foreground">
            Total:{" "}
            <span className="font-mono text-foreground">
              {formatEuro(result.total_value_eur)}
            </span>
            {result.budget_eur != null && (
              <>
                {" "}
                / {formatEuro(result.budget_eur)}{" "}
                <span className={result.within_budget ? "text-positive" : "text-negative"}>
                  {result.within_budget ? "✓ within budget" : "✗ over budget"}
                </span>
              </>
            )}
          </span>
        )}
      </div>
      {byRole.map(({ role, players }) => (
        <div key={role} className="space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {role}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {players.map((s, i) => (
              <div
                key={`${s.player}-${i}`}
                className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{s.player}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {s.squad}
                    {s.age ? ` · ${s.age}y` : ""}
                  </p>
                </div>
                {s.market_value_eur != null && (
                  <span className="shrink-0 font-mono text-xs tabular-nums text-foreground/80">
                    {formatEuro(s.market_value_eur)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function VizCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {title}
        </p>
        {children}
      </CardContent>
    </Card>
  );
}

function CompareTable({
  players,
  metrics,
  leaders,
}: {
  players: NonNullable<ChatResult["players"]>;
  metrics: string[];
  leaders: Record<string, string>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-xs text-muted-foreground">
            <th className="py-1.5 pr-3 text-left font-medium">Metric</th>
            {players.map((p) => (
              <th key={p.player} className="px-3 py-1.5 text-right font-medium">
                {p.player}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m} className="border-b border-border/50">
              <td className="py-1.5 pr-3 font-mono text-xs text-muted-foreground">
                {m}
              </td>
              {players.map((p) => {
                const v = p.stats[m];
                const lead = leaders[m] === p.player;
                return (
                  <td
                    key={p.player}
                    className={
                      "px-3 py-1.5 text-right font-mono tabular-nums " +
                      (lead ? "font-semibold text-foreground" : "text-muted-foreground")
                    }
                  >
                    {v == null ? "—" : v}
                    {lead && " ★"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function chartFor(result: ChatResult) {
  const { intent, results, archetype } = result;
  if (intent === "squad" && result.lineup && result.lineup.length) {
    return (
      <VizCard title="Squad">
        <SquadLineup result={result} />
      </VizCard>
    );
  }
  if (intent === "compare" && result.players && result.players.length >= 2) {
    return (
      <div className="space-y-3">
        {result.radar && result.radar.series.length > 1 && (
          <VizCard title="Style profile (percentile within position)">
            <ClonesRadar radar={result.radar} />
          </VizCard>
        )}
        <VizCard title="Head-to-head — ★ marks the leader">
          <CompareTable
            players={result.players}
            metrics={result.metrics ?? []}
            leaders={result.leaders ?? {}}
          />
        </VizCard>
      </div>
    );
  }
  if (intent === "discover" && results.length) {
    return (
      <div className="space-y-3">
        {result.metrics && result.metrics.length > 0 && (
          <VizCard title="Ranked by">
            <div className="flex flex-wrap gap-1.5">
              {result.metrics.map((m) => (
                <Badge key={m} variant="outline" className="font-mono text-[11px]">
                  {m}
                </Badge>
              ))}
            </div>
          </VizCard>
        )}
        <VizCard title="Trait fit (relative to the filtered pool)">
          <SimilarityBars rows={results} />
        </VizCard>
      </div>
    );
  }
  if (intent === "counter" && results.length) {
    return (
      <div className="space-y-3">
        {result.threat && result.threat.length > 0 && (
          <VizCard title={`Threat profile — ${result.target?.player ?? "attacker"}`}>
            <div className="flex flex-wrap gap-1.5">
              {result.threat
                .filter((t) => t.weight > 0)
                .map((t) => (
                  <Badge key={t.axis} variant="outline">
                    {t.label} · {Math.round(t.weight * 100)}%
                  </Badge>
                ))}
            </div>
          </VizCard>
        )}
        <VizCard title="Counter fit (relative to all defenders)">
          <SimilarityBars rows={results} />
        </VizCard>
      </div>
    );
  }
  if ((intent === "clone" || intent === "budget") && results.length) {
    const radar = result.radar;
    return (
      <div className="space-y-3">
        {radar && radar.series.length > 1 && (
          <VizCard title="Style profile — target vs top 3 (percentile within position)">
            <ClonesRadar radar={radar} />
          </VizCard>
        )}
        <VizCard title="Similarity to target">
          <SimilarityBars rows={results} />
        </VizCard>
      </div>
    );
  }
  if (intent === "value") {
    if (results.length) {
      return (
        <VizCard title="Predicted vs market value — above the line = underpriced">
          <ValueScatter rows={results} />
        </VizCard>
      );
    }
    if (result.predicted_value_eur != null) {
      return (
        <VizCard title="Valuation">
          <ValueCompare
            actual={result.actual_value_eur}
            predicted={result.predicted_value_eur}
            verdict={result.verdict}
            ratio={result.ratio}
          />
        </VizCard>
      );
    }
  }
  if (intent === "archetype" && archetype?.axes?.length) {
    return (
      <VizCard title={`Style profile · ${archetype.archetype}`}>
        <ArchetypeRadar axes={archetype.axes} />
      </VizCard>
    );
  }
  return null;
}

export function AgentMessage({ result }: { result: ChatResult }) {
  // intel: grounded markdown brief + clickable source chips
  if (result.intent === "intel") {
    const body = result.answer.split(/\n\nSources:/)[0];
    return (
      <div className="space-y-3">
        <div className="md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
        </div>
        {result.sources && result.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {result.sources.map((s, i) => (
              <a key={i} href={s.uri} target="_blank" rel="noreferrer noopener">
                <Badge
                  variant="outline"
                  className="max-w-[220px] truncate hover:bg-accent"
                >
                  {s.title}
                </Badge>
              </a>
            ))}
          </div>
        )}
      </div>
    );
  }

  // everything else: the prose report + a tailored chart
  return (
    <div className="space-y-3">
      <p className="whitespace-pre-wrap text-sm leading-relaxed">
        {result.answer}
      </p>
      {chartFor(result)}
    </div>
  );
}
