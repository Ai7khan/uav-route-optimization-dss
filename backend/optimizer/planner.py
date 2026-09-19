"""Adaptive route planner.

Wraps D* Lite and A* and picks the cheaper replanning strategy per tick:

* Gradual change (weather drift, few cells cross the danger threshold) -> D* Lite
  incremental repair, typically single-digit milliseconds.
* Large discrete change (a SAM illuminates a wide area, thousands of cells flip)
  -> a full rebuild, because incremental repair of a huge changed set is slower
  than replanning from scratch.

This mirrors how a real DSS would behave: cheap continuous updates, occasional
full replans on major events. The planner reports which strategy ran, timing,
and vertex expansions so the UI/pitch can show the benefit honestly.
"""
from __future__ import annotations

import time
from typing import Optional

from backend.config import GRID, UAV_CRUISE_KMH
from backend.optimizer.astar import astar
from backend.optimizer.dstar_lite import DStarLite, changed_cells
from backend.optimizer.route import path_to_route
from backend.risk.cost import CostField
from backend.schemas import Route, Weights

# If more than this many cells change in one tick, rebuild instead of repairing.
REBUILD_THRESHOLD = 400
DANGER_DELTA = 0.08  # min danger change for a cell to count as "changed"


class AdaptivePlanner:
    def __init__(self, field: CostField, start: tuple[int, int], goal: tuple[int, int],
                 weights: Weights, cruise_kmh: float = UAV_CRUISE_KMH):
        self.start = start
        self.goal = goal
        self.weights = weights
        self.cruise = cruise_kmh
        self.field = field
        self.dstar = DStarLite(field, start, goal, weights, cruise_kmh)
        self.dstar.compute_shortest_path()
        self.last_stats: dict = {"strategy": "initial", "ms": 0.0, "expansions": self.dstar.expansions,
                                 "changed_cells": 0}

    def current_route(self, label: str = "optimal") -> Optional[Route]:
        path = self.dstar.get_path()
        if path is None:
            return None
        return path_to_route(self.field, path, self.weights, self.cruise, label)

    def update(self, new_field: CostField) -> Optional[Route]:
        cc = changed_cells(self.field, new_field, threshold=DANGER_DELTA)
        self.field = new_field
        maintenance_ms = 0.0

        if len(cc) > REBUILD_THRESHOLD:
            # Major discrete event: the operator's route comes from a full A* solve
            # (the latency they actually wait for). D* Lite is then re-warmed so the
            # following continuous ticks are cheap again -- in production this
            # re-warm runs on a background thread, off the operator's critical path.
            t0 = time.time()
            route = plan_once(new_field, self.start, self.goal, self.weights, self.cruise)
            latency_ms = (time.time() - t0) * 1000
            t1 = time.time()
            self.dstar = DStarLite(new_field, self.start, self.goal, self.weights, self.cruise)
            self.dstar.compute_shortest_path()
            maintenance_ms = (time.time() - t1) * 1000
            strategy = "full_replan(A*)"
        else:
            t0 = time.time()
            self.dstar.update_field(new_field, cc)
            latency_ms = (time.time() - t0) * 1000
            route = self.current_route()
            strategy = "incremental(D*Lite)"

        self.last_stats = {"strategy": strategy, "ms": latency_ms,
                           "maintenance_ms": maintenance_ms,
                           "expansions": self.dstar.expansions, "changed_cells": len(cc)}
        return route


def plan_once(field: CostField, start, goal, weights: Weights,
              cruise_kmh: float = UAV_CRUISE_KMH, label: str = "optimal") -> Optional[Route]:
    """One-shot A* plan (used for alternatives and stateless requests)."""
    path = astar(field, start, goal, weights, cruise_kmh)
    if path is None:
        return None
    return path_to_route(field, path, weights, cruise_kmh, label)
