"""FastAPI backend for the UAV route-optimization DSS.

Endpoints:
  POST /login            -> JWT for the operator
  GET  /scenarios        -> preset scenario ids
  GET  /metrics          -> trained-model accuracy metrics
  POST /mission          -> create a live mission, returns full state
  POST /mission/{id}/step   -> advance the clock one tick, replan, return state
  POST /mission/{id}/replan -> re-plan now (e.g. after changing weights)
  GET  /mission/{id}/state  -> current state
  WS   /ws/{id}          -> stream state on each tick (send "step" to advance)

Auth is required for mission endpoints (Bearer token). CORS is open for the demo UI.
"""
from __future__ import annotations

import json
import os

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")

from backend.api import security, session
from backend.config import GRID, UAV_ALT_MAX_M, UAV_ALT_MIN_M
from backend.schemas import Weights
from backend.sim.scenario import PRESETS

app = FastAPI(title="UAV Route Optimization DSS", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

bearer = HTTPBearer(auto_error=False)


def require_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    if creds is None or security.decode_token(creds.credentials) is None:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return security.decode_token(creds.credentials)


# --- auth -------------------------------------------------------------------
class LoginReq(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(req: LoginReq):
    if not security.verify_credentials(req.username, req.password):
        raise HTTPException(status_code=401, detail="bad credentials")
    return {"token": security.create_token(req.username), "user": req.username}


# --- info -------------------------------------------------------------------
@app.get("/scenarios")
def scenarios():
    return {"presets": PRESETS}


@app.get("/metrics")
def metrics():
    path = os.path.join("data", "ml_metrics.json")
    if not os.path.exists(path):
        return {"note": "run: python -m backend.ml.train"}
    with open(path) as f:
        return json.load(f)


# --- missions ---------------------------------------------------------------
class MissionReq(BaseModel):
    scenario_id: str = "sam_popup"
    # Defaults null -> filled from the theatre box (near-corner start/goal),
    # so moving the bounding box never leaves the mission outside the map.
    start_lat: float | None = None
    start_lon: float | None = None
    goal_lat: float | None = None
    goal_lon: float | None = None
    alt_m: float = 500.0
    weights: Weights = Weights()
    use_forecast: bool = True
    robust: bool = True
    waypoints: list[tuple[float, float]] = []  # ordered (lat, lon) the route must pass


@app.post("/mission")
def create_mission(req: MissionReq, user: str = Depends(require_user)):
    if req.scenario_id not in PRESETS:
        raise HTTPException(400, f"unknown scenario_id; choose from {PRESETS}")
    dstart = GRID.frac_to_latlon(0.05, 0.05)
    dgoal = GRID.frac_to_latlon(0.95, 0.95)
    start = (req.start_lat if req.start_lat is not None else dstart[0],
             req.start_lon if req.start_lon is not None else dstart[1])
    goal = (req.goal_lat if req.goal_lat is not None else dgoal[0],
            req.goal_lon if req.goal_lon is not None else dgoal[1])
    alt_m = max(UAV_ALT_MIN_M, min(UAV_ALT_MAX_M, req.alt_m))  # enforce altitude band
    m = session.create_mission(
        scenario_id=req.scenario_id, start=start, goal=goal,
        weights=req.weights, alt_m=alt_m, use_forecast=req.use_forecast,
        robust=req.robust, waypoints=req.waypoints)
    return m.state()


def _mission_or_404(mission_id: str) -> session.Mission:
    m = session.get_mission(mission_id)
    if m is None:
        raise HTTPException(404, "mission not found")
    return m


@app.get("/mission/{mission_id}/state")
def mission_state(mission_id: str, user: str = Depends(require_user)):
    return _mission_or_404(mission_id).state()


@app.get("/mission/{mission_id}/pareto")
def mission_pareto(mission_id: str, user: str = Depends(require_user)):
    return {"front": _mission_or_404(mission_id).pareto()}


@app.post("/mission/{mission_id}/step")
def mission_step(mission_id: str, user: str = Depends(require_user)):
    return _mission_or_404(mission_id).step()


class ReplanReq(BaseModel):
    weights: Weights | None = None


@app.post("/mission/{mission_id}/replan")
def mission_replan(mission_id: str, req: ReplanReq, user: str = Depends(require_user)):
    return _mission_or_404(mission_id).replan(req.weights)


# --- websocket (token via query param) --------------------------------------
@app.websocket("/ws/{mission_id}")
async def ws(websocket: WebSocket, mission_id: str, token: str = ""):
    if security.decode_token(token) is None:
        await websocket.close(code=4401)
        return
    m = session.get_mission(mission_id)
    if m is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    await websocket.send_json(m.state())
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "step":
                await websocket.send_json(m.step())
            elif msg == "state":
                await websocket.send_json(m.state())
    except WebSocketDisconnect:
        return


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def ui():
    return FileResponse(FRONTEND)
