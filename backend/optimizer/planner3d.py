"""3D (altitude-aware) planning.

Nodes are (row, col, layer) where layer indexes a set of flight altitudes above
ground level (AGL). Each layer has its own terrain-masked detection field, so the
optimizer can fly low to hide behind ridges and climb only when it must (nap-of-
the-earth). Horizontal moves stay in a layer; vertical moves change altitude at a
cell for a climb/descent cost. A virtual goal lets the UAV arrive at the objective
at whatever altitude is cheapest.

Provides:
* CostField3D  - L terrain-masked detection layers + shared weather hazard
* astar3d      - optimal 3D route
* AdaptivePlanner3D - D* Lite incremental repair + A* full replan, in 3D
"""
from __future__ import annotations

import heapq
import time
from typing import Optional

import numpy as np

from backend.config import GRID, UAV_CRUISE_KMH
from backend.risk.cost import weather_hazard
from backend.schemas import Route, RouteSegment, Weights
from backend.sim.airdefense import detection_field

DEFAULT_AGLS = (200.0, 700.0, 1500.0)  # nap-of-earth / low / medium
HORIZ = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
INF = float("inf")
GOAL_LAYER = 99  # virtual "arrived" layer (any altitude accepted at the objective)


class CostField3D:
    def __init__(self, ad_sites, tick, weather, terrain=None, agls=DEFAULT_AGLS):
        self.agls = list(agls)
        self.L = len(self.agls)
        self.weather = weather
        self.hazard = weather_hazard(weather)
        self.detect = [detection_field(ad_sites, tick, agl, weather["visibility_km"],
                                       terrain=terrain) for agl in self.agls]
        # Display heatmap: the risk the UAV would face at its *best* (lowest-risk)
        # altitude, blended with weather hazard.
        best = np.minimum.reduce(self.detect)
        self.danger = np.clip(0.75 * best + 0.6 * self.hazard, 0, 1)

    # --- node helpers -------------------------------------------------------
    def cell_risk(self, node):
        r, c, l = node
        if l == GOAL_LAYER:
            return 0.0
        return float(self.detect[l][r, c])

    def cell_hazard(self, node):
        r, c, l = node
        return float(self.hazard[r, c])

    def edge_cost_scalar(self, a, b, ws, wt, wf, cruise=UAV_CRUISE_KMH) -> float:
        ar, ac, al = a
        br, bc, bl = b
        if bl == GOAL_LAYER:            # arrival transition (free)
            return 0.0
        if (ar, ac) == (br, bc) and al != bl:   # vertical move (climb/descend)
            dalt = abs(self.agls[bl] - self.agls[al])
            climb_time = dalt / 300.0            # ~300 m/min climb/descent
            climb_fuel = dalt / 100.0 * 0.6
            risk = 0.5 * (self.detect[al][ar, ac] + self.detect[bl][br, bc])
            return ws * (risk * risk) * 50.0 + wt * climb_time + wf * climb_fuel + 0.4
        # horizontal move within layer bl
        import math
        cell_km = GRID.cell_km
        east = (bc - ac) * cell_km
        north = (br - ar) * cell_km
        dist_km = math.hypot(east, north)
        wu = 0.5 * (self.weather["wind_u"][ar, ac] + self.weather["wind_u"][br, bc])
        wv = 0.5 * (self.weather["wind_v"][ar, ac] + self.weather["wind_v"][br, bc])
        norm = math.hypot(east, north)
        gs = cruise if norm < 1e-9 else max(cruise + (wu * east + wv * north) / norm, 10.0)
        t_h = dist_km / gs
        base = t_h * 10.0
        fuel = base + base * max(0.0, (cruise - gs) / cruise) * 0.5
        risk = 0.5 * (self.detect[bl][ar, ac] + self.detect[bl][br, bc])
        hazard = 0.5 * (self.hazard[ar, ac] + self.hazard[br, bc])
        return (ws * (risk * risk) * 50.0 + ws * (hazard ** 2) * 30.0
                + wt * (t_h * 60.0) + wf * fuel)


