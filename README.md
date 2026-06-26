# AI Football Scout ⚽

Find statistically similar players ("clones") across Europe's Big 5 leagues, served
through a FastAPI backend with an optional natural-language agent (LangGraph + Groq).

Similarity is computed on **per-90 + percentage style stats**, z-scored **within
position group** (so a striker is compared on striker-relevant scales, not against
centre-backs), then ranked by cosine similarity.

## Project layout

```
.
├── data/
│   ├── raw/                 # 10 worldfootballR Big-5 CSVs (input)
│   └── processed/           # generated: scout_dataset_*.csv, scout_clean_*.csv
├── pipeline/
│   ├── 01_build.py            # join 10 raw tables -> one wide table + minutes filter
│   ├── 02_select_rename.py    # select ~45 cols, clean schema, derive per-90s
│   ├── 03_market_values.py    # join Transfermarkt values -> scout_valued_*.csv
│   ├── 04_train_value_model.py# train PyTorch MLP + LightGBM value model -> models/
│   ├── 05_build_gk.py         # build goalkeeper dataset -> scout_gk_*.csv
│   ├── prep_kaggle_values.py  # convert Kaggle Transfermarkt dump -> market_values.csv
│   └── fetch_market_values.R  # (R) pull Transfermarkt values via worldfootballR
├── src/scout/
│   ├── engine.py            # outfield similarity engine + name resolution (core logic)
│   ├── gk_engine.py         # goalkeeper similarity engine (GK-specific stats)
│   ├── archetype.py         # KMeans style clustering ("what kind of player is X")
│   ├── value_model.py       # market-value prediction + undervalued detection
│   ├── agent.py             # LangGraph agent: parse -> route -> capability -> report
│   └── api.py               # FastAPI app (all endpoints below)
├── models/                  # generated: trained value-model artifacts
├── notebooks/
│   └── data_exploration.ipynb
├── frontend/                # React + Vite + Tailwind v4 SaaS UI (see frontend/README.md)
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

## 1. Build the dataset

Run from the project root, in order:

```bash
python pipeline/01_build.py          # data/raw/*.csv  -> data/processed/scout_dataset_2025.csv
python pipeline/02_select_rename.py  # ...             -> data/processed/scout_clean_2025.csv
```

To rebuild for a future season, change `SEASON` at the top of each script (one line).

Goalkeepers are built separately (different stats — saves, PSxG, distribution,
sweeping — so they get their own engine):

```bash
python pipeline/05_build_gk.py     # data/raw keeper CSVs -> data/processed/scout_gk_2025.csv
```

### Optional: add Transfermarkt market values

Enables the `budget` agent branch (and provides the target for the future value
model). **Recommended path — static Kaggle dataset** (no live scraping):

1. Download [Football Data from Transfermarkt](https://www.kaggle.com/datasets/davidcariboo/player-scores)
   (browser is fine), unzip, and place `players.csv` and `player_valuations.csv`
   into `data/raw/transfermarkt/`.
2. Run the prep + join:

```bash
python pipeline/prep_kaggle_values.py   # picks each player's 2024/25-window value -> data/raw/market_values.csv
python pipeline/03_market_values.py     # name-matches + joins -> data/processed/scout_valued_2025.csv
```

`prep_kaggle_values.py` uses the historical `player_valuations.csv` to pick the
value **contemporaneous with the 2024/25 stats** (not the current snapshot),
falling back to the current value only when a player has no in-window valuation.

**Alternative — live pull via R** (worldfootballR; fragile, Transfermarkt often
blocks scrapers):

```bash
Rscript pipeline/fetch_market_values.R   # -> data/raw/market_values.csv
python pipeline/03_market_values.py
```

Either way: the engine automatically prefers `scout_valued_*.csv` over
`scout_clean_*.csv` when it exists. Unmatched players are written to
`data/processed/market_values_unmatched_*.csv` for manual review.
`market_value_eur` is treated strictly as a label — it never enters the
similarity feature matrix.

## 2. Run the API

```bash
uvicorn src.scout.api:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs>

| Method | Endpoint           | Description                                       |
|--------|--------------------|---------------------------------------------------|
| GET    | `/`                | health check (players loaded, features used)      |
| GET    | `/player/{name}`   | resolve a name → player profile                   |
| GET    | `/search`          | clone finder (query params)                       |
| POST   | `/search`          | clone finder (JSON body)                           |
| GET    | `/archetype/{name}`| player's statistical style + exemplar players      |
| GET    | `/archetypes`      | all discovered archetypes per position group       |
| GET    | `/value/{name}`    | predicted vs actual market value + verdict         |
| GET    | `/value/undervalued`| players the model prices above their market value |
| GET    | `/gk/{name}`       | resolve a goalkeeper -> profile                    |
| GET    | `/gk/search`       | find statistically similar goalkeepers             |
| GET    | `/intel/{name}`    | live news / injury / discipline / rumours (Gemini) |
| POST   | `/chat`            | natural-language agent (needs `GROQ_API_KEY`)     |

