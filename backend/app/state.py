"""In-memory unit state (Person 1). Replace with FHIR + PostgreSQL step by step.

Mirrors frontend/src/api/mock.ts: holds patients, runs the Vital engine after every change,
keeps the audit log, and builds the Snapshot pushed to every client.
"""
from __future__ import annotations

import copy
from typing import Optional

from vital import evaluate
from vital.data import load_json
from vital.models import Alert, Patient, Snapshot, User


class UnitState:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        snap = load_json("snapshot.json")  # starting point = the frontend's first screen
        self.sim: float = 0
        self.paused = False
        self.patients: list[Patient] = [Patient(**p) for p in snap["patients"]]
        self.log: list[dict] = [{"t": 0, "text": f"Shift started. Monitoring {len(self.patients)} patients.", "kind": ""}]
        self.discharged: list[dict] = []
        self.alerts: list[Alert] = []
        self.seen: dict[str, float] = {}
        self.run_rules()

    def run_rules(self) -> None:
        """Re-check every patient. TODO(Person 1): add acked/overrides/resolved like mock.ts."""
        out: list[Alert] = []
        for p in self.patients:
            for a in evaluate(p, self.sim):
                self.seen.setdefault(a.id, self.sim)
                a.firstSeen = self.seen[a.id]
                out.append(a)
        self.alerts = out

    def add_log(self, text: str, kind: str = "", user: Optional[User] = None) -> None:
        self.log.append({"t": self.sim, "text": text + (f" — {user.name}" if user else ""), "kind": kind})

    def snapshot(self) -> Snapshot:
        return Snapshot(
            sim=self.sim, paused=self.paused, patients=copy.deepcopy(self.patients),
            alerts=[a for a in self.alerts if a.sev != "info"], heldBack=[a for a in self.alerts if a.sev == "info"],
            log=list(reversed(self.log[-60:])), discharged=self.discharged, scenarios=[],
        )


STATE = UnitState()
