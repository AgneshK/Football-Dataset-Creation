"""
AI Football Scout — Stage 2: Select & Rename
=============================================
Takes the 229-column joined file and selects the ~45 columns that matter,
renames them to clean schema names, computes per-90s, and tags the
similarity-feature columns. Output is model-ready.

Run (from project root):  python pipeline/02_select_rename.py
Reads:   data/processed/scout_dataset_<SEASON>.csv
Writes:  data/processed/scout_clean_<SEASON>.csv
"""
from pathlib import Path
import pandas as pd

SEASON = 2025

ROOT = Path(__file__).resolve().parents[1]
IN_FILE  = ROOT / "data" / "processed" / f"scout_dataset_{SEASON}.csv"
OUT_FILE = ROOT / "data" / "processed" / f"scout_clean_{SEASON}.csv"

df = pd.read_csv(IN_FILE)

# ---------------------------------------------------------------------------
# MAP: clean_name -> source_column  (exact worldfootballR names)
# ---------------------------------------------------------------------------
RENAME = {
    # identity / meta
    "player":            "Player",
    "squad":             "Squad",
    "league":            "Comp__std",
    "nation":            "Nation__std",
    "position":          "Pos__std",
    "age":               "Age__std",
    "born_year":         "Born__std",
    "player_type":       "player_type",
    # playing time
    "minutes":           "Min_Playing__std",
    "matches_played":    "MP_Playing__std",
    "starts":            "Starts_Playing__std",
    "nineties":          "Mins_Per_90_Playing__std",
    # attacking output (totals; we per-90 below)
    "goals":             "Gls__std",
    "assists":           "Ast__std",
    "np_goals":          "G_minus_PK__std",
    "xg":                "xG_Expected__std",
    "npxg":              "npxG_Expected__std",
    "xag":               "xAG_Expected__std",
    # pre-computed per-90 from FBref (handy, already normalised)
    "goals_per90":       "Gls_Per__std",
    "assists_per90":     "Ast_Per__std",
    "xg_per90":          "xG_Per__std",
    "xag_per90":         "xAG_Per__std",
    "npxg_per90":        "npxG_Per__std",
    # shooting
    "shots":             "Sh_Standard__shooting",
    "shots_on_target":   "SoT_Standard__shooting",
    "sot_pct":           "SoT_percent_Standard__shooting",
    "shots_per90":       "Sh_per_90_Standard__shooting",
    "goals_per_shot":    "G_per_Sh_Standard__shooting",
    "avg_shot_distance": "Dist_Standard__shooting",
    "npxg_per_shot":     "npxG_per_Sh_Expected__shooting",
    "finishing_delta":   "G_minus_xG_Expected__shooting",
    # passing / creation
    "pass_completion_pct":   "Cmp_percent_Total__passing",
    "prog_passes":           "PrgP__passing",
    "key_passes":            "KP__passing",
    "passes_final_third":    "Final_Third__passing",
    "passes_pen_area":       "PPA__passing",
    "xa":                    "xA__passing",
    "crosses":               "Crs__misc",
    # possession / carrying
    "touches":               "Touches_Touches__possession",
    "touches_att_pen":       "Att Pen_Touches__possession",
    "carries":               "Carries_Carries__possession",
    "prog_carries":          "PrgC_Carries__possession",
    "prog_carry_distance":   "PrgDist_Carries__possession",
    "take_ons_att":          "Att_Take__possession",
    "take_on_success_pct":   "Succ_percent_Take__possession",
    "dispossessed":          "Dis_Carries__possession",
    "miscontrols":           "Mis_Carries__possession",
    "prog_passes_received":  "PrgR_Receiving__possession",
    # defending
    "tackles":               "Tkl_Tackles__defense",
    "tackles_won":           "TklW_Tackles__defense",
    "tackles_def_third":     "Def 3rd_Tackles__defense",
    "tackles_mid_third":     "Mid 3rd_Tackles__defense",
    "tackles_att_third":     "Att 3rd_Tackles__defense",
    "interceptions":         "Int__defense",
    "blocks":                "Blocks_Blocks__defense",
    "clearances":            "Clr__defense",
    "ball_recoveries":       "Recov__misc",
    "errors":                "Err__defense",
    # aerials / discipline
    "aerials_won":           "Won_Aerial__misc",
    "aerials_lost":          "Lost_Aerial__misc",
    "aerial_win_pct":        "Won_percent_Aerial__misc",
    "fouls_committed":       "Fls__misc",
    "fouls_drawn":           "Fld__misc",
    "yellow_cards":          "CrdY__std",
    "red_cards":             "CrdR__std",
}

# Keep only mappings whose source column actually exists; warn on the rest.
present = {k: v for k, v in RENAME.items() if v in df.columns}
missing = {k: v for k, v in RENAME.items() if v not in df.columns}
if missing:
    print("WARNING: these source columns weren't found (skipped):")
    for k, v in missing.items():
        print(f"   {k:22s} <- {v}")

clean = df[list(present.values())].copy()
clean.columns = list(present.keys())

# ---------------------------------------------------------------------------
# Derive per-90s for counting stats FBref didn't pre-compute (per 90 = stat / nineties)
# ---------------------------------------------------------------------------
clean["nineties"] = pd.to_numeric(clean["nineties"], errors="coerce")

PER90_FROM_TOTAL = [
    "key_passes", "prog_passes", "passes_final_third", "passes_pen_area",
    "crosses", "touches", "touches_att_pen", "carries", "prog_carries",
    "take_ons_att", "dispossessed", "miscontrols", "prog_passes_received",
    "tackles", "tackles_won", "tackles_def_third", "tackles_mid_third",
    "tackles_att_third", "interceptions", "blocks", "clearances",
    "ball_recoveries", "aerials_won", "aerials_lost", "fouls_committed",
    "fouls_drawn",
]
for col in PER90_FROM_TOTAL:
    if col in clean.columns:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
        clean[f"{col}_per90"] = (clean[col] / clean["nineties"]).round(3)

clean.to_csv(OUT_FILE, index=False)
print(f"\nWrote {len(clean)} players x {clean.shape[1]} cols -> {OUT_FILE}")
print("Columns:", list(clean.columns))
