"""Who can do what. Same table as frontend/src/engine/permissions.ts (done for you)."""
from __future__ import annotations

from typing import Optional

from .data import reference
from .models import Permission, User

PERMISSIONS: dict[str, list[str]] = reference()["permissions"]
ROLE_LABEL = {"nurse": "Nurse", "charge": "Charge nurse", "pharmacist": "Pharmacist", "provider": "Provider"}


def can(user: Optional[User], action: Permission) -> bool:
    return user is not None and user.role in PERMISSIONS[action]


def why_not(action: Permission) -> str:
    who = [ROLE_LABEL[r].lower() + "s" for r in PERMISSIONS[action]]
    joined = who[0] if len(who) == 1 else ", ".join(who[:-1]) + " and " + who[-1]
    return f"Only {joined} can do this."
