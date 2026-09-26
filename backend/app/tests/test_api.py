"""API tests (Person 1). Run:  pytest app

Each test starts from a fresh unit (STATE.reset()). One TestClient per signed-in user, so
each keeps its own session cookie. The simulator is off in tests; call STATE.tick() instead.
"""
import os

os.environ.setdefault("VITAL_SIMULATOR", "0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.state as state_mod  # noqa: E402
from app.main import app  # noqa: E402
from app.state import STATE  # noqa: E402
from vital.models import Alert  # noqa: E402

anon = TestClient(app)


def signed_in(username: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "pin": "1234"}).json()["ok"]
    return c


@pytest.fixture(autouse=True)
def fresh_unit():
    STATE.reset()
    yield


@pytest.fixture
def nurse():
    return signed_in("jrivera")


@pytest.fixture
def provider():
    return signed_in("spatel")


@pytest.fixture
def charge():
    return signed_in("sreyes")


def med(pid, mid):
    return STATE.med(pid, mid)


def last_log():
    return STATE.log[-1]["text"]


# ---- auth & permissions ----------------------------------------------------------------
def test_health():
    assert anon.get("/health").json() == {"ok": True}


def test_login_and_check_medication():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": "jrivera", "pin": "0000"}).json()["ok"] is False
    r = c.post("/api/auth/login", json={"username": "jrivera", "pin": "1234"}).json()
    assert r["ok"] and r["user"]["role"] == "nurse"
    res = c.post("/api/patients/p1/medication-check", json={"drugKey": "ibu"})
    assert res.status_code == 200 and isinstance(res.json(), list)


def test_catalog_and_users_hide_pins():
    assert len(anon.get("/api/catalog").json()) > 30
    assert all("pin" not in u for u in anon.get("/api/auth/users").json())


def test_actions_need_a_session():
    assert anon.post("/api/patients/p1/medications/m1/give", json={}).status_code == 401
    assert anon.post("/api/demo/reset").status_code == 401
    assert anon.get("/api/patients/p1/medications/m1/administration-check").status_code == 401


def test_logout_ends_session(nurse):
    assert nurse.post("/api/auth/logout").json() == {"ok": True}
    assert nurse.post("/api/patients/p1/medications/m1/give", json={}).status_code == 401
    assert "signed out" in last_log()


@pytest.mark.parametrize("user,method,path,body", [
    ("spatel", "post", "/api/patients/p1/medications/m1/give", {}),        # provider can't administer
    ("jrivera", "post", "/api/patients/p1/medications", {"drugKey": "ibu"}),  # nurse can't order
    ("jrivera", "delete", "/api/patients/p1/medications/m1", None),
    ("jrivera", "post", "/api/patients/p1/discharge", None),
    ("akim", "put", "/api/patients/p1", {"name": "X", "age": 50, "sex": "F", "wt": 70, "bed": "412A"}),
    ("akim", "post", "/api/patients/p11/tasks/t1/complete", None),
])
def test_permissions_are_enforced_on_the_server(user, method, path, body):
    c = signed_in(user)
    r = getattr(c, method)(path, json=body) if body is not None else getattr(c, method)(path)
    assert r.status_code == 403
    assert r.json()["ok"] is False and r.json()["error"].startswith("Only ")


# ---- giving medications ----------------------------------------------------------------
def test_give_normal_medication(nurse):
    chk = nurse.get("/api/patients/p1/medications/m1/administration-check").json()
    assert chk == {"blocking": [], "highAlert": False, "expected": None}
    assert nurse.post("/api/patients/p1/medications/m1/give", json={}).json() == {"ok": True}
    assert med("p1", "m1").status == "given"
    assert "Gave Lisinopril 10 mg. All checks passed. — RN Jamie Rivera" in last_log()
    again = nurse.post("/api/patients/p1/medications/m1/give", json={}).json()
    assert again == {"ok": False, "error": "This order is no longer active."}


