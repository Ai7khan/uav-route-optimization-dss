"""Risk model and cost field.

Combines air-defense detection probability with a weather-hazard score into a
per-cell field, and turns local conditions into the edge cost used by the
optimizer:  cost = w_safety*risk + w_time*time + w_fuel*fuel.
"""
from __future__ import annotations

import numpy as np

from backend.config import GRID
from backend.schemas import ADSite, Weights
from backend.sim.airdefense import detection_field
from backend.sim.uav import ground_speed, leg_fuel, leg_time_hours


def weather_hazard(weather: dict[str, np.ndarray]) -> np.ndarray:
    """0..1 hazard from wind, visibility and precip (flight-safety risk)."""
    wind = np.sqrt(weather["wind_u"] ** 2 + weather["wind_v"] ** 2)
    wind_haz = np.clip(wind / 80.0, 0, 1)              # 80+ km/h = max hazard
    vis_haz = np.clip((6.0 - weather["visibility_km"]) / 6.0, 0, 1)  # <6km worsens
    precip_haz = np.clip(weather["precip"], 0, 1)
    hazard = 0.5 * wind_haz + 0.3 * vis_haz + 0.2 * precip_haz
    return np.clip(hazard, 0, 1)


class CostField:
    """Precomputed per-cell risk & hazard used to evaluate optimizer edges."""

    def __init__(self, ad_sites: list[ADSite], tick: int, uav_alt_m: float,
                 weather: dict[str, np.ndarray]):
        self.tick = tick
        self.alt = uav_alt_m
        self.weather = weather
        self.detect = detection_field(ad_sites, tick, uav_alt_m, weather["visibility_km"])
        self.hazard = weather_hazard(weather)
        # Combined "danger" for display / heatmaps.
        self.danger = np.clip(0.7 * self.detect + 0.3 * self.hazard, 0, 1)

    def cell_risk(self, cell: tuple[int, int]) -> float:
        return float(self.detect[cell])

    def cell_hazard(self, cell: tuple[int, int]) -> float:
        return float(self.hazard[cell])

    def edge_cost_scalar(self, a: tuple[int, int], b: tuple[int, int],
                         w_safety: float, w_time: float, w_fuel: float,
                         cruise_kmh: float = 120.0) -> float:
        """Fast scalar edge cost for the optimizer hot loops (no dict alloc)."""
        import math
        dr = b[0] - a[0]
        dc = b[1] - a[1]
        cell_km = GRID.cell_km
        east = dc * cell_km
        north = dr * cell_km
        dist_km = math.hypot(east, north)

        wu = 0.5 * (self.weather["wind_u"][a] + self.weather["wind_u"][b])
        wv = 0.5 * (self.weather["wind_v"][a] + self.weather["wind_v"][b])
        norm = math.hypot(east, north)
        if norm < 1e-9:
            gs = cruise_kmh
        else:
            wind_along = (wu * east + wv * north) / norm
            gs = max(cruise_kmh + wind_along, 10.0)
        t_h = dist_km / gs
        base = t_h * 10.0
        fuel = base + base * max(0.0, (cruise_kmh - gs) / cruise_kmh) * 0.5

        risk = 0.5 * (self.detect[a] + self.detect[b])
        hazard = 0.5 * (self.hazard[a] + self.hazard[b])
        risk_term = w_safety * (risk * risk) * 50.0 + w_safety * hazard * 5.0
        time_term = w_time * (t_h * 60.0)
        fuel_term = w_fuel * fuel
        return risk_term + time_term + fuel_term

    def edge_cost(self, a: tuple[int, int], b: tuple[int, int],
                  weights: Weights, cruise_kmh: float = 120.0) -> dict:
        """Cost of moving from cell a to neighbour b.

        Returns a dict with the scalar cost plus its components so the API can
        report per-segment time / fuel / risk.
        """
        dist_km = GRID.cell_distance_km(a, b)

        # Heading (east, north) from a to b in km space.
        east = (b[1] - a[1]) * GRID.cell_km
        north = (b[0] - a[0]) * GRID.cell_km

        # Wind at the midpoint (average of the two cells).
        wu = 0.5 * (self.weather["wind_u"][a] + self.weather["wind_u"][b])
        wv = 0.5 * (self.weather["wind_v"][a] + self.weather["wind_v"][b])
        gs = ground_speed(cruise_kmh, (east, north), wu, wv)
        t_h = leg_time_hours(dist_km, gs)
        fuel = leg_fuel(dist_km, gs, cruise_kmh=cruise_kmh)

        # Risk of the destination cell (detection) + weather hazard.
        risk = 0.5 * (self.detect[a] + self.detect[b])
        hazard = 0.5 * (self.hazard[a] + self.hazard[b])

        # Normalise components to comparable scales.
        # risk in 0..1 already; scale up so w_safety=1 dominates dangerous cells.
        risk_term = weights.safety * (risk ** 2) * 50.0 + weights.safety * hazard * 5.0
        time_term = weights.time * (t_h * 60.0)   # minutes
        fuel_term = weights.fuel * fuel

        cost = risk_term + time_term + fuel_term
        return {
            "cost": float(cost),
            "time_min": float(t_h * 60.0),
            "fuel": float(fuel),
            "risk": float(risk),
            "hazard": float(hazard),
            "dist_km": float(dist_km),
        }
