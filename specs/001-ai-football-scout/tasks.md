# Tasks: AI Football Scout

Derived from [spec.md](./spec.md) and [plan.md](./plan.md). `[P]` = parallelizable
(independent files/areas). Completed items reflect the system as built; open items
are the prioritised backlog.

## Done (delivered)

- [x] T001 Data pipeline: build → select/rename → market-value join → value model → GK dataset
- [x] T002 `ScoutEngine`: load, per-group z-scoring, name resolution, clones
- [x] T003 FastAPI endpoints for clones / player resolution
- [x] T004 `ArchetypeModel` (KMeans per group) + endpoints
- [x] T005 Value model (GBM + MLP) + undervalued / single-player endpoints
- [x] T006 LangGraph agent: parse → route → capability → report; intel via Gemini
- [x] T007 `counter` intent + `find_counters` + `/counter`
- [x] T008 `discover` trait search + leaderboards (per90/total) + `/discover`
- [x] T009 `compare` head-to-head + `/compare`
- [x] T010 `squad` builder (budget greedy) + `/squad`
- [x] T011 General-fallback intent (any question answered)
- [x] T012 Conversational memory (history through parse + metric picker)
- [x] T013 Frontend tabs: Clones, Matchup, Squad, Archetype, Value, Agent

## Backlog (prioritised)

### P0 — Foundational debt (Constitution Art. V)
- [ ] T100 Test fixture: a small synthetic dataset written to a temp path
      (never overwrite real CSVs) for deterministic engine tests.
- [ ] T101 [P] Unit tests for `find_clones`, `find_counters`, `search_by_traits`
      (per90 + total), `compare`, `build_squad` (budget honoured, players unique).
- [ ] T102 [P] Parser/intent tests with recorded LLM fixtures (no live calls in CI).
- [ ] T103 OpenAPI snapshot test for the API contract.

### P1 — High-value features (no data work)
- [ ] T110 `explain` drill-down: per-metric percentile contribution for a ranking
      (components already computed — surface them in API + UI).
- [ ] T111 `recommend`/replacement intent (compose counter + budget + age + role):
      "find a replacement for our ageing right-back under €30M".
- [ ] T112 Squad builder: optional quality/value prior blended with style fit
      (resolves spec ambiguity on outlier picks).
- [ ] T113 [P] Shortlists: save/export results (CSV/PDF) — needs light persistence.
- [ ] T114 [P] "Similarity with divergence": "like Rodri but more attacking".

### P2 — UX & reach
- [ ] T120 [P] Example-driven empty states for Matchup & Squad tabs (match chat).
- [ ] T121 [P] "Send to Agent" hand-off between tabs.
- [ ] T122 Confidence/sample badges in the UI for low-minutes players.
- [ ] T123 Code-split the frontend bundle (currently > 500 kB warning).

### P3 — Data-dependent (tracked, out of current scope)
- [ ] T130 Add pressing/pressures + (if available) pace/height columns to enable
      true "high-pressing"/"fastest" queries.
- [ ] T131 Multi-season support for trend questions.

## Notes
- Tasks T101/T102 unblock everything else by making refactors safe.
- T110 is the highest interpretability win per effort (data already exists).
