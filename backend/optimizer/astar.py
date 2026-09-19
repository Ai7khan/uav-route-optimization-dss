"""A* route planner over the 8-connected grid using the risk cost field."""
from __future__ import annotations

import heapq
from typing import Optional

from backend.config import GRID, UAV_CRUISE_KMH
from backend.risk.cost import CostField
from backend.schemas import Weights

# 8-connected neighbourhood.
NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _heuristic(cell: tuple[int, int], goal: tuple[int, int], weights: Weights,
               cruise_kmh: float, max_tailwind: float = 60.0) -> float:
    """Admissible lower bound: best-case time+fuel to the goal, ignoring risk (>=0)."""
    dist_km = GRID.cell_distance_km(cell, goal)
    best_gs = cruise_kmh + max_tailwind
    t_min = dist_km / best_gs * 60.0
    min_fuel = dist_km / best_gs * 10.0
    return weights.time * t_min + weights.fuel * min_fuel


def astar(field: CostField, start: tuple[int, int], goal: tuple[int, int],
          weights: Weights, cruise_kmh: float = UAV_CRUISE_KMH,
          blocked: Optional[set[tuple[int, int]]] = None) -> Optional[list[tuple[int, int]]]:
    """Return the least-cost cell path start->goal, or None if unreachable."""
    n = GRID.n
    blocked = blocked or set()
    if start in blocked or goal in blocked:
        return None

    ws, wt, wf = weights.safety, weights.time, weights.fuel
    open_heap: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_heap, (0.0, start))
    g_score = {start: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    closed: set[tuple[int, int]] = set()

    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current == goal:
            return _reconstruct(came_from, current)
        if current in closed:
            continue
        closed.add(current)

        cr, cc = current
        for dr, dc in NEIGHBORS:
            nb = (cr + dr, cc + dc)
            if not (0 <= nb[0] < n and 0 <= nb[1] < n):
                continue
            if nb in blocked or nb in closed:
                continue
            step = field.edge_cost_scalar(current, nb, ws, wt, wf, cruise_kmh)
            tentative = g_score[current] + step
            if tentative < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative
                f = tentative + _heuristic(nb, goal, weights, cruise_kmh)
                heapq.heappush(open_heap, (f, nb))

    return None


def _reconstruct(came_from: dict, current: tuple[int, int]) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
