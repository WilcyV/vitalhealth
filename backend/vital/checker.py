"""New-medication check: every safety rule for a drug BEFORE it is ordered.

Port of frontend/src/engine/checker.ts (allergies, duplicates, acetaminophen max, interactions,
conditions, pregnancy, Parkinson's, GI bleed, dysphagia, kidney function, labs, vitals, age).
Titles must stay identical to the TypeScript: rules.py builds alert IDs from them.
The rules written as code below match checker.ts; the table-driven ones (interactions, kidney
dosing, age cautions in drugs.py) and the extra lab/vital checks marked "backend" are additions.

Returns issues sorted critical → warning → info.
Tests:  pytest vital/tests/test_checker.py   (expected results in fixtures/checker-cases.json)
"""
from __future__ import annotations

from typing import Optional

from . import drugs
from .models import CatalogDrug, CheckIssue, Medication, Patient, Severity
from .util import crcl, first_name, is_active, list_names, num, round_vitals, sev_rank, thousands



def check_new_medication(p: Patient, d: CatalogDrug, self_id: Optional[str] = None) -> list[CheckIssue]:
    """`self_id`: when re-checking an order already on the chart, the med to leave out of "others"."""
    issues: list[CheckIssue] = []
    others = [m for m in p.meds if m.id != self_id]

    def has(c: str) -> list[Medication]:
        return [m for m in others if c in m.cls]

    def cond(c: str) -> bool:
        return c in p.conditions

    def dc(c: str) -> bool:
        return c in d.cls

    def add(sev: Severity, type_: str, title: str, why: str, action: str) -> None:
        issues.append(CheckIssue(sev=sev, type=type_, title=title, why=why, action=action))

    c = crcl(p)
    L = p.labs
    v = round_vitals(p.vit)
    first = first_name(p)
    label = drugs.CLASS_LABELS

    # Allergies and intolerances
    for a in p.allergies:
        if not dc(a.cls):
            continue
        if a.intol:
            add("warn", "Intolerance", f"Documented {a.agent.lower()} intolerance",
                f"{first} had {a.rxn.replace(' (intolerance)', '', 1)} with {a.agent.lower()}. This is an intolerance, not a true allergy.",
                "Consider a different pain medication, or pre-treat for nausea.")
        else:
            add("crit", "Allergy", f"Allergy: {d.name} is a {label.get(a.cls) or a.cls}",
                f"{first} has a documented {a.agent.lower()} allergy ({a.rxn}).",
                "Do not order. Choose a drug from a different family.")
    if dc("cephalosporin"):
        pen = [a for a in p.allergies if a.cls == "penicillin" and not a.intol]
        if pen:
            add("warn", "Allergy", "Penicillin allergy: low cross-reactivity",
                f"{first} has a documented {pen[0].agent.lower()} allergy ({pen[0].rxn}). Cephalosporins rarely cross-react, but it can happen.",
                "Confirm the reaction history. Give the first dose with monitoring.")

    # Duplicate therapy
    flagged: set[str] = set()
    for cl in drugs.DUPLICATE_CLASSES:
        if not dc(cl):
            continue
        ex = has(cl)
        if not ex:
            continue
        flagged.update(m.id for m in ex)
        soft = cl in ("opioid", "anticoag")
        if soft:
            effect = "add up sedation and can slow breathing" if cl == "opioid" else "raise bleeding risk"
            bridging = " (for example, bridging)" if cl == "anticoag" else ""
            why = f"{first} already has {list_names(ex)} ordered. Two {label[cl]}s together {effect}, unless this is intentional{bridging}."
        else:
            why = f"{first} is already on {list_names(ex)}, from the same drug class. Giving both doubles the effect."
        add("warn" if soft else "crit", "Duplicate therapy", f"Duplicate {label[cl]}: already on {list_names(ex)}", why,
            "Confirm with the provider that both are intended." if soft else "Do not add. Adjust the existing order instead.")

    # Same drug already ordered (backend; classes above catch most, this catches the rest)
    same = [m for m in others if m.id not in flagged and not m.apap and _same_drug(m.name, d.name)]
    if same:
        add("crit", "Duplicate therapy", f"Already ordered: {list_names(same)}",
            f"{first} already has {list_names(same)} ordered.", "Do not add. Adjust the existing order instead.")

    # Duplicate ingredient: acetaminophen
    if d.apap:
        ap = [m for m in others if m.apap]
        tot = sum(m.apap or 0 for m in ap) + (d.apap or 0)
        if ap and tot > 4000:
            add("crit", "Duplicate ingredient", "Acetaminophen over the daily max",
                f"{list_names(ap)} already {'contain' if len(ap) > 1 else 'contains'} acetaminophen. Adding this allows up to {thousands(tot)} mg a day. The max is 4,000 mg.",
                "Do not add. Use the existing acetaminophen order.")

    if dc("NSAID"):
        if has("warfarin"):
            add("crit", "Drug interaction", "Bleeding risk with warfarin",
                f"NSAIDs plus warfarin raise the risk of serious bleeding.{f' INR is {num(L.inr.v)}.' if L.inr else ''}",
                "Avoid. Consider acetaminophen for pain.")
        if cond("HF"):
            tw = bool(has("ACEi")) and bool(has("loop"))
            add("crit" if tw else "warn", "Condition",
                'Heart failure + ACE inhibitor + diuretic ("triple whammy")' if tw else "Can worsen heart failure",
                f"{first} has heart failure and takes {list_names(has('ACEi') + has('loop'))}. Adding an NSAID to an ACE inhibitor and a diuretic is a known cause of acute kidney injury, and NSAIDs cause fluid retention."
                if tw else "NSAIDs cause salt and fluid retention and can trigger a heart failure flare.",
                "Avoid NSAIDs. Consider acetaminophen.")
        if cond("CKD") or c < 60:
            add("crit" if c < 30 else "warn", "Kidney function", f"Kidney function: CrCl {c} mL/min",
                f"NSAIDs reduce blood flow to the kidneys{', and ' + first + ' has chronic kidney disease' if cond('CKD') else ''}.",
                "Avoid, or use the lowest dose for the shortest time.")
        if cond("ASTHMA"):
            add("warn", "Condition", "Asthma: NSAIDs can trigger bronchospasm", "Some people with asthma react to NSAIDs.",
                "Ask whether the patient has taken NSAIDs safely before.")
        if p.age >= 65:
            add("warn", "Age", f"Age {p.age}: stomach bleeding risk (Beers list)", "NSAIDs raise the risk of stomach bleeding in older adults.",
                "Use the lowest dose for the shortest time, or choose acetaminophen.")

    if dc("BB"):
        if cond("ASTHMA"):
            ns = dc("BB-ns")
            add("crit" if ns else "warn", "Condition", "Contraindicated in asthma" if ns else "Use caution in asthma",
                f"{d.name} also blocks beta receptors in the lungs and can cause severe bronchospasm." if ns
                else f"{d.name} is cardioselective, but it can still tighten airways at higher doses.",
                "Do not order. If a beta-blocker is needed, ask about a cardioselective one." if ns else "Use the lowest dose and monitor breathing.")
        nd = has("CCB-nd")
        if nd:
            add("warn", "Drug interaction", f"Slow heart rate with {list_names(nd)}",
                f"Beta-blockers and {list_names(nd)} both slow the heart. Together they can cause bradycardia or heart block.",
                "Check heart rate and ECG, and confirm with the provider.")
        if v.hr < 60:
            add("warn", "Vitals", f"Heart rate is {num(v.hr)}", "A beta-blocker would slow it further.", "Recheck heart rate before the first dose.")

    if dc("CCB-nd"):
        bb = has("BB")
        if bb:
            add("crit", "Drug interaction", f"Heart block risk with {list_names(bb)}",
                f"{d.name} plus {list_names(bb)} can dangerously slow heart rate and conduction.", "Avoid this combination.")
        if cond("HF"):
            add("crit", "Condition", "Can worsen heart failure",
                f"{d.name} weakens heart contraction and is avoided in heart failure with reduced ejection fraction.", "Choose a different drug.")

    if dc("tmpsmx"):
        if has("warfarin"):
            add("crit", "Drug interaction", "Raises INR with warfarin",
                "This antibiotic blocks warfarin breakdown. INR can rise quickly and cause bleeding.",
                "Choose a different antibiotic, or lower warfarin and check INR closely.")
        kk = has("ACEi") + has("ARB") + has("Ksparing")
        if kk:
            add("crit" if has("Ksparing") else "warn", "Drug interaction", "High potassium risk",
                f"Trimethoprim raises potassium, and so {'do' if len(kk) > 1 else 'does'} {list_names(kk)}. Current K+ is {num(L.k.v)} mmol/L.",
                "Choose a different antibiotic, or monitor potassium closely.")
        if c < 30:
            add("warn", "Kidney function", f"Dose adjustment: CrCl {c} mL/min", "This antibiotic is cleared by the kidneys.", "Reduce the dose by half.")

    if dc("azole"):
        if has("warfarin"):
            add("crit", "Drug interaction", "Raises INR with warfarin",
                "Fluconazole strongly blocks warfarin breakdown. INR can double within days.",
                "Lower the warfarin dose and recheck INR in 3 days, or choose another antifungal.")
        if has("statin"):
            add("warn", "Drug interaction", f"Raises {list_names(has('statin'))} levels",
                "Higher statin levels raise the risk of muscle damage.", "Watch for muscle pain; consider holding the statin.")

    if dc("macrolide-strong"):
        if has("statin"):
            add("warn", "Drug interaction", f"Raises {list_names(has('statin'))} levels",
                "Clarithromycin sharply raises statin levels, with a risk of muscle breakdown (rhabdomyolysis).",
                "Hold the statin during the antibiotic course.")
        if has("warfarin"):
            add("warn", "Drug interaction", "Can raise INR with warfarin", "Clarithromycin slows warfarin breakdown.", "Check INR within a few days.")
        if has("CCB-nd"):
            add("warn", "Drug interaction", f"Raises {list_names(has('CCB-nd'))} levels",
                "Can cause low blood pressure and slow heart rate.", "Monitor BP and heart rate.")

    if dc("QT"):
        q = has("QT")
        if q:
            add("warn", "Drug interaction", "QT prolongation risk",
                f"{d.name} and {list_names(q)} both prolong the QT interval, which can trigger a dangerous heart rhythm.",
                "Get a baseline ECG and check potassium and magnesium.")

    if dc("quinolone"):
        if has("warfarin"):
            add("warn", "Drug interaction", "Can raise INR with warfarin", f"{d.name} can increase warfarin effect.", "Check INR within a few days.")
        if p.age >= 65:
            add("warn", "Age", f"Age {p.age}: tendon and confusion risk",
                "Fluoroquinolones carry an FDA boxed warning for tendon rupture, and older adults are at higher risk.",
                "Consider another antibiotic if one fits.")

    if dc("benzo") or dc("sedative") or dc("sedating"):
        op = has("opioid")
        if op:
            boxed = " The FDA has a boxed warning for this combination." if dc("benzo") else ""
            add("crit" if dc("benzo") else "warn", "Drug interaction", "Breathing risk with opioids",
                f"{d.name} plus {list_names(op)} can cause deep sedation and slowed breathing.{boxed}",
                "Avoid, or use the lowest doses with continuous SpO2 monitoring.")
        if p.age >= 65:
            add("warn", "Age", f"Age {p.age}: falls and confusion (Beers list)",
                f"{d.name} raises the risk of falls, delirium and fractures in older adults.",
                "Try non-drug sleep or anxiety measures first.")
        if v.spo2 < 92:
            add("warn", "Vitals", f"SpO2 is {num(v.spo2)}%", "A sedative could lower it further.", "Assess breathing before giving.")

    if dc("opioid"):
        bz = has("benzo")
        if bz:
            add("crit", "Drug interaction", f"Breathing risk with {list_names(bz)}",
                "Opioids plus benzodiazepines can stop breathing. The FDA has a boxed warning for this combination.",
                "Avoid, or use the lowest doses with continuous SpO2 monitoring.")

    if dc("Ksupp"):
        kk = has("ACEi") + has("ARB") + has("Ksparing")
        if L.k.v > 5.0:
            add("crit", "Lab", f"Potassium is already {num(L.k.v)}", "Adding potassium could push it to a dangerous level.", "Do not order.")
        elif kk:
            add("crit" if len(kk) >= 2 else "warn", "Drug interaction", "High potassium risk",
                f"{list_names(kk)} already {'raise' if len(kk) > 1 else 'raises'} potassium. Current K+ is {num(L.k.v)} mmol/L.",
                "Confirm the need with a repeat potassium first.")

    if dc("TZD"):
        if cond("HF"):
            add("crit", "Condition", "Contraindicated in heart failure",
                "Pioglitazone causes fluid retention and has an FDA boxed warning for heart failure.",
                "Choose a different diabetes medication.")
        if has("insulin"):
            add("warn", "Drug interaction", "Fluid retention with insulin",
                "Pioglitazone with insulin raises the risk of swelling and fluid overload.", "Monitor weight and swelling.")

    if dc("SU"):
        if has("insulin"):
            add("warn", "Drug interaction", "Low blood sugar risk with insulin",
                f"{d.name} and {list_names(has('insulin'))} both lower blood sugar.",
                "Confirm the combination and increase fingerstick checks.")
        if c < 50:
            add("warn", "Kidney function", f"Kidney function: CrCl {c} mL/min",
                "Lower kidney function raises the risk of low blood sugar.", "Start at the lowest dose.")
        if L.glu.v < 100:
            add("warn", "Lab", f"Glucose is {num(L.glu.v)} mg/dL", "Blood sugar is already on the low side.", "Recheck glucose before ordering.")

    if dc("metformin"):
        if c < 30:
            add("crit", "Kidney function", f"Contraindicated: CrCl {c} mL/min",
                "Metformin can build up and cause lactic acidosis when kidney function is below 30.",
                "Choose a different diabetes medication.")
        elif c < 45:
            add("warn", "Kidney function", f"Dose limit: CrCl {c} mL/min",
                "Metformin needs a lower maximum dose at this kidney function.", "Keep the total dose at or below 1,000 mg a day.")

    if dc("nitroimidazole") and has("warfarin"):
        add("crit", "Drug interaction", "Raises INR with warfarin",
            "Metronidazole strongly blocks warfarin breakdown. INR can rise sharply and cause bleeding.",
            "Choose a different antibiotic, or lower warfarin and check INR in 3 days.")

    if dc("vasodilator") and v.sbp < 110:
        add("warn", "Vitals", f"Blood pressure is {num(v.sbp)}/{num(v.dbp)}",
            f"{d.name} is for severe high blood pressure. The current reading is not high.", "Confirm the indication before ordering.")

    if dc("antiplatelet") and has("anticoag"):
        add("warn", "Drug interaction", f"Bleeding risk with {list_names(has('anticoag'))}",
            f"{d.name} plus an anticoagulant raises bleeding risk.", "Confirm there is a clear reason for both.")

    if dc("LMWH") and c < 30:
        add("warn", "Kidney function", f"Dose adjustment: CrCl {c} mL/min",
            "Enoxaparin builds up when kidney function is below 30.", "Use 30 mg daily for prevention.")

    # ---- backend additions: labs and vitals for more drug classes ----
    if dc("ACEi") or dc("ARB") or dc("Ksparing"):
        if L.k.v > 5.0:
            add("crit" if L.k.v > 5.5 else "warn", "Lab", f"Potassium is {num(L.k.v)}",
                f"{d.name} raises potassium, and it is already above normal.", "Recheck potassium and ask the provider before ordering.")
    if dc("loop") or dc("thiazide"):
        if L.k.v < 3.5:
            add("warn", "Lab", f"Potassium is low ({num(L.k.v)})", f"{d.name} makes the kidneys lose more potassium.",
                "Replace potassium first, or order it together.")
        if v.sbp < 90:
            add("warn", "Vitals", f"Blood pressure is {num(v.sbp)}/{num(v.dbp)}", f"{d.name} removes fluid and can lower blood pressure further.",
                "Confirm with the provider before ordering.")
    if dc("digoxin"):
        if L.k.v < 3.5:
            add("warn", "Lab", f"Potassium is low ({num(L.k.v)})", "Low potassium makes digoxin toxicity much more likely.",
                "Correct potassium before starting digoxin.")
        if v.hr < 60:
            add("warn", "Vitals", f"Heart rate is {num(v.hr)}", "Digoxin slows the heart rate further.", "Recheck the apical pulse before the first dose.")
    if dc("warfarin") and L.inr and L.inr.v > 3:
        add("warn", "Lab", f"INR is already {num(L.inr.v)}", "INR is above the usual 2.0–3.0 target.", "Confirm the dose with the provider.")
    if dc("insulin") and L.glu.v < 70:
        add("crit", "Lab", f"Glucose is {num(L.glu.v)} mg/dL", "Blood sugar is already low. Insulin would lower it further.",
            "Do not give now. Follow the hypoglycemia protocol and notify the provider.")

    # ---- backend additions: rules from the tables in drugs.py ----
    ctx = {"drug": d.name, "k": num(L.k.v)}
    for rule in drugs.INTERACTIONS:
        if not any(dc(x) for x in rule["drug"]):
            continue
        ms = [m for m in others if any(x in _classes(m) for x in rule["other"])]
        if ms:
            f = dict(ctx, others=list_names(ms))
            add(rule["sev"], "Drug interaction", rule["title"].format(**f), rule["why"].format(**f), rule["action"].format(**f))
    for below, sev, why, action in drugs.RENAL_DOSING.get(d.key, []):
        if c < below:
            add(sev, "Kidney function", f"{'Avoid' if sev == 'crit' else 'Dose adjustment'}: CrCl {c} mL/min", why, action)
            break
    if p.age >= 65:
        for cl, (title, why, action) in drugs.AGE_CAUTIONS.items():
            if dc(cl):
                add("warn", "Age", f"Age {p.age}: {title}", why.format(**ctx), action.format(**ctx))

    if cond("PREG"):
        if dc("ACEi"):
            add("crit", "Pregnancy", "Contraindicated in pregnancy",
                "ACE inhibitors can damage the baby's kidneys and cause low amniotic fluid, especially in the 2nd and 3rd trimesters.",
                "Do not order. Labetalol or nifedipine are preferred in pregnancy.")
        if dc("ARB"):
            add("crit", "Pregnancy", "Contraindicated in pregnancy",
                "ARBs can damage the baby's kidneys and cause low amniotic fluid, especially in the 2nd and 3rd trimesters.",
                "Do not order. Labetalol or nifedipine are preferred in pregnancy.")
        if dc("amiodarone"):
            add("warn", "Pregnancy", "Avoid in pregnancy if possible", "Amiodarone can affect the baby's thyroid and heart rate.",
                "Confirm with the provider and cardiology.")
        if dc("NSAID"):
            add("crit", "Pregnancy", "Avoid after 20 weeks of pregnancy",
                "NSAIDs can lower amniotic fluid and, in the 3rd trimester, can close a vital fetal blood vessel (the ductus arteriosus) too early.",
                "Use acetaminophen instead.")
        if dc("tetracycline"):
            add("crit", "Pregnancy", "Avoid in pregnancy", "Tetracyclines can stain the baby's teeth and affect bone growth.",
                "Choose a different antibiotic.")
        if dc("anticoag") and not (dc("LMWH") or dc("heparin")):
            add("crit", "Pregnancy", "Avoid in pregnancy", "This anticoagulant can cause birth defects.",
                "Enoxaparin is the usual choice in pregnancy.")
        if dc("quinolone"):
            add("warn", "Pregnancy", "Generally avoided in pregnancy", "Safer antibiotic options are usually available.", "Confirm with the provider.")
        if dc("azole"):
            add("warn", "Pregnancy", "Fluconazole in pregnancy", "Higher or repeated doses have been linked to birth defects.",
                "Consider a topical antifungal.")
        if dc("tmpsmx"):
            add("warn", "Pregnancy", "Late pregnancy", "Sulfonamides close to delivery can raise the newborn’s bilirubin.",
                "Choose a different antibiotic if possible.")
        if dc("statin"):
            add("warn", "Pregnancy", "Usually stopped in pregnancy", "Cholesterol drugs are generally paused during pregnancy.",
                "Confirm with the provider.")

    if cond("PD") and dc("dopamine-block"):
        add("crit", "Condition", "Worsens Parkinson's disease",
            f"{d.name} blocks dopamine, the chemical that Parkinson's medication replaces. It can cause severe stiffness, freezing and swallowing problems.",
            "Do not order. For agitation, low-dose quetiapine is a safer choice." if d.group == "agitation"
            else "Do not order. For nausea, ondansetron is a safer choice.")

    if cond("GIB"):
        if dc("NSAID") or dc("antiplatelet"):
            add("crit", "Condition", "Active GI bleed",
                f"{d.name} irritates the stomach lining and slows clotting. It can make the bleeding worse.", "Do not order.")
        if dc("anticoag"):
            add("crit", "Condition", "Active GI bleed", "Anticoagulants are contraindicated while the patient is actively bleeding.",
                "Do not order. For clot prevention, use compression devices.")
        if dc("steroid"):
            add("warn", "Condition", "Raises ulcer bleeding risk", "Steroids slow ulcer healing and raise bleeding risk.",
                "Confirm the need with the provider.")

    if cond("DYSPH") and dc("ER") and d.route == "PO":
        add("warn", "Condition", "Dysphagia: extended-release tablet",
            f"{first} has trouble swallowing and gets meds crushed. Crushing {d.name} releases the whole dose at once.",
            "Ask pharmacy for an immediate-release or liquid form.")

    if dc("steroid") and cond("DM"):
        add("warn", "Condition", "Raises blood sugar in diabetes", "Steroids raise glucose, often for several days.",
            "Increase fingerstick checks; insulin may need adjusting.")

    return sorted(issues, key=lambda i: sev_rank(i.sev))


