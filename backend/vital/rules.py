"""Continuous rules — PERSON 2 starts here.

Port `evaluate()` from frontend/src/engine/rules.ts. It returns every alert for one patient
right now (critical, warning and low-priority "info"). The server calls it after every change.

Keep alert IDs identical to the TypeScript version (e.g. "k:p1", "hold:p1:m1",
"renal:p2:m1", "tc:p11:m1:crit") — the tests compare against the frontend's output.

Rules to port, in the same order as rules.ts:
  [ ] hold parameters from the order (SBP / HR)            -> id hold:{pid}:{mid}
  [ ] BP falling fast (trend, still >= 90)                  -> trend:{pid}
  [ ] potassium with ACEi/ARB/K-sparing (crit/warn/info)    -> k / k5 / kinfo
  [ ] kidney function: metformin, enoxaparin                -> renal / renal45
  [ ] low glucose + insulin                                 -> glu:{pid}
  [ ] INR + warfarin, NSAID + warfarin                      -> inr / inr3 / nsaid
  [ ] allergies (skip meds with catKey)                     -> allergy:{pid}:{mid}
  [ ] duplicate acetaminophen > 4 g/day                     -> apap:{pid}
  [ ] orders placed via the checker keep being re-checked   -> new:{pid}:{mid}:{js_hash(title)}
  [ ] opioids + RR < 12 or SpO2 < 90                        -> resp:{pid}
  [ ] hemoglobin < 7, lactate >= 4                          -> hgb / lac
  [ ] time-critical meds + care tasks (warn / crit)         -> tc:{pid}:{id}:warn|crit
  [ ] low-priority "info" checks                            -> i1, beers, st, dil, qt, az, lm, ceph, dx, pr, dy, gi, va

Helpers ready in util.py: fmt, round_vitals, crcl, is_active, list_names, js_hash.
Run the target tests:  pytest vital/tests/test_rules.py
"""
from __future__ import annotations

from .models import Alert, Patient


def evaluate(patient: Patient, sim: float) -> list[Alert]:
    """Return all alerts for this patient at demo time `sim` (minutes since 08:40)."""
    # TODO(Person 2): port frontend/src/engine/rules.ts
    return []
