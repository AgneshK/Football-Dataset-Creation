import * as React from "react";
import { Shirt } from "lucide-react";
import { api, LEAGUES, type SquadResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, Field, Spinner, selectClass } from "@/components/shared";
import { formatEuro } from "@/lib/utils";

const FORMATIONS = ["4-3-3", "4-4-2", "4-2-3-1", "3-5-2", "3-4-3", "5-3-2", "4-3-1-2"];
const ROLE_ORDER = ["GK", "DF", "MF", "FW"];
const STYLE_EXAMPLES = ["that presses high", "creative and progressive", "physical and defensive"];

export function SquadBuilder() {
  const [formation, setFormation] = React.useState("4-3-3");
  const [budgetM, setBudgetM] = React.useState(600);
  const [style, setStyle] = React.useState("");
  const [league, setLeague] = React.useState("");
  const [maxAge, setMaxAge] = React.useState("");
  const [data, setData] = React.useState<SquadResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.squad({
        formation,
        budget_eur: budgetM * 1_000_000,
        query: style.trim() || undefined,
        league: league || undefined,
        max_age: maxAge ? Number(maxAge) : undefined,
      });
      setData(res);
    } catch (e) {
      setError((e as Error).message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  const lineup = (data?.lineup ?? []).filter((s) => s.player);
  const byRole = ROLE_ORDER.map((role) => ({
    role,
    players: lineup.filter((s) => s.role === role),
  })).filter((g) => g.players.length);

  return (
    <div className="space-y-6">
      {/* controls */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
        className="space-y-4"
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Formation">
            <select
              className={selectClass()}
              value={formation}
              onChange={(e) => setFormation(e.target.value)}
            >
              {FORMATIONS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </Field>
          <Field label="League">
            <select
              className={selectClass()}
              value={league}
              onChange={(e) => setLeague(e.target.value)}
            >
              <option value="">All leagues</option>
              {LEAGUES.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Max age">
            <Input
              type="number"
              min={15}
              max={45}
              value={maxAge}
              onChange={(e) => setMaxAge(e.target.value)}
              placeholder="any"
            />
          </Field>
          <Field label={`Budget · ${formatEuro(budgetM * 1_000_000)}`}>
            <input
              type="range"
              min={50}
              max={1500}
              step={10}
              value={budgetM}
              onChange={(e) => setBudgetM(Number(e.target.value))}
              className="h-9 w-full accent-foreground"
            />
          </Field>
        </div>

        <div className="flex gap-2">
          <div className="flex-1">
            <Input
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              placeholder="Style (optional) — e.g. ‘that presses high’, ‘creative and progressive’"
              className="h-11 text-base"
            />
          </div>
          <Button type="submit" size="lg" disabled={loading}>
            {loading ? <Spinner /> : <Shirt />}
            Build squad
          </Button>
        </div>

        {!style && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Style ideas:</span>
            {STYLE_EXAMPLES.map((s) => (
              <Button
                key={s}
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setStyle(s)}
              >
                {s}
              </Button>
            ))}
          </div>
        )}
      </form>

      {/* results */}
      {error && <ErrorState message={error} />}

      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      )}

      {!loading && !error && !data && (
        <EmptyState
          title="Build a lineup within a budget"
          hint="Pick a formation and budget, optionally describe a style, and the engine fills each role with the best statistical fit it can afford."
          icon={Shirt}
        />
      )}

      {!loading && data && !data.ok && (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm">
          {data.message ?? "Couldn't build that squad."}
        </div>
      )}

      {!loading && data?.ok && (
        <div className="space-y-4">
          {/* summary */}
          <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-muted/30 p-4">
            <Badge variant="outline" className="font-mono text-sm">
              {data.formation ?? "XI"}
            </Badge>
            {data.total_value_eur != null && (
              <span className="text-sm text-muted-foreground">
                Total{" "}
                <span className="font-mono text-foreground">
                  {formatEuro(data.total_value_eur)}
                </span>
                {data.budget_eur != null && (
                  <>
                    {" / "}
                    {formatEuro(data.budget_eur)}{" "}
                    <span className={data.within_budget ? "text-positive" : "text-negative"}>
                      {data.within_budget ? "✓ within budget" : "✗ over budget"}
                    </span>
                  </>
                )}
              </span>
            )}
            {data.style_metrics && data.style_metrics.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {data.style_metrics.map((m) => (
                  <Badge key={m} variant="muted" className="font-mono text-[10px]">
                    {m}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {data.note && (
            <p className="text-xs text-muted-foreground">{data.note}</p>
          )}

          {/* lineup by role */}
          {byRole.map(({ role, players }) => (
            <div key={role} className="space-y-1.5">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {role}
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
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
      )}
    </div>
  );
}
