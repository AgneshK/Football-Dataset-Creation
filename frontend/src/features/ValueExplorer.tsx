import * as React from "react";
import { Search, TrendingUp, Banknote } from "lucide-react";
import {
  api,
  LEAGUES,
  type ValueReport,
  type UndervaluedResult,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Avatar,
  ErrorState,
  Field,
  Spinner,
  selectClass,
} from "@/components/shared";
import { formatEuro } from "@/lib/utils";

const VERDICT_VARIANT = {
  undervalued: "positive",
  overvalued: "negative",
  fair: "muted",
  unknown: "muted",
} as const;

export function ValueExplorer() {
  // ---- single player verdict ----
  const [name, setName] = React.useState("");
  const [report, setReport] = React.useState<ValueReport | null>(null);
  const [vLoading, setVLoading] = React.useState(false);
  const [vError, setVError] = React.useState<string | null>(null);

  async function lookup(q?: string) {
    const query = (q ?? name).trim();
    if (!query) return;
    setName(query);
    setVLoading(true);
    setVError(null);
    try {
      setReport(await api.valueReport(query));
    } catch (e) {
      setVError((e as Error).message);
      setReport(null);
    } finally {
      setVLoading(false);
    }
  }

  // ---- undervalued board ----
  const [league, setLeague] = React.useState("");
  const [pos, setPos] = React.useState("");
  const [board, setBoard] = React.useState<UndervaluedResult | null>(null);
  const [bLoading, setBLoading] = React.useState(false);
  const [bError, setBError] = React.useState<string | null>(null);

  const loadBoard = React.useCallback(async () => {
    setBLoading(true);
    setBError(null);
    try {
      setBoard(
        await api.undervalued({
          league: league || undefined,
          pos_group: pos || undefined,
          top_n: 12,
        })
      );
    } catch (e) {
      setBError((e as Error).message);
      setBoard(null);
    } finally {
      setBLoading(false);
    }
  }, [league, pos]);

  React.useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  return (
    <div className="space-y-8">
      {/* verdict */}
      <section className="space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void lookup();
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Value a player — predicted vs market price"
              className="h-11 pl-9 text-base"
            />
          </div>
          <Button type="submit" size="lg" disabled={vLoading || !name.trim()}>
            {vLoading ? <Spinner /> : <Banknote />}
            Value
          </Button>
        </form>

        {vError && <ErrorState message={vError} />}
        {vLoading && <Skeleton className="h-28" />}

        {!vLoading && report?.ok && report.target && (
          <Card>
            <CardContent className="flex flex-wrap items-center gap-5 p-5">
              <Avatar name={report.target.player} className="size-11" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{report.target.player}</p>
                <p className="truncate text-sm text-muted-foreground">
                  {report.target.squad} · {report.target.position}
                </p>
              </div>
              <Stat label="Actual" value={formatEuro(report.actual_value_eur)} />
              <Stat
                label="Predicted"
                value={formatEuro(report.predicted_value_eur)}
              />
              <div className="text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Verdict
                </p>
                <Badge
                  variant={VERDICT_VARIANT[report.verdict ?? "unknown"]}
                  className="mt-1 capitalize"
                >
                  {report.verdict}
                  {report.ratio ? ` · ${report.ratio}×` : ""}
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}
        {!vLoading && report && !report.ok && (
          <p className="text-sm text-muted-foreground">
            No match for “{name}”.
            {report.suggestions?.length
              ? ` Try: ${report.suggestions.slice(0, 4).join(", ")}.`
              : ""}
          </p>
        )}
      </section>

      {/* undervalued board */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" />
            <h2 className="font-semibold tracking-tight">Most undervalued</h2>
          </div>
          <div className="flex items-end gap-3">
            <Field label="League">
              <select
                className={selectClass() + " w-40"}
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
            <Field label="Position">
              <select
                className={selectClass() + " w-28"}
                value={pos}
                onChange={(e) => setPos(e.target.value)}
              >
                <option value="">All</option>
                <option value="DF">Defenders</option>
                <option value="MF">Midfielders</option>
                <option value="FW">Forwards</option>
              </select>
            </Field>
          </div>
        </div>

        {bError && <ErrorState message={bError} />}
        {bLoading && <Skeleton className="h-72" />}

        {!bLoading && board?.ok && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2.5 text-left font-medium">Player</th>
                    <th className="px-4 py-2.5 text-left font-medium">Pos</th>
                    <th className="px-4 py-2.5 text-right font-medium">Actual</th>
                    <th className="px-4 py-2.5 text-right font-medium">
                      Predicted
                    </th>
                    <th className="px-4 py-2.5 text-right font-medium">Upside</th>
                  </tr>
                </thead>
                <tbody>
                  {board.results?.map((r, i) => (
                    <tr
                      key={`${r.player}-${i}`}
                      className="border-b last:border-0 hover:bg-muted/40"
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <Avatar name={r.player} className="size-7" />
                          <div className="min-w-0">
                            <p className="truncate font-medium">{r.player}</p>
                            <p className="truncate text-xs text-muted-foreground">
                              {r.squad}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {r.position}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                        {formatEuro(r.actual_value_eur)}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                        {formatEuro(r.predicted_value_eur)}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Badge variant="positive" className="font-mono">
                          {r.ratio}×
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        {!bLoading && board && !board.ok && (
          <ErrorState
            message={
              board.message ?? "Value model unavailable — train it first."
            }
          />
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 font-mono text-base font-medium tabular-nums">
        {value}
      </p>
    </div>
  );
}
