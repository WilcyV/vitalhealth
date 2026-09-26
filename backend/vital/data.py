"""Reference data loaded from backend/fixtures (exported from the frontend with `npm run fixtures`).

Person 2: later, replace CATALOG with RxNorm lookups + a curated rules file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import CatalogDrug, Patient, Snapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@lru_cache
def reference() -> dict:
    return load_json("reference.json")


@lru_cache
def catalog() -> list[CatalogDrug]:
    return [CatalogDrug(**d) for d in load_json("catalog.json")]


def drug(key: str) -> CatalogDrug:
    return next(d for d in catalog() if d.key == key)


@lru_cache
def drug_info() -> dict:
    return load_json("drug-info.json")


def snapshot(name: str = "snapshot.json") -> Snapshot:
    return Snapshot(**load_json(name))


def patient(snap: Snapshot, pid: str) -> Patient:
    return next(p for p in snap.patients if p.id == pid)


CONDITIONS: dict = {}
CLASS_LABELS: dict = {}


def _init() -> None:
    ref = reference()
    CONDITIONS.update(ref["conditions"])
    CLASS_LABELS.update(ref["classLabels"])


_init()
