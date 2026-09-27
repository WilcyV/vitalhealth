"""API tests (Person 1). The Vital engine may still be a stub, so tests that need an alert
patch `evaluate` with a fake rule; everything else runs against the real fixtures."""
import os

os.environ.setdefault("VITAL_TICK_SECONDS", "0")  # no background simulator during tests

import pytest
from fastapi.testclient import TestClient

import app.state as state_mod
from app.main import SESSIONS, app
from app.state import STATE
from vital.models import Alert


@pytest.fixture(autouse=True)
def fresh():
    SESSIONS.clear()
    STATE.reset()
    yield
    SESSIONS.clear()


def as_user(username: str | None) -> TestClient:
    """A client with its own cookie jar, signed in as `username` (None = signed out)."""
    c = TestClient(app)
    if username:
        assert c.post("/api/auth/login", json={"username": username, "pin": "1234"}).json()["ok"]
    return c


def fake_alert(monkeypatch, pid="p1", mid="m1", sev="crit", aid="k:p1"):
    def evaluate(p, sim):
        if p.id != pid:
            return []
        return [Alert(id=aid, pid=pid, sev=sev, meds=[mid], trigger="lab", title="Potassium 5.8 on lisinopril",
                      why="test", data=[], action="Hold")]
    monkeypatch.setattr(state_mod, "evaluate", evaluate)
    STATE.run_rules()


def med(pid, mid):
    return STATE.med(pid, mid)


def input_for(**over):
    body = {"name": "Test Patient", "age": 50, "sex": "F", "wt": 70, "bed": "430B", "dx": "Pneumonia",
            "conditions": [], "otherConds": [], "allergies": []}
    body.update(over)
    return body


# ---- session & basics -------------------------------------------------------------------------------
def test_health():
    assert TestClient(app).get("/health").json() == {"ok": True}


def test_login_and_check_medication():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": "jrivera", "pin": "0000"}).json()["ok"] is False
    r = c.post("/api/auth/login", json={"username": "jrivera", "pin": "1234"}).json()
    assert r["ok"] and r["user"]["role"] == "nurse"
    res = c.post("/api/patients/p1/medication-check", json={"drugKey": "ibu"})
    assert res.status_code == 200 and isinstance(res.json(), list)
    assert c.post("/api/patients/p1/medication-check", json={"drugKey": "nope"}).json() == []


def test_catalog_and_users_hide_pins():
    c = TestClient(app)
    assert len(c.get("/api/catalog").json()) > 30
    assert all("pin" not in u for u in c.get("/api/auth/users").json())


def test_logout_ends_session():
    c = as_user("jrivera")
    assert c.post("/api/auth/logout").json() == {"ok": True}
    assert c.post("/api/patients/p1/medications/m1/hold", json={"reason": "x"}).status_code == 401


def test_actions_need_a_session():
    c = as_user(None)
    assert c.post("/api/patients/p1/medications/m1/give", json={}).status_code == 401
    assert c.get("/api/patients/p1/medications/m1/administration-check").status_code == 401


def test_permissions_return_403_with_reason():
    r = as_user("akim").post("/api/patients/p1/medications/m1/give", json={})  # pharmacist
    assert r.status_code == 403
    assert r.json() == {"ok": False, "error": "Only nurses and charge nurses can do this."}
    assert as_user("jrivera").post("/api/patients", json=input_for()).status_code == 403  # nurse can't admit
    assert as_user("jrivera").post("/api/patients/p1/medications", json={"drugKey": "apap"}).status_code == 403


def test_websocket_sends_snapshot_and_updates():
    c = as_user("jrivera")
    with c.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
        assert len(snap["patients"]) == 11 and len(snap["scenarios"]) == 10
        c.post("/api/patients/p1/medications/m2/hold", json={"reason": "HR 52"})
        snap = ws.receive_json()
        assert next(m for m in snap["patients"][0]["meds"] if m["id"] == "m2")["status"] == "held"
        assert snap["log"][0]["text"] == "412A Rosa Martínez · Held Metoprolol succinate. Reason: HR 52 — RN Jamie Rivera"


# ---- administration ---------------------------------------------------------------------------------
def test_give_simple_medication():
    c = as_user("jrivera")
    assert c.post("/api/patients/p1/medications/m3/give", json={}).json() == {"ok": True}
    assert med("p1", "m3").status == "given"
    assert "All checks passed" in STATE.log[-1]["text"]
    again = c.post("/api/patients/p1/medications/m3/give", json={}).json()
    assert again == {"ok": False, "error": "This order is no longer active."}


