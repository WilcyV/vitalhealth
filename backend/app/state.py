"""In-memory unit state (Person 1). Port of frontend/src/api/mock.ts.

Holds patients, runs the Vital engine after every change, tracks acknowledged / overridden
alerts, keeps the audit log, simulates bedside monitors and builds the Snapshot pushed to
every client. Pure Python: the web layer (main.py) only checks the session and permissions,
calls one method here and broadcasts.

Every action method takes the acting `User` and returns a Result dict: {"ok", "error"?, "id"?}.

Later: patients/labs/orders from HAPI FHIR, audit log + overrides + co-signs in PostgreSQL.
"""
from __future__ import annotations

import copy
import math
import random
import re
from dataclasses import dataclass
from typing import Callable, Optional

from vital import check_new_medication, evaluate, expected_dose
from vital.data import catalog, load_json, reference
from vital.models import Alert, Allergy, CareTask, LabValue, Medication, Patient, Snapshot, User
from vital.util import is_active, is_high_alert

SIM_PER_TICK = 0.5  # demo minutes per monitor update
VITAL_KEYS = ("sbp", "dbp", "hr", "rr", "spo2")
STEP = {"sbp": 6, "dbp": 4, "hr": 4, "rr": 1.6, "spo2": 1.3}
NOISE = {"sbp": 3, "dbp": 2, "hr": 3, "rr": 0.8, "spo2": 0.7}
BED_RE = re.compile(r"^\d{3}[A-D]$")

Result = dict


def js_round(x: float) -> int:
    return math.floor(x + 0.5)


# ---- demo scenarios (same keys, labels and effects as mock.ts) ---------------------------------
@dataclass
class Scenario:
    key: str
    pid: str
    label: str
    log: str
    run: Callable[["UnitState", Patient], None]
    lab: Optional[str] = None
    vit: tuple[str, ...] = ()


def _targets(**v: float) -> Callable[["UnitState", Patient], None]:
    def run(_s: "UnitState", p: Patient) -> None:
        for k, x in v.items():
            setattr(p.target, k, x)
    return run


def _lab(key: str, v: float) -> Callable[["UnitState", Patient], None]:
    return lambda s, p: s.set_lab(p, key, v)


def _med(**m) -> Callable[["UnitState", Patient], None]:
    return lambda s, p: s.add_med(p, dict(m))


SCENARIOS: list[Scenario] = [
    Scenario("bp", "p1", "Blood pressure drops", "Monitor: BP trending down", _targets(sbp=82, dbp=46, hr=52), vit=("sbp", "dbp", "hr")),
    Scenario("k", "p1", "Potassium result: 5.8", "Lab resulted: K+ 5.8 mmol/L", _lab("k", 5.8), lab="k"),
    Scenario("cr", "p2", "Creatinine rises to 2.8", "Lab resulted: creatinine 2.8 mg/dL", _lab("cr", 2.8), lab="cr"),
    Scenario("glu", "p2", "Fingerstick glucose: 58", "POC glucose 58 mg/dL", _lab("glu", 58), lab="glu"),
    Scenario("amox", "p2", "Amoxicillin-clav ordered", "New order: amoxicillin-clavulanate",
             _med(name="Amoxicillin-clavulanate", dose="875 mg", route="PO", freq="BID", due="10:00", cls=["penicillin"])),
    Scenario("norco", "p4", "Norco ordered", "New order: hydrocodone/acetaminophen",
             _med(name="Hydrocodone/APAP 5/325", dose="1 tab", route="PO", freq="q4h PRN pain", due="PRN", cls=["opioid"], apap=1950)),
    Scenario("resp", "p4", "Breathing slows", "Monitor: RR and SpO2 trending down", _targets(rr=9, spo2=88, hr=64), vit=("rr", "spo2", "hr")),
    Scenario("inr", "p3", "INR result: 4.8", "Lab resulted: INR 4.8", _lab("inr", 4.8), lab="inr"),
    Scenario("hgb", "p10", "Hemoglobin drops to 6.6", "Lab resulted: hemoglobin 6.6 g/dL", _lab("hgb", 6.6), lab="hgb"),
    Scenario("nsaid", "p3", "Ibuprofen ordered", "New order: ibuprofen",
             _med(name="Ibuprofen", dose="600 mg", route="PO", freq="q6h PRN pain", due="PRN", cls=["NSAID"])),
]


