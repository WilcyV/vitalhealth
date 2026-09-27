"""Parity tests: the Python engine must produce the same alerts as the frontend (rules.ts),
plus the engine cases from frontend/src/engine/rules.test.ts."""
import pytest

from vital.data import patient, snapshot
from vital.models import Allergy
from vital.rules import evaluate

FIXTURES = ["snapshot.json", "snapshot-potassium-5.8.json", "snapshot-creatinine-2.8.json", "snapshot-after-60-min.json"]


def cases():
    for f in FIXTURES:
        snap = snapshot(f)
        for p in snap.patients:
            yield pytest.param(f, p.id, id=f"{f}:{p.id}")


@pytest.mark.parametrize("fixture,pid", list(cases()))
def test_same_alerts_as_frontend(fixture, pid):
    """Same IDs, and every field (text, data lines, meds, severity) identical."""
    snap = snapshot(fixture)
    p = patient(snap, pid)
    expected = {a.id: a.model_dump(exclude={"firstSeen"}) for a in snap.alerts + snap.heldBack if a.pid == pid}
    got = {a.id: a.model_dump(exclude={"firstSeen"}) for a in evaluate(p, snap.sim)}
    assert got == expected


def test_starts_calm():
    snap = snapshot()
    alerts = [a for p in snap.patients for a in evaluate(p, snap.sim)]
    assert not [a for a in alerts if a.sev == "crit"]
    assert [a for a in alerts if a.sev == "info"]


def test_high_potassium_is_critical_on_both_meds():
    snap = snapshot("snapshot-potassium-5.8.json")
    a = next(a for a in evaluate(patient(snap, "p1"), snap.sim) if a.id == "k:p1")
    assert a.sev == "crit" and set(a.meds) == {"m1", "m4"}


def test_metformin_contraindicated_below_crcl_30():
    snap = snapshot("snapshot-creatinine-2.8.json")
    assert any(a.id == "renal:p2:m1" and a.sev == "crit" for a in evaluate(patient(snap, "p2"), snap.sim))


def test_late_sepsis_antibiotic_escalates_to_critical():
    snap = snapshot("snapshot-after-60-min.json")
    assert any(a.id == "tc:p11:m1:crit" for a in evaluate(patient(snap, "p11"), snap.sim))


def test_rechecks_orders_when_allergies_change():
    snap = snapshot()
    p = patient(snap, "p4")
    assert not any(a.id.startswith("allergy") for a in evaluate(p, 0))
    p.allergies = [Allergy(agent="Morphine / opioids", cls="opioid", rxn="anaphylaxis")]
    assert any(a.id == "allergy:p4:m2" and a.sev == "crit" for a in evaluate(p, 0))


def test_hold_parameter_when_bp_drops():
    snap = snapshot()
    p = patient(snap, "p1")
    p.vit.sbp = 84
    ids = {a.id for a in evaluate(p, snap.sim)}
    assert {"hold:p1:m1", "hold:p1:m2"} <= ids


def test_patient_without_vitals_history():
    snap = snapshot()
    p = patient(snap, "p1")
    p.hist = None
    evaluate(p, snap.sim)  # must not crash
