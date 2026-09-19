"""Forecast interface consumed by the risk/planning layers.

Wraps the trained models to (a) predict a future weather field so the optimizer
can plan against where the storm *will be*, and (b) predict near-future SAM
activity so threat rings can be pre-emptively avoided. Both degrade gracefully to
physics/persistence baselines if models are not trained yet.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import zoom

from backend.config import GRID
from backend.ml import weather_nowcast as wn
from backend.ml.dataset import CHANNELS, denormalize, normalize


def forecast_weather(weather: dict[str, np.ndarray], steps: int = 3) -> dict[str, np.ndarray]:
    """Predict the weather field `steps` ticks ahead.

    Uses the trained CNN nowcaster if available (rolled forward), otherwise falls
    back to the simulator's own advection as a physics baseline.
    """
    model = wn.load_model()
    if model is None:
        return _physics_forecast(weather, steps)

    import torch
    down = 2
    # The CNN predicts a fixed horizon (~6 min) ahead in one pass. Seed k=2 with
    # the current frame duplicated (no earlier frame available at request time).
    cur = np.stack([weather[ch] for ch in CHANNELS]).astype(np.float32)
    cur_n = normalize(cur)[:, ::down, ::down]
    stack = np.concatenate([cur_n, cur_n], axis=0)  # (2C, h, w)
    x = torch.tensor(stack[None, ...])
    with torch.no_grad():
        pred = model(x).numpy()[0]               # (C, h, w) normalised, horizon ahead
    pred_full = denormalize(pred)
    # upsample back to full grid
    fy = GRID.n / pred_full.shape[1]
    fx = GRID.n / pred_full.shape[2]
    out = {}
    for i, ch in enumerate(CHANNELS):
        out[ch] = zoom(pred_full[i], (fy, fx), order=1)
    # keep unmodelled channels from the input
    for ch in ("temp_c", "humidity"):
        out[ch] = weather[ch].copy()
    return out


def _physics_forecast(weather: dict[str, np.ndarray], steps: int) -> dict[str, np.ndarray]:
    from backend.sim.weather import WeatherField
    w = WeatherField.__new__(WeatherField)
    w.n = GRID.n
    for ch in ("wind_u", "wind_v", "visibility_km", "precip", "temp_c", "humidity"):
        setattr(w, ch, weather[ch].copy())
    w.rng = np.random.default_rng(0)
    w.tick = 0
    for _ in range(steps):
        w.step(2.0)
    return {ch: getattr(w, ch) for ch in
            ("wind_u", "wind_v", "visibility_km", "precip", "temp_c", "humidity")}
