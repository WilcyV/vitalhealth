"""Thin LLM wrapper with a safety guard. Person 3 owns this file."""
from __future__ import annotations

import os
import re

SYSTEM = (
    "You rewrite hospital medication-safety messages for nurses. Use plain, calm, specific language. "
    "Never add, remove or change any number, drug name, dose, severity or recommendation. "
    "Never give new clinical advice. If unsure, return the text unchanged."
)


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def rewrite(template: str, instruction: str) -> str:
    """Ask the LLM to polish `template`. Returns the template itself when no key is set or on any error."""
    if not available():
        return template
    try:
        import anthropic  # imported lazily so tests run without the package configured

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("VITAL_MODEL", "claude-sonnet-4-5"),  # TODO(Person 3): pick the model your team has access to
            max_tokens=400,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"{instruction}\n\n---\n{template}"}],
        )
        text = "".join(getattr(b, "text", "") for b in msg.content).strip()
        return guard(template, text)
    except Exception:  # network, quota, etc. — the demo must keep working
        return template


_NUM = re.compile(r"\d+(?:\.\d+)?")


def guard(original: str, candidate: str) -> str:
    """Reject the LLM output if it introduces numbers that weren't in the original
    (a changed dose, lab value or time). TODO(Person 3): also check drug names and severity words."""
    if not candidate:
        return original
    allowed = set(_NUM.findall(original))
    if any(n not in allowed for n in _NUM.findall(candidate)):
        return original
    return candidate
