"""Vital rules engine (Person 2). Pure Python: no web framework, no database.

Public API (keep these signatures; the server and the AI call them):
    evaluate(patient, sim)                 -> list[Alert]       rules.py
    check_new_medication(patient, drug)    -> list[CheckIssue]  checker.py
    expected_dose(patient, med)            -> ExpectedDose      double_check.py
    can(user, permission)                  -> bool              permissions.py
"""
from .models import Alert, CatalogDrug, CheckIssue, ExpectedDose, Medication, Patient, Snapshot, User  # noqa: F401
from .rules import evaluate  # noqa: F401
from .checker import check_new_medication  # noqa: F401
from .double_check import expected_dose  # noqa: F401
from .permissions import can  # noqa: F401