@dataclass
class UndoInfo:
    at: float
    lab: Optional[LabValue]
    new_med: Optional[str]


def init_patient(seed: dict) -> Patient:
    """Seed record → live patient with monitor targets, 24 points of history and fresh order status."""
    seed = copy.deepcopy(seed)
    hist: dict[str, list[float]] = {k: [] for k in VITAL_KEYS}
    for _ in range(24):
        for k in VITAL_KEYS:
            spread = 1 if k in ("spo2", "rr") else 4
            hist[k].append(js_round(seed["vit"][k] + (random.random() - 0.5) * spread))
    seed["target"] = dict(seed["vit"])
    seed["base"] = dict(seed["vit"])
    seed["hist"] = hist
    seed["meds"] = [{**m, "status": "due", "at": None} for m in seed.get("meds", [])]
    seed["tasks"] = [{**t, "done": False, "at": None} for t in seed.get("tasks", [])]
    return Patient(**seed)


def _allergy_dump(items: list[Allergy]) -> list[dict]:
    return [a.model_dump(exclude_none=True) for a in items]


class UnitState:
    def __init__(self) -> None:
        self.users: list[dict] = load_json("users.demo.json")  # demo only — production uses SSO
        self.beds: list[str] = reference()["beds"]
        self.reset()

    # ---- lifecycle ------------------------------------------------------------------------------
    def reset(self) -> None:
        self.sim: float = 0
        self.paused = False
        self.patients: list[Patient] = [init_patient(s) for s in load_json("patients.json")]
        self.alerts: list[Alert] = []
        self.seen: dict[str, float] = {}
        self.acked: dict[str, bool] = {}
        self.overrides: dict[str, str] = {}
        self.used: dict[str, UndoInfo] = {}
        self.log: list[dict] = []
        self.discharged: list[dict] = []
        self.next_id = 100
        self.booted = False
        self.add_log(f"Shift started. Monitoring {len(self.patients)} patients.")
        self.run_rules()
        self.booted = True

    def tick(self) -> None:
        """One monitor update: move every vital toward its target, add noise, re-run the rules."""
        self.sim += SIM_PER_TICK
        for p in self.patients:
            for k in VITAL_KEYS:
                cur, tgt = getattr(p.vit, k), getattr(p.target, k)
                d = tgt - cur
                cur += max(-STEP[k], min(STEP[k], d)) + ((random.random() - 0.5) * NOISE[k] if abs(d) < 2 else 0)
                if abs(cur - tgt) > 4 and abs(d) < 2:
                    cur = tgt
                if k == "spo2":
                    cur = min(100, cur)
                setattr(p.vit, k, cur)
                p.hist[k].append(js_round(cur))
                if len(p.hist[k]) > 30:
                    p.hist[k].pop(0)
        self.run_rules()

    # ---- helpers --------------------------------------------------------------------------------
    def by_id(self, pid: str) -> Optional[Patient]:
        return next((p for p in self.patients if p.id == pid), None)

    def med(self, pid: str, mid: str) -> Optional[Medication]:
        p = self.by_id(pid)
        return next((m for m in p.meds if m.id == mid), None) if p else None

    def alert(self, aid: str) -> Optional[Alert]:
        return next((a for a in self.alerts if a.id == aid), None)

    def add_log(self, text: str, kind: str = "", user: Optional[User] = None) -> None:
        """Audit log. Every action records who did it. TODO: also persist to PostgreSQL."""
        self.log.append({"t": self.sim, "text": text + (f" — {user.name}" if user else ""), "kind": kind})

    @staticmethod
    def label(p: Patient) -> str:
        return f"{p.bed} {p.name}"

    def find_user(self, username: Optional[str]) -> Optional[dict]:
        return next((u for u in self.users if u["username"] == username), None)

    # ---- engine ---------------------------------------------------------------------------------
    def resolved(self, a: Alert) -> bool:
        if a.id in self.overrides:
            return True
        if (a.sev == "warn" or not a.meds) and self.acked.get(a.id):
            return True
        if not a.meds:
            return False
        p = self.by_id(a.pid)
        if not p:
            return False
        return all((m := next((x for x in p.meds if x.id == mid), None)) is None or not is_active(m) for mid in a.meds)

    def run_rules(self) -> None:
        """Re-check every patient; log alerts the first time they appear; forget alerts that cleared."""
        found: list[Alert] = [a for p in self.patients for a in evaluate(p, self.sim)]
        live = {a.id for a in found}
        for a in found:
            if a.id not in self.seen:
                self.seen[a.id] = self.sim
                p = self.by_id(a.pid)
                if self.booted and a.sev != "info" and p:
                    self.add_log(f"{self.label(p)} · {a.title}", "crit" if a.sev == "crit" else "warn")
        for aid in [x for x in self.seen if x not in live]:
            self.seen.pop(aid, None)
            self.overrides.pop(aid, None)
            self.acked.pop(aid, None)
        for a in found:
            a.firstSeen = self.seen[a.id]
        self.alerts = found

    def active_alerts_for(self, pid: str, mid: str) -> list[Alert]:
        return [a for a in self.alerts
                if a.pid == pid and a.sev != "info" and not a.timing and mid in a.meds and not self.resolved(a)]

    def set_lab(self, p: Patient, key: str, v: float) -> None:
        cur: Optional[LabValue] = getattr(p.labs, key, None)
        setattr(p.labs, key, LabValue(v=v, t=self.sim, prev=cur.v if cur else None))

    def add_med(self, p: Patient, m: dict) -> Medication:
        n = len(p.meds) + 1
        while any(x.id == f"n{n}" for x in p.meds):
            n += 1
        med = Medication(**{k: v for k, v in m.items() if v is not None},
                         id=f"n{n}", status="due", at=None, isNew=True, orderedAt=self.sim)
        p.meds.append(med)
        return med

    def snapshot(self) -> Snapshot:
        scenarios = []
        for s in SCENARIOS:
            p = self.by_id(s.pid)
            if p:
                scenarios.append({"key": s.key, "pid": s.pid, "label": s.label,
                                  "patientLabel": f"{p.bed} · {p.name}", "used": s.key in self.used})
        return Snapshot(
            sim=self.sim, paused=self.paused, patients=copy.deepcopy(self.patients),
            alerts=[a for a in self.alerts if a.sev != "info" and not self.resolved(a)],
            heldBack=[a for a in self.alerts if a.sev == "info"],
            log=list(reversed(self.log[-60:])), discharged=list(self.discharged), scenarios=scenarios,
        )

    # ---- administration -------------------------------------------------------------------------
    def check_administration(self, pid: str, mid: str) -> dict:
        p, m = self.by_id(pid), self.med(pid, mid)
        if not p or not m:
            return {"blocking": [], "highAlert": False, "expected": None}
        hi = is_high_alert(m)
        return {"blocking": copy.deepcopy(self.active_alerts_for(pid, mid)), "highAlert": hi,
                "expected": expected_dose(p, m) if hi else None}

    def give(self, user: User, pid: str, mid: str, override_reason: Optional[str] = None,
             cosigner: Optional[str] = None, cosign_pin: Optional[str] = None, cosign_dose: Optional[float] = None) -> Result:
        p, m = self.by_id(pid), self.med(pid, mid)
        if not p or not m or not is_active(m):
            return {"ok": False, "error": "This order is no longer active."}
        reason = (override_reason or "").strip() or None
        blocking = self.active_alerts_for(pid, mid)
        if blocking and not reason:
            return {"ok": False, "error": "Vital alerts must be reviewed and a reason given before giving."}
        e = expected_dose(p, m) if is_high_alert(m) else None
        if e is not None:
            if not cosigner:
                return {"ok": False, "error": "High-alert medication: a second nurse must co-sign."}
            co = self.find_user(cosigner)
            if not co or co["role"] not in ("nurse", "charge"):
                return {"ok": False, "error": "The co-signer must be a nurse."}
            if co["username"] == user.username:
                return {"ok": False, "error": "The double-check must be done by a different nurse."}
            if co["pin"] != cosign_pin:
                return {"ok": False, "error": f"{co['name']}: that PIN doesn’t match."}
            if cosign_dose is None or math.isnan(e.n) or abs(cosign_dose - e.n) > 1e-6:
                self.add_log(f"{self.label(p)} · Double-check caught a mismatch on {m.name}: {co['name']} got "
                             f"{_num(cosign_dose)} {e.unit}, calculated dose is {_num(e.n)} {e.unit}. Not given.", "crit", user)
                return {"ok": False, "error": f"Doses don't match. {co['name']} entered {_num(cosign_dose)} {e.unit}, but the "
                                              f"calculated dose is {_num(e.n)} {e.unit}. {e.calc}. Stop and recalculate together before giving."}
            m.cosign = co["name"]
        if reason:
            for a in blocking:
                self.overrides[a.id] = reason
            self.add_log(f'{self.label(p)} · Override on {m.name}: "{reason}"', "warn", user)
        m.status, m.at = "given", self.sim
        amount = f"{_num(e.n)} {e.unit}" if e else m.dose
        text = f"{self.label(p)} · Gave {m.name} {amount}."
        if m.cosign:
            text += f" Double-checked by {m.cosign}."
        if not reason:
            text += " All checks passed."
        self.add_log(text, "warn" if reason else "ok", user)
        self.run_rules()
        return {"ok": True}

    def hold(self, user: User, pid: str, mid: str, reason: str) -> Result:
        p, m = self.by_id(pid), self.med(pid, mid)
        if not p or not m:
            return {"ok": False, "error": "Order not found."}
        if not reason.strip():
            return {"ok": False, "error": "Enter a reason for holding this medication."}
        m.status, m.at = "held", self.sim
        self.add_log(f"{self.label(p)} · Held {m.name}. Reason: {reason.strip()}", "ok", user)
        self.run_rules()
        return {"ok": True}

    def hold_for_alert(self, user: User, aid: str) -> Result:
        a = self.alert(aid)
        p = self.by_id(a.pid) if a else None
        if not a or not p:
            return {"ok": False, "error": "This alert is no longer active."}
        names = []
        for mid in a.meds:
            m = next((x for x in p.meds if x.id == mid), None)
            if m and is_active(m):
                m.status, m.at = "held", self.sim
                names.append(m.name)
        self.add_log(f"{self.label(p)} · Held {', '.join(names)}. Reason: {a.title}", "ok", user)
        self.run_rules()
        return {"ok": True}

    def discontinue(self, user: User, pid: str, mid: str) -> Result:
        p = self.by_id(pid)
        m = self.med(pid, mid)
        if not p or not m:
            return {"ok": False, "error": "Order not found."}
        p.meds = [x for x in p.meds if x is not m]
        for key in [k for k, u in self.used.items() if u.new_med == mid and _scenario(k) and _scenario(k).pid == pid]:
            del self.used[key]
        self.add_log(f"{self.label(p)} · Discontinued {m.name}", "", user)
        self.run_rules()
        return {"ok": True}

    # ---- new orders -----------------------------------------------------------------------------
    def check_medication(self, pid: str, drug_key: str) -> list:
        p, d = self.by_id(pid), _drug(drug_key)
        return check_new_medication(p, d) if p and d else []

    def suggest_alternatives(self, pid: str, drug_key: str) -> list[dict]:
        """Same group, not already ordered, no critical issue; fewest issues first; max 3."""
        p, d = self.by_id(pid), _drug(drug_key)
        if not p or not d:
            return []
        out = []
        for x in catalog():
            if x.group != d.group or x.key == d.key:
                continue
            if any(is_active(m) and (m.catKey == x.key or m.name == x.name) for m in p.meds):
                continue
            issues = check_new_medication(p, x)
            if not any(i.sev == "crit" for i in issues):
                out.append({"drug": x, "issues": issues})
        out.sort(key=lambda a: len(a["issues"]))  # stable, like Array.prototype.sort
        return out[:3]

    def order(self, user: User, pid: str, drug_key: str, override_reason: Optional[str] = None) -> Result:
        p, d = self.by_id(pid), _drug(drug_key)
        if not p or not d:
            return {"ok": False, "error": "Unknown patient or drug."}
        reason = (override_reason or "").strip() or None
        issues = check_new_medication(p, d)
        if any(i.sev == "crit" for i in issues) and not reason:
            return {"ok": False, "error": "Critical issues found. A reason is required to order anyway."}
        med = self.add_med(p, {"name": d.name, "dose": d.dose, "route": d.route, "freq": d.freq, "due": d.due,
                               "cls": list(d.cls), "apap": d.apap, "catKey": d.key})
        tail = f'. Ordered despite Vital warning: "{reason}"' if reason else ". Passed Vital check."
        self.add_log(f"{self.label(p)} · New order: {d.name} {d.dose}{tail}", "warn" if reason else "ok", user)
        self.run_rules()
        return {"ok": True, "id": med.id}

    # ---- alerts & tasks -------------------------------------------------------------------------
    def acknowledge(self, user: User, aid: str) -> Result:
        a = self.alert(aid)
        p = self.by_id(a.pid) if a else None
        if not a or not p:
            return {"ok": False, "error": "This alert is no longer active."}
        self.acked[aid] = True
        self.add_log(f"{self.label(p)} · Acknowledged: {a.title}", "", user)
        return {"ok": True}

    def complete_task(self, user: User, pid: str, tid: str) -> Result:
        p = self.by_id(pid)
        t: Optional[CareTask] = next((x for x in p.tasks if x.id == tid), None) if p else None
        if not p or not t:
            return {"ok": False, "error": "Task not found."}
        t.done, t.at = True, self.sim
        late = self.sim > t.due + t.grace
        suffix = f" ({math.floor(self.sim - t.due)} min late)" if late else ""
        self.add_log(f"{self.label(p)} · Done: {t.name}{suffix}", "warn" if late else "ok", user)
        self.run_rules()
        return {"ok": True}

    # ---- patients -------------------------------------------------------------------------------
    def validate(self, inp: dict, except_pid: Optional[str] = None) -> Optional[str]:
        if not inp["name"].strip():
            return "Enter the patient’s name."
        if not (0 <= inp["age"] <= 120):
            return "Enter an age between 0 and 120."
        if not (0 < inp["wt"] < 400):
            return "Enter a weight in kg. Vital uses it for kidney function and dosing."
        if not BED_RE.match(inp["bed"]):
            return "Bed must be a room number and letter, like 412A."
        clash = next((p for p in self.patients if p.bed == inp["bed"] and p.id != except_pid), None)
        if clash:
            return f"Bed {inp['bed']} is taken by {clash.name}. Choose another bed or tap Random."
        if any(not a["agent"].strip() for a in inp["allergies"]):
            return "Enter the name of each allergen, or remove that row."
        return None

    def admit(self, user: User, inp: dict) -> Result:
        err = self.validate(inp)
        if err:
            return {"ok": False, "error": err}
        pid = f"p{self.next_id}"
        self.next_id += 1
        lab = lambda v: {"v": v, "t": self.sim}  # noqa: E731
        p = init_patient({
            "id": pid, "bed": inp["bed"], "name": inp["name"].strip(), "age": inp["age"], "sex": inp["sex"], "wt": inp["wt"],
            "dx": inp["dx"].strip() or "Admitted", "conditions": inp["conditions"], "allergies": inp["allergies"],
            "vit": {"sbp": 124, "dbp": 76, "hr": 80, "rr": 16, "spo2": 97},
            "labs": {"k": lab(4.2), "cr": lab(0.9), "glu": lab(110)}, "meds": [], "tasks": [],
        })
        p.otherConds = inp["otherConds"]
        self.patients.append(p)
        allergies = inp["allergies"]
        tail = f" · allergies: {', '.join(a['agent'] for a in allergies)}" if allergies else " · no known drug allergies"
        self.add_log(f"{self.label(p)} · Admitted{tail}", "ok", user)
        self.run_rules()
        return {"ok": True, "id": pid}

    def update_patient(self, user: User, pid: str, inp: dict) -> Result:
        p = self.by_id(pid)
        if not p:
            return {"ok": False, "error": "Patient not found."}
        err = self.validate(inp, pid)
        if err:
            return {"ok": False, "error": err}
        name, dx = inp["name"].strip(), inp["dx"].strip()
        new_allergies = [Allergy(**a) for a in inp["allergies"]]
        changes = []
        if p.name != name: changes.append("name")  # noqa: E701
        if p.age != inp["age"]: changes.append("age")  # noqa: E701
        if p.sex != inp["sex"]: changes.append("gender")  # noqa: E701
        if p.wt != inp["wt"]: changes.append("weight")  # noqa: E701
        if p.bed != inp["bed"]: changes.append(f"bed {p.bed} → {inp['bed']}")  # noqa: E701
        if _allergy_dump(p.allergies) != _allergy_dump(new_allergies): changes.append("allergies")  # noqa: E701
        if p.dx != dx: changes.append("diagnosis")  # noqa: E701
        if p.conditions != inp["conditions"] or (p.otherConds or []) != inp["otherConds"]: changes.append("conditions")  # noqa: E701
        p.name, p.age, p.sex, p.wt, p.bed = name, inp["age"], inp["sex"], inp["wt"], inp["bed"]
        p.dx = dx or p.dx
        p.conditions, p.otherConds, p.allergies = list(inp["conditions"]), list(inp["otherConds"]), new_allergies
        what = ": " + ", ".join(changes) if changes else ""
        self.add_log(f"{self.label(p)} · Patient info updated{what}. Vital re-checked all medications.", "", user)
        self.run_rules()
        return {"ok": True}

    def discharge(self, user: User, pid: str) -> Result:
        p = self.by_id(pid)
        if not p:
            return {"ok": False, "error": "Patient not found."}
        self.patients = [x for x in self.patients if x is not p]
        self.discharged.insert(0, {"name": p.name, "bed": p.bed, "at": self.sim})
        self.add_log(f"{self.label(p)} · Discharged. Bed {p.bed} is now free.", "ok", user)
        self.run_rules()
        return {"ok": True}

    def suggest_bed(self, except_pid: Optional[str] = None) -> str:
        taken = {p.bed for p in self.patients if p.id != except_pid}
        free = [b for b in self.beds if b not in taken]
        return random.choice(free) if free else ""

    # ---- demo controls --------------------------------------------------------------------------
    def trigger_scenario(self, key: str) -> Result:
        """Run a demo scenario; running it again undoes it (lab value, monitor targets, new order)."""
        s = _scenario(key)
        p = self.by_id(s.pid) if s else None
        if not s or not p:
            return {"ok": False, "error": "Unknown scenario."}
        u = self.used.get(key)
        if u:
            if s.lab and u.lab is not None:
                setattr(p.labs, s.lab, u.lab)
            for k in s.vit:
                setattr(p.target, k, getattr(p.base, k))
            if u.new_med:
                p.meds = [m for m in p.meds if m.id != u.new_med]
            for m in p.meds:
                if not is_active(m) and (m.at if m.at is not None else -1) >= u.at:
                    m.status, m.at = "due", None
            del self.used[key]
            self.add_log(f"{self.label(p)} · Undid: {s.label}")
        else:
            lab = getattr(p.labs, s.lab, None) if s.lab else None
            info = UndoInfo(at=self.sim, lab=copy.deepcopy(lab), new_med=None)
            before = len(p.meds)
            s.run(self, p)
            info.new_med = p.meds[-1].id if len(p.meds) > before else None
            self.used[key] = info
            self.add_log(f"{self.label(p)} · {s.log}")
        self.run_rules()
        return {"ok": True}

    def skip(self, minutes: float) -> Result:
        if not (0 < minutes <= 24 * 60):
            return {"ok": False, "error": "Skip between 1 minute and 24 hours."}
        self.sim += minutes - SIM_PER_TICK
        self.add_log(f"Clock moved forward {_num(minutes)} min (demo)")
        self.tick()
        return {"ok": True}

    def set_paused(self, paused: bool) -> Result:
        self.paused = paused
        return {"ok": True}


def _scenario(key: str) -> Optional[Scenario]:
    return next((s for s in SCENARIOS if s.key == key), None)


def _drug(key: str):
    return next((d for d in catalog() if d.key == key), None)


def _num(x: Optional[float]) -> str:
    """Format a number the way JS template strings do (5.0 → "5", None → "undefined")."""
    if x is None:
        return "undefined"
    if isinstance(x, float) and math.isnan(x):
        return "NaN"
    return f"{x:g}" if float(x) != int(x) else str(int(x))


STATE = UnitState()
