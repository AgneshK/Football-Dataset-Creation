// Thin typed client over the FastAPI backend.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} · ${detail}`);
  }
  return (await res.json()) as T;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} · ${res.statusText}`);
  return (await res.json()) as T;
}

function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// ---- types ----
export interface PlayerRef {
  player: string;
  squad: string;
  league: string;
  position: string;
  age: number | null;
}
export interface CloneHit extends PlayerRef {
  similarity: number;
  market_value_eur?: number | null;
  // counter intent extras
  counter_score?: number;
  strengths?: string[];
}
export interface SearchResult {
  ok: boolean;
  player_type?: string;
  target?: PlayerRef & { market_value_eur?: number | null };
  results?: CloneHit[];
  count?: number;
  error?: string;
  query?: string;
  suggestions?: string[];
  radar?: RadarData;
  threat?: ThreatAxis[];
  _note?: string;
}
export interface AxisScore {
  axis: string;
  player: number;
  archetype: number;
}
export interface ArchetypeInfo {
  pos_group: string;
  archetype: string;
  cluster: number;
  signature: string[];
  fit: number | null;
  axes?: AxisScore[];
}
export interface AgentRow extends PlayerRef {
  similarity?: number;
  market_value_eur?: number | null;
  actual_value_eur?: number;
  predicted_value_eur?: number;
  ratio?: number;
  // counter intent
  counter_score?: number;
  strengths?: string[];
  // discover intent
  trait_score?: number;
  stats?: Record<string, number | null>;
}
export interface ThreatAxis {
  axis: string;
  label: string;
  weight: number;
}
export interface ComparePlayer extends PlayerRef {
  market_value_eur?: number | null;
  stats: Record<string, number | null>;
}
export interface SquadSlot {
  role: string;
  player: string | null;
  squad?: string;
  league?: string;
  position?: string;
  age?: number | null;
  market_value_eur?: number | null;
  fit?: number;
}
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}
export interface SquadResult {
  ok: boolean;
  mode?: string;
  formation?: string | null;
  roles?: Record<string, number>;
  budget_eur?: number | null;
  total_value_eur?: number | null;
  within_budget?: boolean | null;
  style_metrics?: string[];
  count?: number;
  lineup?: SquadSlot[];
  note?: string | null;
  error?: string;
  message?: string;
}
export interface Source {
  title: string;
  uri: string;
}
export interface RadarSeries {
  player: string;
  target?: boolean;
  values: number[];
}
export interface RadarData {
  kind: "outfield" | "gk";
  axes: string[];
  series: RadarSeries[];
}
export interface ArchetypeResult {
  ok: boolean;
  target?: PlayerRef;
  archetype?: ArchetypeInfo;
  peers?: PlayerRef[];
  error?: string;
  suggestions?: string[];
  query?: string;
}
export interface ValueReport {
  ok: boolean;
  target?: PlayerRef;
  predicted_value_eur?: number;
  actual_value_eur?: number | null;
  ratio?: number | null;
  verdict?: "undervalued" | "overvalued" | "fair" | "unknown";
  model?: string;
  error?: string;
  suggestions?: string[];
}
export interface UndervaluedHit extends PlayerRef {
  actual_value_eur: number;
  predicted_value_eur: number;
  ratio: number;
}
export interface UndervaluedResult {
  ok: boolean;
  results?: UndervaluedHit[];
  count?: number;
  error?: string;
  message?: string;
  model?: string;
}
export interface ChatResult {
  query: string;
  intent: string;
  parsed: Record<string, unknown>;
  target?: PlayerRef | null;
  results: AgentRow[];
  radar?: RadarData | null;
  archetype?: ArchetypeInfo | null;
  threat?: ThreatAxis[] | null;
  metrics?: string[] | null;
  players?: ComparePlayer[] | null;
  leaders?: Record<string, string> | null;
  lineup?: SquadSlot[] | null;
  formation?: string | null;
  budget_eur?: number | null;
  total_value_eur?: number | null;
  within_budget?: boolean | null;
  verdict?: string | null;
  predicted_value_eur?: number | null;
  actual_value_eur?: number | null;
  ratio?: number | null;
  sources?: Source[] | null;
  answer: string;
}

export interface SearchParams {
  name: string;
  league?: string;
  same_position?: boolean;
  max_age?: number;
  top_n?: number;
}

export const api = {
  health: () => getJSON<Record<string, unknown>>("/"),

  searchClones: (p: SearchParams) =>
    getJSON<SearchResult>(`/search${qs({ ...p })}`),

  gkSearch: (p: Omit<SearchParams, "same_position">) =>
    getJSON<SearchResult>(`/gk/search${qs({ ...p })}`),

  /** Try outfield first; fall back to the goalkeeper engine. */
  async findSimilar(p: SearchParams): Promise<SearchResult> {
    const res = await this.searchClones(p);
    if (!res.ok && res.error === "player_not_found") {
      const gk = await this.gkSearch({
        name: p.name,
        league: p.league,
        max_age: p.max_age,
        top_n: p.top_n,
      });
      if (gk.ok) return { ...gk, player_type: "GK" };
    }
    return res;
  },

  archetype: (name: string) =>
    getJSON<ArchetypeResult>(`/archetype/${encodeURIComponent(name)}`),

  counter: (
    name: string,
    p: { league?: string; max_age?: number; pos?: string; top_n?: number } = {}
  ) => getJSON<SearchResult>(`/counter/${encodeURIComponent(name)}${qs({ ...p })}`),

  compare: (names: string[], query?: string) =>
    postJSON<SearchResult & { players?: ComparePlayer[]; leaders?: Record<string, string> }>(
      "/compare",
      { names, query }
    ),

  valueReport: (name: string) =>
    getJSON<ValueReport>(`/value/${encodeURIComponent(name)}`),

  undervalued: (p: { league?: string; pos_group?: string; max_age?: number; top_n?: number }) =>
    getJSON<UndervaluedResult>(`/value/undervalued${qs({ ...p })}`),

  chat: (message: string, history?: ChatTurn[]) =>
    postJSON<ChatResult>("/chat", { message, history }),

  squad: (body: {
    formation?: string;
    roles?: Record<string, number>;
    budget_eur?: number;
    query?: string;
    league?: string;
    max_age?: number;
  }) => postJSON<SquadResult>("/squad", body),
};

export const LEAGUES = [
  "Premier League",
  "La Liga",
  "Serie A",
  "Bundesliga",
  "Ligue 1",
] as const;
