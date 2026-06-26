# Data Model: AI Football Scout

Source: FBref (Big-5 leagues, 2024/25) via `worldfootballR`, joined with
Transfermarkt market values. Season key `SEASON = 2025`. Eligibility: ≥ 500
minutes. Outfield players ≈ 1,596; goalkeepers ≈ 112.

## Datasets (processed)

| File | Purpose |
|---|---|
| `data/processed/scout_clean_2025.csv` | outfield feature set (no values) |
| `data/processed/scout_valued_2025.csv` | clean + Transfermarkt `market_value_eur` (preferred when present) |
| `data/processed/scout_gk_2025.csv` | goalkeeper dataset (separate engine) |
| `models/value_gbm.pkl`, `value_mlp.pt`, `value_scaler.pkl`, `value_meta.json` | value model artifacts |

## Player record (key fields)

**Identity / non-feature (`ID_COLS`)** — never used as similarity features:
`player, squad, league, nation, position, age, born_year, player_type, minutes,
matches_played, starts, nineties, market_value_eur` (label, not a feature).

**Derived at load:**
- `_norm` — normalised name search key (lowercased, accent/punctuation-stripped).
- `pos_group` — `DF | MF | FW` (first token of `position`; GK handled separately).

**Feature columns (~70 used for similarity):** any column ending in `_per90` or
`_pct`, plus a small shooting set (`goals_per_shot`, `npxg_per_shot`,
`avg_shot_distance`, `finishing_delta`). Raw season totals (`goals`, `assists`,
`tackles`, `prog_passes`, …) exist alongside the per-90s and back the `total`
mode of trait search.

## Style axes (`AXES`)

Interpretable groupings of feature columns, z-scored within position group; shared
by the clone radar and archetype naming:
`finishing, creation, progression, dribbling, distribution, tackling, aerial,
crossing`.

## Counter mappings

- `COUNTER_MAP` — for each offensive threat axis, the defensive metrics that blunt
  it (e.g. `aerial → [aerials_won_per90, aerial_win_pct, clearances_per90]`).
- `THREAT_LABELS` / `COUNTER_STRENGTH_LABELS` — human-readable labels for an
  attacker's threats and a defender's countering strengths.

## Metric catalogue (agent)

`METRIC_CATALOG` (in `agent.py`) — ~30 catalogue keys with plain-language
descriptions that the LLM selects from for `discover`/`compare`/`squad`. All keys
are validated against `ScoutEngine.features` before use.
`DEFAULT_COMPARE_METRICS` provides per-group defaults when none are picked.

## Derived structures (in memory)

- `_Xz` — feature matrix z-scored within position group (drives similarity + axes).
- `_row_for_idx` — dataframe index → matrix row map.
- Archetype model: per-group KMeans labels, centroids, names, distance-to-centroid.

## Transformations

1. Read processed CSV → coerce features to numeric → fill NaN with column median.
2. Z-score per `pos_group` (`StandardScaler`).
3. Similarity: cosine over `_Xz`. Trait search: re-z-score chosen metrics across
   the filtered pool (cross-position comparable).
4. Total mode: swap a `_per90` metric for its raw base column, else `per90 × nineties`.