def test_active_alert_requires_override_reason(monkeypatch):
    fake_alert(monkeypatch)
    c = as_user("jrivera")
    chk = c.get("/api/patients/p1/medications/m1/administration-check").json()
    assert [a["id"] for a in chk["blocking"]] == ["k:p1"] and chk["highAlert"] is False
    r = c.post("/api/patients/p1/medications/m1/give", json={}).json()
    assert r["ok"] is False and "reason" in r["error"]
    assert c.post("/api/patients/p1/medications/m1/give", json={"overrideReason": "   "}).json()["ok"] is False
    assert c.post("/api/patients/p1/medications/m1/give", json={"overrideReason": "Provider aware"}).json()["ok"]
    assert STATE.overrides["k:p1"] == "Provider aware"
    assert STATE.snapshot().alerts == []


def test_high_alert_cosign_rules():
    c = as_user("jrivera")
    url = "/api/patients/p2/medications/m2/give"  # insulin lispro, expected 2 units
    chk = c.get("/api/patients/p2/medications/m2/administration-check").json()
    assert chk["highAlert"] and chk["expected"]["n"] == 2
    assert "co-sign" in c.post(url, json={}).json()["error"]
    assert "must be a nurse" in c.post(url, json={"cosigner": "akim", "cosignPin": "1234", "cosignDose": 2}).json()["error"]
    assert "different nurse" in c.post(url, json={"cosigner": "jrivera", "cosignPin": "1234", "cosignDose": 2}).json()["error"]
    assert "PIN doesn’t match" in c.post(url, json={"cosigner": "mchen", "cosignPin": "9999", "cosignDose": 2}).json()["error"]
    bad = c.post(url, json={"cosigner": "mchen", "cosignPin": "1234", "cosignDose": 4}).json()
    assert bad["ok"] is False and "Doses don't match" in bad["error"] and "calculated dose is 2 units" in bad["error"]
    assert STATE.log[-1]["kind"] == "crit" and med("p2", "m2").status == "due"
    assert c.post(url, json={"cosigner": "mchen", "cosignPin": "1234", "cosignDose": 2}).json() == {"ok": True}
    m = med("p2", "m2")
    assert m.status == "given" and m.cosign == "RN Maria Chen"


def test_hold_and_discontinue():
    nurse, provider = as_user("jrivera"), as_user("spatel")
    assert nurse.post("/api/patients/p1/medications/m2/hold", json={"reason": " "}).json()["ok"] is False
    assert nurse.post("/api/patients/p1/medications/m2/hold", json={"reason": "HR 52"}).json()["ok"]
    assert med("p1", "m2").status == "held"
    assert nurse.delete("/api/patients/p1/medications/m4").status_code == 403
    assert provider.delete("/api/patients/p1/medications/m4").json()["ok"]
    assert med("p1", "m4") is None


def test_alert_hold_and_acknowledge(monkeypatch):
    fake_alert(monkeypatch, sev="warn")
    nurse = as_user("jrivera")
    assert as_user("akim").post("/api/alerts/k:p1/acknowledge").json()["ok"]  # pharmacist may acknowledge
    assert STATE.snapshot().alerts == []  # acknowledged warning is resolved
    assert nurse.post("/api/alerts/k%3Ap1/hold").json()["ok"]
    assert med("p1", "m1").status == "held"
    assert nurse.post("/api/alerts/missing/hold").json()["ok"] is False


def test_complete_task_marks_late():
    c = as_user("jrivera")
    STATE.sim = 60
    assert c.post("/api/patients/p10/tasks/t1/complete").json()["ok"]
    t = STATE.by_id("p10").tasks[0]
    assert t.done and t.at == 60
    assert "(30 min late)" in STATE.log[-1]["text"] and STATE.log[-1]["kind"] == "warn"


# ---- orders -----------------------------------------------------------------------------------------
def test_order_medication(monkeypatch):
    c = as_user("spatel")
    r = c.post("/api/patients/p1/medications", json={"drugKey": "apap"}).json()
    assert r["ok"] and r["id"].startswith("n")
    new = med("p1", r["id"])
    assert new.catKey == "apap" and new.isNew and "Passed Vital check" in STATE.log[-1]["text"]

    from vital.models import CheckIssue
    monkeypatch.setattr(state_mod, "check_new_medication",
                        lambda p, d: [CheckIssue(sev="crit", type="allergy", title="Allergy", why="", action="")])
    blocked = c.post("/api/patients/p1/medications", json={"drugKey": "ibu"}).json()
    assert blocked == {"ok": False, "error": "Critical issues found. A reason is required to order anyway."}
    assert c.post("/api/patients/p1/medications", json={"drugKey": "ibu", "overrideReason": "Benefit outweighs"}).json()["ok"]
    assert STATE.log[-1]["kind"] == "warn"


