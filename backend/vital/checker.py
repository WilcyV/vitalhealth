"""New-medication check — PERSON 2.

Port `checkNewMedication()` from frontend/src/engine/checker.ts: every safety rule for a drug
BEFORE it is ordered (allergies, duplicates, acetaminophen max, interactions, conditions,
pregnancy, Parkinson's, GI bleed, dysphagia, kidney function, labs, vitals, age).

Return issues sorted critical → warning → info.
Target tests:  pytest vital/tests/test_checker.py   (expected results in fixtures/checker-cases.json)
"""
from __future__ import annotations

from typing import Optional

from .models import CatalogDrug, CheckIssue, Patient


def check_new_medication(patient: Patient, drug: CatalogDrug, self_id: Optional[str] = None) -> list[CheckIssue]:
    # TODO(Person 2): port frontend/src/engine/checker.ts
    return []


def suggest_alternatives(patient: Patient, drug: CatalogDrug) -> list[dict]:
    """Drugs in the same `group` that have no critical issue, fewest issues first, max 3.
    Returns [{"drug": CatalogDrug, "issues": [CheckIssue]}]. See suggestAlternatives in api/mock.ts."""
    # TODO(Person 2)
    return []
