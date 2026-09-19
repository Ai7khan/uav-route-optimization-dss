# UAV Route Optimization DSS

A decision-support system that optimizes UAV routes **in real time** under
**changing weather** and **air-defense (AD) activity**. It plans a route
automatically, scores detection + weather risk per segment, and recommends the
optimal route given operator priorities (safety / speed / fuel) — re-planning
continuously as conditions change.

> Hackathon problem: *"Оптимизация маршрутов БПЛА в условиях изменяющейся
> погодной обстановки и активности ПВО"* (Приложение 2). All data is **simulated**.

![status](https://img.shields.io/badge/tests-passing-brightgreen) ·
Python 3.10 · FastAPI · PyTorch · scikit-learn · Leaflet

---

## Highlights (mapped to the judging criteria)

| Criterion | What we built | Result |
|---|---|---|
| **Prediction accuracy** | Weather nowcaster (PyTorch CNN) + AD-activity predictor (sklearn GBM) | Weather: **-39.4% RMSE** vs persistence @6 min · AD: **+22.3 pts** accuracy vs persistence @6 min, AUC 0.79–0.86 |
| **Route efficiency** | Multi-objective A* + risk cost field | Per-route time / fuel / max & mean detection risk; keeps risk low by detouring around threats |
| **Innovation** | **Adaptive D* Lite** incremental re-planning + ML-driven **pre-emptive** threat avoidance | Continuous replans in **~0 ms** vs A*'s ~155 ms → **10.9× lower** operator-facing latency |
| **UI** | Live operator dashboard (map, danger heatmap, routes, sliders, clock) | Zero-build, runs from one command |
| **Documentation** | This README + [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) + [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) + 21 tests | — |

---

## Quick start

```bash
python -m venv .venv
# Windows:
.venv\Scripts\pip install -r requirements.txt
# macOS/Linux:
# .venv/bin/pip install -r requirements.txt

# 1) Train the ML models (writes data/*.pt, data/*.pkl, data/ml_metrics.json)
.venv\Scripts\python -m backend.ml.train

# 2) Run the app (API + dashboard on one port)
.venv\Scripts\python -m uvicorn backend.api.main:app --port 8017
```

Open **http://localhost:8017** → click **Start mission** → **Play**.
Demo login is automatic (operator / uav-demo).

Run the tests:

```bash
.venv\Scripts\python -m pytest backend/tests -q
```

---

## How it works (60-second version)

```
Simulation → ML forecast → Risk cost field → Adaptive optimizer → Operator UI
 weather      weather CNN    P(detect) +        A* + D* Lite        map, routes,
 + AD sites   AD classifier  weather hazard     multi-objective      risk, controls
```

1. **Simulate** coherent, time-evolving weather (smoothed noise + wind advection)
   and AD sites with intermittent emissions.
2. **Forecast** where the weather and threats *will be* (6 min ahead) with trained models.
3. **Score risk**: detection probability (distance/range/power/altitude, reduced by
   low visibility) + weather hazard (wind/visibility/precip) → a weighted per-cell cost.
4. **Optimize**: A* finds the least-cost route; **D* Lite** repairs it incrementally as
   conditions drift; a full A* replan runs on major discrete events. Operator sliders
   set the safety/speed/fuel trade-off; "safest" and "fastest" alternatives are shown.
5. **Visualize**: danger heatmap, threat rings, risk-colored routes, and a live clock.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for algorithms and design decisions,
and [`PLAN.md`](PLAN.md) for the build plan.

## Security (brief §7)

- JWT operator authentication; no plaintext secrets (PBKDF2-hashed credentials).
- Fernet/AES at-rest encryption helper for stored scenario/route data.
- Secrets read from environment variables (dev fallbacks for the demo).

## Repo layout

```
backend/
  config.py         grid model + constants
  schemas.py        Pydantic data contracts
  sim/              weather, air-defense, UAV, scenarios
  ml/               dataset, weather nowcast (torch), AD predictor (sklearn), forecast, train
  risk/             detection + weather-hazard cost field
  optimizer/        a_star, dstar_lite, route, planner (adaptive)
  api/              FastAPI app, session manager, security
  tests/            21 tests (sim, optimizer, ML, API)
frontend/index.html operator dashboard (Leaflet)
docs/               architecture + demo script
```