def test_alternatives_same_group_max_three():
    alts = as_user("spatel").post("/api/patients/p1/medication-alternatives", json={"drugKey": "ibu"}).json()
    assert 0 < len(alts) <= 3
    assert all(a["drug"]["group"] == "pain" and a["drug"]["key"] != "ibu" for a in alts)


# ---- patients ---------------------------------------------------------------------------------------
def test_admit_edit_discharge():
    charge = as_user("sreyes")
    r = charge.post("/api/patients", json=input_for(allergies=[{"agent": "Penicillin", "cls": "penicillin", "rxn": "Hives"}])).json()
    assert r["ok"] and r["id"] == "p100"
    p = STATE.by_id("p100")
    assert p.bed == "430B" and len(p.hist["sbp"]) == 24 and "allergies: Penicillin" in STATE.log[-1]["text"]

    assert charge.post("/api/patients", json=input_for(bed="412A")).json()["error"].startswith("Bed 412A is taken by")
    assert "room number" in charge.post("/api/patients", json=input_for(bed="99")).json()["error"]
    assert "age" in charge.post("/api/patients", json=input_for(age=130)).json()["error"]
    assert "weight" in charge.post("/api/patients", json=input_for(wt=0)).json()["error"]
    assert "name" in charge.post("/api/patients", json=input_for(name="  ")).json()["error"]
    assert "allergen" in charge.post("/api/patients", json=input_for(bed="428A", allergies=[{"agent": "", "cls": "other", "rxn": ""}])).json()["error"]

    nurse = as_user("jrivera")
    assert nurse.put("/api/patients/p100", json=input_for(bed="430A", wt=72)).json()["ok"]
    assert "weight, bed 430B → 430A" in STATE.log[-1]["text"]
    assert nurse.put("/api/patients/p100", json=input_for(bed="430A")).json()["ok"]  # own bed isn't a clash

    assert nurse.post("/api/patients/p100/discharge").status_code == 403
    assert charge.post("/api/patients/p100/discharge").json()["ok"]
    assert STATE.by_id("p100") is None and STATE.discharged[0]["bed"] == "430A"


def test_suggest_bed_is_free():
    c = TestClient(app)
    taken = {p.bed for p in STATE.patients}
    for _ in range(10):
        assert c.get("/api/beds/suggest").json()["bed"] not in taken
    own = STATE.by_id("p1").bed
    beds = {c.get("/api/beds/suggest?except=p1").json()["bed"] for _ in range(60)}
    assert beds <= (set(STATE.beds) - taken) | {own}


def test_drug_info():
    c = TestClient(app)
    assert c.get("/api/drug-info?name=zzz").json() is None


# ---- demo controls & simulator ----------------------------------------------------------------------
def test_scenario_runs_and_undoes():
    c = TestClient(app)
    before = STATE.by_id("p1").labs.k.v
    assert c.post("/api/demo/scenarios/k").json()["ok"]
    assert STATE.by_id("p1").labs.k.v == 5.8 and "k" in STATE.used
    assert c.post("/api/demo/scenarios/k").json()["ok"]  # second tap undoes
    assert STATE.by_id("p1").labs.k.v == before and "k" not in STATE.used

    n = len(STATE.by_id("p3").meds)
    c.post("/api/demo/scenarios/nsaid")
    assert len(STATE.by_id("p3").meds) == n + 1
    c.post("/api/demo/scenarios/nsaid")
    assert len(STATE.by_id("p3").meds) == n
    assert c.post("/api/demo/scenarios/nope").json()["ok"] is False


def test_skip_pause_reset():
    c = TestClient(app)
    assert c.post("/api/demo/skip", json={"minutes": 30}).json()["ok"]
    assert STATE.sim == 30
    assert c.post("/api/demo/pause", json={"paused": True}).json()["ok"] and STATE.paused
    c.post("/api/demo/reset")
    assert STATE.sim == 0 and not STATE.paused and len(STATE.patients) == 11


def test_tick_moves_vitals_toward_target():
    p = STATE.by_id("p1")
    p.target.sbp = p.vit.sbp - 30
    start = p.vit.sbp
    for _ in range(3):
        STATE.tick()
    assert p.vit.sbp < start and STATE.sim == 1.5 and len(p.hist["sbp"]) <= 30


def test_new_alerts_are_logged_once(monkeypatch):
    fake_alert(monkeypatch)
    before = len([e for e in STATE.log if "Potassium 5.8" in e["text"]])
    STATE.run_rules()
    STATE.run_rules()
    after = len([e for e in STATE.log if "Potassium 5.8" in e["text"]])
    assert after == before  # already seen during fake_alert's first run
    assert before == 1
