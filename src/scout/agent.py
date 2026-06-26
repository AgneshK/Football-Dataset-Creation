"""
agent.py — LangGraph agent over the ScoutEngine
================================================
Flow:  parse (Groq LLM) -> route (by intent) -> capability node -> report (Groq LLM)

Capabilities:
  * clone    -> engine.find_clones()           [LIVE]
  * budget   -> clone + value filter           [STUB: needs Transfermarkt value]
  * archetype-> cluster lookup                 [STUB: needs clustering model]
  * value    -> undervalued detection          [STUB: needs DL value model]

Env:  GROQ_API_KEY must be set.
Model: llama-3.3-70b-versatile (good at structured parsing, fast on Groq)
"""
import os
import re
import json
from pathlib import Path
from typing import Optional, TypedDict, List

# Load GROQ_API_KEY (and friends) from a project-root .env if present, so the
# agent works whether launched via the API or `python -m scout.agent`.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ModuleNotFoundError:
    pass

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .engine import ScoutEngine
from .archetype import ArchetypeModel

MODEL = "llama-3.3-70b-versatile"
engine = ScoutEngine()              # shared single instance
archetypes = ArchetypeModel(engine)  # style clustering over the same engine


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------
class ScoutState(TypedDict, total=False):
    query: str                  # raw user message
    history: List[dict]         # prior [{role, content}] turns — conversation memory
    intent: str                 # clone | budget | archetype | value | unknown
    target: Optional[str]       # player name
    targets: List[str]          # multiple player names — compare intent
    league: Optional[str]
    pos: Optional[str]          # position/role hint (FW|MF|DF|CB|FB|DM)
    metrics: List[str]          # stat keys to rank by — discover/compare intents
    formation: Optional[str]    # e.g. "4-3-3" — squad intent
    roles: Optional[dict]       # e.g. {"FW": 3} — squad intent
    max_age: Optional[int]
    max_value_eur: Optional[float]
    top_n: int
    search: dict                # raw engine output
    answer: str                 # final natural-language report


def _history_messages(history, limit=8):
    """Convert stored [{role, content}] turns into LangChain messages so the LLM
    can resolve follow-ups ('now under 23') against the conversation."""
    msgs = []
    for turn in (history or [])[-limit:]:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        if turn.get("role") == "assistant":
            msgs.append(AIMessage(content=content[:1500]))
        else:
            msgs.append(HumanMessage(content=content[:1500]))
    return msgs


def _llm(temperature=0):
    return ChatGroq(model=MODEL, temperature=temperature,
                    api_key=os.environ["GROQ_API_KEY"])


# Scout-stat vocabulary the LLM can rank by for open-ended "find me a …" queries.
# Keys MUST be real engine feature columns (validated again in the engine).
METRIC_CATALOG = {
    # finishing & shooting
    "goals_per90": "goals per 90", "npxg_per90": "non-penalty expected goals per 90",
    "xg_per90": "expected goals per 90", "shots_per90": "shots per 90",
    "goals_per_shot": "finishing efficiency (goals per shot)",
    "touches_att_pen_per90": "touches in the opposition box per 90",
    # creation & passing
    "assists_per90": "assists per 90", "xag_per90": "expected assists per 90",
    "key_passes_per90": "key passes (shot-creating) per 90",
    "passes_final_third_per90": "passes into the final third per 90",
    "passes_pen_area_per90": "passes into the penalty area per 90",
    "crosses_per90": "crosses per 90",
    "pass_completion_pct": "pass completion %",
    # progression & carrying
    "prog_passes_per90": "progressive passes per 90",
    "prog_carries_per90": "progressive carries (ball-carrying upfield) per 90",
    "carries_per90": "total carries per 90",
    "prog_passes_received_per90": "progressive passes received (off-ball movement) per 90",
    "touches_per90": "touches per 90 (involvement)",
    # dribbling
    "take_ons_att_per90": "dribbles attempted per 90",
    "take_on_success_pct": "dribble success %",
    # defending
    "tackles_per90": "tackles per 90", "tackles_won_per90": "tackles won per 90",
    "tackles_def_third_per90": "tackles in own third per 90",
    "interceptions_per90": "interceptions per 90", "blocks_per90": "blocks per 90",
    "clearances_per90": "clearances per 90",
    "ball_recoveries_per90": "ball recoveries per 90",
    # aerial & physical
    "aerials_won_per90": "aerial duels won per 90",
    "aerial_win_pct": "aerial duel win %",
    "fouls_drawn_per90": "fouls drawn per 90",
    "fouls_committed_per90": "fouls committed per 90",
}