def _neighbors3d(node, n, goal_rc, nlayers=3):
    """Symmetric adjacency (so D* Lite's predecessor/successor handling is valid):
    the goal node connects both ways to the arrival cells at every layer."""
    r, c, l = node
    if l == GOAL_LAYER:                    # goal <-> arrival cells (all layers)
        for al in range(nlayers):
            yield (goal_rc[0], goal_rc[1], al)
        return
    if (r, c) == goal_rc:                  # arrival transition to the goal
        yield (goal_rc[0], goal_rc[1], GOAL_LAYER)
    for dr, dc in HORIZ:                    # horizontal, same layer
        nr, nc = r + dr, c + dc
        if 0 <= nr < n and 0 <= nc < n:
            yield (nr, nc, l)
    for dl in (-1, 1):                      # vertical, same cell
        nl = l + dl
        if 0 <= nl < nlayers:
            yield (r, c, nl)


def _heur3d(node, goal_rc, wt, wf, cruise):
    if node[2] == GOAL_LAYER:
        return 0.0
    dist = GRID.cell_distance_km((node[0], node[1]), goal_rc)
    best_gs = cruise + 60.0
    return wt * (dist / best_gs * 60.0) + wf * (dist / best_gs * 10.0)


def astar3d(field: CostField3D, start, goal_rc, weights: Weights,
            cruise=UAV_CRUISE_KMH):
    n = GRID.n
    ws, wt, wf = weights.safety, weights.time, weights.fuel
    goal = (goal_rc[0], goal_rc[1], GOAL_LAYER)
    openh = [(0.0, start)]
    g = {start: 0.0}
    came = {}
    closed = set()
    while openh:
        _, cur = heapq.heappop(openh)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            path.reverse()
            return path
        if cur in closed:
            continue
        closed.add(cur)
        for nb in _neighbors3d(cur, n, goal_rc):
            if nb in closed:
                continue
            t = g[cur] + field.edge_cost_scalar(cur, nb, ws, wt, wf, cruise)
            if t < g.get(nb, INF):
                came[nb] = cur
                g[nb] = t
                heapq.heappush(openh, (t + _heur3d(nb, goal_rc, wt, wf, cruise), nb))
    return None


def path_to_route3d(field: CostField3D, path, weights: Weights,
                    cruise=UAV_CRUISE_KMH, label="optimal") -> Route:
    ws, wt, wf = weights.safety, weights.time, weights.fuel
    segs, cum_t, cum_f, risks = [], 0.0, 0.0, []
    real = [nd for nd in path if nd[2] != GOAL_LAYER]
    r0, c0, l0 = real[0]
    lat0, lon0 = GRID.cell_to_latlon(r0, c0)
    segs.append(RouteSegment(lat=lat0, lon=lon0, alt_agl_m=field.agls[l0],
                             risk=field.cell_risk(real[0]), hazard=field.cell_hazard(real[0]),
                             cumulative_time_min=0.0, cumulative_fuel=0.0))
    risks.append(field.cell_risk(real[0]))
    total = 0.0
    for a, b in zip(real[:-1], real[1:]):
        ec = field.edge_cost_scalar(a, b, ws, wt, wf, cruise)
        total += ec
        # approximate per-leg time/fuel for reporting (recompute lightweight)
        dalt = abs(field.agls[b[2]] - field.agls[a[2]]) if (a[0], a[1]) == (b[0], b[1]) else 0.0
        if dalt:
            cum_t += dalt / 300.0
            cum_f += dalt / 100.0 * 0.6
        else:
            dist = GRID.cell_distance_km((a[0], a[1]), (b[0], b[1]))
            cum_t += dist / cruise * 60.0
            cum_f += dist / cruise * 10.0
        lat, lon = GRID.cell_to_latlon(b[0], b[1])
        rk = field.cell_risk(b)
        risks.append(rk)
        segs.append(RouteSegment(lat=lat, lon=lon, alt_agl_m=field.agls[b[2]], risk=rk,
                                 hazard=field.cell_hazard(b), cumulative_time_min=cum_t,
                                 cumulative_fuel=cum_f))
    return Route(segments=segs, total_time_min=cum_t, total_fuel=cum_f,
                 max_risk=max(risks), mean_risk=sum(risks) / len(risks),
                 total_cost=total, label=label)


