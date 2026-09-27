from __future__ import annotations

from vital.models import Alert, Patient
from vital.util import crcl, round_vitals

from .llm import rewrite


def sbar(patient: Patient, alerts: list[Alert]) -> str:
    """Message the nurse can send to the provider. Used by the 'Notify provider' button."""
    v = round_vitals(patient.vit)
    top = sorted(alerts, key=lambda a: {"crit": 0, "warn": 1, "info": 2}[a.sev])
    main = top[0] if top else None
    meds = ", ".join(f"{m.name} {m.dose} {m.route}" for m in patient.meds if m.status == "due") or "none due"
    allergies = ", ".join(a.agent for a in patient.allergies) or "no known drug allergies"
    template = "\n".join([
        f"S: {patient.name}, bed {patient.bed}. " + (f"{main.title}." if main else "No active Vital alerts."),
        f"B: {patient.age}{patient.sex}, {patient.dx}. Allergies: {allergies}. Due meds: {meds}.",
        f"A: BP {v.sbp:g}/{v.dbp:g}, HR {v.hr:g}, RR {v.rr:g}, SpO2 {v.spo2:g}%. K+ {patient.labs.k.v:g}, CrCl {crcl(patient)} mL/min."
        + (f" {main.why}" if main else ""),
        f"R: {main.action} Please advise." if main else "R: For your awareness.",
    ])
    return rewrite(template, "Tighten this SBAR message. Keep the S/B/A/R lines and every fact.", patient, "sbar")
