"""The drug database: every drug Vital knows about, and the data-driven safety rules.

The backend owns this data. `vital/data.py` serves it to the server and the engine.
The first 37 catalog drugs mirror frontend/src/engine/data.ts (demo mode); the rest exist only in
the backend. `vital/tests/test_drugs.py` checks the frontend's drugs are all here unchanged.

How a drug plugs into the rules:
  cls    drug classes. The rules in checker.py / rules.py and the tables below match on these
         (e.g. "NSAID", "QT", "BB-ns" for non-selective beta-blockers). A new drug with existing
         classes gets every existing check for free.
  group  therapeutic group. suggest_alternatives() offers other drugs from the same group.
  apap   max acetaminophen per day from this order (mg), for the duplicate-ingredient check.
  tall / lasa / purpose   look-alike / sound-alike names (ISMP list): tall-man spelling, the key
         of the drug it gets confused with (pairs point at each other), and a plain-language
         purpose shown in the warning.
  rxcui  RxNorm ingredient codes (one per ingredient), from the NIH RxNav API.

Rules as data (read by checker.py), so a pharmacist can review and extend them without code:
  INTERACTIONS   ordering a drug of class X while the patient has class Y
  RENAL_DOSING   kidney-function (CrCl) limits per drug
  AGE_CAUTIONS   extra cautions for patients 65 and older (Beers list)

Synthetic demo data, simplified: not for clinical use. Needs pharmacist review (NEXT_STEPS.md).
"""
from __future__ import annotations

from typing import Optional

from .models import CatalogDrug

# Patient conditions (codes used in Patient.conditions).
CONDITIONS: dict[str, str] = {
    "PREG": "Pregnant",
    "PID": "Pelvic inflammatory disease",
    "PD": "Parkinson's disease",
    "DYSPH": "Dysphagia (trouble swallowing)",
    "GIB": "Active upper GI bleed",
    "SEPSIS": "Sepsis",
    "HF": "Heart failure",
    "HTN": "Hypertension",
    "DM": "Type 2 diabetes",
    "CKD": "Chronic kidney disease",
    "AF": "Atrial fibrillation",
    "ASTHMA": "Asthma",
    "POSTOP": "Post-op",
    "PNA": "Pneumonia",
}

# Plain-language names for drug classes, used in alert text.
CLASS_LABELS: dict[str, str] = {
    "ACEi": "ACE inhibitor",
    "tetracycline": "tetracycline antibiotic",
    "BB": "beta-blocker",
    "NSAID": "NSAID",
    "opioid": "opioid",
    "anticoag": "anticoagulant",
    "statin": "statin",
    "benzo": "benzodiazepine",
    "steroid": "steroid",
    "metformin": "metformin",
    "penicillin": "penicillin",
    "sulfonamide": "sulfonamide",
    "codeine": "codeine",
    "CCB-nd": "rate-slowing calcium channel blocker",
    # backend additions
    "ARB": "ARB (angiotensin receptor blocker)",
    "SSRI": "SSRI antidepressant",
    "antipsychotic": "antipsychotic",
    "SU": "sulfonylurea",
    "PPI": "proton pump inhibitor",
    "loop": "loop diuretic",
    "CCB-dhp": "calcium channel blocker",
    "gabapentinoid": "gabapentinoid",
    "cephalosporin": "cephalosporin",
    "quinolone": "fluoroquinolone",
}

# Therapeutic groups, used for safer alternatives.
GROUP_LABELS: dict[str, str] = {
    "pain": "pain relief",
    "sleep-anxiety": "sleep or anxiety",
    "rate-bp": "heart rate control",
    "bp": "blood pressure",
    "potassium": "potassium replacement",
    "antibiotic": "antibiotics",
    "antifungal": "antifungals",
    "antiplatelet": "antiplatelets",
    "anticoag": "clot prevention",
    "diabetes": "diabetes",
    "steroid": "steroids",
    "statin": "cholesterol",
    "nausea": "nausea",
    "agitation": "agitation",
    # backend additions
    "diuretic": "fluid removal (diuretics)",
    "mood": "depression and anxiety",
    "stomach": "stomach acid",
    "seizure": "seizures",
}

# Allergy choices in the admit / edit form. `cls` is matched against a drug's classes.
ALLERGENS: list[dict[str, str]] = [
    {"agent": "Penicillin", "cls": "penicillin"},
    {"agent": "Sulfa drugs", "cls": "sulfonamide"},
    {"agent": "Codeine", "cls": "codeine"},
    {"agent": "NSAIDs (ibuprofen, naproxen)", "cls": "NSAID"},
    {"agent": "Aspirin", "cls": "antiplatelet"},
    {"agent": "Cephalosporins", "cls": "cephalosporin"},
    {"agent": "Morphine / opioids", "cls": "opioid"},
    {"agent": "Tetracyclines", "cls": "tetracycline"},
    {"agent": "Statins", "cls": "statin"},
    {"agent": "Fluoroquinolones", "cls": "quinolone"},
    {"agent": "Latex", "cls": "latex"},
    {"agent": "Other", "cls": "other"},
]

