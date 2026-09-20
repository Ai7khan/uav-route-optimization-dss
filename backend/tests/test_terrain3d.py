"""Tests for terrain masking and 3D altitude-aware planning."""
import numpy as np

from backend.config import GRID
from backend.sim.terrain import build_dem, viewshed
from backend.sim.scenario import build_scenario
from backend.optimizer.planner3d import (CostField3D, astar3d, path_to_route3d,
                                         DStarLite3D, plan3d, DEFAULT_AGLS, GOAL_LAYER)
from backend.schemas import Weights

W = Weights()
START = GRID.latlon_to_cell(*GRID.frac_to_latlon(0.05, 0.05)) + (1,)
GOAL_RC = GRID.latlon_to_cell(*GRID.frac_to_latlon(0.95, 0.95))


def test_dem_shape_and_relief():
    dem = build_dem()
    assert dem.shape == (GRID.n, GRID.n)
    # south edge (mountains) higher than north edge (plains)
    assert dem[0].mean() > dem[-1].mean() + 1000


def test_viewshed_lower_is_more_masked():
    dem = build_dem()
    radar = (20, 50)
    low = viewshed(dem, radar, uav_agl_m=150).mean()
    high = viewshed(dem, radar, uav_agl_m=1500).mean()
    assert low < high  # flying lower => less visible to radar


def test_terrain_masks_detection():
    from backend.sim.airdefense import detection_field
    sc = build_scenario("clear")
    w = sc.weather.snapshot()
    no_terrain = detection_field(sc.ad_sites, 0, 300, w["visibility_km"]).mean()
    with_terrain = detection_field(sc.ad_sites, 0, 300, w["visibility_km"],
                                   terrain=sc.terrain).mean()
    assert with_terrain <= no_terrain  # terrain can only block, not add, detection


def _field(sid, tick=0):
    sc = build_scenario(sid)
    for _ in range(tick):
        sc.step()
    return CostField3D(sc.ad_sites, sc.tick, sc.weather.snapshot(), terrain=sc.terrain)


def test_astar3d_reaches_goal():
    f = _field("clear")
    path = astar3d(f, START, GOAL_RC, W)
    assert path is not None
    assert path[-1] == (GOAL_RC[0], GOAL_RC[1], GOAL_LAYER)


def test_dstar3d_matches_astar3d_cost():
    f = _field("sam_popup", tick=8)
    ar = path_to_route3d(f, astar3d(f, START, GOAL_RC, W), W)
    d = DStarLite3D(f, START, GOAL_RC, W)
    d.compute_shortest_path()
    dr = path_to_route3d(f, d.get_path(), W)
    assert abs(ar.total_cost - dr.total_cost) / max(ar.total_cost, 1e-9) < 0.01


def test_altitude_is_used_by_safest():
    """Safety-heavy weighting should exploit low nap-of-earth altitude."""
    f = _field("sam_popup", tick=8)
    safest = plan3d(f, START, GOAL_RC, Weights(safety=2.5, time=0.15, fuel=0.1))
    alts = {round(s.alt_agl_m) for s in safest.segments}
    assert min(alts) == DEFAULT_AGLS[0]  # uses the lowest layer somewhere
