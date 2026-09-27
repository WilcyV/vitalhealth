"""Continuous rules: re-checks every active order for one patient.

Port of frontend/src/engine/rules.ts. `evaluate()` returns every alert for one patient right now
(critical, warning and low-priority "info"). The server calls it after every change to a vital,
lab, order or patient detail.

Alert IDs are identical to the TypeScript version (e.g. "k:p1", "hold:p1:m1", "renal:p2:m1",
"tc:p11:m1:crit"): the server uses them to remember acknowledgements and first-seen times, and
the parity tests compare them with the frontend's output.

Tests:  pytest vital/tests/test_rules.py
"""
from __future__ import annotations

import math

from . import drugs
from .checker import check_new_medication
from .models import Alert, Medication, Patient
from .util import crcl, first_name, fmt, is_active, js_hash, list_names, num, round_vitals, thousands

BP_MED_CLASSES = ("ACEi", "BB", "CCB", "loop")
POTASSIUM_RAISING = ("ACEi", "ARB", "Ksparing")


def evaluate(p: Patient, sim: float) -> list[Alert]:
    """Return all alerts for this patient at demo time `sim` (minutes since 08:40)."""
    alerts: list[Alert] = []
    v = round_vitals(p.vit)
    L = p.labs
    meds = p.meds
    now = fmt(sim)
    first = first_name(p)

    def add(**a) -> None:
        alerts.append(Alert(pid=p.id, **a))

    def cls(c: str) -> list[Medication]:
        return [m for m in meds if c in m.cls]

    def ids(ms: list[Medication]) -> list[str]:
        return [m.id for m in ms]

    # Hold parameters from the order
    for m in meds:
        if not m.hold:
            continue
        r = []
        if m.hold.sbp and v.sbp < m.hold.sbp:
            r.append(f"systolic BP is {num(v.sbp)} (below {num(m.hold.sbp)})")
        if m.hold.hr and v.hr < m.hold.hr:
            r.append(f"heart rate is {num(v.hr)} (below {num(m.hold.hr)})")
        if r:
            add(id=f"hold:{p.id}:{m.id}", sev="crit", meds=[m.id], trigger="Vital sign change",
                title=f"Hold {m.name}: below ordered parameter",
                why=f'{first}\'s {" and ".join(r)}. The order says "{m.param}." {m.name} lowers {m.effect} and would push them lower.',
                data=[f"BP {num(v.sbp)}/{num(v.dbp)} mmHg · HR {num(v.hr)} · bedside monitor · {now}",
                      f"Order: {m.name} {m.dose} {m.route} {m.freq} · {m.param}"],
                action="Hold this dose. Recheck vitals in 15 minutes and notify the provider.")

    # BP trend (before it crosses the threshold)
    win = ((p.hist or {}).get("sbp") or [])[-14:]
    if win:
        mx = max(win)
        drop = mx - v.sbp
        if drop >= 22 and v.sbp >= 90:
            due = [m for m in meds if is_active(m) and m.due != "PRN" and any(c in BP_MED_CLASSES for c in m.cls)]
            if due:
                add(id=f"trend:{p.id}", sev="warn", meds=ids(due), trigger="Vital sign trend",
                    title="Blood pressure falling fast",
                    why=f"Systolic BP dropped from {num(mx)} to {num(v.sbp)} in the last few minutes. It is still above 90, but "
                        f"{list_names(due)} {'are' if len(due) > 1 else 'is'} due at {due[0].due}.",
                    data=[f"SBP {num(mx)} → {num(v.sbp)} mmHg · last 7 min · bedside monitor"],
                    action="Recheck BP right before giving any blood-pressure medication.")

    # Potassium
    k_meds = [m for m in meds if any(c in POTASSIUM_RAISING for c in m.cls)]
    k = L.k.v
    if k_meds:
        names = list_names(k_meds)
        data = [f"K+ {num(k)} mmol/L · lab result · {fmt(L.k.t)}" + (f" (was {num(L.k.prev)})" if L.k.prev is not None else ""),
                "Normal range 3.5–5.0 mmol/L"]
        if k > 5.5:
            add(id=f"k:{p.id}", sev="crit", meds=ids(k_meds), trigger="New lab result",
                title=f"High potassium: hold {names}",
                why=f"Potassium is {num(k)} mmol/L. {names} both raise potassium. At this level the risk of dangerous heart rhythms goes up.",
                data=data, action="Hold both. Repeat the potassium, get an ECG, and notify the provider.")
        elif k > 5.0:
            add(id=f"k5:{p.id}", sev="warn", meds=ids(k_meds), trigger="New lab result",
                title="Potassium above normal", why=f"Potassium is {num(k)} mmol/L and {names} can raise it further.",
                data=data, action="Review with the provider before giving.")
        elif len(k_meds) >= 2:
            add(id=f"kinfo:{p.id}", sev="info", meds=[], trigger="Order check",
                title=f"{names}: potassium can rise",
                why=f"Known combination. Potassium is {num(k)}, within range. Daily labs are ordered.", data=[],
                action="No action needed now.")

    # Kidney function
    c = crcl(p)
    cr = L.cr
    aki = cr.prev is not None and cr.v - cr.prev >= 0.3
    cr_data = [f"Creatinine {num(cr.v)} mg/dL · lab result · {fmt(cr.t)}" + (f" (was {num(cr.prev)})" if cr.prev is not None else ""),
               f"Est. CrCl {c} mL/min (Cockcroft-Gault, {num(p.wt)} kg, age {p.age})"]
    if aki:
        cr_data.append(f"Rise of {cr.v - cr.prev:.1f} mg/dL meets the acute kidney injury flag (≥ 0.3)")
    for m in meds:
        if not m.renal:
            continue
        if "metformin" in m.cls and c < 30:
            add(id=f"renal:{p.id}:{m.id}", sev="crit", meds=[m.id], trigger="New lab result",
                title="Metformin contraindicated at current kidney function",
                why=f"Creatinine went up and estimated CrCl is now {c} mL/min. Metformin should not be used below 30. It can build up and cause lactic acidosis.",
                data=cr_data, action="Hold metformin and ask the provider to change diabetes therapy.")
        elif "metformin" in m.cls and c < 45:
            add(id=f"renal45:{p.id}:{m.id}", sev="warn", meds=[m.id], trigger="New lab result",
                title="Metformin: review dose for kidney function", why=f"Estimated CrCl is {c} mL/min.",
                data=cr_data, action="Ask the provider whether to reduce the dose.")
        if "LMWH" in m.cls and c < 30:
            add(id=f"renal:{p.id}:{m.id}", sev="warn", meds=[m.id], trigger="New lab result",
                title="Enoxaparin dose needs kidney adjustment",
                why=f"Estimated CrCl is {c} mL/min. For prevention doses below 30 mL/min, the usual dose is 30 mg daily, not 40 mg. Higher levels raise bleeding risk.",
                data=cr_data, action="Ask the provider or pharmacist to adjust the dose before giving.")

    # Glucose
    g = L.glu.v
    ins = cls("insulin")
    if ins and g < 70:
        add(id=f"glu:{p.id}", sev="crit", meds=ids(ins), trigger="New point-of-care result",
            title="Low blood sugar: hold insulin",
            why=f"Fingerstick glucose is {num(g)} mg/dL. {list_names(ins)} is due at {ins[0].due} and would lower it further.",
            data=[f"Glucose {num(g)} mg/dL · fingerstick · {fmt(L.glu.t)}", "Hypoglycemia threshold < 70 mg/dL"],
            action="Hold insulin. Follow the hypoglycemia protocol (15 g fast-acting carbs, recheck in 15 min) and notify the provider.")

    # Warfarin / INR
    war = cls("warfarin")
    if war and L.inr:
        i = L.inr.v
        d = [f"INR {num(i)} · lab result · {fmt(L.inr.t)}" + (f" (was {num(L.inr.prev)})" if L.inr.prev is not None else ""),
             "Target 2.0–3.0 for atrial fibrillation"]
        if i > 4:
            add(id=f"inr:{p.id}", sev="crit", meds=ids(war), trigger="New lab result",
                title="INR too high: hold warfarin", why=f"INR is {num(i)}, well above the 2.0–3.0 target. Bleeding risk is high.",
                data=d, action="Hold tonight's warfarin, check for signs of bleeding, and notify the provider.")
        elif i > 3:
            add(id=f"inr3:{p.id}", sev="warn", meds=ids(war), trigger="New lab result",
                title="INR above target", why=f"INR is {num(i)}.", data=d, action="Review the warfarin dose with the provider.")
        ns = [m for m in cls("NSAID") if not m.catKey]
        if ns:
            add(id=f"nsaid:{p.id}", sev="crit" if i > 4 else "warn", meds=ids(ns), trigger="New order",
                title=f"Bleeding risk: {list_names(ns)} with warfarin",
                why=f"{list_names(ns)} together with warfarin raises the risk of bleeding, especially stomach bleeding. INR is {num(i)}.",
                data=[f"New order: {', '.join(f'{m.name} {m.dose} {m.route} {m.freq}' for m in ns)}", f"Active: Warfarin {war[0].dose} daily"],
                action="Hold ibuprofen and ask the provider about acetaminophen instead.")

    # Allergies (orders placed through the checker are covered by the "new:" re-check below)
    for m in meds:
        for a in p.allergies:
            if not m.catKey and not a.intol and a.cls in m.cls:
                add(id=f"allergy:{p.id}:{m.id}", sev="crit", meds=[m.id], trigger="New order",
                    title=f"Allergy: {m.name} is a {drugs.CLASS_LABELS.get(a.cls) or a.cls}",
                    why=f"{first} has a documented {a.agent.lower()} allergy ({a.rxn}). {m.name} belongs to the same drug family.",
                    data=[f"Allergy list: {a.agent} · {a.rxn} · EHR", f"New order: {m.name} {m.dose} {m.route} {m.freq}"],
                    action=f"Do not give. Ask the provider for a non-{drugs.CLASS_LABELS.get(a.cls) or a.cls} alternative.")

    # Duplicate ingredient: acetaminophen
    ap = [m for m in meds if m.apap and not m.catKey]
    tot = sum(m.apap or 0 for m in ap)
    if len(ap) > 1 and tot > 4000:
        flagged = [m for m in ap if m.isNew]
        add(id=f"apap:{p.id}", sev="crit", meds=ids(flagged or ap), trigger="New order",
            title="Duplicate acetaminophen: over the daily max",
            why=f"Two orders contain acetaminophen: {' and '.join(f'{m.name} (up to {thousands(m.apap or 0)} mg/day)' for m in ap)}. "
                f"Together that is up to {thousands(tot)} mg a day. The max is 4,000 mg. Too much can cause liver injury.",
            data=[f"{m.name} {m.dose} {m.route} {m.freq}" for m in ap],
            action="Ask the provider to change the new order or stop the scheduled acetaminophen.")

    # Orders placed through the new-medication checker keep being re-checked
    for m in meds:
        if not (m.catKey and is_active(m)):
            continue
        cat = drugs.by_key(m.catKey)
        if cat is None:
            continue
        for issue in check_new_medication(p, cat, m.id):
            add(id=f"new:{p.id}:{m.id}:{js_hash(issue.title)}", sev=issue.sev, meds=[m.id], trigger="New order",
                title=f"{m.name}: {issue.title}", why=issue.why,
                data=[f"{issue.type} check · ordered {fmt(m.orderedAt if m.orderedAt is not None else sim)}"], action=issue.action)

    # Opioids + breathing
    op = cls("opioid")
    if op and (v.rr < 12 or v.spo2 < 90):
        add(id=f"resp:{p.id}", sev="crit", meds=ids(op), trigger="Vital sign change",
            title="Breathing is slowing: hold opioids",
            why=f"Respiratory rate is {num(v.rr)}/min and SpO2 is {num(v.spo2)}%. {list_names(op)} can slow breathing further.",
            data=[f"RR {num(v.rr)}/min · SpO2 {num(v.spo2)}% · bedside monitor · {now}", f"Opioid orders: {', '.join(m.name for m in op)}"],
            action="Hold opioids. Check sedation, stimulate the patient, apply oxygen, follow the naloxone protocol if needed, and notify the provider.")

    # Hemoglobin / lactate
    if L.hgb and L.hgb.v < 7:
        was = f" (was {num(L.hgb.prev)})" if L.hgb.prev is not None else ""
        add(id=f"hgb:{p.id}", sev="crit", meds=[], trigger="New lab result", title="Hemoglobin below transfusion threshold",
            why=f"Hemoglobin is {num(L.hgb.v)} g/dL{was}. With an active GI bleed, transfusion is usually considered below 7.",
            data=[f"Hgb {num(L.hgb.v)} g/dL · lab result · {fmt(L.hgb.t)}", f"HR {num(v.hr)} · BP {num(v.sbp)}/{num(v.dbp)}"],
            action="Notify the provider now, confirm type and crossmatch, and check for signs of ongoing bleeding.")
    if L.lac and L.lac.v >= 4:
        add(id=f"lac:{p.id}", sev="crit", meds=[], trigger="New lab result", title="Lactate 4 or higher: septic shock risk",
            why=f"Lactate is {num(L.lac.v)} mmol/L.", data=[f"Lactate {num(L.lac.v)} mmol/L · {fmt(L.lac.t)}"],
            action="Start the 30 mL/kg fluid bolus and notify the provider.")

    # Time-critical meds and timed care tasks
    items = [("med", m.id, m.name, m.tc.due, m.tc.grace, m.tc.why) for m in meds if m.tc and is_active(m)]
    items += [("task", t.id, t.name, t.due, t.grace, t.why) for t in (p.tasks or []) if not t.done]
    for kind, xid, name, due, grace, why in items:
        left = due - sim
        base = dict(meds=[xid] if kind == "med" else [], task=xid if kind == "task" else None, timing=True, trigger="Time-critical")
        if left <= -grace:
            window = f" · {num(grace)}-min window" if grace else ""
            add(id=f"tc:{p.id}:{xid}:crit", sev="crit", title=f"Late: {name}",
                why=f"{name} was due at {fmt(due)} and is now {max(1, math.floor(-left))} min late. {why}",
                data=[f"Due {fmt(due)}{window} · now {fmt(sim)}"],
                action="Give it now, or notify the provider if it cannot be given." if kind == "med" else "Complete it now and document, or notify the provider.",
                **base)
        elif left <= 15:
            add(id=f"tc:{p.id}:{xid}:warn", sev="warn", title=f"Due soon: {name}" if left > 0 else f"Overdue: {name}",
                why=f"Due at {fmt(due)}, in {math.ceil(left)} min. {why}" if left > 0 else f"Was due at {fmt(due)}. Becomes critical at {fmt(due + grace)}. {why}",
                data=[f"Due {fmt(due)} · now {fmt(sim)}"],
                action="Give on time." if kind == "med" else "Complete on time.",
                **base)

    # Low-priority checks (held back)
    def info(id_: str, title: str, why: str) -> None:
        add(id=id_, sev="info", meds=[], trigger="Order check", title=title, why=why, data=[], action="")

    if cls("ACEi") and cls("loop"):
        info(f"i1:{p.id}", f"{cls('ACEi')[0].name} + {cls('loop')[0].name.lower()}: additive BP lowering", "Common, intended combination. Vitals are monitored.")
    for m in meds:
        if m.beers and p.age >= 65:
            info(f"beers:{p.id}:{m.id}", f"{m.name} in a patient over 65 (Beers list)", "May cause confusion or falls. Already a PRN with fall precautions.")
    if cls("steroid"):
        info(f"st:{p.id}", f"{cls('steroid')[0].name} can raise glucose", f"Glucose is {num(g)} mg/dL. Fingerstick checks are ordered.")
    if any(m.dilt for m in meds) and cls("CCB"):
        info(f"dil:{p.id}", "Diltiazem can raise atorvastatin levels", "Dose is within the usual limit. Monitor for muscle pain.")
    if any(m.qt for m in meds):
        info(f"qt:{p.id}", "Ondansetron: low QT risk at this dose", "No other QT-prolonging drugs active.")
    if cls("tetracycline") and p.sex == "F" and "PREG" not in p.conditions:
        info(f"dx:{p.id}", "Doxycycline: pregnancy test negative on admission", "Take upright with a full glass of water.")
    if "PREG" in p.conditions and cls("BB"):
        info(f"pr:{p.id}", "Labetalol + nifedipine: preferred in pregnancy", "Both are first-line for high blood pressure in pregnancy.")
    if "DYSPH" in p.conditions:
        info(f"dy:{p.id}", "Dysphagia: oral meds crushed per swallow evaluation", "Check each new oral order can be crushed.")
    if "GIB" in p.conditions:
        info(f"gi:{p.id}", "NPO: all medications given IV", "NSAIDs, aspirin and anticoagulants will be blocked for this patient.")
    if cls("glycopeptide"):
        info(f"va:{p.id}", f"{cls('glycopeptide')[0].name}: infuse over at least 90 minutes", f"Est. CrCl {c} mL/min. Pharmacy will dose follow-up by levels.")
    if cls("macrolide"):
        info(f"az:{p.id}", f"{cls('macrolide')[0].name}: QT prolongation (rare)", "No other risk factors found.")
    if cls("LMWH") and c >= 30:
        info(f"lm:{p.id}", "Enoxaparin: kidney function OK for current dose", f"Est. CrCl {c} mL/min.")
    if cls("cephalosporin") and any(a.cls == "penicillin" for a in p.allergies):
        info(f"ceph:{p.id}", f"{cls('cephalosporin')[0].name} with penicillin allergy", "Low cross-reactivity; tolerated previous doses without reaction.")
    return alerts