DISCOVER_SYS = """You translate a football scout's free-text request into the
statistical metrics that define it. Pick the most relevant metric KEYS (2-6,
fewer is better) from this catalogue:

{catalog}

Rules:
  * Use ONLY keys exactly as written above.
  * Choose metrics that capture the SPECIFIC traits asked for. E.g.
    "ball-carrying midfielder with progressive passing" ->
    ["prog_carries_per90","carries_per90","prog_passes_per90"].
    "clinical poacher" -> ["goals_per90","npxg_per90","goals_per_shot","touches_att_pen_per90"].
    "ball-winning destroyer" -> ["tackles_per90","interceptions_per90","ball_recoveries_per90"].
Also decide a "mode":
  * "total"  -> absolute SEASON volume / leaderboards ("most assists", "top scorer",
                "who made the most tackles this season", "leaders in goals").
  * "per90"  -> rates, efficiency, or general style/trait searches (the DEFAULT).
Respond with ONLY JSON: {{"metrics": ["key1", ...], "mode": "per90"|"total"}} — no prose, no fences."""

# Phrases that imply absolute season totals rather than per-90 rates.
_TOTAL_HINTS = re.compile(
    r"\b(most|total|tally|leader|leaders|leading|top\s+scorer|this season|"
    r"in total|overall|how many)\b", re.I)


# ---------------------------------------------------------------------------
# NODE 1: parse — LLM turns free text into structured intent + slots
# ---------------------------------------------------------------------------
PARSE_SYS = """You are a parser for a football scouting assistant.
Extract the user's request into JSON with EXACTLY these keys:
  intent: one of "clone", "budget", "archetype", "value", "intel", "counter", "discover", "compare", "squad", "unknown"
  target: the player name in focus — who they want similar players to, OR for "counter" the ATTACKER to be stopped (or null)
  targets: list of player names to compare head-to-head (only for "compare"; else [])
  formation: a formation string like "4-3-3" / "4-2-3-1" for "squad" requests, else null
  roles: for partial squad asks, an object of position->count, e.g. "front three"->{"FW":3}, "back four"->{"DF":4}, "a midfield three"->{"MF":3}; else null
  league: one of "Premier League","La Liga","Serie A","Bundesliga","Ligue 1" or null
  pos: position/role wanted, one of "FW","MF","DF","CB","FB","DM" or null (map "striker/forward/poacher/winger/attacker"->"FW", "centre-back/centre back"->"CB", "full-back/full back/wing-back"->"FB", "defensive/holding midfielder"->"DM", a generic "defender"->"DF", "midfielder"->"MF")
  max_age: integer or null
  max_value_eur: number in euros or null (e.g. "40M" -> 40000000)
  top_n: integer, default 8

Intent guide:
  "clone"     -> find similar players ("like X", "clone of X", "similar to X")
  "budget"    -> similar players under a price ("like X under 40M")
  "archetype" -> what type/style a player is ("what kind of striker is X")
  "value"     -> undervalued/overvalued players ("undervalued midfielders")
  "intel"     -> latest news, injury, suspension/discipline, or transfer rumours about a player ("any injury news on X", "what's the latest on X", "is X suspended", "transfer rumours for X")
  "counter"   -> find a DEFENDER / player to stop, mark, neutralise or nullify an ATTACKER ("a defender that can stop X", "who can mark X", "best CB to nullify X", "someone to handle X"). Put the attacker in `target`.
  "discover"  -> open-ended search for players by TRAITS / stats, NOT tied to a specific player ("find me a ball-carrying midfielder with progressive passes", "clinical poachers under 23", "aerially dominant centre-backs in Serie A", "high-pressing forwards"). Also use for superlatives / leaderboards ("who has the most assists", "top scorers in Serie A", "best dribblers"). Leave `target` null; set `pos` from any role mentioned.
  "compare"   -> head-to-head between two or more NAMED players ("compare X and Y", "X vs Y", "who is better, X or Y", "is X better than Y aerially"). Put every named player in `targets`.
  "squad"     -> build a team / lineup / XI or part of one within a budget ("build a 150M front three that presses", "a 4-3-3 under 600M", "best XI of under-21s", "give me a back four on a budget"). Set `formation` or `roles`; put the TOTAL budget in max_value_eur.
  "unknown"   -> a general football question that fits none of the above (still answer it)

FOLLOW-UPS: the conversation so far may be provided. If the latest message refines a
previous request (e.g. "now under 23", "only La Liga", "make it cheaper", "what about
wingers instead"), CARRY OVER the unstated fields from the previous request and apply
the change. Always output the COMPLETE merged request, not just the delta.

Respond with ONLY the JSON object, no prose, no markdown fences."""


