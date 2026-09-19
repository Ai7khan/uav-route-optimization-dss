"""Data contracts shared across the system (Phase 0 - frozen first).

These Pydantic models define the JSON shapes exchanged between the simulation,
the ML/risk layers, the optimizer, and the API/UI. Grid fields (weather, risk)
are transmitted as nested lists (row-major NxN) for easy JSON serialisation.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Air defense ------------------------------------------------------------
class ADType(str, Enum):
    short_range = "short_range"   # e.g. point-defense, ~15 km
    medium_range = "medium_range"  # ~40 km
    long_range = "long_range"     # ~120 km


class ADSite(BaseModel):
    id: str
    lat: float
    lon: float
    ad_type: ADType
    max_range_km: float
    power: float = Field(1.0, description="relative emitter power, scales detection")
    active: bool = True
    # Emission on/off schedule as (start_tick, end_tick) windows; empty => always on.
    schedule: list[tuple[int, int]] = Field(default_factory=list)


# --- Weather ----------------------------------------------------------------
class WeatherCell(BaseModel):
    wind_u: float   # eastward wind component (km/h)
    wind_v: float   # northward wind component (km/h)
    visibility_km: float
    precip: float   # 0..1 precipitation intensity
    temp_c: float
    humidity: float  # 0..1


class WeatherGrid(BaseModel):
    """Row-major NxN grids, one per weather variable."""
    wind_u: list[list[float]]
    wind_v: list[list[float]]
    visibility_km: list[list[float]]
    precip: list[list[float]]
    temp_c: list[list[float]]
    humidity: list[list[float]]


# --- UAV --------------------------------------------------------------------
class UAVState(BaseModel):
    lat: float
    lon: float
    alt_m: float
    speed_kmh: float
    fuel: float


# --- Route ------------------------------------------------------------------
class RouteSegment(BaseModel):
    lat: float
    lon: float
    risk: float           # detection risk at this point (0..1)
    hazard: float         # weather hazard at this point (0..1)
    cumulative_time_min: float
    cumulative_fuel: float


class Route(BaseModel):
    segments: list[RouteSegment]
    total_time_min: float
    total_fuel: float
    max_risk: float
    mean_risk: float
    total_cost: float
    label: str = "optimal"


class Weights(BaseModel):
    safety: float = 1.0
    time: float = 0.4
    fuel: float = 0.3


# --- Requests / responses ---------------------------------------------------
class PlanRequest(BaseModel):
    scenario_id: str
    start_lat: float
    start_lon: float
    goal_lat: float
    goal_lon: float
    alt_m: float = 500.0
    weights: Weights = Field(default_factory=Weights)
    tick: int = 0
    waypoints: list[tuple[float, float]] = Field(default_factory=list)
    use_forecast: bool = True
    alternatives: bool = True


class ScenarioState(BaseModel):
    scenario_id: str
    tick: int
    time_min: float
    weather: WeatherGrid
    ad_sites: list[ADSite]
    uav: Optional[UAVState] = None
