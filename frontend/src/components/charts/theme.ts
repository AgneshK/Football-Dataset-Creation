// Shared chart styling — everything resolves to the app's CSS-variable palette
// so charts track light/dark automatically.
export const C = {
  fg: "var(--foreground)",
  muted: "var(--muted-foreground)",
  border: "var(--border)",
  pos: "var(--positive)",
  neg: "var(--negative)",
  card: "var(--card)",
};

export const tooltip = {
  contentStyle: {
    background: "var(--popover)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    fontSize: 12,
    color: "var(--popover-foreground)",
    boxShadow: "0 6px 24px rgb(0 0 0 / 0.14)",
    padding: "8px 10px",
  } as React.CSSProperties,
  labelStyle: { color: "var(--muted-foreground)", marginBottom: 4 } as React.CSSProperties,
  itemStyle: { color: "var(--popover-foreground)", padding: 0 } as React.CSSProperties,
};

export const eurM = (v: number | null | undefined) =>
  v == null ? 0 : v / 1_000_000;

// z-score -> 0..100 (logistic). Monotonic, so radar comparisons stay faithful.
export const zToPct = (z: number) => 100 / (1 + Math.exp(-z));

export const pretty = (s: string) =>
  s.charAt(0).toUpperCase() + s.slice(1);
