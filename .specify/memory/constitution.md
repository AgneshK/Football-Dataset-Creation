# AI Football Scout — Project Constitution

> Adapted from GitHub spec-kit's Specification-Driven Development. These are the
> governing principles for the project. Where the current codebase does not yet
> satisfy an article, it is recorded honestly as a **Gap** rather than asserted
> as met. New work should move the project toward these principles.

## Article I — Specification First
Every capability begins as a user story and acceptance criteria in `spec.md`
before implementation. Code is the expression of the spec, not the source of it.

## Article II — Interpretable Over Opaque
Analytical answers MUST be traceable to real data. Rankings expose the metrics
and (where possible) the per-metric contribution that produced them. The LLM is
used to *route* and *narrate*, never to invent statistics.
- **Met:** every grounded intent returns the metrics/filters it used.
- **Gap:** the general-fallback intent answers from model knowledge, not data —
  it is explicitly labelled as such.

## Article III — Position-Relative Reasoning
Player metrics are z-scored within position group (DF/MF/FW) so "progressive"
means progressive *for that position*. Cross-position rankings re-normalise
across the candidate pool.

## Article IV — Single Engine, Many Surfaces
Core logic lives in a framework-free engine (`ScoutEngine`) loaded once and
shared by the API, the agent, and every UI tab. No capability may duplicate
ranking logic in the frontend.

## Article V — Test-First (Aspirational)
- **Gap:** the project currently has no automated test suite. New capabilities
  SHOULD ship with unit tests over the engine methods (pure functions over a
  fixed fixture dataset). This is the top-priority debt.

## Article VI — Simplicity & Right-Sized Tooling
Prefer the simplest tool that fits the data scale (~1,700 rows): in-memory
NumPy/pandas over external infrastructure. A dependency (e.g. a vector DB) must
justify itself against this baseline.
- **Met:** similarity runs in-memory; no premature infrastructure.

## Article VII — Honest Limits
Data and model limitations are surfaced to the user, not hidden: missing market
values, the 500-minute sample floor, per-90 small-sample spikes, heuristic
CB/FB sub-roles, and the absence of pressing/pace/height stats.

## Amendment process
Changes to this constitution are made by editing this file in a dedicated commit
that explains the rationale. Specs and plans cite the article numbers they rely on.
