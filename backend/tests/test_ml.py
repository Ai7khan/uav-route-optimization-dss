"""ML tests: dataset shapes, forecast interface, graceful fallback."""
import numpy as np

from backend.config import GRID
from backend.ml.dataset import (CHANNELS, ad_dataset, emission_series,
                                 featurize_history, weather_sequences)
from backend.ml.forecast import forecast_weather
from backend.sim.scenario import build_scenario


def test_weather_sequences_shapes():
    X, Y = weather_sequences(n_series=2, steps=8)
    assert X.ndim == 4 and Y.ndim == 4
    assert Y.shape[1] == len(CHANNELS)
    assert X.shape[0] == Y.shape[0]


def test_ad_dataset_shapes():
    X, y = ad_dataset(n_series=3, T=60, horizon=3)
    assert len(X) == len(y)
    assert set(np.unique(y)).issubset({0, 1})


def test_featurize_length_stable():
    act = emission_series(n_sites=2, T=40, seed=1)
    f0 = featurize_history(act, 20, 0)
    f1 = featurize_history(act, 5, 1)
    assert len(f0) == len(f1)


def test_forecast_weather_returns_full_grid():
    sc = build_scenario("storm_front")
    fc = forecast_weather(sc.weather.snapshot(), steps=3)
    for ch in CHANNELS:
        assert fc[ch].shape == (GRID.n, GRID.n)


def test_forecast_differs_from_persistence():
    """A trained model should move the field; if untrained, physics fallback still does."""
    sc = build_scenario("storm_front")
    cur = sc.weather.snapshot()
    fc = forecast_weather(cur, steps=3)
    diff = np.abs(fc["precip"] - cur["precip"]).mean()
    assert diff > 0  # forecast is not a no-op