def test_high_alert_double_check(nurse):
    url = "/api/patients/p2/medications/m2/give"  # insulin lispro, expected 2 units
    chk = nurse.get("/api/patients/p2/medications/m2/administration-check").json()
    assert chk["highAlert"] and chk["expected"]["n"] == 2

    assert "second nurse" in nurse.post(url, json={}).json()["error"]
    assert "different nurse" in nurse.post(url, json={"cosigner": "jrivera", "cosignPin": "1234", "cosignDose": 2}).json()["error"]
    assert "must be a nurse" in nurse.post(url, json={"cosigner": "spatel", "cosignPin": "1234", "cosignDose": 2}).json()["error"]
    assert "PIN doesn’t match" in nurse.post(url, json={"cosigner": "mchen", "cosignPin": "9999", "cosignDose": 2}).json()["error"]

    r = nurse.post(url, json={"cosigner": "mchen", "cosignPin": "1234", "cosignDose": 4}).json()
    assert r["ok"] is False and "entered 4 units, but the calculated dose is 2 units" in r["error"]
    assert STATE.log[-1]["kind"] == "crit" and "Double-check caught a mismatch" in last_log()
    assert med("p2", "m2").status == "due"

    assert nurse.post(url, json={"cosigner": "mchen", "cosignPin": "1234", "cosignDose": 2}).json()["ok"]
    assert med("p2", "m2").cosign == "RN Maria Chen"
    assert "Gave Insulin lispro 2 units. Double-checked by RN Maria Chen." in last_log()


def test_hold_and_discontinue(nurse, provider):
    assert nurse.post("/api/patients/p1/medications/m2/hold", json={"reason": "HR 52"}).json()["ok"]
    assert med("p1", "m2").status == "held" and "Held Metoprolol succinate. Reason: HR 52" in last_log()
    assert provider.delete("/api/patients/p1/medications/m3").json()["ok"]
    assert med("p1", "m3") is None and "Discontinued Furosemide" in last_log()
    assert provider.delete("/api/patients/p1/medications/nope").json()["ok"] is False


# ---- alerts (the engine is Person 2's; fake one alert to test the server flow) ---------
@pytest.fixture
def fake_alert(monkeypatch):
    def evaluate(p, sim):
        if p.id != "p1":
            return []
        return [Alert(id="hold:p1:m1", pid="p1", sev="crit", meds=["m1"], trigger="BP", title="Hold lisinopril",
                      why="SBP below hold parameter", data=["SBP 82"], action="Hold and call provider")]
    monkeypatch.setattr(state_mod, "evaluate", evaluate)
    STATE.reset()


def test_blocking_alert_needs_override_reason(nurse, fake_alert):
    chk = nurse.get("/api/patients/p1/medications/m1/administration-check").json()
    assert [a["id"] for a in chk["blocking"]] == ["hold:p1:m1"]
    r = nurse.post("/api/patients/p1/medications/m1/give", json={}).json()
    assert r["ok"] is False and "reason" in r["error"]
    assert nurse.post("/api/patients/p1/medications/m1/give", json={"overrideReason": "  "}).json()["ok"] is False

    assert nurse.post("/api/patients/p1/medications/m1/give", json={"overrideReason": "Provider aware"}).json()["ok"]
    assert STATE.overrides["hold:p1:m1"] == "Provider aware"
    assert any('Override on Lisinopril: "Provider aware"' in e["text"] for e in STATE.log)
    assert STATE.snapshot().alerts == []


def test_hold_for_alert(nurse, fake_alert):
    assert nurse.post("/api/alerts/hold:p1:m1/hold").json()["ok"]
    assert med("p1", "m1").status == "held" and "Reason: Hold lisinopril" in last_log()
    assert STATE.snapshot().alerts == []  # resolved: its only med is no longer active