def parse_node(state: ScoutState) -> ScoutState:
    msg = ([SystemMessage(content=PARSE_SYS)]
           + _history_messages(state.get("history"))
           + [HumanMessage(content=state["query"])])
    raw = _llm().invoke(msg).content.strip()
    # strip accidental code fences
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(raw)
    except Exception:
        data = {"intent": "unknown"}
    return {
        "intent": data.get("intent", "unknown"),
        "target": data.get("target"),
        "targets": data.get("targets") or [],
        "league": data.get("league"),
        "pos": data.get("pos"),
        "metrics": data.get("metrics") or [],
        "formation": data.get("formation"),
        "roles": data.get("roles"),
        "max_age": data.get("max_age"),
        "max_value_eur": data.get("max_value_eur"),
        "top_n": data.get("top_n") or 8,
    }


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------
_KNOWN_INTENTS = {"clone", "budget", "archetype", "value", "intel",
                  "counter", "discover", "compare", "squad"}


def route(state: ScoutState) -> str:
    intent = state.get("intent", "unknown")
    return intent if intent in _KNOWN_INTENTS else "unknown"


# ---------------------------------------------------------------------------
# NODE 2a: clone search (LIVE)
# ---------------------------------------------------------------------------
def clone_node(state: ScoutState) -> ScoutState:
    if not state.get("target"):
        return {"search": {"ok": False, "error": "no_target"}}
    res = engine.find_clones(
        state["target"], league=state.get("league"),
        top_n=state.get("top_n", 8), max_age=state.get("max_age"))
    # Goalkeepers aren't in the outfield engine — fall back to the GK engine so
    # "find a clone of Alisson" works through chat too.
    if not res.get("ok") and res.get("error") == "player_not_found":
        from .gk_engine import get_gk_engine
        gk = get_gk_engine()
        if gk is not None:
            gk_res = gk.find_clones(
                state["target"], league=state.get("league"),
                top_n=state.get("top_n", 8), max_age=state.get("max_age"))
            if gk_res.get("ok"):
                return {"search": gk_res}
    return {"search": res}


# ---------------------------------------------------------------------------
# NODE 2b: budget (STUB — needs market value join)
# ---------------------------------------------------------------------------
def budget_node(state: ScoutState) -> ScoutState:
    if not state.get("target"):
        return {"search": {"ok": False, "error": "no_target"}}
    res = engine.find_clones(
        state["target"], league=state.get("league"),
        top_n=state.get("top_n", 8), max_age=state.get("max_age"),
        max_value_eur=state.get("max_value_eur"))
    # find_clones sets its own _note explaining whether the budget was applied
    # (live when the Transfermarkt join has run, ignored with a note otherwise).
    return {"search": res}


