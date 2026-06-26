# Implementation Plan: AI Football Scout

**Spec:** [spec.md](./spec.md) · **Constitution:** [../../.specify/memory/constitution.md](../../.specify/memory/constitution.md)

This plan documents the technical architecture as built and the rationale behind
the key decisions, with constitutional compliance gates noted.

---

## Architecture overview

```
            ┌─────────────────────────── React + Vite frontend ───────────────────────────┐
            │  Tabs: Clones · Matchup · Squad · Archetype · Value · Agent (chat w/ memory)  │
            └───────────────────────────────────┬──────────────────────────────────────────┘
                                                 │ REST (fetch)
                                    ┌────────────▼─────────────┐
                                    │   FastAPI (api.py)        │
                                    │   /search /counter        │
                                    │   /discover /compare      │
                                    │   /squad /chat /value …   │
                                    └──────┬─────────────┬──────┘
                                           │             │
                          ┌────────────────▼──┐     ┌────▼───────────────────────────┐
                          │ ScoutEngine        │     │ LangGraph agent (agent.py)     │
                          │ (engine.py)        │◄────┤ parse → route → node → report  │
                          │  clones, counters, │     │ Groq llama-3.3-70b-versatile   │
                          │  discover, compare,│     └────────────────────────────────┘
                          │  squad             │
                          ├────────────────────┤
                          │ ArchetypeModel     │  value_model (GBM + MLP) · gk_engine · intel (Gemini)
                          └────────────────────┘
                                   │
                          processed CSVs (FBref via worldfootballR + Transfermarkt values)
```

## Technology choices (mapped to requirements)

| Decision | Choice | Why (rationale) |
|---|---|---|
| Core engine | pandas + NumPy + scikit-learn, framework-free | Art. IV/VI; ~1,700 rows fit in memory; shared by API + agent |
| Similarity | `cosine_similarity` over z-scored feature matrix | FR-3; interpretable, no infra (Art. VI) — **a vector DB was explicitly rejected** at this scale |
| Normalisation | `StandardScaler` per position group | Art. III (position-relative) |
| Archetypes | KMeans per group, k by silhouette, axis-named | US-3; transparent, every label tied to signature stats |
| Value model | Gradient Boosting + PyTorch MLP (ensemble) | US-4 |
| NL routing | LangGraph `StateGraph`, Groq `llama-3.3-70b-versatile` | FR-1; fast structured parsing |
| Intent design | LLM parses to intent + slots; capability nodes do deterministic math; LLM narrates | Art. II (LLM routes/narrates, never invents) |
| Metric mapping | second LLM hop maps free text → catalogue keys | FR-4/FR-7; football vocabulary → exact columns |
| Live intel | Gemini + Google Search grounding | US-5 |
| Frontend | React + Vite + TS + Tailwind + recharts | tabbed UI + chat |

## Phase-based roadmap (as delivered)

1. **Data pipeline** — `pipeline/01…05`: build, select/rename, market-value join,
   train value model, build GK dataset → processed CSVs.
2. **Engine + API** — `ScoutEngine`, clone search, FastAPI endpoints.
3. **Archetype + value** — clustering + value model endpoints.
4. **Agent** — LangGraph parse/route/report over the engine; intel.
5. **Capability expansion** — counter → discover (per90/total) → compare → squad.
6. **Conversational memory** — history threaded through parse + metric picker.
7. **UI surfaces** — dedicated tabs mirroring the chat capabilities.

## Constitutional compliance gates

- **Art. II (Interpretable):** PASS — grounded intents return metrics/filters;
  general fallback is labelled ungrounded.
- **Art. III (Position-relative):** PASS — per-group z-scoring throughout.
- **Art. IV (Single engine):** PASS — one `ScoutEngine` shared by API + agent.
- **Art. V (Test-first):** FAIL (Gap) — no automated tests yet; top debt item.
- **Art. VI (Simplicity):** PASS — in-memory, no external datastore.
- **Project count:** backend + frontend = 2 (within the ≤3 guideline).

## Key risks / mitigations

- **LLM emits malformed JSON** → tolerant parsing + regex/keyword fallbacks in
  `_pick_metrics` and the parser.
- **LLM routes to an unknown intent** → router guards to the general node.
- **Missing market values** → budget filters degrade with an explicit note.
- **Small-sample per-90 spikes** → surfaced to the user; 500-minute floor.
