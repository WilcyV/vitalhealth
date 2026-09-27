import os

os.environ.setdefault("VITAL_SIMULATOR", "0")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def signed_in():
    c = TestClient(app)
    c.post("/api/demo/reset")
    assert c.post("/api/auth/login", json={"username": "jrivera", "pin": "1234"}).json()["ok"]
    c.post("/api/demo/reset")
    return c


def test_sbar_requires_login():
    assert TestClient(app).get("/api/patients/p1/sbar").status_code == 401


def test_sbar_and_handoff(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = signed_in()
    r = c.get("/api/patients/p1/sbar").json()
    assert r["source"] == "template" and r["text"].startswith("S: Rosa Martínez")
    h = c.get("/api/patients/p1/handoff").json()
    assert "Rosa Martínez" in h["text"]
    assert c.get("/api/patients/nope/sbar").status_code == 404


def test_sbar_sent_is_logged():
    c = signed_in()
    assert c.post("/api/patients/p1/sbar/sent", json={"text": "S: Rosa Martínez, bed 412A."}).json()["ok"]
    with c.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
    assert any("SBAR sent to provider" in l["text"] and "RN Jamie Rivera" in l["text"] for l in snap["log"])
