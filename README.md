# AI Football Scout ⚽

Find statistically similar players ("clones") across Europe's Big 5 leagues, discover
player **archetypes**, predict **market value**, and ask questions in plain English — served
through a FastAPI backend, a PyTorch/LightGBM value model, and a LangGraph + Groq agent,
behind a React UI.

<p align="center">
  <b><a href="https://YOUR-PROJECT.pages.dev">🔗 Live App</a></b> ·
  <b><a href="https://AgneshK10-football-scout-api.hf.space/docs">📘 API Docs</a></b> ·
  <b><a href="https://AgneshK10-football-scout-api.hf.space/">❤️ API Health</a></b>
</p>

> Hosted free: frontend on **Cloudflare Pages**, backend on a **Hugging Face Space** (Docker).
> See [`DEPLOY.md`](./DEPLOY.md) for the full deployment guide.

---

## Features

- **Clone finder** — statistically nearest players to anyone, with automatic goalkeeper fallback.
- **Archetypes** — KMeans style-clusters within each position group ("what kind of player is X?").
- **Value model** — predicted vs. actual market value, with an undervalued/overvalued verdict.
- **Live intel** — news, injuries, discipline and transfer rumours via Gemini 2.5 Pro grounded with Google Search.
- **Natural-language agent** — ask in plain English; the agent parses, routes, and writes a scouting report.

## How it works

Similarity is computed on **per-90 + percentage style stats**, z-scored **within position group**
(so a striker is compared on striker scales, not against centre-backs), then ranked by **cosine
similarity**. Market value is treated strictly as a label — it never enters the similarity matrix.

- **Archetypes** (`src/scout/archetype.py`) — KMeans per position group on the same z-scored
  features; cluster count chosen by silhouette score, each cluster auto-named by scoring its
  centroid on interpretable axes (finishing, creation, progression, tackling, aerial, …).
- **Value model** (`src/scout/value_model.py`) — predicts `log1p(market_value_eur)` from style
  stats + age + position + league + raw output/playing-time. `pipeline/04_train_value_model.py`
  trains a **PyTorch MLP** (architecture/optimiser tuned by **Optuna**), a **LightGBM** baseline,
  and their **ensemble**, picking the winner by 5-fold CV R²(log) (≈ **0.52** on ~1,570 players).

> The model regresses superstar outliers (Haaland, Mbappé, Bellingham) toward the mean — their
> price reflects reputation and marketability stats can't see, so verdicts are most reliable in
> the mid-market.

## Tech stack

| Layer     | Tech |
|-----------|------|
| Frontend  | React 19, Vite, Tailwind v4, shadcn-style components |
| Backend   | FastAPI, Uvicorn, Pydantic |
| ML        | scikit-learn, PyTorch, LightGBM, Optuna |
| Agent/LLM | LangGraph, Groq (parser + reports), Gemini 2.5 Pro (grounded intel) |
| Hosting   | Cloudflare Pages (frontend) · Hugging Face Spaces / Docker (backend) |

## API endpoints

| Method | Endpoint              | Description                                       |
|--------|-----------------------|---------------------------------------------------|
| GET    | `/`                   | health check (players loaded, features used)      |
| GET    | `/player/{name}`      | resolve a name → player profile                   |
| GET/POST | `/search`           | clone finder (query params or JSON body)          |
| GET    | `/archetype/{name}`   | player's statistical style + exemplar players     |
| GET    | `/archetypes`         | all discovered archetypes per position group      |
| GET    | `/value/{name}`       | predicted vs. actual market value + verdict       |
| GET    | `/value/undervalued`  | players the model prices above their market value |
| GET    | `/gk/{name}`          | resolve a goalkeeper → profile                    |
| GET    | `/gk/search`          | find statistically similar goalkeepers            |
| GET    | `/intel/{name}`       | live news / injury / discipline / rumours (Gemini)|
| POST   | `/chat`               | natural-language agent (needs `GROQ_API_KEY`)     |

`/value/*`, `/gk/*`, `/intel/*` and `/chat` return **503** until their prerequisite (trained
model, GK dataset, or API key) is present; the API still boots without them.

## Local development

### 1. Backend

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.scout.api:app --reload --port 8000   # docs at http://localhost:8000/docs
```

Copy `.env.example` → `.env` and add `GROQ_API_KEY` and `GEMINI_API_KEY` to enable the agent
and live intel. (Tip: `gemini-2.5-pro` has tiny free quota — set
`GEMINI_MODEL=gemini-2.5-flash` for a free, fully-grounded alternative.)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api -> :8000)
```

### 3. Rebuild the dataset (optional)

The processed CSVs and trained models ship ready to run. To rebuild from `data/raw/`:

```bash
python pipeline/01_build.py            # raw Big-5 CSVs -> scout_dataset_2025.csv
python pipeline/02_select_rename.py    #               -> scout_clean_2025.csv
python pipeline/05_build_gk.py         # goalkeeper dataset -> scout_gk_2025.csv
# optional: Transfermarkt values + value model
python pipeline/prep_kaggle_values.py  # Kaggle dump -> data/raw/market_values.csv
python pipeline/03_market_values.py    # name-match + join -> scout_valued_2025.csv
python pipeline/04_train_value_model.py# train MLP + LightGBM -> models/
```

Change `SEASON` at the top of each script to target a different season.

## Project structure

```
.
├── data/
│   ├── raw/                 # worldfootballR Big-5 CSVs + Transfermarkt dump (input)
│   └── processed/           # generated datasets (scout_*_2025.csv)
├── pipeline/                # data build + value-model training scripts
├── src/scout/
│   ├── engine.py            # outfield similarity engine + name resolution
│   ├── gk_engine.py         # goalkeeper similarity engine
│   ├── archetype.py         # KMeans style clustering
│   ├── value_model.py       # market-value prediction
│   ├── agent.py             # LangGraph agent (parse -> route -> report)
│   └── api.py               # FastAPI app
├── models/                  # trained value-model artifacts
├── frontend/                # React + Vite + Tailwind v4 UI
├── Dockerfile               # backend image for Hugging Face Spaces
├── DEPLOY.md                # full deployment guide
└── requirements.txt
```

## Deployment

Both halves run on free tiers. Full step-by-step is in [`DEPLOY.md`](./DEPLOY.md):

- **Backend** → Hugging Face Space (Docker SDK). 16 GB RAM, kept warm with a cron-job.org pinger.
- **Frontend** → Cloudflare Pages. Static, always-on; build root `frontend/`, output `dist`,
  with `VITE_API_BASE` pointing at the Space URL.

## Roadmap

- [x] Clone finder (outfield + goalkeeper engines)
- [x] Player-archetype clustering
- [x] Transfermarkt / Kaggle market-value join
- [x] Value model (PyTorch MLP + LightGBM ensemble)
- [x] Live intel via Gemini + Google Search grounding
- [x] React frontend (Vite + Tailwind v4)
- [x] Free cloud deployment (Cloudflare Pages + Hugging Face Spaces)
