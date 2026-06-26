import * as React from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

export function Header() {
  const [online, setOnline] = React.useState<boolean | null>(null);
  const [players, setPlayers] = React.useState<number | null>(null);

  React.useEffect(() => {
    api
      .health()
      .then((h) => {
        setOnline(true);
        if (typeof h.players_loaded === "number") setPlayers(h.players_loaded);
      })
      .catch(() => setOnline(false));
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-7 items-center justify-center rounded-md bg-foreground text-background font-mono text-sm font-bold">
            S
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-[15px] font-semibold tracking-tight">
              Scout
            </span>
            <span className="hidden font-mono text-xs text-muted-foreground sm:inline">
              ai football scouting
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="mr-1 hidden items-center gap-1.5 text-xs text-muted-foreground md:flex">
            <span
              className={cn(
                "size-2 rounded-full",
                online === null && "bg-muted-foreground/40",
                online === true && "bg-positive",
                online === false && "bg-negative"
              )}
            />
            <span className="font-mono">
              {online === null
                ? "connecting…"
                : online
                  ? players
                    ? `${players.toLocaleString()} players`
                    : "online"
                  : "api offline"}
            </span>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
