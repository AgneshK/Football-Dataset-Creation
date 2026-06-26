import * as React from "react";
import { Loader2, AlertCircle, SearchX } from "lucide-react";
import { cn, initials } from "@/lib/utils";

export function Avatar({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground font-mono text-xs font-medium",
        "size-9",
        className
      )}
      aria-hidden
    >
      {initials(name)}
    </div>
  );
}

export function SimilarityMeter({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-foreground/80 transition-[width]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {value.toFixed(3)}
      </span>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} />;
}

export function EmptyState({
  title,
  hint,
  icon: Icon = SearchX,
}: {
  title: string;
  hint?: string;
  icon?: typeof SearchX;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
      <Icon className="size-7 text-muted-foreground/60" />
      <div>
        <p className="text-sm font-medium">{title}</p>
        {hint && <p className="mt-1 text-sm text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-negative/30 bg-[color-mix(in_oklch,var(--negative)_8%,transparent)] p-4 text-sm">
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-negative" />
      <div>
        <p className="font-medium text-negative">Something went wrong</p>
        <p className="mt-0.5 text-muted-foreground">{message}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Is the API running at <span className="font-mono">localhost:8000</span>?
        </p>
      </div>
    </div>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

export function selectClass() {
  return "flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&>option]:bg-popover";
}