# ---------------------------------------------------------------------------
# NODE 2c / 2d: archetype + value (STUBS — models not built yet)
# ---------------------------------------------------------------------------
def archetype_node(state: ScoutState) -> ScoutState:
    if not state.get("target"):
        return {"search": {"ok": False, "error": "no_target",
                "message": "Tell me which player's style you want analysed."}}
    return {"search": archetypes.describe(state["target"])}


def value_node(state: ScoutState) -> ScoutState:
    from .value_model import get_predictor
    vp = get_predictor()
    if vp is None:
        return {"search": {"ok": False, "not_implemented": "value",
                "message": "Value model not trained yet. "
                           "Run pipeline/04_train_value_model.py."}}
    # If a specific player was named, give a single-player verdict; otherwise
    # return the most undervalued players (optionally filtered by league/age).
    if state.get("target"):
        return {"search": vp.value_report(engine, state["target"])}
    return {"search": vp.undervalued(
        engine, league=state.get("league"), max_age=state.get("max_age"),
        top_n=state.get("top_n", 10))}


# ---------------------------------------------------------------------------
# NODE 2e: intel (LIVE) — Gemini + Google Search for news/injury/rumours
# ---------------------------------------------------------------------------
def intel_node(state: ScoutState) -> ScoutState:
    if not state.get("target"):
        return {"search": {"ok": False, "error": "no_target",
                "message": "Which player do you want news / injury / rumour intel on?"}}
    from .intel import player_intel
    # enrich with squad/league from the local data for disambiguation
    squad = league = None
    idx, _ = engine.resolve(state["target"])
    if idx is not None:
        r = engine.out.loc[idx]
        squad, league = r["squad"], r["league"]
    return {"search": player_intel(state["target"], squad, league)}


# ---------------------------------------------------------------------------
# NODE 2f: counter (LIVE) — find defenders to neutralise an attacker
# ---------------------------------------------------------------------------
def counter_node(state: ScoutState) -> ScoutState:
    if not state.get("target"):
        return {"search": {"ok": False, "error": "no_target",
                "message": "Which attacker do you want a defender to stop?"}}
    res = engine.find_counters(
        state["target"], league=state.get("league"),
        max_age=state.get("max_age"), top_n=state.get("top_n", 8),
        pos=state.get("pos"))
    return {"search": res}


# ---------------------------------------------------------------------------
# NODE 2g: discover (LIVE) — open-ended trait search ("find me a … with …")
# ---------------------------------------------------------------------------
def _pick_metrics(query: str, history=None):
    """Second LLM hop: map the request to ranking metrics + a value mode.
    Kept separate from the main parser so the big catalogue only loads here.
    Returns (metrics: list[str], mode: 'per90'|'total')."""
    catalog = "\n".join(f"  {k}: {v}" for k, v in METRIC_CATALOG.items())
    msg = ([SystemMessage(content=DISCOVER_SYS.format(catalog=catalog))]
           + _history_messages(history)
           + [HumanMessage(content=query)])
    raw = _llm().invoke(msg).content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    metrics, mode = [], None
    try:
        data = json.loads(raw)
        metrics = data.get("metrics", [])
        mode = data.get("mode")
    except Exception:
        # the model sometimes injects prose into the JSON array, breaking the
        # parse — fall back to scanning the raw text for known catalogue keys.
        metrics = re.findall(r"[a-z_]+_(?:per90|pct)|goals_per_shot", raw)
    # keep only catalogue keys, preserve order, de-dup
    seen, out = set(), []
    for m in metrics:
        if m in METRIC_CATALOG and m not in seen:
            seen.add(m); out.append(m)
    # keyword backstop so "most assists" -> totals even if the JSON mode was lost
    if mode not in ("per90", "total"):
        mode = "total" if _TOTAL_HINTS.search(query or "") else "per90"
    return out, mode


