"""Live mission session: ties simulation + ML forecast + 3D adaptive planner
together and produces compact state payloads for the operator UI."""
from __future__ import annotations

import uuid

import numpy as np

from backend.config import GRID, TIME_STEP_MIN
from backend.ml import ad_predictor
from backend.ml.forecast import forecast_weather
from backend.optimizer.planner3d import (DEFAULT_AGLS, AdaptivePlanner3D,
                                         CostField3D, plan3d)
from backend.schemas import Route, Weights
from backend.sim.airdefense import site_is_active, threat_rings
from backend.sim.scenario import Scenario, build_scenario

DANGER_DOWN = 50   # danger heatmap resolution sent to UI
WIND_DOWN = 12     # wind arrow grid resolution
TERRAIN_DOWN = 80  # hillshade resolution

ALT_PRESETS = {
    "safest": Weights(safety=2.5, time=0.15, fuel=0.1),
    "fastest": Weights(safety=0.3, time=1.0, fuel=0.2),
}


def _downsample(arr: np.ndarray, size: int) -> list[list[float]]:
    step = max(1, arr.shape[0] // size)
    return arr[::step, ::step].round(3).tolist()


def _hillshade(dem: np.ndarray) -> np.ndarray:
    """Simple shaded relief (illumination from the NW), normalised 0..1."""
    gy, gx = np.gradient(dem)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy) / 30.0)
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    hs = (np.sin(alt) * np.sin(slope) +
          np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip(hs, 0, 1)


class Mission:
    def __init__(self, scenario_id: str, start: tuple[float, float],
                 goal: tuple[float, float], weights: Weights, alt_m: float = 700.0,
                 use_forecast: bool = True):
        self.id = str(uuid.uuid4())[:8]
        self.scenario: Scenario = build_scenario(scenario_id)
        self.scenario_id = scenario_id
        self.start_latlon = start
        self.goal_latlon = goal
        rc = GRID.latlon_to_cell(*start)
        self.start_layer = int(np.argmin([abs(a - alt_m) for a in DEFAULT_AGLS]))
        self.start = (rc[0], rc[1], self.start_layer)     # 3D start node
        self.goal_rc = GRID.latlon_to_cell(*goal)
        self.weights = weights
        self.use_forecast = use_forecast

        self.emission_history = np.zeros((1, len(self.scenario.ad_sites)), dtype=np.int8)
        self._record_emissions()

        self.field = self._build_field()
        self.planner = AdaptivePlanner3D(self.field, self.start, self.goal_rc, weights)
        self.route: Route | None = self.planner.current_route()
        self.alternatives: list[Route] = self._alts()
        self.uav_elapsed_min = 0.0

    # --- field construction -------------------------------------------------
    def _build_field(self) -> CostField3D:
        weather = self.scenario.weather.snapshot()
        if self.use_forecast:
            weather = forecast_weather(weather, steps=3)  # plan against future weather
        sites = self._effective_sites()
        return CostField3D(sites, self.scenario.tick, weather, terrain=self.scenario.terrain)

    def _effective_sites(self):
        """Currently-active sites plus those the AD predictor says will activate
        soon (pre-emptive avoidance in forecast mode)."""
        sites = []
        t = self.emission_history.shape[0] - 1
        for j, s in enumerate(self.scenario.ad_sites):
            active = site_is_active(s, self.scenario.tick)
            if not active and self.use_forecast and t >= 3:
                if ad_predictor.predict_activity(self.emission_history, t, j) >= 0.5:
                    active = True
            s2 = s.model_copy()
            s2.active = active
            sites.append(s2)
        return sites

    def _record_emissions(self):
        row = np.array([[1 if site_is_active(s, self.scenario.tick) else 0
                         for s in self.scenario.ad_sites]], dtype=np.int8)
        if (self.emission_history.shape[0] == 1 and self.emission_history.sum() == 0
                and self.scenario.tick == 0):
            self.emission_history = row
        else:
            self.emission_history = np.vstack([self.emission_history, row])

    def _alts(self) -> list[Route]:
        out = []
        for label, w in ALT_PRESETS.items():
            r = plan3d(self.field, self.start, self.goal_rc, w, label=label)
            if r:
                out.append(r)
        return out

    # --- clock --------------------------------------------------------------
    def step(self) -> dict:
        self.scenario.step()
        self._record_emissions()
        new_field = self._build_field()
        self.route = self.planner.update(new_field)
        self.field = new_field
        self.alternatives = self._alts()
        self.uav_elapsed_min += TIME_STEP_MIN
        return self.state()

    def replan(self, weights: Weights | None = None) -> dict:
        if weights is not None:
            self.weights = weights
        # Rebuild the adaptive planner with current field + weights.
        self.planner = AdaptivePlanner3D(self.field, self.start, self.goal_rc, self.weights)
        self.route = self.planner.current_route()
        self.alternatives = self._alts()
        return self.state()

    # --- UI state -----------------------------------------------------------
    def _uav_position(self):
        if not self.route or not self.route.segments:
            return {"lat": self.start_latlon[0], "lon": self.start_latlon[1], "alt_agl_m": 0}
        segs = self.route.segments
        elapsed = min(self.uav_elapsed_min, segs[-1].cumulative_time_min)
        for i in range(1, len(segs)):
            if segs[i].cumulative_time_min >= elapsed:
                s0, s1 = segs[i - 1], segs[i]
                span = s1.cumulative_time_min - s0.cumulative_time_min
                frac = 0 if span <= 0 else (elapsed - s0.cumulative_time_min) / span
                return {"lat": s0.lat + (s1.lat - s0.lat) * frac,
                        "lon": s0.lon + (s1.lon - s0.lon) * frac,
                        "alt_agl_m": round(s0.alt_agl_m)}
        return {"lat": segs[-1].lat, "lon": segs[-1].lon, "alt_agl_m": round(segs[-1].alt_agl_m)}

    def _ad_predictions(self):
        t = self.emission_history.shape[0] - 1
        out = []
        for j, s in enumerate(self.scenario.ad_sites):
            active = site_is_active(s, self.scenario.tick)
            p_next = (ad_predictor.predict_activity(self.emission_history, t, j)
                      if t >= 3 else float(active))
            out.append({"id": s.id, "active_now": active, "p_active_soon": round(p_next, 2)})
        return out

    def _route_altitudes(self):
        if not self.route:
            return {}
        a = [s.alt_agl_m for s in self.route.segments]
        return {"min": round(min(a)), "max": round(max(a)), "mean": round(sum(a) / len(a))}

    def state(self) -> dict:
        weather = self.scenario.weather.snapshot()
        return {
            "mission_id": self.id,
            "scenario_id": self.scenario_id,
            "tick": self.scenario.tick,
            "time_min": round(self.scenario.time_min, 1),
            "bounds": {"lat_min": GRID.lat_min, "lat_max": GRID.lat_max,
                       "lon_min": GRID.lon_min, "lon_max": GRID.lon_max},
            "danger": _downsample(self.field.danger, DANGER_DOWN),
            "terrain": _downsample(_hillshade(self.scenario.terrain), TERRAIN_DOWN),
            "wind_u": _downsample(weather["wind_u"], WIND_DOWN),
            "wind_v": _downsample(weather["wind_v"], WIND_DOWN),
            "visibility_mean_km": round(float(weather["visibility_km"].mean()), 1),
            "wind_mean_kmh": round(float(np.sqrt(weather["wind_u"]**2 + weather["wind_v"]**2).mean()), 1),
            "threat_rings": threat_rings(self.scenario.ad_sites, self.scenario.tick),
            "ad_predictions": self._ad_predictions(),
            "start": {"lat": self.start_latlon[0], "lon": self.start_latlon[1]},
            "goal": {"lat": self.goal_latlon[0], "lon": self.goal_latlon[1]},
            "uav": self._uav_position(),
            "route": self.route.model_dump() if self.route else None,
            "alternatives": [a.model_dump() for a in self.alternatives],
            "route_altitudes": self._route_altitudes(),
            "altitude_layers": list(DEFAULT_AGLS),
            "planner_stats": self.planner.last_stats,
            "use_forecast": self.use_forecast,
            "weights": self.weights.model_dump(),
        }


# --- in-memory session registry --------------------------------------------
_SESSIONS: dict[str, Mission] = {}


def create_mission(**kwargs) -> Mission:
    m = Mission(**kwargs)
    _SESSIONS[m.id] = m
    return m


def get_mission(mission_id: str) -> Mission | None:
    return _SESSIONS.get(mission_id)
