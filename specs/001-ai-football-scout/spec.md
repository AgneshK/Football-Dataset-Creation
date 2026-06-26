# Feature Specification: AI Football Scout

**Feature branch:** `001-ai-football-scout`
**Status:** Retroactive (documents the existing system + governs future work)
**Input:** A conversational scouting assistant over Europe's Big-5 leagues, 2024/25.

---

## Overview (WHAT / WHY)

Professional scouting insight is locked behind tools that require expertise:
analysts must know which of ~90 per-90 metrics matter, how to normalise them by
position, and how to turn a football idea ("a destroyer who can also progress
play") into a query. **AI Football Scout lets anyone interrogate a full season of
Big-5 data in plain language.** The system infers what kind of question is being
asked, runs the appropriate analysis on real statistics, and returns a ranked,
explained answer with visuals — and it remembers the conversation so scouting is
a dialogue, not a series of one-off searches.

---

## User Stories & Acceptance Criteria

### US-1 — Find statistical clones
*As a recruiter, I want players statistically similar to a target so I can find
cheaper or younger alternatives.*
- **Given** a known player, **when** I ask "a winger like Lamine Yamal under 23",
  **then** I get same-position players ranked by cosine similarity, filtered by
  age, each with a similarity score and a style radar.
- Falls back to the goalkeeper engine when the named player is a GK.

### US-2 — Budget-constrained clones
*As a recruiter with a budget, I want similar players under a price.*
- "a striker like Haaland under €40M" → clones filtered by market value, with a
  note when value data is unavailable.

### US-3 — Playing-style archetype
*As an analyst, I want a player's statistical style.*
- "what kind of player is Rodri" → a named archetype (KMeans within position),
  signature stats, a fit score, and exemplar players.

### US-4 — Market value verdict
*As a director, I want to know if a player is over/under-valued.*
- "undervalued midfielders" → players whose model-predicted value exceeds their
  market value; "is Gvardiol overvalued" → a single-player verdict.

### US-5 — Live intel
*As a scout, I want current news/injury/transfer context.*
- "any injury news on Saka" → a grounded brief with sources (Gemini + Search).

### US-6 — Tactical counter
*As a coach, I want a player to neutralise a specific opponent.*
- "find me a defender that can stop Haaland" → the attacker's threat profile
  (which offensive axes they dominate) and a ranked list of DF/MF players whose
  defensive strengths counter those threats, with a counter-fit score.

### US-7 — Open-ended trait search & leaderboards
*As a scout, I want to discover players by qualities, not by name.*
- "ball-carrying midfielder with progressive passes" → ranked by per-90 traits.
- "who has the most assists in the Premier League" → ranked by **season totals**
  (absolute values), not per-90.

### US-8 — Head-to-head comparison
*As an analyst, I want to compare named players.*
- "is Saliba better than Gvardiol aerially?" → per-metric values, the leader of
  each metric, an overlaid style radar, and a balanced verdict.

### US-9 — Squad building
*As a manager, I want a lineup within a budget and style.*
- "build me a €150M front three that presses" → a lineup filling each role with
  the best style-fit player affordable within the total budget, flagged
  within/over budget.

### US-10 — General fallback
*As any user, I want every question answered.*
- "what formation suits high pressing" → a conversational answer, explicitly
  marked as general knowledge rather than dataset-derived.

### US-11 — Conversational memory (multi-turn)
*As a user, I want to refine results without repeating myself.*
- After US-7, "now only ones under 23 in Serie A" → carries over the prior
  intent and trait metrics, applies the new league/age filters.

---

## Functional Requirements

- **FR-1** The agent MUST classify each message into one of nine grounded intents
  (clone, budget, archetype, value, intel, counter, discover, compare, squad) or
  a general fallback, and route to the matching capability.
- **FR-2** Name resolution MUST handle accents, aliases (e.g. "kdb", "vini"),
  last-name/substring matches, and return suggestions on ambiguity.
- **FR-3** Similarity and trait rankings MUST be computed on position-group
  z-scored features; cross-position pools re-normalise across the pool.
- **FR-4** `discover` MUST support per-90 (rates) and total (season volume) modes,
  preferring raw total columns and falling back to per90×90s where absent.
- **FR-5** `counter` MUST derive threat weights from the attacker's offensive
  axis profile and map them to defensive counter-metrics.
- **FR-6** `squad` MUST respect a total budget via a greedy fit-per-euro downgrade
  and keep players unique across slots.
- **FR-7** `/chat` MUST accept prior turns and resolve follow-ups against them.
- **FR-8** Every grounded answer MUST return the metrics/filters used; the LLM
  MUST NOT introduce statistics not present in the engine output.
- **FR-9** All capabilities MUST be reachable via REST endpoints and (where
  applicable) dedicated UI tabs, sharing one engine instance.

## Non-Functional Requirements

- **NFR-1** Engine + models load once at API startup, not per request.
- **NFR-2** Players need ≥ 500 minutes in the season to be eligible.
- **NFR-3** The API must boot even if `GROQ_API_KEY` is unset (agent endpoints
  degrade with a clear error; data endpoints keep working).
- **NFR-4** Data scale (~1,700 players) fits in memory; no external datastore.

---

## Ambiguities & Open Questions

- `[NEEDS CLARIFICATION]` CB vs FB vs DM sub-roles are inferred from a statistical
  heuristic because FBref positions are only DF/MF/FW — acceptable accuracy?
- `[NEEDS CLARIFICATION]` Squad-builder ranks on style fit, which can prefer a
  cheap statistical outlier over a famous name. Should it blend in a quality/value
  prior?
- `[NEEDS CLARIFICATION]` Leaderboards still apply the 500-minute floor; is that
  the desired definition of "most assists"?
- `[NEEDS CLARIFICATION]` General-fallback answers are ungrounded — acceptable, or
  should out-of-scope questions be refused instead?

## Out of Scope (current)

- Multi-season / historical trends; live match data.
- Pressing, pace (GPS), and height-based analysis (not in the dataset).
- Authentication, persistence of user shortlists, exports.

## Review Checklist

- [x] User stories have testable acceptance criteria
- [x] Functional requirements are implementation-agnostic (WHAT, not HOW)
- [x] Ambiguities explicitly marked
- [x] Out-of-scope recorded
- [ ] Automated acceptance tests exist (Gap — see constitution Article V)
