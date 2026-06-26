"""
AI Football Scout — prep the Kaggle Transfermarkt dataset
==========================================================
Converts the Kaggle "player-scores" (Football Data from Transfermarkt) dump into
the single market_values.csv that pipeline/03_market_values.py expects.

Why a prep step: that dataset is several CSVs, and its *current* market value
reflects whenever the snapshot was taken (likely a later season than our stats).
The value model needs the value CONTEMPORANEOUS with the 2024/25 stats, so we use
the historical player_valuations.csv and take each player's latest valuation
inside the 2024/25 window. We fall back to the current value only if a player has
no valuation in that window (or if player_valuations.csv isn't provided).

Setup:
  1. Download from kaggle.com/datasets/davidcariboo/player-scores (browser is fine).
  2. Unzip and put at least players.csv (and ideally player_valuations.csv) into
     data/raw/transfermarkt/.
  3. Run (from project root):  python pipeline/prep_kaggle_values.py
     -> writes data/raw/market_values.csv
  4. Then:  python pipeline/03_market_values.py
"""
import sys
from pathlib import Path

import pandas as pd

SEASON = 2025
SEASON_START = pd.Timestamp("2024-07-01")   # 2024/25 window
SEASON_END   = pd.Timestamp("2025-06-30")
AGE_REF      = pd.Timestamp("2025-01-01")    # mid-season, for age

ROOT = Path(__file__).resolve().parents[1]
TM_DIR     = ROOT / "data" / "raw" / "transfermarkt"
PLAYERS    = TM_DIR / "players.csv"
VALUATIONS = TM_DIR / "player_valuations.csv"
OUT        = ROOT / "data" / "raw" / "market_values.csv"


def pick(df, candidates, what):
    for c in candidates:
        if c in df.columns:
            return c
    sys.exit(f"FATAL: no {what} column found. Looked for {candidates}; "
             f"got {list(df.columns)}")


def main():
    if not PLAYERS.exists():
        sys.exit(f"FATAL: {PLAYERS} not found.\n"
                 f"Download kaggle.com/datasets/davidcariboo/player-scores, unzip, "
                 f"and place players.csv (+ player_valuations.csv) in {TM_DIR}/.")

    players = pd.read_csv(PLAYERS)
    pid   = pick(players, ["player_id"], "player-id")
    pname = pick(players, ["name", "player_name", "pretty_name"], "player-name")
    pcur  = pick(players, ["market_value_in_eur", "market_value", "current_market_value"],
                 "current-value")
    pdob  = next((c for c in ["date_of_birth", "dob"] if c in players.columns), None)

    base = players[[pid, pname, pcur]].rename(
        columns={pid: "player_id", pname: "player_name", pcur: "current_value"})
    if pdob:
        dob = pd.to_datetime(players[pdob], errors="coerce")
        base["player_age"] = ((AGE_REF - dob).dt.days // 365).astype("Int64")
    else:
        base["player_age"] = pd.NA

    season_value = pd.Series(dtype="float64")
    if VALUATIONS.exists():
        val = pd.read_csv(VALUATIONS)
        vid   = pick(val, ["player_id"], "player-id")
        vdate = pick(val, ["date", "datetime", "dateweek"], "date")
        vval  = pick(val, ["market_value_in_eur", "market_value"], "value")
        val[vdate] = pd.to_datetime(val[vdate], errors="coerce")
        window = val[(val[vdate] >= SEASON_START) & (val[vdate] <= SEASON_END)].copy()
        # latest valuation per player inside the window
        window = window.sort_values(vdate).groupby(vid).tail(1)
        season_value = window.set_index(vid)[vval]
        print(f"player_valuations.csv: {len(val)} rows, "
              f"{len(window)} players valued in the 2024/25 window")
    else:
        print("player_valuations.csv not provided — using current values only "
              "(note: may not match the 2024/25 season).")

    # season value where available, else current snapshot value
    base["player_market_value_euro"] = (
        base["player_id"].map(season_value).fillna(base["current_value"]))
    base = base[base["player_market_value_euro"].notna()]
    used_window = base["player_id"].map(season_value).notna().sum()

    out = base[["player_name", "player_age", "player_market_value_euro"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {len(out)} players -> {OUT}")
    print(f"  {used_window} from the 2024/25 valuation window, "
          f"{len(out) - used_window} from the current-value fallback")


if __name__ == "__main__":
    main()
