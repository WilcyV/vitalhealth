"""LLM wrapper with a safety guard (Person 3).

The rules engine decides; the LLM only rewrites text. Every rewrite goes through `guard()`,
and if the model changed any clinical fact we silently fall back to the template.
"""
from __future__ import annotations

import contextvars
import os
import re
from functools import lru_cache

SYSTEM = (
    "You rewrite hospital medication-safety messages for nurses. Use plain, calm, specific language. "
    "Never add, remove or change any number, unit, drug name, dose, severity or recommendation. "
    "Never give new clinical advice. Keep it short. If unsure, return the text unchanged. "
    "Reply with the rewritten message only."
)

# "ai" when the last rewrite() used the model's text, "template" when it fell back.
LAST_SOURCE: contextvars.ContextVar[str] = contextvars.ContextVar("vital_ai_source", default="template")


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def rewrite(template: str, instruction: str) -> str:
    """Ask the LLM to polish `template`. Returns the template when no key is set, on any error,
    or when guard() rejects the model's answer."""
    LAST_SOURCE.set("template")
    if not available():
        return template
    try:
        import anthropic  # imported lazily so the app runs without the package configured

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("VITAL_MODEL", "claude-sonnet-4-5"),  # set VITAL_MODEL to a model your key can use
            max_tokens=500,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"{instruction}\n\n---\n{template}"}],
        )
        text = "".join(getattr(b, "text", "") for b in msg.content).strip()
    except Exception:  # network, quota, bad model name… the demo must keep working
        return template
    checked = guard(template, text)
    if checked is not template:
        LAST_SOURCE.set("ai")
    return checked


# ---- guard -------------------------------------------------------------------------------
_NUM = re.compile(r"\d+(?:\.\d+)?")
# Words whose appearance changes the clinical meaning. If the model adds one, reject.
_SEVERITY = ("critical", "warning", "urgent", "emergency", "stat", "minor", "mild", "low risk", "no risk",
             "safe to give", "fine", "normal", "stable", "ignore", "not needed", "optional")
# Actions the model must never drop if the original had them.
_ACTIONS = ("hold", "do not give", "don't give", "stop", "notify", "call", "recheck", "repeat", "avoid")


@lru_cache
def known_drugs() -> frozenset[str]:
    """Lower-case drug names Vital knows about (catalog + drug reference + patients' orders)."""
    from vital.data import catalog, drug_info, load_json

    names = {k for k in drug_info()}
    for d in catalog():
        names.add(d.name.lower().split(" ")[0].split("/")[0])
    for p in load_json("patients.json"):
        for m in p["meds"]:
            names.add(m["name"].lower().split(" ")[0].split("/")[0])
    return frozenset(n for n in names if len(n) > 3)


def _has(text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) is not None


def guard(original: str, candidate: str) -> str:
    """Return `candidate` only if it keeps every clinical fact of `original`; else `original`.

    Rejects when the candidate:
      - is empty or much longer than the original,
      - contains a number that isn't in the original (changed dose, lab value, time),
      - names a drug that isn't in the original,
      - adds a severity / reassurance word ("minor", "safe to give", …),
      - drops an action the original asked for ("hold", "notify", …).
    """
    if not candidate or len(candidate) > 2 * len(original) + 200:
        return original
    o, c = original.lower(), candidate.lower()
    if not set(_NUM.findall(candidate)) <= set(_NUM.findall(original)):
        return original
    if any(_has(c, d) and not _has(o, d) for d in known_drugs()):
        return original
    if any(_has(c, w) and not _has(o, w) for w in _SEVERITY):
        return original
    if any(_has(o, w) and not _has(c, w) for w in _ACTIONS):
        return original
    return candidate
