"""Expected dose for the high-alert independent double-check (port of doubleCheck.ts, done for you)."""
from __future__ import annotations

import re

from .models import ExpectedDose, Medication, Patient
from .util import fmt


def sliding_scale(glucose: float) -> int:
    for limit, units in ((150, 0), (200, 2), (250, 4), (300, 6), (350, 8)):
        if glucose <= limit:
            return units
    return 10


def expected_dose(p: Patient, m: Medication) -> ExpectedDose:
    if "insulin" in m.cls:
        g = p.labs.glu.v
        n = sliding_scale(g)
        band = ("≤ 150 = 0" if g <= 150 else "151–200 = 2" if g <= 200 else "201–250 = 4" if g <= 250
                else "251–300 = 6" if g <= 300 else "301–350 = 8" if g <= 350 else "> 350 = 10 (call provider)")
        when = "last check" if p.labs.glu.t < 0 else fmt(p.labs.glu.t)
        return ExpectedDose(n=n, unit="units", calc=f"Glucose {g:g} mg/dL at {when} → sliding scale {band} units")
    mm = re.match(r"^([\d.]+)\s*(.*)$", m.dose)
    return ExpectedDose(n=float(mm.group(1)) if mm else float("nan"), unit=mm.group(2) if mm else "", calc=f"Ordered dose: {m.dose} {m.route}")
