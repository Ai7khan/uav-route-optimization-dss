"""Turn a cell path into a Route with per-segment and total metrics, and build
multi-objective alternatives by re-running A* under different weight presets."""
from __future__ import annotations

from typing import Optional

from backend.config import GRID, UAV_CRUISE_KMH
from backend.optimizer.astar import astar
from backend.risk.cost import CostField
from backend.schemas import Route, RouteSegment, Weights


def path_to_route(field: CostField, path: list[tuple[int, int]], weights: Weights,
                  cruise_kmh: float = UAV_CRUISE_KMH, label: str = "optimal") -> Route:
    segments: list[RouteSegment] = []
    cum_time = 0.0
    cum_fuel = 0.0
    risks: list[float] = []

    # First point.
    lat0, lon0 = GRID.cell_to_latlon(*path[0])
    segments.append(RouteSegment(
        lat=lat0, lon=lon0, risk=field.cell_risk(path[0]),
        hazard=field.cell_hazard(path[0]), cumulative_time_min=0.0, cumulative_fuel=0.0))
    risks.append(field.cell_risk(path[0]))

    total_cost = 0.0
    for a, b in zip(path[:-1], path[1:]):
        ec = field.edge_cost(a, b, weights, cruise_kmh)
        cum_time += ec["time_min"]
        cum_fuel += ec["fuel"]
        total_cost += ec["cost"]
        lat, lon = GRID.cell_to_latlon(*b)
        seg_risk = field.cell_risk(b)
        risks.append(seg_risk)
        segments.append(RouteSegment(
            lat=lat, lon=lon, risk=seg_risk, hazard=field.cell_hazard(b),
            cumulative_time_min=cum_time, cumulative_fuel=cum_fuel))

    return Route(
        segments=segments,
        total_time_min=cum_time,
        total_fuel=cum_fuel,
        max_risk=max(risks) if risks else 0.0,
        mean_risk=sum(risks) / len(risks) if risks else 0.0,
        total_cost=total_cost,
        label=label,
    )


def plan_route(field: CostField, start: tuple[int, int], goal: tuple[int, int],
               weights: Weights, cruise_kmh: float = UAV_CRUISE_KMH,
               label: str = "optimal") -> Optional[Route]:
    path = astar(field, start, goal, weights, cruise_kmh)
    if path is None:
        return None
    return path_to_route(field, path, weights, cruise_kmh, label)


# Weight presets for the alternative routes shown to the operator.
ALT_PRESETS = {
    "safest": Weights(safety=2.5, time=0.15, fuel=0.1),
    "fastest": Weights(safety=0.3, time=1.0, fuel=0.2),
}


def plan_alternatives(field: CostField, start: tuple[int, int], goal: tuple[int, int],
                      base_weights: Weights,
                      cruise_kmh: float = UAV_CRUISE_KMH) -> list[Route]:
    """Optimal (operator weights) + a safest and a fastest alternative."""
    routes: list[Route] = []
    opt = plan_route(field, start, goal, base_weights, cruise_kmh, "optimal")
    if opt:
        routes.append(opt)
    for label, w in ALT_PRESETS.items():
        r = plan_route(field, start, goal, w, cruise_kmh, label)
        if r:
            routes.append(r)
    return routes
