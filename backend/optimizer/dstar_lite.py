"""D* Lite incremental route planner (Koenig & Likhachev, 2002).

Why this over plain A*: when conditions change *locally* mid-flight (a SAM switches
on, a storm cell drifts across one corridor), D* Lite repairs the existing shortest
path instead of recomputing it from scratch. It plans backward from the goal, so as
the UAV advances and nearby edge costs change, only the affected part of the search
tree is updated -- much cheaper than a fresh A* each tick.

This implementation validates against A* on static fields (see tests) and reports how
many vertex expansions a repair costs vs. a full replan.
"""
from __future__ import annotations

import heapq
from typing import Optional

from backend.config import GRID, UAV_CRUISE_KMH
from backend.risk.cost import CostField
from backend.schemas import Weights

NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
INF = float("inf")


class DStarLite:
    def __init__(self, field: CostField, start: tuple[int, int], goal: tuple[int, int],
                 weights: Weights, cruise_kmh: float = UAV_CRUISE_KMH):
        self.field = field
        self.weights = weights
        self.ws, self.wt, self.wf = weights.safety, weights.time, weights.fuel
        self.cruise = cruise_kmh
        self.n = GRID.n
        self.start = start
        self.goal = goal
        self.km = 0.0  # key modifier accumulated as the start moves

        self.g: dict[tuple[int, int], float] = {}
        self.rhs: dict[tuple[int, int], float] = {}
        self.U: list[tuple[tuple[float, float], tuple[int, int]]] = []
        self.U_lookup: dict[tuple[int, int], tuple[float, float]] = {}
        self.expansions = 0

        self.rhs[goal] = 0.0
        self.g[goal] = INF
        self._u_insert(goal, self._calc_key(goal))

    # --- cost helpers -------------------------------------------------------
    def _g(self, s):
        return self.g.get(s, INF)

    def _rhs(self, s):
        return self.rhs.get(s, INF)

    def _edge(self, u, v) -> float:
        """Directed cost u->v (cost is the destination-based term in edge_cost)."""
        return self.field.edge_cost_scalar(u, v, self.ws, self.wt, self.wf, self.cruise)

    def _heuristic(self, s) -> float:
        dist_km = GRID.cell_distance_km(self.start, s)
        best_gs = self.cruise + 60.0
        return self.weights.time * (dist_km / best_gs * 60.0)

    def _neighbors(self, s):
        r, c = s
        for dr, dc in NEIGHBORS:
            nb = (r + dr, c + dc)
            if 0 <= nb[0] < self.n and 0 <= nb[1] < self.n:
                yield nb

    # --- priority queue (lazy-deletion heap) --------------------------------
    def _calc_key(self, s) -> tuple[float, float]:
        k2 = min(self._g(s), self._rhs(s))
        k1 = k2 + self._heuristic(s) + self.km
        return (k1, k2)

    def _u_insert(self, s, key):
        self.U_lookup[s] = key
        heapq.heappush(self.U, (key, s))

    def _u_update(self, s, key):
        self.U_lookup[s] = key
        heapq.heappush(self.U, (key, s))  # stale entries filtered on pop

    def _u_remove(self, s):
        self.U_lookup.pop(s, None)

    def _u_top_key(self) -> tuple[float, float]:
        while self.U:
            key, s = self.U[0]
            if self.U_lookup.get(s) != key:  # stale
                heapq.heappop(self.U)
                continue
            return key
        return (INF, INF)

    def _u_pop(self):
        while self.U:
            key, s = heapq.heappop(self.U)
            if self.U_lookup.get(s) == key:
                self.U_lookup.pop(s, None)
                return s
        return None

    # --- core ---------------------------------------------------------------
    def _update_vertex(self, u):
        if u != self.goal:
            best = INF
            for v in self._neighbors(u):
                gv = self._g(v)
                if gv == INF:      # edge + INF never wins the min; skip the edge eval
                    continue
                c = self._edge(u, v) + gv
                if c < best:
                    best = c
            self.rhs[u] = best
        self._u_remove(u)
        if self._g(u) != self._rhs(u):
            self._u_insert(u, self._calc_key(u))

    def compute_shortest_path(self):
        while (self._u_top_key() < self._calc_key(self.start)
               or self._rhs(self.start) != self._g(self.start)):
            u = self._u_pop()
            if u is None:
                break
            self.expansions += 1
            k_old = self.U_lookup.get(u)  # already removed; recompute
            k_new = self._calc_key(u)
            if self._g(u) > self._rhs(u):
                self.g[u] = self._rhs(u)
                for s in self._neighbors(u):
                    self._update_vertex(s)
            else:
                self.g[u] = INF
                self._update_vertex(u)
                for s in self._neighbors(u):
                    self._update_vertex(s)

    def get_path(self) -> Optional[list[tuple[int, int]]]:
        if self._g(self.start) == INF:
            return None
        path = [self.start]
        s = self.start
        guard = 0
        while s != self.goal and guard < self.n * self.n:
            guard += 1
            best_v, best_c = None, INF
            for v in self._neighbors(s):
                c = self._edge(s, v) + self._g(v)
                if c < best_c:
                    best_c, best_v = c, v
            if best_v is None or best_c == INF:
                return None
            s = best_v
            path.append(s)
        return path if s == self.goal else None

    # --- dynamic update -----------------------------------------------------
    def update_field(self, new_field: CostField, changed_cells: list[tuple[int, int]]):
        """Apply a new cost field, repairing only vertices around changed cells."""
        self.field = new_field
        self.expansions = 0
        touched = set()
        for cell in changed_cells:
            touched.add(cell)
            for nb in self._neighbors(cell):
                touched.add(nb)
        for u in touched:
            self._update_vertex(u)
        self.compute_shortest_path()

    def move_start(self, new_start: tuple[int, int]):
        """Advance the UAV: update the key modifier and start vertex."""
        self.km += self._heuristic(new_start)
        self.start = new_start


def changed_cells(old: CostField, new: CostField, threshold: float = 0.05) -> list[tuple[int, int]]:
    """Cells whose combined danger changed by more than `threshold`."""
    import numpy as np
    diff = np.abs(new.danger - old.danger)
    rows, cols = np.where(diff > threshold)
    return list(zip(rows.tolist(), cols.tolist()))
