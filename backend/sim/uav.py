"""UAV kinematics and fuel model.

Kept intentionally simple: the optimizer needs a consistent way to turn a leg
(distance + local wind) into a time and fuel cost. Headwind slows the UAV and
burns more fuel; tailwind helps.
"""
from __future__ import annotations

import numpy as np

from backend.config import UAV_CRUISE_KMH


def leg_time_hours(dist_km: float, ground_speed_kmh: float) -> float:
    return dist_km / max(ground_speed_kmh, 1e-3)


def ground_speed(cruise_kmh: float, heading: tuple[float, float],
                 wind_u: float, wind_v: float) -> float:
    """Ground speed given air cruise speed, unit heading vector and wind (km/h).

    heading is a unit vector (east, north). Projected wind along the heading adds
    to (tailwind) or subtracts from (headwind) the airspeed.
    """
    hu, hv = heading
    norm = np.hypot(hu, hv)
    if norm < 1e-9:
        return cruise_kmh
    hu, hv = hu / norm, hv / norm
    wind_along = wind_u * hu + wind_v * hv
    return max(cruise_kmh + wind_along, 10.0)


def leg_fuel(dist_km: float, ground_speed_kmh: float, climb_m: float = 0.0,
             cruise_kmh: float = UAV_CRUISE_KMH) -> float:
    """Fuel units for a leg. Base burn ~ time; penalty for slow ground speed
    (fighting wind) and for climbing."""
    t_h = leg_time_hours(dist_km, ground_speed_kmh)
    base = t_h * 10.0                       # 10 fuel units per hour cruise
    wind_penalty = base * max(0.0, (cruise_kmh - ground_speed_kmh) / cruise_kmh) * 0.5
    climb_penalty = max(0.0, climb_m) / 100.0 * 0.2
    return base + wind_penalty + climb_penalty
