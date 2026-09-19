# Implementation Plan — UAV Route Optimization DSS

**Hackathon problem (Приложение 2, §8):** A Decision Support System that optimizes UAV/drone
routes in **real time** under **changing weather** and **air-defense (AD / ПВО) activity**.
It must plan a route automatically, score detection + weather risk per route, and recommend the
optimal one given operator priorities (safety vs. speed vs. fuel). All data is **simulated**
(no real data allowed).

## Team decisions
- **Frontend:** decide later — scaffold backend first, choose React+Leaflet vs. Streamlit once core logic works.
- **ML:** real trained models (weather nowcast + AD-activity predictor) with reported accuracy metrics.
- **Deliverable format:** this file (`PLAN.md`) in the repo.

---

## Requirements traceability

| Brief area | Requirement | Phase |
|---|---|---|
| Data ingest | Weather (temp, humidity, wind, visibility), AD sites (location, type, emission intensity), UAV telemetry (alt, speed, coords) — simulated | 1 |
| Analysis | ML forecast of weather + AD activity / pattern detection | 2 |
| Planning | Route optimizer under constraints (flight time, fuel, altitude), minimizing risk | 4 |
| Visualization | Map with danger zones, alternative routes, per-segment risk | 5 |
| UI | Operator-friendly, allows manual corrections | 5 |
| Non-functional | Data encryption, scalability | 6 |
| Deliverables | Working demo + presentation + source code | 7 |

**Judging criteria:** prediction accuracy · route efficiency (time/fuel/detection risk) ·
innovation · UI · documentation.

**Differentiator / innovation hook:** *dynamic re-planning*. When weather or a SAM changes
mid-flight, the route incrementally re-optimizes (D* Lite) instead of recomputing statically.
This is the winning demo moment and covers "real-time / dynamically changing conditions."

---

## Architecture

```
 OPERATOR DASHBOARD (map, danger zones, routes, per-segment risk,
                     priority sliders, waypoints, "Re-plan", scenario clock)
        │ REST + WebSocket
 BACKEND API (FastAPI)
   Sim/scenario engine  →  ML forecast (weather + AD)  →  Risk/cost field
                                                             │
                                              Route optimizer (A* + D* Lite,
                                              multi-objective weights)
   Security: TLS · JWT auth · AES/Fernet encryption of scenario data
```

## Recommended stack
- **Backend:** Python + FastAPI, NumPy, (optional) networkx
- **ML:** PyTorch (ConvLSTM/LSTM weather nowcast) + scikit-learn (AD-activity classifier)
- **Optimizer:** custom A* (static) + D* Lite (incremental replan)
- **Sim:** NumPy + Perlin/simplex noise for coherent, time-evolving weather fields
- **Frontend:** React + Leaflet (polished) or Streamlit + pydeck/folium (fast) — decide later
- **Packaging:** Docker Compose; cloud deploy optional

---

## Repo structure
```
Eighth_01_project/
├── backend/
│   ├── sim/          # weather, air-defense, uav models + preset scenarios
│   ├── ml/           # forecasting models + training scripts + saved weights
│   ├── risk/         # detection probability + weather hazard → cost field
│   ├── optimizer/    # a_star.py, d_star_lite.py, multiobjective.py
│   ├── api/          # FastAPI routes, websocket, auth, crypto
│   └── tests/
├── frontend/         # chosen UI (React or Streamlit)
├── data/             # generated scenarios (encrypted at rest)
├── docs/             # architecture, algorithms, metrics for the pitch
├── docker-compose.yml
└── README.md
```

---

## Phase-by-phase plan (~2-day hackathon, small team)

### Phase 0 — Setup & data contracts (1–2 hrs)
- [ ] Repo scaffold + Docker Compose + README.
- [ ] **Freeze JSON schemas first:** weather grid, AD sites, UAV state, route response. Everything depends on these — agree before splitting up.
- [ ] Define grid model: fixed lat-lon bounding box → NxN grid (e.g. 100×100), each cell holds weather + risk values.

