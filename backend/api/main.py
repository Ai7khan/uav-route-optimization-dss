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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.api import security, session
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
    start_lat: float = 40.05
    start_lon: float = 44.05
    goal_lat: float = 40.95
    goal_lon: float = 44.95
    alt_m: float = 500.0
    weights: Weights = Weights()
    use_forecast: bool = True


@app.post("/mission")
def create_mission(req: MissionReq, user: str = Depends(require_user)):
    if req.scenario_id not in PRESETS:
        raise HTTPException(400, f"unknown scenario_id; choose from {PRESETS}")
    m = session.create_mission(
        scenario_id=req.scenario_id,
        start=(req.start_lat, req.start_lon),
        goal=(req.goal_lat, req.goal_lon),
        weights=req.weights, alt_m=req.alt_m, use_forecast=req.use_forecast)
    return m.state()


def _mission_or_404(mission_id: str) -> session.Mission:
    m = session.get_mission(mission_id)
    if m is None:
        raise HTTPException(404, "mission not found")
    return m


@app.get("/mission/{mission_id}/state")
def mission_state(mission_id: str, user: str = Depends(require_user)):
    return _mission_or_404(mission_id).state()


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
