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
# Transparency record of the last rewrite(): what was sent, why, tokens and cost (see usage.py).
LAST_META: contextvars.ContextVar[dict | None] = contextvars.ContextVar("vital_ai_meta", default=None)


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def model_name() -> str:
    return os.getenv("VITAL_MODEL", "claude-sonnet-4-5")  # set VITAL_MODEL to a model your key can use


def rewrite(template: str, instruction: str, patient=None, kind: str = "text") -> str:
    """Ask the LLM to polish `template`. Returns the template when AI is off, no key is set,
    the monthly budget is spent, on any error, or when guard() rejects the model's answer.

    With `patient`, the name and bed are replaced by placeholders before anything leaves the
    server, and restored locally afterwards (privacy.py). Every call is recorded in usage.py.
    """
    from . import usage
    from .privacy import deidentify, reidentify

    LAST_SOURCE.set("template")
    mapping: dict[str, str] = {}
    removed: list[str] = []
    sent_instr, sent_text = instruction, template
    if patient is not None:
        sent_text, mapping, removed = deidentify(template, patient.name, patient.bed, patient.age)
        sent_instr, m2, _ = deidentify(instruction, patient.name, patient.bed, patient.age)
        mapping.update(m2)
    prompt = f"{sent_instr}\n\n---\n{sent_text}"
    meta = {"kind": kind, "model": model_name(), "sentText": sent_text, "removed": removed,
            "deidentified": patient is not None, "tokensIn": usage.estimate_tokens(SYSTEM + prompt),
            "tokensOut": 0, "costUsd": 0.0, "estimated": True, "reason": "ai"}
    LAST_META.set(meta)

    def fallback(reason: str) -> str:
        meta["reason"] = reason
        usage.record(meta)
        return template

    if usage.mode() == "off":
        return fallback("off")
    if not available():
        return fallback("no-key")
    if usage.over_budget():
        return fallback("budget")
    try:
        import anthropic  # imported lazily so the app runs without the package configured

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=model_name(),
            max_tokens=500,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(b, "text", "") for b in msg.content).strip()
        u = getattr(msg, "usage", None)
        if u is not None and isinstance(getattr(u, "input_tokens", None), int):
            meta["tokensIn"], meta["tokensOut"], meta["estimated"] = u.input_tokens, u.output_tokens, False
        else:
            meta["tokensOut"] = usage.estimate_tokens(text)
        meta["costUsd"] = usage.cost(meta["tokensIn"], meta["tokensOut"])
    except Exception:  # network, quota, bad model name… the demo must keep working
        return fallback("error")
    # The model must keep the placeholders; otherwise it dropped or invented who the message is about.
    if any(ph in sent_text and ph not in text for ph in mapping):
        return fallback("guard")
    checked = guard(sent_text, text)
    if checked is sent_text:
        return fallback("guard")
    LAST_SOURCE.set("ai")
    usage.record(meta)
    return reidentify(checked, mapping)


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