def test_acknowledge_alert(fake_alert):
    pharm = signed_in("akim")
    assert pharm.post("/api/alerts/hold:p1:m1/acknowledge").json()["ok"]
    assert STATE.acked["hold:p1:m1"] and "Acknowledged: Hold lisinopril — Alex Kim, PharmD" in last_log()
    assert pharm.post("/api/alerts/missing/acknowledge").json()["ok"] is False


def test_new_alert_is_logged_once(fake_alert):
    STATE.log.clear()
    STATE.seen.clear()
    STATE.run_rules()
    STATE.run_rules()
    assert [e["text"] for e in STATE.log] == ["412A Rosa Martínez · Hold lisinopril"]


# ---- ordering --------------------------------------------------------------------------
def test_order_medication(provider):
    assert provider.post("/api/patients/p6/medications", json={"drugKey": "ibu"}).json()["ok"]
    new = STATE.by_id("p6").meds[-1]
    assert new.catKey == "ibu" and new.isNew and new.id.startswith("n")
    assert "Passed Vital check. — Dr. Samuel Patel" in last_log()
    assert provider.post("/api/patients/p6/medications", json={"drugKey": "zzz"}).json()["ok"] is False


def test_order_with_critical_issue_needs_reason(provider, monkeypatch):
    from vital.models import CheckIssue
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "check_new_medication",
                        lambda p, d: [CheckIssue(sev="crit", type="allergy", title="Allergy", why="", action="")])
    r = provider.post("/api/patients/p1/medications", json={"drugKey": "ibu"}).json()
    assert r["ok"] is False and "reason" in r["error"]
    assert provider.post("/api/patients/p1/medications", json={"drugKey": "ibu", "overrideReason": "Benefit > risk"}).json()["ok"]
    assert 'Ordered despite Vital warning: "Benefit > risk"' in last_log()


def test_alternatives_route(nurse):
    r = nurse.post("/api/patients/p1/medication-alternatives", json={"drugKey": "ibu"})
    assert r.status_code == 200 and isinstance(r.json(), list)
    assert nurse.post("/api/patients/nope/medication-alternatives", json={"drugKey": "ibu"}).status_code == 404


# ---- tasks -----------------------------------------------------------------------------
def test_complete_task_on_time_and_late(nurse):
    assert nurse.post("/api/patients/p11/tasks/t1/complete").json()["ok"]
    assert STATE.by_id("p11").tasks[0].done and STATE.log[-1]["kind"] == "ok"
    STATE.sim = 150
    assert nurse.post("/api/patients/p11/tasks/t2/complete").json()["ok"]
    assert "(45 min late)" in last_log() and STATE.log[-1]["kind"] == "warn"


# ---- patients --------------------------------------------------------------------------
NEW_PATIENT = {"name": "Test Person", "age": 60, "sex": "M", "wt": 80, "bed": "430B", "dx": "Pneumonia",
               "conditions": [], "otherConds": [], "allergies": [{"agent": "Penicillin", "cls": "penicillin", "rxn": "Rash"}]}


def test_admit_edit_discharge(charge):
    r = charge.post("/api/patients", json=NEW_PATIENT).json()
    assert r["ok"] and r["id"] == "p100"
    p = STATE.by_id("p100")
    assert p.bed == "430B" and p.allergies[0].agent == "Penicillin" and len(p.hist["sbp"]) == 24
    assert "Admitted · allergies: Penicillin" in last_log()

    edit = {**NEW_PATIENT, "wt": 75, "bed": "428A", "allergies": []}
    assert charge.put("/api/patients/p100", json=edit).json()["ok"]
    assert p.wt == 75 and p.bed == "428A" and p.allergies == []
    assert "updated: weight, bed 430B → 428A, allergies." in last_log()

    assert charge.post("/api/patients/p100/discharge").json()["ok"]
    assert STATE.by_id("p100") is None and STATE.discharged[0]["bed"] == "428A"