def discover_node(state: ScoutState) -> ScoutState:
    metrics, mode = _pick_metrics(state["query"], state.get("history"))
    if not metrics:
        return {"search": {"ok": False, "error": "no_metrics",
                "message": "Tell me which qualities to look for "
                           "(e.g. 'progressive passing', 'aerial duels', 'dribbling')."}}
    res = engine.search_by_traits(
        metrics, pos=state.get("pos"), league=state.get("league"),
        max_age=state.get("max_age"), top_n=state.get("top_n", 10), mode=mode)
    return {"search": res}


# ---------------------------------------------------------------------------
# NODE 2h: compare (LIVE) — head-to-head between named players
# ---------------------------------------------------------------------------
def compare_node(state: ScoutState) -> ScoutState:
    names = list(state.get("targets") or [])
    # tolerate the parser putting one name in `target`
    if state.get("target") and state["target"] not in names:
        names.append(state["target"])
    if len(names) < 2:
        return {"search": {"ok": False, "error": "need_two",
                "message": "Name at least two players to compare, e.g. "
                           "'compare Rodri and Bellingham'."}}
    # pick aspect-specific metrics if the user asked about one ("aerially");
    # engine.compare falls back to a position default when none are found.
    metrics, _ = _pick_metrics(state["query"], state.get("history"))
    return {"search": engine.compare(names, metrics=metrics)}


# ---------------------------------------------------------------------------
# NODE 2j: squad (LIVE) — build a lineup within a budget
# ---------------------------------------------------------------------------
def squad_node(state: ScoutState) -> ScoutState:
    # style metrics from the request ("that presses", "creative") shape the fit;
    # the engine falls back to position defaults when none are picked.
    metrics, _ = _pick_metrics(state["query"], state.get("history"))
    res = engine.build_squad(
        formation=state.get("formation"), roles=state.get("roles"),
        budget_eur=state.get("max_value_eur"), metrics=metrics,
        league=state.get("league"), max_age=state.get("max_age"))
    return {"search": res}


# ---------------------------------------------------------------------------
# NODE 2i: general (LIVE) — conversational fallback so any query is answered
# ---------------------------------------------------------------------------
GENERAL_SYS = """You are a knowledgeable, friendly football scouting assistant.
Answer the user's question directly and conversationally. You have specialist tools
for: statistical clones, playing-style archetypes, market-value estimates, live
news/injury intel, defenders to counter an attacker, open-ended trait search, and
head-to-head comparisons — all over a Big-5 leagues 2024/25 dataset. If the question
would be better served by one of those, answer what you can and invite the user to
ask in that form. Be honest when something needs live data or isn't in a 2024/25
stats dataset; do not invent specific statistics. Keep it concise."""


def general_node(state: ScoutState) -> ScoutState:
    msg = [SystemMessage(content=GENERAL_SYS),
           HumanMessage(content=state["query"])]
    answer = _llm(temperature=0.5).invoke(msg).content.strip()
    return {"search": {"ok": True, "mode": "general", "answer": answer}}


# ---------------------------------------------------------------------------
# NODE 3: report — LLM writes the scouting writeup from search results
# ---------------------------------------------------------------------------
REPORT_SYS = """You are a professional football scout writing a concise report.
You are given a target player and a ranked list of statistically similar players.
Write 2-4 short paragraphs:
  * Open with the target and what kind of player they are.
  * Discuss the top 2-3 matches, noting they are STATISTICAL style comparisons
    (per-90 output, shooting, progression, defensive actions), not identical players.
  * Be honest about similarity scores: ~0.8+ strong, ~0.6-0.8 moderate, below weak.
Do not invent stats not provided. Keep it crisp and useful to a recruiter."""

