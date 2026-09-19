"""API tests via FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def _token():
    r = client.post("/login", json={"username": "operator", "password": "uav-demo"})
    return r.json()["token"]


def _auth():
    return {"Authorization": f"Bearer {_token()}"}


def test_health_and_scenarios():
    assert client.get("/health").json()["status"] == "ok"
    assert "sam_popup" in client.get("/scenarios").json()["presets"]


def test_login_bad_credentials():
    r = client.post("/login", json={"username": "operator", "password": "wrong"})
    assert r.status_code == 401


def test_mission_requires_auth():
    assert client.post("/mission", json={"scenario_id": "clear"}).status_code == 401


def test_mission_lifecycle():
    h = _auth()
    st = client.post("/mission", json={"scenario_id": "sam_popup"}, headers=h).json()
    mid = st["mission_id"]
    assert st["route"] is not None
    assert len(st["alternatives"]) >= 1
    assert len(st["danger"]) > 0

    st2 = client.post(f"/mission/{mid}/step", headers=h).json()
    assert st2["tick"] == 1
    assert "strategy" in st2["planner_stats"]

    st3 = client.post(f"/mission/{mid}/replan",
                      json={"weights": {"safety": 2.5, "time": 0.1, "fuel": 0.1}},
                      headers=h).json()
    assert st3["route"] is not None


def test_unknown_scenario_rejected():
    r = client.post("/mission", json={"scenario_id": "nope"}, headers=_auth())
    assert r.status_code == 400
