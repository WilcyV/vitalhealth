"""Small helpers ported from frontend/src/engine/util.ts (done for you)."""
from __future__ import annotations

import math

from .models import Medication, Patient, Vitals

BASE_MINUTES = 8 * 60 + 40  # demo clock starts at 08:40; `sim` = minutes since then


def fmt(sim: float) -> str:
    t = math.floor(BASE_MINUTES + sim)
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"


def round_vitals(v: Vitals) -> Vitals:
    # JS Math.round rounds .5 up; Python round() is banker's rounding. Match JS.
    r = lambda x: math.floor(x + 0.5)  # noqa: E731
    return Vitals(sbp=r(v.sbp), dbp=r(v.dbp), hr=r(v.hr), rr=r(v.rr), spo2=min(100, r(v.spo2)))


def crcl(p: Patient) -> int:
    """Cockcroft-Gault creatinine clearance (mL/min)."""
    c = ((140 - p.age) * p.wt) / (72 * p.labs.cr.v)
    if p.sex == "F":
        c *= 0.85
    return math.floor(c + 0.5)


def is_active(m: Medication) -> bool:
    return m.status not in ("given", "held")


def is_high_alert(m: Medication) -> bool:
    return any(c in ("insulin", "anticoag", "opioid") for c in m.cls) or ("Ksupp" in m.cls and m.route == "IV")


def list_names(items) -> str:
    n = [x.name for x in items]
    return n[0] if len(n) < 2 else ", ".join(n[:-1]) + " and " + n[-1]


def js_hash(s: str) -> str:
    """Same as hash() in util.ts, so alert IDs match the frontend."""
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if h == 0:
        return "0"
    out = ""
    while h:
        h, r = divmod(h, 36)
        out = digits[r] + out
    return out
