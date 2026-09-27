"""Privacy guard for Vital AI (Assurant "Take Control of AI").

Nothing that identifies a patient leaves the hospital. Before any text goes to the LLM we
replace the patient's name and bed with placeholders; the model rewrites the de-identified
text, and we put the real values back locally. Ages over 89 are generalized to "90+"
(HIPAA Safe Harbor).
"""
from __future__ import annotations

import re

PATIENT = "[PATIENT]"
BED = "[BED]"


def _sub(text: str, value: str, placeholder: str) -> str:
    if not value or len(value) < 2:
        return text
    return re.sub(rf"(?<![\w]){re.escape(value)}(?![\w])", placeholder, text, flags=re.IGNORECASE)


def deidentify(text: str, name: str, bed: str, age: int | None = None) -> tuple[str, dict[str, str], list[str]]:
    """Return (safe_text, mapping placeholder->real value, list of what was removed)."""
    out, removed, mapping = text, [], {}
    parts = [p for p in name.split() if len(p) > 1]
    for value in [name] + sorted(parts, key=len, reverse=True):  # full name first, then first/last name alone
        new = _sub(out, value, PATIENT)
        if new != out:
            out = new
            mapping[PATIENT] = name
            if "name" not in removed:
                removed.append("name")
    new = _sub(out, bed, BED)
    if new != out:
        out, mapping[BED] = new, bed
        removed.append("bed")
    if age is not None and age > 89:
        new = re.sub(rf"(?<!\d){age}(?=[FM]\b|\s*y)", "90+", out)
        if new != out:
            out = new
            mapping["90+"] = str(age)
            removed.append("age over 89")
    return out, mapping, removed


def reidentify(text: str, mapping: dict[str, str]) -> str:
    for placeholder, value in mapping.items():
        text = text.replace(placeholder, value)
    return text


def leaks(text: str, name: str, bed: str) -> bool:
    """True if the text still contains the patient's name or bed (used by tests and as a last check)."""
    safe, _, _ = deidentify(text, name, bed)
    return safe != text
