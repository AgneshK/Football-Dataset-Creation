# Specifications

This project follows **Specification-Driven Development (SDD)**, adapted from
GitHub [spec-kit](https://github.com/github/spec-kit). The specs were authored
retroactively to document the existing system and to govern future work — code is
treated as the expression of these specifications, not the other way around.

## Layout

```
.specify/memory/constitution.md          Governing principles (+ honest gaps)
specs/001-ai-football-scout/
  ├── spec.md                            WHAT / WHY — user stories, requirements, ambiguities
  ├── plan.md                            HOW — architecture, tech choices, compliance gates
  ├── data-model.md                      Datasets, feature schema, derived structures
  ├── contracts/api-contracts.md         REST endpoints + response schemas
  └── tasks.md                           Delivered work + prioritised backlog
```

## SDD workflow (spec-kit equivalents)

| spec-kit command | Artifact here |
|---|---|
| `/speckit.specify` | `spec.md` |
| `/speckit.plan` | `plan.md` (+ `data-model.md`, `contracts/`) |
| `/speckit.tasks` | `tasks.md` |

Open questions are tagged `[NEEDS CLARIFICATION]` in `spec.md`. Where the codebase
does not yet meet a constitutional principle (notably automated tests), it is
recorded as a **Gap** rather than asserted as met.
