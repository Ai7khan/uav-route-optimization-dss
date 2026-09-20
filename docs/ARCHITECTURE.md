# Architecture & Algorithms

This document describes how the DSS works and why each design choice was made.
It is the "principles of operation" deliverable required by the brief (§8, §9).

## 1. Coordinate model

The theatre is a fixed lat/lon bounding box (50.7–51.7°N, 71–72°E — the Astana
region of Kazakhstan) discretised into a 100×100 grid (~1.1 km per cell). Every layer — weather, risk, the optimizer graph —
shares this grid (`backend/config.py: GridSpec`). Helpers convert lat/lon ↔ cell and
compute planar inter-cell distances in km.

All scenario placements (SAM sites) and the default start/goal are expressed as
**fractions of the box** via `GridSpec.frac_to_latlon`, not absolute coordinates —
so retargeting the theatre to any region is a one-line change of the four box
numbers in `config.py`; everything else follows automatically.

## 2. Simulation (`backend/sim/`)

All data is simulated (real data is prohibited by the brief).

- **Weather** (`weather.py`): each variable (wind u/v, visibility, precip, temp,
  humidity) is a smooth field generated as **value noise** (white noise blurred to a
  chosen spatial scale). Time evolution **advects** the fields along the mean wind with
  bilinear interpolation, plus small stochastic diffusion — so a storm front actually
  moves across the map. Deterministic per seed for reproducible demos.
- **Air defense** (`airdefense.py`): each site has a position, type, max range, emitter
  power, and an on/off schedule (supports intermittent / pop-up threats).
- **UAV** (`uav.py`): ground speed = airspeed ± wind projected on the heading; fuel burn
  scales with time plus a head-wind penalty and a climb penalty.
- **Scenarios** (`scenario.py`): three presets — `clear`, `storm_front` (fast-moving
  precip front), and `sam_popup` (a medium SAM switches on mid-mission astride the
  direct route, leaving an avoidable corridor).

## 3. Detection & risk model (`backend/risk/cost.py`)

**Detection probability** per cell, per active site:

```
p = sigmoid( -k · (distance − 0.85·range) ) · power · altitude_factor
```

- Sigmoid falloff: ≈0.9 well inside range, through 0.5 near the edge.
- `altitude_factor` (0.6 low … 1.3 high): flying higher increases radar exposure.
- Low visibility applies a modest reduction (harder optical/IR tracking).
- Sites combine as `1 − Π(1 − pᵢ)`.

**Weather hazard** per cell: weighted mix of high wind, low visibility, precip (0..1).

**Edge cost** for the optimizer (the multi-objective heart of the system):

```
cost(a→b) = w_safety·(risk² · 50 + hazard · 5)  +  w_time·minutes  +  w_fuel·fuel
```

- `risk²` makes the planner strongly avoid the most dangerous cells while tolerating
  faint exposure.
- `minutes` and `fuel` come from the wind-aware UAV model.
- `w_safety / w_time / w_fuel` are the operator sliders.
- A fast scalar variant (`edge_cost_scalar`) is used in the optimizer hot loops.

## 4. Route optimization (`backend/optimizer/`)

### A* baseline (`astar.py`)
8-connected grid search minimising the edge cost, with an **admissible** heuristic
(best-case time+fuel to goal at cruise+tailwind, ignoring the non-negative risk term),
so it returns the true optimum. Constraints (fuel/time, no-fly cells) are
respected; the operator's altitude is clamped to the UAV band
(`UAV_ALT_MIN_M..UAV_ALT_MAX_M`) in the API and feeds the detection model, so
flying lower trades radar exposure for terrain risk. ~130–160 ms for a
corner-to-corner plan on the 100×100 grid.

### Multi-objective alternatives (`route.py`)
Besides the operator-weighted **optimal** route, we solve two presets — **safest**
(safety-heavy) and **fastest** (time-heavy) — so the operator sees the trade-off space.

### D* Lite incremental replanner (`dstar_lite.py`) — the innovation
D* Lite (Koenig & Likhachev, 2002) plans **backward from the goal** and, when edge
costs change, **repairs only the affected part** of the search tree instead of
recomputing from scratch. Validated to return paths with **identical cost to A***
(`test_dstar_matches_astar_cost`).

*Why it matters:* between 2-minute ticks the weather drifts only slightly, so a repair
touches almost nothing — replanning becomes essentially free (**~0 ms** vs A*'s ~155 ms).

### Adaptive planner (`planner.py`) — the honest engineering
D* Lite's incremental repair is a *loss* when a huge area changes at once (e.g. a SAM
suddenly illuminating thousands of cells), because updating that many vertices is
slower than a fresh A*. So the planner **chooses per tick**:

| Change size | Strategy | Latency |
|---|---|---|
| Gradual drift (< 400 cells) | **D* Lite** incremental repair | ~0 ms |
| Major discrete event (≥ 400 cells) | **A\*** full replan (D* Lite re-warms in background) | ~130 ms |

Measured over a 10-tick mission: **130 ms total operator-facing latency vs 1420 ms**
for A*-every-tick → **10.9× faster**, while both return optimal routes.

## 5. Machine learning (`backend/ml/`)

Two trained models, each benchmarked against a **persistence baseline** (assume nothing
changes) — the fair yardstick for short-term forecasting.