ARCHETYPE_SYS = """You are a professional football scout describing a player's STYLE.
You are given a target player, the statistical archetype they were clustered into,
the signature stats that define that archetype, a "fit" score, and a few exemplar
players of the same archetype. Write 2-3 short paragraphs:
  * State the archetype and what that role/style means in plain football terms.
  * Use the signature stats to justify it (these are per-90 / percentage style
    metrics, z-scored within position group — i.e. relative to similar players).
  * Interpret the fit score: ~1.0 = a textbook example of this archetype,
    ~0.5 = a clear member, near 0 = an atypical/edge case who blends styles.
  * Mention 1-2 exemplar players as reference points.
Do not invent stats not provided. Keep it crisp and useful to a recruiter."""

VALUE_SYS = """You are a football recruitment analyst discussing market value.
You are given model output: either a single player's predicted vs actual market
value with a verdict, or a list of the most undervalued players. Write 2-3 short
paragraphs:
  * Be clear these are MODEL ESTIMATES from on-pitch stats + age, not transfer
    quotes — a model that thinks a player is "underpriced" reflects statistical
    output, not insider knowledge.
  * For a single player: state predicted vs actual and what the verdict implies.
  * For a list: highlight the top 2-3 names, their actual vs predicted value, and
    why a recruiter might look closer. Note that extreme ratios can be noise.
Use euros, keep numbers rounded and readable. Do not invent stats not provided."""


COUNTER_SYS = """You are a tactical football scout recommending players to NEUTRALISE a specific attacker.
You are given the attacker, a "threat profile" (the statistical strengths that make them dangerous,
each with a weight), and a ranked list of defenders / defensive midfielders with a counter-fit score
and their standout defensive strengths. Write 2-4 short paragraphs:
  * Open by characterising the attacker's threat in plain football terms from the threat profile
    (e.g. aerial presence, clinical box finishing, 1v1 dribbling, runs in behind) — lead with the
    highest-weight threats.
  * Recommend the top 2-3 names. For each, tie their strengths to the SPECIFIC threat they blunt
    (aerials won / aerial win % vs an aerial threat; tackles & interceptions vs a dribbler; blocks &
    clearances vs a box finisher). Mention squad and position.
  * Be honest: this is a statistical matchup from per-90 defensive output, not a guarantee — stopping
    a top forward is a team job. The counter-fit score is relative to all defenders in the pool.
Do not invent stats not provided. Be crisp and useful to a coach or recruiter."""


DISCOVER_SYS_REPORT = """You are a football scout answering an open-ended player search.
You are given the user's request, the statistical metrics used to rank candidates,
and a ranked shortlist (each with the relevant stats and a trait-fit score that is
relative to the filtered pool). `value_mode` tells you whether the stats are season
TOTALS ("total") or per-90 RATES ("per90") — state which you're quoting. Write 2-3
short paragraphs:
  * Restate what was searched for in plain terms and which stats define it.
  * Highlight the top 3-4 names, citing their actual stat values to justify the pick
    (e.g. progressive carries, progressive passes). Mention squad, league, age.
  * Note the ranking is a statistical fit on the chosen traits, not a full scouting
    judgement (tactics, fit, level of competition still matter).
Do not invent stats not provided. Be crisp and useful to a recruiter."""


COMPARE_SYS = """You are a football scout writing a head-to-head comparison.
You are given two or more players, the metrics being compared (per-90 / percentage),
each player's values, and the per-metric leader. Write 2-3 short paragraphs:
  * Open by framing the comparison and the players' roles/teams.
  * Go metric by metric (or theme by theme) citing the actual numbers, and say who
    leads each and by how much.
  * Close with a balanced verdict — who edges it overall or in what aspect each is
    stronger. Avoid declaring a flat 'winner' if it's close; note context matters.
Do not invent stats not provided. Be crisp and useful to a recruiter."""


SQUAD_SYS = """You are a football scout presenting a squad you assembled.
You are given the formation/roles, the total budget, the total cost, whether it fit
the budget, the style metrics used, and the chosen lineup (each with position, club,
age, market value and a style-fit score). Write 2-3 short paragraphs:
  * State the shape, the budget, and the total cost (note if it came in under or, if
    flagged, couldn't fully fit).
  * Call out the spine / standout picks and how they match the requested style.
  * Be clear picks are ranked on the chosen statistical traits within position, not a
    full scouting judgement; market values are estimates.
Use euros, rounded. Do not invent players or stats not provided."""


