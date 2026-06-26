"""
value_model.py — market-value prediction + undervalued detection
=================================================================
Predicts a player's market value from their style stats (+ age, position,
league) and flags players the model thinks are worth materially more than their
actual Transfermarkt value ("undervalued").

Two models are trained (see pipeline/04_train_value_model.py):
  * a PyTorch MLP  (the deep-learning component)
  * a LightGBM baseline (honest benchmark on tabular data)
The better one on held-out R² is recorded as `primary` and used by default.

This module holds the *feature assembly* (imported by the trainer so training
and serving build identical inputs) and the runtime predictor. Artifacts live in
models/ and are loaded lazily, so the API still boots before the model is trained.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

try:
    import torch
    import torch.nn as nn
    HAVE_TORCH = True
except ImportError:
    HAVE_TORCH = False

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
POS_CATS = ["DF", "MF", "FW"]


def assemble_features(out, numeric_cols, league_cats, medians):
    """Build the model input frame from an engine `out`-style DataFrame.

    Columns are deterministic: numeric_cols (stats + playing time + age) +
    position one-hots + league one-hots. `medians` (computed on TRAIN) fills
    missing values so train/serve match. Returns (frame, continuous_columns)."""
    X = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(pd.Series(medians)).fillna(0.0)

    frame = X.copy()
    for c in POS_CATS:
        frame[f"pos_{c}"] = (out["pos_group"].values == c).astype(float)
    for c in league_cats:
        frame[f"league_{c}"] = (out["league"].values == c).astype(float)

    return frame, list(numeric_cols)


if HAVE_TORCH:
    class MLP(nn.Module):
        """Configurable feed-forward net. `hidden` is a list of layer widths;
        BatchNorm is optional. Architecture is stored in the checkpoint so the
        predictor can rebuild whatever Optuna selected."""

        def __init__(self, d_in, hidden=(128, 64), p=0.2, batchnorm=False):
            super().__init__()
            layers, prev = [], d_in
            for h in hidden:
                layers.append(nn.Linear(prev, h))
                if batchnorm:
                    layers.append(nn.BatchNorm1d(h))
                layers += [nn.ReLU(), nn.Dropout(p)]
                prev = h
            layers.append(nn.Linear(prev, 1))
            self.net = nn.Sequential(*layers)

        def forward(self, x):
            return self.net(x).squeeze(-1)


class ValuePredictor:
    """Loads trained artifacts and predicts values / finds undervalued players."""

    def __init__(self, models_dir=MODELS_DIR):
        self.dir = Path(models_dir)
        meta_p = self.dir / "value_meta.json"
        if not meta_p.exists():
            raise FileNotFoundError(
                f"No trained value model in {self.dir}. "
                f"Run pipeline/04_train_value_model.py first.")
        self.meta = json.loads(meta_p.read_text())
        self.scaler = joblib.load(self.dir / "value_scaler.pkl")
        self.gbm = joblib.load(self.dir / "value_gbm.pkl")

        m = self.meta
        self.feats = m["feats"]
        self.league_cats = m["league_cats"]
        self.medians = m["medians"]
        self.cont_cols = m["cont_cols"]
        self.col_order = m["col_order"]
        self.y_mean, self.y_std = m["y_mean"], m["y_std"]
        self.primary = m["primary"]

        self.mlp = None
        if HAVE_TORCH and (self.dir / "value_mlp.pt").exists():
            ck = torch.load(self.dir / "value_mlp.pt", map_location="cpu",
                            weights_only=False)  # our own checkpoint (config + state)
            self.mlp = MLP(ck["d_in"], tuple(ck["hidden"]), ck["p"],
                           ck.get("batchnorm", False))
            self.mlp.load_state_dict(ck["state"])
            self.mlp.eval()

    # ---- prediction ------------------------------------------------------
    def _frame(self, out):
        frame, _ = assemble_features(out, self.feats, self.league_cats, self.medians)
        return frame.reindex(columns=self.col_order, fill_value=0.0)

    def _scaled(self, frame):
        f = frame.copy()
        f[self.cont_cols] = self.scaler.transform(f[self.cont_cols])
        return f.values.astype("float32")

    def _mlp_log(self, frame):
        with torch.no_grad():
            z = self.mlp(torch.from_numpy(self._scaled(frame))).numpy()
        return z * self.y_std + self.y_mean

    def _gbm_log(self, frame):
        return self.gbm.predict(frame)               # GBM trained on log target

    def predict_log(self, out, model=None):
        model = model or self.primary
        frame = self._frame(out)
        if model == "ensemble" and self.mlp is not None:
            return (self._mlp_log(frame) + self._gbm_log(frame)) / 2
        if model == "mlp" and self.mlp is not None:
            return self._mlp_log(frame)
        return self._gbm_log(frame)

    def predict_eur(self, out, model=None):
        return np.expm1(self.predict_log(out, model))

    # ---- queries ---------------------------------------------------------
    def value_report(self, engine, name, model=None):
        idx, suggestions = engine.resolve(name)
        if idx is None:
            return {"ok": False, "error": "player_not_found",
                    "query": name, "suggestions": suggestions or []}
        row = engine.out.loc[[idx]]
        pred = float(self.predict_eur(row, model)[0])
        actual = engine._value_of(engine.out.loc[idx])
        verdict, ratio = "unknown", None
        if actual and actual > 0:
            ratio = pred / actual
            verdict = ("undervalued" if ratio >= 1.25
                       else "overvalued" if ratio <= 0.8 else "fair")
        r = engine.out.loc[idx]
        return {
            "ok": True, "mode": "value",
            "target": {"player": r["player"], "squad": r["squad"],
                       "league": r["league"], "position": r["position"],
                       "age": None if pd.isna(r["age"]) else float(r["age"])},
            "predicted_value_eur": round(pred),
            "actual_value_eur": actual,
            "ratio": None if ratio is None else round(ratio, 2),
            "verdict": verdict,
            "model": model or self.primary,
        }

    def undervalued(self, engine, league=None, pos_group=None, max_age=None,
                    top_n=10, min_value_eur=1_000_000, model=None):
        if not engine.has_value:
            return {"ok": False, "error": "no_value_data",
                    "message": "Market values not loaded — run the Transfermarkt join."}
        out = engine.out.copy()
        out["_pred"] = self.predict_eur(out, model)
        out["_actual"] = pd.to_numeric(out["market_value_eur"], errors="coerce")
        out = out[out["_actual"].notna() & (out["_actual"] >= min_value_eur)]
        out["_ratio"] = out["_pred"] / out["_actual"]

        if league:
            out = out[out["league"].str.contains(league, case=False, na=False)]
        if pos_group:
            out = out[out["pos_group"] == pos_group]
        if max_age:
            out = out[pd.to_numeric(out["age"], errors="coerce") <= max_age]

        top = out.nlargest(top_n, "_ratio")
        results = [{
            "player": r["player"], "squad": r["squad"], "league": r["league"],
            "position": r["position"],
            "age": None if pd.isna(r["age"]) else float(r["age"]),
            "actual_value_eur": round(float(r["_actual"])),
            "predicted_value_eur": round(float(r["_pred"])),
            "ratio": round(float(r["_ratio"]), 2),
        } for _, r in top.iterrows()]
        return {"ok": True, "mode": "value",
                "filters": {"league": league, "pos_group": pos_group,
                            "max_age": max_age, "min_value_eur": min_value_eur},
                "count": len(results), "results": results,
                "model": model or self.primary}


# ---- lazy singleton --------------------------------------------------------
_PRED = None


def get_predictor():
    """Return a ValuePredictor, or None if the model hasn't been trained yet."""
    global _PRED
    if _PRED is None:
        try:
            _PRED = ValuePredictor()
        except Exception:
            _PRED = False
    return _PRED or None