### Weather nowcaster — PyTorch CNN (`weather_nowcast.py`)
A compact 3-layer CNN takes the last 2 weather frames and predicts the field **6 min
ahead** (predicting one 2-min step is trivial — persistence nearly wins — so we forecast
far enough that the front visibly moves). It learns the advection.

- **RMSE 0.029 vs persistence 0.049 → 39.4% improvement.** Trains in ~15 s on CPU.

### AD-activity predictor — scikit-learn GBM (`ad_predictor.py`)
Gradient-boosted classifier predicting whether a site will emit **6 min ahead** from its
recent activity history (raw lags + active fraction + ticks-since-toggle), learning each
site's periodic duty cycle.

| Horizon | Model acc | Persistence acc | Gain | AUC |
|---|---|---|---|---|
| t+1 (2 min) | 0.79 | 0.78 | +1.5 pts | 0.86 |
| t+2 (4 min) | 0.72 | 0.63 | +9.4 pts | 0.80 |
| **t+3 (6 min)** | **0.73** | **0.50** | **+22.3 pts** | **0.79** |

Persistence collapses to a coin flip at 6 min; the model still holds because it has
learned the pattern.

### Forecast → planning link (`forecast.py`, `api/session.py`)
When **"Use ML forecast"** is on, the optimizer plans against the **predicted** weather
field (where the storm will be), and sites the AD model predicts will activate soon are
treated as threats — so the UAV **pre-emptively** routes around a SAM before it emits.
Both models degrade gracefully to physics/persistence baselines if untrained.

## 5a. Terrain masking & 3D altitude planning (`sim/terrain.py`, `optimizer/planner3d.py`)

**Terrain (DEM).** `build_dem()` produces a realistic elevation grid for the Almaty
theatre — the Trans-Ili Alatau range (to ~4600 m) in the south grading to ~700 m plains
in the north, with a carved valley corridor. The interface takes any NxN metre array, so
a real SRTM/GIS raster drops in unchanged.

**Line-of-sight masking.** `viewshed(dem, radar, uav_agl)` marches sampled rays from each
radar to every cell and marks a cell *masked* if terrain rises above the sightline. A
radar on a ridge sees only ~47 % of the map against a UAV at 150 m AGL, but ~97 % at
1500 m — so **flying low behind ridges breaks detection**. Viewsheds are cached (terrain
and radars are static); ~20 ms each.

**3D optimizer.** Nodes are `(row, col, layer)` over 200 / 700 / 1500 m AGL. Each layer
carries its own terrain-masked detection field; horizontal moves stay in a layer, vertical
moves cost a climb/descent. A virtual goal lets the UAV arrive at whatever altitude is
cheapest. `astar3d` finds the optimum; `DStarLite3D` (adjacency kept symmetric, incl. the
goal, so predecessor/successor logic stays valid) is **validated to return the same cost
as A\***, and `AdaptivePlanner3D` gives the same ~0 ms incremental / A*-fallback behaviour
in 3D. Result: safety-heavy routes fly **nap-of-the-earth at 200 m**; time-heavy routes
cruise high.

## 5b. Survival probability, Pareto front & robust planning

**Survival probability.** Per-cell detection risk is treated as a hazard *rate*; route
detection probability = `1 − exp(−rate · ∫ risk dt)`. This discriminates cleanly
(≈0.70 nap-of-earth vs ≈0.89 exposed) where a naive per-cell product saturates near 1.

**Pareto front.** `pareto_front()` sweeps the safety weight and returns the non-dominated
time-vs-detection routes — the operator sees the whole trade-off surface (and each point's
altitude band), not just three presets.

**Robust planning.** In robust mode the planner optimises against the **worst case of
current conditions and the 6-min ML forecast** (element-wise max of detection + hazard)
with a cautious AD-activation threshold, so the route is safe whether the forecast holds
or current conditions persist. Actual current wind is kept for time/fuel accuracy.

## 5c. Operator mission builder (`optimizer/planner3d.py: plan_through`)

The operator clicks the map to place start, objective and ordered **waypoints**;
`plan_through()` chains optimal 3D A* legs through them. With waypoints the system replans
piecewise each tick; without them it uses the adaptive D* Lite engine.

## 6. API & security (`backend/api/`)

FastAPI serves the dashboard and a small REST + WebSocket surface (login, scenarios,
metrics, mission create/step/replan/state). Missions are live server-side sessions that
bundle the scenario clock, forecast, adaptive planner, UAV progress, and emission
history. Security: JWT auth (PBKDF2-hashed credential), Fernet/AES at-rest encryption,
env-var secrets.

## 7. Scalability notes

- Stateless request handlers; mission state is isolated per session (shardable).
- The grid is fixed-size and the cost field is vectorised NumPy; larger theatres tile
  naturally and the optimizer is O(cells).
- The heavy per-tick work (D* Lite repair) is already near-zero; the rare full replan is
  the only ~100 ms cost and is backgroundable.

## 8. Limitations / future work

- Terrain masking / line-of-sight is not modelled (flat-earth detection).
- D* Lite full-solve in pure Python is ~10× slower than A*; a C/Cython inner loop would
  let D* Lite handle large discrete changes too.
- Weather/AD sims are synthetic; the ML interfaces accept real feeds unchanged.
