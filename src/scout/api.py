"""
api.py — FastAPI backend for the AI Football Scout
===================================================
Run (from project root):
    uvicorn src.scout.api:app --reload --port 8000
Docs: http://localhost:8000/docs   (interactive Swagger UI)

Endpoints
---------
GET  /                       health check
GET  /player/{name}          resolve a name -> player profile (tests normalization)
GET  /search                 clone finder (query params)
POST /search                 clone finder (JSON body) — easier for the frontend
POST /chat                   natural-language agent (requires GROQ_API_KEY)
"""
from typing import List, Optional
from pathlib import Path
import os

# Load environment variables from the project-root .env (e.g. GROQ_API_KEY)
# before anything reads them.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ModuleNotFoundError:
    pass

import pandas as pd
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .engine import ScoutEngine, SEASON
from .archetype import ArchetypeModel

app = FastAPI(title="AI Football Scout", version="0.1")

# allow the React frontend (any origin during dev) to call the API
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# load the engine + archetype model ONCE at startup (not per request)
engine = ScoutEngine()
archetypes = ArchetypeModel(engine)


# ---- schemas --------------------------------------------------------------
class SearchRequest(BaseModel):
    name: str
    league: Optional[str] = None
    same_position: bool = True
    top_n: int = 8
    max_age: Optional[int] = None
    min_similarity: Optional[float] = None


# ---- endpoints ------------------------------------------------------------
@app.get("/")
def health():
    return {"status": "ok", "season": SEASON,
            "players_loaded": int(len(engine.out)),
            "features_used": len(engine.features)}


@app.get("/player/{name}")
def resolve_player(name: str):
    idx, suggestions = engine.resolve(name)
    if idx is None:
        return {"ok": False, "query": name, "suggestions": suggestions or []}
    r = engine.out.loc[idx]
    return {"ok": True, "player": r["player"], "squad": r["squad"],
            "league": r["league"], "position": r["position"],
            "age": None if r["age"] != r["age"] else float(r["age"])}


@app.get("/search")
def search_get(
    name: str = Query(..., description="Target player, e.g. 'Harry Kane' or 'mbappe'"),
    league: Optional[str] = Query(None, description="e.g. 'La Liga'"),
    same_position: bool = Query(True),
    top_n: int = Query(8, ge=1, le=50),
    max_age: Optional[int] = Query(None),
    min_similarity: Optional[float] = Query(None, ge=0, le=1),
):
    res = engine.find_clones(name, league=league, same_position=same_position,
                             top_n=top_n, max_age=max_age,
                             min_similarity=min_similarity)
    return res


@app.post("/search")
def search_post(req: SearchRequest):
    return engine.find_clones(
        req.name, league=req.league, same_position=req.same_position,
        top_n=req.top_n, max_age=req.max_age, min_similarity=req.min_similarity)


@app.get("/archetype/{name}")
def archetype(name: str):
    """What statistical style/archetype is this player, and who else fits it."""
    return archetypes.describe(name)


@app.get("/archetypes")
def archetype_summary():
    """All discovered archetypes per position group, with player counts."""
    return {"season": SEASON, "groups": archetypes.summary()}


@app.get("/value/undervalued")
def undervalued(
    league: Optional[str] = Query(None),
    pos_group: Optional[str] = Query(None, description="DF | MF | FW"),
    max_age: Optional[int] = Query(None),
    top_n: int = Query(10, ge=1, le=50),
):
    """Players the value model thinks are worth more than their market price."""
    from .value_model import get_predictor
    vp = get_predictor()
    if vp is None:
        raise HTTPException(503, "Value model not trained. Run pipeline/04_train_value_model.py.")
    return vp.undervalued(engine, league=league, pos_group=pos_group,
                          max_age=max_age, top_n=top_n)


@app.get("/value/{name}")
def value(name: str):
    """Predicted vs actual market value for one player, with a verdict."""
    from .value_model import get_predictor
    vp = get_predictor()
    if vp is None:
        raise HTTPException(503, "Value model not trained. Run pipeline/04_train_value_model.py.")
    return vp.value_report(engine, name)


# ---- goalkeepers ----------------------------------------------------------
def _gk_or_503():
    from .gk_engine import get_gk_engine
    gk = get_gk_engine()
    if gk is None:
        raise HTTPException(503, "GK dataset not built. Run pipeline/05_build_gk.py.")
    return gk


