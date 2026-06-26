# Scout — frontend

Production-grade React UI for the AI Football Scout API. Vite + React 19 +
TypeScript, Tailwind CSS v4, shadcn-style components (Radix primitives), Geist
typeface, and light / dark / system theming.

## Run

The backend must be running first (from the project root):

```bash
uvicorn src.scout.api:app --reload --port 8000
```

Then, in this folder:

```bash
npm install
npm run dev          # http://localhost:5173
```

In dev, requests to `/api/*` are proxied to `http://localhost:8000` (see
`vite.config.ts`), so no CORS setup is needed. For a deployed build, set
`VITE_API_BASE` (see `.env.example`) and run `npm run build`.

## Features

| Tab        | Backend endpoint(s)                | What it does                                  |
|------------|------------------------------------|-----------------------------------------------|
| Clones     | `/search`, `/gk/search` (fallback) | Statistical clones; auto-routes goalkeepers   |
| Archetype  | `/archetype/{name}`                | Playing-style cluster + fit + signature stats |
| Value      | `/value/{name}`, `/value/undervalued` | Predicted vs market value; undervalued board |
| Agent      | `/chat`                            | Natural-language scouting (needs `GROQ_API_KEY`) |

## Design

- **Type**: Geist Sans (UI) + Geist Mono (all numbers/stats), via Google Fonts.
- **Palette**: near-monochrome zinc; accent reserved for primary actions, with a
  subtle emerald/red only on value verdicts and the status dot.
- **Theme**: `light` / `dark` / `system`, persisted to `localStorage`; defaults
  to dark via `class="dark"` on `<html>`.
- Components live in `src/components/ui` (shadcn-style — owned, not a dependency).
