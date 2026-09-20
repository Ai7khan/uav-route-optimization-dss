"""Terrain model and radar line-of-sight (LOS) masking.

The Almaty theatre has the Trans-Ili Alatau range along its southern edge and
steppe/reservoir plains to the north. We build a deterministic, realistic digital
elevation model (DEM) for the box: high, ridged mountains in the south (low grid
rows) grading to plains in the north, with a winding valley the UAV can exploit.

`viewshed()` computes, for one radar and one UAV flight altitude (AGL), which grid
cells the radar can actually see — terrain between the radar and the UAV blocks the
line of sight. This is the key realism upgrade: routes can hide behind ridges.

The DEM is synthetic (real feeds are unavailable per the brief), but the interface
accepts any NxN elevation array in metres, so a real SRTM/GIS raster drops in
unchanged.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from backend.config import GRID


def _noise(rng, n, sigma):
    f = gaussian_filter(rng.standard_normal((n, n)), sigma=sigma, mode="reflect")
    f -= f.min()
    d = f.max() - f.min()
    return f / d if d > 1e-9 else f


def build_dem(seed: int = 42) -> np.ndarray:
    """Return an NxN elevation grid (metres). Row 0 = south (mountains)."""
    n = GRID.n
    rng = np.random.default_rng(seed)
    rows, cols = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")

    # South-to-north gradient: high in the south (low row index), plains north.
    south = (n - 1 - rows) / (n - 1)              # 1 at south edge, 0 at north
    base = 700 + 3100 * south ** 1.7              # ~700 m plains .. ~3800 m peaks

    # Ridged mountains concentrated in the southern third.
    ridge = np.abs(np.sin(cols / n * np.pi * 4 + _noise(rng, n, 6) * 4))
    ridge_mask = np.clip((south - 0.35) / 0.65, 0, 1)
    mountains = ridge * ridge_mask * 900

    # Rough texture everywhere, stronger in the mountains.
    texture = (_noise(rng, n, 4) - 0.5) * (250 + 500 * ridge_mask)

    dem = base + mountains + texture

    # Carve a winding valley (a usable low corridor through the ridges).
    valley_col = 0.35 + 0.15 * np.sin(rows / n * np.pi * 1.5)
    dist = np.abs(cols / n - valley_col)
    valley = np.exp(-(dist ** 2) / (2 * 0.05 ** 2)) * ridge_mask * 700
    dem = dem - valley

    dem = gaussian_filter(dem, sigma=1.2, mode="reflect")
    return np.clip(dem, 300, None)


def viewshed(dem: np.ndarray, radar_rc: tuple[int, int], uav_agl_m: float,
             radar_mast_m: float = 15.0, samples: int = 48,
             clearance_m: float = 10.0) -> np.ndarray:
    """Boolean NxN mask: True where a radar at `radar_rc` has line of sight to a
    UAV flying `uav_agl_m` above ground level, given the DEM.

    Straight-line LOS (earth curvature negligible at these ranges). Terrain rising
    above the sightline anywhere between radar and target blocks detection.
    """
    n = dem.shape[0]
    rr, rc = radar_rc
    radar_h = dem[rr, rc] + radar_mast_m
    uav_h = dem + uav_agl_m                                   # (n,n) target heights
    rows, cols = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")

    blocked = np.zeros((n, n), dtype=bool)
    for t in np.linspace(0.04, 0.96, samples):               # intermediate points
        pr = rr + t * (rows - rr)
        pc = rc + t * (cols - rc)
        terr_t = map_coordinates(dem, [pr, pc], order=1, mode="nearest")
        sightline_t = radar_h + t * (uav_h - radar_h)
        blocked |= terr_t > sightline_t + clearance_m
    vis = ~blocked
    vis[rr, rc] = True
    return vis
