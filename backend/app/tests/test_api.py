from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_login_and_check_medication():
    assert client.post("/api/auth/login", json={"username": "jrivera", "pin": "0000"}).json()["ok"] is False
    r = client.post("/api/auth/login", json={"username": "jrivera", "pin": "1234"}).json()
    assert r["ok"] and r["user"]["role"] == "nurse"
    res = client.post("/api/patients/p1/medication-check", json={"drugKey": "ibu"})
    assert res.status_code == 200 and isinstance(res.json(), list)


def test_catalog_and_users_hide_pins():
    assert len(client.get("/api/catalog").json()) > 30
    assert all("pin" not in u for u in client.get("/api/auth/users").json())


def test_websocket_sends_snapshot():
    with client.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
        assert len(snap["patients"]) == 11


def test_unbuilt_routes_return_501():
    assert client.post("/api/demo/reset").status_code == 501
