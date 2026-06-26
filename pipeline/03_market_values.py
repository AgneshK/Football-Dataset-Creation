"""
AI Football Scout — Stage 3: Transfermarkt market-value join
=============================================================
Joins Transfermarkt market values (pulled by fetch_market_values.R) onto the
clean player dataset, producing scout_valued_<SEASON>.csv with a
`market_value_eur` column. This unlocks the agent's budget branch and provides
the training target for the (later) deep-learning value model.

The hard part is name matching: FBref and Transfermarkt spell players
differently ("Kylian Mbappé" vs "Kylian Mbappe", "Vini Jr." vs "Vinicius
Junior"). Strategy, in order:
  1. Exact normalized-name match. If a name is ambiguous (two players share it),
     disambiguate by closest age.
  2. Fuzzy match (rapidfuzz) for the remainder, above FUZZY_THRESHOLD.
  3. Anything still unmatched is written to a review CSV (no value assigned).

Run (from project root):  python pipeline/03_market_values.py
Reads:   data/processed/scout_clean_<SEASON>.csv  and  data/raw/market_values.csv
Writes:  data/processed/scout_valued_<SEASON>.csv
         data/processed/market_values_unmatched_<SEASON>.csv  (for manual review)
"""
import re
import sys
from pathlib import Path

import pandas as pd
from unidecode import unidecode

try:
    from rapidfuzz import process, fuzz
    HAVE_RAPIDFUZZ = True
except ImportError:
    HAVE_RAPIDFUZZ = False

SEASON = 2025
FUZZY_THRESHOLD = 88        # 0-100; below this we don't trust a fuzzy match
AGE_TOLERANCE = 2           # years, when disambiguating same-name players

ROOT = Path(__file__).resolve().parents[1]
PLAYERS_FILE = ROOT / "data" / "processed" / f"scout_clean_{SEASON}.csv"
TM_FILE      = ROOT / "data" / "raw" / "market_values.csv"
OUT_FILE     = ROOT / "data" / "processed" / f"scout_valued_{SEASON}.csv"
UNMATCHED    = ROOT / "data" / "processed" / f"market_values_unmatched_{SEASON}.csv"


def norm(s):
    """Same normalization the engine uses for name resolution."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"[^a-z ]", "", unidecode(s).lower()).strip()


def pick_col(df, candidates, what):
    """Find the first present column from a list of likely names."""
    for c in candidates:
        if c in df.columns:
            return c
    raise SystemExit(f"FATAL: couldn't find a {what} column in market_values.csv. "
                     f"Looked for {candidates}; got {list(df.columns)}")


def parse_value(v):
    """Coerce Transfermarkt value to a float in euros.

    worldfootballR usually gives a numeric `player_market_value_euro`, but be
    defensive about strings like '€40.00m' / '900Th.' just in case."""
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower().replace("€", "").replace(",", "")
    mult = 1.0
    if s.endswith("m"):
        mult, s = 1e6, s[:-1]
    elif s.endswith(("k", "th.", "th")):
        mult, s = 1e3, s.rstrip("th.").rstrip("k")
    try:
        return float(s) * mult
    except ValueError:
        return None


def main():
    if not TM_FILE.exists():
        sys.exit(f"FATAL: {TM_FILE} not found. Run pipeline/fetch_market_values.R first.")

    players = pd.read_csv(PLAYERS_FILE)
    tm = pd.read_csv(TM_FILE)
    print(f"Players: {len(players)}   Transfermarkt rows: {len(tm)}")

    name_col = pick_col(tm, ["player_name", "Player", "player"], "player-name")
    val_col  = pick_col(tm, ["player_market_value_euro", "market_value_euro",
                             "player_market_value", "market_value"], "market-value")
    age_col  = next((c for c in ["player_age", "age", "Age"] if c in tm.columns), None)

    tm = tm.copy()
    tm["_norm"] = tm[name_col].apply(norm)
    tm["_value"] = tm[val_col].apply(parse_value)
    tm["_age"] = pd.to_numeric(tm[age_col], errors="coerce") if age_col else pd.NA
    tm = tm[tm["_norm"].astype(bool) & tm["_value"].notna()]

    # Build lookup: normalized name -> list of (value, age)
    tm_groups = {}
    for _, r in tm.iterrows():
        tm_groups.setdefault(r["_norm"], []).append((r["_value"], r["_age"]))

    players = players.copy()
    players["_norm"] = players["player"].apply(norm)
    players["age_num"] = pd.to_numeric(players["age"], errors="coerce")

    values = [None] * len(players)
    methods = [""] * len(players)

    def resolve_candidates(cands, age):
        """From [(value, age), ...] pick one value, using age to disambiguate."""
        if len(cands) == 1:
            return cands[0][0]
        if pd.notna(age):
            scored = [(abs((a - age)) if pd.notna(a) else 99, v) for v, a in cands]
            scored.sort()
            if scored[0][0] <= AGE_TOLERANCE:
                return scored[0][1]
        # ambiguous and age didn't help: take the max value (most likely the
        # first-team player rather than a youth/duplicate)
        return max(v for v, _ in cands)

    # Pull columns to plain lists — itertuples mangles names starting with "_".
    p_norms = players["_norm"].tolist()
    p_ages = players["age_num"].tolist()

    # ---- pass 1: exact normalized-name match ----
    unmatched_pos = []
    for i in range(len(players)):
        nm = p_norms[i]
        if nm in tm_groups:
            values[i] = resolve_candidates(tm_groups[nm], p_ages[i])
            methods[i] = "exact"
        else:
            unmatched_pos.append(i)
    print(f"Exact matches: {len(players) - len(unmatched_pos)} / {len(players)}")

    # ---- pass 2: fuzzy match the remainder ----
    if unmatched_pos and HAVE_RAPIDFUZZ:
        tm_norms = list(tm_groups.keys())
        fuzzy_hits = 0
        for i in unmatched_pos:
            best = process.extractOne(p_norms[i], tm_norms, scorer=fuzz.WRatio,
                                      score_cutoff=FUZZY_THRESHOLD)
            if best:
                values[i] = resolve_candidates(tm_groups[best[0]], p_ages[i])
                methods[i] = f"fuzzy({int(best[1])})"
                fuzzy_hits += 1
        print(f"Fuzzy matches:  {fuzzy_hits} (threshold {FUZZY_THRESHOLD})")
    elif unmatched_pos and not HAVE_RAPIDFUZZ:
        print("rapidfuzz not installed — skipping fuzzy pass. "
              "`pip install rapidfuzz` to match more players.")

    players["market_value_eur"] = values
    players["_match_method"] = methods

    matched = players["market_value_eur"].notna().sum()
    print(f"\nTOTAL matched: {matched} / {len(players)} "
          f"({matched / len(players):.0%})")

    # ---- write outputs ----
    out = players.drop(columns=["_norm", "age_num", "_match_method"])
    out.to_csv(OUT_FILE, index=False)
    print(f"Wrote {OUT_FILE.name} ({out.shape[1]} cols)")

    miss = players[players["market_value_eur"].isna()][
        ["player", "squad", "league", "position", "age"]]
    miss.to_csv(UNMATCHED, index=False)
    print(f"Wrote {len(miss)} unmatched players -> {UNMATCHED.name} (for review)")


if __name__ == "__main__":
    main()
