"""Parity tests: the Python engine must produce the same alert IDs as the frontend.

These are marked xfail until Person 2 ports rules.ts. When they start passing,
pytest shows XPASS — then delete the xfail marker.
"""
import pytest

from vital.data import snapshot
from vital.rules import evaluate

FIXTURES = ["snapshot.json", "snapshot-potassium-5.8.json", "snapshot-creatinine-2.8.json", "snapshot-after-60-min.json"]
PORTED = False  # Person 2: flip to True when evaluate() is done


def cases():
    for f in FIXTURES:
        snap = snapshot(f)
        for p in snap.patients:
            yield pytest.param(f, p.id, id=f"{f}:{p.id}")


@pytest.mark.xfail(not PORTED, reason="Person 2: port rules.ts", strict=False)
@pytest.mark.parametrize("fixture,pid", list(cases()))
def test_same_alert_ids_as_frontend(fixture, pid):
    snap = snapshot(fixture)
    p = next(x for x in snap.patients if x.id == pid)
    expected = {a.id for a in snap.alerts + snap.heldBack if a.pid == pid}
    got = {a.id for a in evaluate(p, snap.sim)}
    assert got == expected


@pytest.mark.xfail(not PORTED, reason="Person 2: port rules.ts", strict=False)
def test_high_potassium_is_critical_on_both_meds():
    snap = snapshot("snapshot-potassium-5.8.json")
    rosa = next(p for p in snap.patients if p.id == "p1")
    a = next(a for a in evaluate(rosa, snap.sim) if a.id == "k:p1")
    assert a.sev == "crit" and set(a.meds) == {"m1", "m4"}