def suggest_alternatives(p: Patient, d: CatalogDrug) -> list[dict]:
    """Drugs in the same `group` that have no critical issue, fewest issues first, max 3.
    Skips drugs the patient already has as an active order. Same as suggestAlternatives in api/mock.ts.
    Returns [{"drug": CatalogDrug, "issues": [CheckIssue]}]."""
    candidates = [
        x for x in drugs.CATALOG
        if x.group == d.group and x.key != d.key
        and not any(is_active(m) and (m.catKey == x.key or m.name == x.name) for m in p.meds)
    ]
    alts = [{"drug": x, "issues": check_new_medication(p, x)} for x in candidates]
    alts = [a for a in alts if not any(i.sev == "crit" for i in a["issues"])]
    return sorted(alts, key=lambda a: len(a["issues"]))[:3]


def _same_drug(a: str, b: str) -> bool:
    """"Potassium chloride" vs "Potassium chloride IV", "Ondansetron" vs "Ondansetron": same drug."""
    a, b = a.lower(), b.lower()
    return a.startswith(b) or b.startswith(a)


def _classes(m: Medication) -> set[str]:
    """A med's classes plus those of its catalog entry. Orders from the EHR may carry only the
    basic class ("statin"); the catalog adds finer ones ("statin-3A4") used by the tables."""
    extra = next((d.cls for d in drugs.CATALOG if _same_drug(m.name, d.name)), [])
    return set(m.cls) | set(extra)
