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
   - `VITE_API_BASE` = `https://AgneshK10-football-scout-api.hf.space`
     (bare origin, **no** trailing slash, **no** `/api` — the client appends paths like
     `/search` directly.)
   - `NODE_VERSION` = `22` (also pinned via `frontend/.nvmrc`).
4. **Save and Deploy.** Live at <https://footy-scout.efootballaggu.workers.dev/>.

> Changing `VITE_API_BASE` later requires a **redeploy** (Vite inlines env vars at build time).

### ⚠️ Gotcha: `npm ci` fails on a Windows-generated lockfile

A `package-lock.json` generated on **Windows** omits Linux-only optional deps (e.g.
`@emnapi/*`), so Cloudflare's Linux `npm ci` fails with *"package.json and package-lock.json
… not in sync / Missing: @emnapi/core"*. Fix: **don't commit the lockfile** — it's gitignored
in `frontend/.gitignore`, so Cloudflare falls back to `npm install`, which resolves per-platform
deps correctly. If a build still runs `npm clean-install`, you're looking at a **retry of an old
commit** (which still had the lockfile) or a stale **build cache** — trigger a fresh deploy of the
latest commit, or recreate the Pages project.

---

## 3. Keep the backend warm (no cold start)

HF Spaces pause after ~48 h idle. A periodic GET request resets that timer so the backend
never cold-starts.

1. Go to **https://cron-job.org** → create a free account.
2. **Create cronjob:**
   - **Title**: `football-scout keep-warm`
   - **URL**: `https://AgneshK10-football-scout-api.hf.space/`
   - **Schedule**: every **6 hours** (custom: minutes `0`, hours `*/6`). Well inside the 48 h
     window; bump to hourly if you want it guaranteed-hot during the day.
   - **Request method**: GET. Leave notifications on so you're emailed if the Space ever 5xxs.
3. **Save** and ensure it's **enabled**.

The `/` endpoint is the lightweight health check (`{"status":"ok", ...}`) — ideal to ping
since it loads no LLM and returns instantly.

> Alternatives: UptimeRobot (5-min minimum, also free) or a GitHub Actions scheduled workflow
> (`on: schedule: - cron: "0 */6 * * *"` running `curl`). cron-job.org is the simplest.

That's it — frontend is always-on (static edge), backend stays warm via the pinger. All free.

---

## Local dev (unchanged)
```bash
# backend
uvicorn src.scout.api:app --reload --port 8000
# frontend (proxies /api -> :8000, see vite.config.ts)
cd frontend && npm run dev
```
