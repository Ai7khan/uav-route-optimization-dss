"""Scenario orchestrator: bundles weather + air defense + a clock, and defines
the demo presets referenced by the brief (clear / storm-front / SAM-activates)."""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.config import GRID, TIME_STEP_MIN
from backend.schemas import ADSite, ADType
from backend.sim.weather import WeatherField


@dataclass
class Scenario:
    scenario_id: str
    weather: WeatherField
    ad_sites: list[ADSite]
    tick: int = 0

    @property
    def time_min(self) -> float:
        return self.tick * TIME_STEP_MIN

    def step(self) -> None:
        self.weather.step(TIME_STEP_MIN)
        self.tick += 1

    def reset(self) -> None:
        self.tick = 0


def _site(id_, lat, lon, t: ADType, rng, power=1.0, schedule=None) -> ADSite:
    return ADSite(id=id_, lat=lat, lon=lon, ad_type=t, max_range_km=rng,
                  power=power, schedule=schedule or [])


def build_scenario(scenario_id: str) -> Scenario:
    """Factory for the demo presets."""
    if scenario_id == "clear":
        weather = WeatherField(seed=1, base_wind=(15.0, 5.0), storminess=0.05)
        sites = [
            _site("SAM-Alpha", 40.35, 44.30, ADType.medium_range, 40.0, power=1.0),
            _site("SAM-Bravo", 40.70, 44.75, ADType.short_range, 15.0, power=1.0),
        ]
        return Scenario(scenario_id, weather, sites)

    if scenario_id == "storm_front":
        # Strong wind pushing a precipitation front across the map.
        weather = WeatherField(seed=7, base_wind=(55.0, 20.0), storminess=0.75)
        sites = [
            _site("SAM-Alpha", 40.30, 44.40, ADType.medium_range, 40.0, power=1.0),
            _site("SAM-Charlie", 40.55, 44.20, ADType.long_range, 120.0, power=0.8),
        ]
        return Scenario(scenario_id, weather, sites)

    if scenario_id == "sam_popup":
        # A medium SAM switches on mid-mission (ticks 6..999) astride the direct
        # route -> forces a replan around it, but leaves an avoidable corridor.
        weather = WeatherField(seed=3, base_wind=(20.0, 8.0), storminess=0.25)
        sites = [
            _site("SAM-Alpha", 40.20, 44.25, ADType.short_range, 15.0, power=1.0),
            _site("SAM-Delta", 40.50, 44.50, ADType.medium_range, 38.0, power=1.1,
                  schedule=[(6, 999)]),
        ]
        return Scenario(scenario_id, weather, sites)

    raise ValueError(f"unknown scenario_id: {scenario_id}")


PRESETS = ["clear", "storm_front", "sam_popup"]
