"""Air-defense (SAM/radar) simulation and detection-probability model.

Each site emits within a maximum range. Detection probability for a UAV at a given
cell/altitude is modelled with a smooth sigmoid falloff around the site's effective
range, scaled by emitter power and reduced by low visibility (harder optical/IR cue)
but increased by higher UAV altitude (larger radar line-of-sight & exposure).
"""
from __future__ import annotations

import numpy as np

from backend.config import GRID
from backend.schemas import ADSite, ADType

# Nominal ranges by type (km).
TYPE_RANGE = {
    ADType.short_range: 15.0,
    ADType.medium_range: 40.0,
    ADType.long_range: 120.0,
}


def site_is_active(site: ADSite, tick: int) -> bool:
    if not site.active:
        return False
    if not site.schedule:
        return True
    return any(start <= tick <= end for start, end in site.schedule)


def detection_field(sites: list[ADSite], tick: int, uav_alt_m: float,
                    visibility_km: np.ndarray | None = None) -> np.ndarray:
    """Return an NxN array of detection probability (0..1) over the whole grid.

    Probability is combined across active sites as 1 - prod(1 - p_i).
    """
    n = GRID.n
    combined = np.zeros((n, n))

    # Altitude factor: flying higher => more exposed to radar (0.6 low .. 1.3 high).
    alt_factor = 0.6 + 0.7 * np.clip(uav_alt_m / 3000.0, 0, 1)

    # Precompute cell centre coordinates in km relative to grid origin.
    rows, cols = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")

    for site in sites:
        if not site_is_active(site, tick):
            continue
        srow, scol = GRID.latlon_to_cell(site.lat, site.lon)
        dlat_km = (rows - srow) * GRID.cell_km
        dlon_km = (cols - scol) * GRID.cell_km
        dist = np.sqrt(dlat_km ** 2 + dlon_km ** 2)

        rng_km = site.max_range_km or TYPE_RANGE[site.ad_type]
        # Sigmoid: ~0.9 well inside range, dropping through 0.5 near the edge.
        steepness = 6.0 / rng_km
        p = 1.0 / (1.0 + np.exp(steepness * (dist - rng_km * 0.85)))
        p = p * site.power * alt_factor
        p = np.clip(p, 0, 1)
        combined = 1 - (1 - combined) * (1 - p)

    if visibility_km is not None:
        # Low visibility modestly reduces detection (harder optical/IR tracking).
        vis_factor = 0.75 + 0.25 * np.clip(visibility_km / 10.0, 0, 1)
        combined = combined * vis_factor

    return np.clip(combined, 0, 1)


def threat_rings(sites: list[ADSite], tick: int) -> list[dict]:
    """Danger-zone descriptors for the UI (centre + range in km)."""
    out = []
    for site in sites:
        out.append({
            "id": site.id,
            "lat": site.lat,
            "lon": site.lon,
            "ad_type": site.ad_type.value,
            "range_km": site.max_range_km or TYPE_RANGE[site.ad_type],
            "active": site_is_active(site, tick),
        })
    return out
