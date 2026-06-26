"""
archetype.py — player-style clustering ("what kind of player is X?")
=====================================================================
Built on top of a fitted ScoutEngine. We reuse the engine's feature matrix,
which is already z-scored WITHIN position group, and run KMeans separately per
position group (DF / MF / FW). The number of clusters per group is chosen by
silhouette score, and each cluster is auto-named by scoring its centroid on a
handful of interpretable statistical "axes" (finishing, creation, progression,
tackling, aerial, …) and mapping the dominant axis to a scouting label.

This is intentionally model-light and transparent: every archetype name comes
with the raw signature features that produced it, so it can be sanity-checked.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from .engine import AXES  # interpretable style axes (shared with the clone radar)

# Dominant axis -> human-readable scouting label, per position group.
GROUP_LABELS = {
    "FW": {
        "finishing":    "Poacher / Finisher",
        "creation":     "Creative Forward",
        "progression":  "Progressive Carrier",
        "dribbling":    "Dribbling Winger",
        "aerial":       "Target Forward",
        "tackling":     "Pressing Forward",
        "crossing":     "Wide Forward",
        "distribution": "Link-up Forward",
    },
    "MF": {
        "creation":     "Advanced Playmaker",
        "finishing":    "Goalscoring Midfielder",
        "progression":  "Box-to-Box Carrier",
        "dribbling":    "Dribbling Midfielder",
        "distribution": "Deep-Lying Playmaker",
        "tackling":     "Defensive Midfielder",
        "aerial":       "Aerial Midfielder",
        "crossing":     "Wide Midfielder",
    },
    "DF": {
        "tackling":     "No-Nonsense Stopper",
        "aerial":       "Aerial Defender",
        "distribution": "Ball-Playing Defender",
        "progression":  "Progressive Defender",
        "creation":     "Attacking Full-Back",
        "crossing":     "Overlapping Full-Back",
        "dribbling":    "Inverted Full-Back",
        "finishing":    "Marauding Defender",
    },
}

MIN_GROUP_SIZE = 8          # below this we don't bother clustering a group
K_RANGE = (3, 4, 5, 6)      # candidate cluster counts; best silhouette wins


class ArchetypeModel:
    """Fit once over an existing ScoutEngine; then query per player."""

    def __init__(self, engine, k_range=K_RANGE, random_state=42):
        self.engine = engine
        self.k_range = k_range
        self.random_state = random_state
        self._feat_pos = {f: i for i, f in enumerate(engine.features)}
        self._row_for_idx = engine._row_for_idx
        self._fit()

    # ---- fitting ---------------------------------------------------------
    def _fit(self):
        out = self.engine.out
        Xz = self.engine._Xz
        groups = out["pos_group"].values
        n = len(out)

        self._labels = np.full(n, -1, dtype=int)            # cluster id within group
        self._arch_name = np.array([""] * n, dtype=object)  # human label per player
        self._dist = np.full(n, np.nan)                     # distance to own centroid
        self._group_info = {}                               # group -> fit details

        for g in pd.unique(groups):
            pos = np.where(groups == g)[0]
            if len(pos) < MIN_GROUP_SIZE:
                self._arch_name[pos] = f"{g} (unclustered)"
                continue
            Xg = Xz[pos]
            k = self._best_k(Xg)
            km = KMeans(n_clusters=k, n_init=10,
                        random_state=self.random_state).fit(Xg)
            names = self._name_clusters(g, km.cluster_centers_)
            dist = np.linalg.norm(Xg - km.cluster_centers_[km.labels_], axis=1)

            self._labels[pos] = km.labels_
            self._dist[pos] = dist
            self._arch_name[pos] = [names[c] for c in km.labels_]
            self._group_info[g] = {
                "k": k, "centers": km.cluster_centers_,
                "names": names, "pos": pos, "labels": km.labels_,
            }

    def _best_k(self, X):
        best_k, best_s = None, -1.0
        for k in self.k_range:
            if k >= len(X):
                continue
            km = KMeans(n_clusters=k, n_init=10,
                        random_state=self.random_state).fit(X)
            try:
                s = silhouette_score(X, km.labels_)
            except Exception:
                continue
            if s > best_s:
                best_s, best_k = s, k
        return best_k or min(self.k_range)

    # ---- naming ----------------------------------------------------------
    def _axis_scores(self, center):
        scores = {}
        for axis, fnames in AXES.items():
            idxs = [self._feat_pos[f] for f in fnames if f in self._feat_pos]
            if idxs:
                scores[axis] = float(np.mean([center[i] for i in idxs]))
        return scores

    def _name_clusters(self, group, centers):
        labelmap = GROUP_LABELS.get(group, {})
        raw = []
        for c in centers:
            scores = self._axis_scores(c)
            top_axis = max(scores, key=scores.get)
            raw.append((labelmap.get(top_axis, f"{group} type"), top_axis, scores))

        base_names = [r[0] for r in raw]
        names = []
        for name, axis, scores in raw:
            if base_names.count(name) > 1:   # disambiguate duplicate labels
                ranked = sorted(scores, key=scores.get, reverse=True)
                second = next((a for a in ranked if a != axis), None)
                name = f"{name} ({second})" if second else name
            names.append(name)
        return names

    def signature(self, center, n=4):
        """Top-n features (by centroid z-score) that define a cluster."""
        order = np.argsort(center)[::-1]
        feats = self.engine.features
        return [feats[i] for i in order[:n]]

    # ---- queries ---------------------------------------------------------
    def archetype_of(self, idx):
        row = self._row_for_idx.get(idx)
        if row is None:
            return None
        g = self.engine.out.loc[idx, "pos_group"]
        info = self._group_info.get(g)
        cluster = int(self._labels[row])
        sig = self.signature(info["centers"][cluster]) if (info and cluster >= 0) else []
        # how prototypical: smaller distance-to-centroid = more textbook example
        fit_note = None
        axes = []
        if info is not None and cluster >= 0:
            same = self._dist[info["pos"][info["labels"] == cluster]]
            pct = float((same > self._dist[row]).mean())  # share farther than this player
            fit_note = round(pct, 2)
            # per-axis profile: this player vs the archetype's typical profile,
            # both as z-scores within position group (drives the radar chart).
            p_ax = self._axis_scores(self.engine._Xz[row])
            c_ax = self._axis_scores(info["centers"][cluster])
            axes = [{"axis": a, "player": round(p_ax[a], 2),
                     "archetype": round(c_ax.get(a, 0.0), 2)}
                    for a in AXES if a in p_ax]
        return {
            "pos_group": g,
            "archetype": self._arch_name[row],
            "cluster": cluster,
            "signature": sig,
            "fit": fit_note,   # 1.0 = most textbook example of the archetype
            "axes": axes,      # [{axis, player(z), archetype(z)}] for the radar
        }

    def exemplars(self, idx, n=5):
        """Most prototypical other players sharing this player's archetype."""
        row = self._row_for_idx.get(idx)
        g = self.engine.out.loc[idx, "pos_group"]
        info = self._group_info.get(g)
        if row is None or info is None or self._labels[row] < 0:
            return []
        cluster = self._labels[row]
        out = self.engine.out
        recs = [(out.index[p], self._dist[p])
                for p in info["pos"][info["labels"] == cluster]
                if out.index[p] != idx]
        recs.sort(key=lambda t: t[1])
        res = []
        for df_idx, _ in recs[:n]:
            r = out.loc[df_idx]
            res.append({"player": r["player"], "squad": r["squad"],
                        "league": r["league"], "position": r["position"],
                        "age": None if pd.isna(r["age"]) else float(r["age"])})
        return res

    def summary(self):
        """All archetypes per group with player counts — handy for inspection."""
        out = {}
        for g, info in self._group_info.items():
            counts = pd.Series(info["names"])[info["labels"]].value_counts()
            out[g] = {"k": info["k"], "archetypes": counts.to_dict()}
        return out

    def describe(self, name):
        """Resolve a name and return its archetype profile + exemplars."""
        idx, suggestions = self.engine.resolve(name)
        if idx is None:
            return {"ok": False, "error": "player_not_found",
                    "query": name, "suggestions": suggestions or []}
        r = self.engine.out.loc[idx]
        return {
            "ok": True,
            "mode": "archetype",
            "target": {"player": r["player"], "squad": r["squad"],
                       "league": r["league"], "position": r["position"],
                       "age": None if pd.isna(r["age"]) else float(r["age"])},
            "archetype": self.archetype_of(idx),
            "peers": self.exemplars(idx),
        }
