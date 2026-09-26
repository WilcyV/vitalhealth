"""Parity tests for the new-medication check (expected results exported from the frontend)."""
import pytest

from vital.checker import check_new_medication
from vital.data import drug, load_json, patient, snapshot

PORTED = False  # Person 2: flip to True when check_new_medication() is done
CASES = load_json("checker-cases.json")


@pytest.mark.xfail(not PORTED, reason="Person 2: port checker.ts", strict=False)
@pytest.mark.parametrize("case", CASES, ids=[f"{c['patient']}-{c['drug']}" for c in CASES])
def test_same_issues_as_frontend(case):
    snap = snapshot()
    got = [(i.sev, i.type, i.title) for i in check_new_medication(patient(snap, case["patient"]), drug(case["drug"]))]
    assert got == [(i["sev"], i["type"], i["title"]) for i in case["issues"]]
