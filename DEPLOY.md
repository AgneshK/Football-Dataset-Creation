# Deployment

Free hosting with a backend that stays warm:

- **Backend** → Hugging Face Space (Docker SDK). Free tier = 2 vCPU / 16 GB RAM, only
  sleeps after **48 h** of no traffic. A scheduled ping keeps it from ever cold-starting.
- **Frontend** → Cloudflare Pages. Static, free, never cold-starts.

---

## 1. Backend → Hugging Face Space

The backend reads `data/processed/*.csv` and `models/*` at startup. **Both are gitignored**
in this project, so the steps below copy them into a separate Space repo where `.gitignore`
does not apply.

### 1a. Create the Space
1. Go to https://huggingface.co/new-space
2. Name it e.g. `football-scout-api`. **SDK = Docker** (blank template). Visibility: Public.
3. Create. HF makes a git repo with a `README.md` whose frontmatter declares `sdk: docker`.

### 1b. Fill the Space repo
```bash
# Clone the empty Space (use your username / space name)
git clone https://huggingface.co/spaces/<your-username>/football-scout-api
cd football-scout-api

# Copy the backend bits from this project into the Space repo.
# (Adjust the source path to wherever this project lives.)
SRC="/c/Users/Agnesh Kundu/Football Dataset Creation"
cp "$SRC/Dockerfile" .
cp "$SRC/.dockerignore" .
cp "$SRC/requirements.txt" .
cp -r "$SRC/src" .
mkdir -p data
cp -r "$SRC/data/processed" data/processed
cp -r "$SRC/models" .
```
> Leave the Space's own `README.md` untouched — its frontmatter (`sdk: docker`,
> `app_port: 7860`) is what tells HF how to run the container. If `app_port` is missing,
> add `app_port: 7860` under the frontmatter.

### 1c. Set the API keys as Secrets
In the Space → **Settings → Variables and secrets → New secret**:
- `GROQ_API_KEY` = your Groq key
- `GEMINI_API_KEY` = your Gemini key

(The app calls `load_dotenv()` but falls back to real env vars, which is how HF injects secrets.)

### 1d. Push
```bash
git add -A
git commit -m "Deploy AI Football Scout backend"
git push
```
HF builds the image and boots it. Watch the **Logs** tab. When healthy, your API is at:
```
https://<your-username>-football-scout-api.hf.space
```
Test it: open `https://<your-username>-football-scout-api.hf.space/` → should return the
health JSON. `…/docs` gives the Swagger UI.

---

## 2. Frontend → Cloudflare Pages

Requires the project (at least `frontend/`) pushed to a GitHub repo.

1. https://dash.cloudflare.com → **Workers & Pages → Create → Pages → Connect to Git**.
2. Pick the repo. **Build settings:**
   - Framework preset: **Vite**
   - **Root directory:** `frontend`
   - Build command: `npm run build`
   - Build output directory: `dist`
3. **Environment variables** (Production):
   - `VITE_API_BASE` = `https://<your-username>-football-scout-api.hf.space`
     (bare origin, **no** trailing slash, **no** `/api` — the client appends paths like
     `/search` directly.)
4. **Save and Deploy.** You get a `https://<project>.pages.dev` URL.

> Changing `VITE_API_BASE` later requires a **redeploy** (Vite inlines env vars at build time).

---

## 3. Keep the backend warm (no cold start)

HF Spaces pause after ~48 h idle. A periodic ping resets that timer.

1. https://cron-job.org → free account → **Create cronjob**.
2. URL: `https://<your-username>-football-scout-api.hf.space/`
3. Schedule: **every 6 hours** (well inside the 48 h window; bump to hourly if you want it
   guaranteed-hot during active periods).

That's it — frontend is always-on (static), backend stays warm via the pinger.

---

## Local dev (unchanged)
```bash
# backend
uvicorn src.scout.api:app --reload --port 8000
# frontend (proxies /api -> :8000, see vite.config.ts)
cd frontend && npm run dev
```
