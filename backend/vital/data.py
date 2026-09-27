"""Data access for the server and the engine.

Drug data (catalog, drug reference, class/group labels) lives in `vital/drugs.py`, owned by the
backend. Demo patients, snapshots and the permissions table still come from backend/fixtures
(exported from the frontend with `npm run fixtures`).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import drugs
from .drugs import CLASS_LABELS, CONDITIONS, GROUP_LABELS  # noqa: F401  (re-exported)
from .models import CatalogDrug, Patient, Snapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@lru_cache
def reference() -> dict:
    return load_json("reference.json")


def catalog() -> list[CatalogDrug]:
    return drugs.CATALOG


def drug(key: str) -> CatalogDrug:
    d = drugs.by_key(key)
    if d is None:
        raise KeyError(key)
    return d


def drug_info() -> dict:
    return drugs.DRUG_INFO


def snapshot(name: str = "snapshot.json") -> Snapshot:
    return Snapshot(**load_json(name))


def patient(snap: Snapshot, pid: str) -> Patient:
    return next(p for p in snap.patients if p.id == pid)