def report_node(state: ScoutState) -> ScoutState:
    search = state.get("search", {})
    # general fallback already produced a complete conversational answer
    if search.get("mode") == "general":
        return {"answer": search.get("answer") or "Sorry, I couldn't answer that."}
    if not search.get("ok") and search.get("mode") == "squad":
        return {"answer": search.get("message") or "Couldn't build that squad."}
    if not search.get("ok"):
        msg = search.get("message") or search.get("error") or "No results."
        sugg = search.get("suggestions")
        if sugg:
            msg += " Did you mean: " + ", ".join(sugg) + "?"
        return {"answer": msg}

    if search.get("mode") == "compare":
        payload = json.dumps({
            "metrics": search.get("metrics"),
            "players": search.get("players"),
            "leaders": search.get("leaders"),
        }, default=str)
        msg = [SystemMessage(content=COMPARE_SYS),
               HumanMessage(content="Comparison data:\n" + payload)]
        answer = _llm(temperature=0.4).invoke(msg).content.strip()
        return {"answer": answer}

    if search.get("mode") == "squad":
        payload = json.dumps({
            "formation": search.get("formation"), "roles": search.get("roles"),
            "budget_eur": search.get("budget_eur"),
            "total_value_eur": search.get("total_value_eur"),
            "within_budget": search.get("within_budget"),
            "style_metrics": search.get("style_metrics"),
            "lineup": search.get("lineup"), "note": search.get("note"),
        }, default=str)
        msg = [SystemMessage(content=SQUAD_SYS),
               HumanMessage(content="Squad data:\n" + payload)]
        answer = _llm(temperature=0.4).invoke(msg).content.strip()
        return {"answer": answer}

    if search.get("mode") == "intel":
        # Gemini already wrote a grounded brief — pass it through with sources.
        ans = search.get("report") or "No intel found."
        src = search.get("sources") or []
        if src:
            ans += "\n\nSources:\n" + "\n".join(
                f"- {s['title']} — {s['uri']}" for s in src)
        return {"answer": ans}

    if search.get("mode") == "discover":
        payload = json.dumps({
            "request": state.get("query"),
            "metrics": search.get("metrics"),
            "value_mode": search.get("value_mode"),  # "total" or "per90"
            "filters": search.get("filters"),
            "results": search.get("results"),
        }, default=str)
        msg = [SystemMessage(content=DISCOVER_SYS_REPORT),
               HumanMessage(content="Search data:\n" + payload)]
        answer = _llm(temperature=0.4).invoke(msg).content.strip()
        return {"answer": answer}

    if search.get("mode") == "counter":
        payload = json.dumps({
            "attacker": search.get("target"),
            "threat_profile": search.get("threat"),
            "candidates": search.get("results"),
            "filters": search.get("filters"),
        }, default=str)
        msg = [SystemMessage(content=COUNTER_SYS),
               HumanMessage(content="Matchup data:\n" + payload)]
        answer = _llm(temperature=0.4).invoke(msg).content.strip()
        return {"answer": answer}

    if search.get("mode") == "value":
        payload = json.dumps({
            "target": search.get("target"),
            "verdict": search.get("verdict"),
            "predicted_value_eur": search.get("predicted_value_eur"),
            "actual_value_eur": search.get("actual_value_eur"),
            "ratio": search.get("ratio"),
            "undervalued_players": search.get("results"),
            "model": search.get("model"),
        }, default=str)
        msg = [SystemMessage(content=VALUE_SYS),
               HumanMessage(content="Value data:\n" + payload)]
        answer = _llm(temperature=0.4).invoke(msg).content.strip()
        return {"answer": answer}

    if search.get("mode") == "archetype":
        payload = json.dumps({
            "target": search.get("target"),
            "archetype": search.get("archetype"),
            "exemplars": search.get("peers"),
        }, default=str)
        msg = [SystemMessage(content=ARCHETYPE_SYS),
               HumanMessage(content="Scout data:\n" + payload)]
        answer = _llm(temperature=0.4).invoke(msg).content.strip()
        return {"answer": answer}

    payload = json.dumps({
        "target": search.get("target"),
        "filters": search.get("filters"),
        "results": search.get("results"),
        "note": search.get("_note"),
    }, default=str)
    msg = [SystemMessage(content=REPORT_SYS),
           HumanMessage(content="Scout data:\n" + payload)]
    answer = _llm(temperature=0.4).invoke(msg).content.strip()
    return {"answer": answer}


