"""Global configuration and the geographic grid model.

Everything in the system is defined over a fixed lat/lon bounding box discretised
into an N x N grid. The grid is the shared coordinate frame for weather fields,
air-defense risk, and the route optimizer.
"""
from __future__ import annotations

from dataclasses import dataclass


# --- Geographic domain (fictional area of operations) -----------------------
# Roughly 1 degree of latitude ~= 111 km. We use a 1 deg x 1 deg box so that
# with GRID_N = 100 each cell is ~1.1 km across (fine enough for a demo).
# Theatre: Astana (Nur-Sultan) region, north-central Kazakhstan.
LAT_MIN = 50.7
LAT_MAX = 51.7
LON_MIN = 71.0
LON_MAX = 72.0

GRID_N = 100  # grid resolution (GRID_N x GRID_N cells)

# Approx km per degree at this latitude (used for distances / speeds).
KM_PER_DEG_LAT = 111.0
KM_PER_DEG_LON = 111.0 * 0.6266  # cos(51.2 deg)


@dataclass(frozen=True)
class GridSpec:
    n: int = GRID_N
    lat_min: float = LAT_MIN
    lat_max: float = LAT_MAX
    lon_min: float = LON_MIN
    lon_max: float = LON_MAX

    @property
    def cell_km(self) -> float:
        """Approximate width of one cell in km."""
        return (self.lat_max - self.lat_min) * KM_PER_DEG_LAT / self.n

    def latlon_to_cell(self, lat: float, lon: float) -> tuple[int, int]:
        """Map a lat/lon to (row, col) grid indices (clamped to bounds)."""
        row = int((lat - self.lat_min) / (self.lat_max - self.lat_min) * self.n)
        col = int((lon - self.lon_min) / (self.lon_max - self.lon_min) * self.n)
        row = max(0, min(self.n - 1, row))
        col = max(0, min(self.n - 1, col))
        return row, col

    def cell_to_latlon(self, row: int, col: int) -> tuple[float, float]:
        """Map (row, col) to the lat/lon of the cell centre."""
        lat = self.lat_min + (row + 0.5) / self.n * (self.lat_max - self.lat_min)
        lon = self.lon_min + (col + 0.5) / self.n * (self.lon_max - self.lon_min)
        return lat, lon

    def frac_to_latlon(self, fr_lat: float, fr_lon: float) -> tuple[float, float]:
        """Map fractional position in the box (0..1, 0..1) to lat/lon.

        Keeps scenarios and defaults independent of the theatre's absolute
        coordinates, so moving the bounding box never strands hardcoded points.
        """
        lat = self.lat_min + fr_lat * (self.lat_max - self.lat_min)
        lon = self.lon_min + fr_lon * (self.lon_max - self.lon_min)
        return lat, lon

    def cell_distance_km(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        """Great-circle-ish distance between two cell centres in km (planar approx)."""
        dlat = (a[0] - b[0]) / self.n * (self.lat_max - self.lat_min) * KM_PER_DEG_LAT
        dlon = (a[1] - b[1]) / self.n * (self.lon_max - self.lon_min) * KM_PER_DEG_LON
        return (dlat * dlat + dlon * dlon) ** 0.5


GRID = GridSpec()

# --- Simulation defaults ----------------------------------------------------
TIME_STEP_MIN = 2.0        # minutes of simulated time per tick
UAV_CRUISE_KMH = 120.0     # nominal UAV cruise speed
UAV_ALT_MIN_M = 100.0
UAV_ALT_MAX_M = 3000.0
UAV_FUEL_FULL = 100.0      # arbitrary fuel units (percent)

# --- Default multi-objective weights (operator sliders override these) ------
DEFAULT_WEIGHTS = {
    "safety": 1.0,   # weight on detection/threat risk
    "time": 0.4,     # weight on flight time
    "fuel": 0.3,     # weight on fuel burn
}
