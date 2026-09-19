"""Air-defense activity predictor (scikit-learn).

Forecasts whether a SAM site will be emitting next tick from its recent activity
history. A gradient-boosted classifier learns the periodic duty cycle + noise and
beats the persistence baseline (assume next == current).
"""
from __future__ import annotations

import os
import pickle

import numpy as np

from backend.ml.dataset import LAGS, ad_dataset, featurize_history

MODEL_PATH = os.path.join("data", "ad_predictor.pkl")


# Operationally useful lookahead: 3 ticks = 6 min, enough for the operator to
# react before a SAM starts emitting.
PRIMARY_HORIZON = 3


def train(seed: int = 0) -> dict:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    horizons = {}
    primary_model = None
    for h in (1, 2, 3):
        X, y = ad_dataset(n_series=30, T=160, seed=seed, horizon=h)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=seed)
        clf = GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=seed)
        clf.fit(Xtr, ytr)
        proba = clf.predict_proba(Xte)[:, 1]
        acc = float(accuracy_score(yte, (proba >= 0.5).astype(int)))
        auc = float(roc_auc_score(yte, proba))
        persist_acc = float(accuracy_score(yte, Xte[:, 0].astype(int)))
        horizons[f"t+{h}"] = {
            "accuracy": round(acc, 3), "auc": round(auc, 3),
            "persistence_accuracy": round(persist_acc, 3),
            "gain_pts": round((acc - persist_acc) * 100, 1),
        }
        if h == PRIMARY_HORIZON:
            primary_model = clf
            primary = horizons[f"t+{h}"]
            n_tr, n_te = len(Xtr), len(Xte)

    os.makedirs("data", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(primary_model, f)

    return {
        "primary_horizon": f"t+{PRIMARY_HORIZON} ({PRIMARY_HORIZON*2} min)",
        **primary,
        "by_horizon": horizons,
        "n_train": int(n_tr), "n_test": int(n_te),
    }


_loaded = {"model": None}


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    if _loaded["model"] is None:
        with open(MODEL_PATH, "rb") as f:
            _loaded["model"] = pickle.load(f)
    return _loaded["model"]


def predict_activity(history: np.ndarray, t: int, j: int, window: int = LAGS) -> float:
    """P(site j active at t+1) given activity history matrix (T, n_sites)."""
    model = load_model()
    feats = np.array([featurize_history(history, t, j, window)], dtype=np.float32)
    if model is None:
        return float(history[t, j])  # persistence fallback
    return float(model.predict_proba(feats)[0, 1])
