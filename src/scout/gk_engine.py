"""
gk_engine.py — goalkeeper similarity engine
============================================
Goalkeepers are compared only against other goalkeepers, on GK-specific stats
(shot-stopping, workload, distribution, cross-claiming, sweeping). Same approach
as the outfield engine — z-score features, cosine similarity — but there's no
position grouping (all keepers are one group).

Loaded lazily (get_gk_engine) so the API/agent boot even before the GK dataset
is built via pipeline/05_build_gk.py.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

from .engine import normalize_name

SEASON = 2025
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GK_FILE = PROJECT_ROOT / "data" / "processed" / f"scout_gk_{SEASON}.csv"

GK_FEATURES = [
    "save_pct", "psxg_per_sot", "psxg_plus_minus_per90", "cs_pct",
    "ga_per90", "sota_per90", "saves_per90",
    "launched_cmp_pct", "launch_pct_passes", "avg_pass_len",
    "throws_per90", "gk_passes_per90", "goalkick_launch_pct", "goalkick_avg_len",
    "cross_stop_pct", "crosses_faced_per90", "sweeper_per90", "sweeper_avg_dist",
]

# GK-specific radar axes (z-scored across goalkeepers).
GK_AXES = {
    "shot-stopping":   ["save_pct", "psxg_plus_minus_per90", "cs_pct"],
    "shots faced":     ["sota_per90", "saves_per90"],
    "distribution":    ["launched_cmp_pct", "gk_passes_per90"],
    "long passing":    ["launch_pct_passes", "avg_pass_len", "goalkick_launch_pct"],
    "sweeping":        ["sweeper_per90", "sweeper_avg_dist"],
    "cross-claiming":  ["cross_stop_pct", "crosses_faced_per90"],
}


class GKEngine:
    def __init__(self, data_file=GK_FILE):
        self.gk = pd.read_csv(data_file)
        self._prepare()

    def _prepare(self):
        df = self.gk
        df["_norm"] = df["player"].apply(normalize_name)
        self.features = [c for c in GK_FEATURES if c in df.columns]

        X = df[self.features].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(X.median())
        self._Xz = StandardScaler().fit_transform(X)
        self._row_for_idx = {idx: i for i, idx in enumerate(df.index)}

    # ---- name resolution (mirror of ScoutEngine.resolve) -----------------
    def resolve(self, name):
        q = normalize_name(name)
        exact = self.gk.index[self.gk["_norm"] == q].tolist()
        if exact:
            return exact[0], None
        partial = self.gk[self.gk["_norm"].str.contains(q, na=False)]
        if len(partial) == 1:
            return partial.index[0], None
        if len(partial) > 1:
            return None, partial["player"].head(6).tolist()
        toks = set(q.split())
        if toks:
            cand = self.gk[self.gk["_norm"].apply(lambda n: bool(toks & set(n.split())))]
            if len(cand):
                return None, cand["player"].head(6).tolist()
        return None, []

    def radar_profile(self, idxs):
        """Per-axis GK style profile (z-scored across keepers); first = target."""
        feat_pos = {f: i for i, f in enumerate(self.features)}
        axis_keys = [a for a in GK_AXES if any(f in feat_pos for f in GK_AXES[a])]
        series = []
        for j, idx in enumerate(idxs):
            row = self._row_for_idx.get(idx)
            if row is None:
                continue
            z = self._Xz[row]
            vals = [round(float(np.mean([z[feat_pos[f]] for f in GK_AXES[a]
                                         if f in feat_pos])), 2) for a in axis_keys]
            series.append({"player": str(self.gk.loc[idx, "player"]),
                           "target": j == 0, "values": vals})
        return {"kind": "gk", "axes": axis_keys, "series": series}

    # ---- similarity ------------------------------------------------------
    def find_clones(self, name, league=None, top_n=8, max_age=None,
                    min_similarity=None):
        idx, suggestions = self.resolve(name)
        if idx is None:
            return {"ok": False, "error": "player_not_found",
                    "query": name, "suggestions": suggestions or []}

        target = self.gk.loc[idx]
        row = self._row_for_idx[idx]
        sims = cosine_similarity(self._Xz[row:row + 1], self._Xz)[0]

        pool = self.gk.copy()
        pool["similarity"] = sims
        pool = pool.drop(index=idx)
        if league:
            pool = pool[pool["league"].str.contains(league, case=False, na=False)]
        if max_age:
            pool = pool[pd.to_numeric(pool["age"], errors="coerce") <= max_age]
        if min_similarity:
            pool = pool[pool["similarity"] >= min_similarity]

        top = pool.nlargest(top_n, "similarity")
        results = [{
            "player": r["player"], "squad": r["squad"], "league": r["league"],
            "position": "GK",
            "age": None if pd.isna(r["age"]) else float(r["age"]),
            "similarity": round(float(r["similarity"]), 3),
        } for _, r in top.iterrows()]

        return {
            "ok": True, "player_type": "GK",
            "target": {"player": target["player"], "squad": target["squad"],
                       "league": target["league"], "position": "GK",
                       "age": None if pd.isna(target["age"]) else float(target["age"])},
            "filters": {"league": league, "max_age": max_age,
                        "min_similarity": min_similarity},
            "count": len(results), "results": results,
            "radar": self.radar_profile([idx] + list(top.index[:3])),
        }


# ---- lazy singleton --------------------------------------------------------
_GK = None


def get_gk_engine():
    """Return a GKEngine, or None if the GK dataset hasn't been built yet."""
    global _GK
    if _GK is None:
        try:
            _GK = GKEngine()
        except Exception:
            _GK = False
    return _GK or None
