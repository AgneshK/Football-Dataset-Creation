# API Contracts: AI Football Scout

FastAPI app (`src/scout/api.py`). Run: `uvicorn src.scout.api:app --reload --port 8000`.
Interactive docs at `/docs`. All responses JSON. CORS open for dev.

Convention: list endpoints return `{ ok, ... }`; unresolved names return
`{ ok: false, error, suggestions[] }`.

| Method | Path | Body / Query | Maps to | Returns |
|---|---|---|---|---|
| GET | `/` | — | health | `{status, season, players_loaded, features_used}` |
| GET | `/player/{name}` | — | `engine.resolve` | player profile or suggestions |
| GET | `/search` | `name, league?, same_position?, top_n?, max_age?, min_similarity?` | `find_clones` | clones + radar (US-1/US-2) |
| POST | `/search` | `SearchRequest` | `find_clones` | clones + radar |
| GET | `/archetype/{name}` | — | `ArchetypeModel.describe` | archetype + peers (US-3) |
| GET | `/archetypes` | — | `ArchetypeModel.summary` | all archetypes per group |
| GET | `/value/undervalued` | `league?, pos_group?, max_age?, top_n?` | value model | undervalued list (US-4) |
| GET | `/value/{name}` | — | value model | predicted vs actual + verdict |
| GET | `/gk/search` | `name, league?, top_n?, max_age?, min_similarity?` | gk engine | similar GKs |
| GET | `/gk/{name}` | — | gk engine | GK profile |
| GET | `/counter/{name}` | `league?, max_age?, pos?, top_n?` | `find_counters` | threat profile + ranked stoppers (US-6) |
| POST | `/discover` | `{query, league?, pos?, max_age?, top_n?}` | `_pick_metrics` → `search_by_traits` | ranked shortlist + `value_mode` (US-7) |
| POST | `/compare` | `{names[], query?}` | `compare` | per-player stats, leaders, radar (US-8) |
| POST | `/squad` | `{formation?, roles?, budget_eur?, query?, league?, max_age?}` | `build_squad` | lineup + budget summary (US-9) |
| GET | `/intel/{name}` | — | `player_intel` (Gemini) | grounded brief + sources (US-5) |
| POST | `/chat` | `{message, history?: [{role, content}]}` | `run_agent` | routed answer + structured payload (US-1…11) |

## Selected schemas

**`/chat` response (`ChatResult`)** — superset; fields populated by intent:
```
query, intent, parsed{target, league, pos, formation, roles, max_age, max_value_eur, top_n},
metrics[], players[], leaders{}, lineup[], formation, budget_eur, total_value_eur,
within_budget, target, results[], radar, archetype, threat[], verdict,
predicted_value_eur, actual_value_eur, ratio, sources[], answer
```

**`/counter/{name}`**: `{ ok, mode:"counter", target, threat:[{axis,label,weight}],
filters, count, results:[{player, …, counter_score, similarity, strengths[]}] }`

**`/discover`**: `{ ok, mode:"discover", value_mode:"per90"|"total", metrics[],
filters, count, results:[{player, …, trait_score, similarity, stats{}}] }`

**`/squad`**: `{ ok, mode:"squad", formation, roles, budget_eur, total_value_eur,
within_budget, style_metrics[], count, lineup:[{role, player, squad, league,
position, age, market_value_eur, fit}], note }`

## Error contracts

- `503` when a model/dataset isn't built (value model, GK dataset).
- `500` when `GROQ_API_KEY` is unset for `/chat`, `/discover`, `/compare`, `/squad`
  (data-only endpoints remain available — NFR-3).
- `400` from `/discover` when no metric can be mapped from the query.

> `[NEEDS CLARIFICATION]` No OpenAPI contract test suite yet — these contracts are
> hand-maintained from the code. A generated `openapi.json` snapshot test is a
> candidate task.
