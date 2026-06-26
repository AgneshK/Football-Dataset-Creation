"""
intel.py — live player intelligence via Gemini 2.5 Pro + Google Search
=======================================================================
The local dataset is a season snapshot — it can't know about last week's injury,
a new suspension, or a transfer rumour. This module asks Gemini 2.5 Pro, grounded
with Google Search, to compile a current intelligence brief on a player and
returns it with its web sources.

Lazy + defensive: imports without the SDK or key, and every call returns a
structured {ok: False, ...} instead of raising, so the API/agent stay up.

Env: GEMINI_API_KEY (required), GEMINI_MODEL (optional, default gemini-2.5-pro).
"""
import os
from datetime import date

from .engine import SEASON

try:
    from google import genai
    from google.genai import types
    HAVE_GENAI = True
except ImportError:
    HAVE_GENAI = False

DEFAULT_MODEL = "gemini-2.5-pro"
DATA_SEASON = f"{SEASON - 1}/{str(SEASON)[-2:]}"   # 2025 -> "2024/25"

PROMPT = """You are a football scout's research assistant. The statistical profile
on file for {who} is from the {season} season — so this brief's job is to add the
CURRENT real-world context that those season stats can't show: what's happened
since, and where things stand today. Today is {today}.

Use these markdown sections (omit one only if there is genuinely nothing):
### Current status & recent form
### Injury status
### Disciplinary record
### Transfer rumours

Then add:
### What's changed since {season}
- Flag anything that changes how the {season} stats should be read now — a club
  move, a long-term injury, a clear decline or breakout, a position/role change,
  or a big drop in minutes. If little has changed, say so.

Rules:
- Prioritise the last few months; lead with the most recent items, with dates.
- Mark anything unconfirmed (especially rumours) as such.
- Be concise — short bullets, no filler. Never invent specifics; if unknown, say so.
"""


def _model() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def player_intel(name: str, squad: str | None = None, league: str | None = None) -> dict:
    """Return {ok, mode, player, report (markdown), sources, model} or an error dict."""
    if not HAVE_GENAI:
        return {"ok": False, "error": "genai_not_installed",
                "message": "google-genai is not installed (pip install google-genai)."}
    if not os.environ.get("GEMINI_API_KEY"):
        return {"ok": False, "error": "no_key",
                "message": "GEMINI_API_KEY not set — add it to .env to enable player intel."}

    who = name
    if squad:
        who += f" ({squad}{', ' + league if league else ''})"
    prompt = PROMPT.format(who=who, today=date.today().isoformat(), season=DATA_SEASON)

    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
            ),
        )
    except Exception as e:  # network / auth / quota — keep the service alive
        return {"ok": False, "error": "gemini_error", "message": str(e)}

    # collect grounding sources (deduped, capped)
    sources, seen = [], set()
    try:
        gm = resp.candidates[0].grounding_metadata
        for ch in (gm.grounding_chunks or []):
            web = getattr(ch, "web", None)
            uri = getattr(web, "uri", None) if web else None
            if uri and uri not in seen:
                seen.add(uri)
                sources.append({"title": getattr(web, "title", None) or uri, "uri": uri})
    except Exception:
        pass

    return {
        "ok": True,
        "mode": "intel",
        "player": name,
        "report": (resp.text or "").strip(),
        "sources": sources[:8],
        "model": _model(),
    }
