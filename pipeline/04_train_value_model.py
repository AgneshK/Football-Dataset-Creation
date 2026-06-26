"""
AI Football Scout — Stage 4: train the market-value model (Optuna-tuned + ensemble)
====================================================================================
Trains a PyTorch MLP whose architecture + optimiser are tuned by Optuna (TPE
search with pruning), a LightGBM baseline, and an MLP+GBM ensemble. Selection is
by 5-fold cross-validated R²(log) — value is right-skewed, so this is the
principled metric, and "undervalued" is a multiplicative (log-space) judgement.

Feature set is value-specific and richer than the similarity features: per-90
rates + percentages PLUS raw output totals and PLAYING TIME (minutes, matches,
starts) and age — so the model can distinguish an every-week starter from a
low-minutes squad player with identical per-90s. Per fold, medians + scaler are
refit on the training portion only (no leakage).

Note: even a well-tuned model regresses extreme outliers (Haaland, Bellingham)
toward the conditional mean — their price reflects reputation/age/marketability
that on-pitch stats can't see. That gap is expected, not a defect.

Requires the value-joined dataset (run pipeline/03_market_values.py first).
Run (from project root):  python pipeline/04_train_value_model.py [--trials N]
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import joblib
import torch
import torch.nn as nn
import lightgbm as lgb
import optuna
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score

from scout.engine import ScoutEngine
from scout.value_model import assemble_features, MLP, MODELS_DIR

SEED = 42
N_TRIALS = 50
OPTUNA_TIMEOUT = 600
OBJ_FOLDS = 3
FINAL_FOLDS = 5
MAX_EPOCHS = 500
PATIENCE = 30

# Extra value-relevant columns on top of the similarity features (per-90/pct).
# Raw volume + availability matter a lot for market value.
EXTRA = ["age", "minutes", "nineties", "matches_played", "starts",
         "goals", "assists", "np_goals", "xg", "npxg", "xag",
         "shots", "shots_on_target", "prog_passes", "key_passes",
         "prog_carries", "tackles", "interceptions"]

GBM_GRID = [
    dict(num_leaves=15, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8),
    dict(num_leaves=31, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8),
    dict(num_leaves=31, learning_rate=0.02, subsample=0.9, colsample_bytree=0.9),
    dict(num_leaves=63, learning_rate=0.02, subsample=0.7, colsample_bytree=0.7),
]
GBM_COMMON = dict(n_estimators=2000, random_state=SEED, n_jobs=-1, verbose=-1,
                  min_child_samples=20)


def scale(df, cont, scaler):
    d = df.copy()
    d[cont] = scaler.transform(d[cont])
    return d.values.astype("float32")


def train_mlp(Xtr_s, ytr_z, d_in, cfg, Xva_s=None, yva_z=None,
              max_epochs=MAX_EPOCHS, patience=PATIENCE, seed=SEED):
    torch.manual_seed(seed)
    model = MLP(d_in, cfg["hidden"], cfg["dropout"], cfg["batchnorm"])
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
    lossf = nn.MSELoss()
    n, batch = Xtr_s.shape[0], cfg["batch"]
    best_val, best_state, best_epoch, bad = float("inf"), None, max_epochs, 0
    for epoch in range(1, max_epochs + 1):
        model.train()
        for idx in torch.randperm(n).split(batch):
            if idx.numel() < 2:
                continue
            opt.zero_grad()
            lossf(model(Xtr_s[idx]), ytr_z[idx]).backward()
            opt.step()
        if Xva_s is not None:
            model.eval()
            with torch.no_grad():
                v = lossf(model(Xva_s), yva_z).item()
            if v < best_val - 1e-6:
                best_val, best_epoch, bad = v, epoch, 0
                best_state = {k: t.detach().clone()
                              for k, t in model.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_epoch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=N_TRIALS)
    args = ap.parse_args()

    eng = ScoutEngine()
    if not eng.has_value:
        raise SystemExit("No market_value_eur column. Run pipeline/03_market_values.py first.")

    out = eng.out.copy()
    out["_value"] = pd.to_numeric(out["market_value_eur"], errors="coerce")
    data = out[out["_value"].notna() & (out["_value"] > 0)].copy().reset_index(drop=True)

    num_cols = list(dict.fromkeys(
        [*eng.features, *[c for c in EXTRA if c in data.columns]]
    ))
    league_cats = sorted(data["league"].dropna().unique().tolist())
    y = np.log1p(data["_value"].values)
    print(f"Training rows: {len(data)}  |  numeric features: {len(num_cols)} "
          f"(was {len(eng.features)})\n")

    def build_fold(tr_idx, va_idx):
        tr, va = data.iloc[tr_idx], data.iloc[va_idx]
        med = {c: float(pd.to_numeric(tr[c], errors="coerce").median()) for c in num_cols}
        Xtr, cont = assemble_features(tr, num_cols, league_cats, med)
        Xva, _ = assemble_features(va, num_cols, league_cats, med)
        Xva = Xva.reindex(columns=Xtr.columns, fill_value=0.0)
        scaler = StandardScaler().fit(Xtr[cont])
        return Xtr, Xva, cont, scaler

    def cv_mlp(cfg, folds, trial=None):
        kf = KFold(folds, shuffle=True, random_state=SEED)
        scores = []
        for i, (tr_idx, va_idx) in enumerate(kf.split(data)):
            Xtr, Xva, cont, scaler = build_fold(tr_idx, va_idx)
            ytr, yva = y[tr_idx], y[va_idx]
            ym, ys = ytr.mean(), ytr.std()
            Xtr_s = torch.from_numpy(scale(Xtr, cont, scaler))
            Xva_s = torch.from_numpy(scale(Xva, cont, scaler))
            ytr_z = torch.tensor((ytr - ym) / ys, dtype=torch.float32)
            yva_z = torch.tensor((yva - ym) / ys, dtype=torch.float32)
            model, _ = train_mlp(Xtr_s, ytr_z, Xtr_s.shape[1], cfg, Xva_s, yva_z)
            with torch.no_grad():
                pred = model(Xva_s).numpy() * ys + ym
            scores.append(r2_score(yva, pred))
            if trial is not None:
                trial.report(float(np.mean(scores)), i)
                if trial.should_prune():
                    raise optuna.TrialPruned()
        return float(np.mean(scores))

    # ---- Optuna search for the MLP ----
    def objective(trial):
        n_layers = trial.suggest_int("n_layers", 2, 5)
        cfg = {
            "hidden": [trial.suggest_categorical(f"u{i}", [64, 128, 256, 384])
                       for i in range(n_layers)],
            "dropout": trial.suggest_float("dropout", 0.0, 0.5),
            "batchnorm": trial.suggest_categorical("batchnorm", [True, False]),
            "lr": trial.suggest_float("lr", 1e-4, 5e-3, log=True),
            "wd": trial.suggest_float("wd", 1e-6, 1e-3, log=True),
            "batch": trial.suggest_categorical("batch", [64, 128, 256]),
        }
        return cv_mlp(cfg, OBJ_FOLDS, trial)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=SEED),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=8, n_warmup_steps=1),
    )
    print(f"Optuna search: up to {args.trials} trials (≤{OPTUNA_TIMEOUT}s)…")
    study.optimize(objective, n_trials=args.trials, timeout=OPTUNA_TIMEOUT)
    bp = study.best_params
    best_cfg = {
        "hidden": [bp[f"u{i}"] for i in range(bp["n_layers"])],
        "dropout": bp["dropout"], "batchnorm": bp["batchnorm"],
        "lr": bp["lr"], "wd": bp["wd"], "batch": bp["batch"],
    }
    print(f"  trials: {len(study.trials)} | best obj R²log={study.best_value:.3f}")
    print(f"  best arch: {best_cfg['hidden']} dropout={best_cfg['dropout']:.2f} "
          f"bn={best_cfg['batchnorm']} lr={best_cfg['lr']:.1e} batch={best_cfg['batch']}")

    # ---- pick GBM params via CV ----
    kf = KFold(FINAL_FOLDS, shuffle=True, random_state=SEED)
    best_gbm = None
    for params in GBM_GRID:
        s = []
        for tr_idx, va_idx in kf.split(data):
            Xtr, Xva, _, _ = build_fold(tr_idx, va_idx)
            g = lgb.LGBMRegressor(**GBM_COMMON, **params)
            g.fit(Xtr, y[tr_idx], eval_set=[(Xva, y[va_idx])],
                  callbacks=[lgb.early_stopping(50, verbose=False)])
            s.append(r2_score(y[va_idx], g.predict(Xva)))
        m = float(np.mean(s))
        if best_gbm is None or m > best_gbm[1]:
            best_gbm = (params, m)
    gbm_params = best_gbm[0]

    # ---- unified final CV: MLP, GBM and ensemble on identical folds ----
    mlp_s, gbm_s, ens_s, epochs, iters = [], [], [], [], []
    for tr_idx, va_idx in kf.split(data):
        Xtr, Xva, cont, scaler = build_fold(tr_idx, va_idx)
        ytr, yva = y[tr_idx], y[va_idx]
        g = lgb.LGBMRegressor(**GBM_COMMON, **gbm_params)
        g.fit(Xtr, ytr, eval_set=[(Xva, yva)],
              callbacks=[lgb.early_stopping(50, verbose=False)])
        gp = g.predict(Xva)
        iters.append(g.best_iteration_ or GBM_COMMON["n_estimators"])
        ym, ys = ytr.mean(), ytr.std()
        Xtr_s = torch.from_numpy(scale(Xtr, cont, scaler))
        Xva_s = torch.from_numpy(scale(Xva, cont, scaler))
        ytr_z = torch.tensor((ytr - ym) / ys, dtype=torch.float32)
        yva_z = torch.tensor((yva - ym) / ys, dtype=torch.float32)
        model, be = train_mlp(Xtr_s, ytr_z, Xtr_s.shape[1], best_cfg, Xva_s, yva_z)
        epochs.append(be)
        with torch.no_grad():
            mp = model(Xva_s).numpy() * ys + ym
        mlp_s.append(r2_score(yva, mp))
        gbm_s.append(r2_score(yva, gp))
        ens_s.append(r2_score(yva, (mp + gp) / 2))

    def agg(s):
        return float(np.mean(s)), float(np.std(s))

    mlp_log, mlp_std = agg(mlp_s)
    gbm_log, gbm_std = agg(gbm_s)
    ens_log, ens_std = agg(ens_s)
    print("\nCross-validated performance (R²log):")
    print(f"  MLP (tuned)   {mlp_log:.3f} ± {mlp_std:.3f}")
    print(f"  LightGBM      {gbm_log:.3f} ± {gbm_std:.3f}")
    print(f"  Ensemble      {ens_log:.3f} ± {ens_std:.3f}")
    scores = {"mlp": mlp_log, "gbm": gbm_log, "ensemble": ens_log}
    primary = max(scores, key=scores.get)
    print(f"\nPrimary model: {primary.upper()}")

    # ---- retrain both on FULL data ----
    med = {c: float(pd.to_numeric(data[c], errors="coerce").median()) for c in num_cols}
    Xfull, cont = assemble_features(data, num_cols, league_cats, med)
    col_order = list(Xfull.columns)
    scaler = StandardScaler().fit(Xfull[cont])
    y_mean, y_std = float(y.mean()), float(y.std())

    gbm_final = lgb.LGBMRegressor(**{**GBM_COMMON, **gbm_params,
                                     "n_estimators": max(50, int(np.mean(iters)))})
    gbm_final.fit(Xfull, y)

    Xfull_s = torch.from_numpy(scale(Xfull, cont, scaler))
    yfull_z = torch.tensor((y - y_mean) / y_std, dtype=torch.float32)
    mlp_final, _ = train_mlp(Xfull_s, yfull_z, Xfull_s.shape[1], best_cfg,
                             max_epochs=max(20, int(np.mean(epochs))))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(gbm_final, MODELS_DIR / "value_gbm.pkl")
    joblib.dump(scaler, MODELS_DIR / "value_scaler.pkl")
    torch.save({"state": mlp_final.state_dict(), "d_in": Xfull_s.shape[1],
                "hidden": best_cfg["hidden"], "p": best_cfg["dropout"],
                "batchnorm": best_cfg["batchnorm"]},
               MODELS_DIR / "value_mlp.pt")
    meta = {
        "feats": num_cols, "league_cats": league_cats, "medians": med,
        "cont_cols": cont, "col_order": col_order,
        "y_mean": y_mean, "y_std": y_std, "primary": primary,
        "metrics": {"cv_folds": FINAL_FOLDS,
                    "mlp_r2log": mlp_log, "mlp_r2log_std": mlp_std,
                    "gbm_r2log": gbm_log, "gbm_r2log_std": gbm_std,
                    "ensemble_r2log": ens_log, "ensemble_r2log_std": ens_std},
        "mlp_arch": best_cfg, "gbm_params": {**gbm_params, "n_estimators": max(50, int(np.mean(iters)))},
        "optuna_trials": len(study.trials), "n_rows": len(data),
    }
    (MODELS_DIR / "value_meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(f"Saved model artifacts -> {MODELS_DIR}")


if __name__ == "__main__":
    main()
