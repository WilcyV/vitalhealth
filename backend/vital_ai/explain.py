from __future__ import annotations

from vital.models import Alert, Patient

from .llm import rewrite


def explain(alert: Alert, patient: Patient) -> str:
    """Plain-language explanation shown on the alert card. Template first, LLM polish optional."""
    first = patient.name.split(" ")[0]
    template = f"{alert.title}. {alert.why} Suggested: {alert.action}".strip()
    return rewrite(template, f"Rewrite this alert about {first} for a busy nurse in 2–3 short sentences.")
