from vital.data import patient, snapshot
from vital.double_check import expected_dose
from vital.data import load_json
from vital.permissions import can
from vital.models import User
from vital.util import crcl, fmt, js_hash


def test_clock():
    assert fmt(0) == "08:40" and fmt(20) == "09:00"


def test_crcl_matches_frontend():
    snap = snapshot()
    assert crcl(patient(snap, "p2")) == 63
    assert crcl(patient(snap, "p1")) == 50


def test_hash_matches_frontend():
    # value produced by util.ts hash('abc')
    assert js_hash("abc") == "22ci"


def test_double_check_doses_match_frontend():
    snap = snapshot()
    for case in load_json("double-check-cases.json"):
        p = patient(snap, case["patient"])
        m = next(x for x in p.meds if x.id == case["med"])
        assert expected_dose(p, m).n == case["expected"]["n"], case


def test_permissions():
    nurse = User(username="x", name="x", role="nurse", title="RN")
    assert can(nurse, "administer") and not can(nurse, "order")
