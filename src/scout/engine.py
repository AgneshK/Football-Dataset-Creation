"""
engine.py — core similarity engine + name resolution
=====================================================
Loaded ONCE at API startup. Holds the feature matrix in memory and exposes
search functions. No FastAPI here — pure logic, so the LangGraph agent can
import the same engine.
"""
import re
from pathlib import Path

import pandas as pd
import numpy as np
from unidecode import unidecode
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

SEASON = 2025

# Resolve the processed dataset relative to the project root so the engine
# works no matter what the current working directory is. Prefer the value-joined
# dataset (Transfermarkt) when it exists; fall back to the plain clean file.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROCESSED = PROJECT_ROOT / "data" / "processed"
_VALUED = _PROCESSED / f"scout_valued_{SEASON}.csv"
_CLEAN = _PROCESSED / f"scout_clean_{SEASON}.csv"
DATA_FILE = _VALUED if _VALUED.exists() else _CLEAN

# Identity / non-feature columns. market_value_eur is a LABEL, never a
# similarity feature — keep it here so it can't leak into the feature matrix.
ID_COLS = {"player","squad","league","nation","position","age","born_year",
           "player_type","minutes","matches_played","starts","nineties",
           "market_value_eur"}


def normalize_name(s):
    """Lowercase, strip accents and punctuation — the shared name search key."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"[^a-z ]", "", unidecode(s).lower()).strip()


# Interpretable style axes for outfield players — each a group of clean feature
# columns. Shared by the archetype clustering and the clone radar. Values are
# z-scored WITHIN position group, so an axis means "relative to similar players".
AXES = {
    "finishing":    ["goals_per90", "npxg_per90", "xg_per90", "goals_per_shot",
                     "touches_att_pen_per90", "shots_per90"],
    "creation":     ["assists_per90", "xag_per90", "key_passes_per90",
                     "passes_pen_area_per90", "passes_final_third_per90"],
    "progression":  ["prog_carries_per90", "prog_passes_per90",
                     "prog_passes_received_per90", "carries_per90"],
    "dribbling":    ["take_ons_att_per90", "take_on_success_pct"],
    "distribution": ["pass_completion_pct", "touches_per90", "prog_passes_per90"],
    "tackling":     ["tackles_per90", "interceptions_per90", "blocks_per90",
                     "tackles_def_third_per90", "ball_recoveries_per90"],
    "aerial":       ["aerials_won_per90", "aerial_win_pct", "clearances_per90"],
    "crossing":     ["crosses_per90", "passes_pen_area_per90"],
}

# Counter-scouting: when an attacker DOMINATES an offensive axis, defenders strong
# in the paired defensive metrics are the ones equipped to neutralise it. All
# entries are per-90 / percentage columns, z-scored across the defender pool at
# query time so centre-backs, full-backs and defensive mids compare fairly.
COUNTER_MAP = {
    "finishing":    ["blocks_per90", "clearances_per90",
                     "tackles_def_third_per90", "interceptions_per90"],
    "aerial":       ["aerials_won_per90", "aerial_win_pct", "clearances_per90"],
    "dribbling":    ["tackles_per90", "tackles_won_per90", "interceptions_per90"],
    "progression":  ["interceptions_per90", "ball_recoveries_per90", "tackles_per90"],
    "creation":     ["interceptions_per90", "blocks_per90", "tackles_mid_third_per90"],
    "crossing":     ["aerials_won_per90", "clearances_per90", "blocks_per90"],
    "distribution": ["interceptions_per90", "ball_recoveries_per90"],
}

# Plain-football labels for an attacker's offensive threat axes.
THREAT_LABELS = {
    "finishing":    "clinical finishing & box presence",
    "aerial":       "aerial threat",
    "dribbling":    "1v1 dribbling",
    "progression":  "runs in behind / ball progression",
    "creation":     "chance creation",
    "crossing":     "wide delivery",
    "distribution": "deep build-up",
}

# The DEFENDER-facing capability that blunts each threat axis (used to describe
# a candidate's standout strengths, not the attacker's threat).
COUNTER_STRENGTH_LABELS = {
    "finishing":    "box defending & blocks",
    "aerial":       "aerial dominance",
    "dribbling":    "1v1 tackling",
    "progression":  "covering runs / interceptions",
    "creation":     "cutting passing lanes",
    "crossing":     "aerial & cross defending",
    "distribution": "pressing & ball recovery",
}


def _num(v):
    """Coerce to a rounded float, or None when missing."""
    v = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(v) else round(float(v), 2)


# Sensible default metric set for a head-to-head when the user doesn't specify
# an aspect ("compare X and Y"). Keyed by the first player's position group.
DEFAULT_COMPARE_METRICS = {
    "FW": ["goals_per90", "npxg_per90", "assists_per90", "xag_per90",
           "shots_per90", "take_ons_att_per90"],
    "MF": ["prog_passes_per90", "prog_carries_per90", "key_passes_per90",
           "tackles_per90", "interceptions_per90", "pass_completion_pct"],
    "DF": ["tackles_per90", "interceptions_per90", "clearances_per90",
           "aerials_won_per90", "aerial_win_pct", "prog_passes_per90"],
}


# Common short-name / alias -> how it appears in the data (substring match).
# Extend freely; this is just the high-traffic set.
ALIASES = {
    "rodri": "Rodri",                # may be filtered out if low minutes
    "mbappe": "Mbappé",
    "vini": "Vinícius",
    "vinicius": "Vinícius",
    "lewa": "Lewandowski",
    "cr7": "Cristiano Ronaldo",
    "kdb": "De Bruyne",
    "auba": "Aubameyang",
    "dembele": "Dembélé",
    "odegaard": "Ødegaard",
    "sorloth": "Sørloth",
    "gyokeres": "Gyökeres",
    "haaland": "Haaland",
    "yamal": "Lamine Yamal",
}


class ScoutEngine:
    def __init__(self, data_file=DATA_FILE):
        self.df = pd.read_csv(data_file)
        self._prepare()

    # ---- setup -----------------------------------------------------------
    def _prepare(self):
        df = self.df
        df["player_type"] = df.get("player_type", "outfield")
        # market values are optional (present only after the Transfermarkt join)
        self.has_value = "market_value_eur" in df.columns
        # normalized search key for every player
        df["_norm"] = df["player"].apply(self._norm)

        # feature selection (per-90 + percentages)
        self.features = [c for c in df.columns if self._is_feature(c)]

        out = df[df["player_type"] == "outfield"].copy()
        self.out_idx = out.index

        X = out[self.features].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(X.median())

        # position-group z-scoring
        out["pos_group"] = out["position"].apply(self._pos_group)
        df.loc[out.index, "pos_group"] = out["pos_group"]
        Xz = X.copy()
        for g in out["pos_group"].unique():
            m = out["pos_group"] == g
            Xz.loc[m, :] = StandardScaler().fit_transform(X.loc[m, :])

        self._Xz = Xz.values
        self._row_for_idx = {idx: i for i, idx in enumerate(out.index)}
        self.out = out

    @staticmethod
    def _norm(s):
        return normalize_name(s)

    @staticmethod
    def _pos_group(p):
        if not isinstance(p, str): return "MF"
        p = p.split(",")[0]
        if "DF" in p: return "DF"
        if "FW" in p: return "FW"
        return "MF"

    def _is_feature(self, col):
        if col in ID_COLS or col.startswith("_"): return False
        if col.endswith("_per90") or col.endswith("_pct"): return True
        return col in {
            "goals_per90","assists_per90","xg_per90","xag_per90","npxg_per90",
            "shots_per90","goals_per_shot","npxg_per_shot","avg_shot_distance",
            "finishing_delta"}

    # ---- name resolution -------------------------------------------------
    def resolve(self, name):
        """Return (matched_index, suggestions). One of them is None."""
        q = self._norm(name)
        # alias hop
        if q in ALIASES:
            q = self._norm(ALIASES[q])
        # exact normalized match
        exact = self.out.index[self.out["_norm"] == q].tolist()
        if exact:
            return exact[0], None
        # substring (last-name) match
        partial = self.out[self.out["_norm"].str.contains(q, na=False)]
        if len(partial) == 1:
            return partial.index[0], None
        if len(partial) > 1:
            return None, partial["player"].head(6).tolist()
        # token overlap fallback
        toks = set(q.split())
        if toks:
            mask = self.out["_norm"].apply(
                lambda n: bool(toks & set(n.split())))
            cand = self.out[mask]
            if len(cand):
                return None, cand["player"].head(6).tolist()
        return None, []

    # ---- the search ------------------------------------------------------
    def _value_of(self, row):
        """Market value (eur) for a row, or None when unavailable."""
        if not self.has_value:
            return None
        v = pd.to_numeric(row.get("market_value_eur"), errors="coerce")
        return None if pd.isna(v) else float(v)

    def radar_profile(self, idxs):
        """Per-axis style profile (z-scored within position group) for a list of
        player indices — first is treated as the target. Drives the clone radar."""
        feat_pos = {f: i for i, f in enumerate(self.features)}
        axis_keys = [a for a in AXES if any(f in feat_pos for f in AXES[a])]
        series = []
        for j, idx in enumerate(idxs):
            row = self._row_for_idx.get(idx)
            if row is None:
                continue
            z = self._Xz[row]
            vals = [round(float(np.mean([z[feat_pos[f]] for f in AXES[a]
                                         if f in feat_pos])), 2) for a in axis_keys]
            series.append({"player": str(self.out.loc[idx, "player"]),
                           "target": j == 0, "values": vals})
        return {"kind": "outfield", "axes": axis_keys, "series": series}

    def find_clones(self, name, league=None, same_position=True,
                    top_n=8, max_age=None, min_similarity=None,
                    max_value_eur=None):
        idx, suggestions = self.resolve(name)
        if idx is None:
            return {"ok": False, "error": "player_not_found",
                    "query": name, "suggestions": suggestions or []}

        target = self.out.loc[idx]
        row = self._row_for_idx[idx]
        sims = cosine_similarity(self._Xz[row:row+1], self._Xz)[0]

        pool = self.out.copy()
        pool["similarity"] = sims
        pool = pool.drop(index=idx)

        if league:
            pool = pool[pool["league"].str.contains(league, case=False, na=False)]
        if same_position:
            pool = pool[pool["pos_group"] == target["pos_group"]]
        if max_age:
            pool = pool[pd.to_numeric(pool["age"], errors="coerce") <= max_age]
        if min_similarity:
            pool = pool[pool["similarity"] >= min_similarity]
        # budget filter — only applies when the Transfermarkt join has run
        value_filtered = False
        if max_value_eur and self.has_value:
            pool = pool[pd.to_numeric(pool["market_value_eur"], errors="coerce")
                        <= max_value_eur]
            value_filtered = True

        top = pool.nlargest(top_n, "similarity")
        results = [{
            "player": r["player"], "squad": r["squad"], "league": r["league"],
            "position": r["position"],
            "age": None if pd.isna(r["age"]) else float(r["age"]),
            "market_value_eur": self._value_of(r),
            "similarity": round(float(r["similarity"]), 3),
        } for _, r in top.iterrows()]

        out = {
            "ok": True,
            "target": {
                "player": target["player"], "squad": target["squad"],
                "league": target["league"], "position": target["position"],
                "age": None if pd.isna(target["age"]) else float(target["age"]),
                "market_value_eur": self._value_of(target),
            },
            "filters": {"league": league, "same_position": same_position,
                        "max_age": max_age, "min_similarity": min_similarity,
                        "max_value_eur": max_value_eur},
            "count": len(results),
            "results": results,
            # target + top-3 style profiles for the radar overlay
            "radar": self.radar_profile([idx] + list(top.index[:3])),
        }
        # be explicit when a budget was requested but we can't honour it yet
        if max_value_eur and not self.has_value:
            out["_note"] = ("Market-value data not loaded yet (run the "
                            "Transfermarkt join), so the budget filter was ignored.")
        elif value_filtered:
            out["_note"] = f"Filtered to players valued <= €{max_value_eur:,.0f}."
        return out

    # ---- counter scouting ------------------------------------------------
    def _axis_profile(self, idx):
        """Per-axis z-score profile (within position group) for one player —
        positive on an axis means 'above average for their position'."""
        row = self._row_for_idx[idx]
        z = self._Xz[row]
        feat_pos = {f: i for i, f in enumerate(self.features)}
        prof = {}
        for axis, fnames in AXES.items():
            idxs = [feat_pos[f] for f in fnames if f in feat_pos]
            if idxs:
                prof[axis] = float(np.mean([z[i] for i in idxs]))
        return prof

    @staticmethod
    def _zsum(pool, plus, minus=()):
        """Sum of within-pool z-scores (plus minus a penalty set) — used for the
        sub-role heuristics. Robust to missing columns / zero variance."""
        s = pd.Series(0.0, index=pool.index)
        for cols, sign in ((plus, 1.0), (minus, -1.0)):
            for c in cols:
                if c in pool.columns:
                    x = pd.to_numeric(pool[c], errors="coerce").fillna(0.0)
                    sd = x.std(ddof=0) or 1.0
                    s = s + sign * (x - x.mean()) / sd
        return s

    def _apply_role(self, pool, pos):
        """Filter a candidate pool to a position / sub-role. FBref positions only
        carry DF/MF/FW, so centre-back vs full-back and holding-mid are inferred
        from a transparent statistical heuristic (crossing/progression for FBs,
        ball-winning for DMs)."""
        if not pos:
            return pool
        key = pos.strip().lower().replace("_", "-")
        group = {
            "fw": "FW", "forward": "FW", "forwards": "FW", "striker": "FW",
            "st": "FW", "cf": "FW", "attacker": "FW",
            "winger": "FW", "wing": "FW", "lw": "FW", "rw": "FW",
            "df": "DF", "defender": "DF", "defenders": "DF",
            "cb": "DF", "centre-back": "DF", "center-back": "DF", "centreback": "DF",
            "fb": "DF", "full-back": "DF", "fullback": "DF",
            "wing-back": "DF", "wingback": "DF", "wb": "DF",
            "mf": "MF", "midfielder": "MF", "midfield": "MF",
            "dm": "MF", "dmf": "MF", "cdm": "MF", "holding": "MF",
        }.get(key)
        if group:
            pool = pool[pool["pos_group"] == group]
        if len(pool) < 3:
            return pool
        # full-back-ness: crosses + carrying forward, minus aerial/clearance volume
        if key in {"fb", "full-back", "fullback", "wing-back", "wingback", "wb"}:
            pool = pool[self._zsum(
                pool, ["crosses_per90", "prog_carries_per90", "take_ons_att_per90"],
                ["clearances_per90", "aerials_won_per90"]) > 0]
        elif key in {"cb", "centre-back", "center-back", "centreback"}:
            pool = pool[self._zsum(
                pool, ["crosses_per90", "prog_carries_per90", "take_ons_att_per90"],
                ["clearances_per90", "aerials_won_per90"]) <= 0]
        elif key in {"dm", "dmf", "cdm", "holding"}:
            pool = pool[self._zsum(
                pool, ["tackles_per90", "interceptions_per90", "ball_recoveries_per90"],
                ["key_passes_per90", "xag_per90"]) > 0]
        return pool

    def find_counters(self, name, league=None, max_age=None, top_n=8, pos=None):
        """Find defenders / defensive mids best equipped to neutralise an
        attacker. We profile what makes the attacker dangerous (which offensive
        axes they dominate), weight the defensive metrics that counter those
        threats, and rank the DF+MF pool by a 'counter fit' score."""
        idx, suggestions = self.resolve(name)
        if idx is None:
            return {"ok": False, "mode": "counter", "error": "player_not_found",
                    "query": name, "suggestions": suggestions or []}

        target = self.out.loc[idx]
        prof = self._axis_profile(idx)
        # offensive threats = axes the attacker is above-average on
        threats = {a: max(0.0, prof.get(a, 0.0)) for a in COUNTER_MAP}
        tot = sum(threats.values())
        if tot <= 0:  # not a notable attacker on any axis — default to all-round
            threats = {"finishing": 1.0, "dribbling": 1.0, "progression": 1.0}
            tot = sum(threats.values())
        weights = {a: v / tot for a, v in threats.items() if v > 0}

        # candidate pool: defenders + midfielders (the counter score sorts out
        # whether a CB, full-back or holding mid is the best fit) — never forwards
        pool = self.out[self.out["pos_group"].isin(["DF", "MF"])].copy()
        pool = pool.drop(index=idx, errors="ignore")
        if league:
            pool = pool[pool["league"].str.contains(league, case=False, na=False)]
        if max_age:
            pool = pool[pd.to_numeric(pool["age"], errors="coerce") <= max_age]
        if pos:
            pool = self._apply_role(pool, pos)
        if len(pool) < 3:
            return {"ok": False, "mode": "counter", "error": "empty_pool",
                    "message": "Not enough defenders match those filters."}

        # z-score the relevant defensive metrics ACROSS the pool (cross-position
        # comparable), then strength on an axis = mean z of its counter metrics
        metrics = sorted({m for a in weights for m in COUNTER_MAP[a]
                          if m in pool.columns})
        M = pool[metrics].apply(pd.to_numeric, errors="coerce")
        M = M.fillna(M.median())
        Mz = (M - M.mean()) / M.std(ddof=0).replace(0, 1.0)

        axis_strength = {}
        for a in weights:
            cols = [m for m in COUNTER_MAP[a] if m in Mz.columns]
            axis_strength[a] = Mz[cols].mean(axis=1)

        score = sum(weights[a] * axis_strength[a] for a in weights)
        pool["counter_score"] = score
        lo, hi = float(score.min()), float(score.max())
        rng = (hi - lo) or 1.0

        top = pool.nlargest(top_n, "counter_score")
        results = []
        for di, r in top.iterrows():
            # this defender's standout counter strengths (best weighted axes)
            contrib = {a: float(axis_strength[a].loc[di]) for a in weights}
            strong = sorted(contrib, key=contrib.get, reverse=True)[:2]
            results.append({
                "player": r["player"], "squad": r["squad"], "league": r["league"],
                "position": r["position"],
                "age": None if pd.isna(r["age"]) else float(r["age"]),
                "market_value_eur": self._value_of(r),
                "counter_score": round(float(r["counter_score"]), 3),
                # normalised 0..1 counter fit so the existing bar chart renders
                "similarity": round((float(r["counter_score"]) - lo) / rng, 3),
                "strengths": [COUNTER_STRENGTH_LABELS.get(a, a) for a in strong],
                "tackles_per90": _num(r.get("tackles_per90")),
                "interceptions_per90": _num(r.get("interceptions_per90")),
                "aerials_won_per90": _num(r.get("aerials_won_per90")),
                "aerial_win_pct": _num(r.get("aerial_win_pct")),
                "blocks_per90": _num(r.get("blocks_per90")),
                "clearances_per90": _num(r.get("clearances_per90")),
            })

        threat_profile = [
            {"axis": a, "label": THREAT_LABELS.get(a, a), "weight": round(weights[a], 2)}
            for a in sorted(weights, key=weights.get, reverse=True)
        ]
        return {
            "ok": True, "mode": "counter",
            "target": {
                "player": target["player"], "squad": target["squad"],
                "league": target["league"], "position": target["position"],
                "age": None if pd.isna(target["age"]) else float(target["age"]),
                "market_value_eur": self._value_of(target),
            },
            "threat": threat_profile,
            "filters": {"league": league, "max_age": max_age, "pos": pos},
            "count": len(results),
            "results": results,
        }

    # ---- open-ended trait search -----------------------------------------
    def _metric_series(self, pool, metric, mode):
        """Resolve a catalogue metric to a (display_key, values) pair for the
        requested mode. In 'total' mode a per-90 metric is swapped for its raw
        season-total column when one exists (preferred — it's the real count),
        else reconstructed as per90 x 90s-played. Ratio/% metrics have no total,
        so they pass through unchanged."""
        if mode == "total" and metric.endswith("_per90"):
            base = metric[:-len("_per90")]
            if base in pool.columns:
                return base, pd.to_numeric(pool[base], errors="coerce")
            if "nineties" in pool.columns:
                return base, (pd.to_numeric(pool[metric], errors="coerce")
                              * pd.to_numeric(pool["nineties"], errors="coerce"))
        return metric, pd.to_numeric(pool.get(metric), errors="coerce")

    def search_by_traits(self, metrics, pos=None, league=None, max_age=None,
                         top_n=10, weights=None, mode="per90"):
        """Rank players by an arbitrary set of statistical traits — the engine
        behind open-ended scout queries ('a ball-carrying midfielder with
        progressive passing') and leaderboards ('most assists this season').
        `metrics` are catalogue keys; `mode` is 'per90' (rates/style, default) or
        'total' (absolute season volume). We z-score the chosen metrics ACROSS
        the filtered pool and rank by their (optionally weighted) mean."""
        valid = [m for m in (metrics or []) if m in self.features]
        if not valid:
            return {"ok": False, "mode": "discover", "error": "no_metrics",
                    "message": "I couldn't map that request to any tracked stats."}

        pool = self.out.copy()
        if league:
            pool = pool[pool["league"].str.contains(league, case=False, na=False)]
        if max_age:
            pool = pool[pd.to_numeric(pool["age"], errors="coerce") <= max_age]
        if pos:
            pool = self._apply_role(pool, pos)
        if len(pool) < 3:
            return {"ok": False, "mode": "discover", "error": "empty_pool",
                    "message": "Not enough players match those filters."}

        # resolve each metric to a display key + values for the requested mode
        cols, disp = {}, []
        wmap = {}
        for m in valid:
            key, series = self._metric_series(pool, m, mode)
            cols[key] = series
            disp.append(key)
            wmap[key] = float((weights or {}).get(m, 1.0))

        raw = pd.DataFrame(cols, index=pool.index)            # real values (NaNs)
        Mf = raw.fillna(raw.median())                         # filled for scoring
        Mz = (Mf - Mf.mean()) / Mf.std(ddof=0).replace(0, 1.0)
        w = np.array([wmap[k] for k in disp])
        w = w / (w.sum() or 1.0)
        score = (Mz.values * w).sum(axis=1)

        pool = pool.assign(trait_score=score)
        lo, hi = float(score.min()), float(score.max())
        rng = (hi - lo) or 1.0
        top = pool.nlargest(top_n, "trait_score")
        results = [{
            "player": r["player"], "squad": r["squad"], "league": r["league"],
            "position": r["position"],
            "age": None if pd.isna(r["age"]) else float(r["age"]),
            "market_value_eur": self._value_of(r),
            "trait_score": round(float(r["trait_score"]), 3),
            # normalised 0..1 so the existing bar chart renders
            "similarity": round((float(r["trait_score"]) - lo) / rng, 3),
            "stats": {k: _num(raw.loc[di, k]) for k in disp},
        } for di, r in top.iterrows()]

        return {
            "ok": True, "mode": "discover", "value_mode": mode,
            "metrics": disp,
            "filters": {"pos": pos, "league": league, "max_age": max_age},
            "count": len(results),
            "results": results,
        }

    # ---- head-to-head comparison -----------------------------------------
    def compare(self, names, metrics=None):
        """Compare two or more named players head-to-head on a set of metrics.
        If `metrics` is empty we default to a sensible set for the first player's
        position group. Returns each player's values, the per-metric leader, and
        a style radar overlaying all of them."""
        names = [n for n in (names or []) if n]
        if len(names) < 2:
            return {"ok": False, "mode": "compare", "error": "need_two",
                    "message": "Name at least two players to compare."}

        resolved = []
        for nm in names:
            idx, sugg = self.resolve(nm)
            if idx is None:
                return {"ok": False, "mode": "compare", "error": "player_not_found",
                        "query": nm, "suggestions": sugg or []}
            resolved.append(idx)

        valid = [m for m in (metrics or []) if m in self.features]
        if not valid:
            g = self.out.loc[resolved[0], "pos_group"]
            valid = [m for m in DEFAULT_COMPARE_METRICS.get(g,
                     DEFAULT_COMPARE_METRICS["MF"]) if m in self.features]

        players = []
        for idx in resolved:
            r = self.out.loc[idx]
            players.append({
                "player": r["player"], "squad": r["squad"], "league": r["league"],
                "position": r["position"],
                "age": None if pd.isna(r["age"]) else float(r["age"]),
                "market_value_eur": self._value_of(r),
                "stats": {m: _num(r.get(m)) for m in valid},
            })

        # per-metric leader (higher is better for every metric in the catalogue)
        leaders = {}
        for m in valid:
            vals = [(p["player"], p["stats"][m]) for p in players
                    if p["stats"][m] is not None]
            if vals:
                leaders[m] = max(vals, key=lambda t: t[1])[0]

        return {
            "ok": True, "mode": "compare",
            "metrics": valid,
            "players": players,
            "leaders": leaders,
            "radar": self.radar_profile(resolved),
        }

    # ---- squad builder ---------------------------------------------------
    @staticmethod
    def _parse_formation(formation):
        """'4-3-3' -> {GK:1, DF:4, MF:3, FW:3}. Middle bands collapse into MF,
        so '4-2-3-1' -> DF 4, MF 5, FW 1."""
        nums = [int(x) for x in re.findall(r"\d+", formation or "")]
        if len(nums) < 2:
            return None
        return {"GK": 1, "DF": nums[0], "MF": sum(nums[1:-1]), "FW": nums[-1]}

    def _role_candidates(self, role, base, metrics):
        """Candidate players for an outfield role, ranked by style fit (mean of
        z-scored metrics across the role pool)."""
        pool = base[base["pos_group"] == role]
        if not len(pool):
            return []
        mets = metrics or [m for m in DEFAULT_COMPARE_METRICS.get(role, [])
                           if m in self.features]
        mets = [m for m in mets if m in pool.columns] or ["touches_per90"]
        M = pool[mets].apply(pd.to_numeric, errors="coerce")
        M = M.fillna(M.median())
        fit = ((M - M.mean()) / M.std(ddof=0).replace(0, 1.0)).mean(axis=1)
        cand = [{
            "player": r["player"], "squad": r["squad"], "league": r["league"],
            "position": r["position"],
            "age": None if pd.isna(r["age"]) else float(r["age"]),
            "value": self._value_of(r), "fit": float(fit.loc[idx]),
        } for idx, r in pool.iterrows()]
        cand.sort(key=lambda c: c["fit"], reverse=True)
        return cand[:80]

    def _gk_candidates(self, base_mask_league, base_mask_age, league, max_age):
        """Goalkeeper candidates (the outfield engine excludes GKs) — ranked by
        market value as a quality proxy since GK shot-stopping stats aren't in
        the outfield feature set."""
        if "player_type" not in self.df.columns:
            return []
        gk = self.df[self.df["player_type"] == "GK"].copy()
        if league:
            gk = gk[gk["league"].str.contains(league, case=False, na=False)]
        if max_age:
            gk = gk[pd.to_numeric(gk["age"], errors="coerce") <= max_age]
        cand = [{
            "player": r["player"], "squad": r["squad"], "league": r["league"],
            "position": "GK",
            "age": None if pd.isna(r["age"]) else float(r["age"]),
            "value": self._value_of(r), "fit": 0.0,
        } for _, r in gk.iterrows()]
        cand.sort(key=lambda c: (c["value"] or 0), reverse=True)
        return cand[:40]

    def build_squad(self, formation=None, roles=None, budget_eur=None,
                    metrics=None, league=None, max_age=None):
        """Assemble a lineup for a formation / set of roles, maximising style fit
        within a total budget. Greedy: start from the best-fit player per slot,
        then repeatedly downgrade the slot that loses the least fit-per-euro until
        the squad is within budget. Players are unique across slots."""
        if roles:
            role_counts = {str(k).upper(): int(v) for k, v in roles.items()
                           if int(v) > 0}
        elif formation:
            role_counts = self._parse_formation(formation)
        else:
            role_counts = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
        if not role_counts:
            return {"ok": False, "mode": "squad", "error": "bad_formation",
                    "message": "Give me a formation (e.g. 4-3-3) or roles "
                               "(e.g. 'a front three')."}

        note = None
        if budget_eur and not self.has_value:
            budget_eur, note = None, ("Market-value data isn't loaded, so the "
                                      "budget was ignored.")

        valid_metrics = [m for m in (metrics or []) if m in self.features]

        base = self.out
        if league:
            base = base[base["league"].str.contains(league, case=False, na=False)]
        if max_age:
            base = base[pd.to_numeric(base["age"], errors="coerce") <= max_age]

        pools = {}
        for role in role_counts:
            if role == "GK":
                pools["GK"] = self._gk_candidates(None, None, league, max_age)
            else:
                pools[role] = self._role_candidates(role, base, valid_metrics)

        # expand to individual slots and greedily fill with the best available
        slots = [role for role, n in role_counts.items() for _ in range(n)]
        used, selection = set(), []
        for role in slots:
            pick = next((c for c in pools.get(role, [])
                         if c["player"] not in used), None)
            if pick is None:
                selection.append({"role": role, "empty": True})
            else:
                used.add(pick["player"])
                selection.append({"role": role, **pick})

        def total():
            return sum((s.get("value") or 0) for s in selection
                       if not s.get("empty"))

        # downgrade loop: smallest fit-loss-per-euro-saved first
        if budget_eur:
            guard = 0
            while total() > budget_eur and guard < 1000:
                guard += 1
                best = None  # (efficiency, slot_index, alternative)
                for i, s in enumerate(selection):
                    if s.get("empty"):
                        continue
                    cur_val = s.get("value") or 0
                    for c in pools.get(s["role"], []):
                        if c["player"] in used:
                            continue
                        alt_val = c["value"] or 0
                        if alt_val >= cur_val:
                            continue
                        saved = cur_val - alt_val
                        eff = (s["fit"] - c["fit"]) / saved if saved else 1e9
                        if best is None or eff < best[0]:
                            best = (eff, i, c)
                if best is None:
                    break
                _, i, alt = best
                used.discard(selection[i]["player"])
                used.add(alt["player"])
                selection[i] = {"role": selection[i]["role"], **alt}
            if total() > budget_eur:
                note = ((note + " ") if note else "") + (
                    "Couldn't fully meet the budget with distinct players; "
                    "this is the closest fit.")

        lineup = []
        for s in selection:
            if s.get("empty"):
                lineup.append({"role": s["role"], "player": None})
            else:
                lineup.append({
                    "role": s["role"], "player": s["player"], "squad": s["squad"],
                    "league": s["league"], "position": s["position"],
                    "age": s["age"], "market_value_eur": s.get("value"),
                    "fit": round(s["fit"], 3),
                })

        spent = total()
        return {
            "ok": True, "mode": "squad",
            "formation": formation, "roles": role_counts,
            "budget_eur": budget_eur,
            "total_value_eur": spent if self.has_value else None,
            "within_budget": (budget_eur is None) or (spent <= budget_eur),
            "style_metrics": valid_metrics,
            "count": len([l for l in lineup if l["player"]]),
            "lineup": lineup, "note": note,
        }