@app.get("/gk/search")
def gk_search(
    name: str = Query(..., description="Goalkeeper name, e.g. 'Alisson'"),
    league: Optional[str] = Query(None),
    top_n: int = Query(8, ge=1, le=50),
    max_age: Optional[int] = Query(None),
    min_similarity: Optional[float] = Query(None, ge=0, le=1),
):
    """Find statistically similar goalkeepers."""
    return _gk_or_503().find_clones(name, league=league, top_n=top_n,
                                    max_age=max_age, min_similarity=min_similarity)


@app.get("/counter/{name}")
def counter(
    name: str,
    league: Optional[str] = Query(None, description="e.g. 'Premier League'"),
    max_age: Optional[int] = Query(None),
    pos: Optional[str] = Query(None, description="DF | MF | CB | FB | DM"),
    top_n: int = Query(8, ge=1, le=50),
):
    """Defenders / defensive mids best equipped to neutralise a given attacker."""
    return engine.find_counters(name, league=league, max_age=max_age,
                                pos=pos, top_n=top_n)


class DiscoverRequest(BaseModel):
    query: str
    league: Optional[str] = None
    pos: Optional[str] = None
    max_age: Optional[int] = None
    top_n: int = 10


@app.post("/discover")
def discover(req: DiscoverRequest):
    """Open-ended trait search: free text -> ranked shortlist. Needs GROQ_API_KEY
    to map the request to metrics (falls back to 400 if it can't)."""
    if "GROQ_API_KEY" not in os.environ:
        raise HTTPException(500, "GROQ_API_KEY not set in environment.")
    from .agent import _pick_metrics
    metrics, mode = _pick_metrics(req.query)
    if not metrics:
        raise HTTPException(400, "Could not map that request to any tracked stats.")
    return engine.search_by_traits(
        metrics, pos=req.pos, league=req.league,
        max_age=req.max_age, top_n=req.top_n, mode=mode)


class CompareRequest(BaseModel):
    names: List[str]
    query: Optional[str] = None   # optional aspect, e.g. "aerially" — picks metrics


@app.post("/compare")
def compare(req: CompareRequest):
    """Head-to-head comparison of two or more players on relevant metrics."""
    metrics = None
    if req.query and "GROQ_API_KEY" in os.environ:
        from .agent import _pick_metrics
        metrics, _ = _pick_metrics(req.query)
    return engine.compare(req.names, metrics=metrics)


@app.get("/intel/{name}")
def intel(name: str):
    """Live news / injury / discipline / transfer-rumour brief (Gemini + Search)."""
    from .intel import player_intel
    # enrich with squad/league from local data for disambiguation, if known
    squad = league = None
    idx, _ = engine.resolve(name)
    if idx is not None:
        r = engine.out.loc[idx]
        squad, league = r["squad"], r["league"]
    res = player_intel(name, squad, league)
    if not res["ok"] and res.get("error") in {"no_key", "genai_not_installed"}:
        raise HTTPException(503, res["message"])
    return res


@app.get("/gk/{name}")
def gk_player(name: str):
    """Resolve a goalkeeper name -> profile."""
    gk = _gk_or_503()
    idx, suggestions = gk.resolve(name)
    if idx is None:
        return {"ok": False, "query": name, "suggestions": suggestions or []}
    r = gk.gk.loc[idx]
    return {"ok": True, "player": r["player"], "squad": r["squad"],
            "league": r["league"], "position": "GK",
            "age": None if pd.isna(r["age"]) else float(r["age"])}


class SquadRequest(BaseModel):
    formation: Optional[str] = None
    roles: Optional[dict] = None
    budget_eur: Optional[float] = None
    query: Optional[str] = None        # style, e.g. "that presses" -> metrics
    league: Optional[str] = None
    max_age: Optional[int] = None


@app.post("/squad")
def squad(req: SquadRequest):
    """Assemble a lineup for a formation/roles, maximising style fit within a budget."""
    metrics = None
    if req.query and "GROQ_API_KEY" in os.environ:
        from .agent import _pick_metrics
        metrics, _ = _pick_metrics(req.query)
    return engine.build_squad(
        formation=req.formation, roles=req.roles, budget_eur=req.budget_eur,
        metrics=metrics, league=req.league, max_age=req.max_age)


# ---- agent (/chat) --------------------------------------------------------
# Imported lazily so the API still boots if GROQ_API_KEY isn't set yet.
class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatTurn]] = None   # prior turns — conversation memory


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        from .agent import run_agent
    except Exception as e:
        raise HTTPException(500, f"Agent unavailable: {e}")
    if "GROQ_API_KEY" not in os.environ:
        raise HTTPException(500, "GROQ_API_KEY not set in environment.")
    history = [t.model_dump() for t in (req.history or [])]
    return run_agent(req.message, history=history)