@pytest.mark.parametrize("change,error", [
    ({"name": " "}, "Enter the patient’s name."),
    ({"age": 130}, "age between 0 and 120"),
    ({"age": None}, "age between 0 and 120"),
    ({"wt": 0}, "weight in kg"),
    ({"bed": "12"}, "like 412A"),
    ({"bed": "412A"}, "Bed 412A is taken by Rosa Martínez"),
    ({"allergies": [{"agent": "", "cls": "", "rxn": ""}]}, "name of each allergen"),
])
def test_admit_validation(charge, change, error):
    r = charge.post("/api/patients", json={**NEW_PATIENT, **change})
    assert r.status_code == 200 and r.json()["ok"] is False and error in r.json()["error"]


def test_bad_body_gets_friendly_422(charge):
    r = charge.post("/api/patients", json={**NEW_PATIENT, "allergies": "none"})
    assert r.status_code == 422 and r.json()["ok"] is False and r.json()["error"]


def test_editing_keeps_own_bed(nurse):
    p = STATE.by_id("p1")
    body = {"name": p.name, "age": p.age, "sex": p.sex, "wt": p.wt, "bed": p.bed, "dx": p.dx,
            "conditions": p.conditions, "otherConds": [], "allergies": [a.model_dump(exclude_none=True) for a in p.allergies]}
    assert nurse.put("/api/patients/p1", json=body).json()["ok"]
    assert "Patient info updated. Vital re-checked" in last_log()


def test_suggest_bed(nurse):
    taken = {p.bed for p in STATE.patients}
    bed = nurse.get("/api/beds/suggest").json()["bed"]
    assert bed and bed not in taken
    assert nurse.get("/api/beds/suggest?except=p1").json()["bed"] not in taken - {"412A"}


# ---- demo controls, simulator & live feed ------------------------------------------------
def test_scenario_trigger_and_undo(nurse):
    assert nurse.post("/api/demo/scenarios/k").json()["ok"]
    p = STATE.by_id("p1")
    assert p.labs.k.v == 5.8 and p.labs.k.prev == 4.6
    assert {s["key"]: s["used"] for s in STATE.snapshot().scenarios}["k"] is True
    assert nurse.post("/api/demo/scenarios/k").json()["ok"]
    assert p.labs.k.v == 4.6 and "Undid: Potassium result: 5.8" in last_log()


def test_order_scenario_adds_and_removes_med(nurse):
    nurse.post("/api/demo/scenarios/norco")
    meds = STATE.by_id("p4").meds
    assert meds[-1].name.startswith("Hydrocodone") and meds[-1].apap == 1950
    nurse.post("/api/demo/scenarios/norco")
    assert not any(m.name.startswith("Hydrocodone") for m in STATE.by_id("p4").meds)


def test_vitals_move_toward_target(nurse):
    nurse.post("/api/demo/scenarios/bp")
    for _ in range(20):
        STATE.tick()
    assert abs(STATE.by_id("p1").vit.sbp - 82) <= 4
    assert len(STATE.by_id("p1").hist["sbp"]) == 30


def test_skip_pause_reset(nurse):
    nurse.post("/api/demo/skip", json={"minutes": 15})
    assert STATE.sim == 15 and "Clock moved forward 15 min (demo)" in STATE.log[-1]["text"]
    nurse.post("/api/demo/pause", json={"paused": True})
    assert STATE.paused
    nurse.post("/api/demo/reset")
    assert STATE.sim == 0 and not STATE.paused and len(STATE.patients) == 11


def test_websocket_sends_snapshot():
    with anon.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
        assert len(snap["patients"]) == 11
        assert len(snap["scenarios"]) == 10 and snap["scenarios"][0]["patientLabel"] == "412A · Rosa Martínez"


def test_every_change_is_broadcast(nurse):
    with nurse.websocket_connect("/ws") as ws:
        ws.receive_json()
        nurse.post("/api/patients/p1/medications/m1/give", json={})
        snap = ws.receive_json()
        rosa = next(p for p in snap["patients"] if p["id"] == "p1")
        assert rosa["meds"][0]["status"] == "given"
        assert snap["log"][0]["text"].endswith("— RN Jamie Rivera")
