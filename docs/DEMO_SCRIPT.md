# Demo Script (5 minutes)

Goal: show automatic planning, real-time risk-aware re-planning, ML forecasting, and
the operator UI — mapped to the judging criteria.

## Setup (before you present)
```bash
.venv\Scripts\python -m backend.ml.train                 # once; prints the metrics
.venv\Scripts\python -m uvicorn backend.api.main:app --port 8017
```
Open http://localhost:8017. Have the **Model accuracy** card visible (bottom-left).

---

## Beat 1 — The problem (30s)
"UAV operators plan routes against threats that change *in flight* — weather fronts move,
air-defense radars switch on. Static plans get UAVs detected. Our DSS re-optimizes the
route continuously." Point to the map: theatre, start (green), objective (blue).

## Beat 2 — Automatic planning (45s)
Scenario = **SAM pop-up**, **Use ML forecast** ON. Click **Start mission**.
- Three routes appear: **optimal** (risk-colored), **safest** (green dashed), **fastest**
  (amber dashed). Read the **Recommended route** card: ~59 min, **max risk 6%**.
- "The system chose a route that stays out of SAM-Alpha's envelope (the red ring)."

## Beat 3 — Priorities (30s)
Drag **Speed** up / **Safety** down → **Re-plan**. Route straightens, risk rises.
Drag **Safety** back up → **Re-plan**. Route hugs the safe corridor again.
"One control turns the same engine from a fast-but-exposed plan into a safe detour."

## Beat 4 — Real-time re-planning (90s) — the headline
Click **▶ Play**. As the clock advances:
- Around tick 6 **SAM-Delta switches on** (a second red ring blooms with a danger halo).
- The route **immediately re-routes** around it; the UAV ✈️ keeps heading to the objective.
- Point to **Replan: `incremental(D*Lite)` ~0 ms**. "Each continuous update is basically
  free — D* Lite repairs the existing plan instead of recomputing. That's **~11× lower
  latency** than replanning from scratch every tick."
- Because **ML forecast is ON**, notice the route often bends away *before* the SAM is
  fully active — the AD predictor flagged it (**P(soon)** in the Air-defense card).

*Optional contrast:* restart with **forecast OFF** — now the reaction is after the fact,
and you'll see a one-off `full_replan(A*)` banner when the threat appears.

## Beat 5 — Prediction accuracy (30s)
Point to **Model accuracy**:
- Weather nowcast: **39.4% lower RMSE** than persistence at 6 min.
- AD activity: **AUC 0.79**, **+22.3 pts** over persistence at 6 min.
"These aren't heuristics — they're trained models, benchmarked against a fair baseline."

## Beat 5b — Advanced capabilities (60s, optional deep-dive)
- **Terrain masking + 3D:** point to the hillshade (Almaty mountains). Set **Safety** high, Re-plan → the route drops to **200 m nap-of-the-earth** (see "Altitude AGL" in the panel) to hide behind ridges; a fast/high route is exposed. This is real line-of-sight radar masking over a real-relief DEM.
- **Pareto:** click **Compute trade-offs** → the time-vs-detection front appears (green points = low/NOE altitude, red = high). "The operator picks the point, not a fixed preset."
- **Robust:** toggle **Robust** — the route is planned for the worst case of current + forecast, so it stays safe if the forecast is wrong.
- **Mission builder:** click **Start / Goal / +Waypoint** on the map and launch — the route threads the waypoints. "Operators task the system directly."

## Beat 6 — Under the hood + close (45s)
"Simulated weather + air-defense feeds → trained forecasts → a risk cost field combining
detection probability and weather hazard → an adaptive A*/D* Lite optimizer → this
dashboard. Auth is JWT, stored data is AES-encrypted, and it all runs from one command.
21 tests pass, including a proof that D* Lite returns the same optimum as A*."

---

## If asked…
- **"Is D* Lite always faster?"** No — and we don't pretend it is. On a massive
  instantaneous change it loses to A*, so the planner *adaptively* falls back to A* for
  those and uses D* Lite for the common gradual case. That honesty is the design.
- **"Real data?"** The sim is synthetic per the brief; the ML/risk interfaces take real
  weather and ELINT feeds unchanged.
- **"Scale?"** Stateless API, per-session missions, vectorised cost field, O(cells)
  optimizer; larger theatres tile.
