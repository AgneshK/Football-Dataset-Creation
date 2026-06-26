"""
AI Football Scout — Stage 5: build the goalkeeper dataset
==========================================================
Goalkeepers live in a different statistical universe (saves, PSxG, distribution,
sweeping) than outfield players, so they get their own table and engine. This
joins the two keeper tables, selects + renames GK-relevant stats, derives per-90s,
and applies a minutes filter.

Run (from project root):  python pipeline/05_build_gk.py
Reads:   data/raw/big5_players_keepers_<SEASON>.csv
         data/raw/big5_players_keepers_adv_<SEASON>.csv
Writes:  data/processed/scout_gk_<SEASON>.csv
"""
from pathlib import Path
import pandas as pd

SEASON = 2025
MIN_MINUTES = 500
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / f"scout_gk_{SEASON}.csv"
JOIN = ["Player", "Squad"]


def num(s):
    return pd.to_numeric(s, errors="coerce")


def main():
    kp = pd.read_csv(RAW / f"big5_players_keepers_{SEASON}.csv")
    adv = pd.read_csv(RAW / f"big5_players_keepers_adv_{SEASON}.csv")
    print(f"keepers: {kp.shape}   keepers_adv: {adv.shape}")

    # inner-join; keep keepers' identity cols, suffix any adv duplicates
    m = kp.merge(adv, on=JOIN, how="inner", suffixes=("", "__adv"))
    print(f"joined: {len(m)} goalkeepers")

    nineties = num(m["Mins_Per_90"]).replace(0, pd.NA)
    c = pd.DataFrame()
    # identity / meta
    c["player"] = m["Player"]
    c["squad"] = m["Squad"]
    c["league"] = m["Comp"]
    c["nation"] = m["Nation"]
    c["position"] = m["Pos"]
    c["age"] = num(m["Age"])
    c["born_year"] = num(m["Born"])
    c["player_type"] = "GK"
    c["minutes"] = num(m["Min_Playing"])
    c["matches_played"] = num(m["MP_Playing"])
    c["starts"] = num(m["Starts_Playing"])
    c["nineties"] = num(m["Mins_Per_90"])

    # ---- style/quality features ----
    # shot-stopping
    c["save_pct"] = num(m["Save_percent"])
    c["psxg_per_sot"] = num(m["PSxG_per_SoT_Expected"])
    c["psxg_plus_minus_per90"] = num(m["_per_90_Expected"])
    c["cs_pct"] = num(m["CS_percent"])
    # workload
    c["ga_per90"] = num(m["GA90"])
    c["sota_per90"] = (num(m["SoTA"]) / nineties)
    c["saves_per90"] = (num(m["Saves"]) / nineties)
    # distribution
    c["launched_cmp_pct"] = num(m["Cmp_percent_Launched"])
    c["launch_pct_passes"] = num(m["Launch_percent_Passes"])
    c["avg_pass_len"] = num(m["AvgLen_Passes"])
    c["throws_per90"] = (num(m["Thr_Passes"]) / nineties)
    c["gk_passes_per90"] = (num(m["Att (GK)_Passes"]) / nineties)
    c["goalkick_launch_pct"] = num(m["Launch_percent_Goal"])
    c["goalkick_avg_len"] = num(m["AvgLen_Goal"])
    # cross-claiming + sweeping
    c["cross_stop_pct"] = num(m["Stp_percent_Crosses"])
    c["crosses_faced_per90"] = (num(m["Opp_Crosses"]) / nineties)
    c["sweeper_per90"] = num(m["#OPA_per_90_Sweeper"])
    c["sweeper_avg_dist"] = num(m["AvgDist_Sweeper"])

    before = len(c)
    c = c[c["minutes"] >= MIN_MINUTES].copy()
    print(f"minutes filter (>= {MIN_MINUTES}): {before} -> {len(c)} goalkeepers")

    # round derived per-90s for a tidy file
    per90 = ["sota_per90", "saves_per90", "throws_per90", "gk_passes_per90",
             "crosses_faced_per90"]
    c[per90] = c[per90].round(3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    c.to_csv(OUT, index=False)
    print(f"Wrote {len(c)} GKs x {c.shape[1]} cols -> {OUT}")


if __name__ == "__main__":
    main()
