"""Core tests: simulation, risk field, and optimizer correctness."""
import numpy as np

from backend.config import GRID
from backend.sim.scenario import build_scenario, PRESETS
from backend.sim.airdefense import detection_field, site_is_active
from backend.risk.cost import CostField, weather_hazard
from backend.optimizer.astar import astar
from backend.optimizer.route import path_to_route, plan_alternatives
from backend.optimizer.dstar_lite import DStarLite, changed_cells
from backend.optimizer.planner import AdaptivePlanner
from backend.schemas import Weights

START = GRID.latlon_to_cell(*GRID.frac_to_latlon(0.05, 0.05))
GOAL = GRID.latlon_to_cell(*GRID.frac_to_latlon(0.95, 0.95))
W = Weights()


def _field(sid, tick=0, alt=500.0):
    sc = build_scenario(sid)
    for _ in range(tick):
        sc.step()
    return sc, CostField(sc.ad_sites, sc.tick, alt, sc.weather.snapshot())


def test_grid_roundtrip():
    for fr in [(0.05, 0.05), (0.5, 0.5), (0.95, 0.95)]:
        lat, lon = GRID.frac_to_latlon(*fr)
        r, c = GRID.latlon_to_cell(lat, lon)
        blat, blon = GRID.cell_to_latlon(r, c)
        assert abs(blat - lat) < GRID.cell_km / 111 + 1e-6
        assert abs(blon - lon) < GRID.cell_km / 80 + 1e-6


def test_presets_build():
    for sid in PRESETS:
        sc = build_scenario(sid)
        assert sc.ad_sites and 0 <= sc.tick


def test_detection_field_bounds():
    _, f = _field("clear")
    assert f.detect.shape == (GRID.n, GRID.n)
    assert f.detect.min() >= 0 and f.detect.max() <= 1


def test_sam_popup_activates():
    sc = build_scenario("sam_popup")
    delta = next(s for s in sc.ad_sites if s.id == "SAM-Delta")
    assert not site_is_active(delta, 0)
    assert site_is_active(delta, 8)


def test_weather_hazard_bounds():
    _, f = _field("storm_front")
    h = weather_hazard(f.weather)
    assert h.min() >= 0 and h.max() <= 1


def test_astar_reaches_goal():
    _, f = _field("clear")
    path = astar(f, START, GOAL, W)
    assert path is not None and path[0] == START and path[-1] == GOAL


def test_dstar_matches_astar_cost():
    """D* Lite must return an optimal path with the same cost as A*."""
    _, f = _field("sam_popup")
    a = path_to_route(f, astar(f, START, GOAL, W), W)
    d = DStarLite(f, START, GOAL, W)
    d.compute_shortest_path()
    dr = path_to_route(f, d.get_path(), W)
    assert abs(a.total_cost - dr.total_cost) / a.total_cost < 0.01


def test_reroute_keeps_risk_low_after_popup():
    """After the SAM pops up, the optimal route should still avoid high risk."""
    _, f0 = _field("sam_popup", tick=0)
    _, f8 = _field("sam_popup", tick=8)
    r0 = path_to_route(f0, astar(f0, START, GOAL, W), W)
    r8 = path_to_route(f8, astar(f8, START, GOAL, W), W)
    assert r0.max_risk < 0.3 and r8.max_risk < 0.3
    # It should cost more (detour) after the threat appears.
    assert r8.total_time_min >= r0.total_time_min - 1


def test_alternatives_distinct():
    _, f = _field("clear")
    routes = plan_alternatives(f, START, GOAL, W)
    labels = {r.label for r in routes}
    assert {"optimal", "safest", "fastest"} <= labels


def test_adaptive_planner_incremental_is_cheap():
    sc = build_scenario("sam_popup")
    f0 = CostField(sc.ad_sites, sc.tick, 500.0, sc.weather.snapshot())
    p = AdaptivePlanner(f0, START, GOAL, W)
    sc.step()
    f1 = CostField(sc.ad_sites, sc.tick, 500.0, sc.weather.snapshot())
    r = p.update(f1)
    assert r is not None
    assert p.last_stats["strategy"].startswith("incremental")


def test_changed_cells_detects_popup():
    sc = build_scenario("sam_popup")
    f_before = CostField(sc.ad_sites, sc.tick, 500.0, sc.weather.snapshot())
    for _ in range(8):
        sc.step()
    f_after = CostField(sc.ad_sites, sc.tick, 500.0, sc.weather.snapshot())
    cc = changed_cells(f_before, f_after)
    assert len(cc) > 100  # the SAM footprint