### Phase 1 — Simulation / scenario engine (½ day) — *Person A*
- [ ] Weather field generator: Perlin-noise fields for wind vector, visibility, precip, temp, humidity; advect over time steps so weather truly changes.
- [ ] Air-defense model: N radar/SAM sites `{position, type, max_range, power, on/off schedule}`; intermittent emissions (predictable but dynamic).
- [ ] UAV model: state `{lat, lon, alt, speed, fuel}` + kinematics + fuel burn = f(speed, headwind, climb).
- [ ] 2–3 preset scenarios: clear / storm-front-moving-in / SAM-activates-mid-route (controllable demo).

### Phase 2 — ML forecasting & pattern analysis (½–1 day) — *Person B*
- [ ] Weather nowcast: small ConvLSTM (or per-cell LSTM) predicting weather 1–5 steps ahead. Log **RMSE/MAE**.
- [ ] AD-activity predictor: features (recent emission pattern, time, location) → P(active)/threat intensity. Report accuracy/AUC.
- [ ] Wrap both as `/forecast` functions returning grids for the risk layer.
- [ ] **Fallback stub:** physics/heuristic forecast so downstream isn't blocked if ML slips (build in Phase 1).

### Phase 3 — Risk model & cost field (½ day) — *Person B/C*
- [ ] Detection probability per cell: `P_detect = f(distance_to_radar, radar_range, power, uav_altitude)` — sigmoid falloff; combine over active radars.
- [ ] Weather hazard per cell: penalize high wind, low visibility, precip.
- [ ] Combined edge cost: `cost = w_safety·risk + w_time·time(headwind) + w_fuel·fuel`, weights from operator sliders.

### Phase 4 — Route optimizer (½–1 day) — *Person C* (differentiator)
- [ ] A* baseline: shortest weighted path start→goal, respecting constraints (max fuel/time, altitude band, no-fly cells).
- [ ] Multi-objective: expose safety/speed/fuel weights; optionally compute 2–3 Pareto alternatives.
- [ ] **D* Lite dynamic replan:** incrementally repair path when weather/AD changes as the clock advances.
- [ ] Per-route output: total time, fuel, max & mean detection risk, per-segment risk for coloring.

### Phase 5 — Visualization & operator UI (1 day) — *Person D*
- [ ] Map: base terrain, danger zones (radar-range circles / risk heatmap), weather overlay (wind arrows, visibility shading).
- [ ] Recommended route + 1–2 alternatives; segments colored by risk (green→red).
- [ ] Controls: set start/goal + waypoints, priority sliders, "Re-plan", play/pause scenario clock.
- [ ] Info panel: route metrics (time/fuel/risk), forecast confidence, alerts ("SAM-3 activated, rerouting").
- [ ] Live updates over WebSocket as the scenario ticks.

### Phase 6 — Security & non-functional (2–3 hrs)
- [ ] Encrypt stored scenario/route data at rest (Fernet/AES); serve over TLS.
- [ ] Simple JWT login (operator role).
- [ ] Document scalability design (stateless API, grid tiling).

### Phase 7 — Docs, demo & pitch (½ day)
- [ ] Technical doc: architecture, algorithms (A*/D* Lite, ML models), metrics achieved.
- [ ] Scripted demo: launch scenario → optimal route → advance clock → storm/SAM appears → auto re-plan → operator tweaks sliders.
- [ ] Presentation deck: problem → approach → innovation → results/metrics → next steps.

---

## Scope guardrails
- **MVP first (build in this order):** sim engine → static risk field → A* route → map with danger zones + route + metrics. This alone satisfies §5.
- **Winning stretch:** trained ML forecasts w/ accuracy, D* Lite dynamic replan, multi-route Pareto, live WebSocket demo.
- **Skip / mock:** real QGIS/GIS integration, real map-tile auth, heavy cloud infra. Judges reward the working demo + innovation, not infrastructure.

## Criteria → phase map
- Prediction accuracy → Phase 2 (report RMSE/AUC)
- Route efficiency → Phase 4 (time/fuel/risk metrics)
- Innovation → Phase 4 (D* Lite dynamic replan + multi-objective)
- UI → Phase 5
- Documentation → Phase 7
