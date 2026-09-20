"""Data contracts shared across the system.

Pydantic models exchanged between the simulation, ML/risk layers, optimizer and
API. The live mission-state payload is assembled as a dict in
`backend/api/session.py: Mission.state()`; the models here are the typed pieces
that payload is built from (routes, sites, weights).
"""
from __future__ import annotations

from enum import Enum

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


# --- Route ------------------------------------------------------------------
class RouteSegment(BaseModel):
    lat: float
    lon: float
    alt_agl_m: float = 0.0  # flight altitude above ground level at this point
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


# --- Operator multi-objective weights (safety / speed / fuel sliders) --------
class Weights(BaseModel):
    safety: float = 1.0
    time: float = 0.4
    fuel: float = 0.3