# ---------------------------------------------------------------------------
# BUILD GRAPH
# ---------------------------------------------------------------------------
def build_agent():
    g = StateGraph(ScoutState)
    g.add_node("parse", parse_node)
    g.add_node("clone", clone_node)
    g.add_node("budget", budget_node)
    g.add_node("archetype", archetype_node)
    g.add_node("value", value_node)
    g.add_node("intel", intel_node)
    g.add_node("counter", counter_node)
    g.add_node("discover", discover_node)
    g.add_node("compare", compare_node)
    g.add_node("squad", squad_node)
    g.add_node("unknown", general_node)
    g.add_node("report", report_node)

    g.set_entry_point("parse")
    g.add_conditional_edges("parse", route, {
        "clone": "clone", "budget": "budget", "archetype": "archetype",
        "value": "value", "intel": "intel", "counter": "counter",
        "discover": "discover", "compare": "compare", "squad": "squad",
        "unknown": "unknown",
    })
    for n in ["clone", "budget", "archetype", "value", "intel", "counter",
              "discover", "compare", "squad", "unknown"]:
        g.add_edge(n, "report")
    g.add_edge("report", END)
    return g.compile()


agent = build_agent()


def run_agent(query: str, history=None) -> dict:
    final = agent.invoke({"query": query, "history": history or []})
    search = final.get("search", {})
    return {
        "query": query,
        "intent": final.get("intent"),
        "parsed": {k: final.get(k) for k in
                   ["target", "league", "pos", "formation", "roles",
                    "max_age", "max_value_eur", "top_n"]},
        # discover intent: the stat keys the shortlist was ranked by
        "metrics": search.get("metrics"),
        # compare intent: per-player values + per-metric leaders
        "players": search.get("players"),
        "leaders": search.get("leaders"),
        # squad intent: the assembled lineup + budget summary
        "lineup": search.get("lineup"),
        "formation": search.get("formation"),
        "budget_eur": search.get("budget_eur"),
        "total_value_eur": search.get("total_value_eur"),
        "within_budget": search.get("within_budget"),
        # clones use "results"; archetype uses "peers" — surface whichever exists
        "target": search.get("target"),
        "results": search.get("results") or search.get("peers") or [],
        "radar": search.get("radar"),
        "archetype": search.get("archetype"),
        # counter intent: the attacker's threat profile (None for other intents)
        "threat": search.get("threat"),
        # value single-player verdict fields (None for other intents)
        "verdict": search.get("verdict"),
        "predicted_value_eur": search.get("predicted_value_eur"),
        "actual_value_eur": search.get("actual_value_eur"),
        "ratio": search.get("ratio"),
        "sources": search.get("sources"),
        "answer": final.get("answer"),
    }


if __name__ == "__main__":
    # quick manual test (requires GROQ_API_KEY)
    for q in ["find me a clone of Harry Kane in La Liga",
              "what kind of player is Rodri",
              "show me undervalued midfielders",
              "a winger like Lamine Yamal under 23"]:
        print("\n" + "=" * 70 + f"\nQ: {q}")
        out = run_agent(q)
        print("intent:", out["intent"], "| parsed:", out["parsed"])
        print(out["answer"][:500])
