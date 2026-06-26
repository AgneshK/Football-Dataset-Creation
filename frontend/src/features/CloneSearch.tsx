import * as React from "react";
import { Search } from "lucide-react";
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

const EXAMPLES = ["Harry Kane", "Jude Bellingham", "Lamine Yamal", "Alisson"];

export function CloneSearch() {
  const [name, setName] = React.useState("");
  const [league, setLeague] = React.useState("");
  const [maxAge, setMaxAge] = React.useState("");
  const [samePos, setSamePos] = React.useState(true);
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
      const res = await api.findSimilar({
        name: query,
        league: league || undefined,
        max_age: maxAge ? Number(maxAge) : undefined,
        same_position: samePos,
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

  const isGK = data?.player_type === "GK";

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
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Search a player — e.g. Mbappé, Rodri, Alisson…"
              className="h-11 pl-9 text-base"
              autoFocus
            />
          </div>
          <Button type="submit" size="lg" disabled={loading || !name.trim()}>
            {loading ? <Spinner /> : <Search />}
            Find clones
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-[1fr_auto_auto]">
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
          <Field label="Same position">
            <button
              type="button"
              onClick={() => setSamePos((v) => !v)}
              className={selectClass() + " justify-between"}
              style={{ display: "flex", alignItems: "center", width: "7rem" }}
            >
              <span>{samePos ? "On" : "Off"}</span>
              <span
                className={
                  "ml-2 h-4 w-7 rounded-full p-0.5 transition-colors " +
                  (samePos ? "bg-foreground" : "bg-muted-foreground/40")
                }
              >
                <span
                  className={
                    "block size-3 rounded-full bg-background transition-transform " +
                    (samePos ? "translate-x-3" : "")
                  }
                />
              </span>
            </button>
          </Field>
        </div>
      </form>

      {/* results */}
      {error && <ErrorState message={error} />}

      {loading && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px]" />
          ))}
        </div>
      )}

      {!loading && !error && !data && (
        <EmptyState
          title="Find a player's statistical clones"
          hint="Similarity is computed on per-90 style stats, z-scored within position group."
          icon={Search}
        />
      )}

      {!loading && data && !data.ok && (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm font-medium">
            No exact match for “{data.query ?? name}”.
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
            <p className="mt-1 text-sm text-muted-foreground">
              Player not found (needs ≥ 500 minutes in 2024/25).
            </p>
          )}
        </div>
      )}

      {!loading && data?.ok && data.target && (
        <div className="space-y-4">
          {/* target */}
          <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-muted/30 p-4">
            <Avatar name={data.target.player} className="size-11" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h2 className="truncate text-lg font-semibold tracking-tight">
                  {data.target.player}
                </h2>
                {isGK && <Badge variant="outline">GK</Badge>}
              </div>
              <p className="truncate text-sm text-muted-foreground">
                {data.target.squad} · {data.target.league} ·{" "}
                {data.target.position}
                {data.target.age ? ` · ${data.target.age}y` : ""}
              </p>
            </div>
            {data.target.market_value_eur != null && (
              <div className="text-right">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Market value
                </p>
                <p className="font-mono text-lg font-medium tabular-nums">
                  {formatEuro(data.target.market_value_eur)}
                </p>
              </div>
            )}
          </div>

          <p className="text-sm text-muted-foreground">
            {data.count} closest {isGK ? "goalkeepers" : "matches"}
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
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => void run(r.player)}
                    >
                      clones
                    </Button>
                  </div>
                  <SimilarityMeter value={r.similarity} />
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
          <span className="text-xs text-muted-foreground">Try:</span>
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