# Drugs available in "Check a new medication".
_CATALOG: list[dict] = [
    {"key": "ibu", "group": "pain", "name": "Ibuprofen", "dose": "600 mg", "route": "PO", "freq": "q6h PRN pain", "due": "PRN", "cls": ["NSAID"], "rxcui": ["5640"]},
    {"key": "keto", "group": "pain", "name": "Ketorolac", "dose": "15 mg", "route": "IV", "freq": "q6h", "due": "12:00", "cls": ["NSAID"], "rxcui": ["35827"]},
    {"key": "apap", "group": "pain", "name": "Acetaminophen", "dose": "650 mg", "route": "PO", "freq": "q6h PRN pain", "due": "PRN", "cls": ["analgesic"], "apap": 2600, "rxcui": ["161"]},
    {"key": "tram", "group": "pain", "name": "Tramadol", "tall": "TraMADol", "lasa": "traz", "purpose": "opioid pain medicine", "dose": "50 mg", "route": "PO", "freq": "q6h PRN pain", "due": "PRN", "cls": ["opioid", "serotonergic"], "rxcui": ["10689"]},
    {"key": "cod", "group": "pain", "name": "Codeine/APAP 30/300", "dose": "1 tab", "route": "PO", "freq": "q6h PRN pain", "due": "PRN", "cls": ["opioid", "codeine"], "apap": 1200, "rxcui": ["2670", "161"]},
    {"key": "lora", "group": "sleep-anxiety", "name": "Lorazepam", "tall": "LORazepam", "lasa": "alpraz", "purpose": "benzodiazepine for anxiety or seizures", "dose": "1 mg", "route": "IV", "freq": "q6h PRN anxiety", "due": "PRN", "cls": ["benzo"], "rxcui": ["6470"]},
    {"key": "zolp", "group": "sleep-anxiety", "name": "Zolpidem", "dose": "5 mg", "route": "PO", "freq": "Nightly PRN sleep", "due": "PRN", "cls": ["sedative"], "rxcui": ["39993"]},
    {"key": "prop", "group": "rate-bp", "name": "Propranolol", "dose": "20 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["BB", "BB-ns"], "rxcui": ["8787"]},
    {"key": "meto", "group": "rate-bp", "name": "Metoprolol tartrate", "dose": "25 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["BB"], "rxcui": ["6918"]},
    {"key": "vera", "group": "rate-bp", "name": "Verapamil", "dose": "80 mg", "route": "PO", "freq": "TID", "due": "12:00", "cls": ["CCB", "CCB-nd"], "rxcui": ["11170"]},
    {"key": "kcl", "group": "potassium", "name": "Potassium chloride", "dose": "20 mEq", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["Ksupp"], "rxcui": ["8591"]},
    {"key": "smx", "group": "antibiotic", "name": "Trimethoprim-sulfamethoxazole DS", "dose": "1 tab", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["sulfonamide", "tmpsmx"], "rxcui": ["10829", "10180"]},
    {"key": "amox", "group": "antibiotic", "name": "Amoxicillin", "dose": "500 mg", "route": "PO", "freq": "TID", "due": "12:00", "cls": ["penicillin"], "rxcui": ["723"]},
    {"key": "cipro", "group": "antibiotic", "name": "Ciprofloxacin", "dose": "500 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["quinolone", "QT"], "rxcui": ["2551"]},
    {"key": "clari", "group": "antibiotic", "name": "Clarithromycin", "dose": "500 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["macrolide-strong", "QT"], "rxcui": ["21212"]},
    {"key": "fluc", "group": "antifungal", "name": "Fluconazole", "dose": "200 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["azole", "QT"], "rxcui": ["4450"]},
    {"key": "asa", "group": "antiplatelet", "name": "Aspirin", "dose": "81 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["antiplatelet"], "rxcui": ["1191"]},
    {"key": "enox", "group": "anticoag", "name": "Enoxaparin", "dose": "40 mg", "route": "SC", "freq": "Daily", "due": "12:00", "cls": ["LMWH", "anticoag"], "rxcui": ["67108"]},
    {"key": "metf", "group": "diabetes", "name": "Metformin", "tall": "MetFORMIN", "lasa": "metro", "purpose": "diabetes medicine", "dose": "500 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["metformin"], "rxcui": ["6809"]},
    {"key": "glip", "group": "diabetes", "name": "Glipizide", "tall": "glipiZIDE", "lasa": "glyb", "purpose": "diabetes pill (sulfonylurea)", "dose": "5 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["SU"], "rxcui": ["4821"]},
    {"key": "pio", "group": "diabetes", "name": "Pioglitazone", "dose": "15 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["TZD"], "rxcui": ["33738"]},
    {"key": "pred", "group": "steroid", "name": "Prednisone", "tall": "predniSONE", "lasa": "predl", "purpose": "steroid tablet", "dose": "40 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["steroid"], "rxcui": ["8640"]},
    {"key": "lisi", "group": "bp", "name": "Lisinopril", "dose": "10 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["ACEi"], "rxcui": ["29046"]},
    {"key": "nife", "group": "bp", "name": "Nifedipine ER", "dose": "30 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["CCB", "ER", "CCB-dhp"], "rxcui": ["7417"]},
    {"key": "atorva", "group": "statin", "name": "Atorvastatin", "dose": "40 mg", "route": "PO", "freq": "Nightly", "due": "21:00", "cls": ["statin", "statin-3A4"], "rxcui": ["83367"]},
    {"key": "doxy", "group": "antibiotic", "name": "Doxycycline", "dose": "100 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["tetracycline"], "rxcui": ["3640"]},
    {"key": "reglan", "group": "nausea", "name": "Metoclopramide", "dose": "10 mg", "route": "IV", "freq": "q6h PRN nausea", "due": "PRN", "cls": ["dopamine-block"], "rxcui": ["6915"]},
    {"key": "haldol", "group": "agitation", "name": "Haloperidol", "dose": "2 mg", "route": "IV", "freq": "q6h PRN agitation", "due": "PRN", "cls": ["dopamine-block", "QT", "antipsychotic"], "rxcui": ["5093"]},
    {"key": "ondan", "group": "nausea", "name": "Ondansetron", "dose": "4 mg", "route": "IV", "freq": "q8h PRN nausea", "due": "PRN", "cls": ["antiemetic", "QT"], "rxcui": ["26225"]},
    {"key": "labe", "group": "bp", "name": "Labetalol", "dose": "100 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["BB"], "rxcui": ["6185"]},
    {"key": "hydral", "group": "bp", "name": "Hydralazine", "tall": "HydrALAZINE", "lasa": "hydroxy", "purpose": "blood pressure medicine", "dose": "10 mg", "route": "IV", "freq": "q6h PRN SBP > 160", "due": "PRN", "cls": ["vasodilator"], "rxcui": ["5470"]},
    {"key": "hydroxy", "group": "sleep-anxiety", "name": "Hydroxyzine", "tall": "HydrOXYzine", "lasa": "hydral", "purpose": "antihistamine for anxiety or itching", "dose": "25 mg", "route": "PO", "freq": "q6h PRN anxiety", "due": "PRN", "cls": ["antihistamine", "sedating", "QT"], "rxcui": ["5553"]},
    {"key": "traz", "group": "sleep-anxiety", "name": "Trazodone", "tall": "TraZODone", "lasa": "tram", "purpose": "antidepressant used for sleep", "dose": "50 mg", "route": "PO", "freq": "Nightly PRN sleep", "due": "PRN", "cls": ["sedating", "QT", "serotonergic"], "rxcui": ["10737"]},
    {"key": "metro", "group": "antibiotic", "name": "Metronidazole", "tall": "MetroNIDAZOLE", "lasa": "metf", "purpose": "antibiotic", "dose": "500 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["nitroimidazole"], "rxcui": ["6922"]},
    {"key": "cephx", "group": "antibiotic", "name": "Cephalexin", "dose": "500 mg", "route": "PO", "freq": "QID", "due": "12:00", "cls": ["cephalosporin"], "rxcui": ["2231"]},
    {"key": "quet", "group": "agitation", "name": "Quetiapine", "tall": "QUEtiapine", "lasa": "olanz", "purpose": "antipsychotic for agitation or delirium", "dose": "12.5 mg", "route": "PO", "freq": "Nightly PRN agitation", "due": "PRN", "cls": ["antipsychotic", "QT"], "rxcui": ["51272"]},
    {"key": "melat", "group": "sleep-anxiety", "name": "Melatonin", "dose": "3 mg", "route": "PO", "freq": "Nightly PRN sleep", "due": "PRN", "cls": ["supplement"], "rxcui": ["6711"]},
    # ---- added in the backend (not in the frontend's demo catalog) ----
    {"key": "nap", "group": "pain", "name": "Naproxen", "dose": "500 mg", "route": "PO", "freq": "BID with food", "due": "12:00", "cls": ["NSAID"], "rxcui": ["7258"]},
    {"key": "cele", "group": "pain", "name": "Celecoxib", "dose": "200 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["NSAID", "COX2"], "rxcui": ["140587"]},
    {"key": "oxy", "group": "pain", "name": "Oxycodone", "tall": "OxyCODONE", "lasa": "hydroc", "purpose": "opioid pain medicine (no acetaminophen)", "dose": "5 mg", "route": "PO", "freq": "q4h PRN pain", "due": "PRN", "cls": ["opioid"], "rxcui": ["7804"]},
    {"key": "hydroc", "group": "pain", "name": "Hydrocodone/APAP 5/325", "tall": "HYDROcodone/APAP 5/325", "lasa": "oxy", "purpose": "opioid + acetaminophen combination pill", "dose": "1 tab", "route": "PO", "freq": "q6h PRN pain", "due": "PRN", "cls": ["opioid"], "apap": 1300, "rxcui": ["5489", "161"]},
    {"key": "morph", "group": "pain", "name": "Morphine", "tall": "Morphine", "lasa": "hmorph", "purpose": "opioid pain medicine (standard strength)", "dose": "2 mg", "route": "IV", "freq": "q2h PRN pain", "due": "PRN", "cls": ["opioid"], "rxcui": ["7052"]},
    {"key": "hmorph", "group": "pain", "name": "Hydromorphone", "tall": "HYDROmorphone", "lasa": "morph", "purpose": "strong opioid, about 5–7 times stronger than morphine", "dose": "0.5 mg", "route": "IV", "freq": "q3h PRN severe pain", "due": "PRN", "cls": ["opioid"], "rxcui": ["3423"]},
    {"key": "gaba", "group": "pain", "name": "Gabapentin", "dose": "300 mg", "route": "PO", "freq": "TID", "due": "12:00", "cls": ["gabapentinoid", "sedating"], "rxcui": ["25480"]},
    {"key": "alpraz", "group": "sleep-anxiety", "name": "Alprazolam", "tall": "ALPRAZolam", "lasa": "lora", "purpose": "short-acting benzodiazepine for anxiety", "dose": "0.25 mg", "route": "PO", "freq": "TID PRN anxiety", "due": "PRN", "cls": ["benzo"], "rxcui": ["596"]},
    {"key": "clonaz", "group": "sleep-anxiety", "name": "Clonazepam", "tall": "clonazePAM", "lasa": "clonid", "purpose": "long-acting benzodiazepine for anxiety or seizures", "dose": "0.5 mg", "route": "PO", "freq": "BID PRN anxiety", "due": "PRN", "cls": ["benzo"], "rxcui": ["2598"]},
    {"key": "diphen", "group": "sleep-anxiety", "name": "Diphenhydramine", "dose": "25 mg", "route": "PO", "freq": "Nightly PRN sleep", "due": "PRN", "cls": ["antihistamine", "sedating", "anticholinergic"], "rxcui": ["3498"]},
    {"key": "dilt", "group": "rate-bp", "name": "Diltiazem", "dose": "30 mg", "route": "PO", "freq": "q6h", "due": "12:00", "cls": ["CCB", "CCB-nd"], "rxcui": ["3443"]},
    {"key": "carv", "group": "rate-bp", "name": "Carvedilol", "dose": "6.25 mg", "route": "PO", "freq": "BID with food", "due": "12:00", "cls": ["BB", "BB-ns"], "rxcui": ["20352"]},
    {"key": "aten", "group": "rate-bp", "name": "Atenolol", "dose": "25 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["BB"], "rxcui": ["1202"]},
    {"key": "digox", "group": "rate-bp", "name": "Digoxin", "dose": "0.125 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["digoxin"], "rxcui": ["3407"]},
    {"key": "amio", "group": "rate-bp", "name": "Amiodarone", "dose": "200 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["amiodarone", "QT"], "rxcui": ["703"]},
    {"key": "losar", "group": "bp", "name": "Losartan", "dose": "50 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["ARB"], "rxcui": ["52175"]},
    {"key": "amlo", "group": "bp", "name": "Amlodipine", "dose": "5 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["CCB", "CCB-dhp"], "rxcui": ["17767"]},
    {"key": "clonid", "group": "bp", "name": "Clonidine", "tall": "cloNIDine", "lasa": "clonaz", "purpose": "blood pressure medicine", "dose": "0.1 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["alpha2", "sedating"], "rxcui": ["2599"]},
    {"key": "furo", "group": "diuretic", "name": "Furosemide", "dose": "40 mg", "route": "IV", "freq": "BID", "due": "12:00", "cls": ["loop"], "rxcui": ["4603"]},
    {"key": "hctz", "group": "diuretic", "name": "Hydrochlorothiazide", "dose": "25 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["thiazide"], "rxcui": ["5487"]},
    {"key": "spiro", "group": "diuretic", "name": "Spironolactone", "dose": "25 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["Ksparing"], "rxcui": ["9997"]},
    {"key": "kcliv", "group": "potassium", "name": "Potassium chloride IV", "dose": "10 mEq", "route": "IV", "freq": "Once over 1 hour", "due": "12:00", "cls": ["Ksupp"], "rxcui": ["8591"]},
    {"key": "levo", "group": "antibiotic", "name": "Levofloxacin", "dose": "750 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["quinolone", "QT"], "rxcui": ["82122"]},
    {"key": "azith", "group": "antibiotic", "name": "Azithromycin", "dose": "500 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["macrolide", "QT"], "rxcui": ["18631"]},
    {"key": "ceftri", "group": "antibiotic", "name": "Ceftriaxone", "dose": "1 g", "route": "IV", "freq": "Daily", "due": "12:00", "cls": ["cephalosporin"], "rxcui": ["2193"]},
    {"key": "cefaz", "group": "antibiotic", "name": "Cefazolin", "dose": "2 g", "route": "IV", "freq": "q8h", "due": "12:00", "cls": ["cephalosporin"], "rxcui": ["2180"]},
    {"key": "pip", "group": "antibiotic", "name": "Piperacillin-tazobactam", "dose": "4.5 g", "route": "IV", "freq": "q6h", "due": "12:00", "cls": ["penicillin"], "rxcui": ["8339", "37617"]},
    {"key": "vanc", "group": "antibiotic", "name": "Vancomycin", "dose": "1 g", "route": "IV", "freq": "q12h", "due": "12:00", "cls": ["glycopeptide"], "rxcui": ["11124"]},
    {"key": "nitrof", "group": "antibiotic", "name": "Nitrofurantoin", "dose": "100 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["nitrofuran"], "rxcui": ["7454"]},
    {"key": "linez", "group": "antibiotic", "name": "Linezolid", "dose": "600 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["oxazolidinone", "MAOI"], "rxcui": ["190376"]},
    {"key": "clop", "group": "antiplatelet", "name": "Clopidogrel", "dose": "75 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["antiplatelet"], "rxcui": ["32968"]},
    {"key": "hep", "group": "anticoag", "name": "Heparin", "dose": "5000 units", "route": "SC", "freq": "q8h", "due": "12:00", "cls": ["heparin", "anticoag"], "rxcui": ["5224"]},
    {"key": "apix", "group": "anticoag", "name": "Apixaban", "dose": "5 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["DOAC", "anticoag"], "rxcui": ["1364430"]},
    {"key": "riva", "group": "anticoag", "name": "Rivaroxaban", "dose": "20 mg", "route": "PO", "freq": "Daily with evening meal", "due": "17:00", "cls": ["DOAC", "anticoag"], "rxcui": ["1114195"]},
    {"key": "warf", "group": "anticoag", "name": "Warfarin", "dose": "5 mg", "route": "PO", "freq": "Daily", "due": "17:00", "cls": ["warfarin", "anticoag"], "rxcui": ["11289"]},
    {"key": "glarg", "group": "diabetes", "name": "Insulin glargine", "dose": "10 units", "route": "SC", "freq": "Nightly", "due": "21:00", "cls": ["insulin"], "rxcui": ["274783"]},
    {"key": "lispro", "group": "diabetes", "name": "Insulin lispro", "dose": "per sliding scale", "route": "SC", "freq": "AC meals", "due": "12:00", "cls": ["insulin"], "rxcui": ["86009"]},
    {"key": "glyb", "group": "diabetes", "name": "Glyburide", "tall": "glyBURIDE", "lasa": "glip", "purpose": "long-acting diabetes pill (sulfonylurea)", "dose": "5 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["SU", "SU-long"], "rxcui": ["4815"]},
    {"key": "sita", "group": "diabetes", "name": "Sitagliptin", "dose": "100 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["DPP4"], "rxcui": ["593411"]},
    {"key": "empa", "group": "diabetes", "name": "Empagliflozin", "dose": "10 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["SGLT2"], "rxcui": ["1545653"]},
    {"key": "mpred", "group": "steroid", "name": "Methylprednisolone", "dose": "40 mg", "route": "IV", "freq": "q12h", "due": "12:00", "cls": ["steroid"], "rxcui": ["6902"]},
    {"key": "dexa", "group": "steroid", "name": "Dexamethasone", "dose": "6 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["steroid"], "rxcui": ["3264"]},
    {"key": "predl", "group": "steroid", "name": "Prednisolone", "tall": "prednisoLONE", "lasa": "pred", "purpose": "steroid (often the liquid form)", "dose": "40 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["steroid"], "rxcui": ["8638"]},
    {"key": "simva", "group": "statin", "name": "Simvastatin", "dose": "20 mg", "route": "PO", "freq": "Nightly", "due": "21:00", "cls": ["statin", "statin-3A4"], "rxcui": ["36567"]},
    {"key": "rosu", "group": "statin", "name": "Rosuvastatin", "dose": "10 mg", "route": "PO", "freq": "Nightly", "due": "21:00", "cls": ["statin"], "rxcui": ["301542"]},
    {"key": "prava", "group": "statin", "name": "Pravastatin", "dose": "40 mg", "route": "PO", "freq": "Nightly", "due": "21:00", "cls": ["statin"], "rxcui": ["42463"]},
    {"key": "prochl", "group": "nausea", "name": "Prochlorperazine", "dose": "10 mg", "route": "IV", "freq": "q6h PRN nausea", "due": "PRN", "cls": ["dopamine-block", "sedating"], "rxcui": ["8704"]},
    {"key": "prometh", "group": "nausea", "name": "Promethazine", "dose": "12.5 mg", "route": "IV", "freq": "q6h PRN nausea", "due": "PRN", "cls": ["dopamine-block", "sedating", "antihistamine"], "rxcui": ["8745"]},
    {"key": "olanz", "group": "agitation", "name": "Olanzapine", "tall": "OLANZapine", "lasa": "quet", "purpose": "antipsychotic for agitation", "dose": "5 mg", "route": "PO", "freq": "Nightly PRN agitation", "due": "PRN", "cls": ["antipsychotic", "dopamine-block", "sedating"], "rxcui": ["61381"]},
    {"key": "sert", "group": "mood", "name": "Sertraline", "dose": "50 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["SSRI", "serotonergic"], "rxcui": ["36437"]},
    {"key": "escit", "group": "mood", "name": "Escitalopram", "dose": "10 mg", "route": "PO", "freq": "Daily", "due": "12:00", "cls": ["SSRI", "serotonergic", "QT"], "rxcui": ["321988"]},
    {"key": "panto", "group": "stomach", "name": "Pantoprazole", "dose": "40 mg", "route": "IV", "freq": "Daily", "due": "12:00", "cls": ["PPI"], "rxcui": ["40790"]},
    {"key": "famo", "group": "stomach", "name": "Famotidine", "dose": "20 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["H2"], "rxcui": ["4278"]},
    {"key": "levet", "group": "seizure", "name": "Levetiracetam", "dose": "500 mg", "route": "PO", "freq": "BID", "due": "12:00", "cls": ["antiepileptic"], "rxcui": ["114477"]},
]

CATALOG: list[CatalogDrug] = [CatalogDrug(**d) for d in _CATALOG]

# Drug reference card: name prefix -> (class, used for, watch for, nursing notes).
# Lookup is by prefix, so 'metoprolol' also covers 'Metoprolol succinate'.
_INFO: dict[str, tuple[str, str, str, str]] = {
    "hydralazine": ("Vasodilator", "Severe high blood pressure", "Low BP, fast heart rate, headache", "Check BP before and 15–30 min after. Look-alike: hydrOXYzine."),
    "hydroxyzine": ("First-generation antihistamine", "Anxiety, itching", "Sedation, confusion in older adults, QT prolongation", "Beers list for 65+. Look-alike: hydrALAZINE."),
    "trazodone": ("Antidepressant (sedating)", "Sleep", "Drowsiness, low BP when standing, QT prolongation", "Fall precautions. Sound-alike: traMADol."),
    "cephalexin": ("Cephalosporin antibiotic (1st gen)", "Skin and urinary infections", "Rash, diarrhea", "Low cross-reactivity with penicillin allergy."),
    "quetiapine": ("Atypical antipsychotic", "Agitation, delirium (low dose)", "Sedation, low BP, QT prolongation", "Preferred over haloperidol in Parkinson’s disease."),
    "melatonin": ("Sleep supplement", "Trouble sleeping", "Morning drowsiness", "Safer first choice for sleep in older adults."),
    "lisinopril": ("ACE inhibitor", "High blood pressure, heart failure", "Low BP, high potassium, dry cough, face or tongue swelling (angioedema)", "Check BP and potassium before giving. Not for use in pregnancy."),
    "metoprolol": ("Beta-blocker (heart-selective)", "Blood pressure, heart failure, heart rate control", "Slow heart rate, low BP, fatigue", "Check heart rate and BP before giving. Do not stop suddenly."),
    "furosemide": ("Loop diuretic", "Fluid overload, heart failure", "Low potassium, dehydration, low BP", "Daily weight, intake and output, potassium."),
    "spironolactone": ("Potassium-sparing diuretic", "Heart failure", "High potassium", "Check potassium and kidney function."),
    "metformin": ("Biguanide", "Type 2 diabetes", "Stomach upset; rare lactic acidosis", "Hold before IV contrast and when kidney function is below 30."),
    "insulin": ("Rapid-acting insulin · high-alert", "High blood sugar", "Low blood sugar", "Check glucose, give within 15 min of a meal, independent double-check."),
    "enoxaparin": ("Low-molecular-weight heparin · high-alert", "Preventing blood clots", "Bleeding, low platelets", "Check platelets and kidney function. Do not expel the air bubble."),
    "cefazolin": ("Cephalosporin antibiotic (1st gen)", "Skin and soft tissue infections", "Rash, diarrhea", "Low cross-reactivity with penicillin allergy."),
    "warfarin": ("Vitamin K antagonist · high-alert", "Stroke prevention in atrial fibrillation", "Bleeding", "Check INR. Many drug and food (vitamin K) interactions."),
    "diltiazem": ("Calcium channel blocker (rate-slowing)", "Heart rate control, blood pressure", "Slow heart rate, low BP", "Check heart rate and BP. Do not crush ER tablets."),
    "atorvastatin": ("Statin", "High cholesterol", "Muscle pain, liver problems", "Watch for interactions with azole antifungals and some antibiotics."),
    "acetaminophen": ("Analgesic / fever reducer", "Pain, fever", "Liver injury above 4 g a day", "Count every source, including combination pills."),
    "morphine": ("Opioid · high-alert", "Severe pain", "Slowed breathing, sedation, constipation", "Check sedation level, RR and SpO2 before and after. Naloxone at the bedside."),
    "ondansetron": ("5-HT3 antiemetic", "Nausea and vomiting", "QT prolongation, headache, constipation", "Safe antiemetic choice in Parkinson’s disease."),
    "ceftriaxone": ("Cephalosporin antibiotic (3rd gen)", "Pneumonia, PID, other serious infections", "Rash, diarrhea", "Give on schedule to keep levels steady."),
    "azithromycin": ("Macrolide antibiotic", "Pneumonia", "QT prolongation, stomach upset", "Check for other QT-prolonging drugs."),
    "diphenhydramine": ("First-generation antihistamine", "Allergy, sleep", "Sedation, confusion, falls in older adults", "On the Beers list for patients 65+."),
    "prednisone": ("Corticosteroid", "Inflammation, asthma flares", "High blood sugar, mood changes, infection risk", "Give with food. Check glucose in diabetes."),
    "albuterol": ("Short-acting bronchodilator", "Wheezing, bronchospasm", "Fast heart rate, tremor, low potassium", "Check lung sounds and heart rate after."),
    "doxycycline": ("Tetracycline antibiotic", "PID, some STIs, pneumonia", "Esophageal irritation, sun sensitivity", "Take upright with a full glass of water. Avoid in pregnancy."),
    "metronidazole": ("Nitroimidazole antibiotic", "PID, anaerobic infections", "Metallic taste, nausea", "No alcohol during and 3 days after."),
    "labetalol": ("Alpha/beta-blocker", "High blood pressure in pregnancy", "Low BP, slow heart rate, dizziness", "Check BP and heart rate before giving."),
    "nifedipine": ("Calcium channel blocker (dihydropyridine)", "High blood pressure, including pregnancy", "Headache, flushing, low BP", "Do not crush the ER tablet."),
    "prenatal": ("Vitamin and mineral supplement", "Pregnancy", "Constipation, nausea (iron)", "Separate from antacids."),
    "carbidopa": ("Dopamine precursor · time-critical", "Parkinson’s disease", "Nausea, low BP when standing, involuntary movements", "Give within 30 min of the scheduled time. Late doses cause stiffness and swallowing problems."),
    "ampicillin": ("Penicillin + beta-lactamase inhibitor", "Aspiration pneumonia, mixed infections", "Allergy, rash, diarrhea", "Check penicillin allergy first."),
    "pantoprazole": ("Proton pump inhibitor", "Bleeding stomach ulcers", "Headache, diarrhea", "IV push over at least 2 minutes."),
    "piperacillin": ("Penicillin + beta-lactamase inhibitor", "Sepsis, serious infections", "Allergy, diarrhea, kidney effects", "Draw blood cultures first. First dose within 1 hour in sepsis."),
    "vancomycin": ("Glycopeptide antibiotic", "Sepsis, MRSA", "Kidney injury, flushing if infused too fast", "Infuse slowly (at least 60 min per gram). Dosing guided by blood levels."),
    "amoxicillin": ("Penicillin antibiotic", "Ear, sinus, skin infections", "Allergic reactions, diarrhea", "Check penicillin allergy first."),
    "hydrocodone": ("Opioid + acetaminophen · high-alert", "Moderate to severe pain", "Sedation, slowed breathing, liver injury from acetaminophen", "Count total daily acetaminophen."),
    "ibuprofen": ("NSAID", "Pain, fever, inflammation", "Stomach bleeding, kidney injury, higher BP", "Avoid with warfarin, kidney disease, heart failure, GI bleed and late pregnancy."),
    "ketorolac": ("NSAID (IV)", "Short-term moderate to severe pain", "Stomach bleeding, kidney injury", "Maximum 5 days of use."),
    "tramadol": ("Weak opioid · high-alert", "Moderate pain", "Seizures, serotonin syndrome, sedation", "Avoid with other opioids and benzodiazepines."),
    "codeine": ("Opioid + acetaminophen · high-alert", "Mild to moderate pain", "Nausea, sedation; effect varies by person", "Count total acetaminophen."),
    "lorazepam": ("Benzodiazepine", "Anxiety, seizures", "Sedation, slowed breathing, falls", "Never combine with opioids without close monitoring."),
    "zolpidem": ("Sedative-hypnotic", "Short-term insomnia", "Falls, confusion, sleepwalking", "Avoid in older adults when possible."),
    "propranolol": ("Beta-blocker (non-selective)", "Blood pressure, tremor, migraine", "Bronchospasm, slow heart rate", "Contraindicated in asthma."),
    "verapamil": ("Calcium channel blocker (rate-slowing)", "Heart rate control, blood pressure", "Heart block, constipation", "Avoid with beta-blockers and in heart failure."),
    "potassium": ("Electrolyte replacement (IV = high-alert)", "Low potassium", "High potassium, stomach irritation", "Check potassium first. Never give IV push."),
    "trimethoprim": ("Sulfonamide antibiotic", "Urinary and skin infections", "High potassium, raises INR, rash", "Check sulfa allergy first."),
    "ciprofloxacin": ("Fluoroquinolone antibiotic", "Urinary and other infections", "Tendon rupture, QT, confusion", "Boxed warning for tendon damage."),
    "clarithromycin": ("Macrolide antibiotic", "Respiratory infections, H. pylori", "QT prolongation, many drug interactions", "Strongly raises statin levels."),
    "fluconazole": ("Azole antifungal", "Yeast infections", "QT prolongation, liver effects", "Strongly raises warfarin effect."),
    "aspirin": ("Antiplatelet", "Heart attack and stroke prevention", "Bleeding, stomach ulcers", "Avoid in active GI bleeding."),
    "glipizide": ("Sulfonylurea", "Type 2 diabetes", "Low blood sugar", "Higher risk with kidney disease and with insulin."),
    "pioglitazone": ("Thiazolidinedione", "Type 2 diabetes", "Fluid retention, weight gain", "Boxed warning: avoid in heart failure."),
    "metoclopramide": ("Dopamine-blocking antiemetic", "Nausea, slow stomach emptying", "Muscle spasms, restlessness", "Contraindicated in Parkinson’s disease."),
    "haloperidol": ("Antipsychotic", "Agitation, delirium", "Muscle stiffness, QT prolongation", "Avoid in Parkinson’s disease."),
    # ---- backend additions ----
    "naproxen": ("NSAID", "Pain, inflammation", "Stomach bleeding, kidney injury, fluid retention", "Give with food. Same cautions as ibuprofen."),
    "celecoxib": ("NSAID (COX-2 selective)", "Arthritis pain", "Less stomach bleeding than other NSAIDs, but still kidney and heart risks", "Avoid in heart failure and kidney disease."),
    "oxycodone": ("Opioid · high-alert", "Moderate to severe pain", "Sedation, slowed breathing, constipation", "Check sedation and RR. Look-alike: HYDROcodone."),
    "hydromorphone": ("Opioid · high-alert", "Severe pain", "Sedation, slowed breathing", "About 5–7 times stronger than morphine. Look-alike: morphine."),
    "gabapentin": ("Gabapentinoid", "Nerve pain, seizures", "Drowsiness, dizziness, falls", "Dose by kidney function. Adds to opioid sedation."),
    "alprazolam": ("Benzodiazepine (short-acting)", "Anxiety", "Sedation, falls, dependence", "Look-alike: LORazepam. Avoid with opioids."),
    "clonazepam": ("Benzodiazepine (long-acting)", "Anxiety, seizures", "Sedation, falls", "Look-alike: cloNIDine."),
    "carvedilol": ("Beta-blocker (non-selective, alpha-blocking)", "Heart failure, blood pressure", "Slow heart rate, low BP, dizziness", "Give with food. Avoid in asthma."),
    "atenolol": ("Beta-blocker (heart-selective)", "Blood pressure, heart rate control", "Slow heart rate, low BP", "Check heart rate and BP before giving."),
    "digoxin": ("Cardiac glycoside", "Atrial fibrillation rate control, heart failure", "Nausea, vision changes, slow or irregular heartbeat", "Check apical pulse for 1 minute; hold if below 60. Low potassium raises toxicity."),
    "amiodarone": ("Antiarrhythmic", "Atrial fibrillation, ventricular arrhythmias", "Slow heart rate, QT prolongation, thyroid, lung and liver effects", "Many interactions: raises warfarin, digoxin and statin levels."),
    "losartan": ("ARB (angiotensin receptor blocker)", "High blood pressure, kidney protection in diabetes", "Low BP, high potassium, dizziness", "Do not combine with an ACE inhibitor. Not for use in pregnancy."),
    "amlodipine": ("Calcium channel blocker (dihydropyridine)", "High blood pressure", "Ankle swelling, headache, low BP", "Does not slow the heart rate."),
    "hydrochlorothiazide": ("Thiazide diuretic", "High blood pressure", "Low potassium and sodium, dehydration", "Check electrolytes. Give in the morning."),
    "clonidine": ("Central alpha-2 agonist", "High blood pressure, withdrawal symptoms", "Sedation, low BP, rebound high BP if stopped suddenly", "Look-alike: clonazePAM. Do not stop suddenly."),
    "levofloxacin": ("Fluoroquinolone antibiotic", "Pneumonia, urinary infections", "Tendon rupture, QT prolongation, confusion, low blood sugar", "Separate from antacids and iron by 2 hours. Dose by kidney function."),
    "nitrofurantoin": ("Urinary antibiotic", "Bladder infections", "Nausea, lung and liver reactions (rare)", "Avoid when CrCl is below 30 (Beers list). Give with food."),
    "linezolid": ("Oxazolidinone antibiotic", "MRSA, VRE", "Low platelets, serotonin syndrome with antidepressants", "Weak MAO inhibitor: check for SSRIs, tramadol and other serotonergic drugs."),
    "clopidogrel": ("Antiplatelet (P2Y12 inhibitor)", "After heart attack or stent, stroke prevention", "Bleeding, bruising", "Do not stop without asking the cardiologist, especially after a stent."),
    "heparin": ("Unfractionated heparin · high-alert", "Preventing and treating blood clots", "Bleeding, low platelets (HIT)", "Check platelets. Safe in pregnancy and kidney failure."),
    "apixaban": ("Direct oral anticoagulant (factor Xa) · high-alert", "Atrial fibrillation, blood clots", "Bleeding", "No INR monitoring. Hold before procedures per protocol."),
    "rivaroxaban": ("Direct oral anticoagulant (factor Xa) · high-alert", "Atrial fibrillation, blood clots", "Bleeding", "Give with the evening meal. Dose by kidney function."),
    "insulin glargine": ("Long-acting (basal) insulin · high-alert", "Background blood sugar control", "Low blood sugar", "Give at the same time daily. Do not mix with other insulins. Usually given even when NPO (ask the provider)."),
    "glyburide": ("Sulfonylurea (long-acting)", "Type 2 diabetes", "Prolonged low blood sugar", "Avoid in older adults (Beers list). Look-alike: glipiZIDE."),
    "sitagliptin": ("DPP-4 inhibitor", "Type 2 diabetes", "Low risk of low blood sugar; rare pancreatitis", "Dose by kidney function."),
    "empagliflozin": ("SGLT2 inhibitor", "Type 2 diabetes, heart failure, kidney disease", "Genital infections, dehydration, ketoacidosis (rare)", "Hold before surgery and when not eating."),
    "methylprednisolone": ("Corticosteroid (IV)", "Severe inflammation, asthma or COPD flares", "High blood sugar, mood changes, infection risk", "Check glucose."),
    "dexamethasone": ("Corticosteroid (long-acting)", "Inflammation, brain swelling, nausea prevention", "High blood sugar, insomnia, mood changes", "Give in the morning. Check glucose."),
    "prednisolone": ("Corticosteroid", "Inflammation, asthma flares", "High blood sugar, mood changes", "Look-alike: predniSONE."),
    "simvastatin": ("Statin", "High cholesterol", "Muscle pain, liver problems", "Many interactions (clarithromycin, azoles, amiodarone, diltiazem)."),
    "rosuvastatin": ("Statin", "High cholesterol", "Muscle pain", "Few interactions. Lower dose in severe kidney disease."),
    "pravastatin": ("Statin", "High cholesterol", "Muscle pain", "Fewest drug interactions of the statins."),
    "prochlorperazine": ("Dopamine-blocking antiemetic", "Nausea and vomiting", "Sedation, muscle spasms, restlessness", "Avoid in Parkinson’s disease."),
    "promethazine": ("Phenothiazine antihistamine", "Nausea, sedation", "Heavy sedation, tissue injury if IV leaks", "Dilute and give IV slowly into a large vein. Avoid in Parkinson’s disease."),
    "olanzapine": ("Atypical antipsychotic", "Agitation, delirium, psychosis", "Sedation, weight gain, high blood sugar", "Look-alike: QUEtiapine. Avoid in Parkinson’s disease."),
    "sertraline": ("SSRI antidepressant", "Depression, anxiety", "Nausea, low sodium, bleeding risk", "Watch for serotonin syndrome with tramadol or linezolid."),
    "escitalopram": ("SSRI antidepressant", "Depression, anxiety", "QT prolongation, low sodium, bleeding risk", "Check for other QT-prolonging drugs."),
    "famotidine": ("H2 blocker", "Stomach acid, ulcer prevention", "Headache, confusion in older adults or kidney disease", "Dose by kidney function."),
    "levetiracetam": ("Antiepileptic", "Seizures", "Drowsiness, mood changes", "Do not miss doses. Dose by kidney function."),
}

# Longest key first, so a first-prefix-match lookup picks "insulin glargine" over "insulin".
DRUG_INFO: dict[str, dict[str, str]] = {
    k: {"cls": c, "use": u, "watch": w, "nursing": n}
    for k, (c, u, w, n) in sorted(_INFO.items(), key=lambda kv: -len(kv[0]))
}

# Ordering a second drug from one of these classes is flagged as duplicate therapy.
# "opioid" and "anticoag" are warnings (sometimes intended); the rest are critical.
DUPLICATE_CLASSES = [
    "BB", "CCB-nd", "ACEi", "NSAID", "opioid", "anticoag", "statin", "benzo", "steroid", "metformin", "tetracycline",
    # backend additions
    "ARB", "SSRI", "antipsychotic", "SU", "PPI", "loop", "CCB-dhp", "gabapentinoid",
]

# Drug interactions: when the ordered drug has a class in `drug` and the patient already has a
# med with a class in `other`. Text placeholders: {drug} ordered drug, {others} matching meds,
# {k} potassium. Pairs already covered in checker.py code are not repeated here.
INTERACTIONS: list[dict] = [
    # Kidney hormone system / potassium
    {"drug": ["ACEi"], "other": ["ARB"], "sev": "crit", "title": "Dual RAAS blockade with {others}",
     "why": "{drug} and {others} both block the same blood-pressure hormone system. Together they raise the risk of kidney injury, high potassium and low blood pressure, with no added benefit.",
     "action": "Avoid. Use one or the other."},
    {"drug": ["ARB"], "other": ["ACEi"], "sev": "crit", "title": "Dual RAAS blockade with {others}",
     "why": "{drug} and {others} both block the same blood-pressure hormone system. Together they raise the risk of kidney injury, high potassium and low blood pressure, with no added benefit.",
     "action": "Avoid. Use one or the other."},
    {"drug": ["ACEi", "ARB"], "other": ["Ksparing", "Ksupp"], "sev": "warn", "title": "High potassium risk with {others}",
     "why": "{drug} raises potassium, and so does {others}. Current K+ is {k} mmol/L.",
     "action": "Check potassium within 3 days of starting."},
    {"drug": ["Ksparing"], "other": ["ACEi", "ARB", "Ksupp"], "sev": "warn", "title": "High potassium risk with {others}",
     "why": "{drug} keeps potassium in the body, and {others} raises it too. Current K+ is {k} mmol/L.",
     "action": "Check potassium within 3 days of starting."},
    # Digoxin
    {"drug": ["digoxin"], "other": ["amiodarone", "CCB-nd"], "sev": "warn", "title": "Higher digoxin levels with {others}",
     "why": "{others} slows digoxin clearance. Levels can double and cause toxicity (nausea, vision changes, dangerous rhythms).",
     "action": "Start digoxin at a lower dose and check a digoxin level."},
    {"drug": ["amiodarone", "CCB-nd"], "other": ["digoxin"], "sev": "warn", "title": "Raises {others} levels",
     "why": "{drug} slows digoxin clearance. Levels can double and cause toxicity (nausea, vision changes, dangerous rhythms).",
     "action": "Lower the digoxin dose (often by half) and check a digoxin level."},
    # Warfarin (ordering warfarin; the reverse direction is in checker.py)
    {"drug": ["warfarin"], "other": ["azole", "nitroimidazole", "tmpsmx", "amiodarone"], "sev": "crit", "title": "INR will rise with {others}",
     "why": "{others} blocks warfarin breakdown. INR can rise sharply and cause bleeding.",
     "action": "Start warfarin at a lower dose and check INR within 3 days."},
    {"drug": ["warfarin"], "other": ["NSAID"], "sev": "crit", "title": "Bleeding risk with {others}",
     "why": "Warfarin plus {others} raises the risk of serious bleeding, especially from the stomach.",
     "action": "Stop the NSAID or choose a different plan. Use acetaminophen for pain."},
    {"drug": ["warfarin"], "other": ["quinolone", "macrolide-strong"], "sev": "warn", "title": "INR may rise with {others}",
     "why": "{others} can increase the effect of warfarin.", "action": "Check INR within a few days."},
    {"drug": ["amiodarone"], "other": ["warfarin"], "sev": "crit", "title": "Raises INR with {others}",
     "why": "Amiodarone blocks warfarin breakdown. INR rises over 1–2 weeks and stays high for months.",
     "action": "Lower the warfarin dose (often by 30–50%) and check INR weekly."},
    # Bleeding (other anticoagulants, antiplatelets, SSRIs)
    {"drug": ["DOAC", "LMWH", "heparin"], "other": ["NSAID"], "sev": "warn", "title": "Bleeding risk with {others}",
     "why": "{drug} plus {others} raises bleeding risk, especially from the stomach.",
     "action": "Avoid the NSAID if possible; use acetaminophen for pain."},
    {"drug": ["anticoag"], "other": ["antiplatelet"], "sev": "warn", "title": "Bleeding risk with {others}",
     "why": "{drug} plus {others} raises bleeding risk.", "action": "Confirm there is a clear reason for both."},
    {"drug": ["anticoag", "antiplatelet", "NSAID"], "other": ["SSRI"], "sev": "warn", "title": "Bleeding risk with {others}",
     "why": "SSRIs like {others} weaken platelets. Together with {drug} they raise bleeding risk, especially from the stomach.",
     "action": "Watch for bleeding; consider a stomach-protecting drug."},
    {"drug": ["SSRI"], "other": ["anticoag", "antiplatelet", "NSAID"], "sev": "warn", "title": "Bleeding risk with {others}",
     "why": "SSRIs weaken platelets. Together with {others} they raise bleeding risk, especially from the stomach.",
     "action": "Watch for bleeding; consider a stomach-protecting drug."},
    # Serotonin syndrome
    {"drug": ["serotonergic"], "other": ["serotonergic"], "sev": "warn", "title": "Serotonin syndrome risk with {others}",
     "why": "{drug} and {others} both raise serotonin. Too much can cause agitation, fever, fast heart rate and muscle twitching.",
     "action": "Confirm both are needed and watch for symptoms."},
    {"drug": ["serotonergic"], "other": ["MAOI"], "sev": "crit", "title": "Serotonin syndrome with {others}",
     "why": "{others} blocks serotonin breakdown. With {drug} this can cause serotonin syndrome, which can be life-threatening.",
     "action": "Avoid. Choose a different drug."},
    {"drug": ["MAOI"], "other": ["serotonergic"], "sev": "crit", "title": "Serotonin syndrome with {others}",
     "why": "{drug} blocks serotonin breakdown. With {others} this can cause serotonin syndrome, which can be life-threatening.",
     "action": "Avoid, or stop the serotonergic drug first and monitor closely (ask pharmacy)."},
    # Statins broken down by CYP3A4 (the reverse direction for azoles/clarithromycin is in checker.py)
    {"drug": ["statin-3A4"], "other": ["macrolide-strong", "azole", "CCB-nd", "amiodarone"], "sev": "warn", "title": "Higher {drug} levels with {others}",
     "why": "{others} slows the breakdown of {drug}, raising the risk of muscle damage.",
     "action": "Use a lower statin dose, or choose pravastatin or rosuvastatin."},
    {"drug": ["amiodarone"], "other": ["statin-3A4"], "sev": "warn", "title": "Raises {others} levels",
     "why": "Amiodarone slows the breakdown of {others}, raising the risk of muscle damage.",
     "action": "Limit the statin dose, or switch to pravastatin or rosuvastatin."},
    # Heart rate
    {"drug": ["amiodarone"], "other": ["BB", "CCB-nd"], "sev": "warn", "title": "Slow heart rate with {others}",
     "why": "Amiodarone and {others} both slow the heart. Together they can cause bradycardia or heart block.",
     "action": "Check heart rate and ECG, and confirm with the provider."},
    {"drug": ["BB", "CCB-nd"], "other": ["amiodarone"], "sev": "warn", "title": "Slow heart rate with {others}",
     "why": "{drug} and {others} both slow the heart. Together they can cause bradycardia or heart block.",
     "action": "Check heart rate and ECG, and confirm with the provider."},
    # Diabetes (ordering insulin; the reverse direction is in checker.py)
    {"drug": ["insulin"], "other": ["SU"], "sev": "warn", "title": "Low blood sugar risk with {others}",
     "why": "{drug} and {others} both lower blood sugar.", "action": "Confirm the combination and increase fingerstick checks."},
    {"drug": ["insulin"], "other": ["TZD"], "sev": "warn", "title": "Fluid retention with {others}",
     "why": "{others} with insulin raises the risk of swelling and fluid overload.", "action": "Monitor weight and swelling."},
]

# Kidney dosing: catalog key -> [(CrCl below, severity, why, action)], lowest limit first.
# The first matching limit is used. Metformin, enoxaparin, TMP-SMX and glipizide are in checker.py.
RENAL_DOSING: dict[str, list[tuple[int, str, str, str]]] = {
    "levo": [(50, "warn", "Levofloxacin is cleared by the kidneys and builds up at this level.", "Give 750 mg every 48 hours, or ask pharmacy.")],
    "pip": [(40, "warn", "Piperacillin-tazobactam is cleared by the kidneys.", "Reduce to 3.375 g every 6 hours, or ask pharmacy.")],
    "cefaz": [(35, "warn", "Cefazolin is cleared by the kidneys.", "Extend the dosing interval to every 12 hours.")],
    "vanc": [(50, "warn", "Vancomycin builds up when kidney function is low and can injure the kidneys further.", "Ask pharmacy to dose by blood levels.")],
    "nitrof": [(30, "crit", "Nitrofurantoin does not reach the urine well at this level and builds up in the blood (Beers list).", "Choose a different antibiotic.")],
    "gaba": [(30, "warn", "Gabapentin builds up and causes sedation and falls.", "Keep the total dose at or below 700 mg a day."),
             (60, "warn", "Gabapentin builds up and causes sedation and falls.", "Keep the total dose at or below 1,400 mg a day.")],
    "digox": [(50, "warn", "Digoxin is cleared by the kidneys. Levels rise and can cause toxicity.", "Use a lower dose (0.0625 mg daily) and check a level.")],
    "apix": [(25, "warn", "Apixaban builds up at this kidney function and bleeding risk rises.", "Confirm the dose with pharmacy.")],
    "riva": [(15, "crit", "Rivaroxaban should not be used at this kidney function.", "Choose a different anticoagulant."),
             (50, "warn", "Rivaroxaban builds up at this kidney function.", "For atrial fibrillation, use 15 mg daily.")],
    "sita": [(30, "warn", "Sitagliptin is cleared by the kidneys.", "Use 25 mg daily."),
             (45, "warn", "Sitagliptin is cleared by the kidneys.", "Use 50 mg daily.")],
    "empa": [(20, "warn", "Empagliflozin should not be started at this kidney function; it barely lowers glucose.", "Choose a different diabetes medication.")],
    "rosu": [(30, "warn", "Rosuvastatin levels rise with severe kidney disease.", "Start at 5 mg and do not exceed 10 mg a day.")],
    "famo": [(50, "warn", "Famotidine builds up and can cause confusion.", "Reduce to 20 mg once daily.")],
    "levet": [(50, "warn", "Levetiracetam is cleared by the kidneys.", "Reduce the dose; ask pharmacy.")],
    "morph": [(30, "warn", "Morphine's active breakdown products build up and can cause sedation and slowed breathing.", "Use a lower dose, or ask about hydromorphone.")],
    "kcl": [(30, "warn", "The kidneys cannot clear extra potassium well.", "Use a lower dose and recheck potassium.")],
    "kcliv": [(30, "warn", "The kidneys cannot clear extra potassium well.", "Use a lower dose and recheck potassium.")],
}

# Age 65+ cautions (Beers list) by class: (title after "Age N: ", why, action). {drug} = ordered drug.
# Sedatives and NSAIDs are covered in checker.py.
AGE_CAUTIONS: dict[str, tuple[str, str, str]] = {
    "SU-long": ("prolonged low blood sugar (Beers list)", "{drug} can cause long, severe low blood sugar in older adults.", "Choose glipizide or another diabetes medication."),
}

_BY_KEY = {d.key: d for d in CATALOG}


def by_key(key: str) -> Optional[CatalogDrug]:
    return _BY_KEY.get(key)


def drug_info_for(name: str) -> Optional[dict[str, str]]:
    "Reference card for a drug name (\"Metoprolol succinate\" -> the metoprolol card), or None."
    n = name.lower()
    key = next((k for k in DRUG_INFO if n.startswith(k)), None)
    return DRUG_INFO[key] if key else None


def look_alike(drug: CatalogDrug) -> Optional[CatalogDrug]:
    "The drug this one is commonly confused with (ISMP look-alike / sound-alike list), if any."
    return by_key(drug.lasa) if drug.lasa else None
