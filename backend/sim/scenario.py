"""Scenario orchestrator: bundles weather + air defense + a clock, and defines
the demo presets referenced by the brief (clear / storm-front / SAM-activates)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from backend.config import GRID, TIME_STEP_MIN
from backend.schemas import ADSite, ADType
from backend.sim.terrain import build_dem
from backend.sim.weather import WeatherField


@dataclass
class Scenario:
    scenario_id: str
    weather: WeatherField
    ad_sites: list[ADSite]
    terrain: np.ndarray = field(default=None)
    tick: int = 0

    @property
    def time_min(self) -> float:
        return self.tick * TIME_STEP_MIN

    def step(self) -> None:
        self.weather.step(TIME_STEP_MIN)
        self.tick += 1

    def reset(self) -> None:
        self.tick = 0


def _site(id_, fr_lat, fr_lon, t: ADType, rng, power=1.0, schedule=None) -> ADSite:
    """Create a site from a fractional position in the theatre box (0..1)."""
    lat, lon = GRID.frac_to_latlon(fr_lat, fr_lon)
    return ADSite(id=id_, lat=lat, lon=lon, ad_type=t, max_range_km=rng,
                  power=power, schedule=schedule or [])


_DEM = None


def _dem():
    """Shared, cached terrain (static across scenarios)."""
    global _DEM
    if _DEM is None:
        _DEM = build_dem()
    return _DEM


def build_scenario(scenario_id: str) -> Scenario:
    """Factory for the demo presets. Site positions are fractions of the box."""
    if scenario_id == "clear":
        # Baseline: calm weather, SAMs well off the direct corridor -> a clean,
        # near-straight low-risk route.
        weather = WeatherField(seed=1, base_wind=(15.0, 5.0), storminess=0.05)
        sites = [
            _site("SAM-Alpha", 0.80, 0.20, ADType.medium_range, 30.0, power=1.0),
            _site("SAM-Bravo", 0.20, 0.80, ADType.short_range, 15.0, power=1.0),
        ]
        return Scenario(scenario_id, weather, sites, terrain=_dem())

    if scenario_id == "storm_front":
        # A localized precipitation band cuts across the map leaving a western
        # corridor -> the route detours around the weather (not the SAMs). Strong
        # wind advects the band over time, so the route shifts as it moves.
        weather = WeatherField(seed=7, base_wind=(12.0, -18.0), storminess=0.12)
        weather.add_storm_band(row_frac=0.55, col_lo_frac=0.28, col_hi_frac=1.0,
                               half_width_frac=0.09, intensity=1.0)
        sites = [
            _site("SAM-Charlie", 0.28, 0.72, ADType.short_range, 15.0, power=1.0),
        ]
        return Scenario(scenario_id, weather, sites, terrain=_dem())

    if scenario_id == "sam_popup":
        # A medium SAM switches on mid-mission (ticks 6..999) astride the direct
        # route -> forces a replan around it, but leaves an avoidable corridor.
        weather = WeatherField(seed=3, base_wind=(20.0, 8.0), storminess=0.25)
        sites = [
            _site("SAM-Alpha", 0.20, 0.25, ADType.short_range, 15.0, power=1.0),
            _site("SAM-Delta", 0.50, 0.50, ADType.medium_range, 38.0, power=1.1,
                  schedule=[(6, 999)]),
        ]
        return Scenario(scenario_id, weather, sites, terrain=_dem())

    raise ValueError(f"unknown scenario_id: {scenario_id}")


PRESETS = ["clear", "storm_front", "sam_popup"]
