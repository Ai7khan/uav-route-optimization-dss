"""Train both ML models and persist them + metrics.

Run:  python -m backend.ml.train
Writes data/weather_nowcast.pt, data/ad_predictor.pkl, data/ml_metrics.json
"""
from __future__ import annotations

import json
import os
import time


def main():
    os.makedirs("data", exist_ok=True)
    metrics = {}

    print("Training AD-activity predictor (scikit-learn)...")
    from backend.ml import ad_predictor
    t0 = time.time()
    metrics["ad_predictor"] = ad_predictor.train()
    metrics["ad_predictor"]["train_seconds"] = round(time.time() - t0, 1)
    print("  ", metrics["ad_predictor"])

    print("Training weather nowcaster (PyTorch CNN)...")
    try:
        from backend.ml import weather_nowcast
        t0 = time.time()
        metrics["weather_nowcast"] = weather_nowcast.train()
        metrics["weather_nowcast"]["train_seconds"] = round(time.time() - t0, 1)
        print("  ", metrics["weather_nowcast"])
    except AssertionError:
        print("  PyTorch not installed; skipping weather nowcaster.")
        metrics["weather_nowcast"] = {"error": "torch not installed"}

    with open(os.path.join("data", "ml_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print("Saved data/ml_metrics.json")


if __name__ == "__main__":
    main()
