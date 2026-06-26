"""
AI Football Scout — Stage 1: Join & Clean
==========================================
Takes the 10 CSVs pulled from worldfootballR (load_fb_big5_advanced_season_stats)
and builds ONE model-ready player-per-row table.

Design goals:
  * Parameterised on SEASON so swapping 2025 -> 2026 later is a one-line change.
  * Defensive: inspects every file, reports what it finds, and is loud about
    missing columns / dropped players instead of silently producing nulls.
  * Handles the known data-integrity issue: attacking tables (~2854 rows, fresh)
    vs defensive tables (~2180 rows, older cache). We INNER-join the core
    outfield tables so only players with COMPLETE data survive.

Run (from project root):  python pipeline/01_build.py
Reads:   data/raw/big5_players_*_<SEASON>.csv
Writes:  data/processed/scout_dataset_<SEASON>.csv
"""

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG  — change SEASON here to rebuild for a different year later
# ---------------------------------------------------------------------------
SEASON = 2025                      # 2024/25.  Set to 2026 when that data exists.
MIN_MINUTES = 500                  # filter low-sample players (noisy per-90s)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"                 # folder containing big5_players_*.csv
OUT_FILE = ROOT / "data" / "processed" / f"scout_dataset_{SEASON}.csv"

# Which tables are core outfield (INNER join — must have all) vs optional.
CORE_OUTFIELD = ["standard", "shooting", "passing", "passing_types",
                 "possession", "defense", "misc"]
OPTIONAL      = ["playing_time", "gca"]          # left-join if present
KEEPER_TABLES = ["keepers", "keepers_adv"]        # handled separately

# Columns that identify a player across every table (the join keys).
# worldfootballR uses these exact names in its wide output.
KEY_CANDIDATES = ["Player", "Squad", "Comp", "Nation", "Born", "Pos", "Age"]
JOIN_KEYS = ["Player", "Squad"]   # Player+Squad uniquely IDs a player-season

# ---------------------------------------------------------------------------
# 1. LOAD + INSPECT
# ---------------------------------------------------------------------------
def load_table(stat_type):
    """Load one CSV if it exists; return None otherwise."""
    path = DATA_DIR / f"big5_players_{stat_type}_{SEASON}.csv"
    if not path.exists():
        print(f"  [missing file] {path}")
        return None
    df = pd.read_csv(path)
    print(f"  {stat_type:15s} {df.shape[0]:5d} rows  {df.shape[1]:3d} cols")
    return df

def dedupe_columns(df, suffix):
    """Keep join keys clean; suffix every other column so tables don't collide
    on shared names (e.g. several tables carry 'Gls', 'Min', '90s')."""
    new_cols = []
    for c in df.columns:
        if c in JOIN_KEYS:
            new_cols.append(c)
        else:
            new_cols.append(f"{c}__{suffix}")
    df = df.copy()
    df.columns = new_cols
    return df

# ---------------------------------------------------------------------------
# 2. JOIN OUTFIELD
# ---------------------------------------------------------------------------
def build_outfield(tables):
    # Start from 'standard' — it has the broadest player list + identity cols.
    base = tables["standard"].copy()

    # Keep identity columns from standard as-is; we'll suffix the rest.
    base = dedupe_columns(base, "std")

    merged = base
    report = {"standard": len(base)}

    for st in CORE_OUTFIELD:
        if st == "standard":
            continue
        df = tables.get(st)
        if df is None:
            print(f"  WARNING: core table '{st}' missing — skipping (will lose its columns)")
            continue
        df = dedupe_columns(df, st)
        before = len(merged)
        merged = merged.merge(df, on=JOIN_KEYS, how="inner")  # INNER = complete data only
        report[st] = len(merged)
        print(f"  inner-join {st:13s}: {before} -> {len(merged)} players")

    # Optional tables: left-join so we never lose players if they're absent.
    for st in OPTIONAL:
        df = tables.get(st)
        if df is None:
            print(f"  optional table '{st}' not available — skipping")
            continue
        df = dedupe_columns(df, st)
        merged = merged.merge(df, on=JOIN_KEYS, how="left")
        print(f"  left-join  {st:13s}: now {merged.shape[1]} cols")

    return merged, report

# ---------------------------------------------------------------------------
# 3. CLEAN: minutes filter, GK flag, numeric coercion
# ---------------------------------------------------------------------------
def find_col(df, want):
    """Find the first column whose name starts with `want` (post-suffix)."""
    hits = [c for c in df.columns if c == want or c.startswith(want + "__")]
    return hits[0] if hits else None

def clean(df):
    # Minutes lives in standard as 'Min' -> 'Min__std'
    min_col = find_col(df, "Min")
    if min_col:
        df[min_col] = pd.to_numeric(df[min_col], errors="coerce")
        before = len(df)
        df = df[df[min_col] >= MIN_MINUTES].copy()
        print(f"  minutes filter (>= {MIN_MINUTES}): {before} -> {len(df)} players")
    else:
        print("  WARNING: no minutes column found — skipping minutes filter")

    # player_type flag from Pos (drives GK vs outfield routing later)
    pos_col = find_col(df, "Pos")
    if pos_col:
        df["player_type"] = df[pos_col].apply(
            lambda p: "GK" if isinstance(p, str) and "GK" in p else "outfield")
        print("  player_type counts:")
        print(df["player_type"].value_counts().to_string())
    return df

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"=== Building scout dataset for season_end_year={SEASON} ===\n")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("Loading tables:")
    all_types = CORE_OUTFIELD + OPTIONAL + KEEPER_TABLES
    tables = {st: load_table(st) for st in all_types}

    if tables.get("standard") is None:
        raise SystemExit("FATAL: standard table missing — cannot build base.")

    print("\nJoining outfield tables (INNER join on core = complete data only):")
    outfield, report = build_outfield(tables)

    print("\nCleaning:")
    outfield = clean(outfield)

    outfield.to_csv(OUT_FILE, index=False)
    print(f"\nWrote {len(outfield)} players x {outfield.shape[1]} cols -> {OUT_FILE}")

    # ---- quick sanity check: top scorers ----
    gls = find_col(outfield, "Gls")
    if gls:
        outfield[gls] = pd.to_numeric(outfield[gls], errors="coerce")
        cols = [c for c in ["Player", "Squad", "Comp", gls] if c in outfield.columns]
        print("\nTop 10 scorers (sanity check):")
        print(outfield.nlargest(10, gls)[cols].to_string(index=False))

    # ---- keeper table summary (kept separate) ----
    if tables.get("keepers") is not None:
        print(f"\nKeeper table: {len(tables['keepers'])} GKs available "
              f"(joined/cleaned separately for GK similarity).")
