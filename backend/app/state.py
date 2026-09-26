"""In-memory unit state (Person 1). Port of frontend/src/api/mock.ts.

Holds the patients, simulates the bedside monitors, runs the Vital engine after every change,
tracks acknowledged/overridden alerts, keeps the audit log and builds the Snapshot pushed to
every client. Every action returns a Result dict: {"ok": bool, "error"?: str, "id"?: str}.

Next steps (see NEXT_STEPS.md): swap the seed data for HAPI FHIR + Synthea and write the audit
log, overrides and co-signs to PostgreSQL. Keep the method signatures and the server won't change.
"""
from __future__ import annotations

import copy
import math
import random
import re
from dataclasses import dataclass
from typing import Callable, Optional

from vital import evaluate, expected_dose
from vital.data import load_json, reference
from vital.models import Alert, Allergy, CareTask, LabValue, Medication, Patient, Snapshot, User
from vital.util import is_active, is_high_alert

TICK_SECONDS = 2.0        # real time between monitor updates
SIM_PER_TICK = 0.5        # demo minutes per tick
VITAL_KEYS = ("sbp", "dbp", "hr", "rr", "spo2")
STEP = {"sbp": 6, "dbp": 4, "hr": 4, "rr": 1.6, "spo2": 1.3}
NOISE = {"sbp": 3, "dbp": 2, "hr": 3, "rr": 0.8, "spo2": 0.7}
BED_RE = re.compile(r"^\d{3}[A-D]$")

USERS: list[dict] = load_json("users.demo.json")  # demo only — production uses hospital SSO
BED_POOL: list[str] = reference()["beds"]

Result = dict


def ok(**extra) -> Result:
    return {"ok": True, **extra}


def fail(error: Optional[str] = None) -> Result:
    return {"ok": False, "error": error} if error else {"ok": False}


# ---- demo scenarios (same keys, labels and effects as mock.ts) ---------------------------
@dataclass
class Scenario:
    key: str
    pid: str
    label: str
    log: str
    run: Callable[["UnitState", Patient], None]
    lab: Optional[str] = None
    vit: tuple[str, ...] = ()


def _targets(**values: float) -> Callable[["UnitState", Patient], None]:
    def run(_s: "UnitState", p: Patient) -> None:
        for k, v in values.items():
            setattr(p.target, k, v)
    return run


def _lab(key: str, v: float) -> Callable[["UnitState", Patient], None]:
    return lambda s, p: s.set_lab(p, key, v)


def _order(**med) -> Callable[["UnitState", Patient], None]:
    return lambda s, p: s.add_med(p, med)


SCENARIOS: list[Scenario] = [
    Scenario("bp", "p1", "Blood pressure drops", "Monitor: BP trending down", _targets(sbp=82, dbp=46, hr=52), vit=("sbp", "dbp", "hr")),
    Scenario("k", "p1", "Potassium result: 5.8", "Lab resulted: K+ 5.8 mmol/L", _lab("k", 5.8), lab="k"),
    Scenario("cr", "p2", "Creatinine rises to 2.8", "Lab resulted: creatinine 2.8 mg/dL", _lab("cr", 2.8), lab="cr"),
    Scenario("glu", "p2", "Fingerstick glucose: 58", "POC glucose 58 mg/dL", _lab("glu", 58), lab="glu"),
    Scenario("amox", "p2", "Amoxicillin-clav ordered", "New order: amoxicillin-clavulanate",
             _order(name="Amoxicillin-clavulanate", dose="875 mg", route="PO", freq="BID", due="10:00", cls=["penicillin"])),
    Scenario("norco", "p4", "Norco ordered", "New order: hydrocodone/acetaminophen",
             _order(name="Hydrocodone/APAP 5/325", dose="1 tab", route="PO", freq="q4h PRN pain", due="PRN", cls=["opioid"], apap=1950)),
    Scenario("resp", "p4", "Breathing slows", "Monitor: RR and SpO2 trending down", _targets(rr=9, spo2=88, hr=64), vit=("rr", "spo2", "hr")),
    Scenario("inr", "p3", "INR result: 4.8", "Lab resulted: INR 4.8", _lab("inr", 4.8), lab="inr"),
    Scenario("hgb", "p10", "Hemoglobin drops to 6.6", "Lab resulted: hemoglobin 6.6 g/dL", _lab("hgb", 6.6), lab="hgb"),
    Scenario("nsaid", "p3", "Ibuprofen ordered", "New order: ibuprofen",
             _order(name="Ibuprofen", dose="600 mg", route="PO", freq="q6h PRN pain", due="PRN", cls=["NSAID"])),
]
SCENARIO_BY_KEY = {s.key: s for s in SCENARIOS}


