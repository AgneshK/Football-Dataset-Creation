# AI Football Scout — Use Case Diagram

This document models **all user interactions** with the AI Football Scout system.
It separates **human actors** (who initiate goals) from **external system actors**
(third-party services the system depends on to fulfil those goals).

## Actors

| Actor | Type | Role |
|-------|------|------|
| **Scout / Analyst** | Human (primary) | End user — finds clones, archetypes, value verdicts, intel via the React UI or API |
| **Data Engineer** | Human (primary) | Builds datasets, joins market values, trains the value model (runs the `pipeline/` scripts) |
| **FBref / worldfootballR** | External system | Source of the raw Big-5 per-90 / style CSVs |
| **Transfermarkt / Kaggle** | External system | Source of player market values (label for the value model) |
| **Groq LLM (LangGraph agent)** | External system | Powers the natural-language `/chat`, `/discover`, `/compare`, `/squad` features |
| **Gemini + Google Search** | External system | Grounded live news / injury / discipline / rumour intel |

---

## PlantUML (standard UML use-case notation)

> Render at <https://www.plantuml.com/plantuml> or with the PlantUML VS Code extension.

```plantuml
@startuml AI_Football_Scout_UseCases
left to right direction
skinparam packageStyle rectangle
skinparam actorStyle awesome

actor "Scout /\nAnalyst" as Scout
actor "Data\nEngineer" as Eng

actor "FBref /\nworldfootballR" as FBref
actor "Transfermarkt /\nKaggle" as TM
actor "Groq LLM\n(LangGraph agent)" as Groq
actor "Gemini +\nGoogle Search" as Gemini

rectangle "AI Football Scout" {

  ' ---- Scouting / analysis (Scout) ----
  usecase "Resolve & view\nplayer profile" as UC_Profile
  usecase "Find similar\noutfield players (clones)" as UC_Clone
  usecase "Find similar\ngoalkeepers" as UC_GK
  usecase "View player\narchetype / style" as UC_Arch
  usecase "Browse all\narchetypes" as UC_Archs
  usecase "Get market-value\nverdict" as UC_Value
  usecase "Browse undervalued\nplayers" as UC_Under
  usecase "Find a counter\nfor a player" as UC_Counter
  usecase "Compare\nplayers" as UC_Compare
  usecase "Discover players\nby free-text traits" as UC_Discover
  usecase "Build a\nsquad" as UC_Squad
  usecase "Get live intel\n(news / injury / rumours)" as UC_Intel
  usecase "Ask the NL\nagent (chat)" as UC_Chat

  ' ---- Data / ML pipeline (Data Engineer) ----
  usecase "Build scouting\ndataset" as UC_Build
  usecase "Join market\nvalues" as UC_JoinMV
  usecase "Build goalkeeper\ndataset" as UC_BuildGK
  usecase "Train value\nmodel" as UC_Train
}

' ---- Scout associations ----
Scout --> UC_Profile
Scout --> UC_Clone
Scout --> UC_GK
Scout --> UC_Arch
Scout --> UC_Archs
Scout --> UC_Value
Scout --> UC_Under
Scout --> UC_Counter
Scout --> UC_Compare
Scout --> UC_Discover
Scout --> UC_Squad
Scout --> UC_Intel
Scout --> UC_Chat

' ---- Data Engineer associations ----
Eng --> UC_Build
Eng --> UC_JoinMV
Eng --> UC_BuildGK
Eng --> UC_Train

' ---- The chat agent routes into the underlying capabilities ----
UC_Chat ..> UC_Clone   : <<include>>
UC_Chat ..> UC_GK      : <<include>>
UC_Chat ..> UC_Arch    : <<include>>
UC_Chat ..> UC_Value   : <<include>>
UC_Chat ..> UC_Intel   : <<include>>

' ---- Clone falls back to GK when name isn't an outfield player ----
UC_Clone ..> UC_GK     : <<extend>>

' ---- NL features depend on the LLM ----
UC_Chat     --> Groq
UC_Discover --> Groq
UC_Compare  --> Groq
UC_Squad    --> Groq

' ---- Intel depends on Gemini grounding ----
UC_Intel --> Gemini

' ---- Pipeline depends on external data sources ----
UC_Build  --> FBref
UC_JoinMV --> TM
UC_BuildGK --> FBref

' ---- Serving value verdict needs the trained model (built by the engineer) ----
UC_Value ..> UC_Train  : <<include>>
UC_Under ..> UC_Train  : <<include>>

@enduml
```

---

## Mermaid (quick-preview alternative)

> GitHub / most markdown previewers render this without any tooling.

```mermaid
flowchart LR
  Scout(["👤 Scout / Analyst"])
  Eng(["👤 Data Engineer"])
  FBref(["⚙️ FBref / worldfootballR"])
  TM(["⚙️ Transfermarkt / Kaggle"])
  Groq(["⚙️ Groq LLM agent"])
  Gemini(["⚙️ Gemini + Google Search"])

  subgraph System["AI Football Scout"]
    UC_Profile(["View player profile"])
    UC_Clone(["Find similar players"])
    UC_GK(["Find similar goalkeepers"])
    UC_Arch(["View archetype / style"])
    UC_Archs(["Browse archetypes"])
    UC_Value(["Get value verdict"])
    UC_Under(["Browse undervalued"])
    UC_Counter(["Find a counter"])
    UC_Compare(["Compare players"])
    UC_Discover(["Discover by traits"])
    UC_Squad(["Build a squad"])
    UC_Intel(["Get live intel"])
    UC_Chat(["Ask NL agent (chat)"])

    UC_Build(["Build dataset"])
    UC_JoinMV(["Join market values"])
    UC_BuildGK(["Build GK dataset"])
    UC_Train(["Train value model"])
  end

  Scout --- UC_Profile & UC_Clone & UC_GK & UC_Arch & UC_Archs & UC_Value
  Scout --- UC_Under & UC_Counter & UC_Compare & UC_Discover & UC_Squad & UC_Intel & UC_Chat

  Eng --- UC_Build & UC_JoinMV & UC_BuildGK & UC_Train

  UC_Chat -.->|include| UC_Clone
  UC_Chat -.->|include| UC_Arch
  UC_Chat -.->|include| UC_Value
  UC_Chat -.->|include| UC_Intel
  UC_Clone -.->|extend: GK fallback| UC_GK

  UC_Chat --> Groq
  UC_Discover --> Groq
  UC_Compare --> Groq
  UC_Squad --> Groq
  UC_Intel --> Gemini
  UC_Build --> FBref
  UC_BuildGK --> FBref
  UC_JoinMV --> TM
```

---

## Reading notes

- **`<<include>>`** — the chat agent always *routes into* one of the core
  capabilities (clone / archetype / value / intel) once it parses intent.
- **`<<extend>>`** — the outfield clone finder *optionally* falls back to the
  goalkeeper engine when the queried name isn't an outfield player.
- **External system actors** appear on the right: the system can't fulfil the
  NL, intel, or data-build use cases without them.
- The four **Data Engineer** use cases are offline pipeline steps
  (`pipeline/01..05`, `04_train_value_model.py`); the value-serving routes
  return `503` until `Train value model` has been run.
