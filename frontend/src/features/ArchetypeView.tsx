import * as React from "react";
import { Fingerprint, Search } from "lucide-react";
import { api, type ArchetypeResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, EmptyState, ErrorState, Spinner } from "@/components/shared";

const EXAMPLES = ["Rodri", "Virgil van Dijk", "Florian Wirtz"];

function prettyStat(s: string): string {
  return s
    .replace(/_per90$/, " /90")
    .replace(/_pct$/, " %")
    .replace(/_/g, " ");
}

export function ArchetypeView() {
  const [name, setName] = React.useState("");
  const [data, setData] = React.useState<ArchetypeResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function run(q?: string) {
    const query = (q ?? name).trim();
    if (!query) return;
    setName(query);
    setLoading(true);
    setError(null);
    try {
      setData(await api.archetype(query));
    } catch (e) {
      setError((e as Error).message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  const fit = data?.archetype?.fit ?? null;

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="What kind of player is…? e.g. Rodri"
            className="h-11 pl-9 text-base"
          />
        </div>
        <Button type="submit" size="lg" disabled={loading || !name.trim()}>
          {loading ? <Spinner /> : <Fingerprint />}
          Analyse
        </Button>
      </form>

      {error && <ErrorState message={error} />}
      {loading && <Skeleton className="h-64" />}

      {!loading && !error && !data && (
        <EmptyState
          title="Identify a player's statistical archetype"
          hint="Players are clustered within position group; each archetype is named by its dominant stats."
          icon={Fingerprint}
        />
      )}

      {!loading && data && !data.ok && (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm font-medium">
            No match for “{data.query ?? name}”.
          </p>
          {data.suggestions && data.suggestions.length > 0 && (
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
          )}
        </div>
      )}

      {!loading && data?.ok && data.target && data.archetype && (
        <div className="grid gap-4 lg:grid-cols-5">
          <Card className="lg:col-span-3">
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <Avatar name={data.target.player} className="size-11" />
                <div className="min-w-0">
                  <p className="truncate font-semibold">{data.target.player}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {data.target.squad} · {data.target.league}
                  </p>
                </div>
              </div>

              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Archetype · {data.archetype.pos_group}
                </p>
                <h2 className="mt-1 text-2xl font-semibold tracking-tight">
                  {data.archetype.archetype}
                </h2>
              </div>

              {fit != null && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="uppercase tracking-wide text-muted-foreground">
                      Fit to archetype
                    </span>
                    <span className="font-mono tabular-nums">
                      {(fit * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-foreground/80"
                      style={{ width: `${Math.round(fit * 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {fit >= 0.66
                      ? "A textbook example of this style."
                      : fit >= 0.33
                        ? "A clear member of this cluster."
                        : "An atypical / blended profile."}
                  </p>
                </div>
              )}

              <div>
                <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                  Signature stats
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {data.archetype.signature.map((s) => (
                    <Badge key={s} variant="muted" className="font-mono">
                      {prettyStat(s)}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardContent className="p-5">
              <p className="mb-3 text-xs uppercase tracking-wide text-muted-foreground">
                Most representative of this archetype
              </p>
              <div className="space-y-1">
                {data.peers?.map((p) => (
                  <button
                    key={p.player}
                    onClick={() => void run(p.player)}
                    className="flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-accent"
                  >
                    <Avatar name={p.player} className="size-8" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{p.player}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {p.squad}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
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