@dataclass
class UndoInfo:
    at: float
    lab: Optional[LabValue]
    new_med: Optional[str]


def init_patient(seed: dict) -> Patient:
    """A seed patient as it looks at the start of the shift (same as initPatient in mock.ts)."""
    seed = copy.deepcopy(seed)
    vit = seed["vit"]
    hist = {k: [] for k in VITAL_KEYS}
    for _ in range(24):
        for k in VITAL_KEYS:
            spread = 1 if k in ("spo2", "rr") else 4
            hist[k].append(math.floor(vit[k] + (random.random() - 0.5) * spread + 0.5))
    seed["meds"] = [{**m, "status": "due", "at": None} for m in seed.get("meds", [])]
    seed["tasks"] = [{**t, "done": False, "at": None} for t in seed.get("tasks", [])]
    return Patient(**seed, target=dict(vit), base=dict(vit), hist=hist)


class UnitState:
    def __init__(self) -> None:
        self.reset()

    # ---------- lifecycle ----------
    def reset(self) -> None:
        self.sim: float = 0
        self.paused = False
        self.booted = False
        self.seen: dict[str, float] = {}
        self.acked: dict[str, bool] = {}
        self.overrides: dict[str, str] = {}
        self.used: dict[str, UndoInfo] = {}
        self.log: list[dict] = []
        self.discharged: list[dict] = []
        self.alerts: list[Alert] = []
        self.next_id = 100
        self.patients: list[Patient] = [init_patient(s) for s in load_json("patients.json")]
        self.add_log(f"Shift started. Monitoring {len(self.patients)} patients.")
        self.run_rules()
        self.booted = True

    def tick(self) -> None:
        """One monitor update: vitals drift toward their targets, then every rule re-runs.

        The time-critical scheduler lives in the engine: `evaluate()` compares each
        time-critical dose / care task with `sim`, so re-running rules every tick escalates
        late items from warning to critical automatically.
        """
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
                p.hist[k].append(math.floor(cur + 0.5))
                if len(p.hist[k]) > 30:
                    p.hist[k].pop(0)
        self.run_rules()

    # ---------- helpers ----------
    def by_id(self, pid: str) -> Optional[Patient]:
        return next((p for p in self.patients if p.id == pid), None)

    def med(self, pid: str, mid: str) -> Optional[Medication]:
        p = self.by_id(pid)
        return next((m for m in p.meds if m.id == mid), None) if p else None

    @staticmethod
    def label(p: Patient) -> str:
        return f"{p.bed} {p.name}"

    @staticmethod
    def by(user: Optional[User]) -> str:
        return f" — {user.name}" if user else ""

    def add_log(self, text: str, kind: str = "", user: Optional[User] = None) -> None:
        """Audit log entry. TODO(Person 1): also INSERT into PostgreSQL with user + timestamp."""
        self.log.append({"t": self.sim, "text": text + self.by(user), "kind": kind})

    # ---------- engine ----------
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
        found = [a for p in self.patients for a in evaluate(p, self.sim)]
        live = {a.id for a in found}
        for a in found:
            if a.id not in self.seen:
                self.seen[a.id] = self.sim
                if self.booted and a.sev != "info":
                    p = self.by_id(a.pid)
                    self.add_log(f"{self.label(p)} · {a.title}", "crit" if a.sev == "crit" else "warn")
        for aid in list(self.seen):
            if aid not in live:
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
        cur = getattr(p.labs, key, None)
        setattr(p.labs, key, LabValue(v=v, t=self.sim, prev=cur.v if cur else None))

    def add_med(self, p: Patient, m: dict) -> Medication:
        n = len(p.meds) + 1
        while any(x.id == f"n{n}" for x in p.meds):
            n += 1
        med = Medication(**{k: v for k, v in m.items() if v is not None}, id=f"n{n}", status="due", at=None,
                         isNew=True, orderedAt=self.sim)
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
            sim=self.sim, paused=self.paused, patients=self.patients,
            alerts=[a for a in self.alerts if a.sev != "info" and not self.resolved(a)],
            heldBack=[a for a in self.alerts if a.sev == "info"],
            log=list(reversed(self.log[-60:])), discharged=self.discharged, scenarios=scenarios,
        )

    # ---------- administration ----------
    def check_administration(self, pid: str, mid: str) -> dict:
        p, m = self.by_id(pid), self.med(pid, mid)
        if not p or not m:
            return {"blocking": [], "highAlert": False, "expected": None}
        hi = is_high_alert(m)
        return {"blocking": self.active_alerts_for(pid, mid), "highAlert": hi,
                "expected": expected_dose(p, m) if hi else None}

    def give(self, user: User, pid: str, mid: str, override_reason: Optional[str] = None,
             cosigner: Optional[str] = None, cosign_pin: Optional[str] = None,
             cosign_dose: Optional[float] = None) -> Result:
        p, m = self.by_id(pid), self.med(pid, mid)
        if not p or not m or not is_active(m):
            return fail("This order is no longer active.")
        override_reason = (override_reason or "").strip() or None
        blocking = self.active_alerts_for(pid, mid)
        if blocking and not override_reason:
            return fail("Vital alerts must be reviewed and a reason given before giving.")
        e = expected_dose(p, m) if is_high_alert(m) else None
        if e is not None:
            if not cosigner:
                return fail("High-alert medication: a second nurse must co-sign.")
            co = next((u for u in USERS if u["username"] == cosigner), None)
            if not co or co["role"] not in ("nurse", "charge"):
                return fail("The co-signer must be a nurse.")
            if co["username"] == user.username:
                return fail("The double-check must be done by a different nurse.")
            if co["pin"] != cosign_pin:
                return fail(f"{co['name']}: that PIN doesn’t match.")
            if cosign_dose is None or math.isnan(e.n) or abs(cosign_dose - e.n) > 1e-6:
                self.add_log(f"{self.label(p)} · Double-check caught a mismatch on {m.name}: {co['name']} got "
                             f"{_num(cosign_dose)} {e.unit}, calculated dose is {_num(e.n)} {e.unit}. Not given.", "crit", user)
                return fail(f"Doses don't match. {co['name']} entered {_num(cosign_dose)} {e.unit}, but the calculated dose is "
                            f"{_num(e.n)} {e.unit}. {e.calc}. Stop and recalculate together before giving.")
            m.cosign = co["name"]
        if override_reason:
            for a in blocking:
                self.overrides[a.id] = override_reason
            self.add_log(f'{self.label(p)} · Override on {m.name}: "{override_reason}"', "warn", user)
        m.status, m.at = "given", self.sim
        amount = f"{_num(e.n)} {e.unit}" if e is not None else m.dose
        text = f"{self.label(p)} · Gave {m.name} {amount}."
        if m.cosign:
            text += f" Double-checked by {m.cosign}."
        if not override_reason:
            text += " All checks passed."
        self.add_log(text, "warn" if override_reason else "ok", user)
        self.run_rules()
        return ok()

    def hold(self, user: User, pid: str, mid: str, reason: str) -> Result:
        p, m = self.by_id(pid), self.med(pid, mid)
        if not p or not m:
            return fail("Order not found.")
        m.status, m.at = "held", self.sim
        self.add_log(f"{self.label(p)} · Held {m.name}. Reason: {reason}", "ok", user)
        self.run_rules()
        return ok()

    def hold_for_alert(self, user: User, alert_id: str) -> Result:
        a = next((x for x in self.alerts if x.id == alert_id), None)
        p = self.by_id(a.pid) if a else None
        if not a or not p:
            return fail("This alert is no longer active.")
        names = []
        for mid in a.meds:
            m = next((x for x in p.meds if x.id == mid), None)
            if m and is_active(m):
                m.status, m.at = "held", self.sim
                names.append(m.name)
        self.add_log(f"{self.label(p)} · Held {', '.join(names)}. Reason: {a.title}", "ok", user)
        self.run_rules()
        return ok()

    def discontinue(self, user: User, pid: str, mid: str) -> Result:
        p = self.by_id(pid)
        m = self.med(pid, mid)
        if not p or not m:
            return fail("Order not found.")
        p.meds = [x for x in p.meds if x is not m]
        for k in list(self.used):
            if self.used[k].new_med == mid and SCENARIO_BY_KEY[k].pid == pid:
                del self.used[k]
        self.add_log(f"{self.label(p)} · Discontinued {m.name}", "", user)
        self.run_rules()
        return ok()

    # ---------- new orders ----------
    def order(self, user: User, pid: str, drug, issues: list, override_reason: Optional[str] = None) -> Result:
        """`issues` = check_new_medication(patient, drug), computed by the caller."""
        p = self.by_id(pid)
        if not p or not drug:
            return fail("Unknown patient or drug.")
        override_reason = (override_reason or "").strip() or None
        if any(i.sev == "crit" for i in issues) and not override_reason:
            return fail("Critical issues found. A reason is required to order anyway.")
        self.add_med(p, {"name": drug.name, "dose": drug.dose, "route": drug.route, "freq": drug.freq, "due": drug.due,
                         "cls": list(drug.cls), "apap": drug.apap, "catKey": drug.key})
        tail = f'. Ordered despite Vital warning: "{override_reason}"' if override_reason else ". Passed Vital check."
        self.add_log(f"{self.label(p)} · New order: {drug.name} {drug.dose}{tail}", "warn" if override_reason else "ok", user)
        self.run_rules()
        return ok()

    # ---------- alerts & tasks ----------
    def acknowledge(self, user: User, alert_id: str) -> Result:
        a = next((x for x in self.alerts if x.id == alert_id), None)
        p = self.by_id(a.pid) if a else None
        if not a or not p:
            return fail("This alert is no longer active.")
        self.acked[alert_id] = True
        self.add_log(f"{self.label(p)} · Acknowledged: {a.title}", "", user)
        return ok()

    def complete_task(self, user: User, pid: str, task_id: str) -> Result:
        p = self.by_id(pid)
        t: Optional[CareTask] = next((x for x in p.tasks if x.id == task_id), None) if p else None
        if not p or not t:
            return fail("Task not found.")
        t.done, t.at = True, self.sim
        late = self.sim > t.due + t.grace
        suffix = f" ({math.floor(self.sim - t.due)} min late)" if late else ""
        self.add_log(f"{self.label(p)} · Done: {t.name}{suffix}", "warn" if late else "ok", user)
        self.run_rules()
        return ok()

    # ---------- patients ----------
    def validate(self, data: dict, except_pid: Optional[str] = None) -> Optional[str]:
        if not (data.get("name") or "").strip():
            return "Enter the patient’s name."
        age, wt = data.get("age"), data.get("wt")
        if age is None or not (0 <= age <= 120):
            return "Enter an age between 0 and 120."
        if wt is None or not (0 < wt < 400):
            return "Enter a weight in kg. Vital uses it for kidney function and dosing."
        bed = data.get("bed") or ""
        if not BED_RE.match(bed):
            return "Bed must be a room number and letter, like 412A."
        clash = next((p for p in self.patients if p.bed == bed and p.id != except_pid), None)
        if clash:
            return f"Bed {bed} is taken by {clash.name}. Choose another bed or tap Random."
        if any(not (a.get("agent") or "").strip() for a in data.get("allergies", [])):
            return "Enter the name of each allergen, or remove that row."
        return None

    def admit(self, user: User, data: dict) -> Result:
        err = self.validate(data)
        if err:
            return fail(err)
        pid = f"p{self.next_id}"
        self.next_id += 1
        p = init_patient({
            "id": pid, "bed": data["bed"], "name": data["name"].strip(), "age": _int(data["age"]), "sex": data["sex"],
            "wt": data["wt"], "dx": (data.get("dx") or "").strip() or "Admitted",
            "conditions": data.get("conditions", []), "allergies": data.get("allergies", []),
            "vit": {"sbp": 124, "dbp": 76, "hr": 80, "rr": 16, "spo2": 97},
            "labs": {"k": {"v": 4.2, "t": self.sim}, "cr": {"v": 0.9, "t": self.sim}, "glu": {"v": 110, "t": self.sim}},
            "meds": [], "tasks": [],
        })
        p.otherConds = data.get("otherConds", [])
        self.patients.append(p)
        allergies = data.get("allergies", [])
        tail = f" · allergies: {', '.join(a['agent'] for a in allergies)}" if allergies else " · no known drug allergies"
        self.add_log(f"{self.label(p)} · Admitted{tail}", "ok", user)
        self.run_rules()
        return ok(id=pid)

    def update_patient(self, user: User, pid: str, data: dict) -> Result:
        p = self.by_id(pid)
        if not p:
            return fail("Patient not found.")
        err = self.validate(data, pid)
        if err:
            return fail(err)
        name, dx = data["name"].strip(), (data.get("dx") or "").strip()
        allergies = data.get("allergies", [])
        conditions, other = data.get("conditions", []), data.get("otherConds", [])
        changes = []
        if p.name != name: changes.append("name")                         # noqa: E701
        if p.age != data["age"]: changes.append("age")                    # noqa: E701
        if p.sex != data["sex"]: changes.append("gender")                 # noqa: E701
        if p.wt != data["wt"]: changes.append("weight")                   # noqa: E701
        if p.bed != data["bed"]: changes.append(f"bed {p.bed} → {data['bed']}")  # noqa: E701
        if [a.model_dump(exclude_none=True) for a in p.allergies] != allergies: changes.append("allergies")  # noqa: E701
        if p.dx != dx: changes.append("diagnosis")                        # noqa: E701
        if p.conditions != conditions or (p.otherConds or []) != other: changes.append("conditions")  # noqa: E701
        p.name, p.age, p.sex, p.wt, p.bed = name, _int(data["age"]), data["sex"], data["wt"], data["bed"]
        p.dx = dx or p.dx
        p.conditions, p.otherConds = list(conditions), list(other)
        p.allergies = [Allergy(**a) for a in allergies]
        detail = ": " + ", ".join(changes) if changes else ""
        self.add_log(f"{self.label(p)} · Patient info updated{detail}. Vital re-checked all medications.", "", user)
        self.run_rules()
        return ok()

    def discharge(self, user: User, pid: str) -> Result:
        p = self.by_id(pid)
        if not p:
            return fail("Patient not found.")
        self.patients = [x for x in self.patients if x is not p]
        self.discharged.insert(0, {"name": p.name, "bed": p.bed, "at": self.sim})
        self.add_log(f"{self.label(p)} · Discharged. Bed {p.bed} is now free.", "ok", user)
        self.run_rules()
        return ok()

    def suggest_bed(self, except_pid: Optional[str] = None) -> str:
        taken = {p.bed for p in self.patients if p.id != except_pid}
        free = [b for b in BED_POOL if b not in taken]
        return random.choice(free) if free else ""

    # ---------- demo controls ----------
    def trigger_scenario(self, key: str, user: Optional[User] = None) -> Result:
        s = SCENARIO_BY_KEY.get(key)
        p = self.by_id(s.pid) if s else None
        if not s or not p:
            return fail("Unknown scenario.")
        u = self.used.get(key)
        if u:  # pressing it again undoes it
            if s.lab and u.lab:
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
            before = len(p.meds)
            lab = copy.deepcopy(getattr(p.labs, s.lab, None)) if s.lab else None
            s.run(self, p)
            self.used[key] = UndoInfo(at=self.sim, lab=lab, new_med=p.meds[-1].id if len(p.meds) > before else None)
            self.add_log(f"{self.label(p)} · {s.log}")
        self.run_rules()
        return ok()

    def skip(self, minutes: float) -> Result:
        self.sim += minutes - SIM_PER_TICK
        self.add_log(f"Clock moved forward {_num(minutes)} min (demo)")
        self.tick()
        return ok()

    def set_paused(self, paused: bool) -> Result:
        self.paused = paused
        return ok()


def _num(x: Optional[float]) -> str:
    """Format a number like JavaScript's template strings: 4.0 -> '4', None -> 'undefined'."""
    if x is None:
        return "undefined"
    if isinstance(x, float) and math.isnan(x):
        return "NaN"
    return f"{x:g}" if x != int(x) else str(int(x))


def _int(x: float):
    return int(x) if float(x).is_integer() else x


STATE = UnitState()
