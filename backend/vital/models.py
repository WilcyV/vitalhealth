"""Data shapes shared by the whole backend.

These mirror frontend/src/types.ts field-for-field (camelCase on purpose, so the JSON the
server sends is exactly what the frontend expects). If you change one, change both.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

Severity = Literal["crit", "warn", "info"]
Role = Literal["nurse", "charge", "pharmacist", "provider"]
Permission = Literal["administer", "order", "admit", "discharge", "editPatient", "acknowledge", "tasks"]


class _M(BaseModel):
    model_config = ConfigDict(extra="allow")


class Vitals(_M):
    sbp: float
    dbp: float
    hr: float
    rr: float
    spo2: float


class LabValue(_M):
    v: float
    t: float
    prev: Optional[float] = None


class Labs(_M):
    k: LabValue
    cr: LabValue
    glu: LabValue
    inr: Optional[LabValue] = None
    hgb: Optional[LabValue] = None
    lac: Optional[LabValue] = None


class Allergy(_M):
    agent: str
    cls: str
    rxn: str
    intol: Optional[bool] = None


class TimeCritical(_M):
    due: float
    grace: float
    why: str


class Hold(_M):
    sbp: Optional[float] = None
    hr: Optional[float] = None


class Medication(_M):
    id: str
    name: str
    dose: str
    route: str
    freq: str
    due: str
    cls: list[str]
    hold: Optional[Hold] = None
    param: Optional[str] = None
    effect: Optional[str] = None
    renal: Optional[bool] = None
    apap: Optional[float] = None
    beers: Optional[bool] = None
    qt: Optional[bool] = None
    dilt: Optional[bool] = None
    tc: Optional[TimeCritical] = None
    isNew: Optional[bool] = None
    orderedAt: Optional[float] = None
    catKey: Optional[str] = None
    status: Literal["due", "given", "held"] = "due"
    at: Optional[float] = None
    cosign: Optional[str] = None


class CareTask(_M):
    id: str
    name: str
    due: float
    grace: float
    why: str
    done: bool = False
    at: Optional[float] = None


class Patient(_M):
    id: str
    bed: str
    name: str
    age: int
    sex: Literal["F", "M"]
    wt: float
    dx: str
    conditions: list[str]
    otherConds: Optional[list[str]] = None
    allergies: list[Allergy]
    vit: Vitals
    target: Optional[Vitals] = None
    base: Optional[Vitals] = None
    hist: Optional[dict[str, list[float]]] = None
    labs: Labs
    meds: list[Medication]
    tasks: list[CareTask] = []


class Alert(_M):
    id: str
    pid: str
    sev: Severity
    meds: list[str]
    trigger: str
    title: str
    why: str
    data: list[str]
    action: str
    task: Optional[str] = None
    timing: Optional[bool] = None
    firstSeen: Optional[float] = None


class CheckIssue(_M):
    sev: Severity
    type: str
    title: str
    why: str
    action: str


class CatalogDrug(_M):
    key: str
    name: str
    dose: str
    route: str
    freq: str
    due: str
    cls: list[str]
    group: str
    apap: Optional[float] = None
    tall: Optional[str] = None
    lasa: Optional[str] = None
    purpose: Optional[str] = None


class ExpectedDose(_M):
    n: float
    unit: str
    calc: str


class User(_M):
    username: str
    name: str
    role: Role
    title: str


class Snapshot(_M):
    sim: float
    paused: bool
    patients: list[Patient]
    alerts: list[Alert]
    heldBack: list[Alert]
    log: list[dict]
    discharged: list[dict]
    scenarios: list[dict]
