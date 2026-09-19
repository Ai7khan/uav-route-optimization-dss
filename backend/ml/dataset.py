"""Generate training data from the simulation for the ML models.

Weather nowcast: sequences of weather frames produced by WeatherField.
AD-activity: synthetic emission time-series with periodic duty cycles + noise,
so the classifier learns to forecast next-tick activity from recent history.
"""
from __future__ import annotations

import numpy as np

from backend.config import GRID
from backend.sim.weather import WeatherField

# Weather channels used by the nowcaster (the ones that drive hazard/detection).
CHANNELS = ["wind_u", "wind_v", "visibility_km", "precip"]

# Normalisation ranges (approx) so channels are comparable for the CNN.
NORM = {
    "wind_u": (-40.0, 90.0),
    "wind_v": (-40.0, 90.0),
    "visibility_km": (0.0, 12.0),
    "precip": (0.0, 1.0),
}


def normalize(frame: np.ndarray, channels=CHANNELS) -> np.ndarray:
    out = np.empty_like(frame, dtype=np.float32)
    for i, ch in enumerate(channels):
        lo, hi = NORM[ch]
        out[i] = (frame[i] - lo) / (hi - lo)
    return np.clip(out, 0, 1)


def denormalize(frame: np.ndarray, channels=CHANNELS) -> np.ndarray:
    out = np.empty_like(frame, dtype=np.float32)
    for i, ch in enumerate(channels):
        lo, hi = NORM[ch]
        out[i] = frame[i] * (hi - lo) + lo
    return out


def _frame(w: WeatherField) -> np.ndarray:
    return np.stack([getattr(w, ch) for ch in CHANNELS]).astype(np.float32)


HORIZON = 3  # ticks ahead the nowcaster predicts (3 * 2 min = 6 min)


def weather_sequences(n_series: int = 60, steps: int = 16, k: int = 2,
                      horizon: int = HORIZON, down: int = 2, seed: int = 0):
    """Return (X, Y) for `horizon`-step-ahead frame prediction.

    X: (samples, k*C, h, w) last-k frames ending at index e.
    Y: (samples, C, h, w) frame at index e + horizon.
    `down` spatially downsamples the grid to keep CPU training fast.
    """
    rng = np.random.default_rng(seed)
    X, Y = [], []
    for s in range(n_series):
        w = WeatherField(seed=int(rng.integers(0, 1_000_000)),
                         base_wind=(float(rng.uniform(10, 60)), float(rng.uniform(-10, 30))),
                         storminess=float(rng.uniform(0.05, 0.8)))
        frames = [normalize(_frame(w))[:, ::down, ::down]]
        for _ in range(steps):
            w.step(2.0)
            frames.append(normalize(_frame(w))[:, ::down, ::down])
        for e in range(k - 1, len(frames) - horizon):
            X.append(np.concatenate(frames[e - k + 1:e + 1], axis=0))
            Y.append(frames[e + horizon])
    return np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32)


# --- Air-defense emission series -------------------------------------------
def emission_series(n_sites: int = 6, T: int = 200, seed: int = 0):
    """Binary activity matrix (T, n_sites) from periodic duty cycles + jitter."""
    rng = np.random.default_rng(seed)
    periods = rng.integers(6, 20, size=n_sites)
    duty = rng.uniform(0.3, 0.7, size=n_sites)
    phase = rng.integers(0, 20, size=n_sites)
    act = np.zeros((T, n_sites), dtype=np.int8)
    for j in range(n_sites):
        for t in range(T):
            base = ((t + phase[j]) % periods[j]) / periods[j] < duty[j]
            flip = rng.random() < 0.05  # emission noise
            act[t, j] = int(base ^ flip)
    return act


LAGS = 14  # raw recent states exposed to the model (lets it infer the period)


def featurize_history(act: np.ndarray, t: int, j: int, window: int = LAGS) -> list[float]:
    """Features for predicting site j's activity at t+1 from history up to t.

    Includes the raw last `window` states (so the classifier can recover the
    periodic duty cycle), plus the recent active fraction and ticks-since-toggle.
    """
    lags = []
    for d in range(window):
        idx = t - d
        lags.append(float(act[idx, j]) if idx >= 0 else 0.0)
    hist = act[max(0, t - window + 1):t + 1, j]
    frac = float(hist.mean()) if len(hist) else 0.0
    cur = float(act[t, j])
    since = 0
    for k in range(t, max(0, t - window), -1):
        if act[k, j] == act[t, j]:
            since += 1
        else:
            break
    return lags + [frac, since / window]


def ad_dataset(n_series: int = 30, T: int = 160, seed: int = 0, horizon: int = 1):
    """Predict site activity `horizon` ticks ahead from history up to t."""
    X, y = [], []
    for s in range(n_series):
        act = emission_series(n_sites=6, T=T, seed=seed + s)
        for t in range(LAGS, T - horizon):
            for j in range(act.shape[1]):
                X.append(featurize_history(act, t, j))
                y.append(int(act[t + horizon, j]))
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int8)
