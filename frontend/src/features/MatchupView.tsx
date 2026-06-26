import * as React from "react";
import { Shield, Swords } from "lucide-react";
import { api, LEAGUES, type SearchResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Avatar,
  SimilarityMeter,
  EmptyState,
  ErrorState,
  Field,
  Spinner,
  selectClass,
} from "@/components/shared";
import { formatEuro } from "@/lib/utils";

const EXAMPLES = ["Haaland", "Mbappé", "Vinícius", "Kane"];
const ROLES = [
  { value: "", label: "Any defender" },
  { value: "CB", label: "Centre-backs" },
  { value: "FB", label: "Full-backs" },
  { value: "DM", label: "Defensive mids" },
  { value: "DF", label: "All defenders" },
  { value: "MF", label: "All midfielders" },
];

export function MatchupView() {
  const [name, setName] = React.useState("");
  const [league, setLeague] = React.useState("");
  const [maxAge, setMaxAge] = React.useState("");
  const [pos, setPos] = React.useState("");
  const [data, setData] = React.useState<SearchResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function run(q?: string) {
    const query = (q ?? name).trim();
    if (!query) return;
    setName(query);
    setLoading(true);
    setError(null);
    try {
      const res = await api.counter(query, {
        league: league || undefined,
        max_age: maxAge ? Number(maxAge) : undefined,
        pos: pos || undefined,
        top_n: 12,
      });
      setData(res);
    } catch (e) {
      setError((e as Error).message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* search bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
        className="space-y-4"
      >
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Swords className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name the attacker to stop — e.g. Haaland, Mbappé…"
              className="h-11 pl-9 text-base"
              autoFocus
            />
          </div>
          <Button type="submit" size="lg" disabled={loading || !name.trim()}>
            {loading ? <Spinner /> : <Shield />}
            Find stoppers
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <Field label="Role">
            <select
              className={selectClass()}
              value={pos}
              onChange={(e) => setPos(e.target.value)}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
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
              className="w-24"
            />
          </Field>
        </div>
      </form>

      {/* results */}
      {error && <ErrorState message={error} />}

      {loading && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[112px]" />
          ))}
        </div>
      )}

      {!loading && !error && !data && (
        <EmptyState
          title="Find defenders to neutralise an attacker"
          hint="We profile what makes the attacker dangerous, then rank defenders by the defensive traits that counter those specific threats."
          icon={Shield}
        />
      )}

      {!loading && data && !data.ok && (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm font-medium">
            {data.error === "empty_pool"
              ? "No defenders match those filters."
              : `No exact match for “${data.query ?? name}”.`}
          </p>
          {data.suggestions && data.suggestions.length > 0 ? (
            <>
              <p className="mt-1 text-sm text-muted-foreground">Did you mean:</p>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {data.suggestions.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    onClick={() => void run(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </>
          ) : (
            data.error !== "empty_pool" && (
              <p className="mt-1 text-sm text-muted-foreground">
                Attacker not found (needs ≥ 500 minutes in 2024/25).
              </p>
            )
          )}
        </div>
      )}

      {!loading && data?.ok && data.target && (
        <div className="space-y-4">
          {/* attacker + threat profile */}
          <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Avatar name={data.target.player} className="size-11" />
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold tracking-tight">
                  Stopping {data.target.player}
                </h2>
                <p className="truncate text-sm text-muted-foreground">
                  {data.target.squad} · {data.target.league} ·{" "}
                  {data.target.position}
                  {data.target.age ? ` · ${data.target.age}y` : ""}
                </p>
              </div>
            </div>
            {data.threat && data.threat.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Threats:</span>
                {data.threat
                  .filter((t) => t.weight > 0)
                  .map((t) => (
                    <Badge key={t.axis} variant="outline">
                      {t.label} · {Math.round(t.weight * 100)}%
                    </Badge>
                  ))}
              </div>
            )}
          </div>

          <p className="text-sm text-muted-foreground">
            {data.count} best-matched defenders by counter fit
          </p>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.results?.map((r, i) => (
              <Card
                key={`${r.player}-${i}`}
                className="transition-colors hover:border-foreground/20"
              >
                <CardContent className="flex flex-col gap-3 p-4">
                  <div className="flex items-center gap-3">
                    <Avatar name={r.player} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{r.player}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {r.squad} · {r.league}
                      </p>
                    </div>
                  </div>
                  <SimilarityMeter value={r.similarity} />
                  {r.strengths && r.strengths.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {r.strengths.map((s) => (
                        <Badge key={s} variant="muted" className="text-[10px]">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {r.position}
                      {r.age ? ` · ${r.age}y` : ""}
                    </span>
                    {r.market_value_eur != null && (
                      <span className="font-mono tabular-nums text-foreground/80">
                        {formatEuro(r.market_value_eur)}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {!loading && !data && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">Try stopping:</span>
          {EXAMPLES.map((ex) => (
            <Button
              key={ex}
              variant="secondary"
              size="sm"
              onClick={() => void run(ex)}
            >
              {ex}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
