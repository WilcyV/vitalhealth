"""Parity tests for the new-medication check (expected results exported from the frontend),
plus the checker cases from frontend/src/engine/rules.test.ts."""
import pytest

from vital.checker import check_new_medication, suggest_alternatives
from vital.data import drug, load_json, patient, snapshot

CASES = load_json("checker-cases.json")


@pytest.mark.parametrize("case", CASES, ids=[f"{c['patient']}-{c['drug']}" for c in CASES])
def test_catches_everything_the_frontend_catches(case):
    """The backend has extra rules (drugs.py tables), so it may find more, never less."""
    snap = snapshot()
    got = [(i.sev, i.type, i.title) for i in check_new_medication(patient(snap, case["patient"]), drug(case["drug"]))]
    missing = [i for i in case["issues"] if (i["sev"], i["type"], i["title"]) not in got]
    assert not missing


def test_blocks_lisinopril_in_pregnancy():
    priya = patient(snapshot(), "p8")
    assert any(i.sev == "crit" and i.type == "Pregnancy" for i in check_new_medication(priya, drug("lisi")))


def test_propranolol_critical_metoprolol_warning_in_asthma():
    luis = patient(snapshot(), "p6")
    assert check_new_medication(luis, drug("prop"))[0].sev == "crit"
    assert all(i.sev != "crit" for i in check_new_medication(luis, drug("meto")))


def test_catches_penicillin_allergy():
    james = patient(snapshot(), "p2")
    assert check_new_medication(james, drug("amox"))[0].type == "Allergy"


def test_sorted_critical_first():
    rosa = patient(snapshot(), "p1")
    ranks = [{"crit": 0, "warn": 1, "info": 2}[i.sev] for i in check_new_medication(rosa, drug("ibu"))]
    assert ranks == sorted(ranks) and ranks[0] == 0


def test_suggests_safer_alternatives():
    rosa = patient(snapshot(), "p1")
    alts = suggest_alternatives(rosa, drug("ibu"))
    assert alts and alts[0]["drug"].key == "apap"
    assert len(alts) <= 3
    assert all(i.sev != "crit" for a in alts for i in a["issues"])
    assert all(a["drug"].group == "pain" for a in alts)


# ---- backend additions (drugs.py tables and extra checks) ----------------------------------
def issues(pid, key, snap=None):
    return check_new_medication(patient(snap or snapshot(), pid), drug(key))


def titles(pid, key, snap=None):
    return {i.title for i in issues(pid, key, snap)}


def test_dual_raas_blockade():
    rosa = issues("p1", "losar")  # Rosa is on lisinopril
    assert any(i.sev == "crit" and i.title == "Dual RAAS blockade with Lisinopril" for i in rosa)


def test_arb_in_pregnancy():
    assert any(i.sev == "crit" and i.type == "Pregnancy" for i in issues("p8", "losar"))


def test_warfarin_order_checks_existing_meds():
    # Ana (p3) is on warfarin; ordering a DOAC is a duplicate anticoagulant
    assert any(i.type == "Duplicate therapy" for i in issues("p3", "apix"))
    # Ana is on diltiazem + atorvastatin: amiodarone interacts with both, and warfarin
    got = titles("p3", "amio")
    assert {"Raises INR with Warfarin", "Slow heart rate with Diltiazem ER", "Raises Atorvastatin levels"} <= got


def test_serotonin_syndrome():
    snap = snapshot()
    p = patient(snap, "p4")
    from vital.models import Medication
    p.meds.append(Medication(id="x1", name="Sertraline", dose="50 mg", route="PO", freq="Daily", due="09:00", cls=["SSRI", "serotonergic"]))
    got = check_new_medication(p, drug("linez"))
    assert any(i.sev == "crit" and i.title == "Serotonin syndrome with Sertraline" for i in got)
    assert any(i.title == "Serotonin syndrome risk with Sertraline" for i in check_new_medication(p, drug("tram")))


def test_renal_dosing_table():
    snap = snapshot("snapshot-creatinine-2.8.json")  # James (p2): CrCl drops below 30
    got = issues("p2", "nitrof", snap)
    assert any(i.sev == "crit" and i.type == "Kidney function" for i in got)
    assert any(i.title.startswith("Dose adjustment") for i in issues("p2", "gaba", snap))
    assert not any(i.type == "Kidney function" for i in issues("p2", "nitrof"))  # fine at baseline


def test_beers_long_acting_sulfonylurea():
    assert any(i.type == "Age" for i in issues("p5", "glyb"))  # Grace, 81
    assert not any(i.type == "Age" for i in issues("p5", "glip"))


def test_same_drug_already_ordered():
    assert "Already ordered: Ondansetron" in titles("p4", "ondan")


def test_heparin_ok_in_pregnancy_warfarin_not():
    assert not any(i.type == "Pregnancy" for i in issues("p8", "hep"))
    assert any(i.sev == "crit" and i.type == "Pregnancy" for i in issues("p8", "warf"))


def test_olanzapine_blocked_in_parkinsons():
    got = issues("p9", "olanz")
    assert got[0].sev == "crit" and "quetiapine" in got[0].action


def test_safer_statin_suggested_with_interacting_drugs():
    # Ana (p3) is on diltiazem, which slows simvastatin/atorvastatin breakdown (not pravastatin/rosuvastatin)
    ana = patient(snapshot(), "p3")
    ana.meds = [m for m in ana.meds if "statin" not in m.cls]
    alts = suggest_alternatives(ana, drug("simva"))
    assert {a["drug"].key for a in alts[:2]} == {"prava", "rosu"} and not alts[0]["issues"]