`/intel/*` uses **Gemini 2.5 Pro with Google Search grounding** and needs
`GEMINI_API_KEY` (returns 503 without it). Note: `gemini-2.5-pro` has minimal
free-tier quota — set `GEMINI_MODEL=gemini-2.5-flash` in `.env` for a free,
fully-grounded alternative.

`/gk/*` requires the GK dataset (`python pipeline/05_build_gk.py`); the routes
return 503 until it's built. Goalkeeper clone requests through `/chat` work too —
the agent falls back to the GK engine when a name isn't an outfield player.

`/value/*` requires the value model — train it with
`python pipeline/04_train_value_model.py` after the Transfermarkt join. The API
still boots without it (those routes return 503 until trained).

Example:

```bash
curl "http://localhost:8000/search?name=Harry%20Kane&league=La%20Liga&top_n=8"
```

## 3. Natural-language agent (optional)

The `/chat` endpoint and `src/scout/agent.py` need a Groq key:

```bash
export GROQ_API_KEY=...           # Windows: $env:GROQ_API_KEY="..."
python -m scout.agent             # run the built-in demo queries (run from src/)
```

Five intents are live: **clone**, **archetype**, **budget** (needs the
Transfermarkt join), **value** (needs the trained value model — name a player for
a verdict, or ask broadly for the most undervalued players), and **intel** —
live news, injury status, discipline and transfer rumours via Gemini 2.5 Pro
grounded with Google Search (needs `GEMINI_API_KEY`).

### How archetypes work

`src/scout/archetype.py` clusters players (KMeans) **within each position group**,
on the same within-position z-scored feature matrix the clone engine uses. The
number of clusters per group is chosen by silhouette score, and each cluster is
auto-named by scoring its centroid on interpretable axes (finishing, creation,
progression, tackling, aerial, …) and mapping the dominant axis to a scouting
label. Every label ships with the raw signature stats that produced it, plus a
`fit` score (≈1.0 = textbook example, near 0 = atypical/blended style).

### How the value model works

`src/scout/value_model.py` predicts market value from style stats + age +
position + league. The target is `log1p(market_value_eur)` (values are heavily
right-skewed). The feature set is value-specific and richer than the similarity
features: per-90 rates + percentages **plus raw output totals and playing time
(minutes, matches, starts) and age** — so the model can tell an every-week
starter from a low-minutes squad player with the same per-90s.

`pipeline/04_train_value_model.py` trains three things and picks the best by
**5-fold cross-validated R²(log)** (medians/scaler refit per fold — no leakage):
a **PyTorch MLP** whose architecture + optimiser are tuned by **Optuna** (TPE
search with pruning over depth, width, dropout, BatchNorm, LR, weight decay,
batch size), a **LightGBM baseline**, and their **ensemble** (mean in log space,
which usually wins). The winner becomes `primary`; all retrain on the full data.
Current CV R²(log) ≈ **0.52** (ensemble) on ~1,570 players.

> Note: even the tuned model regresses extreme outliers (Haaland, Bellingham,
> Mbappé) toward the conditional mean — their price reflects reputation, age and
> marketability that on-pitch stats can't see, so the undervalued/overvalued
> verdict is most reliable in the mid-market, not for superstars.

"Undervalued" players are those
whose predicted value materially exceeds their actual value (ratio ≥ 1.25).
Feature assembly lives in one place and is shared by training and serving to
avoid train/serve skew. Market value is never a similarity feature — only a label.

## 4. Frontend

A production-grade React UI lives in `frontend/` (Vite + React 19, Tailwind v4,
shadcn-style components, Geist type, dark/light/system themes). With the API
running:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api -> :8000)
```

Tabs: **Clones** (with automatic goalkeeper fallback), **Archetype**, **Value**
(verdict + undervalued board), and **Agent** (the `/chat` LLM). See
`frontend/README.md` for details.

## Roadmap

- [x] Player-archetype clustering → `archetype` agent branch is **live**
- [x] Market-value join (Transfermarkt / Kaggle) → `budget` branch is **live**
- [x] Value model (PyTorch MLP + LightGBM baseline) → `value` branch is **live**
- [x] Goalkeeper similarity (separate GK engine; `/gk/*` + chat fallback) — **live**
- [x] React frontend (Vite + Tailwind v4 + shadcn UI; dark/light/system) — see `frontend/`
