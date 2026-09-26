from __future__ import annotations

from vital.models import Alert, Patient
from vital.util import fmt

from .llm import rewrite


def handoff(patient: Patient, alerts: list[Alert]) -> str:
    """Shift handoff summary for the next nurse."""
    held = [m for m in patient.meds if m.status == "held"]
    given = [m for m in patient.meds if m.status == "given"]
    open_tasks = [t for t in patient.tasks if not t.done]
    lines = [f"{patient.bed} {patient.name} — {patient.dx}."]
    if alerts:
        lines.append("Open alerts: " + "; ".join(a.title for a in alerts if a.sev != "info") + ".")
    if held:
        lines.append("Held: " + ", ".join(m.name for m in held) + ".")
    if given:
        lines.append("Given this shift: " + ", ".join(f"{m.name} at {fmt(m.at or 0)}" for m in given) + ".")
    if open_tasks:
        lines.append("Still due: " + ", ".join(f"{t.name} by {fmt(t.due + t.grace)}" for t in open_tasks) + ".")
    return rewrite(" ".join(lines), "Turn this into a short, clear nursing handoff. Keep every fact.")