def plan3d(field, start, goal_rc, weights, cruise=UAV_CRUISE_KMH, label="optimal"):
    path = astar3d(field, start, goal_rc, weights, cruise)
    return path_to_route3d(field, path, weights, cruise, label) if path else None


# --- 3D D* Lite (subclass of the validated 2D engine) -----------------------
from backend.optimizer.dstar_lite import DStarLite, changed_cells  # noqa: E402


class DStarLite3D(DStarLite):
    """D* Lite over (row, col, layer). Adjacency is symmetric (incl. the goal),
    so the base algorithm's predecessor/successor logic stays valid."""

    def __init__(self, field: CostField3D, start, goal_rc, weights, cruise=UAV_CRUISE_KMH):
        self.goal_rc = goal_rc
        self.nlayers = field.L
        goal = (goal_rc[0], goal_rc[1], GOAL_LAYER)
        super().__init__(field, start, goal, weights, cruise)

    def _neighbors(self, s):
        return _neighbors3d(s, self.n, self.goal_rc, self.nlayers)

    def _heuristic(self, s):
        rc = self.start[:2]
        target = self.goal_rc if s[2] == GOAL_LAYER else (s[0], s[1])
        dist = GRID.cell_distance_km(rc, target)
        return self.weights.time * (dist / (self.cruise + 60.0) * 60.0)

    def update_field(self, new_field: CostField3D, changed_2d):
        self.field = new_field
        self.expansions = 0
        touched = set()
        for (r, c) in changed_2d:
            for l in range(self.nlayers):
                node = (r, c, l)
                touched.add(node)
                for nb in self._neighbors(node):
                    touched.add(nb)
        for u in touched:
            self._update_vertex(u)
        self.compute_shortest_path()


ALT_PRESETS_3D = {
    "safest": Weights(safety=2.5, time=0.15, fuel=0.1),
    "fastest": Weights(safety=0.3, time=1.0, fuel=0.2),
}
REBUILD_THRESHOLD = 400


class AdaptivePlanner3D:
    """3D adaptive planner: D* Lite incremental repair on gradual drift, full A*
    replan on major discrete events (same strategy as the 2D planner)."""

    def __init__(self, field: CostField3D, start, goal_rc, weights, cruise=UAV_CRUISE_KMH):
        self.start = start
        self.goal_rc = goal_rc
        self.weights = weights
        self.cruise = cruise
        self.field = field
        self.dstar = DStarLite3D(field, start, goal_rc, weights, cruise)
        self.dstar.compute_shortest_path()
        self.last_stats = {"strategy": "initial", "ms": 0.0,
                           "expansions": self.dstar.expansions, "changed_cells": 0,
                           "maintenance_ms": 0.0}

    def current_route(self, label="optimal") -> Optional[Route]:
        path = self.dstar.get_path()
        return path_to_route3d(self.field, path, self.weights, self.cruise, label) if path else None

    def update(self, new_field: CostField3D) -> Optional[Route]:
        cc = changed_cells(self.field, new_field, threshold=0.08)
        self.field = new_field
        maint = 0.0
        if len(cc) > REBUILD_THRESHOLD:
            t0 = time.time()
            route = plan3d(new_field, self.start, self.goal_rc, self.weights, self.cruise)
            latency = (time.time() - t0) * 1000
            t1 = time.time()
            self.dstar = DStarLite3D(new_field, self.start, self.goal_rc, self.weights, self.cruise)
            self.dstar.compute_shortest_path()
            maint = (time.time() - t1) * 1000
            strat = "full_replan(A*)"
        else:
            t0 = time.time()
            self.dstar.update_field(new_field, cc)
            latency = (time.time() - t0) * 1000
            route = self.current_route()
            strat = "incremental(D*Lite)"
        self.last_stats = {"strategy": strat, "ms": latency, "maintenance_ms": maint,
                           "expansions": self.dstar.expansions, "changed_cells": len(cc)}
        return route

    def alternatives(self) -> list[Route]:
        out = []
        for label, w in ALT_PRESETS_3D.items():
            r = plan3d(self.field, self.start, self.goal_rc, w, self.cruise, label)
            if r:
                out.append(r)
        return out
