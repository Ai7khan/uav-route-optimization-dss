"""Weather nowcasting model (compact CNN).

Predicts the next weather frame from the last k frames. A CNN can learn the
advection + diffusion the simulator applies, and beats a persistence baseline
(predict = last frame). Trained on CPU in seconds on downsampled grids.
"""
from __future__ import annotations

import os

import numpy as np

try:
    import torch
    import torch.nn as nn
    TORCH = True
except Exception:  # torch optional at import time
    TORCH = False

from backend.ml.dataset import CHANNELS

MODEL_PATH = os.path.join("data", "weather_nowcast.pt")


if TORCH:
    class NowcastCNN(nn.Module):
        def __init__(self, k: int = 2, c: int = len(CHANNELS)):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(k * c, 32, 3, padding=1), nn.ReLU(),
                nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
                nn.Conv2d(32, c, 3, padding=1),
            )

        def forward(self, x):
            return torch.sigmoid(self.net(x))


def train(epochs: int = 12, lr: float = 2e-3, seed: int = 0):
    """Train the nowcaster; returns metrics dict incl. vs-persistence comparison."""
    assert TORCH, "PyTorch not installed"
    from backend.ml.dataset import weather_sequences
    torch.manual_seed(seed)

    X, Y = weather_sequences(seed=seed)
    n = len(X)
    idx = np.random.default_rng(seed).permutation(n)
    split = int(n * 0.8)
    tr, te = idx[:split], idx[split:]
    Xt, Yt = torch.tensor(X[tr]), torch.tensor(Y[tr])
    Xv, Yv = torch.tensor(X[te]), torch.tensor(Y[te])

    model = NowcastCNN(k=2)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 32):
            b = perm[i:i + 32]
            opt.zero_grad()
            out = model(Xt[b])
            loss = loss_fn(out, Yt[b])
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        pred = model(Xv).numpy()
    truth = Yv.numpy()
    # persistence baseline = last input frame (channels of the most recent frame)
    c = len(CHANNELS)
    persistence = Xv.numpy()[:, -c:, :, :]

    rmse_model = float(np.sqrt(np.mean((pred - truth) ** 2)))
    rmse_persist = float(np.sqrt(np.mean((persistence - truth) ** 2)))
    mae_model = float(np.mean(np.abs(pred - truth)))

    os.makedirs("data", exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)

    return {
        "rmse_model": rmse_model,
        "rmse_persistence": rmse_persist,
        "mae_model": mae_model,
        "skill_vs_persistence_pct": round((1 - rmse_model / rmse_persist) * 100, 1),
        "horizon_ticks": 3, "horizon_min": 6,
        "n_train": int(len(Xt)), "n_val": int(len(Xv)),
    }


_loaded = {"model": None}


def load_model():
    if not TORCH or not os.path.exists(MODEL_PATH):
        return None
    if _loaded["model"] is None:
        m = NowcastCNN(k=2)
        m.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
        m.eval()
        _loaded["model"] = m
    return _loaded["model"]
