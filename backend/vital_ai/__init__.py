"""Vital AI layer (Person 3). Writes TEXT ONLY.

    explain(alert, patient)     -> str   plain-language alert explanation
    sbar(patient, alerts)       -> str   message to the provider (Situation, Background, Assessment, Recommendation)
    handoff(patient, alerts)    -> str   shift handoff summary

Every function works without an API key (template text), so the demo never breaks.
With ANTHROPIC_API_KEY set, it asks the LLM to rewrite the template, then `guard()` checks
the result and falls back to the template if the model changed any clinical fact.
"""
from .explain import explain  # noqa: F401
from .sbar import sbar  # noqa: F401
from .handoff import handoff  # noqa: F401
