"""Weather field simulation.

Generates coherent, spatially-smooth weather fields over the grid and evolves them
over time by advecting the fields with the prevailing wind. Deterministic given a
seed so scenarios are reproducible for the demo.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from backend.config import GRID


def _smooth_noise(rng: np.random.Generator, n: int, scale: float, sigma: float) -> np.ndarray:
    """Value noise: white noise blurred to a chosen spatial scale, normalised to 0..1."""
    field = rng.standard_normal((n, n))
    field = gaussian_filter(field, sigma=sigma, mode="reflect")
    field -= field.min()
    denom = field.max() - field.min()
    if denom > 1e-9:
        field /= denom
    return field


class WeatherField:
    """Holds NxN arrays for each weather variable and advects them over time."""

    def __init__(self, seed: int = 0, base_wind: tuple[float, float] = (25.0, 10.0),
                 storminess: float = 0.3):
        self.n = GRID.n
        self.rng = np.random.default_rng(seed)
        self.base_wind = base_wind  # (u eastward, v northward) km/h
        self.storminess = storminess  # 0..1, drives precip / low visibility

        n = self.n
        # Wind: a slowly varying field around the base wind.
        self.wind_u = self.base_wind[0] + (_smooth_noise(self.rng, n, 1.0, 12) - 0.5) * 40
        self.wind_v = self.base_wind[1] + (_smooth_noise(self.rng, n, 1.0, 12) - 0.5) * 40

        # A "weather front" of precipitation / low visibility.
        front = _smooth_noise(self.rng, n, 1.0, 8)
        self.precip = np.clip((front - (1 - storminess)) * 3, 0, 1)
        self.visibility_km = 10.0 - self.precip * 8.5 + _smooth_noise(self.rng, n, 1.0, 15) * 1.5
        self.visibility_km = np.clip(self.visibility_km, 0.3, 12.0)

        self.temp_c = 15 + (_smooth_noise(self.rng, n, 1.0, 20) - 0.5) * 12
        self.humidity = np.clip(0.4 + self.precip * 0.5 + (_smooth_noise(self.rng, n, 1.0, 18) - 0.5) * 0.3, 0, 1)

        self.tick = 0

    def add_storm_band(self, row_frac: float, col_lo_frac: float, col_hi_frac: float,
                       half_width_frac: float = 0.08, intensity: float = 1.0) -> None:
        """Stamp a strong, localized storm band (high precip, low visibility, gusty
        wind) across part of the grid, leaving the rest as a clear corridor. Used
        to give the storm scenario a weather feature the route visibly detours
        around. The band advects with the wind like the rest of the field."""
        n = self.n
        rows, cols = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        r0 = row_frac * n
        c_lo, c_hi = col_lo_frac * n, col_hi_frac * n
        hw = half_width_frac * n
        # Gaussian across rows, hard cutoff outside the column span (the corridor).
        band = np.exp(-((rows - r0) ** 2) / (2 * hw ** 2))
        band = np.where((cols >= c_lo) & (cols <= c_hi), band, 0.0)
        band *= intensity
        self.precip = np.clip(self.precip + band, 0, 1)
        self.visibility_km = np.clip(self.visibility_km - band * 9.0, 0.3, 12.0)
        # Strong crosswind gust front (perpendicular to a SW->NE track): it raises
        # the wind hazard sharply without giving a tail/head-wind ground-speed
        # bias, so the band is costly purely as a hazard and the route detours.
        self.wind_u = self.wind_u + band * 42.0
        self.wind_v = self.wind_v - band * 42.0

    def step(self, dt_min: float = 2.0) -> None:
        """Advance the weather one tick by advecting fields along the wind."""
        self.tick += 1
        # Mean wind in cells/step. cell_km ~ 1.1 km; wind km/h * (dt_h) / cell_km
        dt_h = dt_min / 60.0
        mean_u = float(np.mean(self.wind_u))
        mean_v = float(np.mean(self.wind_v))
        shift_col = mean_u * dt_h / GRID.cell_km  # eastward => +col
        shift_row = mean_v * dt_h / GRID.cell_km  # northward => +row

        for name in ("precip", "visibility_km", "temp_c", "humidity"):
            arr = getattr(self, name)
            setattr(self, name, self._advect(arr, shift_row, shift_col))

        # Small random evolution so it is not a pure translation.
        self.precip = np.clip(self.precip + (self.rng.standard_normal(self.precip.shape) * 0.01), 0, 1)
        self.precip = gaussian_filter(self.precip, sigma=1.0, mode="reflect")
        self.visibility_km = np.clip(self.visibility_km, 0.3, 12.0)

    def _advect(self, arr: np.ndarray, shift_row: float, shift_col: float) -> np.ndarray:
        n = self.n
        rows, cols = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        src_rows = rows - shift_row
        src_cols = cols - shift_col
        return map_coordinates(arr, [src_rows, src_cols], order=1, mode="reflect")

    # --- accessors ----------------------------------------------------------
    def wind_speed(self) -> np.ndarray:
        return np.sqrt(self.wind_u ** 2 + self.wind_v ** 2)

    def as_dict(self) -> dict:
        return {
            "wind_u": self.wind_u.tolist(),
            "wind_v": self.wind_v.tolist(),
            "visibility_km": self.visibility_km.tolist(),
            "precip": self.precip.tolist(),
            "temp_c": self.temp_c.tolist(),
            "humidity": self.humidity.tolist(),
        }

    def snapshot(self) -> dict[str, np.ndarray]:
        """Copy of current arrays for the risk/forecast layers."""
        return {
            "wind_u": self.wind_u.copy(),
            "wind_v": self.wind_v.copy(),
            "visibility_km": self.visibility_km.copy(),
            "precip": self.precip.copy(),
            "temp_c": self.temp_c.copy(),
            "humidity": self.humidity.copy(),
        }
