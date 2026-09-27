"""The drug database (vital/drugs.py).

The frontend's 37 demo drugs (data.ts, exported to backend/fixtures by `npm run fixtures`) must
all be here unchanged; the backend may add drugs, classes, look-alike links and reference cards.
"""
import re

from vital import drugs
from vital.data import load_json, reference

FRONTEND_ONLY_EXTRAS = {"tall", "lasa", "purpose", "rxcui"}  # fields the backend may add to a frontend drug


def test_frontend_drugs_are_all_here_unchanged():
    for fe in load_json("catalog.json"):
        be = drugs.by_key(fe["key"])
        assert be is not None, fe["key"]
        be = be.model_dump(exclude_none=True)
        for field, value in fe.items():
            if field == "cls":
                assert set(value) <= set(be["cls"]), fe["key"]  # may add classes, never drop one
            else:
                assert be[field] == value, (fe["key"], field)
        assert set(be) - set(fe) <= FRONTEND_ONLY_EXTRAS, fe["key"]


def test_frontend_reference_data_is_all_here():
    assert load_json("drug-info.json").items() <= drugs.DRUG_INFO.items()
    ref = reference()
    assert drugs.CONDITIONS == ref["conditions"]
    assert ref["classLabels"].items() <= drugs.CLASS_LABELS.items()
    assert ref["groupLabels"].items() <= drugs.GROUP_LABELS.items()
    assert drugs.ALLERGENS == ref["allergens"]


def test_catalog_integrity():
    keys = [d.key for d in drugs.CATALOG]
    assert len(keys) == len(set(keys)), "duplicate drug keys"
    for d in drugs.CATALOG:
        assert d.group in drugs.GROUP_LABELS, d.key
        assert d.cls, d.key
        assert drugs.drug_info_for(d.name), f"no reference card for {d.name}"
        assert d.rxcui and all(re.fullmatch(r"\d+", c) for c in d.rxcui), f"missing RxNorm code: {d.key}"
        if d.lasa:
            other = drugs.look_alike(d)
            assert other and other.lasa == d.key, f"look-alike pair {d.key} <-> {d.lasa} must point both ways"
            assert d.tall and d.purpose, d.key


def test_rule_tables_are_consistent():
    known = {c for d in drugs.CATALOG for c in d.cls}
    for rule in drugs.INTERACTIONS:
        assert set(rule["drug"]) <= known, rule["title"]
        assert rule["sev"] in ("crit", "warn", "info")
    for key, limits in drugs.RENAL_DOSING.items():
        assert drugs.by_key(key), key
        assert [x[0] for x in limits] == sorted(x[0] for x in limits), f"{key}: lowest limit first"
    assert set(drugs.AGE_CAUTIONS) <= known
    assert all(c in drugs.CLASS_LABELS for c in drugs.DUPLICATE_CLASSES)


def test_drug_info_lookup_picks_longest_match():
    assert drugs.drug_info_for("Metoprolol succinate")["cls"].startswith("Beta-blocker")
    assert drugs.drug_info_for("Insulin lispro")["cls"].startswith("Rapid-acting insulin")
    assert drugs.drug_info_for("Insulin glargine")["cls"].startswith("Long-acting")
    assert drugs.drug_info_for("Unknownium") is None
